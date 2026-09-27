import importlib.util
from pathlib import Path
import struct
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("hgss_land", ROOT / "scripts/hgss_land.py")
land = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = land
SPEC.loader.exec_module(land)


class LandTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.members = land.narc_members((ROOT / "files/a/0/6/5").read_bytes())

    def test_all_real_members_roundtrip(self):
        self.assertEqual(len(self.members), 676)
        for i, data in enumerate(self.members):
            with self.subTest(member=i):
                decoded = land.Land.decode(data)
                self.assertEqual(decoded.encode(), data)
                self.assertEqual(decoded.marker, 0x1234)
                # Validate all model block offsets/sizes, not magic scanning.
                model = decoded.model
                count = struct.unpack_from("<H", model, 14)[0]
                ends = []
                for j in range(count):
                    pos = struct.unpack_from("<I", model, 16 + j * 4)[0]
                    size = struct.unpack_from("<I", model, pos + 4)[0]
                    self.assertGreaterEqual(pos, 16 + count * 4)
                    self.assertLessEqual(pos + size, len(model))
                    ends.append(pos + size)
                self.assertEqual(max(ends), len(model))

    def test_extra_precedes_terrain(self):
        decoded = land.Land.decode(self.members[0])
        self.assertEqual(len(decoded.extra), 88)
        self.assertEqual(decoded.terrain, self.members[0][108:2156])
        self.assertEqual(decoded.model[:4], b"BMD0")
        self.assertEqual(self.members[0].index(b"BMD0"), 2972)
        # The fixed 0x14 terrain reader must not be used for extended members.
        self.assertNotEqual(decoded.terrain, self.members[0][20:2068])

    def test_authored_plane_matches_retail_binary(self):
        # This verifies actual writer output against an independently shipped
        # game resource, not merely its own decoder.
        collision = land.Land.decode(self.members[1]).collision
        self.assertEqual(land.flat_bdhc(-256, -256, 256, 256, 16), collision)
        lab_plane = land.flat_bdhc(0, 0, 13 * 16, 13 * 16)
        counts, sections = land.bdhc_sections(lab_plane)
        self.assertEqual(counts, (2, 1, 1, 1, 1, 1))
        self.assertEqual(struct.unpack("<4i", sections[0]),
                         (0, 0, 208 * 4096, 208 * 4096))
        self.assertEqual(struct.unpack("<i", sections[2]), (0,))
        # Do not infer walkability from this height plane.

    def test_malformed_inputs_rejected(self):
        for data in (b"", self.members[0][:-1], self.members[1] + b"\0"):
            with self.assertRaises(ValueError):
                land.Land.decode(data)
        for data in (b"BDHC", land.flat_bdhc(0, 0, 1, 1) + b"\0"):
            with self.assertRaises(ValueError):
                land.bdhc_sections(data)
        for bounds in ((0, 0, 0, 1), (0, 0, 1 << 20, 1)):
            with self.assertRaises(ValueError):
                land.flat_bdhc(*bounds)


if __name__ == "__main__":
    unittest.main()