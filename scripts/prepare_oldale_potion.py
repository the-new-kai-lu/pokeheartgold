#!/usr/bin/env python3
"""Opt-in SOURCE overlay onto verified R7 campaign-save + script-bridge output.

Never prepares the campaign foundation, reads ROMs/saves, builds, migrates or
approves a candidate. Existing sources and historical acceptance pins are inputs
only. The independent asset_changes API can be checked before bridge publication.
"""

import argparse
import json
import os
from pathlib import Path
import re
import struct
import tempfile
import xml.etree.ElementTree as ET

import prepare_campaign_save as campaign
from hgss_land import Land, narc_members


ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = ROOT / "scripts/episode_templates"
EVENT = "files/fielddata/eventdata/zone_event/494_OLDALE_TOWN_TRAVEL.json"
SCRIPT = "files/fielddata/script/scr_seq/scr_seq_0967_oldale_arrival.s"
MESSAGE = "files/msgdata/msg/msg_0830_oldale_arrival.gmm"
HEADER = "files/fielddata/script/scr_seq/scr_seq_0968_oldale_potion_hdr.s"
MAP_HEADERS = "src/data/map_headers.h"
CONTINUE = "src/field_warp_tasks.c"
LAND = "files/a/0/6/5"
REPORT = "oldale-potion-source.json"
SCOPE = frozenset((EVENT, SCRIPT, MESSAGE, HEADER, MAP_HEADERS, CONTINUE))
STATUS = "unapproved-source-candidate-runtime-unverified"
CONTINUE_ANCHOR = (
    "            FieldSystem_StartBugContestTimer(fieldSystem);\n"
    "            sub_0205323C(fieldSystem);\n"
    "        }\n"
)
CONTINUE_REPLACEMENT = (
    "            FieldSystem_StartBugContestTimer(fieldSystem);\n"
    "            sub_0205323C(fieldSystem);\n"
    "            /* Oldale Potion: saved temp vars/actors normally bypass transition.\n"
    "             * Re-arm only this map's non-yielding reset; its frame entry\n"
    "             * repairs the restored employee with a real ScriptEnvironment. */\n"
    "            if (fieldSystem->location->mapId == MAP_OLDALE_TOWN_TRAVEL) {\n"
    "                TryStartMapScriptByType(fieldSystem, INIT_SCRIPT_ON_TRANSITION);\n"
    "            }\n"
    "        }\n"
)
LIMITS = [
    "Native SPRITE_SHOPM1 (24/model23) is the walking Mart-clerk equivalent, not Emerald pixels.",
    "Native follow sequence SEQ_GS_E_TSURETEKE2 (1087), used by Cherrygrove's guide, is not Emerald MUS_FOLLOW_ME audio.",
    "Native movement speeds, sprite turn timing and message pagination require runtime review; donor walk/delay paths are preserved.",
    "Campaign-backed relocation runs at the first asynchronous map frame, not Emerald's synchronous transition; first-render timing needs native review.",
    "The native Potion (17; Emerald item13) uses the MEDICINE pocket, not Emerald's ITEMS pocket.",
    "Native FadeOutBGM/ResetBGM/FadeInBGM implements return to map music, not a port of Emerald's audio engine.",
    "Only the outdoor employee is added; existing girl and R7 warps remain. No interiors, other town NPCs, rival or visited flag.",
    "A hypothetical rollback failure is a terminal locked interaction, never an unlocked unreceipted gift.",
]
GATES = [
    "Independent parent source review; no historical approval hashes have changed.",
    "Native SDK/linker build, appended NARC script-header ordering and message encoding.",
    "Frame entry after arrival and saved-game continue; employee relocation and no menu-resume reset.",
    "All three facing-dependent escorts, collision/timing, sprite and follow/default music.",
    "Successful native Bag_AddItem, full bag, repeated interaction and actual campaign receipt persistence.",
    "Read/write failure injection, synchronous Bag_TakeItem rollback and fail-closed quarantine.",
    "Girl interaction and byte-preserved R7 south-exit/return traversal regression evidence.",
    "Actual flash/save/load/revisit behavior; host tests are not native gameplay proof.",
]


def profile():
    return json.loads(campaign.read(TEMPLATES / "oldale_potion_profile.json"))


def pinned(reader, name, expected):
    data = reader(name)
    if campaign.sha(data) != expected:
        raise ValueError(f"Actual R7/announced donor safety preimage mismatch: {name}")
    return data


