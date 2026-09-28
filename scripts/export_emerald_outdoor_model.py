#!/usr/bin/env python3
"""Author uninstalled, flat exterior prototypes; NOT faithful 3D maps."""
import argparse
import hashlib
import json
from pathlib import Path
import struct

from export_lab_model import container, rgba_preview
from hgss_land import Land, flat_bdhc
from outdoor_nitro import MAP_TEXTURE_BUDGET, RECTANGLES, model, textures


def terrain(cells):
    """Only ordinary elevation-3 ground is walkable; unknown semantics block."""
    if (cells["width"], cells["height"], len(cells["cells"])) != (20, 20, 400):
        raise ValueError("Expected complete 20x20 exterior")
    grid, seen, unsupported = [0x8000] * 1024, set(), []
    for cell in cells["cells"]:
        x, z = cell["x"], cell["y"]
        if not (0 <= x < 20 and 0 <= z < 20) or (x, z) in seen:
            raise ValueError("Invalid or duplicate donor cell")
        seen.add((x, z))
        collision, elevation, behavior = (cell[k] for k in ("collision", "elevation", "behavior"))
        if collision not in (0, 1):
            raise ValueError("Unaudited donor collision value")
        ordinary = behavior == 0 and elevation == 3
        if behavior != 0 or (not collision and elevation != 3):
            unsupported.append(dict(donor=[x, z], behavior=behavior, elevation=elevation,
                                    disposition="blocked; requires authored native semantics"))
        # Boundaries are deliberately sealed: donor connections are NOT warps.
        boundary = x in (0, 19) or z in (0, 19)
        grid[z * 32 + x] = 0 if ordinary and not collision and not boundary else 0x8000
    return struct.pack("<1024H", *grid), unsupported


def export(pack, output):
    manifest = json.loads((pack / "manifest.json").read_text())
    layout = manifest["layout"]
    if layout not in ("LittlerootTown", "Route101"):
        raise ValueError("Unsupported exterior layout")

    def verified(name):
        data = (pack / name).read_bytes()
        if hashlib.sha256(data).hexdigest() != manifest["outputs"][name]:
            raise ValueError(f"{name} differs from extraction manifest")
        return data

    preview, cell_data = verified("preview.png"), verified("cells.json")
    plan = json.loads(verified("chunk-plan.json"))
    if plan["dimensions"] != [20, 20] or plan["matrix_size"] != [1, 1]:
        raise ValueError("Unexpected donor chunk plan")
    attributes, unsupported = terrain(json.loads(cell_data))
    pixels = rgba_preview(preview, 320, 320)
    tex, params = textures(pixels)
    mdl = model(params)
    external = container(b"BMD0", (mdl,))
    artifacts = {
        "outdoor.nsbmd": container(b"BMD0", (mdl, tex)),
        "outdoor.nsbtx": container(b"BTX0", (tex,)),
        "outdoor.land": Land(0x1234, b"", attributes, b"", external,
                             flat_bdhc(-256, -256, 64, 64)).encode(),
    }
    report = dict(
        status="uninstalled-flat-exterior-prototype", layout=layout,
        expected_donor_revision=manifest["expected_donor_revision"],
        world_bounds=[-256, 64], terrain_origin=[0, 0], donor_dimensions=[20, 20],
        texture_rectangles=RECTANGLES, texture_bytes=struct.unpack_from("<H", tex, 12)[0] * 8,
        map_texture_budget=MAP_TEXTURE_BUDGET, remaining_field_texture_bytes=159744,
        RuntimeVerified=False, palette_bytes=512,
        visible_colors=len({pixels[i:i + 3] for i in range(0, len(pixels), 4)}),
        source_outputs={name: manifest["outputs"][name]
                        for name in ("preview.png", "cells.json", "chunk-plan.json")},
        unsupported_cells=unsupported,
        occluded_unavailable_lower_tiles=plan["occluded_unavailable_lower_tiles"],
        outputs={name: hashlib.sha256(data).hexdigest() for name, data in artifacts.items()},
        limitations=[
            "No archive installation, map header, matrix binding or runtime VRAM validation",
            "Old 262144-byte layout consumed entire field texture budget; unsafe to install",
            "102400-byte layout requires bounded concurrent map/props/NPC/transition allocation probe",
            "159744 bytes remaining in field texture budget is not proof other field allocations fit",
            "Flat composite loses height and foreground occlusion; no NPCs or animation",
            "Nonordinary behaviors (including grass, ledges, doors) blocked, not translated",
            "Nonordinary passable elevations blocked; no raw GBA elevation bits copied",
            "Outer donor perimeter and all native padding blocked; no travel/warps authored",
            "Unavailable lower source pixels only hidden beneath opaque composite pixels",
        ])
    output.mkdir(parents=True, exist_ok=False)
    for name, data in artifacts.items():
        (output / name).write_bytes(data)
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