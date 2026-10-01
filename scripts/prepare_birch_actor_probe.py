#!/usr/bin/env python3
"""Prepare a disposable native-rescue lab tree with an unverified Birch actor.

No ROM build, repository binding, save modification or runtime validation.
Slot32 is an unused low ordinary-sprite gap, not a replacement stock NPC.
1050 is deliberately not allocated: max+1 is not a classification proof.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import tempfile

from prepare_lab_debug import prepare as prepare_lab, replace_once

SPRITE_ID = 32
SPRITE_NAME = "SPRITE_HOENN_BIRCH_PROBE"
MEMBER = 863
ACTOR_SHA256 = "5c699d10d769574fa1a7c4e0b0c4e79eee301d56db3353c702de4ee9d069cfdf"
MMODEL = Path("files/data/mmodel/mmodel")
EVENTS = Path("files/fielddata/eventdata/zone_event")
SCRIPTS = Path("files/fielddata/script/scr_seq")
SPRITES = Path("include/constants/sprites.h")
TABLE = Path("asm/overlay_01_sprite_data.s")
SENTINEL = ".short 0xFFFF, 0x0000, 0x000 | (63 << 10)"
ROW = f".short {SPRITE_NAME}, {MEMBER}, 0x000 | (0 << 10)"
PACKING = (
    "filesystem.mk", "files/data/mmodel/mmodel.mk",
    "files/data/mmodel/mmodel.json.txt", str(MMODEL / ".narcignore"),
    "tools/nitroarc/src/opmode_create.c", "tools/nitroarc/lib/nitroarc.c",
)
# Fingerprints bind the audit to actual source, not just a revision label.
# Broad source coverage also gates numeric/indirect SpriteID consumers.
PINS = {
    "members": (863, "93e9ae33f54035d6e5451e968d4bc0aaac66b782697655e26f11899ea467042a"),
    "consumers": (1263, "b75a2d833bc7667388767949515f2a4e52bd83ecae9f601f1ea2ffc454d6883b"),
    "events_scripts": (1457, "5947593c6d20eec6e8815c55817862e771dabeec2bbeb449f2b7c5f5b65429c5"),
    "packing": (6, "ff8d7427f2d539428e2443af2ef80b8fe7faf042336996f35c130412a761efb8"),
}
AUDIT = [
    "Slot32 absent from stock sprite constants, graphics table, events and object-graphics script assignments",
    "src/map_object.c:796 variable substitution is 101..117; slot32 bypasses it",
    "asm/overlay_01_021F72DC.s:17 selects ordinary fallback for32; follower interval is428..993",
    "asm/overlay_01_022053EC.s:220 special follower placeholders are415..420, not32",
    "asm/overlay_01_021F8D80.s:762 linear six-byte graphics lookup ends atFFFF; model is u16",
    "src/map_object.c:1946 callbacks selected by flags bits5..9; flags0 selects ordinary callbacks",
    "asm/overlay_01_021F944C.s:2014 descriptor flags>>10=0 selects geometry266/table280",
    "asm/overlay_01_021F944C.s:ov01_021F9D88/ov01_021FA524 cache searches compare IDs, not ID-sized arrays",
    "src/unk_02025534.c:240 resource lookup scans occupied entries by integer ID",
    "asm/overlay_01_021F8D80.s:854 passes member index to NARC without u8 narrowing",
    "src/filesystem.c:204 indexes BTAF by8*file_id; include/filesystem.h stores u16 member count",
    "mmodel.mk includes NSBTX; .narcignore excludes JSON; nitroarc implicit files are lexically sorted",
    "Fixed-width mmodel_00000863.NSBTX sorts after all863 original compiled members",
    "1050 not allocated: no claim that max+1 is ordinary; low unused gap avoids higher-ID classification assumptions",
]


def fingerprint(root, paths):
    digest = hashlib.sha256()
    for path in sorted(paths):
        digest.update(path.relative_to(root).as_posix().encode() + b"\0")
        digest.update(hashlib.sha256(path.read_bytes()).digest())
    return len(paths), digest.hexdigest()


def audit(root):
    members = sorted((root / MMODEL).glob("mmodel_*"))
    expected = list(range(MEMBER))
    if [int(p.stem.split("_")[1]) for p in members] != expected:
        raise ValueError("Native mmodel member count/order changed")
    allowed = {p.name for p in members} | {".gitignore", ".narcignore"}
    if {p.name for p in (root / MMODEL).iterdir()} != allowed:
        raise ValueError("Unexpected mmodel packing input (requires clean source tree)")
    groups = {
        "members": members,
        "consumers": [*root.glob("asm/**/*.s"), *root.glob("src/**/*.c"),
                      *root.glob("src/**/*.h"), *root.glob("include/**/*.h")],
        "events_scripts": [*(root / EVENTS).glob("*.json"), *(root / SCRIPTS).glob("*.s")],
        "packing": [root / p for p in PACKING],
    }
    hashes = {}
    for key, paths in groups.items():
        actual = fingerprint(root, paths)
        if actual != PINS[key]:
            raise ValueError(f"Unaudited {key} drift: expected {PINS[key]}, got {actual}")
        hashes[key] = actual[1]
    # Explicit readable safety checks supplement the source fingerprints.
    constants = dict(re.findall(r"^#define\s+(SPRITE_\w+)\s+(\d+)\s*$",
                                (root / SPRITES).read_text(), re.M))
    if SPRITE_ID in map(int, constants.values()) or SPRITE_NAME in constants:
        raise ValueError("Birch ordinary-sprite gap is occupied")
    table = (root / TABLE).read_text()
    if table.count(SENTINEL) != 1 or SPRITE_NAME in table:
        raise ValueError("Unexpected graphics table sentinel")
    for path in (root / EVENTS).glob("*.json"):
        for actor in json.loads(path.read_text()).get("objects", []):
            value = actor["spriteId"]
            if str(value) in (str(SPRITE_ID), SPRITE_NAME):
                raise ValueError("Native event consumes Birch slot")
    return hashes


def install_actor(tree, actor):
    """Only call on the freshly generated disposable native lab tree."""
    replace_once(tree / SPRITES, "#endif // POKEHEARTGOLD_CONSTANTS_SPRITES_H",
                 f"// PRIVATE PROBE ONLY: unused ordinary-sprite gap.\n"
                 f"#define {SPRITE_NAME} {SPRITE_ID}\n\n"
                 "#endif // POKEHEARTGOLD_CONSTANTS_SPRITES_H")
    replace_once(tree / TABLE, SENTINEL, ROW + "\n" + SENTINEL)
    member = tree / MMODEL / f"mmodel_{MEMBER:08d}.NSBTX"
    if member.exists():
        raise ValueError("Appended member already exists")
    member.write_bytes(actor)
    event = tree / EVENTS / "491_HOENN_LAB_DEBUG.json"
    data = json.loads(event.read_text())
    actors = data["objects"]
    if [(a["id"], a["x"], a["z"], a["scriptId"], a["spriteId"]) for a in actors] != [
        (0, 14, 17, 2, "SPRITE_ASSISTANTM"),
        (1, 18, 17, 4, "SPRITE_ASSISTANTM"),
        (2, 16, 17, 3, "SPRITE_ASSISTANTM"),
    ]:
        raise ValueError("Native lab actor anchors changed")
    for index in (0, 2):
        actors[index]["spriteId"] = SPRITE_NAME
    event.write_text(json.dumps(data, indent=2) + "\n")


def prepare(root, assets, actor, output):
    root, assets, actor, output = map(Path, (root, assets, actor, output))
    if output.exists():
        raise ValueError("Refusing existing output")
    if output.resolve().is_relative_to(root.resolve()):
        raise ValueError("Probe output must be outside source tree")
    data = actor.read_bytes()
    if hashlib.sha256(data).hexdigest() != ACTOR_SHA256:
        raise ValueError("Unaudited Birch texture")
    source_hashes = audit(root)
    clean = subprocess.run(
        ["git", "-C", str(root), "diff", "--quiet", "HEAD", "--", "src", "asm",
         "include", "files", "filesystem.mk", "tools/nitroarc"],
        capture_output=True)
    if clean.returncode:
        raise ValueError("Audited source must match git archive HEAD")
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".birch-probe-", dir=output.parent) as temp:
        tree = Path(temp) / "tree"
        lab = prepare_lab(root, assets, tree, rescue_mode="native")
        # prepare_lab uses git archive HEAD: check source bindings from the
        # committed snapshot as well as live inputs before editing the actor.
        for path in [SPRITES, TABLE, *(p.relative_to(root) for p in (root / MMODEL).iterdir())]:
            if (tree / path).read_bytes() != (root / path).read_bytes():
                raise ValueError("Archived native actor sources differ from audited inputs")
        install_actor(tree, data)
        report = {
            "status": "private-native-lab-birch-probe", "RuntimeVerified": False,
            "source_commit": lab["source_commit"], "source_audit_sha256": source_hashes,
            "sprite": {"id": SPRITE_ID, "constant": SPRITE_NAME, "flags": 0},
            "texture_member": MEMBER, "texture_sha256": ACTOR_SHA256,
            "geometry_member": 266, "frame_table_member": 280,
            "native_mmodel_members_preserved": MEMBER,
            "rescue_mode": "native", "eligibility_injected": False,
            "actor_changes": [
                {"event": 491, "id": 0, "x": 14, "z": 17, "script": 2},
                {"event": 491, "id": 2, "x": 16, "z": 17, "script": 3},
            ],
            "actor_binding_files": [str(SPRITES), str(TABLE), str(member_path()),
                                    str(EVENTS / "491_HOENN_LAB_DEBUG.json")],
            "lab_overlay": lab, "consumer_audit": AUDIT,
            "limitations": [
                "Disposable saves only; no repository or production binding installed",
                "1050 not allocated; slot32/member863 are private probe bindings only",
                "Doctor54, Elm graphics, Zigzagoon724->593 and all original event NPCs preserved",
                "Return scientist remains placeholder; lab-debug warning about both scientists is inherited",
                "No ROM build or runtime four-direction, walk, foot-placement or transition validation",
                "6KiB image size is not allocator/VRAM headroom proof; separate capacity audit required",
            ],
        }
        (tree / "birch-actor-probe.json").write_text(json.dumps(report, indent=2) + "\n")
        tree.rename(output)
    return report


def member_path():
    return MMODEL / f"mmodel_{MEMBER:08d}.NSBTX"


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--assets", type=Path, required=True, help="Existing lab Nitro export directory")
    parser.add_argument("--actor", type=Path, required=True, help="Verified private birch.nsbtx")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(prepare(args.root, args.assets, args.actor, args.output), indent=2))