#!/usr/bin/env python3
"""Prepare a PRIVATE three-map door/edge-travel source tree from pinned exports.

Not an episode: the only rescue is the existing isolated debug-lab battle.
There is no Route 101 chase, grass, wild encounter or story hookup; optional
--actor binds the SHA-pinned Birch graphic to the existing lab actors.
Never use a valuable save or install this tree into the source checkout.
"""

import argparse
from collections import deque
import hashlib
import importlib
import json
import os
from pathlib import Path
import re
import shutil
import struct
import subprocess
import tempfile

from extract_emerald_lab import DONOR
from hgss_land import Land, narc_members
from prepare_lab_debug import install as install_native_lab
from stage_emerald_opening import (ARCHIVES, MAPS, MATRIX_DIR, STOCK_ARCHIVE_SHA256,
                                   load_assets)
from stage_lab_archives import pack_narc


# Source implementation and layout pins are deliberate. If a warp or matrix
# consumer changes, re-audit it before emitting different travel behavior.
SOURCE_SHA256 = {
    "include/constants/maps.h": "9ebf1f2f6110af509b830cc33f271d4b5d257f309212345a6bb4557321634adb",
    "src/data/map_headers.h": "737c837b717749df464dde7e6989f2c1da98d94ce31072fa2ef7918476ec7b05",
    "files/fielddata/script/scr_seq/scr_seq_0843_T20R0101.s": "dc71aa1bd469f53cc343855ddebfd93688550ba22d122e62b2a8bcd7795f7b24",
    "files/fielddata/script/scr_seq/scr_seq_0965_hoenn_reward.s": "492302362203461f6353391d20b894e2ea032892b2cd02f1fdaf3d5880dc810b",
    "files/msgdata/msg/msg_0829_hoenn_reward.gmm": "e351619e35574da46b7d36898ed8e31bb01fdae82c115dd53a6a90de12920d74",
    "expansion/baseline.json": "7a09bf41c5d437b1717ebc104495f44b0381250f843cd15ebead605b56828c7a",
    "scripts/prepare_lab_debug.py": "d449c426148d6f3d67c3468283f199738d7cf54456922645d91bd8015127abe1",
    "scripts/stage_lab_archives.py": "8f0316a36b1c732715847b4f8df5f5d3c07080d1540105829245f0b2a6aa4fd9",
    "include/constants/metatile_behavior.h": "daf592a2074c423b5649eba564cc37ea5acd224c5c86658dc1fe6b00160f509d",
    "include/map_header.h": "326f080515450519b49bf2b62b3cfba86490a63b305d712cba3d3a4b36ac1074",
    "include/map_matrix.h": "c1cd553900f25192df20aea00f2d754ab9468f4b8caa5c8335b3c2c297c01b95",
    "include/map_events_internal.h": "470228f46460147534f0604a45a86047c30510d8d95f92bd5f649a842f1c94c4",
    "files/fielddata/eventdata/zone_event.json.txt": "59f703a750ff6d42d3c1934e6f4f5ca060e3c82ff92faefbee6c57ebe6d57c33",
    "src/field/field_control.c": "7fa434cf9aeeb24810025051bbf87e4ac63ba7a96e24a032a9661796d01e05e5",
    "src/field_warp_tasks.c": "821846df9378984d14ff7334ed8855dbb7863800f4f551b623b98921629663d5",
    "src/map_events.c": "ca7ae292989ee6ee51888b56acc73848a3842c83a86ac9da02e18c08a609fa3b",
    "src/map_matrix.c": "05da574425b12321cce8432e51411e2fa0fb7d6fc316d8de83ed1f40cf774414",
    "src/terrain_attributes.c": "1201161ae43ab76c88e80f5e4850ce4441b0dd17c96facf11cd036fdcf6d726e",
    "src/map_header.c": "d99890d2ed3a58b04a6e561ebabe89e6e182862e131b8bafec1cb1372a3adc15",
    "src/scrcmd_c.c": "8da03cfda1f5471acf543d358917371d1d7ce598717895a6661bfbe177f6d293",
    "src/unk_02055BF0.c": "1df48bdbb6d231e815daf40aeb0477ed3364e49abef54bf7db1d1f542f1810d8",
    "asm/unk_02055BF0_data.s": "8baca72396cc28a6d1bf16ca503c9e980328a6543d702f55add1c1a2ff27c08b",
    "asm/overlay_01_021E90C0.s": "fd0ebb7c95416a42912838448eaea6e4a862661746f1aa370b282288c4d596cb",
    "asm/unk_02054648.s": "7aa63bed1f949cd858b79146ca594a2b05255da7ae525f8409678d068327a28e",
    "src/field/map_prop_manager.c": "b8459bb966f5fc4e8c291a54faca00f8eda5c2378960cc94b2240b66753c5aa1",
    "include/constants/global_fieldmap.h": "f33984744f2a73af7250e1a8d8e5d1e30748d633d28ace69f5a70b585f9705fe",
}
DONOR_MAP_SHA256 = {
    "LittlerootTown": "5bdd4157ca532864c0ba4bc8d0246e4b9e55c82e52b4d373d58270836ae9330f",
    "LittlerootTown_ProfessorBirchsLab": "13a03483c8fac9a7a6b169ce70bcdc389d86f652529e2b2bfb9cf29e306c5984",
    "Route101": "d66cd8eeed6b6f164ed28060de85262476e016b668a6d9b26cf434efdb1d69f9",
}
DONOR_LAYOUT_SHA256 = "5ac58ee1072862c937f82121a931b3315ccca3b5ae807f2a28a0e273957c2e4f"
EVENTS = "files/fielddata/eventdata/zone_event"
LAND = ARCHIVES["land"]
MAP_ID_MAX = 543
ACTOR_INSTALLER_SHA256 = "2b14933ffdcf83d84afb9fc94962a9a392b5a65db48745de5f88b5d293b17874"


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def verified_source(root, donor, resources, lab_assets):
    """Validate every consumed resource before creating the private tree."""
    root, donor, resources, lab_assets = map(Path, (root, donor, resources, lab_assets))
    revision = subprocess.check_output(
        ["git", "-C", str(donor), "rev-parse", "HEAD"], text=True).strip()
    if revision != DONOR:
        raise ValueError(f"Emerald source revision changed: {revision}; expected {DONOR}")
    maps = {}
    for name, expected in DONOR_MAP_SHA256.items():
        data = (donor / "data/maps" / name / "map.json").read_bytes()
        if sha256(data) != expected:
            raise ValueError(f"Emerald donor map.json drift: {name}")
        maps[name] = json.loads(data)
    layouts_bytes = (donor / "data/layouts/layouts.json").read_bytes()
    if sha256(layouts_bytes) != DONOR_LAYOUT_SHA256:
        raise ValueError("Emerald donor layout metadata drift")
    layouts = {item["id"]: item for item in json.loads(layouts_bytes)["layouts"]}
    if {name: (layouts[m["layout"]]["width"], layouts[m["layout"]]["height"])
        for name, m in maps.items()} != {
            "LittlerootTown": (20, 20),
            "LittlerootTown_ProfessorBirchsLab": (13, 13),
            "Route101": (20, 20),
        }:
        raise ValueError("Emerald map dimensions changed")
    for path, expected in SOURCE_SHA256.items():
        if sha256((root / path).read_bytes()) != expected:
            raise ValueError(f"Native source drift: {path}")
    if len(list((root / EVENTS).glob("*.json"))) != 491:
        raise ValueError("Native event indices drifted")
    if json.loads((root / "expansion/baseline.json").read_text())["capacities"]["map_count"] != 540:
        raise ValueError("Native map-count baseline drifted")
    native = (root / "include/constants/metatile_behavior.h").read_text()
    enum = native.split("enum TILE_BEHAVIOR {", 1)[1].split("};", 1)[0]
    symbols = [item.strip() for item in enum.split(",") if item.strip()]
    for name, number in (("TILE_BEHAVIOR_DOOR", 105),
                         ("TILE_BEHAVIOR_WARP_NORTH", 110),
                         ("TILE_BEHAVIOR_WARP_SOUTH", 111)):
        if symbols[number] != name:
            raise ValueError(f"Native warp behavior drift: {name}")
    # The lab's debug entrance and return are generated by the existing helper;
    # its archive staging is replaced with this independently verified overlay.
    lab_manifest, lab_files, _ = load_assets("lab", lab_assets)
    manifest_bytes = (resources / "manifest.json").read_bytes()
    resource = json.loads(manifest_bytes)
    if resource.get("status") != "resource-overlay-only-three-maps-unreachable":
        raise ValueError("Three-map input is not the conservative resource stage")
    if resource.get("expected_donor_revision") != DONOR:
        raise ValueError("Three-map input donor revision changed")
    if resource.get("asset_sha256", {}).get("lab") != {
            key: sha256(value) for key, value in lab_files.items()}:
        raise ValueError("Lab exporter assets differ from the resource stage")
    if resource.get("source_sha256") != {
            path: STOCK_ARCHIVE_SHA256[kind] for kind, path in ARCHIVES.items()}:
        raise ValueError("Stock resource provenance changed")
    for kind, path in ARCHIVES.items():
        if sha256((root / path).read_bytes()) != STOCK_ARCHIVE_SHA256[kind]:
            raise ValueError(f"Native source archive drift: {kind}")
    expected_paths = set(ARCHIVES[kind] for kind in ("areas", "textures", "land"))
    expected_paths.update(f"{MATRIX_DIR}/{entry[7]}" for entry in MAPS)
    if set(resource.get("output_sha256", {})) != expected_paths:
        raise ValueError("Three-map overlay file inventory differs")
    for kind, layout, map_id, area, land, matrix, events, name, _ in MAPS:
        binding = resource.get("bindings", {}).get(kind, {})
        if any(binding.get(key) != value for key, value in (
                ("donor_layout", layout), ("planned_map", map_id), ("area", area),
                ("texture", area), ("land", land), ("matrix", matrix),
                ("planned_events", events),
                ("terrain_origin", [9, 9] if kind == "lab" else [0, 0]))):
            raise ValueError(f"Three-map {kind} binding drift")
    for path, digest in resource["output_sha256"].items():
        if sha256((resources / path).read_bytes()) != digest:
            raise ValueError(f"Three-map resource differs from manifest: {path}")
    for kind in ("areas", "textures", "land"):
        path = ARCHIVES[kind]
        before, after = narc_members((root / path).read_bytes()), narc_members((resources / path).read_bytes())
        if before != after[:len(before)] or len(after) != len(before) + 3:
            raise ValueError(f"Original {kind} archive members changed")
    return maps, resource, sha256(manifest_bytes), lab_manifest