def once(data, old, new, label):
    if data.count(old) != 1:
        raise ValueError(f"Missing/ambiguous Oldale source anchor: {label}")
    return data.replace(old, new, 1)


def verify_r7(episode):
    """Actual R7 anchors, not a synthetic stock-only episode profile."""
    p = profile()
    if campaign.sha(campaign.read(TEMPLATES / "native_edits.json")) != p["native_edits_sha256"]:
        raise ValueError("Published episode native-edits recipe changed")
    recipe = json.loads(campaign.read(TEMPLATES / "native_edits.json"))
    for name, digest in p["native_sha256"].items():
        pinned(lambda n: campaign.read(episode / n), name, digest)
    # In particular 854 remains the actual actor command, not a bridge reservation.
    for name in ("asm/macros/script.inc", "src/data/fieldmap/script_cmd_table.h",
                 "include/scrcmd.h", "src/scrcmd_c.c"):
        pinned(lambda n: campaign.read(episode / n), name, recipe[name]["after"])
    if not re.search(rb"\.macro EnsureRoute101Actors result\s+\.short 854\s+\.short \\result",
                     campaign.read(episode / "asm/macros/script.inc")):
        raise ValueError("Actual actor opcode854 signature missing")
    if HEADER in source_names(episode):
        raise ValueError("Required append-only script-header slot0968 is occupied")
    headers = campaign.read(episode / MAP_HEADERS).decode()
    old = p["oldale_header_entry"]
    if headers.count(old) != 1 or headers.count("[MAP_OLDALE_TOWN_TRAVEL]") != 1:
        raise ValueError("Actual R7 Oldale map header entry changed")
    return dict(p["native_sha256"], **{MAP_HEADERS: campaign.sha(headers.encode())})


def donor_dialogue(source, label):
    block = re.search(r"^" + re.escape(label) + r"::?[ \t]*\n((?:[ \t]*\.string .*\n?)+)",
                      source, re.M)
    if not block:
        raise ValueError(f"Missing Emerald dialogue: {label}")
    pieces = re.findall(r'^[ \t]*\.string "(.*)"$', block.group(1), re.M)
    return "".join(pieces).removesuffix("$").replace(r"\p", r"\r").replace(r"\l", r"\n")


def verify_donor(donor):
    p = profile()
    sources = {name: pinned(lambda n: campaign.read(donor / n), name, digest)
               for name, digest in p["donor_sha256"].items()}
    flags = sources["include/constants/flags.h"].decode()
    if not re.search(r"#define FLAG_RECEIVED_POTION_OLDALE\s+0x84\b", flags):
        raise ValueError("Emerald receipt identity changed")
    items = sources["include/constants/items.h"].decode()
    # Authentic Emerald enum: NONE=0, twelve balls, POTION=13. Native maps to17.
    enum = re.search(r"enum\s*\{(.*?)\};", items, re.S).group(1)
    enum = re.sub(r"//[^\n]*|/\*.*?\*/", "", enum, flags=re.S)
    if [v.strip() for v in enum.split(",")].index("ITEM_POTION") != 13:
        raise ValueError("Emerald Potion identity changed")
    town = json.loads(sources["data/maps/OldaleTown/map.json"])
    employee = next(o for o in town["object_events"]
                    if o.get("local_id") == "LOCALID_OLDALE_MART_EMPLOYEE")
    if (employee["graphics_id"], employee["script"], employee["x"], employee["y"]) != (
            "OBJ_EVENT_GFX_MART_EMPLOYEE", "OldaleTown_EventScript_MartEmployee", 13, 7):
        raise ValueError("Emerald outdoor employee binding changed")
    messages = ET.fromstring("<body>" + campaign.read(
        TEMPLATES / "oldale_potion_messages.xml").decode() + "</body>")
    texts = {int(row.attrib["index"]): row.find("language").text for row in messages}
    for index, label in ((1, "OldaleTown_Text_IWorkAtPokemonMart"),
                         (2, "OldaleTown_Text_ThisIsAPokemonMart"),
                         (3, "OldaleTown_Text_PotionExplanation")):
        if texts[index] != donor_dialogue(sources["data/maps/OldaleTown/scripts.inc"].decode(), label):
            raise ValueError(f"Employee dialogue differs from Emerald: {label}")
    if texts[4] != donor_dialogue(sources["data/text/obtain_item.inc"].decode(),
                                 "gText_TooBadBagIsFull"):
        raise ValueError("Full bag dialogue differs from Emerald")
    return p["donor_sha256"]


