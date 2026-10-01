#!/usr/bin/env python3
"""Source-only, map-scoped donor state census; not a reachability or allocation proof."""
import argparse
import ast
import hashlib
import json
from pathlib import Path
import re
import subprocess


SCOPE = Path(__file__).resolve().parent / "campaign_scopes/first_badge.json"
IDENT = re.compile(r"\b(?:FLAG_[A-Za-z0-9_]+|VAR_[A-Za-z0-9_]+|TRAINER_[A-Za-z0-9_]+)\b")
LABEL = re.compile(r"^\s*([A-Za-z_]\w*)::?\s*$")
NUM = re.compile(r"^(?:0[xX][0-9a-fA-F]+|[0-9]+)$")
FLOW = re.compile(r"\b(?:goto|call|GoTo|Call|Common_|ScriptEntry|InitScriptEntry)[A-Za-z_0-9]*\b", re.I)
STATE_OP = re.compile(r"(?:flag|var|trainer|badge|special|battle)", re.I)


def operand_mode(op, token, index):
    """Classify actual mutating commands, never a substring of a conditional."""
    command = op.lower()
    if command in ("setflag", "clearflag", "settrainerflag", "cleartrainerflag",
                   "setvar", "addvar", "subvar", "copyvar", "setorcopyvar",
                   "incrementvar", "decrementvar"):
        return "writes" if index == 0 else "reads"
    if token.startswith("TRAINER_") and (
            command.startswith("trainerbattle_") or command == "starttrainerbattle"):
        return "writes"  # trainer defeat is an engine-side effect
    return "reads"


def expression(text, values):
    """Only literal arithmetic and known names; never eval donor source."""
    tree = ast.parse(text.strip(), mode="eval")
    def visit(node):
        if isinstance(node, ast.Constant) and type(node.value) is int:
            return node.value
        if isinstance(node, ast.Name):
            return values[node.id]
        if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Add, ast.Sub, ast.Mod)):
            a, b = visit(node.left), visit(node.right)
            if isinstance(node.op, ast.Add):
                return a + b
            if isinstance(node.op, ast.Sub):
                return a - b
            if b == 0:
                raise ValueError("modulo by zero")
            return a % b
        raise ValueError("unsupported constant expression")
    return visit(tree.body)


def emerald_names(root):
    paths = ["include/constants/opponents.h", "include/constants/flags.h",
             "include/constants/vars.h"]
    values = {}
    for _ in range(5):
        for path in paths:
            for line in (root / path).read_text().splitlines():
                match = re.match(r"^\s*#define\s+(\w+)\s+(.+)", line)
                if match:
                    try:
                        values[match[1]] = expression(match[2].split("//")[0], values)
                    except (ValueError, SyntaxError, KeyError, TypeError):
                        pass
    return values, paths


def platinum_names(root):
    paths = ["generated/vars_flags.txt", "generated/trainers.txt"]
    # Flag zero is followed by the implicit MAP_LOCAL_FLAGS_START marker at 1.
    # FLAG_MAP_LOCAL_0x01 explicitly aliases that marker rather than advancing it.
    values = {"FLAG_UNUSED_0x0000": 0, "MAP_LOCAL_FLAGS_START": 1}
    current = None
    for line in (root / paths[0]).read_text().splitlines():
        line = line.split("//")[0].strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split("=", 1)
        name = parts[0].strip()
        if not re.fullmatch(r"[A-Z][A-Za-z0-9_]*", name):
            continue
        if name == "FLAG_UNUSED_0x0000":
            current = 0
        elif name == "MAP_LOCAL_FLAGS_START":
            current = 1
        elif len(parts) == 2:
            try:
                current = expression(parts[1], values)
            except (ValueError, SyntaxError, KeyError, TypeError):
                current = None
        elif current is not None:
            current += 1
        if current is not None:
            values[name] = current
    for idx, line in enumerate((root / paths[1]).read_text().splitlines()):
        name = line.strip()
        if name.startswith("TRAINER_"):
            values[name] = idx
    return values, paths


def category(name, number, donor):
    if name.startswith("TRAINER_"):
        return "trainer_defeat" if number > 0 else "temporary"
    if name.startswith("VAR_"):
        low = 0x4010 if donor == "emerald" else 0x4020
        high = 0x40ff if donor == "emerald" else 0x4121
        return "variable" if low <= number <= high else "temporary" if (
            0x4000 <= number < low or 0x8000 <= number <= 0x8015) else "outside_saved_namespace"
    if name.startswith("FLAG_"):
        low = 0x20 if donor == "emerald" else 0x41
        high = 0x95f if donor == "emerald" else 0xb5f
        trainer_low = 0x500 if donor == "emerald" else 0x550
        trainer_high = 0x85f if donor == "emerald" else 0x8ef
        if trainer_low <= number <= trainer_high:
            return "trainer_defeat"
        if low <= number <= high:
            return "flag"
        return "temporary" if number < low or 0x4000 <= number <= 0x407f else "outside_saved_namespace"
    return "unknown"


