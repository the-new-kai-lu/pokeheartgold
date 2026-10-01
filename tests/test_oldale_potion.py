"""SOURCE/host verification only. Never opens a ROM/save or runs native gameplay."""

import importlib.util
import csv
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
SPEC = importlib.util.spec_from_file_location("oldale_potion", ROOT / "scripts/prepare_oldale_potion.py")
P = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(P)
R7 = Path(os.environ.get("OLDALE_POTION_R7_SOURCE", "/tmp/hg-oldale-return-exit-r1-after"))
DONOR = Path(os.environ.get("OLDALE_POTION_EMERALD_SOURCE", "/workspace/pokeemerald"))
FOUNDATION = Path(os.environ.get("OLDALE_POTION_CAMPAIGN_SOURCE",
                                "/tmp/hg-campaign-save-v1-bridge-source-r1"))

# Authentic R7 preimages, not a test-only native profile. Their exact hashes are
# checked against the SAME producer profile, also exercised on the real R7 tree.
GIRL = (
    '#include "constants/scrcmd.h"\n.include "asm/macros/script.inc"\n.rodata\n\n'
    'ScrDef Oldale_Girl\nScrDefEnd\n\nOldale_Girl:\nLockAll\nFacePlayer\nNPCMsg 0\n'
    'WaitABPress\nCloseMsg\nReleaseAll\nEnd\n'
)
GIRL_MESSAGE = (
    '<?xml version="1.0"?>\n<body language="English">\n'
    '<row id="msg_0830_00000" index="0"><attribute name="window_context_name">used</attribute>'
    '<language name="English">I want to take a rest, so I’m saving my\\nprogress.</language></row>\n'
    '</body>\n'
)


def fixture():
    girl = dict(id=0, spriteId=8, movement=0, type=0, eventFlag=0, scriptId=1,
                facingDirection=2, param0=0, param1=0, param2=0, xRange=0, yRange=0,
                x=16, z=11, y=0)
    town = dict(bgs=[], coords=[], objects=[girl],
                warps=[dict(x=x, z=z, header=542, anchor=6+i, y=0)
                       for z in (18, 17) for i, x in enumerate((10, 11))])
    return {P.EVENT: (json.dumps(town, indent=2) + "\n").encode(),
            P.SCRIPT: GIRL.encode(), P.MESSAGE: GIRL_MESSAGE.encode(),
            P.MAP_HEADERS: ("/* unrelated header prefix */\n"
                            + P.profile()["oldale_header_entry"] + "\n/* suffix */\n").encode(),
            P.CONTINUE: (ROOT / P.CONTINUE).read_bytes()}


def reader(files):
    def read(name):
        if name not in files:
            raise FileNotFoundError(name)
        return files[name]
    return read


def function(source, name):
    match = re.search(r"^(?:static )?[\w *]+\b" + re.escape(name) + r"\([^;]*?\)\s*\{", source, re.M)
    if not match:
        raise AssertionError(f"Missing actual native function: {name}")
    start = source.index("{", match.start())
    depth, end = 1, start + 1
    while depth:
        depth += (source[end] == "{") - (source[end] == "}")
        end += 1
    return source[match.start():end]


