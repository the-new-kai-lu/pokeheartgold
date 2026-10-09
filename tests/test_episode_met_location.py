"""Bounded host checks for opt-in memo writes, not ROM/save/editor validation."""
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from prepare_emerald_episode import native_edits

MEMO = "src/trainer_memo.c"
SECTIONS = "include/constants/map_sections.h"
NAMES = (MEMO, SECTIONS)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def extract(source, name):
    start = re.search(
        r"^(?:static )?void " + re.escape(name) + r"\([^;{]*\)\s*\{",
        source, re.M
    )
    if start is None:
        raise AssertionError(f"Missing source function: {name}")
    opening = source.index("{", start.start())
    depth = 1
    end = opening + 1
    while depth:
        depth += (source[end] == "{") - (source[end] == "}")
        end += 1
    return source[start.start():end]


HARNESS = r"""
#include <assert.h>
#include <stdint.h>
#include <string.h>
typedef uint16_t u16;
typedef uint32_t u32;
typedef int BOOL;
enum HeapID { HEAP_ID_FIELD2 };
#define TRUE 1
#define FALSE 0
#define MAPSECTYPE_NORMAL 0
#define MAPSECTYPE_GIFT 1
#define MAPSECTYPE_EXTERNAL 2
#define SETMETDATEPARAM_EGG 0
#define SETMETDATEPARAM_MON 1
/* SECTION_CONSTANTS */
enum {
    MON_DATA_IS_EGG, MON_DATA_EGG_LOCATION, MON_DATA_EGG_YEAR,
    MON_DATA_EGG_MONTH, MON_DATA_EGG_DAY, MON_DATA_MET_LOCATION,
    MON_DATA_MET_YEAR, MON_DATA_MET_MONTH, MON_DATA_MET_DAY,
    MON_DATA_MET_LEVEL, MON_DATA_LEVEL, MON_DATA_OT_ID,
    MON_DATA_OT_GENDER, MON_DATA_OT_NAME_STRING,
    MON_DATA_FATEFUL_ENCOUNTER, FIELD_COUNT
};
typedef struct { int year, month, day; } RTCDate;
typedef struct { int fields[FIELD_COUNT]; } BoxPokemon;
typedef struct { int id, gender; } PlayerProfile;
typedef struct { int marker; } String;
static String name_string;
static int rtc_calls, writes, written_fields[32], written_values[32];
static void GF_RTC_CopyDate(RTCDate *date) {
    rtc_calls++; *date = (RTCDate){2025, 8, 16};
}
static void SetBoxMonData(BoxPokemon *mon, int field, const void *value) {
    assert(field >= 0 && field < FIELD_COUNT && writes < 32);
    /* A name is a String pointer, not an integer pointer. */
    int val = field == MON_DATA_OT_NAME_STRING ? 999 : *(const int *)value;
    mon->fields[field] = val;
    written_fields[writes] = field; written_values[writes++] = val;
}
static int GetBoxMonData(BoxPokemon *mon, int field, void *unused) {
    (void)unused; assert(field >= 0 && field < FIELD_COUNT);
    return mon->fields[field];
}
static int sub_02017FE4(int type, int loc) {
    assert(type == MAPSECTYPE_NORMAL || type == MAPSECTYPE_GIFT ||
           type == MAPSECTYPE_EXTERNAL);
    /* asm/unk_02017FAC.s: _020F6280[type] + offset. */
    const int bases[] = {MAPSEC_MYSTERY_ZONE, METLOC_DAY_CARE_COUPLE,
                         METLOC_LOVELY_PLACE};
    return bases[type] + loc;
}
static int BoxmonBelongsToPlayer(BoxPokemon *mon, PlayerProfile *profile, enum HeapID heap) {
    (void)mon; (void)heap; return profile->id == 12;
}
static u32 PlayerProfile_GetTrainerID(PlayerProfile *profile) { return profile->id; }
static u32 PlayerProfile_GetTrainerGender(PlayerProfile *profile) { return profile->gender; }
static String *PlayerProfile_GetPlayerName_NewString(PlayerProfile *profile, enum HeapID heap) {
    (void)profile; (void)heap; return &name_string;
}
static void String_Delete(String *name) { assert(name == &name_string); }
/* PRODUCTION_FUNCTIONS */
static void reset(BoxPokemon *mon) {
    memset(mon, 0, sizeof(*mon));
    for (int i = 0; i < FIELD_COUNT; i++) mon->fields[i] = 100 + i;
    writes = rtc_calls = 0;
}
static void check_helper(int loc, int param) {
    BoxPokemon old, staged;
    reset(&old);
    staged = old;
    Original_SetMetDateAndLocation(&old, loc, param);
    assert(rtc_calls == 1 && writes == 4);
    int old_fields[4], old_values[4];
    memcpy(old_fields, written_fields, sizeof(old_fields));
    memcpy(old_values, written_values, sizeof(old_values));
    writes = rtc_calls = 0;
    BoxMon_SetMetDateAndLocation(&staged, loc, param);
    assert(rtc_calls == 1 && writes == 4);
    int expected = (loc == MAPSEC_LITTLEROOT_TOWN || loc == MAPSEC_ROUTE_101)
                   ? METLOC_HOENN : loc;
    for (int i = 0; i < FIELD_COUNT; i++) {
        assert(staged.fields[i] == (i == (param == SETMETDATEPARAM_EGG ?
               MON_DATA_EGG_LOCATION : MON_DATA_MET_LOCATION) ?
               expected : old.fields[i]));
    }
    for (int i = 0; i < 4; i++) {
        assert(written_fields[i] == old_fields[i]);
        assert(written_values[i] == (i == 0 ? expected : old_values[i]));
    }
}
static void check_strategy(int strat, int egg, int location, int expected) {
    BoxPokemon mon;
    PlayerProfile profile = {12, 1};
    reset(&mon);
    mon.fields[MON_DATA_IS_EGG] = egg;
    mon.fields[MON_DATA_LEVEL] = 17;
    BoxMonSetTrainerMemo(&mon, &profile, strat, location, HEAP_ID_FIELD2);
    assert(rtc_calls == 1);
    assert(mon.fields[egg ? MON_DATA_EGG_LOCATION : MON_DATA_MET_LOCATION] == expected);
    assert(mon.fields[egg ? MON_DATA_MET_LOCATION : MON_DATA_EGG_LOCATION] == 0);
    assert(mon.fields[egg ? MON_DATA_MET_YEAR : MON_DATA_EGG_YEAR] == 0);
    assert(mon.fields[egg ? MON_DATA_EGG_YEAR : MON_DATA_MET_YEAR] == 2025);
    if (!egg) assert(mon.fields[MON_DATA_MET_LEVEL] == 17);
    if (strat == 0) assert(mon.fields[MON_DATA_OT_ID] == 12);
    else assert(mon.fields[MON_DATA_OT_ID] == 100 + MON_DATA_OT_ID);
}
static void check_hatch(int location, int expected, int owned) {
    BoxPokemon mon;
    PlayerProfile profile = {owned ? 12 : 13, 1};
    reset(&mon);
    mon.fields[MON_DATA_MET_LOCATION] = 135;
    mon.fields[MON_DATA_MET_YEAR] = 2010;
    mon.fields[MON_DATA_MET_MONTH] = 3;
    mon.fields[MON_DATA_MET_DAY] = 4;
    BoxMonSetTrainerMemo(&mon, &profile, 6, location, HEAP_ID_FIELD2);
    assert(rtc_calls == 1 && mon.fields[MON_DATA_MET_LOCATION] == expected);
    assert(mon.fields[MON_DATA_MET_YEAR] == 2025);
    assert(mon.fields[MON_DATA_EGG_LOCATION] == (owned ? 100 + MON_DATA_EGG_LOCATION : 135));
    if (!owned) {
        assert(mon.fields[MON_DATA_EGG_YEAR] == 2010);
        assert(mon.fields[MON_DATA_EGG_MONTH] == 3);
        assert(mon.fields[MON_DATA_EGG_DAY] == 4);
    }
}
static void check_legacy_hatch(void) {
    BoxPokemon foreign, owned;
    PlayerProfile other = {13, 1}, player = {12, 1};
    reset(&foreign);
    foreign.fields[MON_DATA_MET_LOCATION] = MAPSEC_LITTLEROOT_TOWN;
    foreign.fields[MON_DATA_MET_YEAR] = 2010;
    BoxMonSetTrainerMemo(&foreign, &other, 6, MAPSEC_ROUTE_101, HEAP_ID_FIELD2);
    assert(rtc_calls == 1);
    assert(foreign.fields[MON_DATA_EGG_LOCATION] == MAPSEC_LITTLEROOT_TOWN);
    assert(foreign.fields[MON_DATA_EGG_YEAR] == 2010);
    assert(foreign.fields[MON_DATA_MET_LOCATION] == METLOC_HOENN);
    assert(foreign.fields[MON_DATA_MET_YEAR] == 2025);

    reset(&owned);
    owned.fields[MON_DATA_EGG_LOCATION] = MAPSEC_ROUTE_101;
    owned.fields[MON_DATA_EGG_YEAR] = 2011;
    BoxMonSetTrainerMemo(&owned, &player, 6, MAPSEC_LITTLEROOT_TOWN, HEAP_ID_FIELD2);
    assert(rtc_calls == 1);
    assert(owned.fields[MON_DATA_EGG_LOCATION] == MAPSEC_ROUTE_101);
    assert(owned.fields[MON_DATA_EGG_YEAR] == 2011);
    assert(owned.fields[MON_DATA_MET_LOCATION] == METLOC_HOENN);
    assert(owned.fields[MON_DATA_MET_YEAR] == 2025);
}
int main(void) {
    assert(MAPSEC_LITTLEROOT_TOWN == 235 && MAPSEC_ROUTE_101 == 236);
    assert(METLOC_HOENN == 2005 && METLOC_DAY_CARE_COUPLE == 2000);
    assert(sub_02017FE4(MAPSECTYPE_GIFT, MAPLOC(METLOC_HOENN)) == METLOC_HOENN);
    assert(sub_02017FE4(MAPSECTYPE_EXTERNAL, MAPLOC(METLOC_FARAWAY_PLACE))
           == METLOC_FARAWAY_PLACE);
    for (int loc = 0; loc <= UINT16_MAX; loc++) {
        check_helper(loc, SETMETDATEPARAM_EGG);
        check_helper(loc, SETMETDATEPARAM_MON);
    }
    for (int strat = 0; strat <= 7; strat += 7) {
        for (int egg = 0; egg <= 1; egg++) {
            check_strategy(strat, egg, 235, 2005);
            check_strategy(strat, egg, 236, 2005);
            check_strategy(strat, egg, 2005, METLOC_FARAWAY_PLACE);
            check_strategy(strat, egg, 234, 234);
        }
    }
    for (int owned = 0; owned <= 1; owned++) {
        check_hatch(235, 2005, owned);
        check_hatch(236, 2005, owned);
        check_hatch(2005, MAPSEC_MYSTERY_ZONE, owned);
        check_hatch(234, 234, owned);
    }
    check_legacy_hatch();
    return 0;
}
"""