def platinum_dispatch(root, names):
    """Validate a deliberately narrow source-backed hidden-item/common dispatch."""
    header = "include/script_manager.h"
    manager = "src/script_manager.c"
    macro = "asm/macros/scrcmd.inc"
    common = "res/field/scripts/scripts_common.s"
    h, c, m, s = [(root / p).read_text() for p in (header, manager, macro, common)]
    offsets = {}
    for name in ("SCRIPT_ID_OFFSET_COMMON_SCRIPTS", "SCRIPT_ID_OFFSET_BG_EVENTS",
                 "SCRIPT_ID_OFFSET_HIDDEN_ITEMS", "SCRIPT_ID_OFFSET_SAFARI_GAME"):
        match = re.search(r"^#define\s+" + name + r"\s+(\d+)\s*$", h, re.M)
        if not match:
            raise ValueError("unverified script dispatch constant: " + name)
        offsets[name] = int(match[1])
    if not (offsets["SCRIPT_ID_OFFSET_COMMON_SCRIPTS"] <
            offsets["SCRIPT_ID_OFFSET_BG_EVENTS"] <
            offsets["SCRIPT_ID_OFFSET_HIDDEN_ITEMS"] <
            offsets["SCRIPT_ID_OFFSET_SAFARI_GAME"]):
        raise ValueError("unverified script dispatch ranges")
    checks = (
        r"scriptID\s*>=\s*SCRIPT_ID_OFFSET_HIDDEN_ITEMS\s*&&\s*scriptID\s*<=\s*SCRIPT_ID_OFFSET_SAFARI_GAME\s*-\s*1",
        r"return\s+scriptID\s*-\s*SCRIPT_ID_OFFSET_HIDDEN_ITEMS\s*\+\s*HIDDEN_ITEM_FLAGS_START\s*;",
        r"FieldSystem_CheckFlag\s*\(\s*fieldSystem\s*,\s*Script_GetHiddenItemFlag\s*\(\s*bgEvents\[eventIndex\]\.script\s*\)",
        r"ScriptManager_SetHiddenItem\s*\(\s*scriptManager\s*,\s*scriptID\s*\)",
        r"Entry\s*\(\s*SCRIPT_ID_OFFSET_COMMON_SCRIPTS\s*,\s*scripts_common\s*,",
    )
    if not all(re.search(pattern, c) for pattern in checks) or "HIDDEN_ITEM_FLAGS_START" not in names:
        raise ValueError("unverified hidden-item/common script-manager semantics")
    entries = {}
    for match in re.finditer(r"^\s*ScriptEntry\s+(\w+)\s*@\s*(0x[0-9A-Fa-f]+|\d+)\s*$", s, re.M):
        entries[int(match[2], 0)] = match[1]
    if not entries or any(not offsets["SCRIPT_ID_OFFSET_COMMON_SCRIPTS"] <= n <
                          offsets["SCRIPT_ID_OFFSET_BG_EVENTS"] for n in entries):
        raise ValueError("unverified common script-entry table")
    macros = {}
    for match in re.finditer(r"(?ms)^\s*\.macro\s+(\w+)[^\n]*\n(.*?)^\s*\.endm\b", m):
        body = match[2]
        calls = re.findall(r"^\s*CallCommonScript\s+(0x[0-9A-Fa-f]+|\d+)\s*$", body, re.M)
        if calls:
            macros[match[1]] = [int(n, 0) for n in calls]
    return offsets, entries, macros, [header, manager, macro, common]


