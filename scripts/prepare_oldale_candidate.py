#!/usr/bin/env python3
"""Author an UNAPPROVED source-only Oldale overlay; never build/install a ROM.

Consumes an independently approved R5 source tree, not compiled banks. This
separate composer intentionally cannot satisfy the production episode contract.
No approval hashes or default episode generator behavior are changed.
"""
import argparse
from collections import deque
import heapq
import json
from pathlib import Path
import re
import struct
import subprocess
import tempfile

import episode_assets as assets
from export_emerald_outdoor_model import terrain
from export_lab_model import container, rgba_preview
from extract_emerald_lab import extract
from hgss_land import Land, flat_bdhc, narc_members
from prepare_emerald_episode import (
    DONOR_COMMIT, LAND, TEXTURES, guard_path, publish_directory, read, sha,
    verify_native_contract, write,
)
from prepare_emerald_opening import set_header_field, warp
from stage_lab_archives import pack_narc

AREAS = "files/a/0/4/2"
EVENTS = "files/fielddata/eventdata/zone_event/"
ROUTE_EVENT = EVENTS + "493_ROUTE_101_TRAVEL.json"
OLDALE_EVENT = EVENTS + "494_OLDALE_TOWN_TRAVEL.json"
MATRIX = "files/fielddata/mapmatrix/map_matrix/map_matrix_0291_OLDALE_TOWN.bin"
SCRIPT = "files/fielddata/script/scr_seq/scr_seq_0967_oldale_arrival.s"
MESSAGE = "files/msgdata/msg/msg_0830_oldale_arrival.gmm"
STATUS = "UNAPPROVED_SOURCE_CANDIDATE_PENDING_INDEPENDENT_PARENT_REVIEW"


def open_donor_grass_corridor(words, cells):
    """Minimum newly opened grass cells, then shortest ordinary walking path.

    R5 conservatively seals the donor's eastern grassy northbound corridor.
    Never translate ledges, collision, elevation, border or encounter tables.
    Only authentic (collision=0,elevation=3,behavior=2) grass may be opened.
    """
    by_position = {(c["x"], c["y"]): c for c in cells["cells"]}
    start, target = (10, 17), (10, 2)
    queue = [(0, 0, start)]
    scores, previous = {start: (0, 0)}, {start: None}
    while queue:
        changes, steps, position = heapq.heappop(queue)
        if scores[position] != (changes, steps):
            continue
        if position == target:
            break
        x, z = position
        for p in ((x-1, z), (x+1, z), (x, z-1), (x, z+1)):
            if not (0 < p[0] < 19 and 0 < p[1] < 19):
                continue
            c = by_position[p]
            value = words[p[1]*32+p[0]]
            grass = (c["collision"], c["elevation"], c["behavior"]) == (0, 3, 2)
            if value & 0x8000 and not grass:
                continue
            score = (changes + bool(value & 0x8000), steps + 1)
            if score < scores.get(p, (1025, 1025)):
                scores[p], previous[p] = score, position
                heapq.heappush(queue, (*score, p))
    if target not in previous:
        raise ValueError("No donor-grass-only Route101 corridor")
    path, edits = [target], []
    while previous[path[-1]] is not None:
        path.append(previous[path[-1]])
    for x, z in reversed(path):
        if words[z*32+x] & 0x8000:
            if words[z*32+x] != 0x8000:
                raise ValueError("Grass corridor would overwrite authored native behavior")
            edits.append(dict(x=x, z=z, before=0x8000, after=2,
                              donor=by_position[(x, z)]))
            words[z*32+x] = 2
    return edits


def route_path(words, start, finish, excluded=()):
    """Explicit four-neighbor terrain proof; objects may be excluded separately."""
    queue = deque([tuple(start)])
    previous = {tuple(start): None}
    excluded = set(excluded)
    while queue:
        x, z = queue.popleft()
        if (x, z) == tuple(finish):
            path = [(x, z)]
            while previous[path[-1]] is not None:
                path.append(previous[path[-1]])
            return list(reversed(path))
        for p in ((x-1, z), (x+1, z), (x, z-1), (x, z+1)):
            if (0 <= p[0] < 20 and 0 <= p[1] < 20 and p not in previous
                    and p not in excluded and not words[p[1]*32+p[0]] & 0x8000):
                previous[p] = (x, z)
                queue.append(p)
    raise ValueError(f"No conservative native path: {start} -> {finish}")


