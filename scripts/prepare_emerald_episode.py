#!/usr/bin/env python3
"""Opt-in, source-only full opening composer; never builds or installs a ROM.

Consume the existing pinned travel inputs plus Emerald outdoor extraction packs.
Create a FRESH external tree. No compiled files, private predecessor trees,
proprietary tools, runtime operations or in-place cache updates are consumed.
"""
import argparse
import ctypes
import errno
import hashlib
import json
import os
from pathlib import Path
import struct
import subprocess
import tempfile
import sys

import episode_assets as assets
from episode_source_inventory import safe_relative
from export_lab_model import container, rgba_preview
from hgss_land import Land, narc_members
from prepare_emerald_opening import prepare as prepare_travel
from stage_lab_archives import pack_narc


TEMPLATES = Path(__file__).with_name("episode_templates")
DONOR_COMMIT = "c925b8482d05fb882d6b64e523653cae599e025f"
LAND = "files/a/0/6/5"
TEXTURES = "files/a/0/4/4"
MODELS = "files/data/mmodel/mmodel"
FINAL_ARCHIVES = {
    LAND: "92d7c1b6aeb0ac971acefd1f40e72654aee2cc1d171694645c046fdb428a0248",
    TEXTURES: "265746500ffdbcaebbc82bc82f949abbc7bfe24231815e4ef9e5500cfa46a5db",
}
ACTOR_HASHES = {
    864: "f965cad0757a835c11361a016a833d527fc677824196ee6268e3c0b37b246aac",
    865: "c5a57ab65630bf23ac3bd269b449befda86c8ffc900751f468fe8e5e05016ce7",
}
TERRAIN_EDITS = {452: 2, 480: 2, 481: 2, 482: 2, 483: 2, 484: 2,
                 618: 111, 619: 111}


def sha(data):
    return hashlib.sha256(data).hexdigest()


def guard_path(path):
    path = Path(os.path.abspath(path))
    if any(p.is_symlink() for p in (path, *path.parents)):
        raise ValueError(f"Symlinked input/output path forbidden: {path}")
    return path


def read(root, name, expected=None):
    safe_relative(name)
    path = guard_path(Path(root) / name)
    if not path.is_file() or path.stat().st_nlink != 1:
        raise ValueError(f"Missing, nonregular or hardlinked input: {name}")
    data = path.read_bytes()
    if expected is not None and sha(data) != expected:
        raise ValueError(f"Pinned input mismatch: {name}")
    return data


def write(root, name, data):
    safe_relative(name)
    path = guard_path(root / name)
    path.parent.mkdir(parents=True, exist_ok=True)
    # Ordinary writes deliberately use current mtimes. Never fake build freshness
    # with epoch timestamps or touch outputs to compensate for stale dependencies.
    path.write_bytes(data)


def publish_directory(source, destination):
    """Atomic no-replace publication, including a concurrently-created empty dir.

    Fail closed when the host lacks an atomic exclusive rename operation.
    No check/rename fallback is safe. Both directories must share a filesystem.
    """
    source, destination = map(guard_path, (source, destination))
    if sys.platform == "win32":
        # Windows rename, unlike POSIX rename, refuses an existing destination.
        os.rename(source, destination)
        return
    libc = ctypes.CDLL(None, use_errno=True)
    if sys.platform.startswith("linux") and hasattr(libc, "renameat2"):
        rename = libc.renameat2
        rename.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int,
                           ctypes.c_char_p, ctypes.c_uint]
        rename.restype = ctypes.c_int
        result = rename(-100, os.fsencode(source), -100, os.fsencode(destination), 1)
    elif sys.platform == "darwin" and hasattr(libc, "renamex_np"):
        rename = libc.renamex_np
        rename.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_uint]
        rename.restype = ctypes.c_int
        result = rename(os.fsencode(source), os.fsencode(destination), 4)
    else:
        raise OSError(errno.ENOTSUP, "Atomic no-replace directory publication unavailable")
    if result:
        error = ctypes.get_errno()
        raise OSError(error, os.strerror(error), str(destination))


def approved_contract():
    """Reviewed episode outputs/preimages, independent of any prepared-tree manifest."""
    return json.loads(read(TEMPLATES, "approved_deltas.json"))


def verify_native_contract(root, tree):
    from episode_source_inventory import native_names
    contract = approved_contract()
    names = native_names(root)
    if not set(contract).issubset(names):
        raise ValueError("Reviewed episode delta contains an unexpected native path")
    hashes = {}
    for name in names:
        before = read(root, name) if (root / name).exists() else None
        before_hash = sha(before) if before is not None else None
        if name in contract:
            if before_hash != contract[name]["before"]:
                raise ValueError(f"Reviewed baseline preimage mismatch: {name}")
            expected = contract[name]["after"]
        else:
            if before is None:
                raise ValueError(f"Unreviewed appended native source: {name}")
            expected = before_hash
        read(tree, name, expected)
        hashes[name] = expected
    return hashes