def donor_travel(maps):
    lab = maps["LittlerootTown_ProfessorBirchsLab"]
    town, route = maps["LittlerootTown"], maps["Route101"]
    lab_doors = lab["warp_events"]
    if [(w["x"], w["y"], w["dest_map"], str(w["dest_warp_id"])) for w in lab_doors] != [
            (6, 12, "MAP_LITTLEROOT_TOWN", "2"),
            (7, 12, "MAP_LITTLEROOT_TOWN", "2")]:
        raise ValueError("Emerald lab exits changed")
    town_doors = [w for w in town["warp_events"]
                  if w["dest_map"] == lab["id"]]
    if len(town_doors) != 1 or any(town_doors[0][key] != value for key, value in (
            ("x", 7), ("y", 16), ("dest_warp_id", "0"))):
        raise ValueError("Emerald lab-town return pairing changed")
    if {"map": route["id"], "offset": 0, "direction": "up"} not in town["connections"]:
        raise ValueError("Emerald town north connection changed")
    if {"map": town["id"], "offset": 0, "direction": "down"} not in route["connections"]:
        raise ValueError("Emerald Route 101 south connection changed")
    # Donor warp (6/7,12) translates by the model's independently checked (9,9)
    # origin. Outdoor positions are untranslated. x is aligned by the donor
    # connection's zero offset, not by a fabricated regional map matrix.
    return {
        "lab_exits": [[w["x"] + 9, w["y"] + 9] for w in lab_doors],
        "town_lab": [town_doors[0]["x"], town_doors[0]["y"]],
        "town_donor_north_row": 0, "route_donor_south_row": 19,
        "connection_offset": 0,
    }


