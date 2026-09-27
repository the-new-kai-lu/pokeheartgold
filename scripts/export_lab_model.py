#!/usr/bin/env python3
"""Export an unhooked, flat Nitro lab model (not a playable 3D map).

Binary layouts: NNS G3D res_struct.h, Nitro GX command encoding. Names use
single-entry Patricia dictionaries; no template model or donor code is copied.
The plane covers [-104,104] in world X/Z: 13 cells of 16 world units.
"""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import zlib

from hgss_land import Land, flat_bdhc


def dictionary(name=None, datum=b""):
    """NNS single-entry dictionary, including the runtime lookup tree."""
    if name is None:
        return struct.pack("<BBHHH4sHH", 0, 0, 16, 8, 12,
                           b"\x7f\0\0\0", 0, 4)
    raw = name.encode("ascii")
    if not raw or len(raw) > 16 or b"\0" in raw:
        raise ValueError("Invalid resource name")
    key = raw.ljust(16, b"\0")
    bit = int.from_bytes(key, "little").bit_length() - 1
    size = 20 + len(datum) + 16
    return (struct.pack("<BBHHH", 0, 1, size, 8, 16)
            + bytes((127, 1, 0, 0, bit, 0, 1, 0))
            + struct.pack("<HH", len(datum), 4 + len(datum)) + datum + key)


def rgba_preview(data):
    """Read only the CRC-checked, unfiltered RGBA extraction output."""
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError("Not PNG")
    pos, compressed, header, ended = 8, bytearray(), None, False
    while pos < len(data):
        length = struct.unpack_from(">I", data, pos)[0]
        tag = data[pos + 4:pos + 8]
        payload = data[pos + 8:pos + 8 + length]
        crc = struct.unpack_from(">I", data, pos + 8 + length)[0]
        if zlib.crc32(tag + payload) != crc:
            raise ValueError("PNG CRC mismatch")
        pos += length + 12
        if tag == b"IHDR":
            header = struct.unpack(">IIBBBBB", payload)
        elif tag == b"IDAT":
            compressed.extend(payload)
        elif tag == b"IEND":
            ended = True
            break
    if header != (208, 208, 8, 6, 0, 0, 0) or not ended or pos != len(data):
        raise ValueError("Expected 208x208 extractor RGBA PNG")
    rows = zlib.decompress(compressed)
    if len(rows) != 208 * 833 or any(rows[y * 833] for y in range(208)):
        raise ValueError("Expected unfiltered extraction rows")
    pixels = b"".join(rows[y * 833 + 1:(y + 1) * 833] for y in range(208))
    if any(pixels[i] != 255 for i in range(3, len(pixels), 4)):
        raise ValueError("Composite must be opaque")
    return pixels


