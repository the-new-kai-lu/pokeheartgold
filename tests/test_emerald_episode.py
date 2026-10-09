"""Separate opt-in episode tests; default travel/message assertions stay intact.

Set EPISODE_TREE and EPISODE_GOLDEN to source trees for complete input parity.
These tests do not build, launch an emulator, or assert runtime success.
"""
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import time
import unittest
from unittest import mock
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import episode_assets
from episode_source_inventory import native_inputs, verify_compiled_inventory, EPISODE_SCRIPT_BANKS
from export_lab_model import container
from hgss_land import Land, narc_members
from prepare_emerald_episode import (
    FINAL_ARCHIVES, LAND, TEXTURES, MODELS, guard_path, native_edits, sha,
    publish_directory, approved_contract, prepare,
)
from stage_emerald_episode import stage
from stage_lab_archives import pack_narc


class EpisodeUnitTests(unittest.TestCase):
    def test_atomic_publish_preserves_existing_empty_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            source, dest = Path(tmp) / "source", Path(tmp) / "destination"
            source.mkdir()
            (source / "payload").write_text("payload")
            dest.mkdir()
            before = dest.stat().st_ino
            with self.assertRaises(FileExistsError):
                publish_directory(source, dest)
            self.assertEqual(dest.stat().st_ino, before)
            self.assertEqual(list(dest.iterdir()), [])
            self.assertTrue((source / "payload").exists())
            dest.rmdir()
            publish_directory(source, dest)
            self.assertFalse(source.exists())
            self.assertEqual((dest / "payload").read_text(), "payload")

    def test_safe_output_parents(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "alias").symlink_to(root, target_is_directory=True)
            with self.assertRaises(ValueError):
                guard_path(root / "alias" / "fresh")

    def test_preflight_is_all_or_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "a").write_bytes(b"old\n")
            recipe = {
                "a": {"before": sha(b"old\n"), "after": sha(b"new\n"),
                      "edits": [{"start": 0, "end": 1, "lines": ["new\n"]}]},
                "b": {"before": "incorrect", "after": sha(b""),
                      "edits": []},
            }
            with self.assertRaises(ValueError):
                native_edits(root, recipe)
            self.assertEqual((root / "a").read_bytes(), b"old\n")

    def test_template_append_and_hash_guards(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            recipe = {"added": {"before": None, "after": sha(b"new\n"),
                               "edits": [{"start": 0, "end": 0, "lines": ["new\n"]}]}}
            native_edits(root, recipe)
            self.assertEqual((root / "added").read_bytes(), b"new\n")
            with self.assertRaises(ValueError):
                native_edits(root, recipe)

    def test_actor_repair_header_uses_resume_not_early_load(self):
        name = "files/fielddata/script/scr_seq/scr_seq_0966_route101_opening_hdr.s"
        recipe = json.loads((ROOT / "scripts/episode_templates/native_edits.json").read_text())
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            native_edits(root, {name: recipe[name]})
            header = (root / name).read_text()
            self.assertEqual(header.count("InitScriptEntry_OnResume 5\n"), 1)
            self.assertNotIn("InitScriptEntry_OnLoad ", header)
            self.assertLess(header.index("InitScriptEntry_OnResume 5\n"),
                            header.index("InitScriptEntry_OnFrameTable "))
            self.assertEqual(sha((root / name).read_bytes()),
                             approved_contract()[name]["after"])

    def test_native_resume_follows_terrain_manager_initialization(self):
        # Source-order regression guard, not a substitute for native menu tests.
        # MovePersonFacing in script 5 consults the terrain manager. OnLoad can
        # see its old freed pointer after returning from a party/menu overlay.
        source = (ROOT / "src/field/fieldmap.c").read_text()
        initializer = source.split("BOOL FieldMap_Init(", 1)[1].split(
            "BOOL FieldMap_Main(", 1)[0]
        anchors = (
            "case FIELD_MAP_INIT_STATE_RESET:",
            "TryStartMapScriptByType(fieldSystem, INIT_SCRIPT_ON_LOAD);",
            "case FIELD_MAP_INIT_STATE_LOAD:",
            "FieldSystem_InitMapLoadManager(fieldSystem);",
            "TryStartMapScriptByType(fieldSystem, INIT_SCRIPT_ON_RESUME);",
            "case FIELD_MAP_INIT_STATE_BOTTOM_SCREEN:",
        )
        positions = [initializer.index(anchor) for anchor in anchors]
        self.assertEqual(positions, sorted(positions))
        manager_init = source.split(
            "static void FieldSystem_InitMapLoadManager(FieldSystem *fieldSystem) {", 1
        )[1].split("\n}", 1)[0]
        self.assertIn(
            "fieldSystem->dynamicTerrainHeightManager = "
            "DynamicTerrainHeightManager_New(8, HEAP_ID_FIELD1);", manager_init)

    def test_compact_geometry_budget(self):
        commands, audit = episode_assets.commands_for([0] * 1024)
        self.assertEqual(audit["begin_quads"], 1024)
        self.assertEqual(audit["vertices"], 4096)
        self.assertEqual(audit["actual_stream_bytes"], len(commands))
        self.assertEqual(len(commands), 8 + 1024 * 52)
        model = container(b"BMD0", (episode_assets.model(0, commands),))
        self.assertEqual(len(model), 53676)
        self.assertLessEqual(len(episode_assets.ensure_model_fits(model)),
                             episode_assets.MAX_FIELD_MODEL_BYTES)

    def test_independently_decode_packed_geometry_and_all_scene_pixels(self):
        # An independent physical display-list parser, not episode_assets.decode_gx.
        colors = [bytes((value * 255 // 31,) * 3 + (255,)) for value in range(31)]
        source = bytearray(512 * 512 * 4)
        for z in range(32):
            for x in range(32):
                identity = (x + z * 3) % 12
                for py in range(16):
                    for px in range(16):
                        pixel = ((z * 16 + py) * 512 + x * 16 + px) * 4
                        source[pixel:pixel + 4] = colors[(identity * 2 + px // 4 + py // 4) % 31]
        image, palette, indices, unique = episode_assets.atlas_for(source)
        self.assertEqual(len(unique), 12)
        commands, geometry = episode_assets.commands_for(indices)
        self.assertEqual(geometry["vertices"], 4096)
        self.assertEqual(len(commands), 53256)
        physical, offset, noop = [], 0, 0
        nargs = {0: 0, 0x20: 1, 0x22: 1, 0x23: 2, 0x26: 1, 0x40: 1, 0x41: 0}
        while offset < len(commands):
            opword = struct.unpack_from("<I", commands, offset)[0]
            offset += 4
            for shift in (0, 8, 16, 24):
                opcode = opword >> shift & 255
                self.assertIn(opcode, nargs)
                count = nargs[opcode]
                self.assertLessEqual(offset + 4 * count, len(commands))
                operands = struct.unpack_from("<" + "I" * count, commands, offset)
                offset += 4 * count
                if opcode:
                    physical.append((opcode, operands))
                else:
                    noop += 1
        self.assertEqual(offset, len(commands))
        self.assertEqual(noop, 3 + 2 * 1024)
        self.assertEqual(physical[0], (0x20, (0x7fff,)))
        self.assertEqual(len(physical), 1 + 1024 * 10)
        position = 1
        for z in range(32):
            for x in range(32):
                self.assertEqual(physical[position], (0x40, (1,)))
                position += 1
                index = indices[z * 32 + x]
                atlas_x = index % episode_assets.COLS * episode_assets.SLOT + 1
                atlas_y = index // episode_assets.COLS * episode_assets.SLOT + 1
                for vertex, (dx, dz) in enumerate(((0, 0), (0, 16), (16, 16), (16, 0))):
                    uv = (atlas_x + dx) * 16 | ((atlas_y + dz) * 16 << 16)
                    self.assertEqual(physical[position], (0x22, (uv,)))
                    position += 1
                    opcode, operands = physical[position]
                    self.assertEqual(opcode, 0x23 if vertex == 0 else 0x26)
                    if vertex == 0:
                        self.assertEqual(operands[0] >> 16, 0)  # explicit y=0
                        self.assertEqual(operands[1] >> 16, 0)
                        raw_x, raw_z = operands
                    else:
                        raw_x, raw_z = operands[0] & 0xffff, operands[0] >> 16
                    self.assertEqual(struct.unpack("<h", struct.pack("<H", raw_x))[0],
                                     (x * 16 + dx - 256) * 64)
                    self.assertEqual(struct.unpack("<h", struct.pack("<H", raw_z))[0],
                                     (z * 16 + dz - 256) * 64)
                    position += 1
                self.assertEqual(physical[position], (0x41, ()))
                position += 1
                # Decode every pixel through the UV-selected atlas tile.
                for py in range(16):
                    for px in range(16):
                        color = palette[image[(atlas_y + py) * episode_assets.ATLAS_W
                                              + atlas_x + px]]
                        decoded = bytes((((color >> (5 * c)) & 31) * 255 // 31
                                         for c in range(3))) + b"\xff"
                        pixel = ((z * 16 + py) * 512 + x * 16 + px) * 4
                        self.assertEqual(source[pixel:pixel + 4], decoded)
        self.assertEqual(position, len(physical))

    def test_model_budget_fails_closed_on_oversize_or_truncated_stream(self):
        with self.assertRaisesRegex(ValueError, "safe per-slot"):
            episode_assets.model(0, b"\0" * episode_assets.MAX_FIELD_MODEL_BYTES)
        with self.assertRaisesRegex(ValueError, "safe per-slot"):
            episode_assets.ensure_model_fits(
                container(b"BMD0", (b"MDL0" + b"\0" * episode_assets.MAX_FIELD_MODEL_BYTES,)))
        with self.assertRaisesRegex(ValueError, "Truncated GX"):
            list(episode_assets.decode_gx(struct.pack("<I", 0x23)))
        with self.assertRaisesRegex(ValueError, "Unsupported GX"):
            episode_assets.pack_gx([(0xff, ())])

    def test_stage_rejects_oversize_actual_archive_despite_claimed_hash(self):
        from prepare_emerald_episode import LAND
        with tempfile.TemporaryDirectory() as tmp:
            prepared, output = Path(tmp) / "prepared", Path(tmp) / "overlay"
            (prepared / LAND).parent.mkdir(parents=True)
            oversized = container(b"BMD0", (b"MDL0" + b"\0" * 0xe000,))
            member = Land(0, b"", b"\0" * 2048, b"", oversized, b"").encode()
            archive = pack_narc([b""] * 678 + [member])
            (prepared / LAND).write_bytes(archive)
            (prepared / "opening-episode.json").write_text(json.dumps({
                "status": "source-only-full-opening-not-runtime-proof",
                "native_input_sha256": {LAND: sha(archive)},
                "episode_changes_sha256": {LAND: sha(archive)},
                "compact": {"model_sha256": sha(oversized)},
            }))
            with self.assertRaisesRegex(ValueError, "safe per-slot"):
                stage(ROOT, prepared, output)
            self.assertFalse(output.exists())

    def test_no_private_dependency_or_graphics_in_templates(self):
        for file in (ROOT / "scripts/episode_templates").iterdir():
            self.assertEqual(file.suffix, ".json")
            data = file.read_text()
            self.assertNotIn("/tmp/", data)
            self.assertNotIn("/workspace/", data)

    def test_compiled_inventory_requires_scoped_pins_and_original_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            with self.assertRaisesRegex(ValueError, "Exactly the three"):
                verify_compiled_inventory(directory, ROOT / "scr_seq.sha1", {})
            pins = {name: "0" * 40 for name in EPISODE_SCRIPT_BANKS}
            with self.assertRaisesRegex(ValueError, "bank inventory differs"):
                verify_compiled_inventory(directory, ROOT / "scr_seq.sha1", pins)
            (directory / "altered.sha1").write_text("not the baseline\n")
            with self.assertRaisesRegex(ValueError, "pinned baseline"):
                verify_compiled_inventory(directory, directory / "altered.sha1", pins)


@unittest.skipUnless(os.environ.get("EPISODE_TREE"), "set EPISODE_TREE for source integration")
class EpisodeSourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tree = Path(os.environ["EPISODE_TREE"])
        cls.report = json.loads((cls.tree / "opening-episode.json").read_text())
        cls.bank = cls.text("files/fielddata/script/scr_seq/scr_seq_0965_hoenn_reward.s")

    @classmethod
    def text(cls, name):
        return (cls.tree / name).read_text()

    def test_complete_manifest(self):
        self.assertEqual(native_inputs(ROOT, self.tree), self.report["native_input_sha256"])
        self.assertFalse(self.report["runtime_verified"])

    def test_correct_texture_archive_and_all_overworld_preservation(self):
        for name, expected in FINAL_ARCHIVES.items():
            self.assertEqual(sha((self.tree / name).read_bytes()), expected)
        for name, expected in self.report["preserved_travel_overworld_sources"].items():
            self.assertEqual(sha((self.tree / MODELS / name).read_bytes()), expected, name)
        # The rejected r1 defect overwrote this unrelated vanilla actor texture.
        original = ROOT / MODELS / "mmodel_00000108.NSBTX"
        self.assertEqual((self.tree / MODELS / original.name).read_bytes(), original.read_bytes())
        archive = narc_members((self.tree / TEXTURES).read_bytes())
        self.assertEqual(len(archive), 109)
        tex = archive[108]
        start = struct.unpack_from("<I", tex, 16)[0]
        self.assertEqual(struct.unpack_from("<H", tex, start + 12)[0] * 8, 32768)
        for name, ledger in self.report["archive_members"].items():
            before, after = ledger["before_members"], ledger["after_members"]
            self.assertEqual(len(before), len(after))
            self.assertEqual([i for i, pair in enumerate(zip(before, after))
                              if pair[0] != pair[1]], [ledger["changed_member"]])

    def test_scene_inventory_messages_and_cold_actor_recovery(self):
        self.assertEqual(len(re.findall(r"^ScrDef ", self.bank, re.M)), 10)
        gmm = ET.fromstring(self.text("files/msgdata/msg/msg_0829_hoenn_reward.gmm"))
        self.assertEqual(len(gmm.findall(".//row")), 22)
        header = self.text("files/fielddata/script/scr_seq/scr_seq_0966_route101_opening_hdr.s")
        self.assertIn("InitScriptEntry_OnResume 5", header)
        self.assertNotIn("InitScriptEntry_OnLoad ", header)
        self.assertIn("InitScriptGoToIfEqual VAR_TEMP_x4000, 3, 7", header)
        self.assertIn("EnsureRoute101Actors VAR_TEMP_x4003", self.bank)
        ensure = self.text("src/scrcmd_c.c").split("BOOL ScrCmd_EnsureRoute101Actors", 1)[1]
        self.assertIn("MapObject_CreateFromObjectEventWithId", ensure)
        self.assertIn("activeCount + missing >= 64", ensure)
        self.assertIn("MapObject_GetMapID(object) != MAP_ROUTE_101_TRAVEL", ensure)

    @unittest.skipUnless(all(shutil.which(tool) for tool in (
        "gcc", "arm-none-eabi-as", "arm-none-eabi-objcopy")),
        "Native ARM script regression requires gcc and binutils-arm-none-eabi")
    def test_compiled_resume_header_changes_only_init_type_in_both_editions(self):
        from test_native_field_scripts import native
        text = self.text("files/fielddata/script/scr_seq/scr_seq_0966_route101_opening_hdr.s")
        self.assertEqual(text.count("InitScriptEntry_OnResume 5\n"), 1)
        includes = [self.tree / name for name in ("include", "files", "asm", "lib/include")]
        includes.append(self.tree)
        with tempfile.TemporaryDirectory() as tmp:
            for edition in ("HEARTGOLD", "SOULSILVER"):
                directory = Path(tmp) / edition
                macro = directory / "asm/macros/script.inc"
                macro.parent.mkdir(parents=True)
                macro.write_text(native.preprocess(
                    self.tree / "asm/macros/script.inc", edition, includes))
                data = []
                for label, source_text in (
                    ("early", text.replace("InitScriptEntry_OnResume 5\n",
                                           "InitScriptEntry_OnLoad 5\n")),
                    ("resume", text),
                ):
                    source = Path(tmp) / (label + ".s")
                    source.write_text(source_text)
                    bank, _ = native.assemble_bank(source, directory, edition, includes)
                    data.append((directory / bank).read_bytes())
                before, after = data
                self.assertEqual(len(before), len(after))
                self.assertEqual((before[0], after[0]), (4, 3))
                self.assertEqual(before[1:], after[1:])

    def test_reward_transaction_and_party_only_nickname(self):
        transaction = self.bank.split("HoennReward_Transaction:\n", 1)[1].split(
            "HoennReward_End:\n", 1)[0]
        self.assertEqual(transaction.count("GiveMonToPartyOrPC VAR_SPECIAL_x8000"), 1)
        self.assertIn("Compare VAR_HOENN_STARTER_RECEIVED, 0", transaction)
        self.assertIn("Compare VAR_SPECIAL_RESULT, GIVE_MON_PC", transaction)
        receipt = transaction.split("GiveMonToPartyOrPC VAR_SPECIAL_x8000", 1)[1]
        self.assertIn("CopyVar VAR_HOENN_STARTER_RECEIVED, VAR_SPECIAL_x8000", receipt)
        for yielding in ("NPCMsg", "WaitABPress", "NicknameInput", "MenuExec", "SaveGame"):
            self.assertNotIn(yielding, receipt)
        party = self.bank.split("HoennReward_Party:\n", 1)[1].split("HoennReward_PC:\n", 1)[0]
        self.assertIn("NicknameInput VAR_TEMP_x4000, VAR_SPECIAL_RESULT", party)
        self.assertEqual(len(re.findall(r"^NicknameInput ", self.bank, re.M)), 1)
        self.assertIn("GetStaticEncounterOutcome VAR_SPECIAL_RESULT", self.bank)
        self.assertIn("Compare VAR_SPECIAL_RESULT, BATTLE_OUTCOME_WIN", self.bank)
        self.assertIn("Compare VAR_SPECIAL_RESULT, BATTLE_OUTCOME_MON_CAUGHT", self.bank)

    def test_south_warps_and_terrain(self):
        event = json.loads(self.text("files/fielddata/eventdata/zone_event/493_ROUTE_101_TRAVEL.json"))
        self.assertEqual([obj["spriteId"] for obj in event["objects"]], [32, 26, 27])
        self.assertEqual([(w["x"], w["z"], w["header"], w["anchor"]) for w in event["warps"]],
                         [(10, 19, 541, 3), (11, 19, 541, 4)] * 2)
        land = Land.decode(narc_members((self.tree / LAND).read_bytes())[678])
        words = struct.unpack("<1024H", land.terrain)
        self.assertEqual((words[618], words[619]), (111, 111))
        self.assertEqual(words[16 * 32], 0x8000)  # preserved cliff
        guard = self.text("src/map_events.c")
        matched = guard.index("if (x == fieldSystem->mapEvents->warp_events[i].x")
        scoped = guard.index("&& (i == 0 || i == 1)", matched)
        rescue = guard.index("VAR_HOENN_RESCUE_STATE) != HOENN_RESCUE_COMPLETE", scoped)
        returned = guard.index("return i;", rescue)
        self.assertLess(matched, scoped)
        self.assertLess(rescue, returned)
        self.assertIn("fieldSystem->location->mapId == MAP_ROUTE_101_TRAVEL",
                      guard[matched:scoped])
        self.assertIn("(i == 2 || i == 3) && x == 10 + (i - 2) && y == 19", guard)
        self.assertEqual(self.report["compact"]["cells"],
                         {"route": 400, "town": 240, "border": 384})

    def test_labels_and_no_save_abi_change(self):
        headers = self.text("src/data/map_headers.h")
        self.assertEqual(headers.count(".mapsec = MAPSEC_LITTLEROOT_TOWN,"), 2)
        self.assertEqual(headers.count(".mapsec = MAPSEC_ROUTE_101,"), 1)
        for name in ("include/constants/vars.h", "include/constants/expansion.h"):
            self.assertEqual((self.tree / name).read_bytes(), (ROOT / name).read_bytes())

    def test_stager_full_delta_no_compiler_outputs_and_current_mtimes(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "overlay"
            started = time.time()
            report = stage(ROOT, self.tree, output)
            self.assertEqual(set(report["payload_sha256"]), set(approved_contract()))
            self.assertIn("expansion/baseline.json", report["payload_sha256"])
            self.assertEqual(
                {p.relative_to(output).as_posix() for p in output.rglob("*") if p.is_file()},
                set(report["payload_sha256"]) | {"episode-overlay.json"})
            for name, expected in report["payload_sha256"].items():
                self.assertEqual(sha((output / name).read_bytes()), expected)
                self.assertGreaterEqual((output / name).stat().st_mtime, started - 1)
            with self.assertRaises(ValueError):
                stage(ROOT, self.tree, output)

    def test_reconstructed_checkout_passes_real_expansion_checker(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            overlay, reconstructed = base / "overlay", base / "checkout"
            stage(ROOT, self.tree, overlay)
            reconstructed.mkdir()
            archive = subprocess.Popen(["git", "-C", str(ROOT), "archive", "HEAD"],
                                       stdout=subprocess.PIPE)
            try:
                subprocess.run(["tar", "-x", "-C", str(reconstructed)],
                               stdin=archive.stdout, check=True)
            finally:
                archive.stdout.close()
            self.assertEqual(archive.wait(), 0)
            for name in approved_contract():
                target = reconstructed / name
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(overlay / name, target)
            check = subprocess.run(
                [sys.executable, str(ROOT / "scripts/check_expansion_baseline.py"),
                 "--root", str(reconstructed)], text=True, capture_output=True)
            self.assertEqual(check.returncode, 0, check.stdout + check.stderr)
            self.assertEqual(json.loads(check.stdout)["observed"]["map_count"], 543)

    def test_forged_manifest_cannot_authorize_changed_native_code(self):
        with tempfile.TemporaryDirectory() as tmp:
            tree = Path(tmp) / "forged"
            shutil.copytree(self.tree, tree)
            report_path = tree / "opening-episode.json"
            original_report = report_path.read_text()
            # Test both an approved changed file and an unrelated vanilla file.
            for name in ("src/map_events.c", "src/encounter.c"):
                with self.subTest(name=name):
                    original = (tree / name).read_bytes()
                    data = original + b"\n/* unreviewed code */\n"
                    (tree / name).write_bytes(data)
                    report = json.loads(original_report)
                    report["native_input_sha256"][name] = sha(data)
                    report["episode_changes_sha256"][name] = sha(data)
                    report_path.write_text(json.dumps(report))
                    with self.assertRaisesRegex(ValueError, "Pinned input mismatch"):
                        stage(ROOT, tree, Path(tmp) / "must-not-publish")
                    self.assertFalse((Path(tmp) / "must-not-publish").exists())
                    (tree / name).write_bytes(original)

    def test_content_contract_survives_producer_commit_metadata_change(self):
        with tempfile.TemporaryDirectory() as tmp:
            tree = Path(tmp) / "prepared"
            shutil.copytree(self.tree, tree)
            report_path = tree / "opening-episode.json"
            report = json.loads(report_path.read_text())
            report["base_commit"] = "0" * 40
            report_path.write_text(json.dumps(report))
            result = stage(ROOT, tree, Path(tmp) / "overlay")
            self.assertEqual(set(result["payload_sha256"]), set(approved_contract()))

    def test_stage_publication_race_preserves_empty_destination(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "raced"
            def race(source, destination):
                destination.mkdir()
                return publish_directory(source, destination)
            with mock.patch("stage_emerald_episode.publish_directory", side_effect=race):
                with self.assertRaises(FileExistsError):
                    stage(ROOT, self.tree, output)
            self.assertTrue(output.is_dir())
            self.assertEqual(list(output.iterdir()), [])

    @unittest.skipUnless(all(os.environ.get(key) for key in (
        "EMERALD_DONOR", "EPISODE_RESOURCES", "EPISODE_LAB_ASSETS",
        "EPISODE_ACTOR", "EPISODE_PACKS")), "set composer input environment for prepare race")
    def test_prepare_publication_race_preserves_empty_destination(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "raced"
            def race(source, destination):
                destination.mkdir()
                return publish_directory(source, destination)
            with mock.patch("prepare_emerald_episode.publish_directory", side_effect=race):
                with self.assertRaises(FileExistsError):
                    prepare(ROOT, os.environ["EMERALD_DONOR"], os.environ["EPISODE_RESOURCES"],
                            os.environ["EPISODE_LAB_ASSETS"], os.environ["EPISODE_ACTOR"],
                            os.environ["EPISODE_PACKS"], output)
            self.assertTrue(output.is_dir())
            self.assertEqual(list(output.iterdir()), [])

    @unittest.skipUnless(os.environ.get("EMERALD_DONOR"), "set EMERALD_DONOR for movement parity")
    def test_movement_translations_from_pinned_donor(self):
        donor = (Path(os.environ["EMERALD_DONOR"]) / "data/maps/Route101/scripts.inc").read_text()
        directions = dict(up="North", down="South", left="West", right="East")
        prefixes = dict(walk_fast="WalkFast", walk_in_place_fast="WalkOnSpotFast",
                        walk_in_place_faster="WalkOnSpotFaster")
        for label in ("BirchRunAway1", "ZigzagoonChase1", "BirchRunInCircles",
                      "ZigzagoonChaseInCircles", "EnterScene", "ZigzagoonFaceBirch",
                      "BirchFaceZigzagoon"):
            text = re.search(r"^Route101_Movement_" + label + r":\n(.*?)^\s*step_end",
                             donor, re.M | re.S).group(1)
            expected = []
            for line in text.strip().splitlines():
                prefix, direction = line.strip().rsplit("_", 1)
                expected.append(prefixes[prefix] + directions[direction])
            actual = re.search(r"^Route101_Move_" + label + r":\n(.*?)^EndMovement",
                               self.bank, re.M | re.S).group(1).strip().splitlines()
            self.assertEqual(actual, expected, label)

    @unittest.skipUnless(os.environ.get("EPISODE_GOLDEN"), "set EPISODE_GOLDEN for parity")
    def test_all_native_inputs_against_corrected_golden(self):
        golden = Path(os.environ["EPISODE_GOLDEN"])
        actual, expected = native_inputs(ROOT, self.tree), native_inputs(ROOT, golden)
        # Historical R2 golden intentionally has the unsafe 94,636-byte model.
        # R3 changes only that land archive; a newer golden may have its model.
        # R4 additionally changes only the init header's actor-repair phase,
        # checked independently below. Texture, terrain and save ABI stay fixed.
        self.assertEqual(actual[LAND], FINAL_ARCHIVES[LAND])
        self.assertIn(expected[LAND], {
            actual[LAND],
            "9cfedfae00b15e1dfd5e1c7e4ca2d38e713e6b6b231b076e932802a110e0d3e5",
        })
        actual.pop(LAND)
        expected.pop(LAND)
        # The current tracked matrix dependency repair postdates private V7/V8.
        # Preserve it: do not reintroduce the stale-cache bug just to match a
        # historical Makefile.
        recipe = "files/fielddata/mapmatrix/map_matrix.mk"
        self.assertEqual((self.tree / recipe).read_bytes(), (ROOT / recipe).read_bytes())
        self.assertIn(expected[recipe], {
            actual[recipe],
            "7c32c5871afac29563a7ef0ac52baebdb70b1837b0a819e132251588ed415683",
        })
        actual.pop(recipe)
        expected.pop(recipe)
        header = "files/fielddata/script/scr_seq/scr_seq_0966_route101_opening_hdr.s"
        self.assertEqual(actual[header], approved_contract()[header]["after"])
        self.assertIn(expected[header], {
            actual[header],
            "98212b940e22f915ef61805740e909ab7e457096634fb6ede4d92f8fa6cdf344",
        })
        actual.pop(header)
        expected.pop(header)
        # Reviewed opt-in memo write postdates historical golden trees; no
        # other trainer-memo digest is accepted.
        memo = "src/trainer_memo.c"
        reviewed = "8a8374504736e61fd2e2a9446edb3da15fbe62f40deb19c9182a8e0a2a176b9b"
        baseline = "a10055077a4084e94bfd3d003c6db7405a15ce6a2f2a9bc893a4defdb17c9827"
        self.assertEqual(actual[memo], reviewed)
        self.assertEqual(actual[memo], approved_contract()[memo]["after"])
        self.assertIn(expected[memo], {baseline, reviewed})
        actual.pop(memo)
        expected.pop(memo)
        self.assertEqual(actual, expected)


if __name__ == "__main__":
    unittest.main()