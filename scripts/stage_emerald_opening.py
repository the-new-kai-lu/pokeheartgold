#!/usr/bin/env python3
"""Stage three append-only Emerald opening resource candidates in a fresh overlay.

This does not install map headers, events, scripts, entrances, doors or warps.
The flat exterior perimeters and the lab exits remain blocked. In particular
this is not a playable episode, an encounter implementation or a ROM patch.
"""

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import struct
import tempfile

from extract_emerald_lab import DONOR
from hgss_land import Land, narc_members
from stage_lab_archives import pack_narc


# The lab exporter does not yet put a donor revision in its manifest. Require
# the independently pinned lab preview, in addition to verifying every asset
# against the manifest, until that exporter records a versioned source pack.
PINNED_LAB_PREVIEW = "5a98c7d14cc1c506aa04242819b48f6250f1969e794ce7cdfb90951cfb7a6f60"
PINNED_EXTERIOR_SOURCES = {
    "town": {
        "preview.png": "e9842e1d0f1c5bad9e0ba76cbff79b199be4c76888e302c719bc9cb5cca3651a",
        "cells.json": "a06a13b786fd6a46fc6b0e43f870eeae8093c261a62d1059affe3df684cb9ce8",
        "chunk-plan.json": "df7843546b5d4810728f9327c5c9b91a0209bdec72146bcc78936fcb50c7b3c7",
    },
    "route": {
        "preview.png": "ce22420881a428c06ba2faa621a5995be81a4274247eb2e1a1a29cf5f1153359",
        "cells.json": "a8b4dd51296c3fcf416914f1764cf8da1852489b5d375d23882a8df3e5d96440",
        "chunk-plan.json": "fe70a07acf5c34110ff259ac50f76203a635bfcf45afbef6a2f1b07aa7c05091",
    },
}
ARCHIVES = {
    "areas": "files/a/0/4/2",
    "textures": "files/a/0/4/4",
    "land": "files/a/0/6/5",
    "props": "files/a/0/4/3",
}
COUNTS = {"areas": 106, "textures": 106, "land": 676, "props": 104}
STOCK_ARCHIVE_SHA256 = {
    "areas": "991506d5626fee587e4bf27042ae7b2945e167b89d6ec9f2d834d29e7476d58f",
    "textures": "6385837c11139c543884434a54768e7279b485214b7ca309cf8a670d8f98d647",
    "land": "0817bd81cc30342bc40dd6ce829121e9a8be4e9d04d0b790f8d9d99688c4bebe",
    "props": "2fc8901dada240a9b4f8040a697d0eead1e33e61ec9f3c80a61cbc191f60c4c9",
}
MAPS = (
    ("lab", "LittlerootTown_ProfessorBirchsLab", 540, 106, 676, 288, 491,
     "map_matrix_0288_HOENN_LAB.bin", "lab"),
    ("town", "LittlerootTown", 541, 107, 677, 289, 492,
     "map_matrix_0289_LITTLEROOT_TOWN.bin", "outdoor"),
    ("route", "Route101", 542, 108, 678, 290, 493,
     "map_matrix_0290_ROUTE_101.bin", "outdoor"),
)
MATRIX_DIR = "files/fielddata/mapmatrix/map_matrix"


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def expected(manifest, key, value, label):
    if manifest.get(key) != value:
        raise ValueError(f"{label}: expected {key}={value!r}, got {manifest.get(key)!r}")


def checked_nitro(data, signature, labels):
    """Validate Nitro container lengths/blocks; return its complete blocks."""
    if len(data) < 16 + 4 * len(labels):
        raise ValueError(f"Truncated {signature.decode()} resource")
    magic, byte_order, version, size, header, count = struct.unpack_from("<4sHHIHH", data)
    if (magic, byte_order, version, size, header, count) != (
            signature, 0xfeff, 2 if signature == b"BMD0" else 1,
            len(data), 16, len(labels)):
        raise ValueError(f"Invalid {signature.decode()} container header")
    offsets = struct.unpack_from("<" + "I" * count, data, 16)
    pos, blocks = 16 + 4 * count, []
    for offset, label in zip(offsets, labels):
        if offset != pos or offset + 8 > len(data):
            raise ValueError(f"Invalid {signature.decode()} block offset")
        tag, length = struct.unpack_from("<4sI", data, offset)
        if tag != label or length < 8 or offset + length > len(data):
            raise ValueError(f"Invalid {signature.decode()} {label.decode()} block")
        blocks.append(data[offset:offset + length])
        pos = offset + length
    if pos != len(data):
        raise ValueError(f"Trailing {signature.decode()} resource bytes")
    return blocks


