"""Read exported binaries independently via their offset tables, not writer offsets."""
from pathlib import Path
import struct
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import export_lab_model as exporter
from extract_emerald_lab import extract
from hgss_land import Land


def entries(data, start):
    revision, count, size, _, offset = struct.unpack_from("<BBHHH", data, start)
    assert revision == 0 and start + size <= len(data)
    unit, names = struct.unpack_from("<HH", data, start + offset)
    result = {}
    for i in range(count):
        entry = start + offset + 4 + unit * i
        name_start = start + offset + names + 16 * i
        name = data[name_start:name_start + 16].rstrip(b"\0").decode("ascii")
        result[name] = data[entry:entry + unit]
        # Execute dictionary's one-entry Patricia traversal as runtime lookup
        # would do (root refBit127 -> highest set key bit -> entry self-link).
        root = data[start + 8:start + 12]
        node = data[start + 12:start + 16]
        assert root == bytes((127, 1, 0, 0))
        assert node[1:] == bytes((0, 1, i))
        key = int.from_bytes(name.encode().ljust(16, b"\0"), "little")
        assert key >> node[0] == 1
    return result


def blocks(data):
    sig, endian, version, size, header, count = struct.unpack_from("<4sHHIHH", data)
    assert sig in (b"BMD0", b"BTX0") and endian == 0xfeff and size == len(data)
    result = {}
    for offset in struct.unpack_from("<" + "I" * count, data, header):
        tag, size = struct.unpack_from("<4sI", data, offset)
        assert offset + size <= len(data)
        result[tag] = data[offset:offset + size]
    return result


class LabModelTests(unittest.TestCase):
    def test_geometry_offsets_material_bindings_and_scale(self):
        tex, params = exporter.texture(bytes((255, 255, 255, 255)) * 208 ** 2)
        mdl = blocks(exporter.container(b"BMD0", (exporter.model(params), tex)))[b"MDL0"]
        start, = struct.unpack("<I", entries(mdl, 8)["emerald_lab"])
        size, sbc, mat, shp, evp = struct.unpack_from("<5I", mdl, start)
        self.assertEqual(start + size, len(mdl))
        self.assertEqual(size, evp)
        self.assertEqual(struct.unpack_from("<ii", mdl, start + 28), (262144, 64))
        node, = struct.unpack("<I", entries(mdl, start + 64)["root"])
        self.assertEqual(struct.unpack_from("<HH", mdl, start + 64 + node), (7, 0))
        self.assertEqual(mdl[start + sbc:start + mat],
                         bytes((38, 0, 0, 0, 0, 2, 0, 1, 11, 4, 0, 5, 0, 1, 0, 0)))
        material, = struct.unpack("<I", entries(mdl, start + mat + 4)["labmat"])
        texdict, paldict = struct.unpack_from("<HH", mdl, start + mat)
        for pairing in (texdict, paldict):
            ids, count, bound = struct.unpack("<HBB", entries(mdl, start + mat + pairing)["lab"])
            self.assertEqual((count, bound), (1, 0))
            self.assertEqual(mdl[start + mat + ids], 0)
        self.assertEqual(struct.unpack_from("<I", mdl, start + mat + material + 20)[0], params)
        shape, = struct.unpack("<I", entries(mdl, start + shp)["floor"])
        shape += start + shp
        _, header, flags, offset, length = struct.unpack_from("<HHIII", mdl, shape)
        self.assertEqual(header, 16)
        display = mdl[shape + offset:shape + offset + length]
        pos, vertices, uvs, primitive = 0, [], [], None
        while pos < len(display):
            op, = struct.unpack_from("<I", display, pos)
            pos += 4
            if op in (0x20, 0x40, 0x22):
                arg, = struct.unpack_from("<I", display, pos)
                pos += 4
                if op == 0x40:
                    primitive = arg
                elif op == 0x22:
                    uvs.append((arg & 65535, arg >> 16))
            elif op == 0x23:
                x, y, z, pad = struct.unpack_from("<4h", display, pos)
                pos += 8
                self.assertEqual(pad, 0)
                vertices.append((x / 64, y / 64, z / 64))
            else:
                self.assertEqual(op, 0x41)
        self.assertEqual(primitive, 1)
        self.assertEqual(vertices, [(-104, 0, -104), (-104, 0, 104),
                                    (104, 0, 104), (104, 0, -104)])
        self.assertEqual(uvs, [(0, 0), (0, 3328), (3328, 3328), (3328, 0)])

    def test_real_donor_texture_is_lossless_and_land_roundtrips(self):
        donor = ROOT.parent / "pokeemerald"
        if not donor.is_dir():
            self.skipTest("Pinned Emerald checkout needed for authentic pixel comparison")
        with tempfile.TemporaryDirectory() as temp:
            pack, out = Path(temp) / "pack", Path(temp) / "nitro"
            extract(donor, pack)
            exporter.export(pack, out)
            tex = blocks((out / "lab.nsbtx").read_bytes())[b"TEX0"]
            tex_dict, = struct.unpack_from("<H", tex, 14)
            params, unused = struct.unpack("<II", entries(tex, tex_dict)["lab"])
            self.assertEqual((params >> 26) & 7, 4)
            self.assertEqual((8 << ((params >> 20) & 7), 8 << ((params >> 23) & 7)), (256, 256))
            image, = struct.unpack_from("<I", tex, 20)
            paldict, paldata = struct.unpack_from("<II", tex, 52)
            self.assertEqual(struct.unpack("<HH", entries(tex, paldict)["lab"]), (0, 0))
            colors = struct.unpack_from("<256H", tex, paldata)
            expected = exporter.rgba_preview((pack / "preview.png").read_bytes())
            for y in range(208):
                for x in range(208):
                    color = colors[tex[image + y * 256 + x]]
                    actual = bytes(((color >> (c * 5) & 31) * 255 // 31 for c in range(3)))
                    p = (y * 208 + x) * 4
                    self.assertEqual(actual, expected[p:p + 3])
            land = (out / "lab.land").read_bytes()
            self.assertEqual(Land.decode(land).encode(), land)
            self.assertEqual(blocks(Land.decode(land).model)[b"MDL0"],
                             blocks((out / "lab.nsbmd").read_bytes())[b"MDL0"])
            with self.assertRaises(FileExistsError):
                exporter.export(pack, out)
            preview = pack / "preview.png"
            preview.write_bytes(preview.read_bytes() + b"x")
            with self.assertRaisesRegex(ValueError, "manifest"):
                exporter.export(pack, Path(temp) / "bad")

    def test_reject_invalid_input(self):
        for name in ("", "x" * 17, "a\0b"):
            with self.assertRaises(ValueError):
                exporter.dictionary(name, b"\0" * 4)
        with self.assertRaises(ValueError):
            exporter.rgba_preview(b"bad")


if __name__ == "__main__":
    unittest.main()