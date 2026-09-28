"""Three-map resource-only staging; no story or travel installation."""

import hashlib
import json
import os
from pathlib import Path
import shutil
import struct
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from extract_emerald_lab import DONOR, extract
from export_lab_model import export as export_lab
from export_emerald_outdoor_model import export as export_outdoor
from hgss_land import Land, narc_members
from stage_emerald_opening import (ARCHIVES, COUNTS, MAPS, MATRIX_DIR,
                                   checked_nitro, stage)
from stage_lab_archives import pack_narc


def sha256(data):
    return hashlib.sha256(data).hexdigest()


class EmeraldOpeningStageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        donor = Path(os.environ.get("EMERALD_DONOR", ROOT.parent / "pokeemerald"))
        if not donor.exists():
            raise unittest.SkipTest("Pinned Emerald donor required")
        cls.temp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.temp.cleanup)
        cls.base = Path(cls.temp.name)
        cls.assets = {}
        for kind, layout in (("lab", "LittlerootTown_ProfessorBirchsLab"),
                             ("town", "LittlerootTown"), ("route", "Route101")):
            pack, output = cls.base / (kind + "-pack"), cls.base / (kind + "-assets")
            extract(donor, pack, layout)
            (export_lab if kind == "lab" else export_outdoor)(pack, output)
            cls.assets[kind] = output

    def call(self, output, **overrides):
        args = dict(root=ROOT, lab_assets=self.assets["lab"],
                    town_assets=self.assets["town"], route_assets=self.assets["route"],
                    output=output)
        args.update(overrides)
        return stage(**args)

    def copy_assets(self, kind, place):
        shutil.copytree(self.assets[kind], place)
        return place

    def test_all_three_binding_ids_and_original_members(self):
        output = self.base / "three-map-stage"
        result = self.call(output)
        self.assertEqual(result["status"], "resource-overlay-only-three-maps-unreachable")
        self.assertEqual(result["expected_donor_revision"], DONOR)
        self.assertTrue(result["original_archive_members_preserved"])
        self.assertEqual(result["source_matrix_count"], 288)
        self.assertEqual(result["matrix_u8_cached_aliases"], {"288": 32, "289": 33, "290": 34})
        self.assertEqual(result["bindings"]["lab"]["script"], 965)
        self.assertEqual(result["bindings"]["lab"]["messages"], 829)
        self.assertIsNone(result["bindings"]["route"]["script"])
        self.assertIsNone(result["bindings"]["town"]["messages"])
        self.assertEqual(result["bindings"]["lab"]["terrain_origin"], [9, 9])
        self.assertEqual(result["bindings"]["town"]["terrain_origin"], [0, 0])
        self.assertEqual(result["bindings"]["route"]["terrain_origin"], [0, 0])
        self.assertEqual(result["bindings"]["route"]["planned_map"], 542)
        self.assertEqual(result["bindings"]["route"]["planned_events"], 493)
        for kind, relpath in ARCHIVES.items():
            original = (ROOT / relpath).read_bytes()
            self.assertEqual(result["source_sha256"][relpath], sha256(original))
            before = narc_members(original)
            self.assertEqual(len(before), COUNTS[kind])
            self.assertEqual(result["archive_member_counts"][kind]["before"], COUNTS[kind])
            if kind == "props":
                self.assertEqual(result["archive_member_counts"][kind]["after"], COUNTS[kind])
                self.assertFalse((output / relpath).exists())
                continue
            new = (output / relpath).read_bytes()
            self.assertEqual(sha256(new), result["output_sha256"][relpath])
            members = narc_members(new)
            self.assertEqual(members[:len(before)], before)
            self.assertEqual(len(members), COUNTS[kind] + 3)
            for n, (mapkind, _, map_id, area_id, land_id, matrix_id, event_id, name, prefix) in enumerate(MAPS):
                src = self.assets[mapkind]
                self.assertEqual(result["bindings"][mapkind]["planned_map"], map_id)
                self.assertEqual(result["bindings"][mapkind]["planned_events"], event_id)
                self.assertEqual(result["bindings"][mapkind]["area"], area_id)
                self.assertEqual(result["bindings"][mapkind]["land"], land_id)
                self.assertEqual(result["bindings"][mapkind]["matrix"], matrix_id)
                if kind == "areas":
                    self.assertEqual(struct.unpack("<4H", members[COUNTS[kind] + n]),
                                     (1, area_id, 0xffff, 0))
                elif kind == "textures":
                    self.assertEqual(members[COUNTS[kind] + n],
                                     (src / f"{prefix}.nsbtx").read_bytes())
                else:
                    self.assertEqual(members[COUNTS[kind] + n],
                                     (src / f"{prefix}.land").read_bytes())
                    decoded = Land.decode(members[COUNTS[kind] + n])
                    self.assertEqual(len(decoded.terrain), 2048)
                matrix_path = f"{MATRIX_DIR}/{name}"
                matrix = (output / matrix_path).read_bytes()
                self.assertEqual(matrix, struct.pack("<5BH", 1, 1, 0, 0, 0, land_id))
                self.assertEqual(sha256(matrix), result["output_sha256"][matrix_path])
        self.assertEqual(json.loads((output / "manifest.json").read_text()), result)
        self.assertEqual(len(result["output_sha256"]), 6)
        # Reading all the sources again also catches a mistaken in-place edit.
        for kind, relpath in ARCHIVES.items():
            self.assertEqual(result["source_sha256"][relpath], sha256((ROOT / relpath).read_bytes()))
        with self.assertRaisesRegex(ValueError, "existing output"):
            self.call(output)

    def test_reject_swapped_maps_and_wrong_provenance_without_output(self):
        with self.assertRaisesRegex(ValueError, "expected layout"):
            self.call(self.base / "swapped", town_assets=self.assets["route"],
                      route_assets=self.assets["town"])
        self.assertFalse((self.base / "swapped").exists())
        lab = self.copy_assets("lab", self.base / "false-lab-preview")
        lab_manifest = lab / "manifest.json"
        data = json.loads(lab_manifest.read_text())
        data["preview_sha256"] = "f" * 64
        lab_manifest.write_text(json.dumps(data))
        with self.assertRaisesRegex(ValueError, "preview_sha256"):
            self.call(self.base / "wrong-lab-preview", lab_assets=lab)
        mutated = self.copy_assets("route", self.base / "false-provenance")
        manifest_path = mutated / "manifest.json"
        manifest = json.loads(manifest_path.read_text())
        manifest["source_outputs"]["cells.json"] = "f" * 64
        manifest_path.write_text(json.dumps(manifest))
        with self.assertRaisesRegex(ValueError, "donor extraction hashes"):
            self.call(self.base / "wrong-source", route_assets=mutated)
        self.assertFalse((self.base / "wrong-source").exists())
        manifest["source_outputs"]["cells.json"] = json.loads(
            (self.assets["route"] / "manifest.json").read_text())["source_outputs"]["cells.json"]
        manifest["expected_donor_revision"] = "0" * 40
        manifest_path.write_text(json.dumps(manifest))
        with self.assertRaisesRegex(ValueError, "expected_donor_revision"):
            self.call(self.base / "wrong-commit", route_assets=mutated)

    def test_reject_grass_probe_and_corrupt_assets_without_partial_overlay(self):
        route = self.copy_assets("route", self.base / "probe")
        manifest_path = route / "manifest.json"
        manifest = json.loads(manifest_path.read_text())
        manifest["status"] = "private-uninstalled-native-grass-effect-probe"
        manifest["terrain_profile"] = "native-grass-probe"
        manifest_path.write_text(json.dumps(manifest))
        with self.assertRaisesRegex(ValueError, "status"):
            self.call(self.base / "disallowed-probe", route_assets=route)
        self.assertFalse((self.base / "disallowed-probe").exists())
        route = self.copy_assets("town", self.base / "corrupt")
        with (route / "outdoor.nsbtx").open("ab") as stream:
            stream.write(b"\0")
        with self.assertRaisesRegex(ValueError, "differs from exporter manifest"):
            self.call(self.base / "bad-digest", town_assets=route)
        self.assertFalse((self.base / "bad-digest").exists())

    def test_reject_rehashed_invalid_terrain_and_lab_exit(self):
        town = self.copy_assets("town", self.base / "bad-terrain")
        land_file = town / "outdoor.land"
        land_bytes = bytearray(land_file.read_bytes())
        # Authoring a native walkable perimeter with a newly self-consistent
        # manifest must still fail the staged-map safety contract.
        struct.pack_into("<H", land_bytes, 20, 0)
        land_file.write_bytes(land_bytes)
        manifest_file = town / "manifest.json"
        manifest = json.loads(manifest_file.read_text())
        manifest["outputs"]["outdoor.land"] = sha256(land_bytes)
        manifest_file.write_text(json.dumps(manifest))
        with self.assertRaisesRegex(ValueError, "perimeter"):
            self.call(self.base / "unapproved-transition", town_assets=town)
        self.assertFalse((self.base / "unapproved-transition").exists())
        lab = self.copy_assets("lab", self.base / "open-exit")
        lab_file = lab / "lab.land"
        lab_bytes = bytearray(lab_file.read_bytes())
        struct.pack_into("<H", lab_bytes, 20 + (21 * 32 + 15) * 2, 0)
        lab_file.write_bytes(lab_bytes)
        manifest_file = lab / "manifest.json"
        manifest = json.loads(manifest_file.read_text())
        manifest["outputs"]["lab.land"] = sha256(lab_bytes)
        manifest_file.write_text(json.dumps(manifest))
        with self.assertRaisesRegex(ValueError, "exits must remain blocked"):
            self.call(self.base / "lab-open", lab_assets=lab)

    def test_source_archive_count_and_nitro_containers_are_checked(self):
        self.assertEqual(checked_nitro(
            (self.assets["lab"] / "lab.nsbtx").read_bytes(), b"BTX0", (b"TEX0",))[0][:4],
            b"TEX0")
        with self.assertRaisesRegex(ValueError, "container header"):
            data = (self.assets["lab"] / "lab.nsbtx").read_bytes()
            checked_nitro(data[:-1], b"BTX0", (b"TEX0",))
        fake_root = self.base / "wrong-archives"
        for kind, path in ARCHIVES.items():
            target = fake_root / path
            target.parent.mkdir(parents=True, exist_ok=True)
            if kind == "areas":
                members = narc_members((ROOT / path).read_bytes())
                target.write_bytes(pack_narc(members[:-1]))
            else:
                shutil.copyfile(ROOT / path, target)
        (fake_root / MATRIX_DIR).parent.mkdir(parents=True, exist_ok=True)
        (fake_root / MATRIX_DIR).symlink_to(ROOT / MATRIX_DIR, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, "Source archive counts changed"):
            self.call(self.base / "wrong-archive-output", root=fake_root)
        self.assertFalse((self.base / "wrong-archive-output").exists())
        altered = narc_members((ROOT / ARCHIVES["areas"]).read_bytes())
        altered[2] += b"x"
        (fake_root / ARCHIVES["areas"]).write_bytes(pack_narc(altered))
        with self.assertRaisesRegex(ValueError, "differ from pinned stock"):
            self.call(self.base / "not-stock-output", root=fake_root)
        self.assertFalse((self.base / "not-stock-output").exists())


if __name__ == "__main__":
    unittest.main()