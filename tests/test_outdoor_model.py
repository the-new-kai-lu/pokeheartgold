"""Lossless outdoor prototypes with conservative, explicitly incomplete terrain."""
import json
import os
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from extract_emerald_lab import extract
from export_emerald_outdoor_model import export, terrain
from export_lab_model import rgba_preview, texture
from hgss_land import Land
from test_lab_model import blocks, entries


class OutdoorModelTests(unittest.TestCase):
    def test_real_exteriors(self):
        donor = ROOT.parent / "pokeemerald"
        if not donor.exists():
            self.skipTest("Pinned Emerald donor checkout required")
        for name in ("LittlerootTown", "Route101"):
            with self.subTest(name=name), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                pack, out = root / "pack", root / "out"
                extract(donor, pack, name)
                report = export(pack, out)
                self.assertEqual(report["visible_colors"], 46 if name == "LittlerootTown" else 25)
                land = Land.decode((out / "outdoor.land").read_bytes())
                # Independent TEX0 offsets and BGR555 pixel reconstruction.
                tex = blocks((out / "outdoor.nsbtx").read_bytes())[b"TEX0"]
                image_offset = struct.unpack_from("<I", tex, 20)[0]
                palette_offset = struct.unpack_from("<I", tex, 56)[0]
                colors = struct.unpack_from("<256H", tex, palette_offset)
                preview = rgba_preview((pack / "preview.png").read_bytes(), 320, 320)
                for y in range(320):
                    for x in range(320):
                        i = (y * 320 + x) * 4
                        expected = sum(round(preview[i + c] * 31 / 255) << (5 * c) for c in range(3))
                        self.assertEqual(colors[tex[image_offset + y * 512 + x]], expected)
                mdl = blocks(land.model)[b"MDL0"]
                base = struct.unpack("<I", entries(mdl, 8)["emerald_outdoor"])[0]
                matoff = base + struct.unpack_from("<I", mdl, base + 8)[0]
                material = matoff + struct.unpack("<I", entries(mdl, matoff + 4)["labmat"])[0]
                self.assertFalse(struct.unpack_from("<H", mdl, material + 30)[0] & 0x20)
                cells = json.loads((pack / "cells.json").read_text())
                terrain_bytes, unsupported = terrain(cells)
                # Land bytes include the exact generated terrain, at native header+20.
                self.assertEqual((out / "outdoor.land").read_bytes()[20:2068], terrain_bytes)
                self.assertEqual(len(unsupported), 5 if name == "LittlerootTown" else 104)
                for z in range(32):
                    for x in range(32):
                        value = struct.unpack_from("<H", terrain_bytes, (z * 32 + x) * 2)[0]
                        expected = 0x8000
                        if 0 < x < 19 and 0 < z < 19:
                            cell = cells["cells"][z * 20 + x]
                            if (cell["collision"], cell["elevation"], cell["behavior"]) == (0, 3, 0):
                                expected = 0
                        self.assertEqual(value, expected)
                        self.assertEqual(((-256 + x * 16 + 8) + 256) // 16, x)
                if os.environ.get("APICULA"):
                    external = root / "external.nsbmd"
                    external.write_bytes(land.model)
                    for variant, inputs in (("embedded", [out / "outdoor.nsbmd"]),
                                            ("external", [external, out / "outdoor.nsbtx"])):
                        decoded = root / variant
                        subprocess.run([os.environ["APICULA"], "convert", *map(str, inputs),
                                        "-o", str(decoded), "-f", "gltf"], check=True, capture_output=True)
                        scene = json.loads((decoded / "emerald_outdoor.gltf").read_text())
                        blob = (decoded / scene["buffers"][0]["uri"]).read_bytes()
                        primitive = scene["meshes"][0]["primitives"][0]
                        for semantic, size, expected in (
                            ("POSITION", 3, [(-256, 0, -256), (-256, 0, 64), (64, 0, 64), (64, 0, -256)]),
                            ("TEXCOORD_0", 2, [(0, 0), (0, .625), (.625, .625), (.625, 0)])):
                            accessor = scene["accessors"][primitive["attributes"][semantic]]
                            view = scene["bufferViews"][accessor["bufferView"]]
                            offset = view.get("byteOffset", 0) + accessor.get("byteOffset", 0)
                            values = [struct.unpack_from("<" + "f" * size, blob,
                                      offset + i * view.get("byteStride", size * 4))
                                      for i in range(accessor["count"])]
                            self.assertEqual(values, expected)
                        self.assertTrue((decoded / scene["images"][0]["uri"]).exists())
                with self.assertRaises(FileExistsError):
                    export(pack, out)
                (pack / "preview.png").write_bytes(b"changed")
                with self.assertRaises(ValueError):
                    export(pack, root / "tampered")

    def test_fail_closed_inputs(self):
        with self.assertRaises(ValueError):
            terrain(dict(width=20, height=20, cells=[]))
        pixels = b"".join(bytes(((v & 31) * 255 // 31, (v >> 5) * 255 // 31, 0, 255))
                          for v in range(257))
        with self.assertRaises(ValueError):
            texture(pixels, 257, 1, 512)