def native_edits(tree, recipe):
    outputs = {}
    for name, item in recipe.items():
        safe_relative(name)
        target = tree / name
        if item["before"] is None:
            if target.exists() or target.is_symlink():
                raise ValueError(f"Append-only source already exists: {name}")
            old = b""
        else:
            old = read(tree, name, item["before"])
        lines = old.decode("utf-8").splitlines(keepends=True)
        previous = len(lines) + 1
        for edit in reversed(item["edits"]):
            start, end = edit["start"], edit["end"]
            if not 0 <= start <= end < previous or end > len(lines):
                raise ValueError(f"Invalid/overlapping source edits: {name}")
            previous = start
            lines[start:end] = edit["lines"]
        result = "".join(lines).encode("utf-8")
        if sha(result) != item["after"]:
            raise ValueError(f"Source template digest mismatch: {name}")
        outputs[name] = result
    # Validate every preimage before the first mutation.
    for name, data in outputs.items():
        write(tree, name, data)
    return outputs


def make_compact(donor, packs, pins):
    def source(name, expected):
        return read(donor, name, expected)
    pack = {
        name: {member: read(packs / (name + "-pack"), member, expected)
               for member, expected in members.items()}
        for name, members in pins["packs"].items()
    }
    route = rgba_preview(pack["Route101"]["preview.png"], 320, 320)
    town = rgba_preview(pack["LittlerootTown"]["preview.png"], 320, 320)
    border = assets.border_pixels(
        json.loads(pack["Route101"]["cells.json"])["border"], pins["donor"], source)
    pixels = bytearray(512 * 512 * 4)
    for y in range(512):
        for x in range(512):
            image, stride, sx, sy = (
                (route, 320, x, y) if x < 320 and y < 320 else
                (town, 320, x, y - 320) if x < 320 else
                (border, 32, x % 32, y % 32))
            offset = (y * 512 + x) * 4
            src = (sy * stride + sx) * 4
            pixels[offset:offset + 4] = image[src:src + 4]
    image, palette, indices, unique = assets.atlas_for(pixels)
    tex, params = assets.texture(image, palette)
    commands, geometry = assets.commands_for(indices)
    model = assets.ensure_model_fits(container(b"BMD0", (assets.model(params, commands),)))
    texture = container(b"BTX0", (tex,))
    if sha(texture) != "4c50532743e4f12faead826b2afdb09f58265db94d7859916cc4cb83c51e93fc":
        raise ValueError("Compact texture mismatch")
    return model, texture, {
        "cells": {"route": 400, "town": 240, "border": 384},
        "atlas_image_bytes": len(image), "unique_tiles": len(unique),
        "geometry": geometry, "model_sha256": sha(model),
        "texture_sha256": sha(texture),
    }


def make_actors(root, donor):
    template = read(root, MODELS + "/mmodel_00000054.NSBTX")
    zig_frames = [1, 5, 1, 6, 0, 3, 0, 4, 2, 7, 2, 8, 2, 7, 2, 8]
    inputs = (
        (864, "pokemon/enemy_zigzagoon.png", "enemy_zigzagoon.pal",
         [(frame, suffix >= 13) for suffix, frame in enumerate(zig_frames, 1)],
         (32, 32), (0, 0)),
        (865, "misc/birchs_bag.png", "npc_2.pal", [(0, False)] * 16,
         (16, 16), (8, 16)),
    )
    outputs = {}
    for member, pic, pal, frames, size, anchor in inputs:
        result = assets.convert(
            template, read(donor, "graphics/object_events/pics/" + pic),
            read(donor, "graphics/object_events/palettes/" + pal),
            frames, size, anchor)
        if sha(result) != ACTOR_HASHES[member]:
            raise ValueError(f"Actor export mismatch: {member}")
        outputs[f"{MODELS}/mmodel_{member:08d}.NSBTX"] = result
    return outputs


def patch_archives(tree, model, texture):
    assets.ensure_model_fits(model)
    old_land, old_tex = (narc_members(read(tree, name)) for name in (LAND, TEXTURES))
    if len(old_land) != 679 or len(old_tex) != 109:
        raise ValueError("Unexpected travel archive member inventory")
    original = Land.decode(old_land[678])
    words = list(struct.unpack("<1024H", original.terrain))
    for index, value in TERRAIN_EDITS.items():
        if words[index] != 0x8000:
            raise ValueError(f"Unexpected Route101 terrain preimage: {index}")
        words[index] = value
    land = Land(original.marker, original.extra, struct.pack("<1024H", *words),
                original.props, model, original.collision).encode()
    outputs, ledgers = {}, {}
    for name, members, index, replacement in (
            (LAND, old_land, 678, land), (TEXTURES, old_tex, 108, texture)):
        changed = list(members)
        changed[index] = replacement
        packed = pack_narc(changed)
        actual = narc_members(packed)
        if len(actual) != len(members):
            raise ValueError(f"Archive member inventory changed: {name}")
        if name == LAND:
            # Recheck the real staged member, not a producer's size assertion.
            assets.ensure_model_fits(Land.decode(actual[678]).model)
        if any(
                member != actual[i] for i, member in enumerate(members) if i != index):
            raise ValueError(f"Unrelated archive member changed: {name}")
        if sha(packed) != FINAL_ARCHIVES[name]:
            raise ValueError(f"Final native archive mismatch: {name}")
        outputs[name] = packed
        ledgers[name] = {
            "changed_member": index,
            "before_members": [sha(member) for member in members],
            "after_members": [sha(member) for member in actual],
        }
    for name, data in outputs.items():
        write(tree, name, data)
    return outputs, ledgers