def load_assets(kind, directory):
    label = kind
    manifest = json.loads((directory / "manifest.json").read_text())
    if kind == "lab":
        expected(manifest, "status", "unhooked-flat-render-prototype", label)
        expected(manifest, "terrain_origin", [9, 9], label)
        expected(manifest, "world_bounds", [-112, 96], label)
        expected(manifest, "preview_sha256", PINNED_LAB_PREVIEW, label)
        expected(manifest, "texture_bytes", 65536, label)
        expected(manifest, "palette_bytes", 512, label)
        names = ("lab.land", "lab.nsbtx", "lab.nsbmd")
        origin = [9, 9]
    else:
        expected(manifest, "status", "uninstalled-flat-exterior-prototype", label)
        expected(manifest, "layout", "LittlerootTown" if kind == "town" else "Route101", label)
        expected(manifest, "expected_donor_revision", DONOR, label)
        expected(manifest, "terrain_origin", [0, 0], label)
        expected(manifest, "donor_dimensions", [20, 20], label)
        expected(manifest, "world_bounds", [-256, 64], label)
        expected(manifest, "RuntimeVerified", False, label)
        expected(manifest, "texture_bytes", 102400, label)
        expected(manifest, "map_texture_budget", 102400, label)
        expected(manifest, "palette_bytes", 512, label)
        if manifest.get("terrain_profile", "conservative") != "conservative":
            raise ValueError(f"{label}: native-grass-probe is not approved for this stager")
        source = manifest.get("source_outputs")
        if source != PINNED_EXTERIOR_SOURCES[kind]:
            raise ValueError(f"{label}: donor extraction hashes differ from pinned Emerald source")
        names = ("outdoor.land", "outdoor.nsbtx", "outdoor.nsbmd")
        origin = [0, 0]
    if not isinstance(manifest.get("outputs"), dict) or set(manifest["outputs"]) != set(names):
        raise ValueError(f"{label}: unexpected or missing exporter outputs")
    artifacts = {}
    for name in names:
        data = (directory / name).read_bytes()
        if sha256(data) != manifest["outputs"][name]:
            raise ValueError(f"{label}: {name} differs from exporter manifest")
        artifacts[name] = data
    land = Land.decode(artifacts[names[0]])
    if land.encode() != artifacts[names[0]] or land.marker != 0x1234 or land.extra or land.props or not land.collision:
        raise ValueError(f"{label}: unexpected authored land sections")
    words = struct.unpack("<1024H", land.terrain)
    if set(words) - {0, 0x8000}:
        raise ValueError(f"{label}: only conservative blocked/ordinary terrain may be staged")
    if kind == "lab":
        exits = manifest.get("pending_exits")
        if (not isinstance(exits, list) or
                {tuple(e.get("terrain", [])) for e in exits} != {(15, 21), (16, 21)} or
                any(words[e["terrain"][1] * 32 + e["terrain"][0]] != 0x8000 for e in exits)):
            raise ValueError("lab: donor exits must remain blocked until native warps are authored")
        if any(words[z * 32 + x] != 0x8000 for z in range(32) for x in range(32)
               if not (9 <= x <= 21 and 9 <= z <= 21)):
            raise ValueError("lab: unverified terrain outside model footprint")
    else:
        if any(words[z * 32 + x] != 0x8000 for z in range(32) for x in range(32)
               if x >= 20 or z >= 20 or x in (0, 19) or z in (0, 19)):
            raise ValueError(f"{label}: exterior perimeter and padding must stay sealed")
        unsupported = manifest.get("unsupported_cells")
        if not isinstance(unsupported, list) or len(unsupported) != (5 if kind == "town" else 104):
            raise ValueError(f"{label}: unsupported donor-cell inventory changed")
        if any(not isinstance(cell.get("donor"), list) or len(cell["donor"]) != 2 or
               not all(isinstance(c, int) and 0 <= c < 20 for c in cell["donor"]) or
               words[cell["donor"][1] * 32 + cell["donor"][0]] != 0x8000
               for cell in unsupported):
            raise ValueError(f"{label}: unsupported donor cells may not be walkable")
    external = checked_nitro(land.model, b"BMD0", (b"MDL0",))
    standalone = checked_nitro(artifacts[names[2]], b"BMD0", (b"MDL0", b"TEX0"))
    texture = checked_nitro(artifacts[names[1]], b"BTX0", (b"TEX0",))
    if external[0] != standalone[0] or texture[0] != standalone[1]:
        raise ValueError(f"{label}: separate field model/texture differ from standalone model")
    return manifest, artifacts, origin


