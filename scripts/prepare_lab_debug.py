#!/usr/bin/env python3
"""Create an isolated opt-in test-build tree with a reachable flat lab.

Use disposable saves only. Elm's interaction becomes the test entrance in this
generated tree only. Select native mode to exercise the real rescue battle;
the default simulated mode preserves the legacy reward-only diagnostic.
"""
import argparse
import json
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

from stage_lab_archives import stage


def replace_once(path, old, new):
    text = path.read_text()
    if text.count(old) != 1:
        raise ValueError("Expected unique anchor in " + str(path))
    path.write_text(text.replace(old, new))


def install(root, assets, rescue_mode="simulated"):
    """Install only into an explicitly supplied disposable extracted tree."""
    if rescue_mode not in ("simulated", "native"):
        raise ValueError("Unknown rescue mode: " + str(rescue_mode))
    with tempfile.TemporaryDirectory() as directory:
        overlay = Path(directory) / "overlay"
        stage(root, assets, overlay)
        for source in (overlay / "files").rglob("*"):
            if source.is_file():
                destination = root / source.relative_to(overlay)
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source, destination)
    maps = root / "include/constants/maps.h"
    replace_once(maps, "#define MAP_ID_MAX                                        540",
                 "#define MAP_HOENN_LAB_DEBUG 540\n#define MAP_ID_MAX 541")
    headers = root / "src/data/map_headers.h"
    text = headers.read_text()
    match = re.search(r"\[MAP_NEW_BARK_ELMS_LAB_1F\] = \{.*?\},", text, re.S)
    if match is None:
        raise ValueError("Missing indoor header template")
    entry = match.group().replace("MAP_NEW_BARK_ELMS_LAB_1F", "MAP_HOENN_LAB_DEBUG")
    for field, value in {"areaDataBank": "106", "matrixId": "288",
                         "scriptsBank": "965", "scriptHeaderBank": "399",
                         "msgBank": "829", "eventsBank": "491",
                         "followMode": "MAP_FOLLOWMODE_PREVENT",
                         "outgoingCalls": "FALSE", "incomingCalls": "FALSE",
                         "radioSignal": "FALSE"}.items():
        entry, count = re.subn(r"(\." + field + r"\s*=\s*)[^,]+",
                              lambda m: m[1] + value, entry)
        if count != 1:
            raise ValueError("Missing map field: " + field)
    if text.count("\n};") != 1:
        raise ValueError("Unexpected map table terminator")
    headers.write_text(text.replace("\n};", "\n    " + entry + "\n};"))
    scripts = root / "files/fielddata/script/scr_seq"
    reward = scripts / "scr_seq_0965_hoenn_reward.s"
    reward_text = reward.read_text()
    if reward_text.count("ScrDefEnd") != 1:
        raise ValueError("Unexpected reward script entry table")
    definitions = re.findall(r"^\s*ScrDef\s+([A-Za-z_]\w*)\s*$",
                             reward_text.split("ScrDefEnd", 1)[0], re.M)
    if (definitions[:3] != ["HoennReward_Claim", "HoennReward_Interaction",
                            "HoennRescue_Interaction"]
            or len(definitions) != 3):
        raise ValueError("Invalid reward script entry table")
    # Object script IDs are one-based, while archive entries are zero-based.
    # Production entries (including the rescue) must never be reused for return.
    return_entry = len(definitions)
    events = root / "files/fielddata/eventdata/zone_event"
    if len(list(events.glob("*.json"))) != 491:
        raise ValueError("Event archive index changed")
    def actor(number, x, script):
        return dict(id=number, spriteId="SPRITE_ASSISTANTM", movement=0, type=0,
                    eventFlag=0, scriptId=script, facingDirection=1,
                    param0=0, param1=0, param2=0, xRange=0, yRange=0,
                    x=x, z=17, y=0)
    actors = [actor(0, 14, 2), actor(1, 18, return_entry + 1)]
    if rescue_mode == "native":
        actors.append(actor(2, 16, 3))  # Script ID 3 is production entry 2.
    (events / "491_HOENN_LAB_DEBUG.json").write_text(json.dumps(
        dict(bgs=[], objects=actors, warps=[], coords=[]), indent=2) + "\n")
    entrance = scripts / "scr_seq_0843_T20R0101.s"
    eligibility = ("SetVar 0x416e, 1\n" if rescue_mode == "simulated" else "")
    comment = ("// DEBUG ONLY: disposable-save rescue simulation.\n"
               if rescue_mode == "simulated" else
               "// DEBUG ONLY: native rescue battle; do not change earned state.\n")
    replace_once(entrance, "scr_seq_T20R0101_000:",
                 "scr_seq_T20R0101_000:\n"
                 + comment +
                 "GoToIfUnset FLAG_GOT_STARTER, HoennDebug_ElmOriginal\n"
                 + eligibility +
                 "Warp 540, 0, 16, 19, 0\nEnd\n"
                 "HoennDebug_ElmOriginal:\n")
    replace_once(reward, "ScrDefEnd", "ScrDef HoennDebug_Return\nScrDefEnd")
    with reward.open("a") as stream:
        stream.write("\n// DEBUG ONLY: return NPC (right scientist).\n"
                     "HoennDebug_Return:\n"
                     "Warp MAP_NEW_BARK_ELMS_LAB_1F, 0, 6, 12, 1\nEnd\n")
    introduction = (r"DEBUG LAB: Simulated rescue.\nTest a Hoenn starter reward."
                    if rescue_mode == "simulated" else
                    r"DEBUG LAB: Rescue completed.\nChoose a Hoenn partner.")
    replace_once(root / "files/msgdata/msg/msg_0829_hoenn_reward.gmm",
                 r"Birch: Thank you for helping me!\nChoose a partner from Hoenn.",
                 introduction)
    # Hash gates for unmodified banks remain intact; the two intentional
    # debug script changes are re-hashed by the existing native builder.
    baseline = root / "expansion/baseline.json"
    data = json.loads(baseline.read_text())
    data["capacities"]["map_count"] = 541
    baseline.write_text(json.dumps(data, indent=2) + "\n")
    warnings = ["Both scientist actors are technical placeholder art",
                "Never load this debug save with stock ROM or valuable save",
                "Flat model; not the Route 101 chase or a complete campaign"]
    if rescue_mode == "simulated":
        warnings.insert(0, "Rescue eligibility is simulated, not a completed battle")
    return {"debug_only": True, "rescue_mode": rescue_mode,
            "eligibility_injected": rescue_mode == "simulated",
            "requires_real_rescue_battle": rescue_mode == "native",
            "map": 540, "matrix": 288, "events": 491,
            "reward_entry": 1, "return_entry": return_entry,
            "entrance": "Talk to Elm in his lab using a disposable post-starter save",
            "spawn": [16, 19], "reward_actor": [14, 17], "return_actor": [18, 17],
            "rescue_actor": [16, 17] if rescue_mode == "native" else None,
            "warnings": warnings}


