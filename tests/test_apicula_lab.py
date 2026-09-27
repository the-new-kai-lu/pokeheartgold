"""Optional external decoder regression; APICULA must name a built executable."""
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
from export_lab_model import export
from extract_emerald_lab import extract
from hgss_land import Land


@unittest.skipUnless(os.environ.get("APICULA"), "Independent apicula executable not supplied")
class ApiculaLabTests(unittest.TestCase):
    def test_embedded_and_external_texture_bindings(self):
        donor = Path(os.environ.get("EMERALD_DONOR", ROOT.parent / "pokeemerald"))
        if not donor.exists():
            self.skipTest("Pinned Emerald donor checkout unavailable")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            pack, model = root / "pack", root / "model"
            extract(donor, pack)
            export(pack, model)
            external = root / "external.nsbmd"
            external.write_bytes(Land.decode((model / "lab.land").read_bytes()).model)
            for variant, inputs in (
                ("embedded", [model / "lab.nsbmd"]),
                ("external", [external, model / "lab.nsbtx"]),
            ):
                output = root / variant
                subprocess.run([os.environ["APICULA"], "convert", *map(str, inputs),
                                "-o", str(output), "-f", "gltf"], check=True,
                               capture_output=True, text=True)
                scene = json.loads((output / "emerald_lab.gltf").read_text())
                blob = (output / scene["buffers"][0]["uri"]).read_bytes()
                primitive = scene["meshes"][0]["primitives"][0]

                def floats(index, width):
                    accessor = scene["accessors"][index]
                    view = scene["bufferViews"][accessor["bufferView"]]
                    self.assertEqual(accessor["componentType"], 5126)
                    base = view.get("byteOffset", 0) + accessor.get("byteOffset", 0)
                    stride = view.get("byteStride", width * 4)
                    return [struct.unpack_from("<" + "f" * width, blob, base + i * stride)
                            for i in range(accessor["count"])]

                self.assertEqual(floats(primitive["attributes"]["POSITION"], 3),
                                 [(-104, 0, -104), (-104, 0, 104),
                                  (104, 0, 104), (104, 0, -104)])
                self.assertEqual(floats(primitive["attributes"]["TEXCOORD_0"], 2),
                                 [(0, 0), (0, .8125), (.8125, .8125), (.8125, 0)])
                material = scene["materials"][primitive["material"]]
                self.assertTrue(material["doubleSided"])
                self.assertIn("baseColorTexture", material["pbrMetallicRoughness"])
                self.assertTrue((output / scene["images"][0]["uri"]).is_file())