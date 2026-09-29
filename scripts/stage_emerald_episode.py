#!/usr/bin/env python3
"""Stage a verified, source-only opening delta into a fresh external directory.

Does NOT modify a native build cache. Files are written with honest current
mtimes: callers copying this overlay into a cache must preserve those mtimes or
invalidate source dependencies, never restore epoch/old archive timestamps.
"""
import argparse
import json
from pathlib import Path
import subprocess
import tempfile

from episode_source_inventory import native_names, EPISODE_ADDITIONS
from prepare_emerald_episode import (
    guard_path, read, sha, write, publish_directory, verify_native_contract, approved_contract,
)


def stage(root, prepared, output):
    root, prepared, output = map(guard_path, (root, prepared, output))
    if output.exists() or any(output.is_relative_to(p) or p.is_relative_to(output)
                              for p in (root, prepared)):
        raise ValueError("Stage output must be fresh and separate from inputs")
    report = json.loads(read(prepared, "opening-episode.json"))
    if report.get("status") != "source-only-full-opening-not-runtime-proof":
        raise ValueError("Not an episode source manifest")
    revision = subprocess.check_output(
        ["git", "-C", str(root), "rev-parse", "HEAD"], text=True).strip()
    if subprocess.run(
            ["git", "-C", str(root), "diff", "--quiet", "HEAD", "--",
             "asm", "src", "include", "lib", "files", "sub", "tools",
             "heartgold.us", "soulsilver.us", "Makefile", "CMakeLists.txt",
             "binutils.mk", "common.mk", "config.mk", "filesystem.mk",
             "graphics_files_rules.mk", "platform.mk", "charmap.txt",
             "global.inc", "main.lsf", "rom.rsf", "scr_seq.sha1",
             "expansion/baseline.json"]).returncode:
        raise ValueError("Native baseline working files differ from committed source")
    if any((root / name).exists() or (root / name).is_symlink()
           for name in EPISODE_ADDITIONS):
        raise ValueError("Baseline already contains appended episode source inputs")
    inventory = report["native_input_sha256"]
    if set(inventory) != set(native_names(root)):
        raise ValueError("Unexpected native source path inventory")
    independently_verified = verify_native_contract(root, prepared)
    if inventory != independently_verified:
        raise ValueError("Prepared manifest differs from independently reviewed native contract")
    changes = {}
    preimages = {}
    for name, expected in inventory.items():
        data = read(prepared, name, expected)
        before = read(root, name) if (root / name).exists() else None
        if before != data:
            changes[name] = data
            preimages[name] = None if before is None else sha(before)
    if set(changes) != set(approved_contract()):
        raise ValueError("Source overlay differs from the complete reviewed delta")
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".episode-stage-", dir=output.parent) as tmp:
        tree = Path(tmp) / "overlay"
        tree.mkdir()
        for name, data in changes.items():
            write(tree, name, data)
        manifest = {
            "status": "source-only-overlay-not-installed",
            "base_commit": revision,
            "preimage_sha256": preimages,
            "payload_sha256": {name: sha(data) for name, data in changes.items()},
            "complete_native_input_sha256": inventory,
            "prepared_manifest_sha256": sha(read(prepared, "opening-episode.json")),
            "runtime_verified": False,
            "cache_policy": "current source mtimes; never epoch-extract over a build cache",
        }
        write(tree, "episode-overlay.json",
              (json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode())
        publish_directory(tree, output)
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--prepared", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(stage(args.root, args.prepared, args.output), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()