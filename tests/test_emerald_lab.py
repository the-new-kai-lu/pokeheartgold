import importlib.util
import json
from pathlib import Path
import struct
import tempfile
import unittest
import zlib


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("lab", ROOT / "scripts/extract_emerald_lab.py")
lab = importlib.util.module_from_spec(spec)
spec.loader.exec_module(lab)


def indexed_fixture(mode):
    def chunk(tag, data):
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data))
    # Two packed rows, every PNG filter, with known decoded nibbles.
    rows = ([0x12, 0x34], [0x56, 0x78])
    encoded = bytearray()
    previous = [0, 0]
    for row in rows:
        encoded.append(mode)
        for i, value in enumerate(row):
            a, b, c = row[i - 1] if i else 0, previous[i], previous[i - 1] if i else 0
            p = a + b - c
            distances = [abs(p - a), abs(p - b), abs(p - c)]
            paeth = (a, b, c)[distances.index(min(distances))]
            encoded.append((value - (0, a, b, (a + b) // 2, paeth)[mode]) & 255)
        previous = row
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", 4, 2, 4, 3, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(encoded)) + chunk(b"IEND", b""))


class EmeraldLabTests(unittest.TestCase):
    def test_png_filters_and_corruption(self):
        for mode in range(5):
            with self.subTest(mode=mode):
                self.assertEqual(lab.indexed_png(indexed_fixture(mode)), (4, 2, list(range(1, 9))))
        corrupted = bytearray(indexed_fixture(0))
        corrupted[20] ^= 1
        with self.assertRaises(ValueError):
            lab.indexed_png(corrupted)

    def test_tile_flips_palette_and_primary_boundary(self):
        palettes = [[(i, p, 0) for i in range(16)] for p in range(13)]
        sheets = [(8, 8, [x % 8 + 1 for x in range(64)]),
                  (8, 8, [x // 8 + 1 for x in range(64)])]
        self.assertEqual(lab.tile_pixel(0, 0, 0, sheets, palettes), (1, 0, 0, 255))
        self.assertEqual(lab.tile_pixel(1024, 0, 0, sheets, palettes), (8, 0, 0, 255))
        self.assertEqual(lab.tile_pixel(512 | 2048 | (6 << 12), 0, 0, sheets, palettes), (8, 6, 0, 255))
        with self.assertRaises(ValueError):
            lab.tile_pixel(511, 0, 0, sheets, palettes)

    def test_real_donor_lab(self):
        donor = ROOT.parent / "pokeemerald"
        if not donor.exists():
            self.skipTest("Pinned pokeemerald checkout required for resource extraction")
        with tempfile.TemporaryDirectory() as temp:
            out = Path(temp) / "lab"
            manifest = lab.extract(donor, out)
            self.assertEqual(manifest["sources"]["data/layouts/LittlerootTown_ProfessorBirchsLab/map.bin"],
                             "dfb4b37b84e99ae5b82f822bdeb16db665ba7048acd2513522efd7d0fd776f7a")
            cells = json.loads((out / "cells.json").read_text())["cells"]
            self.assertEqual(len(cells), 169)
            source = (donor / "data/layouts/LittlerootTown_ProfessorBirchsLab/map.bin").read_bytes()
            reconstructed = b"".join(struct.pack("<H", c["metatile"] | c["collision"] << 10 | c["elevation"] << 12) for c in cells)
            self.assertEqual(reconstructed, source)
            self.assertEqual(manifest["outputs"]["preview.png"],
                             "5a98c7d14cc1c506aa04242819b48f6250f1969e794ce7cdfb90951cfb7a6f60")
            with self.assertRaises(FileExistsError):
                lab.extract(donor, out)