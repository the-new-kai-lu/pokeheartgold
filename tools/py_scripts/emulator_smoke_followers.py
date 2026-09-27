#!/usr/bin/env python3
"""Replay actual follower walking in DeSmuME with disposable ROM/save copies.

Start with --rom, --save, --output; JSONL input can come from --sequence or stdin.
Use {"keys":[["A",10,400]],"name":"continue"} for setup;
{"capture":{"direction":"LEFT","hold":64,"sample_every":2},"name":"west"}
records native top-screen frames, an animation GIF, and a chronological contact sheet.
Screenshots are visual evidence, not automated proof of gait quality.
"""
import argparse
import hashlib
import json
import os
import shutil
import sys
import time
from pathlib import Path

from desmume.emulator import DeSmuME
from desmume.controls import Keys, keymask
from PIL import Image, ImageDraw


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rom",type=Path,required=True)
    parser.add_argument("--save",type=Path,required=True)
    parser.add_argument("--output",type=Path,required=True)
    parser.add_argument("--sequence",type=Path)
    parser.add_argument("--command-file",type=Path,help="Tail a JSONL control file when a terminal stdin is unavailable; {stop:true} ends")
    args=parser.parse_args()
    rom,save,out=args.rom.resolve(),args.save.resolve(),args.output.resolve()
    def follow_commands(path):
        path=path.resolve();path.touch(exist_ok=True)
        with path.open() as stream:
            while True:
                line=stream.readline()
                if line:yield line
                else:time.sleep(0.05)
    commands=follow_commands(args.command_file) if args.command_file else args.sequence.read_text().splitlines() if args.sequence else sys.stdin
    out.mkdir(parents=True,exist_ok=False)
    basename=out.name+".nds" # Avoid DeSmuME's shared battery-name collisions.
    shutil.copyfile(rom,out/basename);shutil.copyfile(save,out/"input.sav")
    os.chdir(out)
    emulator=DeSmuME();emulator.open(basename);emulator.volume_set(0)
    assert emulator.backup.import_file("input.sav");emulator.reset()
    total=0
    def frames(count):
        nonlocal total
        for _ in range(count):emulator.cycle(False);total+=1
    def key(name,hold=3,wait=120):
        mask=keymask(getattr(Keys,"KEY_"+name));emulator.input.keypad_add_key(mask)
        frames(hold);emulator.input.keypad_rm_key(mask);frames(wait)
    def touch(x,y,hold=3,wait=120):
        emulator.input.touch_set_pos(x,y);frames(hold);emulator.input.touch_release();frames(wait)
    frames(900);emulator.screenshot().save("000-boot.png")
    report={"rom_sha256":hashlib.sha256(rom.read_bytes()).hexdigest(),"input_save":str(save),"input_save_sha256":hashlib.sha256(save.read_bytes()).hexdigest(),"emulator":"py-desmume","captures":[],"status":"awaiting_visual_review"}
    print("READY",flush=True)
    for index,line in enumerate(commands,1):
        if not line.strip():continue
        command=json.loads(line)
        if command.get("stop"):break
        name=command.get("name",f"{index:03d}");start=total
        with open("inputs.jsonl","a") as log:log.write(json.dumps(command)+"\n")
        for item in command.get("keys",[]):key(*(item if isinstance(item,list) else [item]))
        for item in command.get("touches",[]):touch(*item)
        if "capture" in command:
            capture=command["capture"];direction=capture["direction"]
            held=capture.get("hold",64);interval=capture.get("sample_every",2)
            folder=Path(name);folder.mkdir(exist_ok=False)
            mask=keymask(getattr(Keys,"KEY_"+direction));emulator.input.keypad_add_key(mask)
            pictures=[];ticks=[]
            for tick in range(held):
                frames(1)
                if tick%interval==0:
                    image=emulator.screenshot().crop((0,0,256,192)).convert("RGB")
                    image.save(folder/f"{tick:03d}.png");pictures.append(image);ticks.append(total)
            emulator.input.keypad_rm_key(mask);frames(capture.get("wait",90))
            pictures[0].save(f"{name}.gif",save_all=True,append_images=pictures[1:],duration=round(interval*1000/60),loop=0)
            count=min(12,len(pictures))
            selected=sorted({round(i*(len(pictures)-1)/max(1,count-1)) for i in range(count)})
            contact=Image.new("RGB",(256*4,212*((len(selected)+3)//4)),"#eee")
            draw=ImageDraw.Draw(contact)
            for position,picture_index in enumerate(selected):
                x=(position%4)*256;y=(position//4)*212
                contact.paste(pictures[picture_index],(x,y));draw.text((x+5,y+194),f"{direction} tick {ticks[picture_index]}",fill="black")
            contact.save(f"{name}-frames.png")
            report["captures"].append({"name":name,"direction":direction,"hold":held,"sample_every":interval,"frame_count":len(pictures),"frames":ticks})
        frames(command.get("frames",0));emulator.screenshot().save(name+".png")
        if command.get("save"):assert emulator.backup.export_file(command["save"])
        if command.get("state"):emulator.savestate.save_file(command["state"])
        report["total_emulated_frames"]=total
        (out/"run.json").write_text(json.dumps(report,indent=2)+"\n")
        print(f"DONE {name} frames={start}..{total}",flush=True)
    print("FINISHED; inspect captured frames/GIFs before making behavior claims.",flush=True)


if __name__ == "__main__":main()
