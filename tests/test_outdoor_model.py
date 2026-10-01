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
from outdoor_nitro import MAP_TEXTURE_BUDGET, RECTANGLES, resource_dictionary, textures


def multi_entries(data, start):
    revision, count, size, tree_offset, entry_offset = struct.unpack_from("<BBHHH", data, start)
    assert revision == 0 and start + size <= len(data) and tree_offset == 8
    unit, name_offset = struct.unpack_from("<HH", data, start + entry_offset)
    nodes = [struct.unpack_from("<4B", data, start + tree_offset + i * 4) for i in range(count + 1)]
    result = {}
    for i in range(count):
        raw = data[start + entry_offset + name_offset + i * 16: start + entry_offset + name_offset + (i + 1) * 16]
        key = int.from_bytes(raw, "little")
        previous, current = 0, nodes[0][1]
        hops = 0
        while nodes[previous][0] > nodes[current][0]:
            previous, current = current, nodes[current][1 + ((key >> nodes[current][0]) & 1)]
            hops += 1
            assert hops <= count
        assert nodes[current][3] == i
        offset = start + entry_offset + 4 + i * unit
        result[raw.rstrip(b"\0").decode()] = data[offset:offset + unit]
    return result


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
                encoded_size = struct.unpack_from("<H", tex, 12)[0] * 8
                self.assertEqual(encoded_size, MAP_TEXTURE_BUDGET)
                self.assertEqual(palette_offset - image_offset, encoded_size)
                self.assertEqual(report["texture_bytes"], encoded_size)
                self.assertFalse(report["RuntimeVerified"])
                self.assertEqual(262144 - encoded_size, 159744)
                colors = struct.unpack_from("<256H", tex, palette_offset)
                preview = rgba_preview((pack / "preview.png").read_bytes(), 320, 320)
                tex_entries = multi_entries(tex, struct.unpack_from("<H", tex, 14)[0])
                self.assertEqual(len(tex_entries), 4)
                covered = set()
                total = 0
                for n, (left, top, width, height) in enumerate(RECTANGLES):
                    param, _ = struct.unpack("<II", tex_entries[f"tile{n}"])
                    self.assertEqual(8 << ((param >> 20) & 7), width)
                    self.assertEqual(8 << ((param >> 23) & 7), height)
                    self.assertEqual((param & 0xffff) * 8, total)
                    for y in range(height):
                        for x in range(width):
                            coord = (left + x, top + y)
                            self.assertNotIn(coord, covered)
                            covered.add(coord)
                            i = ((top + y) * 320 + left + x) * 4
                            expected = sum(round(preview[i + c] * 31 / 255) << (5 * c) for c in range(3))
                            self.assertEqual(colors[tex[image_offset + total + y * width + x]], expected)
                    total += width * height
                self.assertEqual(len(covered), 320 * 320)
                self.assertEqual(total, encoded_size)
                mdl = blocks(land.model)[b"MDL0"]
                base = struct.unpack("<I", entries(mdl, 8)["emerald_outdoor"])[0]
                matoff = base + struct.unpack_from("<I", mdl, base + 8)[0]
                materials = multi_entries(mdl, matoff + 4)
                self.assertEqual(len(materials), 4)
                for value in materials.values():
                    material = matoff + struct.unpack("<I", value)[0]
                    self.assertFalse(struct.unpack_from("<H", mdl, material + 30)[0] & 0x20)
                    self.assertEqual((struct.unpack_from("<I", mdl, material + 12)[0] >> 16) & 31, 31)
                texbinding, palbinding = struct.unpack_from("<HH", mdl, matoff)
                bindings = multi_entries(mdl, matoff + texbinding)
                for n in range(4):
                    offset, count, _ = struct.unpack("<HBB", bindings[f"tile{n}"])
                    self.assertEqual(count, 1)
                    self.assertEqual(mdl[matoff + offset], n)
                offset, count, _ = struct.unpack("<HBB", entries(mdl, matoff + palbinding)["outdoorpal"])
                self.assertEqual(mdl[matoff + offset:matoff + offset + count], bytes(range(4)))
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
                        primitives = [p for mesh in scene["meshes"] for p in mesh["primitives"]]
                        self.assertEqual(len(primitives), 4)
                        self.assertEqual(len(scene["materials"]), 4)
                        for n, primitive in enumerate(primitives):
                            index_accessor = scene["accessors"][primitive["indices"]]
                            index_view = scene["bufferViews"][index_accessor["bufferView"]]
                            index_type = {5121: "B", 5123: "H", 5125: "I"}[index_accessor["componentType"]]
                            indices = struct.unpack_from("<" + index_type * index_accessor["count"], blob,
                                                         index_view.get("byteOffset", 0) + index_accessor.get("byteOffset", 0))
                            used = sorted(set(indices))
                            self.assertEqual(used, list(range(n * 4, n * 4 + 4)))
                            left, top, width, height = RECTANGLES[n]
                            positions = [(left + dx - 256, 0, top + dz - 256)
                                         for dx, dz in ((0, 0), (0, height), (width, height), (width, 0))]
                            for semantic, size, expected in (
                                ("POSITION", 3, positions),
                                ("TEXCOORD_0", 2, [(0, 0), (0, 1), (1, 1), (1, 0)])):
                                accessor = scene["accessors"][primitive["attributes"][semantic]]
                                view = scene["bufferViews"][accessor["bufferView"]]
                                offset = view.get("byteOffset", 0) + accessor.get("byteOffset", 0)
                                values = [struct.unpack_from("<" + "f" * size, blob,
                                          offset + i * view.get("byteStride", size * 4))
                                          for i in used]
                                self.assertEqual(values, expected)
                            material = scene["materials"][primitive["material"]]
                            self.assertEqual(material["name"], f"mat{n}")
                            self.assertTrue(material["doubleSided"])
                            texture_index = material["pbrMetallicRoughness"]["baseColorTexture"]["index"]
                            source = scene["textures"][texture_index]["source"]
                            self.assertEqual(scene["images"][source]["uri"], f"tile{n}.png")
                            image = (decoded / scene["images"][source]["uri"]).read_bytes()
                            self.assertEqual(struct.unpack_from(">II", image, 16), (width, height))
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

    def test_multientry_lookup_and_budget_rejection(self):
        for names in (["tile0", "tile1", "tile2", "tile3"],
                      ["z", "a", "hello", "foo", "long_resource"],
                      ["quad3", "quad1", "quad0", "quad2"]):
            values = [(name, struct.pack("<I", i)) for i, name in enumerate(names)]
            self.assertEqual(multi_entries(resource_dictionary(values), 0), dict(values))
        with self.assertRaises(ValueError):
            resource_dictionary([("duplicate", bytes(4)), ("duplicate", bytes(4))])
        from unittest.mock import patch
        with patch("outdoor_nitro.MAP_TEXTURE_BUDGET", 102399), self.assertRaises(ValueError):
            textures(bytes((255, 255, 255, 255)) * (320 * 320))