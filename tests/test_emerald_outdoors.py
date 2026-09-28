"""Authentic first-episode exterior extraction; no HGSS walkability inference."""
import hashlib
import importlib.util
import json
from pathlib import Path
import struct
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("extractor", ROOT / "scripts/extract_emerald_lab.py")
extractor = importlib.util.module_from_spec(spec)
spec.loader.exec_module(extractor)


class OutdoorExtractionTests(unittest.TestCase):
    def test_real_maps_semantics_connections_and_chunk_coordinates(self):
        donor = ROOT.parent / "pokeemerald"
        if not donor.exists():
            self.skipTest("Pinned donor checkout required")
        for name in ("LittlerootTown", "Route101"):
            with self.subTest(name=name), tempfile.TemporaryDirectory() as temp:
                out = Path(temp) / name
                manifest = extractor.extract(donor, out, name)
                self.assertEqual(manifest["layout"], name)
                cells = json.loads((out / "cells.json").read_text())
                raw = (donor / f"data/layouts/{name}/map.bin").read_bytes()
                self.assertEqual((cells["width"], cells["height"]), (20, 20))
                self.assertEqual(len(cells["cells"]), 400)
                for i, cell in enumerate(cells["cells"]):
                    block = struct.unpack_from("<H", raw, i * 2)[0]
                    self.assertEqual((cell["x"], cell["y"]), (i % 20, i // 20))
                    self.assertEqual(cell["raw"], block)
                    self.assertEqual(cell["collision"], block >> 10 & 3)
                    self.assertEqual(cell["elevation"], block >> 12)
                events = json.loads((donor / f"data/maps/{name}/map.json").read_text())
                self.assertEqual(json.loads((out / "donor-events.json").read_text()), events)
                plan = json.loads((out / "chunk-plan.json").read_text())
                self.assertEqual(plan["connections"], events["connections"])
                self.assertEqual(plan["warps"], events["warp_events"])
                self.assertEqual(plan["matrix_size"], [1, 1])
                chunk = plan["chunks"][0]
                self.assertEqual(chunk["valid_size"], [20, 20])
                self.assertEqual(chunk["world_origin"], [-256, -256])
                # Each donor tile center maps exactly to its native grid cell.
                for cell in cells["cells"]:
                    for axis in ("x", "y"):
                        center = -256 + cell[axis] * 16 + 8
                        self.assertEqual((center + 256) // 16, cell[axis])
                self.assertEqual(len(plan["occluded_unavailable_lower_tiles"]),
                                 8 if name == "LittlerootTown" else 0)
                for filename, digest in manifest["outputs"].items():
                    self.assertEqual(hashlib.sha256((out / filename).read_bytes()).hexdigest(), digest)
                self.assertEqual(struct.unpack_from(">II", (out / "preview.png").read_bytes(), 16),
                                 (320, 320))
                with self.assertRaises(FileExistsError):
                    extractor.extract(donor, out, name)

    def test_unknown_maps_rejected(self):
        with self.assertRaises(ValueError):
            extractor.extract(Path("/nonexistent-donor"), Path("/unused"), "NotAMap")