def asset_changes(reader):
    """Independent pure overlay, same anchors on fixtures AND actual R7 source.

    reader returns source bytes or raises FileNotFoundError. No input mutations,
    bridge preparation, native code execution or compiled outputs.
    """
    p = profile()
    originals = {name: pinned(reader, name, p["native_sha256"][name])
                 for name in (EVENT, SCRIPT, MESSAGE, CONTINUE)}
    try:
        reader(HEADER)
    except FileNotFoundError:
        pass
    else:
        raise ValueError("Oldale append-only header0968 already exists")
    employee = dict(id=1, spriteId=24, movement=0, type=0, eventFlag=0,
                    scriptId=2, facingDirection=1, param0=0, param1=0, param2=0,
                    xRange=0, yRange=0, x=13, z=7, y=0)
    rendered = "\n".join("    " + line for line in json.dumps(employee, indent=2).splitlines())
    event = once(originals[EVENT], b"    }\n  ],\n  \"warps\": [",
                 ("    },\n" + rendered + '\n  ],\n  "warps": [').encode(), "outdoor object append")
    script = once(originals[SCRIPT], b"ScrDefEnd\n",
                  b"ScrDef Oldale_MartEmployee\nScrDef Oldale_PotionOnTransition\n"
                  b"ScrDef Oldale_PotionOnEntry\nScrDefEnd\n", "one-based script entries")
    script += b"\n" + campaign.read(TEMPLATES / "oldale_potion_script.s")
    message = once(originals[MESSAGE], b"</body>",
                   campaign.read(TEMPLATES / "oldale_potion_messages.xml") + b"</body>", "message append")
    headers = reader(MAP_HEADERS)
    old = p["oldale_header_entry"].encode()
    if headers.count(b"[MAP_OLDALE_TOWN_TRAVEL]") != 1:
        raise ValueError("Oldale header binding is ambiguous")
    new = old.replace(b"NARC_scr_seq_scr_seq_0399_EVERYWHERE_hdr_bin",
                      b"NARC_scr_seq_scr_seq_0968_oldale_potion_hdr_bin")
    headers = once(headers, old, new, "private map header binding")
    continuation = once(originals[CONTINUE], CONTINUE_ANCHOR.encode(),
                        CONTINUE_REPLACEMENT.encode(), "Oldale-only normal continue reset")
    result = {EVENT: event, SCRIPT: script, MESSAGE: message, MAP_HEADERS: headers,
              CONTINUE: continuation, HEADER: campaign.read(TEMPLATES / "oldale_potion_header.s")}
    verify_asset_delta(reader, result)
    return result


def verify_asset_delta(reader, changes):
    if set(changes) != SCOPE:
        raise ValueError("Potion overlay escaped its exact six-file native scope")
    original, after = json.loads(reader(EVENT)), json.loads(changes[EVENT])
    if (after["objects"][:-1] != original["objects"]
            or {k: v for k, v in after.items() if k != "objects"}
            != {k: v for k, v in original.items() if k != "objects"}
            or changes[EVENT].split(b'  "warps":', 1)[1]
            != reader(EVENT).split(b'  "warps":', 1)[1]):
        raise ValueError("Girl or byte-level R7 warp source changed")
    girl = reader(SCRIPT).split(b"Oldale_Girl:\n", 1)[1]
    if not changes[SCRIPT].split(b"Oldale_Girl:\n", 1)[1].startswith(girl):
        raise ValueError("Existing girl's script body changed")
    if reader(MESSAGE).split(b"<row", 1)[1].split(b"</row>", 1)[0] not in changes[MESSAGE]:
        raise ValueError("Existing girl's message bytes changed")
    ET.fromstring(changes[MESSAGE])
    # Native ContinueGame's ONLY delta: one map-scoped reset at a reviewed anchor.
    if once(changes[CONTINUE], CONTINUE_REPLACEMENT.encode(), CONTINUE_ANCHOR.encode(),
            "continue delta reversal") != reader(CONTINUE):
        raise ValueError("ContinueGame change escaped the bounded map-entry reset")


