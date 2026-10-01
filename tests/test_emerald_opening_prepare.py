"""Pinned PRIVATE door/edge travel; no ROM or Hoenn campaign installation."""

import hashlib
import json
from pathlib import Path
import struct
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from hgss_land import Land, narc_members
from prepare_birch_actor_probe import (ACTOR_SHA256, MEMBER, MMODEL, ROW, SENTINEL,
                                       SPRITES, SPRITE_NAME, TABLE, member_path)
from prepare_emerald_opening import (DONOR_MAP_SHA256, EVENTS, LAND,
                                     OUTDOOR_TRANSITION_BRANCH, SOURCE_SHA256,
                                     donor_travel, prepare, verified_source, warp_bytes)
from stage_emerald_opening import ARCHIVES, MAPS, MATRIX_DIR
from stage_lab_archives import pack_narc

DONOR = ROOT.parent / "pokeemerald"
RESOURCE = Path("/tmp/emerald-opening-stage-aa4ce4e9-verified")
LAB_ASSETS = Path("/tmp/emerald-lab-solid")
ACTOR = Path("/tmp/birch-actor-native-slot32-probe") / member_path()


def digest(data):
    return hashlib.sha256(data).hexdigest()


class ThreeMapTravelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not all(p.exists() for p in (DONOR, RESOURCE, LAB_ASSETS)):
            raise unittest.SkipTest("Pinned private Emerald donor/three-map exports required")
        cls.temp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.temp.cleanup)
        cls.base = Path(cls.temp.name)
        cls.output = cls.base / "travel"
        cls.manifest = prepare(ROOT, DONOR, RESOURCE, LAB_ASSETS, cls.output)

    def test_donor_derived_native_warps_and_serialization(self):
        maps, resource, _, _ = verified_source(ROOT, DONOR, RESOURCE, LAB_ASSETS)
        donor = donor_travel(maps)
        self.assertEqual(donor["lab_exits"], [[15, 21], [16, 21]])
        self.assertEqual(donor["town_lab"], [7, 16])
        self.assertEqual(donor["connection_offset"], 0)
        self.assertEqual(self.manifest["native_edge_lanes"], [10, 11])
        self.assertEqual(self.manifest["native_edge_inset"], {
            "town_north": 1, "route_south": 18})
        self.assertEqual(self.manifest["donor_map_sha256"], DONOR_MAP_SHA256)
        self.assertEqual(self.manifest["resource_input_sha256"], resource["output_sha256"])
        self.assertEqual(self.manifest["status"],
                         "private-three-map-native-door-edge-travel-unverified-runtime")
        self.assertEqual(self.manifest["map_count"], 543)
        self.assertEqual(self.manifest["event_count"], 494)
        for kind, expected in (
                ("lab", [(15, 21, 541, 0), (16, 21, 541, 0)]),
                ("town", [(7, 16, 540, 0), (10, 1, 542, 2), (11, 1, 542, 3),
                          (10, 2, 542, 2), (11, 2, 542, 3)]),
                ("route", [(10, 18, 541, 3), (11, 18, 541, 4),
                           (10, 17, 541, 3), (11, 17, 541, 4)])):
            events = self.manifest["events"][kind]
            self.assertEqual([(w["x"], w["z"], w["header"], w["anchor"]) for w in events],
                             expected)
            self.assertEqual(b"".join(warp_bytes(w) for w in events),
                             b"".join(struct.pack("<4HI", x, z, map_id, target, 0)
                                      for x, z, map_id, target in expected))
            self.assertTrue(all(w["y"] == 0 for w in events))
        # The JSON zone-event build template serializes these exact five fields
        # as short x/z/header/anchor, then word y (all signedness/width audited).
        template = (self.output / "files/fielddata/eventdata/zone_event.json.txt").read_text()
        self.assertIn(".short {{ warp.header }}", template)
        self.assertIn(".short {{ warp.anchor }}", template)
        self.assertIn(".word {{ warp.y }}", template)
        for kind, number, name in (("lab", 491, "HOENN_LAB_DEBUG"),
                                    ("town", 492, "LITTLEROOT_TOWN_TRAVEL"),
                                    ("route", 493, "ROUTE_101_TRAVEL")):
            obj = json.loads((self.output / EVENTS / f"{number}_{name}.json").read_text())
            self.assertEqual(obj["warps"], self.manifest["events"][kind])
            self.assertEqual(obj["objects"] if kind != "lab" else len(obj["objects"]),
                             [] if kind != "lab" else 3)
            self.assertEqual(obj["coords"], [])
        self.assertEqual(len(list((self.output / EVENTS).glob("*.json"))), 494)
        control = (ROOT / "src/field/field_control.c").read_text()
        self.assertIn("if (sub_020548C0(fieldSystem, x, z) == FALSE)", control)
        self.assertIn("if (MetatileBehavior_IsDoor(metatileBehavior))", control)
        self.assertIn("FieldSystem_MapConnection(fieldSystem, x, z, &nextMap) && fieldInput->transitionDir != DIR_NONE",
                      control)
        self.assertIn("NewFieldTransitionEnvironment(fieldSystem, nextMap.mapId, nextMap.warpId, 0, 0, fieldInput->transitionDir, 1);",
                      control)
        self.assertIn("MetatileBehavior_IsWarpNorth(metatileBehavior)", control)
        self.assertIn("MetatileBehavior_IsWarpSouth(metatileBehavior)", control)
        # Sources point into inert destination rows, never another warp tile.
        for kind, destination, source_indices, targets in (
                ("town", "route", (1, 2), (2, 3)),
                ("route", "town", (0, 1), (3, 4))):
            for src, target in zip(source_indices, targets):
                source = self.manifest["events"][kind][src]
                arrival = self.manifest["events"][destination][target]
                self.assertEqual(source["anchor"], target)
                self.assertEqual(source["x"], arrival["x"])
                self.assertEqual(arrival["z"], 17 if destination == "route" else 2)
                self.assertNotIn((arrival["x"], arrival["z"]),
                                 {(e["x"], e["z"]) for e in
                                  self.manifest["changed_terrain"][destination]})
        for source in (ROOT / EVENTS).glob("*.json"):
            self.assertEqual((self.output / EVENTS / source.name).read_bytes(),
                             source.read_bytes(), source.name)
        with self.assertRaisesRegex(ValueError, "existing output"):
            prepare(ROOT, DONOR, RESOURCE, LAB_ASSETS, self.output)

    def test_stock_files_and_collision_consistency(self):
        staged = narc_members((RESOURCE / LAND).read_bytes())
        after = narc_members((self.output / LAND).read_bytes())
        self.assertEqual(after[:676], staged[:676])
        self.assertEqual(len(after), len(staged))
        changes = self.manifest["changed_terrain"]
        self.assertEqual({k: len(v) for k, v in changes.items()},
                         {"lab": 2, "town": 3, "route": 2})
        for kind, _, map_id, area, member, matrix, event, matrix_name, _ in MAPS:
            binding = self.manifest["bindings"][kind]
            self.assertEqual((binding["planned_map"], binding["area"], binding["land"],
                              binding["matrix"], binding["planned_events"]),
                             (map_id, area, member, matrix, event))
            before, changed = Land.decode(staged[member]), Land.decode(after[member])
            self.assertEqual((before.marker, before.extra, before.props, before.model,
                              before.collision),
                             (changed.marker, changed.extra, changed.props, changed.model,
                              changed.collision))
            if kind in ("lab", "town"):
                self.assertEqual(changed.props, b"")
            old, new = (struct.unpack("<1024H", value.terrain) for value in (before, changed))
            expected = {(cell["x"], cell["z"]): (cell["old"], cell["new"])
                        for cell in changes[kind]}
            observed = {(x, z): (old[z * 32 + x], new[z * 32 + x])
                        for z in range(32) for x in range(32)
                        if old[z * 32 + x] != new[z * 32 + x]}
            self.assertEqual(observed, expected)
            for (x, z), (old_word, new_word) in observed.items():
                self.assertEqual(old_word & 0x8000, new_word & 0x8000)
                self.assertEqual(new_word & 0x7f00, old_word & 0x7f00)
                self.assertIn(new_word & 0xff, (105, 110, 111))
            if kind != "lab":
                self.assertTrue(all(new[z * 32 + x] == 0x8000
                                    for z in (0, 19) for x in range(20)))
                self.assertTrue(all(new[z * 32 + x] == 0x8000
                                    for z in range(20) for x in (0, 19)))
                self.assertTrue(all(new[z * 32 + x] == 0x8000
                                    for z in range(32) for x in range(32)
                                    if x >= 20 or z >= 20))
                self.assertTrue(all(new[(2 if kind == "town" else 17) * 32 + x] == 0
                                    for x in (10, 11)))
                self.assertTrue(all(new[(3 if kind == "town" else 16) * 32 + x] == 0
                                    for x in (10, 11)))
            self.assertEqual((self.output / MATRIX_DIR / matrix_name).read_bytes(),
                             (RESOURCE / MATRIX_DIR / matrix_name).read_bytes())
        for kind in ("areas", "textures"):
            self.assertEqual((self.output / ARCHIVES[kind]).read_bytes(),
                             (RESOURCE / ARCHIVES[kind]).read_bytes())
        self.assertEqual((self.output / ARCHIVES["props"]).read_bytes(),
                         (ROOT / ARCHIVES["props"]).read_bytes())
        for path, expected in self.manifest["output_sha256"].items():
            self.assertEqual(digest((self.output / path).read_bytes()), expected)
        self.assertEqual(json.loads((self.output / "opening-travel.json").read_text()),
                         self.manifest)

    def test_map_headers_no_forced_rescue_and_existing_johto_unchanged(self):
        source = (ROOT / "src/data/map_headers.h").read_text()
        generated = (self.output / "src/data/map_headers.h").read_text()
        constants = (self.output / "include/constants/maps.h").read_text()
        self.assertTrue(generated.startswith(source.rsplit("\n};", 1)[0]))
        for kind, map_id, map_type, area, matrix, event in (
                ("HOENN_LAB_DEBUG", 540, "MAP_TYPE_INTERIOR", 106, 288, 491),
                ("LITTLEROOT_TOWN_TRAVEL", 541, "MAP_TYPE_CITY_TOWN", 107, 289, 492),
                ("ROUTE_101_TRAVEL", 542, "MAP_TYPE_ROUTE", 108, 290, 493)):
            header = generated.split(f"[MAP_{kind}] = {{", 1)[1].split("},", 1)[0]
            self.assertIn(f"#define MAP_{kind} {map_id}", constants)
            self.assertIn(f".areaDataBank = {area},", header)
            self.assertIn(f".matrixId = {matrix},", header)
            self.assertIn(f".eventsBank = {event},", header)
            self.assertIn(".wildEncounterBank = ENCDATA_NA,", header)
            if kind != "HOENN_LAB_DEBUG":
                self.assertIn(f".mapType = {map_type},", header)
                self.assertIn(".regionNo = MAP_REGION_JOHTO,", header)
                self.assertIn(".followMode = MAP_FOLLOWMODE_PREVENT,", header)
        self.assertIn("#define MAP_ID_MAX 543", constants)
        self.assertEqual(json.loads((self.output / "expansion/baseline.json").read_text())
                         ["capacities"]["map_count"], 543)
        scripts = "files/fielddata/script/scr_seq"
        original_reward = (ROOT / scripts / "scr_seq_0965_hoenn_reward.s").read_text()
        edited_reward = (self.output / scripts / "scr_seq_0965_hoenn_reward.s").read_text()
        self.assertEqual(edited_reward.replace("ScrDef HoennDebug_Return\nScrDefEnd",
                                               "ScrDefEnd").split(
                                                   "\n// DEBUG ONLY: return NPC", 1)[0],
                         original_reward)
        self.assertIn("ScrDef HoennRescue_Interaction", edited_reward)
        self.assertIn("ScrDef HoennDebug_Return", edited_reward)
        elm = (self.output / scripts / "scr_seq_0843_T20R0101.s").read_text()
        original_elm = (ROOT / scripts / "scr_seq_0843_T20R0101.s").read_text()
        ingress = elm.split("scr_seq_T20R0101_000:", 1)[1].split(
            "HoennDebug_ElmOriginal:", 1)[0]
        self.assertEqual(elm.replace(
            "scr_seq_T20R0101_000:" + ingress + "HoennDebug_ElmOriginal:\n",
            "scr_seq_T20R0101_000:", 1), original_elm)
        self.assertNotIn("SetVar 0x416e", ingress)
        self.assertIn("Warp 540, 0, 16, 19, 0", ingress)
        self.assertFalse(self.manifest["eligibility_injected"])
        self.assertNotIn("actor", self.manifest)
        self.assertEqual((self.output / SPRITES).read_bytes(), (ROOT / SPRITES).read_bytes())
        self.assertEqual((self.output / TABLE).read_bytes(), (ROOT / TABLE).read_bytes())
        self.assertFalse((self.output / member_path()).exists())
        warp_command = (ROOT / "src/scrcmd_c.c").read_text().split(
            "BOOL ScrCmd_Warp(ScriptContext *ctx) {", 1)[1].split("\n}", 1)[0]
        self.assertIn("u16 unused = ScriptReadHalfword(ctx);", warp_command)
        self.assertIn("CallTask_ScriptWarp(ctx->taskman, mapId, -1, x, y, direction);",
                      warp_command)
        event_arrival = (ROOT / "src/field_warp_tasks.c").read_text().split(
            "static void sub_02052F94(FieldSystem *fieldSystem, Location *location) {", 1)[1]
        event_arrival = event_arrival.split("\n}", 1)[0]
        self.assertIn("fieldSystem->location->x = warp->x;", event_arrival)
        self.assertIn("fieldSystem->location->y = warp->z;", event_arrival)
        self.assertFalse(self.manifest["warp_resolution_audit"]["runtime_verified"])
        self.assertEqual(self.manifest["matrix_u8_alias_audit"]["aliases"],
                         {"288": 32, "289": 33, "290": 34})
        matrix_header = (ROOT / "include/map_matrix.h").read_text()
        self.assertIn("u8 matrix_id;", matrix_header)
        matrix_source = (ROOT / "src/map_matrix.c").read_text()
        self.assertIn("u16 matrix_id = MapHeader_GetMatrixId(map_no);", matrix_source)
        self.assertIn("MapMatrix_MapMatrixData_Load(&map_matrix->data, matrix_id, map_no);",
                      matrix_source)
        self.assertIn("map_matrix->matrix_id = matrix_id;", matrix_source)
        self.assertIn("#pragma unused(matrix_id)", matrix_source)
        self.assertIn("NARC_map_matrix_map_matrix_0000_EVERYWHERE_bin", matrix_source)
        self.assertIn("NARC_map_matrix_map_matrix_0212_D47R0102_bin", matrix_source)
        self.assertIn("MapHeader.areaDataBank u8",
                      self.manifest["id_width_audit"]["area"])

    def test_native_transition_callbacks_and_only_private_pair_is_rerouted(self):
        original = (ROOT / "src/unk_02055BF0.c").read_text()
        generated = (self.output / "src/unk_02055BF0.c").read_text()
        self.assertEqual(generated.count(OUTDOOR_TRANSITION_BRANCH), 1)
        self.assertEqual(generated.replace(OUTDOOR_TRANSITION_BRANCH,
                                           "    if (MapHeader_IsCave(otherID)) {", 1).replace(
                                               '#include "constants/maps.h"\n', "", 1), original)
        self.assertIn("GF_ASSERT(FALSE);", original.split(
            "if (MapHeader_IsOutdoors(otherID)) {", 1)[1].split(
                "} else if (MapHeader_IsInBuilding(otherID)) {", 1)[0])
        self.assertEqual(self.manifest["transition_source_audit"]
                         ["private_outdoor_pair"], [541, 542])
        self.assertEqual(self.manifest["transition_source_audit"]
                         ["private_outdoor_transition_no"], 6)
        self.assertFalse(self.manifest["transition_source_audit"]["runtime_verified"])
        data = (ROOT / "asm/unk_02055BF0_data.s").read_text()
        def entries(name, next_name):
            body = data.split(name + ":\n", 1)[1].split(
                next_name if next_name == ".text" else next_name + ":", 1)[0]
            return [line.strip().split(" ", 1)[1] for line in
                    body.splitlines()
                    if line.strip().startswith(".word ")]
        enters = entries("sMapEnterRoutines", "sMapExitRoutines")
        exits = entries("sMapExitRoutines", "_020FC76C")
        posts = entries("_020FC76C", ".text")
        self.assertEqual(len(enters), 9)
        self.assertEqual(len(exits), 9)
        self.assertEqual(exits[1], "sub_02056040")
        self.assertEqual(exits[6], "sub_02056004")
        self.assertEqual(enters[1], enters[6])
        self.assertEqual(enters[6], "sub_020565FC")
        self.assertEqual(posts[6], "0")
        self.assertIn("TaskManager_Call(man, sMapExitRoutines[env->transitionNo], env);",
                      original)
        self.assertIn("TaskManager_Call(man, sMapEnterRoutines[env->transitionNo], env);",
                      original)
        self.assertIn("TaskManager_Jump(man, sub_02056530, fenv);", original)
        self.assertIn("if (ov01_021E90E4(fieldSystem, fenv->unk18))", original)
        self.assertIn("if (ov01_021E9374(fieldSystem, unk))", original)
        callbacks = (ROOT / "asm/overlay_01_021E90C0.s").read_text()
        self.assertIn("beq _021E91F4", callbacks)  # Exit door without map prop.
        self.assertIn("_021E91F4:\n\tadd sp, #0x58\n\tmov r0, #1", callbacks)
        self.assertIn("beq _021E9476", callbacks)  # Enter door without map prop.
        self.assertIn("_021E9476:\n\tmov r0, #1\n\tbl FieldMap_FadeScreen", callbacks)
        generic_entry = callbacks.split("ov01_021EA128: ;", 1)[1].split(
            "thumb_func_end ov01_021EA128", 1)[0]
        self.assertIn("cmp r0, #1\n\tbne _021EA178", generic_entry)
        self.assertIn("mov r1, #0xd\n\tbl MapObject_SetHeldMovement", generic_entry)
        self.assertIn("#define DIR_SOUTH 1",
                      (ROOT / "include/constants/global_fieldmap.h").read_text())
        self.assertIn("return &mapPropManager->mapProps[index];",
                      (ROOT / "src/field/map_prop_manager.c").read_text())

    def test_fail_closed_on_source_resource_and_donor_drift(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "native"
            root.mkdir()
            destination = Path(directory) / "would-be-output"
            for relative in SOURCE_SHA256:
                target = root / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                target.symlink_to(ROOT / relative)
            broken = root / "include/constants/maps.h"
            broken.unlink()
            broken.write_bytes((ROOT / "include/constants/maps.h").read_bytes() + b"// changed\n")
            with self.assertRaisesRegex(ValueError, "Native source drift: include/constants/maps.h"):
                prepare(root, DONOR, RESOURCE, LAB_ASSETS, destination)
            self.assertFalse(destination.exists())
            broken = root / "src/unk_02055BF0.c"
            broken.unlink()
            broken.write_bytes((ROOT / "src/unk_02055BF0.c").read_bytes() + b"// changed\n")
            # Restore the first fault to make sure the actual transition source
            # is independently pinned, not merely blocked by the map constants.
            (root / "include/constants/maps.h").unlink()
            (root / "include/constants/maps.h").symlink_to(
                ROOT / "include/constants/maps.h")
            with self.assertRaisesRegex(ValueError, "Native source drift: src/unk_02055BF0.c"):
                prepare(root, DONOR, RESOURCE, LAB_ASSETS, destination)
            self.assertFalse(destination.exists())
        maps, _, _, _ = verified_source(ROOT, DONOR, RESOURCE, LAB_ASSETS)
        maps["Route101"]["connections"][1]["offset"] = 1
        with self.assertRaisesRegex(ValueError, "Route 101 south connection"):
            donor_travel(maps)
        with tempfile.TemporaryDirectory() as directory:
            resource = Path(directory)
            manifest = json.loads((RESOURCE / "manifest.json").read_text())
            manifest["status"] = "unreviewed-native-grass-probe"
            (resource / "manifest.json").write_text(json.dumps(manifest))
            with self.assertRaisesRegex(ValueError, "not the conservative resource stage"):
                prepare(ROOT, DONOR, resource, LAB_ASSETS, resource / "partial")
            self.assertFalse((resource / "partial").exists())
        # Native event struct must fail closed instead of wrapping u16 IDs.
        with self.assertRaises(struct.error):
            warp_bytes(dict(x=0, z=0, header=65536, anchor=0, y=0))

    def test_source_tree_output_and_actor_preflight_fail_before_resource_reads(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "empty-source"
            root.mkdir()
            # Donor, resources and lab assets do not exist. This MUST fail on
            # output containment before attempting to open any of them.
            destination = root / "nested" / "output"
            with self.assertRaisesRegex(ValueError, "outside source tree"):
                prepare(root, root / "missing-donor", root / "missing-resource",
                        root / "missing-lab", destination, actor=root / "missing-birch")
            self.assertFalse(destination.exists())
            bad = Path(directory) / "bad-actor.nsbtx"
            bad.write_bytes(b"unaudited actor")
            destination = Path(directory) / "bad-actor-output"
            with self.assertRaisesRegex(ValueError, "Unaudited Birch actor texture"):
                prepare(ROOT, root / "missing-donor", root / "missing-resource",
                        root / "missing-lab", destination, actor=bad)
            self.assertFalse(destination.exists())
            if ACTOR.exists():
                altered = root / "scripts/prepare_birch_actor_probe.py"
                altered.parent.mkdir(parents=True)
                altered.write_bytes((ROOT / "scripts/prepare_birch_actor_probe.py"
                                     ).read_bytes() + b"\n# drift\n")
                with self.assertRaisesRegex(ValueError, "Birch actor installer drift"):
                    prepare(root, root / "missing-donor", root / "missing-resource",
                            root / "missing-lab", Path(directory) / "bad-installer-output",
                            actor=ACTOR)
                self.assertFalse((Path(directory) / "bad-installer-output").exists())
                native = root / "audited-source"
                script = native / "scripts/prepare_birch_actor_probe.py"
                script.parent.mkdir(parents=True)
                script.symlink_to(ROOT / "scripts/prepare_birch_actor_probe.py")
                mmodel = native / MMODEL
                mmodel.mkdir(parents=True)
                for original in (ROOT / MMODEL).iterdir():
                    (mmodel / original.name).symlink_to(original)
                damaged = mmodel / "mmodel_00000000.NSBTX"
                self.assertTrue(damaged.is_symlink())
                damaged.unlink()
                damaged.write_bytes((ROOT / MMODEL / damaged.name).read_bytes() + b"\0")
                with self.assertRaisesRegex(ValueError, "Unaudited members drift"):
                    prepare(native, root / "missing-donor", root / "missing-resource",
                            root / "missing-lab", Path(directory) / "bad-native-output",
                            actor=ACTOR)
                self.assertFalse((Path(directory) / "bad-native-output").exists())

    def test_optional_birch_actor_composition_preserves_travel_and_stock(self):
        if not ACTOR.exists():
            self.skipTest("Private SHA-pinned Birch member required")
        self.assertEqual(digest(ACTOR.read_bytes()), ACTOR_SHA256)
        combined = self.base / "travel-with-actor"
        report = prepare(ROOT, DONOR, RESOURCE, LAB_ASSETS, combined, actor=ACTOR)
        self.assertFalse(report["eligibility_injected"])
        self.assertFalse(report["actor"]["runtime_verified"])
        self.assertEqual(report["status"],
                         "private-three-map-native-door-edge-travel-with-birch-actor-unverified-runtime")
        self.assertEqual(report["actor"]["actor_sha256"], ACTOR_SHA256)
        self.assertEqual(report["actor"]["texture_member"], MEMBER)
        self.assertEqual(report["actor"]["native_mmodel_members_preserved"], MEMBER)
        self.assertEqual(report["actor"]["source_audit_sha256"],
                         report["actor"]["archive_audit_sha256"])
        self.assertEqual(report["actor"]["binding_files"],
                         [str(SPRITES), str(TABLE), str(member_path()),
                          f"{EVENTS}/491_HOENN_LAB_DEBUG.json"])
        self.assertTrue(report["actor"]["travel_warps_preserved"])
        self.assertEqual((combined / member_path()).read_bytes(), ACTOR.read_bytes())
        self.assertEqual(sorted(p.name for p in (combined / MMODEL).glob("mmodel_*")),
                         sorted([*(p.name for p in (ROOT / MMODEL).glob("mmodel_*")),
                                 member_path().name]))
        def compiled(path):
            if path.suffix != ".json":
                return path.read_bytes()
            rows = json.loads(path.read_text())["data"]
            return (struct.pack("<I", len(rows))
                    + struct.pack("<" + "H" * len(rows), *(v["unk0"] for v in rows))
                    + bytes(v["unk1"] for v in rows) + bytes(v["unk2"] for v in rows))
        stock = [compiled(p) for p in sorted((ROOT / MMODEL).glob("mmodel_*"))]
        appended = [compiled(p) for p in sorted((combined / MMODEL).glob("mmodel_*"))]
        packed = narc_members(pack_narc(appended))
        self.assertEqual(len(packed), MEMBER + 1)
        self.assertEqual(packed[:MEMBER], stock)
        self.assertEqual(packed[MEMBER], ACTOR.read_bytes())
        for p in (ROOT / MMODEL).glob("mmodel_*"):
            self.assertEqual((combined / MMODEL / p.name).read_bytes(), p.read_bytes())
        self.assertEqual((combined / TABLE).read_text().replace(ROW + "\n", ""),
                         (ROOT / TABLE).read_text())
        self.assertIn(ROW + "\n" + SENTINEL, (combined / TABLE).read_text())
        self.assertEqual((combined / SPRITES).read_text().replace(
            f"// PRIVATE PROBE ONLY: unused ordinary-sprite gap.\n"
            f"#define {SPRITE_NAME} 32\n\n", ""), (ROOT / SPRITES).read_text())
        event = f"{EVENTS}/491_HOENN_LAB_DEBUG.json"
        original_text = (self.output / event).read_text()
        changed_text = (combined / event).read_text()
        original = json.loads(original_text)
        changed = json.loads(changed_text)
        self.assertEqual(original["warps"], changed["warps"])
        self.assertEqual(original_text.split('"warps": ', 1)[1].split(
            ',\n  "coords":', 1)[0], changed_text.split('"warps": ', 1)[1].split(
                ',\n  "coords":', 1)[0])
        for index in range(3):
            old_actor, new_actor = original["objects"][index], changed["objects"][index]
            self.assertEqual({key: value for key, value in old_actor.items()
                              if key != "spriteId"},
                             {key: value for key, value in new_actor.items()
                              if key != "spriteId"})
            self.assertEqual(new_actor["spriteId"],
                             SPRITE_NAME if index in (0, 2) else old_actor["spriteId"])
        for kind, number in (("town", 492), ("route", 493)):
            path = f"{EVENTS}/{number}_{'LITTLEROOT_TOWN_TRAVEL' if kind == 'town' else 'ROUTE_101_TRAVEL'}.json"
            self.assertEqual((combined / path).read_bytes(), (self.output / path).read_bytes())
            self.assertEqual(report["events"][kind], self.manifest["events"][kind])
        for kind in ("areas", "textures", "land"):
            path = ARCHIVES[kind]
            self.assertEqual((combined / path).read_bytes(),
                             (self.output / path).read_bytes())
        for path, digest_expected in report["output_sha256"].items():
            self.assertEqual(digest((combined / path).read_bytes()), digest_expected)
        for path, digest_expected in report["actor"]["binding_sha256"].items():
            self.assertEqual(digest((combined / path).read_bytes()), digest_expected)
        self.assertNotEqual(report["output_sha256"][event],
                            self.manifest["output_sha256"][event])
        self.assertEqual(json.loads((combined / "opening-travel.json").read_text()), report)


if __name__ == "__main__":
    unittest.main()