def texture(pixels):
    # Restore the exact original BGR555 values from extractor's expanded bytes.
    colors = [sum(round(pixels[i + c] * 31 / 255) << (5 * c)
                  for c in range(3)) for i in range(0, len(pixels), 4)]
    palette = sorted(set(colors))
    if len(palette) > 256:
        raise ValueError("Lab exceeds lossless 256-color texture budget")
    lookup = {value: index for index, value in enumerate(palette)}
    image = bytearray(256 * 256)
    for y in range(208):
        image[y * 256:y * 256 + 208] = bytes(lookup[c] for c in colors[y * 208:(y + 1) * 208])
    palette += [0] * (256 - len(palette))
    params = (5 << 20) | (5 << 23) | (4 << 26)
    texdict = dictionary("lab", struct.pack("<II", params, 0))
    paldict = dictionary("lab", struct.pack("<HH", 0, 0))
    texoff = 60 + len(texdict) + len(paldict)
    paloff = texoff + len(image)
    header = (b"TEX0" + struct.pack("<I", paloff + 512)
              + struct.pack("<IHHHHI", 0, len(image) // 8, 60, 0, 0, texoff)
              + struct.pack("<IHHHHII", 0, 0, 60, 0, 0, texoff, texoff)
              + struct.pack("<IHHHHI", 0, 64, 0, 60 + len(texdict), 0, paloff))
    assert len(header) == 60
    return header + texdict + paldict + image + struct.pack("<256H", *palette), params


def gx_command(opcode, *params):
    # One command + three NOPs per packed command word. Legal, simple to audit.
    return struct.pack("<" + "I" * (1 + len(params)), opcode, *params)


def model(params):
    node = dictionary("root", struct.pack("<I", 40)) + struct.pack("<HH", 7, 0)
    sbc = bytes((0x26, 0, 0, 0, 0, 2, 0, 1, 0x0b, 4, 0, 5, 0, 1, 0, 0))
    # One material, one texture pairing and one palette pairing; material IDs
    # follow the dictionaries and are explicitly initialized to zero.
    mat_offset, tex_offset, pal_offset, pair_offset = 124, 44, 84, 168
    material = struct.pack("<HH6I4H2i", 0, 44, 0x7fffffff, 0,
                           0x1f00c0, 0xffffffff, params, 0xffffffff,
                           0, 0x1ff, 256, 256, 4096, 4096)
    mats = (struct.pack("<HH", tex_offset, pal_offset)
            + dictionary("labmat", struct.pack("<I", mat_offset))
            + dictionary("lab", struct.pack("<HBB", pair_offset, 1, 0))
            + dictionary("lab", struct.pack("<HBB", pair_offset, 1, 0))
            + material + b"\0" * 4)
    assert len(mats) == 172
    commands = gx_command(0x20, 0x7fff) + gx_command(0x40, 1)
    # A quad with explicit UV and fixed-point16 XYZ. Model scale 64 converts
    # [-1.625,1.625] vertex units to [-104,104] world units.
    for x, z, u, v in ((-6656, -6656, 0, 0), (-6656, 6656, 0, 3328),
                        (6656, 6656, 3328, 3328), (6656, -6656, 3328, 0)):
        commands += gx_command(0x22, u | (v << 16))
        commands += gx_command(0x23, x & 0xffff, z & 0xffff)
    commands += gx_command(0x41)
    shapes = (dictionary("floor", struct.pack("<I", 40))
              + struct.pack("<HHIII", 0, 16, 0, 16, len(commands)) + commands)
    sbcoff = 64 + len(node)
    matoff = sbcoff + len(sbc)
    shpoff = matoff + len(mats)
    size = shpoff + len(shapes)
    info = (bytes((0, 0, 0, 1, 1, 1, 1, 0))
            + struct.pack("<ii4H6hii", 64 * 4096, 64, 4, 1, 0, 1,
                          -6656, 0, -6656, 13312, 0, 13312, 64 * 4096, 64))
    data = struct.pack("<5I", size, sbcoff, matoff, shpoff, size) + info + node + sbc + mats + shapes
    assert len(data) == size
    return b"MDL0" + struct.pack("<I", size + 48) + dictionary("emerald_lab", struct.pack("<I", 48)) + data


def container(signature, blocks):
    offset = 16 + 4 * len(blocks)
    offsets = []
    for block in blocks:
        offsets.append(offset)
        offset += len(block)
    return (struct.pack("<4sHHIHH", signature, 0xfeff, 2 if signature == b"BMD0" else 1,
                        offset, 16, len(blocks))
            + struct.pack("<" + "I" * len(offsets), *offsets) + b"".join(blocks))


def export(pack, output):
    manifest = json.loads((pack / "manifest.json").read_text())
    preview = (pack / "preview.png").read_bytes()
    if hashlib.sha256(preview).hexdigest() != manifest["outputs"]["preview.png"]:
        raise ValueError("Preview differs from extracted manifest")
    tex, params = texture(rgba_preview(preview))
    mdl = model(params)
    standalone = container(b"BMD0", (mdl, tex))
    # HGSS land models use separate area textures. Emit both representations;
    # neither is installed into a live area until binding/rendering is tested.
    external = container(b"BMD0", (mdl,))
    land = Land(0x1234, b"", b"\0" * 2048, b"", external,
                flat_bdhc(-104, -104, 104, 104)).encode()
    artifacts = {"lab.nsbmd": standalone, "lab.nsbtx": container(b"BTX0", (tex,)),
                 "lab.land": land}
    output.mkdir(parents=True, exist_ok=False)
    for name, data in artifacts.items():
        (output / name).write_bytes(data)
    report = dict(status="unhooked-flat-render-prototype", world_bounds=[-104, 104],
                  terrain_status="zero-initialized, not donor walkability",
                  model_vertices=4, model_quads=1, texture_bytes=65536,
                  palette_bytes=512, preview_sha256=hashlib.sha256(preview).hexdigest(),
                  outputs={k: hashlib.sha256(v).hexdigest() for k, v in artifacts.items()},
                  limitations=["Not rendered or integrated into HGSS",
                               "Flat composite loses height and foreground occlusion",
                               "Terrain semantics, camera, NPCs and warps not authored"])
    (output / "manifest.json").write_text(json.dumps(report, indent=2) + "\n")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pack", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(export(args.pack, args.output), indent=2))


if __name__ == "__main__":
    main()