def compact_oldale(donor, pack):
    """Own Oldale pixels/atlas, never the Route101/Littleroot texture."""
    manifest = json.loads(read(pack, "manifest.json"))
    for name, expected in manifest["sources"].items():
        read(donor, name, expected)
    files = {name: read(pack, name, expected)
             for name, expected in manifest["outputs"].items()}
    cells = json.loads(files["cells.json"])
    preview = rgba_preview(files["preview.png"], 320, 320)
    border = assets.border_pixels(
        cells["border"], manifest["sources"], lambda name, digest: read(donor, name, digest))
    pixels = bytearray(512*512*4)
    for y in range(512):
        for x in range(512):
            source, stride, sx, sy = ((preview, 320, x, y) if x < 320 and y < 320
                                     else (border, 32, x % 32, y % 32))
            src, dest = (sy*stride+sx)*4, (y*512+x)*4
            pixels[dest:dest+4] = source[src:src+4]
    image, palette, indices, unique = assets.atlas_for(pixels)
    # Exact per-pixel BGR555/UV reconstruction, including the repeated border.
    for cell_id, tile in enumerate(assets.cells(pixels)):
        slot = indices[cell_id]
        for y in range(16):
            for x in range(16):
                offset = ((slot // assets.COLS * assets.SLOT + 1 + y) * assets.ATLAS_W
                          + slot % assets.COLS * assets.SLOT + 1 + x)
                if palette[image[offset]] != assets.rgba_to_555(tile[(y*16+x)*4:(y*16+x+1)*4]):
                    raise ValueError("Oldale atlas pixel/UV reconstruction differs")
    tex, params = assets.texture(image, palette)
    commands, geometry = assets.commands_for(indices)
    model = assets.ensure_model_fits(container(b"BMD0", (assets.model(params, commands),)))
    texture = container(b"BTX0", (tex,))
    attributes, unsupported = terrain(cells)
    return model, texture, list(struct.unpack("<1024H", attributes)), dict(
        donor=manifest, atlas_indices=indices, unique_tiles=len(unique),
        image_bytes=len(image), palette_colors=len(palette), geometry=geometry,
        pixel_uv_reconstruction="all 1024 cells, all 256 pixels per cell, exact BGR555",
        model_bytes=len(model), model_sha256=sha(model), texture_sha256=sha(texture),
        unsupported_terrain=unsupported,
    )


def overlay(tree, donor, pack, route_pack):
    changes = {}

    def put(name, data):
        before = read(tree, name) if (tree / name).exists() else None
        write(tree, name, data)
        changes[name] = dict(before=changes[name]["before"] if name in changes else
                             (sha(before) if before is not None else None), after=sha(data))

    def replace(name, old, new):
        source = read(tree, name).decode()
        if source.count(old) != 1:
            raise ValueError(f"Unique candidate preimage missing: {name}")
        put(name, source.replace(old, new).encode())

    for name in (OLDALE_EVENT, MATRIX, SCRIPT, MESSAGE):
        if (tree / name).exists():
            raise ValueError(f"Oldale append slot occupied: {name}")
    model, texture, town_words, compact = compact_oldale(donor, pack)
    archives = {name: narc_members(read(tree, name)) for name in (AREAS, TEXTURES, LAND)}
    if [len(archives[name]) for name in (AREAS, TEXTURES, LAND)] != [109, 109, 679]:
        raise ValueError("Expected exact approved R5 archive counts")
    route_land = Land.decode(archives[LAND][678])
    route_words = list(struct.unpack("<1024H", route_land.terrain))
    route_manifest = json.loads(read(route_pack, "manifest.json"))
    # Route101 extraction is otherwise a legacy unpinned resource utility.
    # Candidate authoring checks EVERY consumed source against the donor commit.
    for name, digest in route_manifest["sources"].items():
        actual = read(donor, name, digest)
        pinned = subprocess.check_output(["git", "-C", str(donor), "show", f"{DONOR_COMMIT}:{name}"])
        if name.endswith(".pal"):
            pinned = pinned.replace(b"\n", b"\r\n")
        if actual != pinned:
            raise ValueError(f"Route corridor donor source drift: {name}")
    route_cells = json.loads(read(route_pack, "cells.json", route_manifest["outputs"]["cells.json"]))
    grass_edits = open_donor_grass_corridor(route_words, route_cells)
    paths = {}
    for x in (10, 11):
        if any(route_words[z*32+x] != 0 for z in (1, 2, 3)):
            raise ValueError("Route north approach is not inert floor")
        if any(town_words[z*32+x] != 0 for z in (16, 17, 18)):
            raise ValueError("Oldale south approach is not inert floor")
        if route_words[x] != 0x8000 or town_words[19*32+x] != 0x8000:
            raise ValueError("Connected exterior rims must remain sealed")
        paths[f"route_{x}"] = route_path(route_words, (10, 17), (x, 2))
        paths[f"oldale_girl_{x}"] = route_path(town_words, (x, 17), (15, 11), {(16, 11)})
        route_words[32+x] = 110
        town_words[18*32+x] = 111
    route_land.terrain = struct.pack("<1024H", *route_words)
    town_land = Land(0x1234, b"", struct.pack("<1024H", *town_words), b"", model,
                     flat_bdhc(-256, -256, 64, 64)).encode()
    updated = {name: list(members) for name, members in archives.items()}
    updated[LAND][678] = route_land.encode()
    updated[LAND].append(town_land)
    updated[TEXTURES].append(texture)
    area = archives[AREAS][107]
    if len(area) != 8 or struct.unpack_from("<H", area, 2)[0] != 107:
        raise ValueError("Unexpected Littleroot area template")
    updated[AREAS].append(area[:2] + struct.pack("<H", 109) + area[4:])
    ledgers = {}
    for name, members in updated.items():
        packed = pack_narc(members)
        actual = narc_members(packed)
        if actual != members:
            raise ValueError("NARC serialization mismatch")
        for i, original in enumerate(archives[name]):
            if not (name == LAND and i == 678) and actual[i] != original:
                raise ValueError(f"Unrelated resource member changed: {name}:{i}")
        put(name, packed)
        ledgers[name] = dict(before_members=[sha(m) for m in archives[name]],
                             after_members=[sha(m) for m in actual])
    put(MATRIX, struct.pack("<5BH", 1, 1, 0, 0, 0, 679))

    route = json.loads(read(tree, ROUTE_EVENT))
    if route["warps"] != [warp(x, 19, 541, i+3) for _ in range(2)
                          for i, x in enumerate((10, 11))]:
        raise ValueError("R5 south event indices/preimages changed")
    route["warps"] += [warp(x, z, 543, i+2) for z in (1, 2) for i, x in enumerate((10, 11))]
    put(ROUTE_EVENT, (json.dumps(route, indent=2)+"\n").encode())
    town = dict(bgs=[], coords=[], objects=[
        dict(id=0, spriteId=8, movement=0, type=0, eventFlag=0, scriptId=1,
             facingDirection=2, param0=0, param1=0, param2=0, xRange=0, yRange=0,
             x=16, z=11, y=0)],
        # WARP_SOUTH uses standing row18, not the sealed facing rim at row19.
        warps=[warp(x, z, 542, i+6) for z in (18, 17) for i, x in enumerate((10, 11))])
    if not re.search(r"^#define SPRITE_GIRL3\s+8$", read(tree, "include/constants/sprites.h").decode(), re.M):
        raise ValueError("Stock female sprite mapping changed")
    put(OLDALE_EVENT, (json.dumps(town, indent=2)+"\n").encode())
    put(SCRIPT, b'#include "constants/scrcmd.h"\n.include "asm/macros/script.inc"\n.rodata\n\n'
        b'ScrDef Oldale_Girl\nScrDefEnd\n\nOldale_Girl:\nLockAll\nFacePlayer\n'
        b'NPCMsg 0\nWaitABPress\nCloseMsg\nReleaseAll\nEnd\n')
    put(MESSAGE, b'<?xml version="1.0"?>\n<body language="English">\n'
        b'<row id="msg_0830_00000" index="0"><attribute name="window_context_name">used</attribute>'
        b'<language name="English">I want to take a rest, so I\xe2\x80\x99m saving my\\nprogress.</language></row>\n'
        b'</body>\n')

    replace("include/constants/maps.h", "#define MAP_ID_MAX 543",
            "#define MAP_OLDALE_TOWN_TRAVEL 543\n#define MAP_ID_MAX 544")
    replace("include/constants/map_sections.h", "#define MAPSEC_ROUTE_101        236",
            "#define MAPSEC_ROUTE_101        236\n#define MAPSEC_OLDALE_TOWN      237")
    replace("src/trainer_memo.c",
            "mapsec == MAPSEC_LITTLEROOT_TOWN || mapsec == MAPSEC_ROUTE_101",
            "mapsec == MAPSEC_LITTLEROOT_TOWN || mapsec == MAPSEC_ROUTE_101 || mapsec == MAPSEC_OLDALE_TOWN")
    replace("files/msgdata/msg/msg_0279.gmm", "</body>",
            '<row id="msg_0279_00237" index="237">\n'
            '<attribute name="window_context_name">used</attribute>\n'
            '<language name="English">Oldale Town</language>\n</row>\n</body>')
    header_name = "src/data/map_headers.h"
    headers = read(tree, header_name).decode()
    entry = re.search(r"\[MAP_LITTLEROOT_TOWN_TRAVEL\] = \{.*?\},", headers, re.S).group()
    entry = entry.replace("[MAP_LITTLEROOT_TOWN_TRAVEL]", "[MAP_OLDALE_TOWN_TRAVEL]")
    for field, value in (("areaDataBank", 109), ("matrixId", 291), ("eventsBank", 494),
                         ("mapsec", "MAPSEC_OLDALE_TOWN"),
                         ("scriptsBank", "NARC_scr_seq_scr_seq_0967_oldale_arrival_bin"),
                         ("msgBank", "NARC_msg_msg_0830_oldale_arrival_bin"),
                         ("flyAllowed", "FALSE")):
        entry = set_header_field(entry, field, value)
    replace(header_name, "\n};", "\n    "+entry+"\n};")
    baseline = json.loads(read(tree, "expansion/baseline.json"))
    if baseline["capacities"]["map_count"] != 543:
        raise ValueError("R5 map capacity mismatch")
    baseline["capacities"]["map_count"] = 544
    put("expansion/baseline.json", (json.dumps(baseline, indent=2)+"\n").encode())
    replace("src/unk_02055BF0.c",
            "|| (otherID == MAP_ROUTE_101_TRAVEL && mapID == MAP_LITTLEROOT_TOWN_TRAVEL)) {",
            "|| (otherID == MAP_ROUTE_101_TRAVEL && mapID == MAP_LITTLEROOT_TOWN_TRAVEL)\n"
            "        || (otherID == MAP_ROUTE_101_TRAVEL && mapID == MAP_OLDALE_TOWN_TRAVEL)\n"
            "        || (otherID == MAP_OLDALE_TOWN_TRAVEL && mapID == MAP_ROUTE_101_TRAVEL)) {")
    # Preserve all four R5 indices/exclusions and the earned-rescue return gate.
    replace("src/map_events.c",
            "&& fieldSystem->mapEvents->warp_events[i].z == y)) {",
            "&& fieldSystem->mapEvents->warp_events[i].z == y)\n"
            "            || (fieldSystem->location->mapId == MAP_ROUTE_101_TRAVEL\n"
            "                && (i == 6 || i == 7) && x == 10 + (i - 6) && y == 2\n"
            "                && fieldSystem->mapEvents->warp_events[i].x == x\n"
            "                && fieldSystem->mapEvents->warp_events[i].z == y)\n"
            "            || (fieldSystem->location->mapId == MAP_OLDALE_TOWN_TRAVEL\n"
            "                && (i == 2 || i == 3) && x == 10 + (i - 2) && y == 17\n"
            "                && fieldSystem->mapEvents->warp_events[i].x == x\n"
            "                && fieldSystem->mapEvents->warp_events[i].z == y)) {")
    # Gate only the new north exit indices. The existing south NoSpace escape
    # remains rescue-only, and Oldale's south return is never gated.
    replace("src/map_events.c",
            "        if (x == fieldSystem->mapEvents->warp_events[i].x && y == fieldSystem->mapEvents->warp_events[i].z) {\n",
            "        if (x == fieldSystem->mapEvents->warp_events[i].x && y == fieldSystem->mapEvents->warp_events[i].z) {\n"
            "            if (fieldSystem->location->mapId == MAP_ROUTE_101_TRAVEL\n"
            "                && (i == 4 || i == 5)\n"
            "                && (GetScriptVar(Save_VarsFlags_Get(fieldSystem->saveData), VAR_HOENN_RESCUE_STATE) != HOENN_RESCUE_COMPLETE\n"
            "                    || GetScriptVar(Save_VarsFlags_Get(fieldSystem->saveData), VAR_HOENN_STARTER_RECEIVED) == 0)) {\n"
            "                continue;\n"
            "            }\n")
    return changes, dict(compact=compact, paths=paths, archive_members=ledgers,
                         route_donor=route_manifest, route_grass_corridor=grass_edits,
                         warps=dict(route=route["warps"], oldale=town["warps"]))


def prepare(root, episode, donor, output, *, author_unapproved=False):
    if author_unapproved is not True:
        raise ValueError("Explicit unapproved candidate authoring opt-in required")
    root, episode, donor, output = map(guard_path, (root, episode, donor, output))
    if output.exists():
        raise ValueError("Oldale candidate output must be fresh")
    for source in (root, episode, donor):
        if output.is_relative_to(source) or source.is_relative_to(output):
            raise ValueError("Candidate output overlaps an input")
    # Trust the independent production contract, never an input tree's manifest.
    before = verify_native_contract(root, episode)
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".oldale-unapproved-", dir=output.parent) as directory:
        temp = Path(directory)
        tree, pack = temp / "tree", temp / "OldaleTown-pack"
        tree.mkdir()
        archive = subprocess.Popen(["git", "-C", str(root), "archive", "HEAD"],
                                   stdout=subprocess.PIPE)
        try:
            subprocess.run(["tar", "-x", "-C", str(tree)], stdin=archive.stdout, check=True)
        finally:
            archive.stdout.close()
        if archive.wait():
            raise ValueError("Failed to extract baseline source archive")
        for name, digest in before.items():
            write(tree, name, read(episode, name, digest))
        extract(donor, pack, "OldaleTown")
        route_pack = temp / "Route101-pack"
        extract(donor, route_pack, "Route101")
        changes, audit = overlay(tree, donor, pack, route_pack)
        after = {}
        for name in sorted(set(before) | set(changes)):
            expected = changes[name]["after"] if name in changes else before[name]
            after[name] = sha(read(tree, name, expected))
        try:
            verify_native_contract(root, tree)
        except ValueError:
            pass
        else:
            raise ValueError("Candidate unexpectedly satisfies production approval")
        report = dict(
            format=1, status=STATUS, production_contract_accepted=False,
            donor_commit=DONOR_COMMIT, base_commit=subprocess.check_output(
                ["git", "-C", str(root), "rev-parse", "HEAD"], text=True).strip(),
            proposed_changes=changes, native_before_sha256=before, native_after_sha256=after,
            decoded=audit, additional_save_allocation=0, runtime_verified=False,
            producer_sha256={name: sha(read(Path(__file__).parent, name)) for name in (
                "prepare_oldale_candidate.py", "extract_emerald_lab.py", "episode_assets.py",
                "export_emerald_outdoor_model.py", "prepare_emerald_episode.py",
                "episode_templates/approved_deltas.json")},
            pending=["Independent parent source/contract approval", "Native compilation",
                     "Arrival/reciprocal traversal/NPC runtime, save, VRAM and revisit evidence"],
            exclusions=["Oldale transitions/visited flag/rival/Potion/other NPC scripts",
                        "Route102/Route103 and all Oldale interior doors remain sealed",
                        "No save format, bitfield, heap, VRAM, encounter or ABI changes"])
        write(tree, "oldale-candidate.json", (json.dumps(report, indent=2, sort_keys=True)+"\n").encode())
        publish_directory(tree, output)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("root", "episode", "donor", "output"):
        parser.add_argument("--"+name, type=Path, required=True)
    parser.add_argument("--author-unapproved-oldale", action="store_true", required=True)
    args = parser.parse_args()
    report = prepare(args.root, args.episode, args.donor, args.output,
                     author_unapproved=args.author_unapproved_oldale)
    print(json.dumps(dict(status=report["status"], proposed_changes=report["proposed_changes"]),
                     indent=2, sort_keys=True))


if __name__ == "__main__":
    main()