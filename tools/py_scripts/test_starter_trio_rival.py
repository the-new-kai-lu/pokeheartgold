#!/usr/bin/env python3
"""Audit every Silver variant and optionally its packaged trainer archives.

Run with Python 3 for source checks; --rom also requires ndspy.  The pinned
parent commit makes preservation checks independent of the edited JSON.
"""
import argparse
import json
import re
import struct
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BASE = "ae05df96b9654803cde5891f9f4cb4a2ec9093ce"
TRAINERS = "files/poketool/trainer/trainers.json"
GROUPS = [
    ([495, 496, 497], [("CHIKORITA", 5), ("CYNDAQUIL", 5), ("TOTODILE", 5)]),
    ([265, 2, 3], [("CHIKORITA", 5), ("CYNDAQUIL", 5), ("TOTODILE", 5)]),
    ([1, 266, 269], [("GASTLY", 14), ("ZUBAT", 16), ("BAYLEEF", 18), ("QUILAVA", 18), ("CROCONAW", 18)]),
    ([263, 267, 270], [("GASTLY", 20), ("MAGNEMITE", 18), ("ZUBAT", 20), ("BAYLEEF", 22), ("QUILAVA", 22), ("CROCONAW", 22)]),
    ([288, 289, 271], [("GOLBAT", 32), ("MAGNEMITE", 30), ("HAUNTER", 32), ("MEGANIUM", 34), ("QUILAVA", 34), ("FERALIGATR", 34)]),
    ([264, 268, 272], [("GOLBAT", 38), ("MAGNETON", 37), ("HAUNTER", 37), ("MEGANIUM", 40), ("TYPHLOSION", 40), ("FERALIGATR", 40)]),
    ([285, 286, 287], [("GOLBAT", 47), ("MAGNETON", 46), ("GENGAR", 48), ("MEGANIUM", 50), ("TYPHLOSION", 50), ("FERALIGATR", 50)]),
    ([489, 490, 491], [("CROBAT", 58), ("MAGNETON", 55), ("GENGAR", 56), ("MEGANIUM", 60), ("TYPHLOSION", 60), ("FERALIGATR", 60)]),
    ([735, 736, 737], [("MEGANIUM", 60), ("TYPHLOSION", 60), ("FERALIGATR", 60), ("CROBAT", 58), ("GENGAR", 56)]),
]
LINES = [
    (["CHIKORITA", "BAYLEEF", "MEGANIUM"], [16, 32]),
    (["CYNDAQUIL", "QUILAVA", "TYPHLOSION"], [14, 36]),
    (["TOTODILE", "CROCONAW", "FERALIGATR"], [18, 30]),
]
TYPES = {"TRTYPE_MON": 0, "TRTYPE_MON_MOVES": 1, "TRTYPE_MON_ITEM": 2, "TRTYPE_MON_ITEM_MOVES": 3}
checks = 0


def check(condition, message):
    global checks
    assert condition, message
    checks += 1


def semantic_party(party):
    return [{k: v for k, v in m.items() if k != "item" or v != "ITEM_NONE"} for m in party]


def literal_constants():
    result = {}
    for name in ["species", "moves", "items", "trainer_class", "trainers"]:
        text = (ROOT / "include/constants" / (name + ".h")).read_text()
        for key, value in re.findall(r"^#define\s+(\w+)\s+(0x[0-9A-Fa-f]+|[0-9]+)\s*(?://.*)?$", text, re.M):
            result[key] = int(value, 0)
    return result


