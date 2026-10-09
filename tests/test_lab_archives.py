import os
from pathlib import Path
import struct
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from extract_emerald_lab import extract
from export_lab_model import export
from hgss_land import narc_members
from stage_lab_archives import pack_narc, stage


class LabArchiveTests(unittest.TestCase):
    def test_padding_and_member_identity(self):
        values = [b"", b"x", b"abc", bytes(range(256))]
        self.assertEqual(narc_members(pack_narc(values)), values)

    def test_actual_append_bindings(self):
        donor = Path(os.environ.get("EMERALD_DONOR", ROOT.parent / "pokeemerald"))
        if not donor.exists():
            self.skipTest("Pinned Emerald donor unavailable")
        with tempfile.TemporaryDirectory() as directory:
            temp = Path(directory)
            extract(donor, temp / "pack")
            export(temp / "pack", temp / "assets")
            result = stage(ROOT, temp / "assets", temp / "overlay")
            for path, last in (("files/a/0/4/2", 106), ("files/a/0/4/4", 106),
                               ("files/a/0/6/5", 676)):
                original = narc_members((ROOT / path).read_bytes())
                appended = narc_members((temp / "overlay" / path).read_bytes())
                self.assertEqual(appended[:-1], original)
                self.assertEqual(len(appended), last + 1)
            area = narc_members((temp / "overlay/files/a/0/4/2").read_bytes())[-1]
            self.assertEqual(struct.unpack("<4H", area), (1, 106, 65535, 0))
            matrix = (temp / "overlay/files/fielddata/mapmatrix/map_matrix/"
                      "map_matrix_0288_HOENN_LAB.bin").read_bytes()
            self.assertEqual(struct.unpack("<5BH", matrix), (1, 1, 0, 0, 0, 676))
            self.assertEqual(result["bindings"]["scripts"], 965)
            self.assertEqual(result["bindings"]["messages"], 829)
            with self.assertRaises(ValueError):
                stage(ROOT, temp / "assets", temp / "overlay")
            (temp / "assets/lab.land").write_bytes(b"corrupt")
            with self.assertRaises(ValueError):
                stage(ROOT, temp / "assets", temp / "bad")
            self.assertFalse((temp / "bad").exists())