def census(root, donor, config, scope_path=SCOPE):
    names, definitions = (emerald_names(root) if donor == "emerald" else platinum_names(root))
    files = set(definitions)
    script_paths = []
    event_paths = []
    for name in config["maps"]:
        event = (f"data/maps/{name}/map.json" if donor == "emerald"
                 else f"res/field/events/events_{name}.json")
        script = (f"data/maps/{name}/scripts.inc" if donor == "emerald"
                  else f"res/field/scripts/scripts_{name}.s")
        if not (root / event).is_file() or not (root / script).is_file():
            raise ValueError(f"scope input missing: {root / event} or {root / script}")
        event_paths.append(event)
        script_paths.append(script)
        if donor == "platinum":
            init = f"res/field/scripts/scripts_init_{name}.s"
            if (root / init).is_file():
                script_paths.append(init)
    if not (root / config["badge_evidence"]).is_file():
        raise ValueError("badge evidence missing: " + config["badge_evidence"])
    dispatch = platinum_dispatch(root, names) if donor == "platinum" else None
    if dispatch:
        files.update(dispatch[3])
    files.add(config["badge_evidence"])
    # Shared labels are discovered from source, but only a bounded call closure is traversed.
    common = (sorted((root / "data/scripts").rglob("*.inc")) if donor == "emerald"
              else sorted((root / "res/field/scripts").glob("scripts_common*.s")))
    shared = [p.relative_to(root).as_posix() for p in common]
    if donor == "emerald" and (root / "data/event_scripts.s").exists():
        if (root / "data/event_scripts.s").stat().st_size > 131072:
            raise ValueError("Emerald event_scripts.s exceeds bounded label-index limit")
        shared.append("data/event_scripts.s")
    if donor == "emerald" and (root / "src/event_data.c").exists():
        files.add("src/event_data.c")  # saved-flag map-load lifetime evidence
    labels = {}
    files.update(script_paths)
    files.update(shared)  # label-index provenance, including files with no reached label
    for path in sorted(set(script_paths + shared)):
        lines = (root / path).read_text().splitlines()
        for idx, line in enumerate(lines):
            match = LABEL.match(line.split("@")[0])
            if match:
                labels.setdefault(match[1], []).append((path, idx, lines))
    refs = {}
    unknowns = []
    unknown_keys = set()
    def unknown(kind, path, line, detail):
        key = (kind, path, line, detail)
        if key not in unknown_keys:
            unknown_keys.add(key)
            unknowns.append({"kind": kind, "source": f"{path}:{line}", "detail": detail})
    def record(token, path, line, mode):
        if token not in names:
            unknown("unresolved_id", path, line, token)
            return
        number = names[token]
        kind = category(token, number, donor)
        if kind == "temporary":
            return
        if kind == "outside_saved_namespace":
            unknown("outside_saved_namespace", path, line, token)
            return
        # Platinum trainer scripts have separate saved defeat flags; Emerald flags
        # are at 0x500 + opponent ID. Count only actual IDs, not the entire slice.
        if token.startswith("TRAINER_"):
            number += 0x500 if donor == "emerald" else 0x550
        key = (kind, number)
        refs.setdefault(key, {"category": kind, "id": f"0x{number:04X}",
                              "names": set(), "reads": set(), "writes": set()})
        refs[key]["names"].add(token)
        refs[key][mode].add(f"{path}:{line}")
    def dispatch_script(number, path, line, pending_calls):
        if dispatch is None:
            unknown("unresolved_numeric_script", path, line, str(number))
            return
        offsets, entries, _, _ = dispatch
        if offsets["SCRIPT_ID_OFFSET_HIDDEN_ITEMS"] <= number < offsets["SCRIPT_ID_OFFSET_SAFARI_GAME"]:
            flag = number - offsets["SCRIPT_ID_OFFSET_HIDDEN_ITEMS"] + names["HIDDEN_ITEM_FLAGS_START"]
            if not names["HIDDEN_ITEM_FLAGS_START"] <= flag <= names.get("HIDDEN_ITEM_FLAGS_END", 0x0b5f):
                unknown("hidden_item_flag_out_of_range", path, line, str(number))
                return
            symbols = sorted(n for n, value in names.items()
                             if n.startswith("FLAG_OBTAINED_HIDDEN_") and value == flag)
            if not symbols:
                unknown("hidden_item_flag_unnamed", path, line, str(number))
                return
            record(symbols[0], path, line, "reads")
            record(symbols[0], path, line, "writes")
        elif offsets["SCRIPT_ID_OFFSET_COMMON_SCRIPTS"] <= number < offsets["SCRIPT_ID_OFFSET_BG_EVENTS"]:
            if number in entries:
                pending_calls.add(entries[number])
            else:
                unknown("unresolved_common_script", path, line, str(number))
        else:
            unknown("unresolved_numeric_script", path, line, str(number))
    starts = set()
    for map_name, event in zip(config["maps"], event_paths):
        files.add(event)
        raw = (root / event).read_text()
        data = json.loads(raw)
        # JSON source location for each leaf: match the exact key/value line.
        lines = raw.splitlines()
        def walk(obj, key=""):
            if isinstance(obj, dict):
                for k, v in obj.items():
                    walk(v, k)
            elif isinstance(obj, list):
                for v in obj:
                    walk(v, key)
            elif isinstance(obj, str):
                if key in ("flag", "hidden_flag", "var", "variable", "script"):
                    hits = [i for i, text in enumerate(lines, 1) if json.dumps(obj) in text]
                    at = hits[0] if hits else 1
                    if obj.startswith(("FLAG_", "VAR_", "TRAINER_")):
                        record(obj, event, at, "reads")
                    elif key == "script" and donor == "emerald" and not NUM.fullmatch(obj):
                        starts.add(obj)
                    elif key == "script" and donor == "platinum" and NUM.fullmatch(obj):
                        number = int(obj, 16 if obj.lower().startswith("0x") else 10)
                        if number >= dispatch[0]["SCRIPT_ID_OFFSET_COMMON_SCRIPTS"]:
                            dispatch_script(number, event, at, starts)
                    elif key == "script" and not NUM.fullmatch(obj):
                        unknown("dynamic_script_event", event, at, obj)
            elif key == "script" and isinstance(obj, int) and donor == "platinum":
                # IDs below common-script range index this map's ScriptEntry table;
                # the entire scoped map script is scanned below.
                if obj >= dispatch[0]["SCRIPT_ID_OFFSET_COMMON_SCRIPTS"]:
                    hits = [i for i, text in enumerate(lines, 1)
                            if re.search(r'"script"\s*:\s*' + str(obj) + r'\s*[,}]?', text)]
                    dispatch_script(obj, event, hits[0] if hits else 1, starts)
        walk(data)
    # Map script files contain numbered script entries in Platinum, so inspect
    # every label in each selected file; Emerald map-script tables also seed labels.
    if donor == "platinum":
        for name, locations in labels.items():
            if any(path in script_paths for path, _, _ in locations):
                starts.add(name)
    else:
        for path in script_paths:
            lines = (root / path).read_text().splitlines()
            for line in lines:
                if re.match(r"^\s*(?:map_script|\.2byte|\.4byte)\b", line):
                    starts.update(t for t in re.findall(r"\b[A-Za-z_]\w*\b", line)
                                  if t in labels)
            # Even unlabeled or unreferenced map sections: conservative map overcount.
            starts.update(n for n, locs in labels.items()
                          if any(loc[0] == path for loc in locs))
    pending = sorted(starts)
    visited = set()
    while pending:
        name = pending.pop(0)
        if name in visited:
            continue
        if len(visited) >= 2000:
            unknown("closure_limit", "scope", 0, "2000 script labels; remaining not traversed")
            break
        visited.add(name)
        locs = labels.get(name, [])
        if not locs:
            unknown("unresolved_call", "scope", 0, name)
        if len(locs) > 1:
            unknown("ambiguous_label", locs[0][0], locs[0][1] + 1, name)
        for path, start, lines in locs:
            files.add(path)
            end = start + 1
            while end < len(lines) and not LABEL.match(lines[end].split("@")[0]):
                end += 1
            for idx in range(start + 1, end):
                text = lines[idx].split("@")[0].split("//")[0]
                stripped = text.strip()
                if not stripped or stripped.startswith((".", "#")):
                    continue
                op = re.split(r"[\s(,]+", stripped)[0]
                tokens = IDENT.findall(text)
                for token_index, token in enumerate(tokens):
                    if token.startswith(("FLAG_", "VAR_", "TRAINER_")):
                        record(token, path, idx + 1, operand_mode(op, token, token_index))
                resolved_flow = False
                if FLOW.search(op):
                    operands = [s for s in re.findall(r"\b[A-Za-z_]\w*\b", text[len(op):])
                                if s in labels]
                    pending.extend(operands)
                    resolved_flow = bool(operands)
                if donor == "emerald" and op.lower() == "case":
                    targets = [s for s in re.findall(r"\b[A-Za-z_]\w*\b", text[len(op):])
                               if s in labels]
                    if targets:
                        pending.extend(targets)
                    else:
                        unknown("unresolved_switch_case", path, idx + 1, stripped)
                if donor == "platinum":
                    _, _, macros, _ = dispatch
                    for number in macros.get(op, []):
                        resolved_flow = True  # even an unsupported ID is reported by dispatch
                        new_calls = set()
                        dispatch_script(number, path, idx + 1, new_calls)
                        pending.extend(sorted(new_calls))
                    if op == "CallCommonScript":
                        resolved_flow = True
                        operand = stripped[len(op):].strip().split(",")[0].strip()
                        if NUM.fullmatch(operand):
                            new_calls = set()
                            dispatch_script(int(operand, 16 if operand.lower().startswith("0x") else 10),
                                            path, idx + 1, new_calls)
                            pending.extend(sorted(new_calls))
                        else:
                            unknown("dynamic_common_script", path, idx + 1, stripped)
                if FLOW.search(op) and not resolved_flow and (
                        op.lower().startswith(("call", "goto", "common_"))):
                    unknown("unresolved_call", path, idx + 1, stripped)
                if STATE_OP.search(op) and not tokens and re.search(r"(?:flag|var|trainer|special)", op, re.I):
                    unknown("dynamic_or_c_special", path, idx + 1, stripped)
                if "special" in op.lower() or op.startswith(("CheckBadge", "GiveBadge", "GoToIfBadge")):
                    unknown("c_special_or_non_array_state", path, idx + 1, stripped)
    files.add(config["badge_evidence"])
    # Each reported map has a source path, not merely an implicit name.
    maps = [{"name": name, "event_source": event, "script_source": script,
             "selection_evidence": event}
            for name, event, script in zip(
                config["maps"], event_paths,
                [(f"data/maps/{name}/scripts.inc" if donor == "emerald"
                  else f"res/field/scripts/scripts_{name}.s") for name in config["maps"]])]
    hashes = {path: hashlib.sha256((root / path).read_bytes()).hexdigest()
              for path in sorted(files)}
    values = [{**item, "names": sorted(item["names"]),
               "reads": sorted(item["reads"]), "writes": sorted(item["writes"])}
              for _, item in sorted(refs.items())]
    return {"donor": donor, "revision": subprocess.check_output(
                ["git", "-C", str(root), "rev-parse", "HEAD"], text=True).strip(),
            "git_dirty": bool(subprocess.check_output(
                ["git", "-C", str(root), "status", "--porcelain", "--untracked-files=all"],
                text=True).strip()),
            "source_sha256": hashes, "namespace_allocation": {
                "saved_flags": "0x0020..0x095f" if donor == "emerald" else "0x0041..0x0b5f",
                "saved_vars": "0x4010..0x40ff" if donor == "emerald" else "0x4020..0x4121",
                "trainer_defeat_flags": "0x0500..0x085f" if donor == "emerald" else "0x0550..0x08ef",
                "note": "Allocation ranges are NOT a count of scoped references or host capacity."},
            "scope_selection": config["selection"], "badge_evidence": config["badge_evidence"],
            "maps": maps, "scoped_references": values,
            "reference_census_complete": False,
            "resolved_saved_reference_counts": {category: sum(v["category"] == category for v in values)
                       for category in ("flag", "variable", "trainer_defeat")},
            "unknowns": sorted(unknowns, key=lambda x: (x["source"], x["kind"], x["detail"])),
            "closure_labels_examined": len(visited)}