def reachable(words, start):
    queue, seen = deque([tuple(start)]), {tuple(start)}
    while queue:
        x, z = queue.popleft()
        for next_x, next_z in ((x - 1, z), (x + 1, z), (x, z - 1), (x, z + 1)):
            position = (next_x, next_z)
            if (0 <= next_x < 20 and 0 <= next_z < 20 and position not in seen
                    and words[next_z * 32 + next_x] & 0x8000 == 0):
                seen.add(position)
                queue.append(position)
    return seen


def warp(x, z, map_id, destination):
    """zone_event.json.txt: four native little-endian u16 and one u32."""
    if not all(0 <= value <= 0xffff for value in (x, z, map_id, destination)):
        raise ValueError("Native warp event field width exceeded")
    return dict(x=x, z=z, header=map_id, anchor=destination, y=0)


def warp_bytes(event):
    return struct.pack("<4HI", event["x"], event["z"], event["header"],
                       event["anchor"], event["y"])


def open_travel_lands(root, resource, travel):
    """Edit only explicitly connected native door/edge tiles of three lands."""
    land_path = root / LAND
    members = narc_members(land_path.read_bytes())
    original = narc_members((resource / LAND).read_bytes())
    if members != original:
        raise ValueError("Land stage changed before door/edge authoring")
    words = {}
    for kind, _, _, _, member_id, _, _, _, _ in MAPS:
        land = Land.decode(members[member_id])
        if kind in ("lab", "town") and land.props != b"":
            raise ValueError(f"{kind}: native door-prop fallback must be re-audited")
        values = list(struct.unpack("<1024H", land.terrain))
        if set(values) - {0, 0x8000}:
            raise ValueError(f"{kind}: resource stage not conservatively sealed")
        words[kind] = values
    lab, town, route = words["lab"], words["town"], words["route"]
    doors = travel["lab_exits"]
    if doors != [[15, 21], [16, 21]] or travel["town_lab"] != [7, 16]:
        raise ValueError("Unexpected translated Emerald door position")
    if any(lab[z * 32 + x] != 0x8000 or lab[(z - 1) * 32 + x] != 0
           for x, z in doors):
        raise ValueError("Lab exits or interior approach changed")
    tx, tz = travel["town_lab"]
    if town[tz * 32 + tx] != 0x8000 or town[(tz + 1) * 32 + tx] != 0:
        raise ValueError("Town lab door or south approach changed")
    # Check BOTH pinned donor border columns and actual conservative terrain.
    # Native transition handling cannot enter beyond a sealed one-cell matrix:
    # north triggers on stepping onto z=1; south checks the blocked facing z=19
    # when stepping toward it from z=18. Both exterior perimeters stay sealed.
    lanes = [x for x in range(1, 18)
             if all(town[z * 32 + x + i] == 0 for i in (0, 1) for z in (1, 2))
             and all(route[z * 32 + x + i] == 0 for i in (0, 1) for z in (17, 18))
             and all(town[x + i] == 0x8000 and route[19 * 32 + x + i] == 0x8000
                     for i in (0, 1))]
    if lanes != [10]:
        raise ValueError(f"Donor-aligned conservative exterior corridor drift: {lanes}")
    xs = (lanes[0], lanes[0] + 1)
    if any((x, 2) not in reachable(town, (tx, tz + 1)) or
           town[3 * 32 + x] != 0 for x in xs):
        raise ValueError("No grass-free town approach from lab door to north connection")
    route_reach = reachable(route, (xs[0], 18))
    if not all((x, 17) in route_reach and route[16 * 32 + x] == 0
               for x in xs) or (8, 12) not in route_reach:
        raise ValueError("No grass-free Route 101 component for travel and return")
    changes = {"lab": [], "town": [], "route": []}

    def change(kind, x, z, old, new):
        index = z * 32 + x
        if words[kind][index] != old:
            raise ValueError(f"{kind} terrain precondition changed at {x},{z}")
        words[kind][index] = new
        changes[kind].append(dict(x=x, z=z, old=old, new=new))

    for x, z in doors:
        change("lab", x, z, 0x8000, 0x8000 | 105)  # Native DOOR, facing collision.
    change("town", tx, tz, 0x8000, 0x8000 | 105)
    for x in xs:
        change("town", x, 1, 0, 110)             # Native WARP_NORTH, step onto it.
        change("route", x, 18, 0, 111)           # Native WARP_SOUTH, face blocked rim.
    for kind, _, _, _, member_id, _, _, _, _ in MAPS:
        land = Land.decode(members[member_id])
        land.terrain = struct.pack("<1024H", *words[kind])
        members[member_id] = land.encode()
    packed = pack_narc(members)
    if narc_members(packed)[:676] != original[:676] or any(
            narc_members(packed)[member_id][:20] != original[member_id][:20]
            for _, _, _, _, member_id, _, _, _, _ in MAPS):
        raise ValueError("Land serialization altered stock members or section lengths")
    land_path.write_bytes(packed)
    return xs, changes


