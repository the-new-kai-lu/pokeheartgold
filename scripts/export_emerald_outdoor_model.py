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


# Audited native constants, not copied donor attributes:
# include/constants/metatile_behavior.h; include/encounter_tables_narc.h.
TILE_BEHAVIOR_TALL_GRASS = 2
ENCDATA_NA = 255
PROFILES = ("conservative", "native-grass-probe")


def validate_profile(profile, encounter_bank, normal_field):
    if profile not in PROFILES:
        raise ValueError("Unknown terrain profile")
    if profile == "native-grass-probe":
        if encounter_bank != ENCDATA_NA or normal_field is not True:
            raise ValueError("Private grass probe requires explicit encounter bank 255 and normal-field prerequisite")
    elif encounter_bank is not None or normal_field:
        raise ValueError("Probe prerequisites require native-grass-probe profile")


def terrain(cells, profile="conservative", probe_encounter_bank=None, probe_normal_field=False):
    """Conservative ordinary ground, with explicitly gated private grass probe."""
    validate_profile(profile, probe_encounter_bank, probe_normal_field)
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
        grass_probe = profile == "native-grass-probe" and (behavior, collision, elevation) == (2, 0, 3)
        if not grass_probe and (behavior != 0 or (not collision and elevation != 3)):
            unsupported.append(dict(donor=[x, z], behavior=behavior, elevation=elevation,
                                    disposition="blocked; requires authored native semantics"))
        # Boundaries are deliberately sealed: donor connections are NOT warps.
        boundary = x in (0, 19) or z in (0, 19)
        grid[z * 32 + x] = 0 if ordinary and not collision and not boundary else 0x8000
        if grass_probe and not boundary:
            grid[z * 32 + x] = TILE_BEHAVIOR_TALL_GRASS
    return struct.pack("<1024H", *grid), unsupported


def export(pack, output, terrain_profile="conservative", probe_encounter_bank=None, probe_normal_field=False):
    validate_profile(terrain_profile, probe_encounter_bank, probe_normal_field)
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
    attributes, unsupported = terrain(json.loads(cell_data), terrain_profile,
                                      probe_encounter_bank, probe_normal_field)
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
            ("Only donor (behavior=2,collision=0,elevation=3) maps to named native tall grass; "
             "all ledges/doors and unsupported elevations remain blocked"
             if terrain_profile == "native-grass-probe" else
             "Nonordinary behaviors (including grass, ledges, doors) blocked, not translated"),
            "Nonordinary passable elevations blocked; no raw GBA elevation bits copied",
            "Outer donor perimeter and all native padding blocked; no travel/warps authored",
            "Unavailable lower source pixels only hidden beneath opaque composite pixels",
        ])
    if terrain_profile == "native-grass-probe":
        grass_candidates = [cell for cell in json.loads(cell_data)["cells"]
                            if (cell["behavior"], cell["collision"], cell["elevation"]) == (2, 0, 3)]
        report.update(
            status="private-uninstalled-native-grass-effect-probe",
            terrain_profile=terrain_profile, probe_encounter_bank=ENCDATA_NA,
            requiresGrassEffectsRuntimeValidation=True,
            native_grass_cells=struct.unpack("<1024H", attributes).count(TILE_BEHAVIOR_TALL_GRASS),
            donor_grass_candidates=len(grass_candidates),
            perimeter_grass_cells_blocked=sum(
                cell["x"] in (0, 19) or cell["y"] in (0, 19) for cell in grass_candidates),
            prerequisites=[
                "Destination header must actually use ENCDATA_NA=255; exporter does not edit or verify headers",
                "Normal field only: FLAG_SYS_PAL_PARK must be clear in the private fixture",
                "CLI declarations are prerequisites, NOT runtime safety or effect validation",
                "Native grass field-effect resources must be validated in the bounded private runtime probe",
                "No encounters expected only under these actual native header/fixture conditions",
            ])
        report["limitations"].append(
            "Private walk/effect authoring probe only; NOT production-ready or a wild-encounter implementation")
    output.mkdir(parents=True, exist_ok=False)
    for name, data in artifacts.items():
        (output / name).write_bytes(data)
    (output / "manifest.json").write_text(json.dumps(report, indent=2) + "\n")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pack", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--terrain-profile", choices=PROFILES, default="conservative")
    parser.add_argument("--probe-encounter-bank", type=int)
    parser.add_argument("--probe-normal-field", action="store_true",
                        help="Declare required normal-field fixture (Pal Park flag clear), not runtime verification")
    args = parser.parse_args()
    print(json.dumps(export(args.pack, args.output, args.terrain_profile,
                            args.probe_encounter_bank, args.probe_normal_field), indent=2))


if __name__ == "__main__":
    main()