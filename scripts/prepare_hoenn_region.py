#!/usr/bin/env python3
"""Batch Emerald into a fresh, opt-in HeartGold source tree.

This is an experimental region import, NOT a claim of campaign completion.
Unsupported scripts and terrain are enumerated; gameplay testing is owner-led.
No ROM, save, SDK, compiler or license is consumed or published by this command.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import struct
import tempfile
import xml.etree.ElementTree as ET

from emerald_region_battles import BattleData
from emerald_region_data import DONOR_COMMIT, Emerald, split_chunks, terrain_word
from emerald_region_graphics import map_model, texture_pages
from emerald_region_scripts import Bank, Scripts
from hgss_land import Land, flat_bdhc, narc_members
from prepare_campaign_save import copy_sources, guard_path, publish, replace_once
from stage_lab_archives import pack_narc


PRESERVED = {
    "MAP_LITTLEROOT_TOWN_PROFESSOR_BIRCHS_LAB": (540, 491, 676, 962),
    "MAP_LITTLEROOT_TOWN": (541, 492, 677, 965),
    "MAP_ROUTE101": (542, 493, 678, 965),
    "MAP_OLDALE_TOWN": (543, 494, 679, 967),
}
AREAS, TEXTURES, LANDS = "files/a/0/4/2", "files/a/0/4/4", "files/a/0/6/5"
EVENTS = "files/fielddata/eventdata/zone_event"
MATRICES = "files/fielddata/mapmatrix/map_matrix"
SCRIPTS = "files/fielddata/script/scr_seq"
MESSAGES = "files/msgdata/msg"
FIRST_MAP, FIRST_AREA, FIRST_MATRIX, FIRST_EVENT = 544, 110, 292, 495
FIRST_SCRIPT, FIRST_MESSAGE = 970, 831
EMPTY_HEADER = 969


def json_bytes(value):
    return (json.dumps(value, indent=2, ensure_ascii=False) + "\n").encode()


def sprite(name):
    """Declared stock stand-ins, not a claim of imported Emerald actor artwork."""
    for fragment, number in (
            ("ITEM_BALL", 87), ("NURSE", 25), ("BIRCH", 32), ("SCIENTIST", 29),
            ("GIRL", 6), ("WOMAN", 12), ("LASS", 6), ("BOY", 3),
            ("FAT_MAN", 19), ("OLD_MAN", 17), ("OLD_WOMAN", 18)):
        if fragment in name:
            return number
    return 9


def object_event(local_id, graphic, script_id, x, z, flag=0, facing=1):
    return dict(id=local_id, spriteId=graphic, movement=0, type=0,
                eventFlag=flag, scriptId=script_id, facingDirection=facing,
                param0=0, param1=0, param2=0, xRange=0, yRange=0, x=x, z=z, y=0)


def event_size(event):
    return (16 + len(event["objects"]) * 32 + len(event["bgs"]) * 20
            + len(event["warps"]) * 12 + len(event["coords"]) * 16)


def ranges(values):
    """Maximal inclusive runs, keeping connection event records small."""
    runs = []
    for value in sorted(set(values)):
        if runs and value == runs[-1][1] + 1:
            runs[-1][1] = value
        else:
            runs.append([value, value])
    return runs


def connection_cells(layout, target, connection):
    """Donor offset means target coordinate = source coordinate - offset."""
    direction, offset = connection["direction"], connection["offset"]
    if direction not in ("up", "down", "left", "right"):
        return []
    horizontal = direction in ("up", "down")
    count = layout["width"] if horizontal else layout["height"]
    found = []
    for position in range(count):
        other = position - offset
        if horizontal:
            src = (position, 0 if direction == "up" else layout["height"] - 1)
            dst = (other, target["height"] - 2 if direction == "up" else 1)
        else:
            src = (0 if direction == "left" else layout["width"] - 1, position)
            dst = (target["width"] - 2 if direction == "left" else 1, other)
        if not (0 <= dst[0] < target["width"] and 0 <= dst[1] < target["height"]):
            continue
        # Crossing preserves collision; unsupported water/puzzle cells stay shut.
        usable = True
        for data, (x, y) in ((layout, src), (target, dst)):
            block = data["blocks"][y * data["width"] + x]
            word, _ = terrain_word(block, data["tiles"][block & 1023][1])
            if word & 0x8000:
                usable = False
        if usable:
            found.append((position, src, dst))
    return found


def prepare(episode, donor_root, output):
    episode, output = guard_path(episode), guard_path(output)
    donor = Emerald(donor_root)
    if output.exists() or any(output.is_relative_to(p) or p.is_relative_to(output)
                              for p in (episode, donor.root)):
        raise ValueError("Output must be a fresh directory outside both inputs")
    if "#define MAP_ID_MAX 544" not in (episode / "include/constants/maps.h").read_text():
        raise ValueError("Input must be the four-map opening/campaign-save checkpoint")
    if not (episode / "src/save_campaign.c").is_file():
        raise ValueError("Expanded campaign-save foundation is required")

    maps = list(donor.maps.values())
    added = [m for m in maps if m["id"] not in PRESERVED]
    map_ids = {name: info[0] for name, info in PRESERVED.items()}
    map_ids.update({m["id"]: FIRST_MAP + i for i, m in enumerate(added)})
    battle = BattleData(donor, episode)
    trainers = battle.trainers_data()
    encounters, encounter_banks, encounter_notes = battle.encounters_data()
    scripts = Scripts(donor, battle)
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".hoenn-region-", dir=output.parent) as temporary:
        tree = Path(temporary) / "source"
        tree.mkdir()
        original, _ = copy_sources(episode, tree)
        changes = {}

        def put(name, data):
            if isinstance(data, str):
                data = data.encode()
            path = tree / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
            changes[name] = hashlib.sha256(data).hexdigest()

        def edit(name, before, after):
            put(name, replace_once((tree / name).read_text(), before, after, name))

        archives = {name: narc_members((tree / name).read_bytes())
                    for name in (AREAS, TEXTURES, LANDS)}
        if [len(archives[n]) for n in (AREAS, TEXTURES, LANDS)] != [110, 110, 680]:
            raise ValueError("Unexpected opening resource counts")
        records, layouts, events, banks, terrain, warp_indices = {}, {}, {}, {}, {}, {}
        preserved_paths, preserved_scripts = {}, {}
        for m in maps:
            key = m["id"]
            layout = donor.layout(m["layout"])
            layouts[key] = layout
            records[key] = dict(
                name=m["name"], donor_id=key, native_map=map_ids[key],
                donor_source=f"data/maps/{m['name']}/map.json", layout=m["layout"],
                width=layout["width"], height=layout["height"],
                status="retained-opening-checkpoint" if key in PRESERVED else "batch-converted",
                gaps=[], connections=[], warps=[], interactions=[])
            if key in PRESERVED:
                info = PRESERVED[key]
                path = next((tree / EVENTS).glob(f"{info[1]:03}_*.json"))
                preserved_paths[key] = path.relative_to(tree).as_posix()
                events[key] = json.loads(path.read_text())
                for field in ("bgs", "objects", "warps", "coords"):
                    events[key].setdefault(field, [])
                preserved_scripts[key] = next((tree / SCRIPTS).glob(f"scr_seq_{info[3]:04}_*.s"))
                terrain[key] = list(struct.unpack("<1024H", Land.decode(archives[LANDS][info[2]]).terrain))
                # Only the original lab door maps onto an existing donor warp.
                warp_indices[key] = {}
                if key == "MAP_LITTLEROOT_TOWN_PROFESSOR_BIRCHS_LAB":
                    warp_indices[key] = {i: i for i in range(len(m.get("warp_events", [])))}
                elif key == "MAP_LITTLEROOT_TOWN":
                    for i, warp in enumerate(m.get("warp_events", [])):
                        if warp["dest_map"] == "MAP_LITTLEROOT_TOWN_PROFESSOR_BIRCHS_LAB":
                            warp_indices[key][i] = 0
                for i, warp in enumerate(m.get("warp_events", [])):
                    if i not in warp_indices[key]:
                        warp_indices[key][i] = len(events[key]["warps"])
                        events[key]["warps"].append(dict(x=warp["x"], z=warp["y"],
                                                        header=0, anchor=0, y=0))
                records[key]["gaps"].append("Other donor interactions/map callbacks remain outside the retained opening checkpoint")
            else:
                i = map_ids[key] - FIRST_MAP
                events[key] = dict(bgs=[], objects=[], warps=[], coords=[])
                banks[key] = Bank(scripts, FIRST_MESSAGE + i)
                terrain[key] = []
                unsupported = Counter()
                for block in layout["blocks"]:
                    word, behavior = terrain_word(block, layout["tiles"][block & 1023][1])
                    terrain[key].append(word)
                    if behavior is not None:
                        unsupported[behavior] += 1
                records[key]["unsupported_terrain"] = {f"0x{b:02x}": count for b, count in sorted(unsupported.items())}
                if unsupported:
                    records[key]["gaps"].append("Listed unsupported terrain is blocked, not approximated as ordinary floor")
                warp_indices[key] = {i: i for i, _ in enumerate(m.get("warp_events", []))}
                events[key]["warps"] = [dict(x=w["x"], z=w["y"], header=0, anchor=0, y=0)
                                        for w in m.get("warp_events", [])]

        def tile_index(key, x, y):
            return y * (32 if key in PRESERVED else layouts[key]["width"]) + x

        def set_tile(key, x, y, word):
            if not (0 <= x < layouts[key]["width"] and 0 <= y < layouts[key]["height"]):
                raise ValueError(f"Terrain coordinate outside donor map: {key} {x},{y}")
            terrain[key][tile_index(key, x, y)] = word

        def append_preserved_entry(key, label, body):
            path = preserved_scripts[key].relative_to(tree).as_posix()
            source = (tree / path).read_text()
            index = len(re.findall(r"^ScrDef\s", source, re.M)) + 1
            source = replace_once(source, "ScrDefEnd", f"ScrDef {label}\nScrDefEnd", path)
            put(path, source + f"\n{label}:\n{body}\n")
            return index

        # All static destination identities are allocated before any warp is emitted.
        for m in maps:
            key, event, record = m["id"], events[m["id"]], records[m["id"]]
            for i, warp in enumerate(m.get("warp_events", [])):
                if key in PRESERVED and (
                        key == "MAP_LITTLEROOT_TOWN_PROFESSOR_BIRCHS_LAB" or
                        (key == "MAP_LITTLEROOT_TOWN" and
                         warp["dest_map"] == "MAP_LITTLEROOT_TOWN_PROFESSOR_BIRCHS_LAB")):
                    continue
                target = warp["dest_map"]
                try:
                    index = int(warp["dest_warp_id"], 0)
                    anchor = warp_indices[target][index]
                    destination = donor.maps[target]["warp_events"][index]
                    if (not 0 <= warp["x"] < layouts[key]["width"] or
                            not 0 <= warp["y"] < layouts[key]["height"] or
                            not 0 <= destination["x"] < layouts[target]["width"] or
                            not 0 <= destination["y"] < layouts[target]["height"]):
                        raise KeyError("off-layout warp")
                except (ValueError, KeyError):
                    # Preserve this warp's source coordinate as an inbound anchor,
                    # but seal its outgoing tile. No fake destination/teleport.
                    event["warps"][warp_indices[key][i]].update(header=map_ids[key],
                                                               anchor=warp_indices[key][i])
                    if (0 <= warp["x"] < layouts[key]["width"] and
                            0 <= warp["y"] < layouts[key]["height"]):
                        set_tile(key, warp["x"], warp["y"], 0x8000)
                    record["warps"].append(dict(donor_index=i, status="blocked",
                                                reason="dynamic, off-layout or unresolved destination", donor=warp))
                    continue
                event["warps"][warp_indices[key][i]].update(header=map_ids[target], anchor=anchor)
                set_tile(key, warp["x"], warp["y"], 103)  # native step-on warp panel
                record["warps"].append(dict(donor_index=i, native_index=warp_indices[key][i],
                                            target=target, anchor=anchor, status="converted"))

            for c, connection in enumerate(m.get("connections") or []):
                target = connection["map"]
                if target not in layouts:
                    record["connections"].append(dict(donor=connection, status="unresolved"))
                    continue
                if key in PRESERVED and target in PRESERVED:
                    record["connections"].append(dict(donor=connection, status="retained-opening"))
                    continue
                cells = connection_cells(layouts[key], layouts[target], connection)
                if not cells:
                    record["connections"].append(dict(donor=connection, status="blocked",
                        reason="no supported ground crossing; dive/surface/water/puzzle semantics not implemented"))
                    continue
                direction, offset = connection["direction"], connection["offset"]
                body = ["LockAll", "GetPlayerCoords 0x8000, 0x8001"]
                axis = "0x8000" if direction in ("up", "down") else "0x8001"
                if offset:
                    body.append(f"{'SubVar' if offset > 0 else 'AddVar'} {axis}, {abs(offset)}")
                if direction in ("up", "down"):
                    body.append(f"SetVar 0x8001, {layouts[target]['height'] - 2 if direction == 'up' else 1}")
                else:
                    body.append(f"SetVar 0x8000, {layouts[target]['width'] - 2 if direction == 'left' else 1}")
                facing = dict(up=0, down=1, left=2, right=3)[direction]
                body += [f"Warp {map_ids[target]}, 0, 0x8000, 0x8001, {facing}", "ReleaseAll", "End"]
                script_id = (append_preserved_entry(key, f"HoennExit{map_ids[key]}_{c}", "\n".join(body))
                             if key in PRESERVED else banks[key].raw("\n".join(body)))
                for position, (x, y), _ in cells:
                    set_tile(key, x, y, 0)
                    # Open only matching donor-passable cells, never a cliff/wall.
                    if key in PRESERVED:
                        ix = min(max(x, 1), layouts[key]["width"] - 2)
                        iy = min(max(y, 1), layouts[key]["height"] - 2)
                        block = layouts[key]["blocks"][iy * layouts[key]["width"] + ix]
                        word, _ = terrain_word(block, layouts[key]["tiles"][block & 1023][1])
                        if not word & 0x8000:
                            set_tile(key, ix, iy, word)
                for low, high in ranges([p for p, _, _ in cells]):
                    horizontal = direction in ("up", "down")
                    x = low if horizontal else (0 if direction == "left" else layouts[key]["width"] - 1)
                    y = (0 if direction == "up" else layouts[key]["height"] - 1) if horizontal else low
                    event["coords"].append(dict(scriptId=script_id, x=x, z=y,
                        w=high-low+1 if horizontal else 1, h=1 if horizontal else high-low+1,
                        y=0, val=0, var=0))
                record["connections"].append(dict(donor=connection, status="converted-ground",
                                                   crossing_cells=len(cells), script_id=script_id))

        # Map-local NPC/sign conversion; story callbacks/triggers remain explicit gaps.
        for m in added:
            key, event, bank, record = m["id"], events[m["id"]], banks[m["id"]], records[m["id"]]
            for index, obj in enumerate(m.get("object_events", []), 1):
                if obj.get("type", "object") != "object" or "graphics_id" not in obj:
                    record["gaps"].append(f"Unsupported object template {index}: {obj.get('type')}")
                    continue
                raw_flag = obj.get("flag", "0")
                try:
                    flag = int(raw_flag, 0)
                except (ValueError, TypeError):
                    flag = scripts.names.get(raw_flag, -1)
                if flag != 0 and not 0x20 <= flag < 0x960:
                    record["gaps"].append(f"Object {index} uses unsupported flag {raw_flag}")
                    continue
                if not (0 <= obj["x"] < layouts[key]["width"] and
                        0 <= obj["y"] < layouts[key]["height"]):
                    record["gaps"].append(f"Object {index} starts outside the static layout")
                    continue
                script_id = bank.interaction(obj.get("script", "0x0"), face=True, object_flag=flag)
                facing = next((d for s, d in (("UP", 0), ("DOWN", 1), ("LEFT", 2), ("RIGHT", 3))
                               if obj.get("movement_type", "").endswith("_" + s)), 1)
                event["objects"].append(object_event(
                    index, sprite(obj["graphics_id"]), script_id, obj["x"], obj["y"], flag, facing))
            for bg in m.get("bg_events", []):
                if bg["type"] != "sign":
                    record["gaps"].append("Background event not converted: " + bg["type"])
                    continue
                script_id = bank.interaction(bg["script"])
                event["bgs"].append(dict(scriptId=script_id, type=0, x=bg["x"], z=bg["y"], y=0, dir=0))
            if m.get("coord_events"):
                record["gaps"].append(f"{len(m['coord_events'])} donor story-coordinate triggers not converted")
            record["gaps"].append("Donor map-load/frame callbacks, dynamic object movement and regional new-game initialization not converted")
            record["interactions"] = bank.coverage
            # A test-only return, not a story bypass presented as legitimate progress.
            occupied = {(o["x"], o["z"]) for o in event["objects"]}
            triggers = {(w["x"], w["z"]) for w in event["warps"]}
            layout = layouts[key]
            spawn = None
            for y in range(2, layout["height"] - 2):
                for x in range(1, layout["width"] - 1):
                    positions = ((x, y), (x, y + 1))
                    if any(p in occupied or p in triggers for p in positions):
                        continue
                    if all(terrain[key][tile_index(key, *p)] == 0 for p in positions):
                        spawn = (x, y)
                        break
                if spawn:
                    break
            if spawn:
                msg = bank.message("Test travel: return to Oldale?\\nThis does not change story progress.")
                sid = bank.raw(f"LockAll\nFacePlayer\nNPCMsg {msg}\nYesNo 0x8000\nCloseMsg\n"
                               f"Compare 0x8000, 0\nGoToIfNe ReturnCancel\n"
                               f"Warp 543, 0, 10, 16, 0\nReturnCancel:\nReleaseAll\nEnd")
                event["objects"].append(object_event(250, 29, sid, *spawn))
                record["test_entry"] = [spawn[0], spawn[1] + 1]
            else:
                record["test_entry"] = None
                record["gaps"].append("No safe ordinary-ground test entry; use supported native entrances only")
            if event_size(event) >= 0x800:
                raise ValueError(f"Native event buffer exceeded: {key} ({event_size(event)} bytes)")

        header_entries, area_ids, wild_ids = [], [], []
        put(f"{SCRIPTS}/scr_seq_{EMPTY_HEADER:04}_hoenn_empty_hdr.s", ".rodata\n.byte 0\n")
        area_template = archives[AREAS][107]
        for i, m in enumerate(added):
            key, layout, record = m["id"], layouts[m["id"]], records[m["id"]]
            texture, mapping, pages, stats = texture_pages([t[0] for t in layout["tiles"].values()])
            texture_index, area_index = len(archives[TEXTURES]), len(archives[AREAS])
            archives[TEXTURES].append(texture)
            archives[AREAS].append(area_template[:2] + struct.pack("<H", texture_index) + area_template[4:])
            area_ids.append(area_index)
            wild_ids.append(encounter_banks.get(key, 65535))
            model_ids = []
            model_max = 0
            for cx, cy in split_chunks(layout["width"], layout["height"]):
                words, tiles = [], []
                for y in range(32):
                    for x in range(32):
                        dx, dy = cx * 32 + x, cy * 32 + y
                        inside = dx < layout["width"] and dy < layout["height"]
                        block = (layout["blocks"][dy * layout["width"] + dx] if inside else
                                 layout["border"][(dy % 2) * 2 + dx % 2])
                        tiles.append(layout["tiles"][block & 1023][0])
                        words.append(terrain[key][dy * layout["width"] + dx] if inside else 0x8000)
                model = map_model(tiles, mapping, pages)
                model_max = max(model_max, len(model))
                model_ids.append(len(archives[LANDS]))
                archives[LANDS].append(Land(
                    0x1234, b"", struct.pack("<1024H", *words), b"", model,
                    flat_bdhc(-256, -256, 256, 256)).encode())
            matrix_id, event_id = FIRST_MATRIX + i, FIRST_EVENT + i
            script_id, message_id = FIRST_SCRIPT + i, FIRST_MESSAGE + i
            put(f"{MATRICES}/map_matrix_{matrix_id:04}_HOENN.bin",
                struct.pack("<5B", (layout["width"] + 31) // 32,
                            (layout["height"] + 31) // 32, 0, 0, 0)
                + struct.pack(f"<{len(model_ids)}H", *model_ids))
            # z-prefix avoids reordering existing 3-digit event names at ID 1000.
            put(f"{EVENTS}/z{event_id:04}_HOENN.json", json_bytes(events[key]))
            put(f"{SCRIPTS}/scr_seq_{script_id:04}_hoenn.s", banks[key].assembly())
            put(f"{MESSAGES}/msg_{message_id:04}_hoenn.gmm", banks[key].gmm())
            outdoors = m["map_type"] in ("MAP_TYPE_CITY", "MAP_TYPE_TOWN", "MAP_TYPE_ROUTE", "MAP_TYPE_OCEAN_ROUTE")
            map_type = ("MAP_TYPE_ROUTE" if outdoors else "MAP_TYPE_CAVE"
                        if m["map_type"] == "MAP_TYPE_UNDERGROUND" else "MAP_TYPE_INTERIOR")
            header_entries.append(f"""    [MAP_HOENN_{key.removeprefix("MAP_")}] = {{
        .wildEncounterBank = ENCDATA_NA, .areaDataBank = 0,
        .moveModelBank = 15, .worldMapX = 0, .worldMapY = 0,
        .matrixId = {matrix_id}, .scriptsBank = {script_id},
        .scriptHeaderBank = {EMPTY_HEADER}, .msgBank = {message_id},
        .dayMusicId = SEQ_GS_T_WAKABA, .nightMusicId = SEQ_GS_T_WAKABA,
        .eventsBank = {event_id}, .mapsec = MAPSEC_HOENN_REGION,
        .areaIcon = 2, .momCallIntroParam = 0, .regionNo = MAP_REGION_JOHTO,
        .weather = 0, .mapType = {map_type}, .cameraType = 0,
        .followMode = MAP_FOLLOWMODE_PREVENT, .battleBg = BATTLE_BG_GENERAL,
        .bikeAllowed = FALSE, .runningAllowed_Unused = TRUE,
        .escapeRopeAllowed = FALSE, .flyAllowed = FALSE,
        .outgoingCalls = FALSE, .incomingCalls = FALSE, .radioSignal = FALSE,
    }},""")
            record.update(native_area=area_index, native_matrix=matrix_id,
                          native_event=event_id, native_script=script_id,
                          native_message=message_id, native_land=model_ids,
                          graphics=dict(stats, max_model_bytes=model_max),
                          event_bytes=event_size(events[key]))

        # Native-input test travel, available without editing a save or inventing
        # quest outcomes. Only maps with a supported empty-ground landing qualify.
        directory = sorted((r for r in records.values() if r.get("test_entry")),
                           key=lambda r: r["name"])
        oldale_messages = f"{MESSAGES}/msg_0830_oldale_arrival.gmm"
        xml = ET.fromstring((tree / oldale_messages).read_bytes())
        next_message = max(int(row.attrib["index"]) for row in xml.findall("row")) + 1

        def directory_message(text):
            nonlocal next_message
            index = next_message
            next_message += 1
            row = ET.SubElement(xml, "row", id=f"msg_0830_{index:05}", index=str(index))
            ET.SubElement(row, "attribute", name="window_context_name").text = "used"
            ET.SubElement(row, "language", name="English").text = text
            return index

        intro = directory_message("Hoenn test travel.\\nStory progress is not changed.\\r"
                                  "Choose a map to inspect.\\nThe assistant there brings you back.")
        if intro >= 256:
            raise ValueError("Test directory introduction exceeds NPCMsg's byte operand")
        next_page = directory_message("Next page")
        previous_page = directory_message("Previous page")
        cancel = directory_message("Cancel")
        labels = {}
        for record in directory:
            readable = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", record["name"]).replace("_", " ")
            labels[record["native_map"]] = directory_message(f"{record['native_map']}: {readable[:22]}")
        body = ["LockAll", "FacePlayer", f"NPCMsg {intro}", "WaitABPress", "CloseMsg"]
        pages_count = (len(directory) + 7) // 8
        for page in range(pages_count):
            choices = directory[page * 8:page * 8 + 8]
            body += [f"HoennDirectoryPage{page}:", "MenuInit 1, 1, 0, 1, 0x8000"]
            for choice, record in enumerate(choices):
                body.append(f"MenuItemAdd {labels[record['native_map']]}, 255, {choice}")
            if page + 1 < pages_count:
                body.append(f"MenuItemAdd {next_page}, 255, 247")
            if page > 0:
                body.append(f"MenuItemAdd {previous_page}, 255, 248")
            body += [f"MenuItemAdd {cancel}, 255, 249", "MenuExec"]
            for choice, record in enumerate(choices):
                body += [f"Compare 0x8000, {choice}",
                         f"GoToIfEq HoennDirectoryTravel{record['native_map']}"]
            if page + 1 < pages_count:
                body += ["Compare 0x8000, 247", f"GoToIfEq HoennDirectoryPage{page + 1}"]
            if page > 0:
                body += ["Compare 0x8000, 248", f"GoToIfEq HoennDirectoryPage{page - 1}"]
            body.append("GoTo HoennDirectoryClose")
        for record in directory:
            x, y = record["test_entry"]
            body += [f"HoennDirectoryTravel{record['native_map']}:",
                     f"Warp {record['native_map']}, 0, {x}, {y}, 0",
                     "ReleaseAll", "End"]
        body += ["HoennDirectoryClose:", "ReleaseAll", "End"]
        sid = append_preserved_entry("MAP_OLDALE_TOWN", "HoennTestDirectory", "\n".join(body))
        events["MAP_OLDALE_TOWN"]["objects"].append(object_event(250, 29, sid, 10, 15))
        put(oldale_messages, ET.tostring(xml, encoding="utf-8", xml_declaration=True))

        for key, info in PRESERVED.items():
            event = events[key]
            if event_size(event) >= 0x800:
                raise ValueError("Preserved event buffer overflow: " + key)
            put(preserved_paths[key], json_bytes(event))
            land = Land.decode(archives[LANDS][info[2]])
            land.terrain = struct.pack("<1024H", *terrain[key])
            archives[LANDS][info[2]] = land.encode()
        for name, members in archives.items():
            packed = pack_narc(members)
            if narc_members(packed) != members:
                raise ValueError("Archive serialization mismatch: " + name)
            put(name, packed)
        definitions = "\n".join(f"#define MAP_HOENN_{m['id'].removeprefix('MAP_')} {map_ids[m['id']]}"
                                for m in added)
        edit("include/constants/maps.h", "#define MAP_ID_MAX 544",
             definitions + f"\n#define MAP_ID_MAX {FIRST_MAP + len(added)}")
        edit("include/constants/map_sections.h", "#define MAPSEC_OLDALE_TOWN      237",
             "#define MAPSEC_OLDALE_TOWN      237\n#define MAPSEC_HOENN_REGION     238")
        edit("files/msgdata/msg/msg_0279.gmm", "</body>",
             '<row id="msg_0279_00238" index="238"><attribute name="window_context_name">used</attribute>'
             '<language name="English">Hoenn</language></row>\n</body>')
        edit("src/trainer_memo.c", "mapsec == MAPSEC_OLDALE_TOWN",
             "mapsec == MAPSEC_OLDALE_TOWN || mapsec == MAPSEC_HOENN_REGION")
        edit("src/data/map_headers.h", "\n};", "\n" + "\n".join(header_entries) + "\n};")
        # Sidecars avoid changing MapHeader's packed binary ABI or truncating IDs.
        put("src/data/hoenn_region_banks.h",
            f"#define HOENN_REGION_FIRST_MAP {FIRST_MAP}\n"
            f"#define HOENN_REGION_MAP_COUNT {len(added)}\n"
            "static const u16 sHoennAreaBanks[] = {" + ", ".join(map(str, area_ids)) + "};\n"
            "static const u16 sHoennWildBanks[] = {" + ", ".join(map(str, wild_ids)) + "};\n")
        edit("src/map_header.c", '#include "data/map_headers.h"',
             '#include "data/map_headers.h"\n#include "data/hoenn_region_banks.h"')
        edit("src/map_header.c", "u8 MapHeader_GetAreaDataBank(u32 mapId) {\n",
             "u16 MapHeader_GetAreaDataBank(u32 mapId) {\n"
             "    if (mapId >= HOENN_REGION_FIRST_MAP && mapId < HOENN_REGION_FIRST_MAP + HOENN_REGION_MAP_COUNT) {\n"
             "        return sHoennAreaBanks[mapId - HOENN_REGION_FIRST_MAP];\n    }\n")
        edit("src/map_header.c", "u8 MapHeader_GetWildEncounterBank(u32 mapId) {\n",
             "u16 MapHeader_GetWildEncounterBank(u32 mapId) {\n"
             "    if (mapId >= HOENN_REGION_FIRST_MAP && mapId < HOENN_REGION_FIRST_MAP + HOENN_REGION_MAP_COUNT) {\n"
             "        return sHoennWildBanks[mapId - HOENN_REGION_FIRST_MAP];\n    }\n")
        edit("src/map_header.c", "BOOL MapHeader_HasWildEncounters(u32 mapId) {\n",
             "BOOL MapHeader_HasWildEncounters(u32 mapId) {\n"
             "    if (mapId >= HOENN_REGION_FIRST_MAP && mapId < HOENN_REGION_FIRST_MAP + HOENN_REGION_MAP_COUNT) {\n"
             "        return sHoennWildBanks[mapId - HOENN_REGION_FIRST_MAP] != 0xFFFF;\n    }\n")
        for getter in ("AreaDataBank", "WildEncounterBank"):
            edit("include/map_header.h", f"u8 MapHeader_Get{getter}(u32 mapId);",
                 f"u16 MapHeader_Get{getter}(u32 mapId);")
        # The existing assembly stores/passes this argument as a full register.
        edit("include/field/area_data.h", "AreaDataManager_Alloc(u8 areaDataBank)",
             "AreaDataManager_Alloc(u32 areaDataBank)")
        edit("src/map_events.c", '#include "map_events.h"',
             '#include "map_events.h"\n#include "save_campaign.h"')
        edit("src/map_events.c", "    if (obj_count != 0) {\n",
             f"    if (fieldSystem->location->mapId >= {FIRST_MAP} && fieldSystem->location->mapId < {FIRST_MAP + len(added)}) {{\n"
             "        u32 i;\n        for (i = 0; i < obj_count; i++) {\n"
             "            ObjectEvent object = fieldSystem->mapEvents->object_events[i];\n"
             "            BOOL hidden = FALSE;\n"
             "            if (object.eventFlag != 0 && (!CampaignSave_GetFlag(Save_Campaign_Get(fieldSystem->saveData),\n"
             "                    0, object.eventFlag, &hidden) || hidden)) {\n                continue;\n            }\n"
             "            object.eventFlag = 0;\n"
             "            MapObject_CreateFromMultipleObjectEvents(fieldSystem->mapObjectManager,\n"
             "                fieldSystem->location->mapId, 1, &object);\n"
             "        }\n        return;\n    }\n    if (obj_count != 0) {\n")
        put("files/poketool/trainer/trainers.json", json_bytes(trainers))
        put("files/fielddata/encountdata/gs_enc_data.json", json_bytes(encounters))
        # Any native caller using an imported trainer ID must use the donor
        # defeat namespace, not alias/overflow Johto's finite trainer flag array.
        edit("src/script_manager.c", '#include "script_manager.h"',
             '#include "script_manager.h"\n#include "save_campaign.h"')
        trainer_lo, trainer_hi = battle.first_trainer, battle.first_trainer + len(battle.trainers)
        flag_expression = f"0x500 + trainer - {trainer_lo} + 1"
        edit("src/script_manager.c", "BOOL TrainerFlagCheck(SaveData *saveData, u32 trainer) {\n",
             "BOOL TrainerFlagCheck(SaveData *saveData, u32 trainer) {\n"
             f"    if (trainer >= {trainer_lo} && trainer < {trainer_hi}) {{\n"
             "        BOOL defeated = TRUE;\n"
             f"        if (!CampaignSave_GetFlag(Save_Campaign_Get(saveData), 0, {flag_expression}, &defeated)) {{\n"
             "            return TRUE;\n        }\n        return defeated;\n    }\n")
        for operation, value in (("Set", 1), ("Clear", 0)):
            edit("src/script_manager.c", f"void TrainerFlag{operation}(SaveData *saveData, u32 trainer) {{\n",
                 f"void TrainerFlag{operation}(SaveData *saveData, u32 trainer) {{\n"
                 f"    if (trainer >= {trainer_lo} && trainer < {trainer_hi}) {{\n"
                 f"        if (!CampaignSave_SetFlag(Save_Campaign_Get(saveData), 0, {flag_expression}, {value})) {{\n"
                 "            GF_ASSERT(FALSE);\n        }\n        return;\n    }\n")

        statuses = Counter(r["status"] for rec in records.values() for r in rec["interactions"])
        blockers = Counter(r["reason"] for rec in records.values()
                           for r in rec["interactions"] if "reason" in r)
        report = dict(
            format=1, donor_commit=DONOR_COMMIT,
            status="experimental-bulk-source-candidate", campaign_complete=False,
            native_build_verified=False, gameplay_verified=False,
            scope=dict(donor_maps=len(maps), retained_maps=len(PRESERVED), added_maps=len(added),
                       native_map_count=FIRST_MAP + len(added), land_members=len(archives[LANDS]),
                       trainer_parties=len(battle.trainers), encounter_tables=len(encounter_banks),
                       interactions=dict(statuses)),
            maps=list(records.values()), interaction_blockers=dict(blockers.most_common()),
            trainer_adaptations=battle.trainer_report, encounter_adaptations=encounter_notes,
            test_directory=dict(map=543, npc=[10, 15],
                                destinations=[r["native_map"] for r in directory]),
            limitations=[
                "Flat, static source graphics; no donor animation, occlusion layers, elevation or field effects.",
                "Stock stationary NPC stand-ins, stock music, no Hoenn world-map/Fly integration.",
                "Unsupported story scripts are visibly blocked, not replaced by generic progress.",
                "Story-coordinate triggers, map-load/frame scripts and regional initialization are implementation gaps.",
                "Water/dive/currents/bridges/puzzles and dynamic warps are not yet implemented.",
                "Trainer parties use native battle mechanics, native class artwork/payouts and stock AI flags 7.",
                "Trainer encounters are interaction-driven, not donor line-of-sight movement.",
                "Test-return assistants do not set quest, badge or trainer-defeat flags.",
                "Build success is not campaign, editor, SoulSilver or hardware qualification.",
            ],
            files_changed=dict(changes))
        put("hoenn-import-report.json", json_bytes(report))
        # Keep a compact delta list for incremental builds on the existing SDK cache.
        delta = {name: digest for name, digest in changes.items()
                 if original.get(name) != digest}
        (tree / "hoenn-build-files.json").write_bytes(json_bytes(delta))
        publish(tree, output)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--episode", required=True, type=Path)
    parser.add_argument("--donor", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    try:
        report = prepare(args.episode, args.donor, args.output)
    except (ValueError, KeyError) as error:
        parser.exit(1, str(error) + "\n")
    print(json.dumps(dict(status=report["status"], scope=report["scope"],
                          campaign_complete=False,
                          report=str(args.output / "hoenn-import-report.json")), indent=2))


if __name__ == "__main__":
    main()
