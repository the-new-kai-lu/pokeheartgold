#!/usr/bin/env python3
"""Author an uninstalled Birch texture candidate using the audited human template."""
import argparse
import hashlib
import json
from pathlib import Path
import struct

from extract_emerald_lab import indexed_png, palette

TEMPLATE_SHA256 = "749200a9bcd618fc47b1d56ab8f0c41f3d453a64ceeb72e7318e14ed6975604b"
GEOMETRY_SHA256 = "3432dea6fcb47f310336f2ff6dd2e40cb428360efa7e2847d393e1e877d3cb9a"
TABLE_ORDER = (0, 8, 9, 10, 11, 12, 13, 14, 15, 1, 2, 3, 4, 5, 6, 7)
# Native natural suffix order: N, S, W, E; idle/step/idle/step.
FRAMES = (1, 5, 1, 6, 0, 3, 0, 4, 2, 7, 2, 8, 2, 7, 2, 8)


def build(template, png, pal):
    if hashlib.sha256(template).hexdigest() != TEMPLATE_SHA256:
        raise ValueError("Unaudited human template")
    width, height, pixels = indexed_png(png)
    if (width, height) != (144, 32):
        raise ValueError("Expected nine 16x32 donor frames")
    colors = palette(pal)
    result = bytearray(template)
    base = struct.unpack_from("<I", result, 16)[0]
    image = base + struct.unpack_from("<I", result, base + 20)[0]
    paloff = base + struct.unpack_from("<I", result, base + 56)[0]
    dictionary = base + struct.unpack_from("<H", result, base + 14)[0]
    entries = dictionary + struct.unpack_from("<H", result, dictionary + 6)[0]
    unit, names = struct.unpack_from("<HH", result, entries)
    written = {}
    for index in range(result[dictionary + 1]):
        name = bytes(result[entries + names + index * 16:entries + names + (index + 1) * 16]).rstrip(b"\0").decode("ascii")
        suffix = int(name.split(".")[1])
        donor = FRAMES[suffix - 1]
        canvas = bytearray(1024)
        for y in range(32):
            for x in range(16):
                sx = 15 - x if suffix >= 13 else x
                canvas[y * 32 + x + 8] = pixels[y * 144 + donor * 16 + sx]
        packed = bytes(canvas[i] | (canvas[i + 1] << 4) for i in range(0, 1024, 2))
        param = struct.unpack_from("<I", result, entries + 4 + index * unit)[0]
        offset = image + (param & 65535) * 8
        if offset in written and written[offset] != packed:
            raise ValueError("Template alias conflicts with donor mapping")
        written[offset] = packed
        result[offset:offset + 512] = packed
    native_colors = [sum(round(c[channel] * 31 / 255) << (5 * channel)
                         for channel in range(3)) for c in colors]
    struct.pack_into("<16H", result, paloff, *native_colors)
    return bytes(result)


def export(root, donor, output):
    if output.exists():
        raise ValueError("Refusing existing output")
    paths = {
        "template": root / "files/data/mmodel/mmodel/mmodel_00000054.NSBTX",
        "geometry": root / "files/data/mmodel/mmodel/mmodel_00000266.NSBMD",
        "frame_table": root / "files/data/mmodel/mmodel/mmodel_00000280.json",
    }
    inputs = {key: path.read_bytes() for key, path in paths.items()}
    if hashlib.sha256(inputs["geometry"]).hexdigest() != GEOMETRY_SHA256:
        raise ValueError("Unaudited native geometry266")
    expected_table = {"data": [
        {"unk0": i * 4, "unk1": index, "unk2": 0}
        for i, index in enumerate(TABLE_ORDER)
    ]}
    if json.loads(inputs["frame_table"]) != expected_table:
        raise ValueError("Unaudited native frame table280")
    inputs["png"] = (donor / "graphics/object_events/pics/people/prof_birch.png").read_bytes()
    inputs["palette"] = (donor / "graphics/object_events/palettes/npc_3.pal").read_bytes()
    data = build(inputs["template"], inputs["png"], inputs["palette"])
    report = dict(status="uninstalled-human-texture-candidate", RuntimeVerified=False,
                  source_sha256={k: hashlib.sha256(v).hexdigest() for k, v in inputs.items()},
                  outputs={"birch.nsbtx": hashlib.sha256(data).hexdigest()},
                  frames=list(FRAMES), mirrored_suffixes=[13, 14, 15, 16],
                  canvas=[32, 32], donor_offset=[8, 0], transparent_index=0,
                  native_geometry_member=266, native_frame_table_member=280,
                  declared_descriptor_flags=0,
                  native_quad_bounds=[[-16, 0, 0], [16, 32, 0]],
                  limitations=[
                      "Centered padding preserves all donor rows; world ground alignment remains untested",
                      "Native doctor texture names/order retained for table280 index compatibility",
                      "No sprite ID/model member reserved or installed; candidate next member863 needs consumer audit",
                      "No renderer, actor animation, scene, or runtime allocation validation",
                  ])
    output.mkdir(parents=True)
    (output / "birch.nsbtx").write_bytes(data)
    (output / "manifest.json").write_text(json.dumps(report, indent=2) + "\n")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--donor", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(export(args.root, args.donor, args.output), indent=2))