def prepare(root, donor, resources, lab_assets, actor, packs, output):
    root, donor, resources, lab_assets, actor, packs, output = map(
        guard_path, (root, donor, resources, lab_assets, actor, packs, output))
    if output.exists():
        raise ValueError("Episode output must be fresh")
    for input_path in (root, donor, resources, lab_assets, actor, packs):
        if output.is_relative_to(input_path) or input_path.is_relative_to(output):
            raise ValueError("Episode output overlaps an input")
    if subprocess.check_output(
            ["git", "-C", str(donor), "rev-parse", "HEAD"], text=True).strip() != DONOR_COMMIT:
        raise ValueError("Emerald donor revision mismatch")
    pins = json.loads(read(TEMPLATES, "asset_pins.json"))
    recipe = json.loads(read(TEMPLATES, "native_edits.json"))
    for group, directory in (("donor", donor), ("native", root)):
        for name, expected in pins[group].items():
            read(directory, name, expected)
    model, texture, compact = make_compact(donor, packs, pins)
    actors = make_actors(root, donor)
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".opening-episode-", dir=output.parent) as tmp:
        tree = Path(tmp) / "tree"
        prepare_travel(root, donor, resources, lab_assets, tree, actor=actor)
        baseline_models = {
            p.name: sha(read(tree, p.relative_to(tree).as_posix()))
            for p in (tree / MODELS).iterdir() if p.is_file()
        }
        changed = native_edits(tree, recipe)
        archives, ledgers = patch_archives(tree, model, texture)
        changed.update(archives)
        for name, data in actors.items():
            if (tree / name).exists():
                raise ValueError(f"New actor member already exists: {name}")
            write(tree, name, data)
            changed[name] = data
        for name, expected in baseline_models.items():
            read(tree, MODELS + "/" + name, expected)
        complete_inventory = verify_native_contract(root, tree)
        # No stale/private travel-report paths are published in the episode.
        (tree / "opening-travel.json").unlink()
        report = {
            "format": 1, "status": "source-only-full-opening-not-runtime-proof",
            "episode_definition": "route101-full-v8-r4-resume-safe-actors",
            # R2 provenance is historical, NOT evidence for this R3 output.
            "historical_r2_source_report_sha256":
                "064ee01b0d4d1c90494c5202c5b37418fd7f39ec848b9fec8a3d27f9661d1cb7",
            "donor_commit": DONOR_COMMIT,
            "base_commit": subprocess.check_output(
                ["git", "-C", str(root), "rev-parse", "HEAD"], text=True).strip(),
            "input_sha256": pins, "compact": compact,
            "producer_sha256": {
                name: sha(read(Path(__file__).parent, name))
                for name in ("prepare_emerald_episode.py", "episode_assets.py",
                             "episode_source_inventory.py", "episode_templates/asset_pins.json",
                             "episode_templates/native_edits.json",
                             "episode_templates/approved_deltas.json")
            },
            "episode_changes_sha256": {name: sha(data) for name, data in sorted(changed.items())},
            "archive_members": ledgers,
            "preserved_travel_overworld_sources": baseline_models,
            "native_input_sha256": complete_inventory,
            "retained_current_native_recipe": {
                "path": "files/fielddata/mapmatrix/map_matrix.mk",
                "reason": "Keep tracked incremental dependency fix; do not revert to historical V7 recipe",
            },
            "runtime_verified": False,
        }
        write(tree, "opening-episode.json",
              (json.dumps(report, indent=2, sort_keys=True) + "\n").encode())
        publish_directory(tree, output)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    for name in ("donor", "resources", "lab-assets", "actor", "packs", "output"):
        parser.add_argument("--" + name, required=True, type=Path,
                            help=("Parent of Route101-pack and LittlerootTown-pack, made by "
                                  "extract_emerald_lab.py --map" if name == "packs" else None))
    args = parser.parse_args()
    report = prepare(args.root, args.donor, args.resources, args.lab_assets,
                     args.actor, args.packs, args.output)
    print(json.dumps(report["episode_changes_sha256"], indent=2, sort_keys=True))


if __name__ == "__main__":
    main()