def replace_once(path, old, new):
    data = path.read_text()
    if data.count(old) != 1:
        raise ValueError(f"Expected unique native anchor in {path}: {old!r}")
    path.write_text(data.replace(old, new))


OUTDOOR_TRANSITION_BRANCH = (
    "    if ((otherID == MAP_LITTLEROOT_TOWN_TRAVEL && mapID == MAP_ROUTE_101_TRAVEL)\n"
    "        || (otherID == MAP_ROUTE_101_TRAVEL && mapID == MAP_LITTLEROOT_TOWN_TRAVEL)) {\n"
    "        var = 6; // Native generic fade: both private outdoor maps lack animated doors.\n"
    "    } else if (MapHeader_IsCave(otherID)) {"
)


def install_outdoor_transition(root):
    """Route only the private outdoor pair around vanilla's outdoor assert."""
    path = root / "src/unk_02055BF0.c"
    replace_once(path, '#include "constants/sndseq.h"\n',
                 '#include "constants/sndseq.h"\n#include "constants/maps.h"\n')
    replace_once(path, "    if (MapHeader_IsCave(otherID)) {",
                 OUTDOOR_TRANSITION_BRANCH)


def set_header_field(entry, field, value):
    entry, count = re.subn(r"(\." + field + r"\s*=\s*)[^,]+",
                           lambda match: match[1] + str(value), entry)
    if count != 1:
        raise ValueError(f"Native map header field changed: {field}")
    return entry


