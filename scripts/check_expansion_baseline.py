#!/usr/bin/env python3
"""Fail closed when Stage 1A's vanilla resource/save contract drifts.

This is a source audit, NOT an importer, C parser, or emulator test. Later stages
must deliberately replace this frozen baseline gate with their new contract.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]


def literal(text, name):
    match = re.search(
        rf"^#define\s+{re.escape(name)}\s+\(?\s*(0x[0-9a-fA-F]+|\d+)\s*\)?\s*(?://.*)?$",
        text, re.MULTILINE,
    )
    if not match:
        raise ValueError(f"{name}: expected a literal integer definition; audit parser needs review")
    return int(match[1], 0)


def audit(root, manifest):
    errors = []
    capacities = manifest["capacities"]
    maps = (root / "include/constants/maps.h").read_text()
    headers = (root / "src/data/map_headers.h").read_text()
    header_type = (root / "include/map_header.h").read_text()
    variables = (root / "include/constants/vars.h").read_text()
    flags = (root / "include/constants/flags.h").read_text()
    count = literal(maps, "MAP_ID_MAX")
    definitions = re.findall(r"^#define\s+(MAP_\w+)\s+(\d+)\s*(?://.*)?$", maps, re.MULTILINE)
    ids = {name: int(value) for name, value in definitions if name != "MAP_ID_MAX"}
    if len(ids) != count or sorted(ids.values()) != list(range(count)):
        errors.append("map IDs must uniquely cover 0..MAP_ID_MAX-1")
    entries = re.findall(r"^\s*\[(MAP_\w+)\]\s*=\s*\{", headers, re.MULTILINE)
    if Counter(entries) != Counter(ids.keys()):
        errors.append("map header entries must cover every map exactly once")
    regions = re.findall(r"\.regionNo\s*=\s*(\w+)\s*,", headers)
    if len(regions) != len(entries) or set(regions) - {"MAP_REGION_JOHTO", "MAP_REGION_KANTO"}:
        errors.append("baseline map headers require one Johto/Kanto region per entry")
    bits = re.search(r"\bregionNo\s*:\s*(\d+)\s*;", header_type)
    if not bits:
        errors.append("regionNo layout changed; manual capacity/ABI audit required")
    observed = {
        "map_count": count,
        "region_bits": int(bits[1]) if bits else None,
        "persistent_flags": literal(flags, "NUM_FLAGS"),
        "variables": literal(variables, "NUM_VARS"),
        "variable_base": literal(variables, "VAR_BASE"),
    }
    for key, expected in capacities.items():
        if observed.get(key) != expected:
            errors.append(f"{key}: expected {expected}, observed {observed.get(key)}")
    for name, expected in manifest["layout_source_sha256"].items():
        if hashlib.sha256((root / name).read_bytes()).hexdigest() != expected:
            errors.append(f"{name}: source changed; review save compatibility before updating baseline")
    return errors, observed


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--rom", type=Path, help="Optional baseline ROM to hash; never uploads it")
    parser.add_argument("--game", choices=("heartgold", "soulsilver"), default="heartgold")
    args = parser.parse_args()
    try:
        manifest = json.loads((args.root / "expansion/baseline.json").read_text())
        errors, observed = audit(args.root, manifest)
        if args.rom:
            digest = hashlib.sha1(args.rom.read_bytes()).hexdigest()
            if digest != manifest["rom_sha1"][args.game]:
                errors.append(f"{args.game} ROM does not match the pinned vanilla SHA-1: {digest}")
        print(json.dumps({"observed": observed, "errors": errors,
                          "rom_checked": args.rom is not None,
                          "runtime_tested": False}, indent=2))
        return bool(errors)
    except (OSError, ValueError, KeyError) as error:
        print(f"Baseline check failed: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())