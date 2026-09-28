"""Uninstalled actor texture candidate: pixels and native table ordering."""
import hashlib
import json
import os
import shutil
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from export_birch_actor import FRAMES, GEOMETRY_SHA256, TEMPLATE_SHA256, build, export
from extract_emerald_lab import indexed_png


class BirchActorTests(unittest.TestCase):
    def copy_native_inputs(self, root):
        relative = Path("files/data/mmodel/mmodel")
        target = root / relative
        target.mkdir(parents=True)
        for name in ("mmodel_00000054.NSBTX", "mmodel_00000266.NSBMD", "mmodel_00000280.json"):
            shutil.copyfile(ROOT / relative / name, target / name)
        return target

    def test_reject_geometry_drift_before_writing(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            native = self.copy_native_inputs(root)
            geometry = native / "mmodel_00000266.NSBMD"
            data = bytearray(geometry.read_bytes())
            data[-1] ^= 1
            geometry.write_bytes(data)
            out = root / "actor"
            with self.assertRaisesRegex(ValueError, "geometry266"):
                export(root, root / "absent-donor", out)
            self.assertFalse(out.exists())

    def test_reject_frame_table_drift_before_writing(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            native = self.copy_native_inputs(root)
            path = native / "mmodel_00000280.json"
            original = path.read_text()
            for field in ("unk0", "unk1", "unk2", "row_count"):
                with self.subTest(field=field):
                    table = json.loads(original)
                    if field == "row_count":
                        table["data"].pop()
                    else:
                        table["data"][0][field] += 1
                    path.write_text(json.dumps(table))
                    out = root / "actor"
                    with self.assertRaisesRegex(ValueError, "frame table280"):
                        export(root, root / "absent-donor", out)
                    self.assertFalse(out.exists())

    def test_reject_template(self):
        with self.assertRaises(ValueError):
            build(b"bad", b"", b"")

    def test_native_table(self):
        table = json.loads((ROOT / "files/data/mmodel/mmodel/mmodel_00000280.json").read_text())["data"]
        self.assertEqual([v["unk1"] for v in table], [0, 8, 9, 10, 11, 12, 13, 14, 15, 1, 2, 3, 4, 5, 6, 7])

    def test_all_donor_pixels_and_alpha_padding(self):
        donor = ROOT.parent / "pokeemerald"
        if not donor.exists():
            self.skipTest("Pinned Emerald donor required")
        with tempfile.TemporaryDirectory() as temp:
            out = Path(temp) / "actor"
            report = export(ROOT, donor, out)
            data = (out / "birch.nsbtx").read_bytes()
            self.assertFalse(report["RuntimeVerified"])
            self.assertEqual(report["source_sha256"]["template"], TEMPLATE_SHA256)
            self.assertEqual(report["source_sha256"]["geometry"], GEOMETRY_SHA256)
            self.assertEqual(report["source_sha256"]["frame_table"], hashlib.sha256(
                (ROOT / "files/data/mmodel/mmodel/mmodel_00000280.json").read_bytes()).hexdigest())
            self.assertEqual(report["declared_descriptor_flags"], 0)
            self.assertEqual(hashlib.sha256(data).hexdigest(),
                             "5c699d10d769574fa1a7c4e0b0c4e79eee301d56db3353c702de4ee9d069cfdf")
            self.assertEqual(hashlib.sha256(data).hexdigest(), report["outputs"]["birch.nsbtx"])
            _, _, pixels = indexed_png((donor / "graphics/object_events/pics/people/prof_birch.png").read_bytes())
            base = struct.unpack_from("<I", data, 16)[0]
            image = base + struct.unpack_from("<I", data, base + 20)[0]
            dictionary = base + struct.unpack_from("<H", data, base + 14)[0]
            entries = dictionary + struct.unpack_from("<H", data, dictionary + 6)[0]
            unit, names = struct.unpack_from("<HH", data, entries)
            self.assertEqual(data[dictionary + 1], 16)
            seen = set()
            for i in range(16):
                name = data[entries + names + i * 16:entries + names + (i + 1) * 16].rstrip(b"\0").decode()
                suffix = int(name.split(".")[1])
                seen.add(FRAMES[suffix - 1])
                param = struct.unpack_from("<I", data, entries + 4 + i * unit)[0]
                self.assertEqual(param >> 20, 0x2d2)
                offset = image + (param & 65535) * 8
                unpacked = [n for b in data[offset:offset + 512] for n in (b & 15, b >> 4)]
                for y in range(32):
                    self.assertEqual(unpacked[y * 32:y * 32 + 8], [0] * 8)
                    self.assertEqual(unpacked[y * 32 + 24:y * 32 + 32], [0] * 8)
                    expected = pixels[y * 144 + FRAMES[suffix - 1] * 16:y * 144 + FRAMES[suffix - 1] * 16 + 16]
                    self.assertEqual(unpacked[y * 32 + 8:y * 32 + 24], expected[::-1] if suffix >= 13 else expected)
            self.assertEqual(seen, set(range(9)))
            if os.environ.get("APICULA"):
                subprocess.run([os.environ["APICULA"], "convert", str(out / "birch.nsbtx"),
                                "--more-textures", "-o", str(out / "decoded")],
                               check=True, capture_output=True)
                self.assertEqual(len(list((out / "decoded").glob("*.png"))), 16)
            with self.assertRaises(ValueError):
                export(ROOT, donor, out)