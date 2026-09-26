#!/usr/bin/env python3
"""Read-only port audit. Does not register species or modify stock game data."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[2]


def revision(repo):
    return subprocess.check_output(["git", "-C", str(repo), "rev-parse", "HEAD"], text=True).strip()


def constants(path, prefix):
    result = {}
    for name, value in re.findall(r"^#define\s+(" + prefix + r"\w+)\s+(0x[0-9a-fA-F]+|[0-9]+)\b", path.read_text(), re.M):
        result[name] = int(value, 0)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--hg-engine", type=Path, default=ROOT.parent / "hg-engine")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    source = args.hg_engine.resolve()
    metadata = json.loads((source / "documentation/fakemon/designs-2026-09/species.json").read_text())
    learnsets = json.loads((source / "data/learnsets/learnsets.json").read_text())
    source_moves = constants(source / "include/constants/moves.h", "MOVE_")
    stock_moves = constants(ROOT / "include/constants/moves.h", "MOVE_")
    stock_by_id = {value: name for name, value in stock_moves.items() if value <= 467}
    machine_names = set(re.findall(r"\bMOVE_\w+", (ROOT / "src/item.c").read_text().split("};", 1)[0]))
    tool_paths = [
        "tools/mwccarm/2.0/sp2p2/mwccarm.exe",
        "tools/mwccarm/2.0/sp2p2/mwasmarm.exe",
        "tools/mwccarm/2.0/sp2p2/mwldarm.exe",
        "tools/mwccarm/1.2/sp2p3/mwasmarm.exe",
        "tools/mwccarm/2.0/sp2p3/mwccarm.exe",
        "tools/mwccarm/2.0/sp2p3/mwasmarm.exe",
        "tools/mwccarm/2.0/sp2p3/mwldarm.exe",
        "tools/mwccarm/license.dat",
        "tools/bin/makerom.exe", "tools/bin/makelcf.exe",
        "tools/bin/makebanner.exe", "tools/bin/ntrcomp.exe",
        "ARM9-TS.lcf.template", "mwldarm.response.template", "sub/ARM7-TS.lcf.template",
    ]
    result = {
        "status": "audit_only_not_integrated",
        "source_revision": revision(source),
        "pokeheartgold_base_revision": subprocess.check_output(["git", "-C", str(ROOT), "merge-base", "HEAD", "master"], text=True).strip(),
        "missing_build_inputs": [name for name in tool_paths if not (ROOT / name).is_file()],
        "wine_available": shutil.which("wine") is not None,
        "approved_balance_constraints": metadata["confirmed_balance_constraints"],
        "approved_growth_transition": metadata["growth_curve_transition"],
        "approved_acquisition_policy": metadata["acquisition_policy"],
        "approved_other_defaults": metadata["remaining_defaults_proposal"],
        "species": [],
    }
    for family in metadata["lines"]:
        for mon in family["designs"]:
            key = mon["key"]
            moves = learnsets["SPECIES_" + key.upper()]
            aliases, unavailable, machine_unavailable = {}, {}, []
            for method, entries in moves.items():
                if not isinstance(entries, list):
                    continue
                missing = []
                for entry in entries:
                    name = entry["Move"] if isinstance(entry, dict) else entry
                    move_id = source_moves.get(name)
                    if move_id not in stock_by_id:
                        missing.append(entry)
                    else:
                        stock_name = stock_by_id[move_id]
                        if stock_name != name:
                            aliases[name] = stock_name
                        if method == "MachineMoves" and stock_name not in machine_names:
                            machine_unavailable.append(name)
                unavailable[method] = missing
            assets = list((source / "data/graphics/sprites" / key).rglob("*.png"))
            assets += [source / "documentation/fakemon/designs-2026-09/cries/drafts" / (key + ".wav")]
            result["species"].append({
                "name": mon["name"], "key": key,
                "source_species_id": mon["engine_species_id"],
                "base_stats": mon["base_stats"], "bst": mon["base_stat_total"],
                "types": mon["types"], "abilities": mon["abilities"],
                "growth_rate": mon["growth_rate"], "ev_yield": mon["ev_yield"],
                "breeding": mon["breeding"],
                "pokedex": mon["pokedex_details"],
                "approved_learnset": moves,
                "stock_move_symbol_aliases": aliases,
                "moves_absent_from_stock_by_method": unavailable,
                "existing_moves_not_on_stock_machines": machine_unavailable,
                "assets": [{"path": str(p.relative_to(source)), "sha256": hashlib.sha256(p.read_bytes()).hexdigest()} for p in sorted(assets)],
            })
    assert len(result["species"]) == 11
    assert all(sum(s["base_stats"].values()) == s["bst"] for s in result["species"])
    text = json.dumps(result, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text)
    else:
        print(text, end="")
    missing_level = sorted({m["Move"] for s in result["species"] for m in s["moves_absent_from_stock_by_method"].get("LevelMoves", [])})
    print(f"Audited 11 species; {len(missing_level)} non-stock level-up moves: {', '.join(missing_level)}", file=__import__("sys").stderr)


if __name__ == "__main__":
    main()