class ScriptHost:
    """Execute the ACTUAL authored commands, with explicit host outcome injection.

    Not an Emerald reducer or a native emulator. Independent native C checks below
    establish the actual bag mutation contract; bridge owns its own host ABI tests.
    """
    def __init__(self, *, received=0, count=0, full=False, read_status=(1, 1),
                 write_status=1, rollback_status=1, facing=1):
        text = (P.TEMPLATES / "oldale_potion_script.s").read_text()
        self.commands, self.labels = [], {}
        self.names = {"VAR_TEMP_x4008": 0x4008, "VAR_TEMP_x4009": 0x4009,
                      "VAR_SPECIAL_RESULT": 0x800C, "ITEM_POTION": 17,
                      "DIR_NORTH": 0, "DIR_SOUTH": 1, "DIR_WEST": 2, "DIR_EAST": 3,
                      "obj_player": 255}
        self.names.update({f"VAR_SPECIAL_x800{i:X}": 0x8000+i for i in range(12)})
        for line in text.splitlines():
            line = line.split("//", 1)[0].strip()
            if line.startswith("#define"):
                _, name, value = line.split()
                self.names[name] = self.value(value)
            elif not line or line.startswith("."):
                continue
            elif line.endswith(":"):
                self.labels[line[:-1]] = len(self.commands)
            else:
                command, _, args = line.partition(" ")
                self.commands.append((command, [a.strip() for a in args.split(",")] if args else []))
        self.vars = {0x4008: 0, 0x4009: 0}
        self.received, self.count, self.full = received, count, full
        self.read_status, self.write_status, self.rollback_status = list(read_status), write_status, rollback_status
        self.facing, self.locked = facing, False
        self.positions = {1: (13, 14), 255: {0: (13, 15), 1: (13, 13), 3: (12, 14), 2: (14, 14)}[facing]}
        self.messages, self.trace, self.moved, self.music = [], [], [], []
        self.grants, self.writes, self.removals = 0, 0, 0
        self.quarantined = False

    def value(self, value):
        return self.names[value] if value in self.names else int(value, 0)

    def operand(self, value):
        number = self.value(value)
        return self.vars.get(number, 0) if number >= 0x4000 else number

    def movement(self, obj, label):
        steps = {"WalkNormalNorth": (0, -1), "WalkNormalSouth": (0, 1),
                 "WalkNormalWest": (-1, 0), "WalkNormalEast": (1, 0)}
        pc, path = self.labels[label], [self.positions[obj]]
        while True:
            cmd, args = self.commands[pc]
            if cmd == "EndMovement":
                break
            if cmd in steps:
                dx, dy = steps[cmd]
                for _ in range(self.value(args[0]) if args else 1):
                    x, y = path[-1]
                    path.append((x+dx, y+dy))
            pc += 1
        self.positions[obj] = path[-1]
        self.moved.append((obj, label, path))

    def run(self, label):
        pc, comparison = self.labels[label], 0
        for _ in range(600):
            cmd, args = self.commands[pc]
            self.trace.append(cmd)
            pc += 1
            if cmd == "End":
                return
            if cmd == "SetVar":
                self.vars[self.value(args[0])] = self.operand(args[1])
            elif cmd == "Compare":
                comparison = self.operand(args[0]) - self.operand(args[1])
            elif cmd.startswith("GoTo"):
                take = (cmd == "GoTo" or cmd == "GoToIfEq" and comparison == 0
                        or cmd == "GoToIfNe" and comparison != 0)
                if take:
                    pc = self.labels[args[0]]
            elif cmd == "CampaignGetFlag":
                assert (self.value(args[0]), self.value(args[1])) == (0, 0x84)
                status = self.read_status.pop(0) if self.read_status else 1
                self.vars[self.value(args[2])] = self.received if status else 0
                self.vars[self.value(args[3])] = status
            elif cmd == "CampaignSetFlag":
                assert (self.value(args[0]), self.value(args[1]), self.operand(args[2])) == (0, 0x84, 1)
                self.writes += 1
                if self.write_status:
                    self.received = 1
                self.vars[self.value(args[3])] = self.write_status
            elif cmd == "GiveItem":
                assert [self.operand(a) for a in args[:2]] == [17, 1]
                self.grants += 1
                self.vars[self.value(args[2])] = 0 if self.full else 1
                if not self.full:
                    self.count += 1
            elif cmd == "TakeItem":
                assert [self.operand(a) for a in args[:2]] == [17, 1]
                self.removals += 1
                self.vars[self.value(args[2])] = self.rollback_status
                if self.rollback_status:
                    self.count -= 1
            elif cmd == "GetPlayerFacing":
                self.vars[self.value(args[0])] = self.facing
            elif cmd == "MovePersonFacing":
                self.positions[self.value(args[0])] = (self.operand(args[1]), self.operand(args[3]))
                assert self.operand(args[2]) == 0
            elif cmd == "ApplyMovement":
                self.movement(self.value(args[0]), args[1])
            elif cmd == "LockAll":
                self.locked = True
            elif cmd == "ReleaseAll":
                self.locked = False
            elif cmd == "NPCMsg":
                self.messages.append(int(args[0]))
            elif cmd in ("PlayBGM", "FadeOutBGM", "ResetBGM", "FadeInBGM"):
                self.music.append(cmd)
            elif cmd == "Wait":
                self.quarantined = True
                return
            elif cmd not in ("FacePlayer", "WaitMovement", "WaitABPress", "CloseMsg",
                              "PlayFanfare", "WaitFanfare", "BufferPlayersName"):
                raise AssertionError(f"Unsupported authored command: {cmd}")
        raise AssertionError("Unexpected script cycle")