def terrain_proof(episode):
    members = narc_members(campaign.read(episode / LAND))
    if len(members) != 680:
        raise ValueError("Actual R7 native land bank count changed")
    words = struct.unpack("<1024H", Land.decode(members[679]).terrain)
    paths = {
        "employee_east": [(13, y) for y in range(14, 6, -1)],
        "employee_north": [(13, y) for y in range(14, 6, -1)],
        "employee_south": [(13, 14), (12, 14), (12, 13), (12, 12), (13, 12)]
                          + [(13, y) for y in range(11, 6, -1)],
        "player_east": [(12, 14)] + [(13, y) for y in range(14, 7, -1)],
        "player_north": [(13, y) for y in range(15, 7, -1)],
        "player_south": [(13, y) for y in range(13, 7, -1)],
    }
    for name, path in paths.items():
        if any(words[y * 32 + x] & 0x8000 for x, y in path):
            raise ValueError(f"R7 conservative native terrain blocks donor escort: {name}")
    if not words[14 * 32 + 14] & 0x8000:
        raise ValueError("Unexpected west-facing approach: Emerald has no west escort")
    return dict(land_member=679, land_member_sha256=campaign.sha(members[679]),
                paths=paths, terrain_modified=False, native_runtime_proven=False)


def source_names(root):
    """Same source/asset roots as the campaign composer; excludes before reads."""
    names = {n for n in campaign.SOURCE_FILES if (root / n).exists()}
    for name in campaign.SOURCE_DIRS:
        directory = root / name
        if not directory.exists():
            continue
        campaign.guard_path(directory)
        for current, dirs, files in os.walk(directory, followlinks=False):
            current = Path(current)
            for child in list(dirs):
                path = current / child
                relative = path.relative_to(root).as_posix()
                if (child in campaign.EXCLUDED_DIRS or child.startswith("cmake-build-")
                        or relative in ("tools/bin", "tools/mwccarm")):
                    dirs.remove(child)
                elif path.is_symlink():
                    raise ValueError(f"Symlinked source directory forbidden: {path}")
            names.update((current / f).relative_to(root).as_posix() for f in files
                         if not campaign.excluded_file((current / f).relative_to(root).as_posix()))
    return names