def stage(root, lab_assets, town_assets, route_assets, output):
    root, output = Path(root), Path(output)
    if output.exists() or output.is_symlink():
        raise ValueError("Refusing existing output")
    dirs = {"lab": Path(lab_assets), "town": Path(town_assets), "route": Path(route_assets)}
    inputs = {}
    for kind in dirs:
        inputs[kind] = load_assets(kind, dirs[kind])
    originals = {kind: (root / path).read_bytes() for kind, path in ARCHIVES.items()}
    members = {kind: narc_members(data) for kind, data in originals.items()}
    if {kind: len(files) for kind, files in members.items()} != COUNTS:
        raise ValueError("Source archive counts changed; review append allocation")
    if any(sha256(data) != STOCK_ARCHIVE_SHA256[kind] for kind, data in originals.items()):
        raise ValueError("Source archives differ from pinned stock HGSS resources")
    template = members["areas"][1]
    if template.hex() != "01000100ffff0000":
        raise ValueError("Native indoor area template changed")
    matrix_root = root / MATRIX_DIR
    existing = {int(m.group(1)) for file in matrix_root.glob("*.bin")
                if (m := re.fullmatch(r"map_matrix_(\d{4})(?:_.*)?\.bin", file.name))}
    if len(list(matrix_root.glob("*.bin"))) != 288 or existing != set(range(288)):
        raise ValueError("Source map-matrix index changed; review append allocation")
    added = {"areas": [], "textures": [], "land": []}
    matrices, bindings = {}, {}
    for kind, layout, map_id, area_id, land_id, matrix_id, event_id, matrix_name, prefix in MAPS:
        manifest, artifacts, origin = inputs[kind]
        if (len(members["areas"]) + len(added["areas"]), len(members["textures"]) + len(added["textures"]),
                len(members["land"]) + len(added["land"])) != (area_id, area_id, land_id):
            raise ValueError(f"{kind}: append ordering differs from planned IDs")
        added["areas"].append(template[:2] + struct.pack("<H", area_id) + template[4:])
        added["textures"].append(artifacts[prefix + ".nsbtx"])
        added["land"].append(artifacts[prefix + ".land"])
        matrices[f"{MATRIX_DIR}/{matrix_name}"] = struct.pack("<5BH", 1, 1, 0, 0, 0, land_id)
        bindings[kind] = {
            "donor_layout": layout, "planned_map": map_id, "area": area_id,
            "texture": area_id, "land": land_id, "matrix": matrix_id,
            "planned_events": event_id, "terrain_origin": origin,
            "script": 965 if kind == "lab" else None,
            "messages": 829 if kind == "lab" else None,
            "donor_revision": DONOR if kind != "lab" else None,
        }
    staged = {}
    for kind, extra in added.items():
        packed = pack_narc(members[kind] + extra)
        appended = narc_members(packed)
        if appended[:len(members[kind])] != members[kind] or appended[len(members[kind]):] != extra:
            raise ValueError(f"{kind}: original or appended member differed after repacking")
        staged[ARCHIVES[kind]] = packed
    staged.update(matrices)
    report = {
        "status": "resource-overlay-only-three-maps-unreachable",
        "donor": "Emerald", "expected_donor_revision": DONOR,
        "bindings": bindings,
        "source_sha256": {ARCHIVES[k]: sha256(v) for k, v in originals.items()},
        "asset_sha256": {kind: {name: sha256(data) for name, data in value[1].items()}
                         for kind, value in inputs.items()},
        "output_sha256": {path: sha256(data) for path, data in staged.items()},
        "archive_member_counts": {kind: {"before": len(members[kind]),
                                         "after": len(members[kind]) + len(added.get(kind, []))}
                                  for kind in ARCHIVES},
        "original_archive_members_preserved": True,
        "source_matrix_count": 288,
        "matrix_u8_cached_aliases": {"288": 32, "289": 33, "290": 34},
        "area_template": 1,
        "limitations": [
            "No source map headers, NPC/event archives, scripts, entrances, doors, return travel or gift changed",
            "Area entries reuse indoor template flags/lighting; outdoor behavior and allocator are not validated",
            "Exterior perimeters and donor doors/grass/ledges remain blocked; no donor connections become native warps",
            "Matrix IDs 288-290 cache as u8 aliases 32-34; audit every consumer before map hookup",
            "One area/texture is planned per map; 100 KiB outdoor texture sizes do not establish concurrent VRAM headroom",
            "Lab preview matches the pinned donor, but its exporter does not yet carry a donor-revision field",
            "Not a connected map, gameplay episode, completed Hoenn campaign or installed ROM",
        ],
    }
    # Build an entire fresh overlay before exposing it, then atomically rename.
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=f".{output.name}-", dir=output.parent) as directory:
        staging = Path(directory)
        for path, data in staged.items():
            target = staging / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
        (staging / "manifest.json").write_text(json.dumps(report, indent=2) + "\n")
        if output.exists() or output.is_symlink():
            raise ValueError("Refusing existing output")
        os.rename(staging, output)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--lab-assets", required=True, type=Path)
    parser.add_argument("--town-assets", required=True, type=Path)
    parser.add_argument("--route-assets", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(stage(args.root, args.lab_assets, args.town_assets, args.route_assets,
                           args.output), indent=2))


if __name__ == "__main__":
    main()