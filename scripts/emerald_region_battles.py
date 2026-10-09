"""Name-based Emerald -> HGSS battle data conversion (never numeric-ID reuse)."""
import json
import re

from census_campaign_state import emerald_names


def brace_body(text, start):
    """Balanced C initializer; braces in quoted strings are not structure."""
    depth, quoted, escaped = 0, False, False
    for i in range(start, len(text)):
        char = text[i]
        if escaped:
            escaped = False
        elif quoted and char == "\\":
            escaped = True
        elif char == '"':
            quoted = not quoted
        elif not quoted:
            if char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
                if depth == 0:
                    return text[start + 1:i]
    raise ValueError("Unterminated C initializer")


class BattleData:
    def __init__(self, donor, source):
        self.donor, self.source = donor, source
        self.names, _ = emerald_names(donor.root)
        self.items = set(re.findall(r"^#define (ITEM_\w+)\s", (
            source / "include/constants/items.h").read_text(), re.M))
        self.species = set(re.findall(r"^#define (SPECIES_\w+)\s", (
            source / "include/constants/species.h").read_text(), re.M))
        self.moves = set(re.findall(r"^#define (MOVE_\w+)\s", (
            source / "include/constants/moves.h").read_text(), re.M))
        self.aliases = dict(re.findall(r"^#define (ITEM_\w+)\s+(ITEM_\w+)\b",
                                      donor.text("include/constants/items.h"), re.M))
        self.aliases.update(ITEM_X_DEFEND="ITEM_X_DEFENSE",
                            ITEM_LAVACOOKIE="ITEM_LAVA_COOKIE",
                            ITEM_PARALYZE_HEAL="ITEM_PARLYZ_HEAL")
        self.native_trainers = json.loads((
            source / "files/poketool/trainer/trainers.json").read_text())
        self.first_trainer = len(self.native_trainers["trainers"])
        self.trainers, self.trainer_report = {}, []

    def item(self, name):
        if name not in self.items:
            name = self.aliases.get(name, name)
        if name not in self.items:
            matches = [n for n in self.items
                       if n.replace("_", "") == name.replace("_", "")]
            if len(matches) == 1:
                name = matches[0]
        if name not in self.items:
            raise ValueError("No native item correspondence: " + name)
        return name

    def trainers_data(self):
        parties = {}
        text = self.donor.text("src/data/trainer_parties.h")
        for match in re.finditer(r"static const struct (\w+) (sParty_\w+)\[\]\s*=\s*\{", text):
            body = brace_body(text, match.end() - 1)
            mons, position = [], 0
            while True:
                start = body.find("{", position)
                if start < 0:
                    break
                mon = brace_body(body, start)
                position = start + len(mon) + 2
                fields = dict(re.findall(r"\.(iv|lvl|species|heldItem)\s*=\s*(\w+)", mon))
                species = fields["species"]
                if species not in self.species:
                    raise ValueError("No native species correspondence: " + species)
                row = dict(difficulty=int(fields["iv"]), level=int(fields["lvl"]),
                           species=species, genderOverride="TRPOKE_GENDER_OVERRIDE_OFF",
                           abilityOverride="TRPOKE_ABILITY_OVERRIDE_OFF", capsule=0)
                if "heldItem" in fields:
                    row["item"] = self.item(fields["heldItem"])
                moves = re.search(r"\.moves\s*=\s*\{([^}]+)\}", mon)
                if moves:
                    aliases = {"MOVE_SELF_DESTRUCT": "MOVE_SELFDESTRUCT",
                               "MOVE_SMOKESCREEN": "MOVE_SMOKE_SCREEN"}
                    row["moves"] = [aliases.get(m.strip(), m.strip())
                                    for m in moves[1].split(",") if m.strip()]
                    if len(row["moves"]) != 4 or any(m not in self.moves for m in row["moves"]):
                        raise ValueError("Unresolved trainer moves: " + match[2])
                if not 1 <= row["level"] <= 100 or not 0 <= row["difficulty"] <= 255:
                    raise ValueError("Trainer party exceeds native field range")
                mons.append(row)
            if not 1 <= len(mons) <= 6:
                raise ValueError("Invalid donor party size: " + match[2])
            parties[match[2]] = mons
        classes = set(re.findall(r"^#define (TRAINERCLASS_\w+)\s", (
            self.source / "include/constants/trainer_class.h").read_text(), re.M))
        text = self.donor.text("src/data/trainers.h")
        by_id = {}
        for match in re.finditer(r"\[(TRAINER_\w+)\]\s*=\s*\{", text):
            if match[1] == "TRAINER_NONE":
                continue
            body = brace_body(text, match.end() - 1)
            donor_id = self.names[match[1]]
            party = re.search(r"\.party\s*=\s*(\w+)\((sParty_\w+)\)", body)
            if not party:
                raise ValueError("Unsupported trainer party declaration: " + match[1])
            mons = parties[party[2]]
            old_class = re.search(r"\.trainerClass\s*=\s*(\w+)", body)[1]
            new_class = old_class.replace("TRAINER_CLASS_", "TRAINERCLASS_")
            female = "F_TRAINER_FEMALE" in body
            if new_class not in classes:
                new_class = {
                    "TRAINER_CLASS_COOLTRAINER": "TRAINERCLASS_ACE_TRAINER_" + ("F" if female else "M"),
                    "TRAINER_CLASS_PKMN_BREEDER": "TRAINERCLASS_PKMN_BREEDER_" + ("F" if female else "M"),
                    "TRAINER_CLASS_SWIMMER_M": "TRAINERCLASS_SWIMMER",
                    "TRAINER_CLASS_SWIMMER_F": "TRAINERCLASS_SWIMMER_F",
                    "TRAINER_CLASS_TEAM_AQUA": "TRAINERCLASS_TEAM_ROCKET",
                    "TRAINER_CLASS_TEAM_MAGMA": "TRAINERCLASS_TEAM_ROCKET",
                }.get(old_class, "TRAINERCLASS_PKMN_TRAINER_LYRA" if female else
                      "TRAINERCLASS_PKMN_TRAINER_ETHAN")
                if new_class not in classes:
                    new_class = "TRAINERCLASS_PKMN_TRAINER_LYRA" if female else "TRAINERCLASS_PKMN_TRAINER_ETHAN"
            held = "item" in mons[0]
            moves = "moves" in mons[0]
            row = dict(
                type="TRTYPE_MON" + ("_ITEM" if held else "") + ("_MOVES" if moves else ""),
                name="{TRNAME}" + re.search(r'\.trainerName\s*=\s*_\("([^"]*)"\)', body)[1].replace("'", "’"),
                items=[self.item(n) for n in re.findall(
                    r"\bITEM_\w+", re.search(r"\.items\s*=\s*\{([^}]*)\}", body)[1])],
                ai_flags=7, double=int(bool(re.search(r"\.doubleBattle\s*=\s*TRUE", body))),
                party=mons, messages=[])
            row["class"] = new_class
            by_id[donor_id] = (match[1], row)
            self.trainer_report.append(dict(donor=match[1], donor_id=donor_id,
                                            native_class=new_class, donor_class=old_class,
                                            ai="stock HGSS flags 7; not Emerald AI"))
        if sorted(by_id) != list(range(1, max(by_id) + 1)):
            raise ValueError("Donor trainer IDs are not contiguous")
        for donor_id, (name, row) in sorted(by_id.items()):
            native_id = len(self.native_trainers["trainers"])
            self.trainers[name] = dict(native_id=native_id, donor_id=donor_id,
                                       flag=0x500 + donor_id)
            self.native_trainers["trainers"].append(row)
        return self.native_trainers

    def encounters_data(self):
        original = json.loads((self.source / "files/fielddata/encountdata/gs_enc_data.json").read_text())
        banks, notes = {}, []
        groups = self.donor.json("src/data/wild_encounters.json")["wild_encounter_groups"]
        encounters = next(g["encounters"] for g in groups if g["label"] == "gWildMonHeaders")
        for row in encounters:
            name = row["map"]
            if name in banks:
                notes.append(dict(map=name, reason="alternate donor encounter table not selected",
                                  label=row.get("base_label")))
                continue

            def water(field):
                data = row.get(field, {"encounter_rate": 0, "mons": []})
                mons = []
                for mon in data["mons"]:
                    if mon["species"] not in self.species:
                        raise ValueError("Unresolved wild species " + mon["species"])
                    mons.append(dict(species=mon["species"], level=dict(
                        min=mon["min_level"], max=mon["max_level"])))
                return dict(rate=data["encounter_rate"], mons=mons)

            land = row.get("land_mons", {"encounter_rate": 0, "mons": []})
            land_mons = []
            for mon in land["mons"]:
                if mon["species"] not in self.species:
                    raise ValueError("Unresolved wild species " + mon["species"])
                land_mons.append(dict(level=mon["max_level"],
                                      species={t: mon["species"] for t in ("morn", "day", "nite")}))
                if mon["min_level"] != mon["max_level"]:
                    notes.append(dict(map=name, reason="native walking slot uses fixed maximum donor level"))
            fishing = water("fishing_mons")
            empty = dict(rate=0, mons=[])
            rods = {}
            for rod, indices in (
                    ("old_rod", (0, 1, 0, 0, 0)),
                    ("good_rod", (2, 3, 4, 3, 4)),
                    ("super_rod", (5, 6, 7, 8, 9))):
                rods[rod] = dict(rate=fishing["rate"], mons=[
                    fishing["mons"][i] for i in indices]) if fishing["mons"] else dict(empty)
            if fishing["mons"]:
                notes.append(dict(map=name, reason="native rod slot probabilities, not exact Emerald fishing odds"))
            if row.get("rock_smash_mons"):
                notes.append(dict(map=name, reason="rock-smash encounter conversion not implemented"))
            encounter = dict(
                map="HOENN_" + name.removeprefix("MAP_"),
                land=dict(rate=land["encounter_rate"], mons=land_mons),
                surf=water("water_mons"), rock_smash=dict(empty), fishing=rods,
                hoenn=["SPECIES_NONE"] * 2, sinnoh=["SPECIES_NONE"] * 2,
                surfSwarm="SPECIES_NONE", nightFish="SPECIES_NONE",
                fishSwarm="SPECIES_NONE")
            # Remaining host-only fields use the existing empty-data schema.
            sample = original["encounters"][0]
            for key in sample:
                if key not in encounter:
                    value = sample[key]
                    if isinstance(value, list):
                        encounter[key] = ["SPECIES_NONE"] * len(value)
                    elif isinstance(value, dict):
                        encounter[key] = {k: "SPECIES_NONE" for k in value}
                    elif isinstance(value, str) and value.startswith("SPECIES_"):
                        encounter[key] = "SPECIES_NONE"
                    else:
                        raise ValueError("Unrecognized native encounter field " + key)
            banks[name] = len(original["encounters"])
            original["encounters"].append(encounter)
        return original, banks, notes