def prepare(episode, campaign_source, donor, output, *, author_unapproved=False):
    if author_unapproved is not True:
        raise ValueError("Explicit unapproved Oldale Potion authoring opt-in required")
    episode, campaign_source, donor, output = map(
        campaign.guard_path, (episode, campaign_source, donor, output))
    if output.exists():
        raise ValueError("Oldale Potion source output must be fresh")
    for source in (episode, campaign_source, donor, ROOT):
        if output.is_relative_to(source) or source.is_relative_to(output):
            raise ValueError("Oldale Potion source output overlaps an input/template checkout")
    native_anchors = verify_r7(episode)
    donor_anchors = verify_donor(donor)
    campaign_delta = campaign.verify_candidate(campaign_source, episode, script_bridge=True)
    foundation_report = campaign.read(campaign_source / "campaign-save-source.json")
    foundation = json.loads(foundation_report)
    if (foundation.get("approved") is not False or foundation.get("runtime_verified") is not False
            or foundation.get("script_bridge", {}).get("enabled") is not True
            or foundation["script_bridge"].get("input_profile") != campaign.BRIDGE_INPUT_PROFILE):
        raise ValueError("Expected fresh, unapproved real-R7 optional campaign+bridge output")
    if source_names(campaign_source) != source_names(episode) | set(campaign_delta):
        raise ValueError("Campaign foundation source inventory differs from its exact optional delta")
    changes = asset_changes(lambda n: campaign.read(campaign_source / n))
    decoded = terrain_proof(episode)
    template_hashes = {p.name: campaign.sha(campaign.read(p))
                       for p in sorted(TEMPLATES.glob("oldale_potion_*"))}
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".oldale-potion-source-", dir=output.parent) as tmp:
        tree = Path(tmp) / "tree"
        tree.mkdir()
        inventory, excluded = campaign.copy_sources(campaign_source, tree)
        episode_inventory = {}
        for name, digest in inventory.items():
            source_path = episode / name
            if source_path.exists():
                episode_inventory[name] = campaign.sha(campaign.read(source_path))
            if digest != campaign_delta.get(name, episode_inventory.get(name)):
                raise ValueError(f"Campaign foundation changed unrelated R7 source: {name}")
        for name, data in changes.items():
            target = tree / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
        after = {}
        for name in sorted(set(inventory) | set(changes)):
            expected = campaign.sha(changes[name]) if name in changes else inventory[name]
            after[name] = campaign.sha(campaign.read(tree / name))
            if after[name] != expected:
                raise ValueError(f"Unexpected Potion candidate delta: {name}")
            if name in inventory and campaign.sha(campaign.read(campaign_source / name)) != inventory[name]:
                raise ValueError(f"Campaign input changed during composition: {name}")
            if name in episode_inventory and campaign.sha(campaign.read(episode / name)) != episode_inventory[name]:
                raise ValueError(f"R7 episode input changed during composition: {name}")
        if source_names(tree) != set(after):
            raise ValueError("Candidate contains undeclared source files")
        verify_asset_delta(lambda n: campaign.read(campaign_source / n),
                           {n: campaign.read(tree / n) for n in SCOPE})
        # Potion does not touch ANY campaign delta path; revalidate native bridge.
        campaign.verify_candidate(tree, episode, script_bridge=True)
        if campaign.read(campaign_source / "campaign-save-source.json") != foundation_report:
            raise ValueError("Campaign foundation report changed during composition")
        verify_donor(donor)
        if {p.name: campaign.sha(campaign.read(p)) for p in sorted(
                TEMPLATES.glob("oldale_potion_*"))} != template_hashes:
            raise ValueError("Potion templates changed during composition")
        report = {
            "schema_version": 1, "status": STATUS, "approved": False,
            "runtime_verified": False, "migration_performed": False,
            "additional_save_allocation": 0,
            "mode": "pure-source-overlay-on-verified-optional-campaign-and-bridge",
            "changes": {n: {"before": inventory.get(n), "after": after[n]} for n in sorted(SCOPE)},
            "campaign_delta_sha256": campaign_delta,
            "campaign_foundation_report_sha256": campaign.sha(foundation_report),
            "metadata_files": ["campaign-save-source.json", REPORT],
            "r7_anchor_sha256": native_anchors, "donor_source_sha256": donor_anchors,
            "episode_source_sha256": episode_inventory,
            "input_source_sha256": inventory, "candidate_source_sha256": after,
            "template_sha256": template_hashes,
            "producer_sha256": campaign.sha(campaign.read(Path(__file__))),
            "source_roots": list(campaign.SOURCE_DIRS), "excluded_without_read_or_copy": excluded,
            "receipt": {"region": 0, "emerald_flag": 0x84, "emerald_item": 13,
                        "native_item": 17, "give_opcode": 125, "rollback_opcode": 126,
                        "bag_result": 0x800C, "bridge_status": {"success": 1, "failure": 0}},
            "map_local_state": {"tour": "OLDALE_POTION_TOUR/VAR_TEMP_x4008",
                                "entry_pending": "OLDALE_POTION_ENTRY_PENDING/VAR_TEMP_x4009",
                                "tour_values": {"not_toured": 0, "toured": 1, "entry_read_failed": 2},
                                "owner": "Oldale543 private header and employee bank only; no shared script calls",
                                "campaign_temp_storage": False,
                                "normal_warp_reset": "ClearTempFieldEventData then OnTransition",
                                "saved_game_reset": "Oldale-only ContinueGame_Normal hook invokes OnTransition",
                                "menu_resume_reset": False,
                                "campaign_reads": "async frame/interaction entries with ScriptEnvironment"},
            "unchanged_source_checks": {"girl_body_and_message": True, "girl_event": True,
                                        "r7_warp_source_bytes": True,
                                        "all_unrelated_copied_sources": True,
                                        "opcode854_actor_and_campaign_bridge": True,
                                        "historical_acceptance_pins": "not edited or replaced"},
            "terrain_proof": decoded, "fidelity_limits": LIMITS, "pending_runtime_gates": GATES,
        }
        (tree / "campaign-save-source.json").write_bytes(foundation_report)
        (tree / REPORT).write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
        campaign.publish(tree, output)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("episode", "campaign-source", "donor", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--author-unapproved-oldale-potion", action="store_true", required=True)
    args = parser.parse_args()
    try:
        report = prepare(args.episode, args.campaign_source, args.donor, args.output,
                         author_unapproved=args.author_unapproved_oldale_potion)
    except (ValueError, OSError) as error:
        parser.exit(1, f"{error}\n")
    print(json.dumps({k: report[k] for k in ("status", "changes", "fidelity_limits")}, indent=2))


if __name__ == "__main__":
    main()