def expected_members(trainer, constants):
    typ = TYPES[trainer["type"]]
    items = [constants[x] for x in trainer["items"]]
    header = struct.pack("<4B4H2I", typ, constants[trainer["class"]], 0, len(trainer["party"]), *(items + [0] * (4 - len(items))), trainer["ai_flags"], trainer["double"])
    party = bytearray()
    for mon in trainer["party"]:
        override = constants[mon["genderOverride"]] | (constants[mon["abilityOverride"]] << 4)
        party.extend(struct.pack("<BBHH", mon["difficulty"], override, mon["level"], constants[mon["species"]]))
        if typ & 2:
            party.extend(struct.pack("<H", constants[mon["item"]]))
        if typ & 1:
            party.extend(struct.pack("<4H", *(constants[x] for x in mon["moves"])))
        party.extend(struct.pack("<H", mon["capsule"]))
    party.extend(b"\x00" * (-len(party) % 4))
    return header, bytes(party)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rom", type=Path)
    args = parser.parse_args()
    original = json.loads(subprocess.check_output(["git", "-C", str(ROOT), "show", BASE + ":" + TRAINERS]))["trainers"]
    current = json.loads((ROOT / TRAINERS).read_text())["trainers"]
    expected_ids = {i for ids, _ in GROUPS for i in ids}
    actual_ids = {i for i, t in enumerate(current) if t["class"] in {"TRAINERCLASS_RIVAL", "TRAINERCLASS_PASSERBY"}}
    check(actual_ids == expected_ids, "Missing or unexpected Silver/Passerby trainer record")
    check(len(original) == len(current), "Trainer count changed")
    for i, trainer in enumerate(current):
        if i not in expected_ids:
            check(trainer == original[i], "Non-Silver trainer changed: " + str(i))
        else:
            check({k: v for k, v in trainer.items() if k != "party"} == {k: v for k, v in original[i].items() if k != "party"}, "Trainer metadata/messages changed: " + str(i))
    for ids, expected_party in GROUPS:
        for trainer_id in ids:
            trainer = current[trainer_id]
            party = trainer["party"]
            check([(m["species"].removeprefix("SPECIES_"), m["level"]) for m in party] == expected_party, "Wrong team: " + str(trainer_id))
            check(1 <= len(party) <= 6, "Party limit: " + str(trainer_id))
            check(semantic_party(party) == semantic_party(current[ids[0]]["party"]), "Legacy starter flag changes team: " + str(trainer_id))
            for names, thresholds in LINES:
                selected = [m for m in party if m["species"].removeprefix("SPECIES_") in names]
                check(len(selected) == 1, "Missing or duplicated starter family")
                mon = selected[0]
                stage = sum(mon["level"] >= threshold for threshold in thresholds)
                check(mon["species"] == "SPECIES_" + names[stage], "Incorrect evolution stage")
                source = next(m for i in ids for m in original[i]["party"] if m["species"] == mon["species"])
                check(mon.get("moves") == source.get("moves"), "Original species-specific starter moves not retained")
                check(mon["level"] == source["level"] or trainer_id in {288, 289, 271} and mon["level"] == 34, "Unexpected starter level change")
            for mon in party:
                check(("moves" in mon) == bool(TYPES[trainer["type"]] & 1), "Move-format mismatch")
                check(("item" in mon) == bool(TYPES[trainer["type"]] & 2), "Item-format mismatch")
                if "moves" in mon:
                    check(len(mon["moves"]) == 4 and all(x.startswith("MOVE_") for x in mon["moves"]), "Invalid custom moveset")
                if "item" in mon:
                    check(mon["item"] == "ITEM_NONE", "Unexpected held item")
    # Audit every named rival/Passerby reference in map scripts, not merely the
    # familiar TRAINERCLASS_RIVAL rows. The initial fight uses Passerby Boy.
    constants_text = (ROOT / "include/constants/trainers.h").read_text()
    id_constants = {k: int(v) for k, v in re.findall(r"#define\s+(TRAINER_\w+)\s+(\d+)", constants_text)}
    referenced = set()
    for path in (ROOT / "files/fielddata/script/scr_seq").glob("*.s"):
        for token in re.findall(r"\bTRAINER_(?:RIVAL_SILVER(?:_\d+)?|PARTNER_RIVAL_\d+|PASSERBY_BOY(?:_\d+)?)\b", path.read_text()):
            referenced.add(id_constants[token])
    check(referenced == expected_ids - {265, 2, 3}, "An actual Silver script encounter is missing from the audit")
    result = {"checks": checks, "trainer_records": 27, "encounter_groups": 9, "source": "passed", "baseline_commit": BASE}
    if args.rom:
        from ndspy.narc import NARC
        from ndspy.rom import NintendoDSRom
        rom = NintendoDSRom(args.rom.read_bytes())
        trdata = NARC(rom.getFileByName("a/0/5/5"))
        trpoke = NARC(rom.getFileByName("a/0/5/6"))
        check(len(trdata.files) == len(current), "Packaged trainer metadata count")
        check(len(trpoke.files) == len(current), "Packaged trainer party count")
        constants = literal_constants()
        for trainer_id in sorted(expected_ids):
            header, party = expected_members(current[trainer_id], constants)
            check(trdata.files[trainer_id] == header, "Packaged metadata mismatch: " + str(trainer_id))
            check(trpoke.files[trainer_id] == party, "Packaged party mismatch: " + str(trainer_id))
        result.update(checks=checks, rom=str(args.rom), packaged_archives="passed")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