def install_headers(root):
    replace_once(root / "include/constants/maps.h",
                 "#define MAP_HOENN_LAB_DEBUG 540\n#define MAP_ID_MAX 541",
                 "#define MAP_HOENN_LAB_DEBUG 540\n"
                 "#define MAP_LITTLEROOT_TOWN_TRAVEL 541\n"
                 "#define MAP_ROUTE_101_TRAVEL 542\n#define MAP_ID_MAX 543")
    path = root / "src/data/map_headers.h"
    data = path.read_text()
    additions = []
    for template, new_name, area, matrix, event, category in (
            ("MAP_NEW_BARK", "MAP_LITTLEROOT_TOWN_TRAVEL", 107, 289, 492, "MAP_TYPE_CITY_TOWN"),
            ("MAP_ROUTE_29", "MAP_ROUTE_101_TRAVEL", 108, 290, 493, "MAP_TYPE_ROUTE")):
        match = re.search(r"\[" + template + r"\] = \{.*?\},", data, re.S)
        if match is None:
            raise ValueError(f"Missing native outdoor map template {template}")
        entry = match.group().replace("[" + template + "]", "[" + new_name + "]", 1)
        if not re.search(r"\.mapType\s*=\s*" + category + r",", entry):
            raise ValueError(f"Unexpected native outdoor header type {template}")
        for field, value in (
                ("wildEncounterBank", "ENCDATA_NA"),
                ("areaDataBank", area),
                ("matrixId", matrix),
                ("scriptsBank", "NARC_scr_seq_scr_seq_0139_EVERYWHERE_bin"),
                ("scriptHeaderBank", "NARC_scr_seq_scr_seq_0399_EVERYWHERE_hdr_bin"),
                ("msgBank", "NARC_msg_msg_0003_EVERYWHERE_bin"),
                ("eventsBank", event),
                ("followMode", "MAP_FOLLOWMODE_PREVENT"),
                ("bikeAllowed", "FALSE"),
                ("outgoingCalls", "FALSE"),
                ("incomingCalls", "FALSE"),
                ("radioSignal", "FALSE")):
            entry = set_header_field(entry, field, value)
        additions.append(entry)
    if data.count("\n};") != 1:
        raise ValueError("Native map table terminator changed")
    path.write_text(data.replace("\n};", "\n    " + "\n    ".join(additions) + "\n};"))
    baseline = root / "expansion/baseline.json"
    info = json.loads(baseline.read_text())
    if info["capacities"]["map_count"] != 541:
        raise ValueError("Debug-lab source map count changed")
    info["capacities"]["map_count"] = MAP_ID_MAX
    baseline.write_text(json.dumps(info, indent=2) + "\n")


def install_events(root, travel, xs):
    event_dir = root / EVENTS
    lab_path = event_dir / "491_HOENN_LAB_DEBUG.json"
    lab = json.loads(lab_path.read_text())
    if len(lab.get("objects", [])) != 3 or lab.get("warps") != []:
        raise ValueError("Native debug rescue/gift/return actors changed")
    lab["warps"] = [warp(x, z, 541, 0) for x, z in travel["lab_exits"]]
    lab_path.write_text(json.dumps(lab, indent=2) + "\n")
    tx, tz = travel["town_lab"]
    # Separate warp-trigger rows from destination anchors. Town WARP_NORTH
    # fires when stepped onto, even without a direction test at this point;
    # arrivals from Route must land on inert floor at z=2 (and a south-facing
    # generic entry may advance one further step to z=3). Route arrives at
    # inert z=17; its WARP_SOUTH is at z=18.
    town_warps = ([warp(tx, tz, 540, 0)]
                  + [warp(x, 1, 542, index + 2) for index, x in enumerate(xs)]
                  + [warp(x, 2, 542, index + 2) for index, x in enumerate(xs)])
    route_warps = ([warp(x, 18, 541, index + 3) for index, x in enumerate(xs)]
                   + [warp(x, 17, 541, index + 3) for index, x in enumerate(xs)])
    for number, name, events in ((492, "LITTLEROOT_TOWN_TRAVEL", town_warps),
                                  (493, "ROUTE_101_TRAVEL", route_warps)):
        path = event_dir / f"{number}_{name}.json"
        if path.exists():
            raise ValueError(f"Native event slot occupied: {number}")
        path.write_text(json.dumps(dict(bgs=[], objects=[], warps=events, coords=[]),
                                   indent=2) + "\n")
    if len(list(event_dir.glob("*.json"))) != 494:
        raise ValueError("Native event member count after append changed")
    return dict(lab=lab["warps"], town=town_warps, route=route_warps)


