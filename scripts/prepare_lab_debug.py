#!/usr/bin/env python3
"""Create an isolated opt-in test-build tree with a reachable flat lab.

Use disposable saves only. Elm's interaction becomes the test entrance in this
generated tree only; this simulates rescue eligibility, not the real rescue.
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


def install(root, assets):
    """Install only into an explicitly supplied disposable extracted tree."""
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
    events = root / "files/fielddata/eventdata/zone_event"
    if len(list(events.glob("*.json"))) != 491:
        raise ValueError("Event archive index changed")
    def actor(number, x, script):
        return dict(id=number, spriteId="SPRITE_ASSISTANTM", movement=0, type=0,
                    eventFlag=0, scriptId=script, facingDirection=1,
                    param0=0, param1=0, param2=0, xRange=0, yRange=0,
                    x=x, z=17, y=0)
    (events / "491_HOENN_LAB_DEBUG.json").write_text(json.dumps(
        dict(bgs=[], objects=[actor(0, 14, 2), actor(1, 18, 3)],
             warps=[], coords=[]), indent=2) + "\n")
    scripts = root / "files/fielddata/script/scr_seq"
    entrance = scripts / "scr_seq_0843_T20R0101.s"
    replace_once(entrance, "scr_seq_T20R0101_000:",
                 "scr_seq_T20R0101_000:\n"
                 "// DEBUG ONLY: disposable-save rescue simulation.\n"
                 "GoToIfUnset FLAG_GOT_STARTER, HoennDebug_ElmOriginal\n"
                 "SetVar 0x416e, 1\nWarp 540, 0, 16, 19, 0\nEnd\n"
                 "HoennDebug_ElmOriginal:\n")
    reward = scripts / "scr_seq_0965_hoenn_reward.s"
    replace_once(reward, "ScrDefEnd", "ScrDef HoennDebug_Return\nScrDefEnd")
    with reward.open("a") as stream:
        stream.write("\n// DEBUG ONLY: return NPC (right scientist).\n"
                     "HoennDebug_Return:\n"
                     "Warp MAP_NEW_BARK_ELMS_LAB_1F, 0, 6, 12, 1\nEnd\n")
    replace_once(root / "files/msgdata/msg/msg_0829_hoenn_reward.gmm",
                 r"Birch: Thank you for helping me!\nChoose a partner from Hoenn.",
                 r"DEBUG LAB: Simulated rescue.\nTest a Hoenn starter reward.")
    # Hash gates for unmodified banks remain intact; the two intentional
    # debug script changes are re-hashed by the existing native builder.
    baseline = root / "expansion/baseline.json"
    data = json.loads(baseline.read_text())
    data["capacities"]["map_count"] = 541
    baseline.write_text(json.dumps(data, indent=2) + "\n")
    return {"debug_only": True, "map": 540, "matrix": 288, "events": 491,
            "entrance": "Talk to Elm in his lab using a disposable post-starter save",
            "spawn": [16, 19], "reward_actor": [14, 17], "return_actor": [18, 17],
            "warnings": ["Rescue eligibility is simulated, not an implemented episode",
                         "Both scientist actors are technical placeholder art",
                         "Never load this debug save with stock ROM or valuable save",
                         "Flat model, no emulator/VRAM verification yet"]}


def prepare(root, assets, output):
    if output.exists():
        raise ValueError("Refusing existing output")
    # git archive prevents source-tree edits, build outputs, compiler/license
    # material and untracked files from leaking into the generated test tree.
    output.mkdir(parents=True)
    archive = subprocess.Popen(["git", "-C", str(root), "archive", "HEAD"],
                               stdout=subprocess.PIPE)
    subprocess.run(["tar", "-x", "-C", str(output)], stdin=archive.stdout, check=True)
    archive.stdout.close()
    if archive.wait():
        raise ValueError("git archive failed")
    report = install(output, assets)
    report["source_commit"] = subprocess.check_output(
        ["git", "-C", str(root), "rev-parse", "HEAD"], text=True).strip()
    (output / "lab-debug.json").write_text(json.dumps(report, indent=2) + "\n")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--assets", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(prepare(args.root, args.assets, args.output), indent=2))