class EpisodeMetLocationTests(unittest.TestCase):
    def test_pinned_staging_and_host_memo_writes(self):
        self.assertIsNotNone(shutil.which("cc"), "Host C compiler required")
        recipe = json.loads((ROOT / "scripts/episode_templates/native_edits.json").read_text())
        approved = json.loads((ROOT / "scripts/episode_templates/approved_deltas.json").read_text())
        self.assertEqual(set(NAMES) & recipe.keys(), set(NAMES))
        for name in NAMES:
            self.assertEqual(
                {key: recipe[name][key] for key in ("before", "after")},
                approved[name],
            )
        edit, = recipe[MEMO]["edits"]
        self.assertEqual((edit["start"], edit["end"]), (816, 816))
        self.assertEqual(edit["lines"], [
            "    // Keep custom map labels out of stored Pokemon metadata.\n",
            "    // Translate after the native strategy clamps, only on a new memo write.\n",
            "    if (mapsec == MAPSEC_LITTLEROOT_TOWN || mapsec == MAPSEC_ROUTE_101) {\n",
            "        mapsec = METLOC_HOENN;\n",
            "    }\n",
            "\n",
        ])
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for name in NAMES:
                data = (ROOT / name).read_bytes()
                self.assertEqual(digest(data), recipe[name]["before"])
                (root / name).parent.mkdir(parents=True, exist_ok=True)
                (root / name).write_bytes(data)
            native_edits(root, {name: recipe[name] for name in NAMES})
            for name in NAMES:
                self.assertEqual(digest((root / name).read_bytes()), recipe[name]["after"])
            original = (ROOT / MEMO).read_text()
            staged = (root / MEMO).read_text()
            insertion = "".join(edit["lines"])
            self.assertEqual(staged.count(insertion), 1)
            self.assertEqual(staged.replace(insertion, "", 1), original)
            self.assertEqual(
                extract(staged, "BoxMon_SetMetDateAndLocation").replace(insertion, "", 1),
                extract(original, "BoxMon_SetMetDateAndLocation"),
            )
            self.assertEqual(
                staged.count("mapsec = METLOC_HOENN;"), 1
            )
            self.assertEqual(original.count("mapsec = METLOC_HOENN;"), 0)
            section = (root / SECTIONS).read_text()
            maploc = re.search(r"^#define MAPLOC\(sec\) \(\(sec\) % 1000\)$", section, re.M)
            self.assertIsNotNone(maploc)
            type_header = (ROOT / "include/map_section.h").read_text()
            self.assertRegex(
                type_header,
                r"typedef enum MapsecType \{\s*MAPSECTYPE_NORMAL,\s*"
                r"MAPSECTYPE_GIFT,\s*MAPSECTYPE_EXTERNAL,\s*MAPSECTYPE_MAX",
            )
            assembly = (ROOT / "asm/unk_02017FAC.s").read_text()
            self.assertRegex(
                assembly,
                r"\.short MAPSEC_MYSTERY_ZONE\s+\.short METLOC_DAY_CARE_COUPLE"
                r"\s+\.short METLOC_LOVELY_PLACE",
            )
            self.assertIn("thumb_func_start sub_02017FE4", assembly)
            self.assertRegex(assembly, r"ldrh r0, \[r0, r1\]\s+add r0, r4, r0")
            for definition in (
                "#define MAPSEC_LITTLEROOT_TOWN  235",
                "#define MAPSEC_ROUTE_101        236",
                "#define METLOC_HOENN           2005",
            ):
                self.assertEqual(len(re.findall("^" + re.escape(definition) + "$", section, re.M)), 1)
            section_constants = "\n".join(
                line for line in section.splitlines()
                if re.match(r"#define (?:MAPSEC_(?:MYSTERY_ZONE|PAL_PARK|LITTLEROOT_TOWN|ROUTE_101)|"
                            r"METLOC_(?:DAY_CARE_COUPLE|LINK_TRADE|LINK_TRADE_2|HOENN|"
                            r"LOVELY_PLACE|FARAWAY_PLACE))\s", line)
            )
            self.assertEqual(len(section_constants.splitlines()), 10)
            section_constants += "\n" + maploc.group()
            helper = "BoxMon_SetMetDateAndLocation"
            original_helper = extract(original, helper).replace(
                helper + "(", "Original_SetMetDateAndLocation(", 1
            )
            functions = "\n".join([
                original_helper,
                *(extract(staged, name) for name in (
                    "BoxMon_SetMetDateAndLocation", "BoxMon_ClearMetDateAndLocation",
                    "BoxMon_CopyLevelToMetLevel", "BoxMon_SetOriginalTrainerData",
                    "BoxMon_SetFatefulEncounter",
                    "BoxMonSetTrainerMemo",
                )),
            ])
            source = HARNESS.replace("/* SECTION_CONSTANTS */", section_constants).replace(
                "/* PRODUCTION_FUNCTIONS */", functions
            )
            (root / "memo.c").write_text(source)
            subprocess.run(
                ["cc", "-std=c99", "-Wall", "-Wextra", "-Werror",
                 str(root / "memo.c"), "-o", str(root / "memo")],
                check=True,
            )
            subprocess.run([str(root / "memo")], check=True)