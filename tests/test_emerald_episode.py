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
from hgss_land import Land, narc_members
from prepare_emerald_episode import (
    FINAL_ARCHIVES, LAND, TEXTURES, MODELS, guard_path, native_edits, sha,
    publish_directory, approved_contract, prepare,
)
from stage_emerald_episode import stage


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

    def test_compact_geometry_budget(self):
        commands, audit = episode_assets.commands_for([0] * 1024)
        self.assertEqual(audit["begin_quads"], 1024)
        self.assertEqual(audit["vertices"], 4096)
        self.assertEqual(audit["actual_stream_bytes"], len(commands))

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
        self.assertIn("InitScriptEntry_OnLoad 5", header)
        self.assertIn("InitScriptGoToIfEqual VAR_TEMP_x4000, 3, 7", header)
        self.assertIn("EnsureRoute101Actors VAR_TEMP_x4003", self.bank)
        ensure = self.text("src/scrcmd_c.c").split("BOOL ScrCmd_EnsureRoute101Actors", 1)[1]
        self.assertIn("MapObject_CreateFromObjectEventWithId", ensure)
        self.assertIn("activeCount + missing >= 64", ensure)
        self.assertIn("MapObject_GetMapID(object) != MAP_ROUTE_101_TRAVEL", ensure)

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
        # The current tracked matrix dependency repair postdates private V7/V8.
        # Preserve it: do not reintroduce the stale-cache bug just to match a
        # historical Makefile. This is the ONLY allowed native-recipe difference.
        recipe = "files/fielddata/mapmatrix/map_matrix.mk"
        self.assertEqual((self.tree / recipe).read_bytes(), (ROOT / recipe).read_bytes())
        self.assertIn(expected[recipe], {
            actual[recipe],
            "7c32c5871afac29563a7ef0ac52baebdb70b1837b0a819e132251588ed415683",
        })
        actual.pop(recipe)
        expected.pop(recipe)
        self.assertEqual(actual, expected)


if __name__ == "__main__":
    unittest.main()