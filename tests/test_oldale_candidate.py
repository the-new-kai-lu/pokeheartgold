"""Independent source/resource checks; no NDS compilation or gameplay claims.

Set OLDALE_CANDIDATE and OLDALE_R5_SOURCE to test an explicitly authored tree.
The warp regressions host-compile extracted production callers and lookup only.
"""
import ast
import hashlib
import json
import os
from pathlib import Path
import re
import struct
import subprocess
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import check_expansion_baseline
from episode_source_inventory import native_names
from export_lab_model import rgba_preview
from extract_emerald_lab import extract
from hgss_land import Land, narc_members
from prepare_emerald_episode import verify_native_contract
import prepare_oldale_candidate as candidate


class OptInTests(unittest.TestCase):
    def test_no_implicit_candidate_generation(self):
        with self.assertRaisesRegex(ValueError, "opt-in"):
            candidate.prepare(ROOT, ROOT, ROOT, ROOT)


class ProducerLiteralTests(unittest.TestCase):
    def test_generated_script_and_message_match_native_bytes(self):
        tree = ast.parse((ROOT / "scripts/prepare_oldale_candidate.py").read_text())

        def literal_for(name):
            calls = [node for node in ast.walk(tree)
                     if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                     and node.func.id == "put" and node.args
                     and isinstance(node.args[0], ast.Name) and node.args[0].id == name]
            self.assertEqual(len(calls), 1)
            return ast.literal_eval(calls[0].args[1])

        self.assertEqual(literal_for("SCRIPT"),
                         b'#include "constants/scrcmd.h"\n'
                         b'.include "asm/macros/script.inc"\n'
                         b'.rodata\n\n'
                         b'ScrDef Oldale_Girl\nScrDefEnd\n\nOldale_Girl:\n'
                         b'LockAll\nFacePlayer\nNPCMsg 0\nWaitABPress\nCloseMsg\nReleaseAll\nEnd\n')
        self.assertEqual(literal_for("MESSAGE"),
                         b'<?xml version="1.0"?>\n<body language="English">\n'
                         b'<row id="msg_0830_00000" index="0"><attribute name="window_context_name">used</attribute>'
                         b'<language name="English">I want to take a rest, so I\xe2\x80\x99m saving my\\n'
                         b'progress.</language></row>\n</body>\n')


class AuthoredOldaleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not all(os.environ.get(k) for k in ("OLDALE_CANDIDATE", "OLDALE_R5_SOURCE")):
            raise unittest.SkipTest("Explicit unapproved source trees required")
        cls.tree = Path(os.environ["OLDALE_CANDIDATE"])
        cls.before = Path(os.environ["OLDALE_R5_SOURCE"])
        cls.donor = ROOT.parent / "pokeemerald"
        cls.report = json.loads((cls.tree / "oldale-candidate.json").read_text())
        cls.land = [Land.decode(m) for m in narc_members((cls.tree / candidate.LAND).read_bytes())[-2:]]

    def test_exhaustive_native_inventory_and_approval_separation(self):
        verify_native_contract(ROOT, self.before)
        with self.assertRaises(ValueError):
            verify_native_contract(ROOT, self.tree)
        self.assertFalse((self.tree / "opening-episode.json").exists())
        changed = {
            "expansion/baseline.json", candidate.AREAS, candidate.TEXTURES, candidate.LAND,
            candidate.ROUTE_EVENT, candidate.OLDALE_EVENT, candidate.MATRIX,
            candidate.SCRIPT, candidate.MESSAGE, "files/msgdata/msg/msg_0279.gmm",
            "include/constants/map_sections.h", "include/constants/maps.h",
            "src/data/map_headers.h", "src/map_events.c", "src/trainer_memo.c",
            "src/unk_02055BF0.c",
        }
        added = {candidate.OLDALE_EVENT, candidate.MATRIX, candidate.SCRIPT, candidate.MESSAGE}
        observed = set()
        for name in set(native_names(ROOT)) | added:
            after = (self.tree / name).read_bytes()
            before = (self.before / name).read_bytes() if (self.before / name).exists() else None
            if before != after:
                observed.add(name)
            self.assertEqual(hashlib.sha256(after).hexdigest(), self.report["native_after_sha256"][name])
            if name in changed:
                self.assertEqual(self.report["proposed_changes"][name],
                                 dict(before=hashlib.sha256(before).hexdigest() if before else None,
                                      after=hashlib.sha256(after).hexdigest()))
        self.assertEqual(observed, changed)
        self.assertEqual(set(self.report["proposed_changes"]), changed)
        self.assertEqual(self.report["status"], candidate.STATUS)
        self.assertEqual(self.report["additional_save_allocation"], 0)
        self.assertFalse(self.report["runtime_verified"])
        for root, count in ((ROOT, 540), (self.tree, 544)):
            manifest = json.loads((root / "expansion/baseline.json").read_text())
            errors, observed = check_expansion_baseline.audit(root, manifest)
            self.assertEqual(errors, [])
            self.assertEqual(observed, dict(map_count=count, region_bits=1, persistent_flags=2912,
                                           variables=368, variable_base=16384))
        for name in ("include/save.h", "src/save.c", "include/map_header.h",
                     "src/map_matrix.c", "include/map_matrix.h", "src/terrain_attributes.c"):
            self.assertEqual((self.tree / name).read_bytes(), (ROOT / name).read_bytes())

    def test_archives_matrix_and_minimal_terrain_changes(self):
        for name, count in ((candidate.AREAS, 110), (candidate.TEXTURES, 110), (candidate.LAND, 680)):
            before = narc_members((self.before / name).read_bytes())
            after = narc_members((self.tree / name).read_bytes())
            self.assertEqual(len(after), count)
            for i, original in enumerate(before):
                if name != candidate.LAND or i != 678:
                    self.assertEqual(after[i], original, (name, i))
        self.assertEqual((self.tree / candidate.MATRIX).read_bytes(), struct.pack("<5BH", 1, 1, 0, 0, 0, 679))
        old = Land.decode(narc_members((self.before / candidate.LAND).read_bytes())[678])
        new, town = self.land
        for field in ("marker", "extra", "props", "model", "collision"):
            self.assertEqual(getattr(old, field), getattr(new, field))
        a, b, t = [struct.unpack("<1024H", land.terrain) for land in (old, new, town)]
        actual = {(i % 32, i // 32, a[i], b[i]) for i in range(1024) if a[i] != b[i]}
        expected = {(10, 1, 0, 110), (11, 1, 0, 110)}
        # Independent concrete minimal connector; no ledges or authored rescue tiles.
        grass = {(11, 10), (12, 10), (13, 10), (13, 9), (14, 9),
                 (15, 6), (14, 6), (13, 6), (13, 5), (12, 5)}
        self.assertEqual(actual, expected | {(x, y, 0x8000, 2) for x, y in grass})
        raw = (self.donor / "data/layouts/Route101/map.bin").read_bytes()
        attrs = [(self.donor / ("data/tilesets/"+p+"/metatile_attributes.bin")).read_bytes()
                 for p in ("primary/general", "secondary/petalburg")]
        for x, y in grass:
            block = struct.unpack_from("<H", raw, 2*(y*20+x))[0]
            tile = block & 1023
            behavior = struct.unpack_from("<H", attrs[tile >= 512], 2*(tile % 512))[0] & 255
            self.assertEqual((block >> 10 & 3, block >> 12, behavior), (0, 3, 2))
        for y in range(32):
            for x in range(32):
                if x in (0, 19) or y in (0, 19) or x >= 20 or y >= 20:
                    self.assertEqual(t[y*32+x], 0x8000)
        for x in (10, 11):
            self.assertEqual(t[18*32+x], 111)
            self.assertEqual(t[17*32+x], 0)
            self.assertEqual(b[2*32+x], 0)
            # Independent flood-fill, not the producer's path/cost algorithms.
            for words, start, goal, blocked in (
                    (b, (10, 17), (x, 2), set()), (t, (x, 17), (15, 11), {(16, 11)})):
                seen, pending = {start}, [start]
                while pending:
                    px, pz = pending.pop()
                    for qx, qz in ((px-1, pz), (px+1, pz), (px, pz-1), (px, pz+1)):
                        q = (qx, qz)
                        if (0 <= qx < 20 and 0 <= qz < 20 and q not in seen and
                                q not in blocked and not words[qz*32+qx] & 0x8000):
                            seen.add(q)
                            pending.append(q)
                self.assertIn(goal, seen)
        # Every traversable Oldale cell independently matches donor ordinary floor.
        raw = (self.donor / "data/layouts/OldaleTown/map.bin").read_bytes()
        for i in range(400):
            x, y = i % 20, i // 20
            if not t[y*32+x] & 0x8000:
                block = struct.unpack_from("<H", raw, i*2)[0]
                tile = block & 1023
                behavior = struct.unpack_from("<H", attrs[tile >= 512], 2*(tile % 512))[0] & 255
                self.assertEqual((block >> 10 & 3, block >> 12, behavior), (0, 3, 0))

    def test_reciprocal_events_exclusions_and_rescue_gate(self):
        route = json.loads((self.tree / candidate.ROUTE_EVENT).read_text())
        old_route = json.loads((self.before / candidate.ROUTE_EVENT).read_text())
        town = json.loads((self.tree / candidate.OLDALE_EVENT).read_text())
        unchanged = dict(route, warps=route["warps"][:4])
        self.assertEqual(unchanged, old_route)
        self.assertEqual([(w["x"], w["z"], w["header"], w["anchor"]) for w in route["warps"][4:]],
                         [(10, 1, 543, 2), (11, 1, 543, 3), (10, 2, 543, 2), (11, 2, 543, 3)])
        self.assertEqual([(w["x"], w["z"], w["header"], w["anchor"]) for w in town["warps"]],
                         [(10, 18, 542, 6), (11, 18, 542, 7), (10, 17, 542, 6), (11, 17, 542, 7)])
        source = (self.tree / "src/map_events.c").read_text()
        old_source = (self.before / "src/map_events.c").read_text()
        gate = old_source.split("if (x == fieldSystem->mapEvents->warp_events[i].x", 1)[1]
        suffix = source.split("if (x == fieldSystem->mapEvents->warp_events[i].x", 1)[1]
        new_gate = re.search(
            r"            if \(fieldSystem->location->mapId == MAP_ROUTE_101_TRAVEL\n"
            r"                && \(i == 4 \|\| i == 5\).*?            }\n", suffix, re.S)
        self.assertIsNotNone(new_gate)
        self.assertEqual(suffix.replace(new_gate[0], "", 1), gate)
        expression = re.search(r"        if \((.*?)\) \{\n            continue;\n        \}", source, re.S)[1]
        for old, new in (
            ("fieldSystem->location->mapId", "mapid"),
            ("fieldSystem->mapEvents->warp_events[i].x", "wx"),
            ("fieldSystem->mapEvents->warp_events[i].z", "wz"),
            ("MAP_LITTLEROOT_TOWN_TRAVEL", "541"), ("MAP_ROUTE_101_TRAVEL", "542"),
            ("MAP_OLDALE_TOWN_TRAVEL", "543"), ("&&", " and "), ("||", " or ")):
            expression = expression.replace(old, new)
        expression = " ".join(expression.split())
        for mapid, events, excluded in ((542, route["warps"], {2, 3, 6, 7}),
                                       (543, town["warps"], {2, 3})):
            for i, w in enumerate(events):
                x, y, wx, wz = w["x"], w["z"], w["x"], w["z"]
                self.assertEqual(bool(eval(expression, {"__builtins__": {}}, locals())), i in excluded)
        # Destination indices resolve directly, bypassing coordinate exclusions.
        for i, x in enumerate((10, 11)):
            self.assertEqual(town["warps"][route["warps"][4+i]["anchor"]]["z"], 17)
            self.assertEqual(route["warps"][town["warps"][i]["anchor"]]["z"], 2)
        transition = (self.tree / "src/unk_02055BF0.c").read_text()
        self.assertIn("(otherID == MAP_ROUTE_101_TRAVEL && mapID == MAP_OLDALE_TOWN_TRAVEL)", transition)
        self.assertIn("(otherID == MAP_OLDALE_TOWN_TRAVEL && mapID == MAP_ROUTE_101_TRAVEL)", transition)

    def test_host_compiled_actual_lookup_story_gate_truth_table(self):
        def function(tree):
            source = (tree / "src/map_events.c").read_text()
            return re.search(
                r"int Field_GetWarpEventAtXYPos\(.*?\n}\n", source, re.S)[0]

        fixtures = []
        for name, path in (("route", candidate.ROUTE_EVENT),
                           ("town", candidate.OLDALE_EVENT),
                           ("littleroot", candidate.EVENTS+"492_LITTLEROOT_TOWN_TRAVEL.json")):
            events = json.loads((self.tree / path).read_text())["warps"]
            values = ", ".join("{%d, %d}" % (w["x"], w["z"]) for w in events)
            fixtures.append("static Warp %s[] = {%s};\n" % (name, values))
        harness = r'''
#include <stdio.h>
#include <stdlib.h>
#include "constants/maps.h"
#include "constants/expansion.h"
typedef struct { int x, z; } Warp;
typedef struct { int num_warp_events; Warp *warp_events; } Events;
typedef struct { int mapId; } Location;
typedef struct { int rescue, gift; } Save;
typedef struct { Events *mapEvents; Location *location; Save *saveData; } FieldSystem;
static Save *Save_VarsFlags_Get(Save *save) { return save; }
static int GetScriptVar(Save *save, int var) {
    if (var == VAR_HOENN_RESCUE_STATE) return save->rescue;
    if (var == VAR_HOENN_STARTER_RECEIVED) return save->gift;
    abort();
}
static int checks;
static void check(int actual, int expected, int line) {
    if (actual != expected) {
        fprintf(stderr, "line %d: actual %d expected %d\n", line, actual, expected);
        exit(1);
    }
    checks++;
}
#define CHECK(a, e) check((a), (e), __LINE__)
'''
        harness += function(self.tree)
        harness += function(self.before).replace(
            "Field_GetWarpEventAtXYPos(", "R5_Field_GetWarpEventAtXYPos(", 1)
        harness += "".join(fixtures)
        harness += r'''
int main(void) {
    int states[] = {0, 1, 2, 3, 65535};
    int gifts[] = {0, 1, 252, 65535};
    Save save;
    Location location = {MAP_ROUTE_101_TRAVEL};
    Events events = {8, route};
    FieldSystem field = {&events, &location, &save};
    CHECK(HOENN_RESCUE_COMPLETE, 1);
    for (int r = 0; r < 5; r++) {
        for (int g = 0; g < 4; g++) {
            save.rescue = states[r];
            save.gift = gifts[g];
            for (int lane = 0; lane < 2; lane++) {
                int x = 10 + lane;
                location.mapId = MAP_ROUTE_101_TRAVEL;
                events.num_warp_events = 8; events.warp_events = route;
                /* New exits require both earned states, including scene state3. */
                CHECK(Field_GetWarpEventAtXYPos(&field, x, 1),
                      states[r] == 1 && gifts[g] != 0 ? 4 + lane : -1);
                /* R5 south NoSpace escape must still work with gift=0. */
                CHECK(Field_GetWarpEventAtXYPos(&field, x, 19),
                      states[r] == 1 ? lane : -1);
                CHECK(Field_GetWarpEventAtXYPos(&field, x, 19),
                      R5_Field_GetWarpEventAtXYPos(&field, x, 19));
                /* Route6/7 anchors never appear in coordinate lookup. */
                CHECK(Field_GetWarpEventAtXYPos(&field, x, 2), -1);
                CHECK(Field_GetWarpEventAtXYPos(&field, x, 3), -1);
                location.mapId = MAP_OLDALE_TOWN_TRAVEL;
                events.num_warp_events = 4; events.warp_events = town;
                /* Oldale return unaffected even for unfinished/empty fixtures. */
                CHECK(Field_GetWarpEventAtXYPos(&field, x, 18), lane);
                CHECK(Field_GetWarpEventAtXYPos(&field, x, 17), -1);
                location.mapId = MAP_LITTLEROOT_TOWN_TRAVEL;
                events.num_warp_events = 5; events.warp_events = littleroot;
                CHECK(Field_GetWarpEventAtXYPos(&field, x, 1), 1 + lane);
                CHECK(Field_GetWarpEventAtXYPos(&field, x, 2), -1);
                /* No new blanket restriction on unrelated maps or indices. */
                location.mapId = 0;
                events.num_warp_events = 8; events.warp_events = route;
                CHECK(Field_GetWarpEventAtXYPos(&field, x, 1), 4 + lane);
                CHECK(Field_GetWarpEventAtXYPos(&field, x, 2), 6 + lane);
                CHECK(save.rescue, states[r]);
                CHECK(save.gift, gifts[g]);
            }
        }
    }
    printf("%d host lookup checks passed\n", checks);
    return 0;
}
'''
        with tempfile.TemporaryDirectory(prefix="oldale-host-lookup-") as directory:
            source = Path(directory) / "lookup.c"
            executable = Path(directory) / "lookup"
            source.write_text(harness)
            subprocess.run(["cc", "-std=c99", "-Wall", "-Wextra", "-Werror",
                            "-I", str(self.tree / "include"), str(source), "-o", str(executable)],
                           check=True, capture_output=True, text=True)
            result = subprocess.run([str(executable)], check=True, capture_output=True, text=True)
            self.assertEqual(result.stdout, "521 host lookup checks passed\n")

    def test_host_compiled_actual_standing_south_exit_rejects_old_row19(self):
        control = (self.tree / "src/field/field_control.c").read_text()
        # This is the same production caller, not a Python model of tile choice.
        self.assertEqual(control, (ROOT / "src/field/field_control.c").read_text())

        def function(source, name):
            matches = re.findall(
                r"^(?:static (?:inline )?)?(?:void|BOOL|int|u8) " +
                re.escape(name) + r"\([^;{}]*\) \{.*?^}\n",
                source, re.M | re.S)
            self.assertEqual(len(matches), 1, name)
            return matches[0]

        caller = function(control, "FieldSystem_CheckMapTransition")
        predicates = sorted(set(re.findall(r"\bMetatileBehavior_\w+(?=\()", caller)))
        behaviors = (self.tree / "src/metatile_behavior.c").read_text()
        town = json.loads((self.tree / candidate.OLDALE_EVENT).read_text())["warps"]
        route = json.loads((self.tree / candidate.ROUTE_EVENT).read_text())["warps"]
        fixtures = []
        for name, events in (("town", town), ("route", route)):
            values = ", ".join("{%d, %d, %d, %d}" %
                               (w["x"], w["z"], w["header"], w["anchor"]) for w in events)
            fixtures.append("static WarpEvent %s[] = {%s};\n" % (name, values))
        fixtures.append("static const unsigned short terrain[1024] = {%s};\n" %
                        ", ".join(map(str, struct.unpack("<1024H", self.land[1].terrain))))
        harness = r'''
#include <stdio.h>
#include <stdlib.h>
#include "constants/maps.h"
#include "constants/expansion.h"
#include "constants/global_fieldmap.h"
#include "constants/metatile_behavior.h"
typedef int BOOL;
typedef unsigned char u8;
typedef unsigned int u32;
#define TRUE 1
#define FALSE 0
typedef struct { int x, z, header, anchor; } WarpEvent;
typedef struct { int num_warp_events; WarpEvent *warp_events; } Events;
typedef struct { int mapId, warpId, x, y, direction; } Location;
typedef struct { int rescue, gift; Location entrance; } Save;
typedef struct { int x, z, direction; } Avatar;
typedef struct {
    Events *mapEvents; Location *location; Save *saveData; Avatar *playerAvatar;
} FieldSystem;
typedef struct { int transitionDir; } FieldInput;
static int checks, transitions, destination, anchor, direction;
static void check(int actual, int expected, int line) {
    if (actual != expected) {
        fprintf(stderr, "standing south exit line %d: actual %d expected %d\n",
                line, actual, expected);
        exit(1);
    }
    checks++;
}
#define CHECK(a, e) check((a), (e), __LINE__)
static Save *Save_VarsFlags_Get(Save *save) { return save; }
static int GetScriptVar(Save *save, int var) {
    if (var == VAR_HOENN_RESCUE_STATE) return save->rescue;
    if (var == VAR_HOENN_STARTER_RECEIVED) return save->gift;
    abort();
}
static int PlayerAvatar_GetXCoord(Avatar *avatar) { return avatar->x; }
static int PlayerAvatar_GetZCoord(Avatar *avatar) { return avatar->z; }
static int PlayerAvatar_GetFacingDirection(Avatar *avatar) { return avatar->direction; }
static Save *Save_LocalFieldData_Get(Save *save) { return save; }
static Location *LocalFieldData_GetEntrancePosition(Save *save) { return &save->entrance; }
static Location *LocalFieldData_GetDynamicWarp(Save *save) { (void)save; abort(); }
static void GF_AssertFail(void) { abort(); }
static const WarpEvent *Field_GetWarpEventI(const FieldSystem *field, u32 index) {
    return index < (u32)field->mapEvents->num_warp_events ?
        &field->mapEvents->warp_events[index] : NULL;
}
static void sub_02055CD8(FieldSystem *field, int map, int warp, int x, int z, int dir) {
    (void)field; (void)x; (void)z;
    transitions++; destination = map; anchor = warp; direction = dir;
}
static void NewFieldTransitionEnvironment(FieldSystem *field, int map, int warp,
                                         int x, int z, int dir, u32 type) {
    (void)field; (void)map; (void)warp; (void)x; (void)z; (void)dir; (void)type;
    abort(); /* No door, ladder or stair transition is valid in this fixture. */
}
static void ShiftFieldCoordsByCompassDirection(FieldSystem *, u32, int *, int *);
static BOOL FieldSystem_MapConnection(FieldSystem *, int, int, Location *);
'''
        harness += "".join(fixtures)
        # Narrow terrain-access stubs retain the collision bit seen by the actual
        # caller (sub_020548C0 in asm/unk_02054648.s), including sealed facing row19.
        harness += r'''
static unsigned short terrain_word(int x, int z) {
    CHECK(x >= 0 && x < 32 && z >= 0 && z < 32, TRUE);
    return terrain[z*32+x];
}
static u8 GetMetatileBehavior(FieldSystem *field, int x, int z) {
    (void)field; return terrain_word(x, z) & 255;
}
static BOOL sub_020548C0(FieldSystem *field, int x, int z) {
    (void)field; return (terrain_word(x, z) & 0x8000) != 0;
}
'''
        harness += function((self.tree / "src/map_events.c").read_text(),
                            "Field_GetWarpEventAtXYPos")
        harness += "".join(function(behaviors, name) for name in predicates)
        for name in ("PlayerAvatar_GetStandingTileCoords", "PlayerAvatar_GetFacingTileCoords",
                     "ShiftFieldCoordsByCompassDirection", "SetLocation",
                     "FieldSystem_MapConnection"):
            harness += function(control, name)
        harness += caller
        harness += r'''
int main(int argc, char **argv) {
    (void)argv;
    /* Negative control changes only departure events, never terrain or anchors. */
    if (argc == 2) { town[0].z = 19; town[1].z = 19; }
    int states[] = {0, 1, 2, 3, 65535};
    int gifts[] = {0, 1, 252, 65535};
    Save save = {0};
    Location location = {0};
    Avatar avatar = {0};
    Events events = {4, town};
    FieldSystem field = {&events, &location, &save, &avatar};
    FieldInput input = {DIR_SOUTH};
    location.mapId = MAP_OLDALE_TOWN_TRAVEL;
    CHECK(TILE_BEHAVIOR_WARP_SOUTH, 111);
    for (int z = 0; z < 32; z++) {
        for (int x = 0; x < 32; x++) {
            if (x == 0 || x >= 19 || z == 0 || z >= 19)
                CHECK(terrain[z*32+x], 0x8000);
        }
    }
    for (int r = 0; r < 5; r++) {
        for (int g = 0; g < 4; g++) {
            save.rescue = states[r]; save.gift = gifts[g];
            for (int lane = 0; lane < 2; lane++) {
                avatar.x = 10 + lane; avatar.z = 18; avatar.direction = DIR_SOUTH;
                input.transitionDir = DIR_SOUTH; transitions = 0;
                CHECK(terrain[18*32+avatar.x], TILE_BEHAVIOR_WARP_SOUTH);
                CHECK(terrain[17*32+avatar.x], 0);
                CHECK(terrain[19*32+avatar.x], 0x8000);
                /* Required production result: standing18, facing19, ungated return. */
                CHECK(FieldSystem_CheckMapTransition(&field, &input), TRUE);
                CHECK(transitions, 1);
                CHECK(destination, MAP_ROUTE_101_TRAVEL);
                CHECK(anchor, 6 + lane);
                CHECK(direction, DIR_SOUTH);
                CHECK(save.entrance.warpId, lane);
                CHECK(save.entrance.x, avatar.x);
                CHECK(save.entrance.y, 18);
                CHECK(route[anchor].x, avatar.x);
                CHECK(route[anchor].z, 2);
                /* Direct index access preserves the floor-only inbound anchors. */
                CHECK(Field_GetWarpEventI(&field, 2 + lane)->z, 17);
                CHECK(Field_GetWarpEventAtXYPos(&field, avatar.x, 17), -1);
                CHECK(Field_GetWarpEventAtXYPos(&field, avatar.x, 19), -1);
                for (int dir = DIR_NONE; dir < DIR_MAX; dir++) {
                    if (dir == DIR_SOUTH) continue;
                    input.transitionDir = avatar.direction = dir; transitions = 0;
                    CHECK(FieldSystem_CheckMapTransition(&field, &input), FALSE);
                    CHECK(transitions, 0);
                }
                avatar.direction = input.transitionDir = DIR_SOUTH;
                avatar.z = 17; transitions = 0;
                CHECK(FieldSystem_CheckMapTransition(&field, &input), FALSE);
                CHECK(transitions, 0);
                CHECK(save.rescue, states[r]);
                CHECK(save.gift, gifts[g]);
            }
        }
    }
    printf("%d standing south exit checks passed\n", checks);
    return 0;
}
'''
        with tempfile.TemporaryDirectory(prefix="oldale-host-standing-exit-") as directory:
            source = Path(directory) / "standing.c"
            executable = Path(directory) / "standing"
            source.write_text(harness)
            compilation = subprocess.run(
                ["cc", "-std=c99", "-Wall", "-Wextra", "-Werror",
                 "-I", str(self.tree / "include"), str(source), "-o", str(executable)],
                capture_output=True, text=True)
            self.assertEqual(compilation.returncode, 0, compilation.stderr)
            result = subprocess.run([str(executable)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertRegex(result.stdout, r"^\d+ standing south exit checks passed\n$")
            rejected = subprocess.run([str(executable), "--old-row19"],
                                      capture_output=True, text=True)
            self.assertEqual(rejected.returncode, 1)
            self.assertIn("actual 0 expected 1", rejected.stderr)

    def test_npc_header_name_and_new_memo_only_translation(self):
        town = json.loads((self.tree / candidate.OLDALE_EVENT).read_text())
        self.assertEqual(town["coords"], [])
        self.assertEqual(town["bgs"], [])
        self.assertEqual(len(town["objects"]), 1)
        npc = town["objects"][0]
        self.assertEqual((npc["x"], npc["z"], npc["spriteId"], npc["scriptId"],
                          npc["eventFlag"], npc["facingDirection"]), (16, 11, 8, 1, 0, 2))
        script = (self.tree / candidate.SCRIPT).read_text().split("Oldale_Girl:\n")[1]
        self.assertEqual(script.splitlines(),
                         ["LockAll", "FacePlayer", "NPCMsg 0", "WaitABPress", "CloseMsg", "ReleaseAll", "End"])
        self.assertEqual((self.tree / candidate.SCRIPT).read_bytes(),
                         b'#include "constants/scrcmd.h"\n.include "asm/macros/script.inc"\n.rodata\n\n'
                         b'ScrDef Oldale_Girl\nScrDefEnd\n\nOldale_Girl:\nLockAll\nFacePlayer\n'
                         b'NPCMsg 0\nWaitABPress\nCloseMsg\nReleaseAll\nEnd\n')
        self.assertEqual((self.tree / candidate.MESSAGE).read_bytes(),
                         b'<?xml version="1.0"?>\n<body language="English">\n'
                         b'<row id="msg_0830_00000" index="0"><attribute name="window_context_name">used</attribute>'
                         b'<language name="English">I want to take a rest, so I\xe2\x80\x99m saving my\\n'
                         b'progress.</language></row>\n</body>\n')
        text = ET.parse(self.tree / candidate.MESSAGE).find("./row/language").text
        self.assertEqual(text, "I want to take a rest, so I’m saving my\\nprogress.")
        labels = ET.parse(self.tree / "files/msgdata/msg/msg_0279.gmm")
        self.assertEqual(labels.find("./row[@index='237']/language").text, "Oldale Town")
        source = (self.tree / "src/data/map_headers.h").read_text()
        entry = re.search(r"\[MAP_OLDALE_TOWN_TRAVEL\] = \{.*?\},", source, re.S)[0]
        for field, value in (("wildEncounterBank", "ENCDATA_NA"), ("areaDataBank", "109"),
                             ("matrixId", "291"), ("eventsBank", "494"),
                             ("mapsec", "MAPSEC_OLDALE_TOWN"), ("regionNo", "MAP_REGION_JOHTO"),
                             ("scriptsBank", "NARC_scr_seq_scr_seq_0967_oldale_arrival_bin"),
                             ("msgBank", "NARC_msg_msg_0830_oldale_arrival_bin"),
                             ("flyAllowed", "FALSE"),
                             ("scriptHeaderBank", "NARC_scr_seq_scr_seq_0399_EVERYWHERE_hdr_bin")):
            self.assertRegex(entry, r"\."+field+r"\s*=\s*"+value+",")
        before = (self.before / "src/trainer_memo.c").read_text()
        after = (self.tree / "src/trainer_memo.c").read_text()
        self.assertEqual(after, before.replace(
            "mapsec == MAPSEC_LITTLEROOT_TOWN || mapsec == MAPSEC_ROUTE_101",
            "mapsec == MAPSEC_LITTLEROOT_TOWN || mapsec == MAPSEC_ROUTE_101 || mapsec == MAPSEC_OLDALE_TOWN"))
        self.assertIn("mapsec = METLOC_HOENN;", after)

    def test_serialized_model_uvs_and_texture_pixels(self):
        model = self.land[1].model
        self.assertEqual(len(model), 53676)
        self.assertLessEqual(len(model), 0xE000)
        self.assertEqual(struct.unpack_from("<I", model, 8)[0], len(model))
        mdl = struct.unpack_from("<I", model, 16)[0]
        base = mdl + 48  # single model dictionary offset
        shape = base + struct.unpack_from("<I", model, base+12)[0]
        header = shape + 40
        stream_start = header + struct.unpack_from("<I", model, header+8)[0]
        length = struct.unpack_from("<I", model, header+12)[0]
        stream = model[stream_start:stream_start+length]
        self.assertEqual(stream_start+length, len(model))
        # Independent packed GX reader; ignore the producer's indices/report.
        sizes = {0: 0, 0x20: 1, 0x22: 1, 0x23: 2, 0x26: 1, 0x40: 1, 0x41: 0}
        commands, offset = [], 0
        while offset < len(stream):
            opcodes = struct.unpack_from("<I", stream, offset)[0]
            offset += 4
            for slot in range(4):
                op = opcodes >> (slot*8) & 255
                n = sizes[op]
                operands = struct.unpack_from("<"+"I"*n, stream, offset)
                offset += n*4
                if op:
                    commands.append((op, operands))
        self.assertEqual(commands.pop(0), (0x20, (0x7fff,)))
        self.assertEqual(len(commands), 10240)
        texture = narc_members((self.tree / candidate.TEXTURES).read_bytes())[109]
        tex = struct.unpack_from("<I", texture, 16)[0]
        image_start = tex + struct.unpack_from("<I", texture, tex+20)[0]
        palette_start = tex + struct.unpack_from("<I", texture, tex+56)[0]
        palette = struct.unpack_from("<256H", texture, palette_start)
        with tempfile.TemporaryDirectory() as directory:
            pack = Path(directory) / "OldaleTown"
            extract(self.donor, pack, "OldaleTown")
            pixels = rgba_preview((pack / "preview.png").read_bytes(), 320, 320)
        for i in range(1024):
            quad = commands[i*10:(i+1)*10]
            self.assertEqual(quad[0], (0x40, (1,)))
            self.assertEqual(quad[9], (0x41, ()))
            x, z = i % 32, i // 32
            uv = quad[1][1][0]
            u, v = (uv & 65535)//16, (uv >> 16)//16
            for vertex, (dx, dz) in enumerate(((0, 0), (0, 16), (16, 16), (16, 0))):
                self.assertEqual(quad[1+vertex*2], (0x22, ((u+dx)*16 | ((v+dz)*16 << 16),)))
                op, args = quad[2+vertex*2]
                self.assertEqual(op, 0x23 if vertex == 0 else 0x26)
                vx, vz = (args[0] & 65535, args[1] & 65535) if vertex == 0 else (args[0] & 65535, args[0] >> 16)
                self.assertEqual((vx, vz), (((x*16+dx-256)*64) & 65535,
                                           ((z*16+dz-256)*64) & 65535))
            if x < 20 and z < 20:
                for py in range(16):
                    for px in range(16):
                        off = ((z*16+py)*320+x*16+px)*4
                        rgb = pixels[off:off+3]
                        expected = sum(round(rgb[c]*31/255) << (5*c) for c in range(3))
                        self.assertEqual(palette[texture[image_start+(v+py)*128+u+px]], expected)


if __name__ == "__main__":
    unittest.main()