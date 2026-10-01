#!/usr/bin/env python3
"""Stage append-only lab resources, without overwriting a ROM/source archive.

This is an opt-in filesystem overlay, NOT a reachable map. A header and event
binding must be supplied before using it in a build. Every original member is
verified after packing; output never changes the source tree.
"""
import argparse
import hashlib
import json
from pathlib import Path
import struct

from hgss_land import Land, narc_members


def pack_narc(members):
    image, entries = bytearray(), bytearray()
    for data in members:
        start = len(image)
        image.extend(data)
        entries.extend(struct.pack("<II", start, len(image)))
        image.extend(b"\xff" * (-len(image) % 4))
    fat = struct.pack("<HH", len(members), 0) + entries
    # Nitro anonymous-file root directory; field loaders use member IDs.
    fnt = struct.pack("<IHH", 4, 0, 1)
    blocks = b"".join(tag + struct.pack("<I", len(data) + 8) + data
                      for tag, data in ((b"BTAF", fat), (b"BTNF", fnt),
                                        (b"GMIF", image)))
    result = struct.pack("<4sHHIHH", b"NARC", 0xfffe, 0x100,
                         len(blocks) + 16, 16, 3) + blocks
    if narc_members(result) != list(members):
        raise ValueError("Packed members differ")
    return result


def stage(root, assets, output):
    if output.exists():
        raise ValueError("Refusing existing output")
    manifest = json.loads((assets / "manifest.json").read_text())
    generated = {}
    for name in ("lab.land", "lab.nsbtx"):
        data = (assets / name).read_bytes()
        if hashlib.sha256(data).hexdigest() != manifest["outputs"][name]:
            raise ValueError("Asset differs from exporter manifest: " + name)
        generated[name] = data
    Land.decode(generated["lab.land"])
    if generated["lab.nsbtx"][:4] != b"BTX0":
        raise ValueError("Expected separate Nitro texture resource")
    paths = {"areas": "files/a/0/4/2", "textures": "files/a/0/4/4",
             "land": "files/a/0/6/5", "props": "files/a/0/4/3"}
    originals = {k: (root / v).read_bytes() for k, v in paths.items()}
    members = {k: narc_members(v) for k, v in originals.items()}
    if [len(members[k]) for k in paths] != [106, 106, 676, 104]:
        raise ValueError("Source archive layout changed; review append IDs")
    # Area member 1 is the small indoor template, eight bytes:
    # prop-list u16, map-texture u16, lighting u16, two area flags.
    # Preserve native prop-list/lighting/flags, changing only the texture ID.
    template = members["areas"][1]
    if template.hex() != "01000100ffff0000":
        raise ValueError("Indoor area template changed")
    area = template[:2] + struct.pack("<H", 106) + template[4:]
    staged = {}
    for kind, appended in (("areas", area), ("textures", generated["lab.nsbtx"]),
                           ("land", generated["lab.land"])):
        staged[paths[kind]] = pack_narc(members[kind] + [appended])
    # MapMatrix_MapMatrixData_Load: width,height,header flag,altitude flag,
    # name length, optional name/headers/altitudes, model IDs. Missing headers
    # deliberately inherit the eventual map header passed by the field loader.
    matrix = struct.pack("<5BH", 1, 1, 0, 0, 0, 676)
    matrix_path = "files/fielddata/mapmatrix/map_matrix/map_matrix_0288_HOENN_LAB.bin"
    if len(list((root / "files/fielddata/mapmatrix/map_matrix").glob("*.bin"))) != 288:
        raise ValueError("Matrix append index changed")
    staged[matrix_path] = matrix
    report = {
        "status": "resource-overlay-only-not-reachable",
        "bindings": {"area": 106, "texture": 106, "land": 676, "matrix": 288,
                     "scripts": 965, "messages": 829},
        "area_template": 1,
        "source_sha256": {paths[k]: hashlib.sha256(v).hexdigest()
                          for k, v in originals.items()},
        "output_sha256": {k: hashlib.sha256(v).hexdigest() for k, v in staged.items()},
        "limitations": [
            "No map header, NPC/event bank, entrance, or return warp installed",
            "Matrix 288 caches as u8 32; no equality with main 0 or Safari 212",
            "Indoor template prop list retained; no prop placements authored",
            "Texture VRAM, rendering, and map transitions not runtime tested",
        ],
    }
    output.mkdir(parents=True)
    for path, data in staged.items():
        dest = output / path
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)
    (output / "manifest.json").write_text(json.dumps(report, indent=2) + "\n")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--assets", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(stage(args.root, args.assets, args.output), indent=2))