def prepare(root, donor, resources, lab_assets, output, actor=None):
    root, donor, resources, lab_assets, output = map(
        Path, (root, donor, resources, lab_assets, output))
    if output.exists() or output.is_symlink():
        raise ValueError("Refusing existing output")
    if output.resolve().is_relative_to(root.resolve()):
        raise ValueError("Travel output must be outside source tree")
    actor_bytes = None
    actor_source_audit = None
    birch_actor = None
    if actor is not None:
        birch_actor = importlib.import_module("prepare_birch_actor_probe")
        actor = Path(actor)
        actor_bytes = actor.read_bytes()
        if sha256(actor_bytes) != birch_actor.ACTOR_SHA256:
            raise ValueError("Unaudited Birch actor texture")
        installer = root / "scripts/prepare_birch_actor_probe.py"
        if (sha256(installer.read_bytes()) != ACTOR_INSTALLER_SHA256
                or Path(birch_actor.__file__).resolve() != installer.resolve()):
            raise ValueError("Birch actor installer drift")
        actor_source_audit = birch_actor.audit(root)
    maps, resource, resource_hash, _ = verified_source(root, donor, resources, lab_assets)
    travel = donor_travel(maps)
    source_commit = subprocess.check_output(
        ["git", "-C", str(root), "rev-parse", "HEAD"], text=True).strip()
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=f".{output.name}-", dir=output.parent) as directory:
        tree = Path(directory)
        archive = subprocess.Popen(["git", "-C", str(root), "archive", "HEAD"],
                                   stdout=subprocess.PIPE)
        try:
            subprocess.run(["tar", "-x", "-C", str(tree)], stdin=archive.stdout, check=True)
        finally:
            archive.stdout.close()
        if archive.wait():
            raise ValueError("Failed to extract pinned source archive")
        if actor_bytes is not None:
            # Audit the committed snapshot before any lab or travel mutations.
            if birch_actor.audit(tree) != actor_source_audit:
                raise ValueError("Archived native actor source differs from audited inputs")
        # Reuse the existing native battle/gift/Elm ingress/return preprocessor,
        # explicitly NEVER its simulated rescue-eligibility mode.
        debug = install_native_lab(tree, lab_assets, rescue_mode="native")
        if debug["eligibility_injected"] or debug["rescue_mode"] != "native":
            raise ValueError("Debug-lab helper changed rescue eligibility")
        elm = (tree / "files/fielddata/script/scr_seq/scr_seq_0843_T20R0101.s").read_text()
        injected = elm.split("scr_seq_T20R0101_000:", 1)[1].split(
            "HoennDebug_ElmOriginal:", 1)[0]
        if "SetVar 0x416e" in injected or injected.count("Warp 540, 0, 16, 19, 0") != 1:
            raise ValueError("Native debug Elm entry modified earned rescue state")
        # The one-map helper briefly stages only the lab. Replace every staged
        # archive and all three matrices with the verified THREE-map overlay.
        for path in resource["output_sha256"]:
            target = tree / path
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(resources / path, target)
        xs, changes = open_travel_lands(tree, resources, travel)
        install_headers(tree)
        events = install_events(tree, travel, xs)
        install_outdoor_transition(tree)
        actor_report = None
        if actor_bytes is not None:
            lab_event = tree / EVENTS / "491_HOENN_LAB_DEBUG.json"
            pre_actor = json.loads(lab_event.read_text())
            member = birch_actor.member_path()
            actor_paths = [birch_actor.SPRITES, birch_actor.TABLE, member,
                           Path(EVENTS) / "491_HOENN_LAB_DEBUG.json"]
            birch_actor.install_actor(tree, actor_bytes)
            after_actor = json.loads(lab_event.read_text())
            unchanged = json.loads(json.dumps(after_actor))
            for index in (0, 2):
                unchanged["objects"][index]["spriteId"] = pre_actor["objects"][index]["spriteId"]
            if unchanged != pre_actor:
                raise ValueError("Birch actor installation altered travel warps or native events")
            if (sorted(p.name for p in (tree / birch_actor.MMODEL).glob("mmodel_*"))
                    != sorted([*(p.name for p in (root / birch_actor.MMODEL).glob("mmodel_*")),
                               member.name])):
                raise ValueError("Birch actor installation changed original mmodel members")
            for original in (root / birch_actor.MMODEL).glob("mmodel_*"):
                if (tree / birch_actor.MMODEL / original.name).read_bytes() != original.read_bytes():
                    raise ValueError(f"Original Birch graphics member changed: {original.name}")
            actor_report = {
                "actor_input": str(actor.resolve()),
                "actor_sha256": birch_actor.ACTOR_SHA256,
                "installer_source_sha256": ACTOR_INSTALLER_SHA256,
                "source_audit_sha256": actor_source_audit,
                "archive_audit_sha256": actor_source_audit,
                "sprite": {"id": birch_actor.SPRITE_ID,
                           "constant": birch_actor.SPRITE_NAME, "flags": 0},
                "geometry_member": 266, "frame_table_member": 280,
                "texture_member": birch_actor.MEMBER,
                "native_mmodel_members_preserved": birch_actor.MEMBER,
                "actor_changes": [
                    {"event": 491, "id": pre_actor["objects"][index]["id"],
                     "x": pre_actor["objects"][index]["x"],
                     "z": pre_actor["objects"][index]["z"],
                     "script": pre_actor["objects"][index]["scriptId"]}
                    for index in (0, 2)
                ],
                "binding_files": [str(path) for path in actor_paths],
                "binding_sha256": {
                    str(path): sha256((tree / path).read_bytes()) for path in actor_paths
                },
                "travel_warps_preserved": pre_actor["warps"] == after_actor["warps"],
                "runtime_verified": False,
            }
        modifications = [
            LAND, ARCHIVES["areas"], ARCHIVES["textures"],
            *(f"{MATRIX_DIR}/{entry[7]}" for entry in MAPS),
            "include/constants/maps.h", "src/data/map_headers.h",
            "expansion/baseline.json",
            "src/unk_02055BF0.c",
            f"{EVENTS}/491_HOENN_LAB_DEBUG.json",
            f"{EVENTS}/492_LITTLEROOT_TOWN_TRAVEL.json",
            f"{EVENTS}/493_ROUTE_101_TRAVEL.json",
            "files/fielddata/script/scr_seq/scr_seq_0843_T20R0101.s",
            "files/fielddata/script/scr_seq/scr_seq_0965_hoenn_reward.s",
            "files/msgdata/msg/msg_0829_hoenn_reward.gmm",
        ]
        if actor_report is not None:
            modifications.extend(str(path) for path in actor_paths[:3])
        report = {
            "status": "private-three-map-native-door-edge-travel-unverified-runtime",
            "source_commit": source_commit,
            "source_sha256": SOURCE_SHA256,
            "donor_revision": DONOR, "donor_map_sha256": DONOR_MAP_SHA256,
            "donor_layout_sha256": DONOR_LAYOUT_SHA256,
            "resource_manifest_sha256": resource_hash,
            "resource_input_sha256": resource["output_sha256"],
            "source_archive_sha256": resource["source_sha256"],
            "bindings": {kind: resource["bindings"][kind] for kind, *_ in MAPS},
            "map_count": MAP_ID_MAX, "event_count": 494,
            "donor_coordinates": travel, "native_edge_lanes": list(xs),
            "native_edge_inset": {"town_north": 1, "route_south": 18},
            "events": events, "changed_terrain": changes,
            "eligibility_injected": False,
            "debug_elm_ingress": debug["entrance"],
            "debug_elm_return": debug["return_actor"],
            "warp_resolution_audit": {
                "script_warp": "ScrCmd_Warp reads and ignores the second script halfword; "
                "CallTask_ScriptWarp receives warpId=-1, so Elm ingress (16,19) "
                "and Elm return (6,12) preserve their explicit coordinates even "
                "though the lab now has target event warp 0",
                "event_warp": "FieldSystem_MapConnection passes the destination event "
                "anchor as warpId; sub_02052F94 reloads the target event and "
                "sets x/z from that event, not from the source event coordinates",
                "runtime_verified": False,
            },
            "transition_source_audit": {
                "source": "src/unk_02055BF0.c:sub_02055CD8",
                "private_outdoor_pair": [541, 542],
                "private_outdoor_transition_no": 6,
                "vanilla_outdoor_to_outdoor": "GF_ASSERT(FALSE) remains unchanged "
                "for every other map pair",
                "generic_callbacks": "sMapExitRoutines[6]=sub_02056004 "
                "(generic fade), sMapEnterRoutines[6]=sub_020565FC "
                "(generic entry); _020FC76C[6]=0",
                "door_callbacks": "field_control.c facing-DOOR transitionNo=1; "
                "sMapExitRoutines[1]=sub_02056040 and "
                "sMapEnterRoutines[1]=sub_020565FC; "
                "overlay_01_021E90C0.s has explicit no-map-prop exit "
                "return-TRUE and entry fade fallbacks",
                "land_props": "Both door maps have empty native land prop sections; "
                "prop scan uses fixed initialized slots and skips zero build models",
                "edge_arrival": "Town north triggers at z=1; Route arrival z=17 "
                "is inert before its z=18 south trigger. Route south triggers "
                "at z=18 facing blocked z=19; Town arrival z=2 is inert, "
                "and z=3 is also open for the generic south-facing entry movement",
                "runtime_verified": False,
            },
            "output_sha256": {path: sha256((tree / path).read_bytes()) for path in modifications},
            "matrix_u8_alias_audit": {
                "aliases": {"288": 32, "289": 33, "290": 34},
                "consumers": [
                    "MapHeader_GetMatrixId returns u16 to MapMatrix_Load/NARC member lookup; "
                    "the subsequently stored MapMatrix.matrix_id is u8",
                    "MapMatrix_GetMatrixId returns this u8; ov01_021F4704 passes it only to "
                    "MapMatrix_GetMapAltitude, whose matrix_id parameter is unused",
                    "map_matrix.c direct u8 comparisons for main matrix 0 and Safari 212 "
                    "do not match aliases 32-34",
                    "MapHeader_MapIsOnMainMatrix compares full u16 against main matrix 0",
                ],
                "runtime_consumer_verification": False,
            },
            "id_width_audit": {
                "map_header_index": "MAP_ID_MAX 543; indexed by u32 mapId with "
                "MapNumberBoundsCheck; no saved map-ID layout changed",
                "area": "MapHeader.areaDataBank u8; highest new ID 108",
                "matrix": "MapHeader.matrixId u16; highest new ID 290, correctly read "
                "for NARC lookup; MapMatrix.matrix_id and MapMatrix_GetMatrixId are "
                "u8 aliases audited above",
                "scripts_messages_events": "MapHeader.scriptsBank, msgBank and eventsBank "
                "u16; new event members 491-493",
                "warp_events": "WarpEvent x/z/header/anchor u16 and y u32; "
                "header is destination map ID, anchor is its event index",
                "region": "MapHeader.regionNo one bit; existing Johto value retained",
            },
            "limitations": [
                "PRIVATE travel authoring: no ROM build or native door/edge runtime test yet",
                "Native lab rescue/earned gift/receipt logic preserved; no Route101 chase or actor relocation",
                "Elm ingress and scientist return remain explicit disposable debug-only entry/exit",
                "Door/edge events are field transitions, not NPC teleports; Oldale connection stays sealed",
                "Only two donor-aligned ordinary-floor lanes link town to southern Route101 component",
                "All remaining exterior rim, doors, grass, ledges and unsupported cells remain blocked",
                "Exterior map headers clone native New Bark/Route29 flags and Johto map sections; "
                "no new region/save bits, production weather or authentic outdoor lighting validated",
                "Indoor area template remains used outdoors; simultaneous texture/prop/NPC VRAM "
                "headroom and transition allocations are unmeasured",
                "Warp event IDs and arrival positions are host-authored; live transition/"
                "facing/return/save behavior and matrix cache consumers still need native probing",
                "Generated source changes only the exact private Town541/Route542 outdoor pair "
                "to native generic transition 6; stock outdoor-to-outdoor assert remains",
                "No story installation or playable full campaign",
            ],
        }
        if actor_report is not None:
            report["status"] = (
                "private-three-map-native-door-edge-travel-with-birch-actor-unverified-runtime")
            report["actor"] = actor_report
            report["limitations"].append(
                "Optional Birch slot32/member863 actor binding is private and not "
                "runtime verified; standalone actor manifest is not a combined-tree manifest")
        (tree / "opening-travel.json").write_text(json.dumps(report, indent=2) + "\n")
        if output.exists() or output.is_symlink():
            raise ValueError("Refusing existing output")
        os.rename(tree, output)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--donor", type=Path, required=True)
    parser.add_argument("--resources", type=Path, required=True)
    parser.add_argument("--lab-assets", type=Path, required=True)
    parser.add_argument("--actor", type=Path,
                        help="Optional SHA-pinned Birch NSBTX for private lab actor binding")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(prepare(args.root, args.donor, args.resources,
                             args.lab_assets, args.output, actor=args.actor), indent=2))


if __name__ == "__main__":
    main()