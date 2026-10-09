"""Conservative script conversion for the first bulk region build.

An unsupported reachable operation blocks the *whole* interaction before any
effects occur. Never emit silent no-ops for battles, rewards, C specials or
story transitions. The coverage report is the implementation work list.
"""
import re
import xml.etree.ElementTree as ET

from census_campaign_state import emerald_names


class Unsupported(ValueError):
    pass


class Scripts:
    def __init__(self, donor, battles=None):
        self.blocks, self.locations = {}, {}
        self.battles = battles
        self.names, _ = emerald_names(donor.root)
        for path in sorted((donor.root / "data").rglob("*.inc")):
            current = None
            for number, raw in enumerate(path.read_text().splitlines(), 1):
                label = re.match(r"^(\w+)::?\s*(?:@.*)?$", raw)
                if label:
                    current = label[1]
                    if current in self.blocks:
                        raise ValueError(f"Duplicate donor script label: {current}")
                    self.blocks[current] = []
                    self.locations[current] = f"{path.relative_to(donor.root)}:{number}"
                    continue
                if current:
                    line = raw.strip()
                    if line and not line.startswith(("@", "//")):
                        self.blocks[current].append(line)

    def text(self, label):
        try:
            lines = self.blocks[label]
        except KeyError:
            raise Unsupported("missing text label: " + label) from None
        pieces = []
        for line in lines:
            match = re.fullmatch(r'\.string "(.*)"(?:\s*@.*)?', line)
            if not match:
                if line.startswith((".align ", ".balign ", ".include ")):
                    break
                raise Unsupported("nonliteral text: " + label)
            pieces.append(match[1])
        text = "".join(pieces)
        if not text.endswith("$"):
            raise Unsupported("unterminated text: " + label)
        text = (text[:-1].replace(r"\p", r"\r").replace(r"\l", r"\f")
                .replace("'", "’").replace("{PLAYER}", "{STRVAR_1 3, 0, 0}")
                .replace("{UP_ARROW}", "↑").replace("{DOWN_ARROW}", "↓")
                .replace("{LEFT_ARROW}", "←").replace("{RIGHT_ARROW}", "→"))
        if any(token != "STRVAR_1 3, 0, 0"
               for token in re.findall(r"\{([^}]+)\}", text)):
            raise Unsupported("dynamic text buffer/control: " + label)
        return text

    def flag(self, name):
        try:
            value = int(name, 0)
        except ValueError:
            value = self.names.get(name, -1)
        if not 0x20 <= value < 0x960:
            raise Unsupported("nonpersistent/unresolved flag: " + name)
        return value

    @staticmethod
    def operation(line):
        line = line.split("@", 1)[0].strip()
        parts = line.split(None, 1)
        return parts[0], [a.strip() for a in parts[1].split(",")] if len(parts) > 1 else []

    def closure(self, root, object_flag=0):
        pending, visited = [root], {}
        while pending:
            label = pending.pop()
            if label in visited:
                continue
            if len(visited) >= 128:
                raise Unsupported("script closure exceeds 128 labels")
            if label not in self.blocks:
                raise Unsupported("missing script label: " + label)
            lines = self.blocks[label]
            parsed = []
            terminated = False
            for line in lines:
                if line.startswith((".align ", ".balign ")):
                    continue
                op, args = self.operation(line)
                parsed.append((op, args))
                if op in ("lock", "lockall", "release", "releaseall", "faceplayer",
                          "waitmessage", "waitbuttonpress", "closemessage"):
                    if args:
                        raise Unsupported("unexpected operands: " + op)
                elif op in ("end", "return"):
                    terminated = True
                    break
                elif op in ("goto", "call"):
                    if len(args) != 1:
                        raise Unsupported("dynamic control flow: " + op)
                    pending.append(args[0])
                    if op == "goto":
                        terminated = True
                        break
                elif op in ("goto_if_set", "goto_if_unset"):
                    if len(args) != 2:
                        raise Unsupported("invalid flag branch")
                    self.flag(args[0])
                    pending.append(args[1])
                elif op == "msgbox":
                    if len(args) != 2 or args[1] not in (
                            "MSGBOX_DEFAULT", "MSGBOX_NPC", "MSGBOX_SIGN", "MSGBOX_AUTOCLOSE"):
                        raise Unsupported("message mode: " + ", ".join(args))
                    self.text(args[0])
                elif op == "message":
                    if len(args) != 1:
                        raise Unsupported("dynamic message")
                    self.text(args[0])
                elif op == "special" and args == ["HealPlayerParty"]:
                    pass
                elif op in ("trainerbattle_single", "trainerbattle_double"):
                    expected = 3 if op == "trainerbattle_single" else 4
                    if (len(args) != expected or self.battles is None
                            or args[0] not in self.battles.trainers):
                        raise Unsupported("story/rematch trainer battle: " + ", ".join(args))
                    for text in args[1:]:
                        self.text(text)
                elif op == "finditem":
                    if len(args) not in (1, 2) or not 0x20 <= object_flag < 0x960:
                        raise Unsupported("item pickup needs a persistent donor object flag")
                    if self.battles is None:
                        raise Unsupported("item mapping is unavailable")
                    try:
                        self.battles.item(args[0])
                        quantity = int(args[1], 0) if len(args) > 1 else 1
                        if not 1 <= quantity <= 99:
                            raise ValueError("quantity outside range")
                    except ValueError as error:
                        raise Unsupported(str(error)) from error
                else:
                    raise Unsupported("operation: " + op +
                                      (" " + args[0] if op in ("special", "specialvar") and args else ""))
            if not terminated:
                raise Unsupported("implicit script fallthrough: " + label)
            visited[label] = parsed
        # Native script stack is shallow; do not accept recursion by accident.
        def depth(label, stack, calls):
            if label in stack or calls > 10:
                raise Unsupported("recursive/deep script call graph")
            for op, args in visited[label]:
                if op in ("call", "goto", "goto_if_set", "goto_if_unset"):
                    depth(args[-1], stack + [label], calls + (op == "call"))
        for label in visited:
            depth(label, [], 0)
        return visited