def prepare(root, assets, output, rescue_mode="simulated"):
    if output.exists():
        raise ValueError("Refusing existing output")
    if rescue_mode not in ("simulated", "native"):
        raise ValueError("Unknown rescue mode: " + str(rescue_mode))
    # git archive prevents source-tree edits, build outputs, compiler/license
    # material and untracked files from leaking into the generated test tree.
    output.mkdir(parents=True)
    archive = subprocess.Popen(["git", "-C", str(root), "archive", "HEAD"],
                               stdout=subprocess.PIPE)
    subprocess.run(["tar", "-x", "-C", str(output)], stdin=archive.stdout, check=True)
    archive.stdout.close()
    if archive.wait():
        raise ValueError("git archive failed")
    report = install(output, assets, rescue_mode)
    report["source_commit"] = subprocess.check_output(
        ["git", "-C", str(root), "rev-parse", "HEAD"], text=True).strip()
    (output / "lab-debug.json").write_text(json.dumps(report, indent=2) + "\n")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--assets", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--rescue-mode", choices=("simulated", "native"),
                        default="simulated",
                        help="native (recommended) exposes the real Zigzagoon rescue; "
                             "simulated preserves the legacy reward-only diagnostic")
    args = parser.parse_args()
    print(json.dumps(prepare(args.root, args.assets, args.output,
                             args.rescue_mode), indent=2))