class OldalePotionAssets(unittest.TestCase):
    def test_dedicated_templates_are_exact_public_text_sources(self):
        self.assertEqual(P.TEMPLATES, ROOT / "scripts/oldale_potion_templates")
        expected = {
            "oldale_potion_header.s", "oldale_potion_messages.xml",
            "oldale_potion_profile.json", "oldale_potion_script.s",
        }
        self.assertEqual({p.name for p in P.TEMPLATES.iterdir()}, expected)
        for path in P.TEMPLATES.iterdir():
            self.assertTrue(path.is_file() and not path.is_symlink())
            data = path.read_text(encoding="utf-8")
            self.assertNotIn("\0", data)
            self.assertNotIn("/tmp/", data)
            self.assertNotIn("/workspace/", data)
        json.loads((P.TEMPLATES / "oldale_potion_profile.json").read_text())
        ET.fromstring("<body>" + (P.TEMPLATES / "oldale_potion_messages.xml").read_text() + "</body>")

    def test_authentic_fixture_uses_real_r7_preimages_and_exact_scope(self):
        f = fixture()
        for n in (P.EVENT, P.SCRIPT, P.MESSAGE, P.CONTINUE):
            self.assertEqual(P.campaign.sha(f[n]), P.profile()["native_sha256"][n], n)
        before = dict(f)
        edits = P.asset_changes(reader(f))
        self.assertEqual(set(edits), P.SCOPE)
        self.assertEqual(f, before)
        P.verify_asset_delta(reader(f), edits)
        self.assertEqual(edits[P.EVENT].split(b'  "warps":')[1], f[P.EVENT].split(b'  "warps":')[1])
        self.assertIn(GIRL.split("Oldale_Girl:\n")[1].encode(), edits[P.SCRIPT])

    def test_event_script_message_and_callback_bindings(self):
        edits = P.asset_changes(reader(fixture()))
        obj = json.loads(edits[P.EVENT])["objects"][1]
        self.assertEqual((obj["id"], obj["spriteId"], obj["scriptId"], obj["x"], obj["z"],
                          obj["facingDirection"], obj["movement"], obj["eventFlag"]), (1, 24, 2, 13, 7, 1, 0, 0))
        definitions = re.findall(rb"^ScrDef (\w+)$", edits[P.SCRIPT], re.M)
        self.assertEqual(definitions, [b"Oldale_Girl", b"Oldale_MartEmployee",
                                      b"Oldale_PotionOnTransition", b"Oldale_PotionOnEntry"])
        self.assertIn(b"InitScriptEntry_OnTransition 3", edits[P.HEADER])
        self.assertIn(b"InitScriptGoToIfEqual VAR_TEMP_x4009, 1, 4", edits[P.HEADER])
        self.assertIn(b"NARC_scr_seq_scr_seq_0968_oldale_potion_hdr_bin", edits[P.MAP_HEADERS])
        rows = ET.fromstring(edits[P.MESSAGE]).findall("row")
        self.assertEqual([int(r.attrib["index"]) for r in rows], list(range(11)))
        self.assertIn("{STRVAR_1 3, 0, 0}", rows[10].find("language").text)

    def test_donor_normalization_changes_only_pagination_and_apostrophe_typography(self):
        source = 'Text::\n    .string "I\'d say it\'s a POKéMON…\\p"\n    .string "Hi!\\lBye.$"\n'
        self.assertEqual(P.donor_dialogue(source, "Text"), "I’d say it’s a POKéMON…\\rHi!\\nBye.")
        self.assertIn("I'd say it's", source)
        with self.assertRaisesRegex(ValueError, "Missing Emerald dialogue"):
            P.donor_dialogue(source, "Missing")

    def test_all_composed_message_tokens_are_supported_by_unmodified_native_charmap(self):
        # Runs even without a compiler; preserve spaces on the RHS as msgenc does.
        charmap = {}
        for line in (ROOT / "charmap.txt").read_text(encoding="utf-8").splitlines():
            line = line.split("//", 1)[0].lstrip(" \t")
            if line.strip():
                value, token = line.split("=", 1)
                charmap[token] = int(value, 16)
        self.assertEqual(charmap["’"], 0x01B3)
        self.assertNotIn("'", charmap)
        self.assertEqual(charmap["{STRVAR_1}"], 0x0100)
        edits = P.asset_changes(reader(fixture()))
        rows = ET.fromstring(edits[P.MESSAGE]).findall("row")
        self.assertEqual([int(row.attrib["index"]) for row in rows], list(range(11)))
        for row in rows:
            text = row.find("language").text
            tokens = re.findall(r"\{[^{}]*\}|\\.|.", text)
            self.assertEqual("".join(tokens), text)
            for token in tokens:
                if token.startswith("{"):
                    self.assertEqual(token, "{STRVAR_1 3, 0, 0}")
                else:
                    self.assertIn(token, charmap, f"row {row.attrib['index']}: {token!r}")
        self.assertIn("I’d", rows[2].find("language").text)
        self.assertIn("it’s", rows[3].find("language").text)

    @unittest.skipUnless(shutil.which("g++") or shutil.which("c++"), "host C++ compiler unavailable")
    def test_real_source_msgenc_round_trips_all_rows_and_rejects_ascii_apostrophes(self):
        # Build only the repository's open-source host tool, never SDK/native code.
        tool = ROOT / "tools/msgenc"
        makefile = (tool / "Makefile").read_text()
        sources = re.findall(r"^\s*(\w+\.cpp)\s*\\?$", makefile, re.M)
        self.assertEqual(set(sources), {path.name for path in tool.glob("*.cpp")})
        self.assertIn("-std=c++17", makefile)
        composed = P.asset_changes(reader(fixture()))[P.MESSAGE]
        expected = [(row.attrib["index"], row.find("language").text)
                    for row in ET.fromstring(composed).findall("row")]
        self.assertEqual(len(expected), 11)
        with tempfile.TemporaryDirectory(prefix="oldale-msgenc-host-") as tmp:
            base = Path(tmp)
            encoder = base / "msgenc"
            compile_result = subprocess.run(
                [shutil.which("g++") or shutil.which("c++"), "-std=c++17", "-O2", "-Wall",
                 "-Wno-switch", "-Wno-unused-but-set-variable", "-DNDEBUG",
                 *(str(tool / source) for source in sources), "-o", str(encoder)],
                capture_output=True, text=True, timeout=120)
            self.assertEqual(compile_result.returncode, 0, compile_result.stderr)
            source, binary, decoded = base / "messages.gmm", base / "messages.bin", base / "decoded.gmm"
            source.write_bytes(composed)
            encode = [str(encoder), "-e", "--gmm", "-k", "0", "-c", str(ROOT / "charmap.txt")]
            result = subprocess.run([*encode, str(source), str(binary)],
                                    capture_output=True, text=True, timeout=30)
            self.assertEqual(result.returncode, 0, result.stderr)
            result = subprocess.run(
                [str(encoder), "-d", "--gmm", "-c", str(ROOT / "charmap.txt"), str(binary), str(decoded)],
                capture_output=True, text=True, timeout=30)
            self.assertEqual(result.returncode, 0, result.stderr)
            actual = [(row.attrib["index"], row.find("language").text)
                      for row in ET.fromstring(decoded.read_bytes()).findall("row")]
            self.assertEqual(actual, expected)
            # One failure at a time: row2 must not mask the separate row3 defect.
            for curly, ascii_text, encoder_line in (("I’d", "I'd", 3), ("it’s", "it's", 4)):
                with self.subTest(apostrophe=ascii_text):
                    negative = base / f"ascii-row{encoder_line - 1}.gmm"
                    rejected = negative.with_suffix(".bin")
                    self.assertEqual(composed.count(curly.encode()), 1)
                    negative.write_bytes(composed.replace(curly.encode(), ascii_text.encode()))
                    result = subprocess.run([*encode, str(negative), str(rejected)],
                                            capture_output=True, text=True, timeout=30)
                    self.assertNotEqual(result.returncode, 0)
                    self.assertIn("unrecognized character", result.stderr)
                    self.assertIn(f"line {encoder_line} ", result.stderr)
                    self.assertFalse(rejected.exists())

    def test_negative_preimages_append_collision_and_out_of_scope_delta(self):
        for name in (P.EVENT, P.SCRIPT, P.MESSAGE, P.CONTINUE, P.MAP_HEADERS):
            f = fixture()
            f[name] = f[name].replace(b"MAP_OLDALE_TOWN_TRAVEL", b"MAP_CHANGED_OLDALE", 1) if name == P.MAP_HEADERS else f[name] + b"\n"
            with self.assertRaises(ValueError, msg=name):
                P.asset_changes(reader(f))
        f = fixture()
        f[P.HEADER] = b"occupied"
        with self.assertRaises(ValueError):
            P.asset_changes(reader(f))
        f = fixture()
        edits = P.asset_changes(reader(f))
        edits["src/map_events.c"] = b"forbidden warp change"
        with self.assertRaises(ValueError):
            P.verify_asset_delta(reader(f), edits)

    def test_native_entry_environment_and_reload_reset_are_bounded(self):
        native = (ROOT / "src/script_manager.c").read_text()
        self.assertIn("memset(vars, 0, NUM_TEMP_VARS * 2)", function(native, "ClearTempFieldEventData"))
        self.assertIn("ScriptEnvironment_New()", function(native, "StartMapSceneScript"))
        self.assertNotIn("ScriptEnvironment_New()", function(native, "StartMapLoadScript"))
        self.assertIn("TaskManager_GetEnvironment", function(native, "FieldSysGetAttrAddr"))
        f = fixture()
        continue_fn = function(f[P.CONTINUE].decode(), "FieldTask_ContinueGame_Normal")
        self.assertNotIn("INIT_SCRIPT_ON_TRANSITION", continue_fn)
        edits = P.asset_changes(reader(f))
        new_fn = function(edits[P.CONTINUE].decode(), "FieldTask_ContinueGame_Normal")
        self.assertEqual(new_fn.count("INIT_SCRIPT_ON_TRANSITION"), 1)
        self.assertIn("if (fieldSystem->location->mapId == MAP_OLDALE_TOWN_TRAVEL)", new_fn)
        script = (P.TEMPLATES / "oldale_potion_script.s").read_text()
        callback = script.split("Oldale_PotionOnTransition:\n")[1].split("\nEnd", 1)[0]
        self.assertNotIn("Campaign", callback)
        self.assertNotIn("VAR_SPECIAL", callback)
        self.assertEqual(re.findall(r"^SetVar .*", callback, re.M),
                         ["SetVar OLDALE_POTION_TOUR, 0", "SetVar OLDALE_POTION_ENTRY_PENDING, 1"])
        self.assertNotRegex(script, r"Campaign\w+(?:Flag|Var)\s+[^\n]*TEMP")
        self.assertNotRegex(script, r"\b0x416[0-9a-dA-D]\b")
        for bank in ("scr_seq_0149.s", "scr_seq_0003.s"):
            common = (ROOT / "files/fielddata/script/scr_seq" / bank).read_text()
            self.assertNotRegex(common, r"VAR_TEMP_x400[89]\b")

    def test_native_item_sprite_movement_audio_and_opcode_mappings(self):
        for name, symbol, value in (("items.h", "ITEM_POTION", 17), ("sprites.h", "SPRITE_SHOPM1", 24),
                                    ("mmodel.h", "MMODEL_SHOPM1", 23), ("sndseq.h", "SEQ_GS_E_TSURETEKE2", 1087),
                                    ("sndseq.h", "SEQ_ME_ITEM", 1185), ("vars.h", "VAR_SPECIAL_RESULT", 0x800C),
                                    ("vars.h", "VAR_TEMP_x4008", 0x4008), ("vars.h", "VAR_TEMP_x4009", 0x4009)):
            source = (ROOT / "include/constants" / name).read_text()
            actual = re.search(r"^#define " + symbol + r"\s+(\w+)", source, re.M).group(1)
            self.assertEqual(int(actual, 0), value)
        table = (ROOT / "src/data/fieldmap/script_cmd_table.h").read_text().split("gScriptCmdTable[] = {", 1)[1].split("};", 1)[0]
        handlers = re.findall(r"^\s*(ScrCmd_\w+),", table, re.M)
        self.assertEqual(handlers[125:127], ["ScrCmd_GiveItem", "ScrCmd_TakeItem"])
        movement = (ROOT / "asm/macros/movement.inc").read_text()
        self.assertRegex(movement, r"\.macro WalkNormalNorth length=1\s+\.short MOVEMENT_STEP_UP")
        self.assertRegex(movement, r"\.macro Delay16 length=1\s+\.short 65")
        guide = (ROOT / "files/fielddata/script/scr_seq/scr_seq_0850_T21.s").read_text()
        common = (ROOT / "files/fielddata/script/scr_seq/scr_seq_0003.s").read_text()
        self.assertIn("CallStd std_play_follow_music", guide)
        self.assertIn("TempBGM SEQ_GS_E_TSURETEKE2", common.split("scr_seq_0003_037:", 1)[1].split("End", 1)[0])
        with (ROOT / "files/itemtool/itemdata/item_data.csv").open() as source:
            potion = next(row for row in csv.DictReader(source) if row["item"] == "ITEM_POTION")
        self.assertEqual(potion["fieldPocket"], "POCKET_MEDICINE")

    def test_actual_native_vm_delivery_commit_and_rollback_commands_do_not_yield(self):
        vm = function((ROOT / "src/script.c").read_text(), "RunScriptCommand")
        self.assertIn("while (TRUE)", vm)
        self.assertIn("if ((*cmd)(ctx) == TRUE)", vm)
        commands = (ROOT / "src/scrcmd_c.c").read_text()
        for name in ("ScrCmd_CompareVarToValue", "ScrCmd_GoToIf"):
            actual = function(commands, name)
            self.assertIn("return FALSE;", actual)
            self.assertNotIn("return TRUE;", actual)
            self.assertNotIn("SetupNativeScript", actual)
        bridge = (P.campaign.TEMPLATES / "scrcmd_campaign.c").read_text()
        actual = function(bridge, "CampaignWrite")
        self.assertIn("return FALSE;", actual)
        self.assertNotIn("return TRUE;", actual)
        self.assertNotIn("SetupNativeScript", actual)

    def test_source_only_path_guards_and_opt_in_fail_before_production(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            for n in ("episode", "campaign", "donor"):
                (base/n).mkdir()
            with self.assertRaisesRegex(ValueError, "opt-in"):
                P.prepare(base/"episode", base/"campaign", base/"donor", base/"new")
            with self.assertRaisesRegex(ValueError, "fresh"):
                P.prepare(base/"episode", base/"campaign", base/"donor", base/"campaign", author_unapproved=True)
            with self.assertRaisesRegex(ValueError, "overlaps"):
                P.prepare(base/"episode", base/"campaign", base/"donor", base/"episode/new", author_unapproved=True)
            (base/"link").symlink_to(base/"episode", target_is_directory=True)
            with self.assertRaisesRegex(ValueError, "Symlink"):
                P.prepare(base/"link", base/"campaign", base/"donor", base/"new", author_unapproved=True)
            (base/"a").write_bytes(b"x")
            os.link(base/"a", base/"b")
            with self.assertRaisesRegex(ValueError, "hardlinked"):
                P.campaign.read(base/"b")
            self.assertFalse((base/"new").exists())

    @unittest.skipUnless(R7.is_dir(), "actual R7 source not provided")
    def test_actual_r7_native_profile_overlay_and_all_paths(self):
        self.assertGreater(len(P.verify_r7(R7)), 20)
        edits = P.asset_changes(lambda n: P.campaign.read(R7/n))
        self.assertEqual(set(edits), P.SCOPE)
        proof = P.terrain_proof(R7)
        self.assertFalse(proof["terrain_modified"])
        self.assertEqual(proof["land_member"], 679)

    @unittest.skipUnless(DONOR.is_dir(), "Emerald source not provided")
    def test_actual_donor_flag_item_employee_dialogue_and_movements(self):
        self.assertEqual(len(P.verify_donor(DONOR)), 5)
        template_path = P.TEMPLATES / "oldale_potion_messages.xml"
        template = P.campaign.read(template_path)
        real_read = P.campaign.read
        for old, new in (("I’d", "I'd"), ("it’s", "it's"), ("I’d", "I‘d"),
                         ("a promotional item.", "a different item.")):
            with self.subTest(dialogue=new):
                changed = template.replace(old.encode(), new.encode())
                self.assertNotEqual(changed, template)
                with patch.object(P.campaign, "read",
                                  side_effect=lambda path: changed if path == template_path else real_read(path)):
                    with self.assertRaisesRegex(ValueError, "Employee dialogue differs from Emerald"):
                        P.verify_donor(DONOR)
        source = (DONOR / "data/maps/OldaleTown/scripts.inc").read_text()
        translation = {"walk_up": "WalkNormalNorth", "walk_down": "WalkNormalSouth",
                       "walk_left": "WalkNormalWest", "walk_right": "WalkNormalEast",
                       "walk_in_place_faster_down": "WalkOnSpotFasterSouth",
                       "delay_16": "Delay16", "step_end": "EndMovement"}
        host = ScriptHost()
        for who in ("Employee", "Player"):
            for facing in ("East", "South", "North"):
                label = who + facing
                block = re.search(r"OldaleTown_Movement_" + label + r":\n(.*?step_end)", source, re.S).group(1)
                donor_steps = [translation[w.strip()] for w in block.splitlines()]
                pc, native_steps = host.labels["Oldale_Potion" + label], []
                while True:
                    command, args = host.commands[pc]
                    native_steps.extend([command] * (int(args[0]) if args else 1))
                    pc += 1
                    if command == "EndMovement":
                        break
                self.assertEqual(native_steps, donor_steps, label)

    @unittest.skipUnless(R7.is_dir() and DONOR.is_dir() and FOUNDATION.is_dir(),
                         "parent-reviewed R7 campaign+bridge source input not provided")
    def test_fresh_actual_source_composition_complete_inventory_and_unchanged_inputs(self):
        # Only this optional integration test copies actual source assets. It
        # never invokes the campaign producer or reads/builds native binaries.
        foundation_hash = P.campaign.sha(P.campaign.read(FOUNDATION / "campaign-save-source.json"))
        with tempfile.TemporaryDirectory(prefix="oldale-source-host-") as tmp:
            output = Path(tmp) / "candidate"
            report = P.prepare(R7, FOUNDATION, DONOR, output, author_unapproved=True)
            self.assertFalse(report["approved"])
            self.assertFalse(report["runtime_verified"])
            self.assertEqual(set(report["changes"]), P.SCOPE)
            self.assertEqual(len(report["campaign_delta_sha256"]), 11)
            before, after = report["input_source_sha256"], report["candidate_source_sha256"]
            self.assertEqual(set(after), set(before) | {P.HEADER})
            for name, digest in before.items():
                if name not in P.SCOPE:
                    self.assertEqual(after[name], digest, name)
            for name in ("src/map_events.c", "src/unk_02055BF0.c",
                         "files/fielddata/eventdata/zone_event/493_ROUTE_101_TRAVEL.json",
                         "asm/macros/script.inc", "scr_seq.sha1"):
                self.assertEqual(after[name], before[name])
            self.assertEqual(P.campaign.sha(P.campaign.read(output / "campaign-save-source.json")), foundation_hash)
            self.assertEqual(P.campaign.sha(P.campaign.read(FOUNDATION / "campaign-save-source.json")), foundation_hash)
            self.assertEqual(P.campaign.sha(P.campaign.read(output / P.REPORT)),
                             P.campaign.sha((json.dumps(report, indent=2, sort_keys=True) + "\n").encode()))
            with self.assertRaisesRegex(ValueError, "fresh"):
                P.prepare(R7, FOUNDATION, DONOR, output, author_unapproved=True)
            # No compiler/ROM/save output was authored, and generated sources are
            # independent ordinary files rather than symlinks or hardlinks.
            for name in after:
                path = output / name
                self.assertFalse(path.is_symlink())
                self.assertEqual(path.stat().st_nlink, 1)


class OldalePotionBranches(unittest.TestCase):
    def test_each_facing_delivers_once_and_repeat_only_explains(self):
        for direction in (0, 1, 3):
            h = ScriptHost(facing=direction)
            h.run("Oldale_MartEmployee")
            self.assertEqual((h.grants, h.count, h.received, h.writes), (1, 1, 1, 1))
            self.assertEqual(h.positions, {1: (13, 7), 255: (13, 8)})
            self.assertEqual(h.messages, [1, 2, 5, 10, 3])
            self.assertEqual(h.music, ["PlayBGM", "FadeOutBGM", "ResetBGM", "FadeInBGM"])
            self.assertFalse(h.locked)
            moved = len(h.moved)
            h.run("Oldale_MartEmployee")
            self.assertEqual((h.grants, h.count, len(h.moved)), (1, 1, moved))
            self.assertEqual(h.messages[-1], 3)

    def test_existing_receipt_and_map_local_tour_explain_without_reward(self):
        for received, tour in ((1, 0), (0, 1)):
            h = ScriptHost(received=received)
            h.vars[0x4008] = tour
            h.run("Oldale_MartEmployee")
            self.assertEqual((h.grants, h.writes, h.messages, h.moved), (0, 0, [3], []))

    def test_bagfull_unsets_nothing_and_only_reentry_allows_another_tour(self):
        h = ScriptHost(full=True)
        h.run("Oldale_MartEmployee")
        self.assertEqual((h.grants, h.count, h.received, h.writes), (1, 0, 0, 0))
        self.assertEqual(h.messages[-1], 4)
        self.assertEqual(h.vars[0x4008], 1)
        h.full = False
        h.run("Oldale_MartEmployee")
        self.assertEqual(h.count, 0)
        h.run("Oldale_PotionOnTransition")
        self.assertEqual((h.vars[0x4008], h.vars[0x4009]), (0, 1))
        h.run("Oldale_PotionOnEntry")
        self.assertEqual(h.positions[1], (13, 14))
        self.assertEqual(h.vars[0x4009], 0)
        h.positions[255] = (13, 13)
        h.run("Oldale_MartEmployee")
        self.assertEqual((h.count, h.received), (1, 1))

    def test_status_failure_aborts_before_grant_even_with_received_or_zero_output(self):
        for received in (0, 1):
            h = ScriptHost(received=received, read_status=(0,))
            h.run("Oldale_MartEmployee")
            self.assertEqual((h.grants, h.writes, h.messages, h.moved), (0, 0, [6], []))
        h = ScriptHost(read_status=(1, 0))
        h.run("Oldale_MartEmployee")
        self.assertEqual((h.grants, h.writes, h.messages[-1]), (0, 0, 6))
        self.assertIn("ResetBGM", h.music)

    def test_failed_commit_rolls_back_exactly_one_existing_or_new_unit_without_yield(self):
        for existing in (0, 12):
            h = ScriptHost(count=existing, write_status=0)
            h.run("Oldale_MartEmployee")
            self.assertEqual((h.count, h.received, h.removals, h.messages[-1]), (existing, 0, 1, 7))
            self.assertFalse(h.locked)
            sequence = h.trace[h.trace.index("GiveItem"):h.trace.index("TakeItem")+1]
            self.assertEqual(sequence, ["GiveItem", "Compare", "GoToIfNe",
                                        "CampaignSetFlag", "Compare", "GoToIfNe", "TakeItem"])

    def test_impossible_rollback_failure_quarantines_without_release_or_more_rewards(self):
        h = ScriptHost(write_status=0, rollback_status=0)
        h.run("Oldale_MartEmployee")
        self.assertEqual((h.grants, h.writes, h.count, h.received), (1, 1, 1, 0))
        self.assertTrue(h.locked)
        self.assertTrue(h.quarantined)
        self.assertEqual(h.messages[-1], 8)
        self.assertNotIn("ReleaseAll", h.trace[h.trace.index("TakeItem"):])

    def test_reload_positions_received_default_and_unreceived_relocation_not_menu_reset(self):
        for received, position in ((0, (13, 14)), (1, (13, 7))):
            h = ScriptHost(received=received)
            h.vars[0x4008] = 1  # Exactly the stale native temp value saved by HGSS.
            h.run("Oldale_PotionOnTransition")
            h.run("Oldale_PotionOnEntry")
            self.assertEqual((h.vars[0x4008], h.vars[0x4009], h.positions[1]), (0, 0, position))
            self.assertEqual(h.grants, 0)
            h.vars[0x4008] = 1
            # Header's sole frame predicate is4009==1; menu resume re-arms nothing.
            self.assertEqual(h.vars[0x4009], 0)
            self.assertEqual(h.vars[0x4008], 1)

    def test_entry_read_failure_cannot_start_escort_from_unrelocated_default_position(self):
        h = ScriptHost(read_status=(0, 1))
        h.positions[1] = (13, 7)
        h.run("Oldale_PotionOnTransition")
        h.run("Oldale_PotionOnEntry")
        self.assertEqual(h.vars[0x4008], 2)
        h.run("Oldale_MartEmployee")
        self.assertEqual((h.grants, h.writes, h.moved, h.messages), (0, 0, [], [6, 6]))

    def test_unsupported_west_facing_never_silently_grants(self):
        h = ScriptHost(facing=2)
        h.run("Oldale_MartEmployee")
        self.assertEqual((h.grants, h.vars[0x4008], h.messages, h.moved), (0, 0, [9], []))


class OldaleNativeBagHost(unittest.TestCase):
    @unittest.skipUnless(shutil.which("cc"), "host C compiler unavailable")
    def test_actual_native_bag_and_scrcmd_functions_prove_synchronous_rollback(self):
        bag = (ROOT / "src/bag.c").read_text()
        items = (ROOT / "src/scrcmd_items.c").read_text()
        self.assertEqual(P.campaign.sha(bag.encode()), P.profile()["native_sha256"]["src/bag.c"])
        self.assertEqual(P.campaign.sha(items.encode()), P.profile()["native_sha256"]["src/scrcmd_items.c"])
        functions = "\n".join(function(bag, n) for n in (
            "SwapItemSlots", "PocketCompaction", "SortPocket", "Pocket_GetItemSlotForAdd",
            "Bag_GetItemSlotForAdd", "Bag_AddItem", "Pocket_GetItemSlotForRemove",
            "Bag_GetItemSlotForRemove", "Bag_TakeItem"))
        harness = r"""
#include <assert.h>
#include <stdint.h>
#include <stddef.h>
typedef uint16_t u16; typedef uint32_t u32; typedef int32_t s32; typedef int BOOL;
#define TRUE 1
#define FALSE 0
#define ITEM_NONE 0
#define POCKET_MEDICINE 1
#define POCKET_TMHMS 3
#define POCKET_BERRIES 4
#define BAG_SLOT_QUANTITY_MAX 999
#define BAG_TMHM_QUANTITY_MAX 99
enum HeapID { HEAP_ID_FIELD1 };
typedef struct {u16 id, quantity;} ItemSlot;
typedef struct {ItemSlot slots[2];} Bag;
typedef struct {Bag bag;} Save;
typedef struct {Save *saveData;} FieldSystem;
typedef struct {FieldSystem *fieldSystem; u16 operands[3]; u32 pos; u16 result;} ScriptContext;
static u16 ScriptGetVar(ScriptContext *c) { return c->operands[c->pos++]; }
static u16 *ScriptGetVarPointer(ScriptContext *c) { assert(c->operands[c->pos++] == 0x800C); return &c->result; }
static Bag *Save_Bag_Get(Save *s) {return &s->bag;}
static u32 Bag_GetItemPocket(Bag *b,u16 item,ItemSlot **slots,u32 *count,enum HeapID h) {
    (void)h; assert(item == 17); *slots=b->slots; *count=2; return POCKET_MEDICINE;
}
"""
        harness += functions + "\n" + function(items, "ScrCmd_GiveItem") + "\n" + function(items, "ScrCmd_TakeItem")
        harness += r"""
static ScriptContext context(FieldSystem *f) {
    ScriptContext c = {0}; c.fieldSystem=f; c.operands[0]=17; c.operands[1]=1; c.operands[2]=0x800C; return c;
}
int main(void) {
    Save s={0}; FieldSystem f={&s}; ScriptContext c=context(&f);
    assert(ScrCmd_GiveItem(&c)==FALSE && c.result==1 && s.bag.slots[0].quantity==1);
    c=context(&f); assert(ScrCmd_TakeItem(&c)==FALSE && c.result==1 && s.bag.slots[0].quantity==0);
    s.bag.slots[0].id=17; s.bag.slots[0].quantity=12;
    c=context(&f); assert(ScrCmd_GiveItem(&c)==FALSE && c.result==1);
    c=context(&f); assert(ScrCmd_TakeItem(&c)==FALSE && c.result==1 && s.bag.slots[0].quantity==12);
    s.bag.slots[0].quantity=999;
    c=context(&f); assert(ScrCmd_GiveItem(&c)==FALSE && c.result==0 && s.bag.slots[0].quantity==999);
    s.bag.slots[0].id=18; s.bag.slots[1].id=19; s.bag.slots[1].quantity=999;
    c=context(&f); assert(ScrCmd_GiveItem(&c)==FALSE && c.result==0);
    c=context(&f); assert(ScrCmd_TakeItem(&c)==FALSE && c.result==0);
    return 0;
}
"""
        with tempfile.TemporaryDirectory(prefix="oldale-native-host-") as tmp:
            source, binary = Path(tmp)/"host.c", Path(tmp)/"host"
            source.write_text(harness)
            compile_result = subprocess.run(["cc", "-std=c11", "-Wall", "-Wextra", "-Werror",
                                             "-Wno-sign-compare", str(source),
                                             "-o", str(binary)], capture_output=True, text=True)
            self.assertEqual(compile_result.returncode, 0, compile_result.stderr)
            subprocess.run([str(binary)], check=True, capture_output=True)


if __name__ == "__main__":
    unittest.main()