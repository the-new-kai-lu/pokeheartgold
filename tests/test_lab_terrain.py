"""Independent tile/world coordinate checks for the authored lab."""
import json
from pathlib import Path
import struct
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from export_lab_model import terrain


class LabTerrainTests(unittest.TestCase):
    def test_all_cell_centers_and_outside(self):
        cells = [{"x": x, "y": z, "collision": int((x + z) % 3 == 0),
                  "behavior": 101 if (x, z) == (6, 12) else 0}
                 for z in range(13) for x in range(13)]
        raw, exits = terrain({"width": 13, "height": 13, "cells": cells})
        grid = struct.unpack("<1024H", raw)
        for z in range(32):
            for x in range(32):
                if 9 <= x < 22 and 9 <= z < 22:
                    source = cells[(z - 9) * 13 + x - 9]
                    expected = 0x8000 if source["collision"] or source["behavior"] else 0
                    # Compute from world center, not the writer's direct indices.
                    wx, wz = -112 + (source["x"] + .5)*16, -112 + (source["y"] + .5)*16
                    self.assertEqual((int((wx + 256)//16), int((wz + 256)//16)), (x, z))
                else:
                    expected = 0x8000
                self.assertEqual(grid[z*32 + x], expected)
        self.assertEqual(exits[0]["terrain"], [15, 21])
        cells[-1] = cells[0]
        with self.assertRaises(ValueError):
            terrain({"width": 13, "height": 13, "cells": cells})