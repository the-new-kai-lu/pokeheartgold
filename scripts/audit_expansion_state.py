#!/usr/bin/env python3
"""Conservative state-ID evidence inventory, NOT an allocator or ABI proof.

Scans both preprocessor branches of tracked source and every byte offset of
compiled HG/SS script banks. A binary hit may be data, not an operand: false
positives must be reviewed, never silently discarded. Missing banks and computed
accesses remain explicit blockers. No output from this tool authorizes an ID.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess


ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOTS = {"src", "asm", "include", "files"}
SOURCE_SUFFIXES = {".c", ".h", ".s", ".inc", ".json"}
TOKEN = re.compile(r"\b(?:0[xX][0-9a-fA-F]+|[0-9]+)[uUlL]*\b|\b[A-Za-z_]\w*\b")
DEFINE = re.compile(r"^\s*#define\s+([A-Za-z_]\w*)\s+(.+)$")
ACCESS = re.compile(
    r"\b(?:Save_VarsFlags_\w+|FieldSystem_(?:Var|Flag)\w*|"
    r"TrainerFlag\w*|ScriptGetVar(?:Pointer)?|GetVarPointer|"
    r"(?:Get|Set)ScriptVar|"
    r"CheckFlagVar|SetFlagVar|ClearFlagVar)\b"
)


def number(token):
    token = re.sub(r"[uUlL]+$", "", token)
    try:
        # Leading-zero decimal text is conservatively also inventoried.
        return int(token, 16 if token.lower().startswith("0x") else 10)
    except ValueError:
        return None


def tracked_sources(root):
    names = subprocess.check_output(
        ["git", "-C", str(root), "ls-files", "-z"], text=True
    ).split("\0")
    return sorted(
        name for name in names
        if name and Path(name).parts[0] in SOURCE_ROOTS
        and Path(name).suffix in SOURCE_SUFFIXES
    )


def source_evidence(root, paths, candidates):
    lines = []
    digest = hashlib.sha256()
    definitions = []
    for name in paths:
        raw = (root / name).read_bytes()
        digest.update(name.encode() + b"\0" + raw + b"\0")
        for line_no, text in enumerate(raw.decode("utf-8").splitlines(), 1):
            tokens = TOKEN.findall(text)
            definition = DEFINE.match(text)
            record = (name, line_no, text, tokens, definition)
            lines.append(record)
            if definition:
                definitions.append(record)
    result = {}
    for candidate in candidates:
        # Alias closure is deliberately overinclusive (including expressions
        # containing an ID); it does NOT evaluate arbitrary C expressions.
        aliases = set()
        changed = True
        while changed:
            changed = False
            for _, _, _, _, definition in definitions:
                tokens = TOKEN.findall(definition[2])
                if any(number(t) == candidate or t in aliases for t in tokens):
                    if definition[1] not in aliases:
                        aliases.add(definition[1])
                        changed = True
        hits = []
        for name, line_no, text, tokens, definition in lines:
            if definition:
                continue
            if any(number(t) == candidate or t in aliases for t in tokens):
                hits.append({"path": name, "line": line_no, "text": text.strip()})
        result[f"0x{candidate:04X}"] = {"aliases": sorted(aliases), "source_hits": hits}
    accesses = [
        {"path": name, "line": line_no, "text": text.strip()}
        for name, line_no, text, _, definition in lines
        if not definition and ACCESS.search(text)
    ]
    return result, accesses, digest.hexdigest()


def binary_evidence(directory, expected, candidates):
    result = {"complete": False, "missing": [], "unexpected": [], "empty": [],
              "sha256": {}, "hits": {f"0x{x:04X}": [] for x in candidates}}
    if directory is None:
        result["missing"] = sorted(expected)
        return result
    actual = {p.name for p in directory.glob("*.bin")}
    result["missing"] = sorted(expected - actual)
    result["unexpected"] = sorted(actual - expected)
    for name in sorted(actual):
        data = (directory / name).read_bytes()
        if not data:
            result["empty"].append(name)
        result["sha256"][name] = hashlib.sha256(data).hexdigest()
        for candidate in candidates:
            needle = candidate.to_bytes(2, "little")
            offsets = [i for i in range(len(data) - 1) if data[i:i + 2] == needle]
            if offsets:
                result["hits"][f"0x{candidate:04X}"].append(
                    {"path": name, "offsets": offsets})
    result["complete"] = bool(expected) and not any(
        result[key] for key in ("missing", "unexpected", "empty"))
    return result


def audit(root, candidates, heartgold=None, soulsilver=None, paths=None):
    paths = tracked_sources(root) if paths is None else sorted(paths)
    evidence, accesses, digest = source_evidence(root, paths, candidates)
    expected = {
        Path(name).with_suffix(".bin").name for name in paths
        if name.startswith("files/fielddata/script/scr_seq/") and name.endswith(".s")
    }
    builds = {
        "heartgold": binary_evidence(heartgold, expected, candidates),
        "soulsilver": binary_evidence(soulsilver, expected, candidates),
    }
    for key, value in evidence.items():
        value["binary_hits"] = {game: data["hits"][key] for game, data in builds.items()}
        value["literal_reference_found"] = bool(
            value["source_hits"] or any(value["binary_hits"].values()))
    return {
        "schema_version": 1,
        "allocation_approved": False,
        "source_files": len(paths),
        "source_sha256": digest,
        "expected_script_banks_per_game": len(expected),
        "compiled_coverage_complete": all(b["complete"] for b in builds.values()),
        "candidates": evidence,
        "builds": builds,
        "access_sites_requiring_review": accesses,
        "limitations": [
            "Both conditional source branches scanned; source is not preprocessed.",
            "Literals/alias closure cannot prove computed-ID, range, pointer or assembly dataflow safety.",
            "Byte hits are conservative, not decoded operand classifications.",
            "Caller must supply current independently built HG and SS banks; hashes record inputs, not provenance.",
            "Event JSON is scanned, but arbitrary opaque assets and runtime/mystery-gift scripts are not decoded.",
            "Review native access sites, range resets, dynamic script accesses and imported-save semantics before allocation.",
        ],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", type=lambda value: int(value, 0),
                        action="append", required=True,
                        help="persistent variable ID to investigate; repeatable (not a reservation)")
    parser.add_argument("--heartgold", type=Path, help="directory of compiled HG scr_seq *.bin")
    parser.add_argument("--soulsilver", type=Path, help="directory of compiled SS scr_seq *.bin")
    parser.add_argument("--output", type=Path, help="write complete JSON evidence here")
    args = parser.parse_args()
    # The capacity is a contract tripwire, not newly allocated storage.
    baseline = json.loads((ROOT / "expansion/baseline.json").read_text())["capacities"]
    first = baseline["variable_base"]
    if any(not first <= x < first + baseline["variables"] for x in args.candidate):
        parser.error("candidate must be a persistent variable within the baseline save capacity")
    for directory in (args.heartgold, args.soulsilver):
        if directory is not None and not directory.is_dir():
            parser.error(f"compiled script directory does not exist: {directory}")
    report = audit(ROOT, sorted(set(args.candidate)), args.heartgold, args.soulsilver)
    text = json.dumps(report, indent=2) + "\n"
    if args.output:
        args.output.write_text(text)
        print(f"Evidence written to {args.output}; allocation NOT approved.")
        print(f"Compiled coverage complete: {report['compiled_coverage_complete']}; "
              f"native/dynamic access sites to review: {len(report['access_sites_requiring_review'])}")
    else:
        print(text, end="")
    # Fail closed: this inventory has no automatic allocation-success exit.
    # 1 = observed reference; 2 = no literal found but review still required.
    return 1 if any(c["literal_reference_found"] for c in report["candidates"].values()) else 2


if __name__ == "__main__":
    raise SystemExit(main())