class Bank:
    def __init__(self, scripts, number):
        self.scripts, self.number = scripts, number
        self.messages, self.entries, self.bodies, self.coverage = [], [], [], []
        self.error_message = self.message(
            "This interaction is not converted.\\nSee the import coverage report.")
        self.state_error = self.message("Campaign state could not be read.\\nThe interaction was stopped.")

    def message(self, text):
        if text not in self.messages:
            self.messages.append(text)
        if len(self.messages) > 256:
            raise Unsupported("native NPCMsg bank exceeds 256 messages")
        return self.messages.index(text)

    def raw(self, body):
        name = f"Entry{len(self.entries) + 1}"
        self.entries.append(name)
        self.bodies.append(name + ":\n" + body + "\n")
        return len(self.entries)

    def interaction(self, root, *, face=False, object_flag=0):
        if root in ("0x0", "0", "NULL"):
            return self.raw("End")
        start_messages = len(self.messages)
        entry = len(self.entries) + 1
        prefix = f"Interaction{entry}_"
        try:
            closure = self.scripts.closure(root, object_flag)
            labels = {label: prefix + str(i) for i, label in enumerate(closure)}
            body = ["LockAll", *(["FacePlayer"] if face else []),
                    "BufferPlayersName 0", "Call " + labels[root],
                    "CloseMsg", "ReleaseAll", "End"]
            for label, operations in closure.items():
                body.append(labels[label] + ":")
                for operation_index, (op, args) in enumerate(operations):
                    if op in ("lock", "lockall", "release", "releaseall", "faceplayer"):
                        # One outer lock covers this entire read-only interaction.
                        continue
                    if op in ("waitmessage", "waitbuttonpress"):
                        if op == "waitbuttonpress":
                            body.append("WaitABPress")
                    elif op == "end":
                        body += ["CloseMsg", "ReleaseAll", "End"]
                    elif op == "return":
                        body.append("Return")
                    elif op == "closemessage":
                        body.append("CloseMsg")
                    elif op in ("msgbox", "message"):
                        msg = self.message(self.scripts.text(args[0]))
                        body.append(f"NPCMsg {msg}")
                        if op == "msgbox":
                            body += ["WaitABPress", "CloseMsg"]
                    elif op in ("goto", "call"):
                        body.append(("GoTo " if op == "goto" else "Call ") + labels[args[0]])
                    elif op in ("goto_if_set", "goto_if_unset"):
                        flag = self.scripts.flag(args[0])
                        body += [f"CampaignGetFlag 0, {flag}, 0x800A, 0x800B",
                                 "Compare 0x800B, 1", f"GoToIfNe {prefix}Failure",
                                 "Compare 0x800A, 0",
                                 ("GoToIfNe " if op == "goto_if_set" else "GoToIfEq ") + labels[args[1]]]
                    elif op == "special":
                        body.append("HealParty")
                    elif op in ("trainerbattle_single", "trainerbattle_double"):
                        trainer = self.scripts.battles.trainers[args[0]]
                        after = labels[label] + f"_after_battle{operation_index}"
                        body += [
                            f"CampaignGetFlag 0, {trainer['flag']}, 0x800A, 0x800B",
                            "Compare 0x800B, 1", f"GoToIfNe {prefix}Failure",
                            "Compare 0x800A, 0", "GoToIfNe " + after]
                        if op == "trainerbattle_double":
                            enough = after + "_enough"
                            body += ["PartyCheckForDouble 0x800C", "Compare 0x800C, 1",
                                     "GoToIfEq " + enough,
                                     f"NPCMsg {self.message(self.scripts.text(args[3]))}",
                                     "WaitABPress", "CloseMsg", "ReleaseAll", "End", enough + ":"]
                        body += [f"NPCMsg {self.message(self.scripts.text(args[1]))}",
                                 "WaitABPress", "CloseMsg",
                                 f"TrainerBattle {trainer['native_id']}, 0, 0, 0",
                                 "CheckBattleWon 0x800C", "Compare 0x800C, 1",
                                 "GoToIfEq " + after + "_won", "WhiteOut", "ReleaseAll", "End",
                                 after + "_won:",
                                 f"CampaignSetFlag 0, {trainer['flag']}, 1, 0x800B",
                                 "Compare 0x800B, 1", f"GoToIfNe {prefix}Failure",
                                 f"NPCMsg {self.message(self.scripts.text(args[2]))}",
                                 "WaitABPress", "CloseMsg", after + ":"]
                    elif op == "finditem":
                        item = self.scripts.battles.item(args[0])
                        quantity = int(args[1], 0) if len(args) > 1 else 1
                        base = labels[label] + f"_item{operation_index}"
                        received = self.message("Obtained " + item.removeprefix("ITEM_").replace("_", " ") + "!")
                        full = self.message("The BAG is full.")
                        prior = self.message("This item has already been collected.")
                        rollback = self.message("The receipt could not be saved.\\nThe item was returned.")
                        quarantine = self.message("Item rollback failed.\\nRestart without saving.")
                        body += [
                            f"CampaignGetFlag 0, {object_flag}, 0x800A, 0x800B",
                            "Compare 0x800B, 1", f"GoToIfNe {prefix}Failure",
                            "Compare 0x800A, 0", f"GoToIfNe {base}Prior",
                            f"GiveItem {item}, {quantity}, 0x800C", "Compare 0x800C, 1",
                            f"GoToIfNe {base}Full",
                            f"CampaignSetFlag 0, {object_flag}, 1, 0x800B",
                            "Compare 0x800B, 1", f"GoToIfNe {base}Rollback",
                            f"NPCMsg {received}", f"GoTo {base}Close",
                            f"{base}Prior:", f"NPCMsg {prior}", f"GoTo {base}Close",
                            f"{base}Full:", f"NPCMsg {full}", f"GoTo {base}Close",
                            f"{base}Rollback:", f"TakeItem {item}, {quantity}, 0x800C",
                            "Compare 0x800C, 1", f"GoToIfNe {base}Quarantine",
                            f"NPCMsg {rollback}", f"GoTo {base}Close",
                            f"{base}Quarantine:", f"NPCMsg {quarantine}",
                            "WaitABPress", "CloseMsg", f"{base}Locked:",
                            f"Wait 60, 0x800A", f"GoTo {base}Locked",
                            f"{base}Close:", "WaitABPress", "CloseMsg"]
            body += [prefix + "Failure:", f"NPCMsg {self.state_error}",
                     "WaitABPress", "CloseMsg", "ReleaseAll", "End"]
            status = dict(root=root, status="converted", labels=len(closure))
        except Unsupported as error:
            self.messages[start_messages:] = []
            body = ["LockAll", f"NPCMsg {self.error_message}", "WaitABPress",
                    "CloseMsg", "ReleaseAll", "End"]
            status = dict(root=root, status="blocked-before-execution", reason=str(error))
        self.coverage.append(status)
        return self.raw("\n".join(body))

    def assembly(self):
        if not self.entries:
            self.raw("End")
        return ('#include "constants/scrcmd.h"\n.include "asm/macros/script.inc"\n.rodata\n\n' +
                "\n".join("ScrDef " + entry for entry in self.entries) + "\nScrDefEnd\n\n" +
                "\n".join(self.bodies))

    def gmm(self):
        body = ET.Element("body", language="English")
        for i, text in enumerate(self.messages):
            row = ET.SubElement(body, "row", id=f"msg_{self.number:04}_{i:05}", index=str(i))
            ET.SubElement(row, "attribute", name="window_context_name").text = "used"
            ET.SubElement(row, "language", name="English").text = text
        return ET.tostring(body, encoding="utf-8", xml_declaration=True)
