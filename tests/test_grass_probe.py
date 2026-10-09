"""Private native grass authoring whitelist; no runtime safety assertion."""
import json
from pathlib import Path
import re
import struct
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from export_emerald_outdoor_model import ENCDATA_NA, TILE_BEHAVIOR_TALL_GRASS, export, terrain
from extract_emerald_lab import extract

PROBE = dict(terrain_profile="native-grass-probe", probe_encounter_bank=255, probe_normal_field=True)


class GrassProbeTests(unittest.TestCase):
    def test_native_source_constants(self):
        text = (ROOT / "include/constants/metatile_behavior.h").read_text()
        names = re.findall(r"^\s*(TILE_BEHAVIOR_\w+)\s*,", text, re.M)
        self.assertEqual(names.index("TILE_BEHAVIOR_TALL_GRASS"), TILE_BEHAVIOR_TALL_GRASS)
        self.assertEqual(names.index("TILE_BEHAVIOR_LADDER_DOWN"), 62)
        self.assertRegex((ROOT / "include/encounter_tables_narc.h").read_text(), r"#define ENCDATA_NA\s+255\b")
        self.assertEqual(ENCDATA_NA, 255)

    def test_explicit_prerequisites(self):
        for kwargs in ({}, dict(probe_encounter_bank=255), dict(probe_normal_field=True),
                       dict(probe_encounter_bank=65535, probe_normal_field=True),
                       dict(probe_encounter_bank=0, probe_normal_field=True)):
            with self.assertRaises(ValueError):
                export(Path("/unused"), Path("/unused"), terrain_profile="native-grass-probe", **kwargs)
        with self.assertRaises(ValueError):
            export(Path("/unused"), Path("/unused"), probe_encounter_bank=255)
        with self.assertRaises(ValueError):
            export(Path("/unused"), Path("/unused"), terrain_profile="unknown")

    def test_exact_tuple_and_perimeter(self):
        cells = dict(width=20, height=20, cells=[
            dict(x=x, y=y, collision=0, elevation=3, behavior=0)
            for y in range(20) for x in range(20)])
        variants = [(2, 0, 3), (2, 1, 3), (2, 0, 0), (2, 0, 15),
                    (59, 0, 3), (62, 0, 3), (105, 0, 3), (0, 0, 15)]
        for x, (behavior, collision, elevation) in enumerate(variants, 1):
            cells["cells"][20 + x].update(behavior=behavior, collision=collision, elevation=elevation)
        cells["cells"][0].update(behavior=2)
        default, _ = terrain(cells)
        probe, _ = terrain(cells, "native-grass-probe", 255, True)
        self.assertEqual(probe[66:68], b"\x02\x00")
        for x in range(2, 9):
            self.assertEqual(probe[(32 + x) * 2:(32 + x) * 2 + 2], b"\x00\x80")
        self.assertEqual(probe[:2], b"\x00\x80")
        self.assertEqual(default[66:68], b"\x00\x80")

    def test_real_maps_probe_and_unchanged_defaults(self):
        donor = ROOT.parent / "pokeemerald"
        if not donor.exists():
            self.skipTest("Pinned Emerald donor required")
        for name in ("LittlerootTown", "Route101"):
            with self.subTest(name=name), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                pack = root / "pack"
                extract(donor, pack, name)
                conservative = export(pack, root / "default")
                explicit = export(pack, root / "explicit", terrain_profile="conservative")
                probe = export(pack, root / "probe", **PROBE)
                for filename in ("outdoor.nsbmd", "outdoor.nsbtx", "outdoor.land", "manifest.json"):
                    self.assertEqual((root / "default" / filename).read_bytes(),
                                     (root / "explicit" / filename).read_bytes())
                for filename in ("outdoor.nsbmd", "outdoor.nsbtx"):
                    self.assertEqual(conservative["outputs"][filename], probe["outputs"][filename])
                self.assertFalse(probe["RuntimeVerified"])
                self.assertTrue(probe["requiresGrassEffectsRuntimeValidation"])
                self.assertEqual(probe["probe_encounter_bank"], 255)
                self.assertIn("NOT production-ready", probe["limitations"][-1])
                self.assertEqual(probe["texture_bytes"], 102400)
                cells = json.loads((pack / "cells.json").read_text())["cells"]
                data = (root / "probe/outdoor.land").read_bytes()[20:2068]
                values = struct.unpack("<1024H", data)
                grass, ledges = [], []
                for cell in cells:
                    x, y = cell["x"], cell["y"]
                    value = values[y * 32 + x]
                    if (cell["behavior"], cell["collision"], cell["elevation"]) == (2, 0, 3):
                        grass.append((x, y))
                        self.assertEqual(value, 2 if 0 < x < 19 and 0 < y < 19 else 0x8000)
                    if cell["behavior"] in (59, 62):
                        ledges.append((x, y))
                        self.assertEqual(value, 0x8000)
                if name == "Route101":
                    self.assertEqual(len(grass), 91)
                    self.assertEqual(probe["donor_grass_candidates"], 91)
                    self.assertEqual(probe["native_grass_cells"], 87)
                    self.assertEqual(probe["perimeter_grass_cells_blocked"], 4)
                    self.assertEqual(len(ledges), 13)
                    self.assertEqual(len(probe["unsupported_cells"]), 13)
                    # At least one normal ground component reaches native grass;
                    # ledges remain barriers, not guessed jump semantics.
                    start = next((x, y) for y in range(32) for x in range(32) if values[y * 32 + x] == 0)
                    seen, pending = {start}, [start]
                    while pending:
                        x, y = pending.pop()
                        for nx, ny in ((x-1, y), (x+1, y), (x, y-1), (x, y+1)):
                            if 0 <= nx < 32 and 0 <= ny < 32 and (nx, ny) not in seen and values[ny*32+nx] in (0, 2):
                                seen.add((nx, ny))
                                pending.append((nx, ny))
                    self.assertTrue(seen.intersection(grass))
                    self.assertFalse(seen.intersection(ledges))
                else:
                    self.assertEqual(len(probe["unsupported_cells"]), 5)
                    self.assertEqual(conservative["outputs"]["outdoor.land"], probe["outputs"]["outdoor.land"])