def report(emerald, platinum, scope_path=SCOPE):
    scope = json.loads(scope_path.read_text())
    if scope["schema_version"] != 1:
        raise ValueError("unsupported scope schema")
    return {"schema_version": 1, "scope": scope["scope"],
            "scope_sha256": hashlib.sha256(scope_path.read_bytes()).hexdigest(),
            "reachability_proven": False, "allocation_approved": False,
            "limitations": [
                "Map-scoped overapproximation: post-badge branches and shared scripts may overcount.",
                "Unresolved C specials, dynamic IDs, and external call targets may undercount.",
                "No complete cross-bank C closure, exact before-badge reachability, save mapping, or host capacity proof.",
                "Only explicit maps/interiors are scanned; other maps, world state and opaque subsystems are outside scope."
            ], "donors": {
                "emerald": census(emerald, "emerald", scope["emerald"], scope_path),
                "platinum": census(platinum, "platinum", scope["platinum"], scope_path)}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--emerald", type=Path, required=True, help="owner-local pokeemerald checkout")
    parser.add_argument("--platinum", type=Path, required=True, help="owner-local pokeplatinum checkout")
    parser.add_argument("--scope", type=Path, default=SCOPE)
    parser.add_argument("--output", type=Path, help="write JSON privately; stdout otherwise")
    args = parser.parse_args()
    for root in (args.emerald, args.platinum):
        if not (root / ".git").exists():
            parser.error(f"expected local git donor checkout: {root}")
    result = report(args.emerald, args.platinum, args.scope)
    text = json.dumps(result, sort_keys=True, indent=2) + "\n"
    if args.output:
        args.output.write_text(text)
    else:
        print(text, end="")


if __name__ == "__main__":
    main()