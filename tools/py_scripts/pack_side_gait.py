#!/usr/bin/env python3
"""Pack reviewed generated leg poses while preserving original follower bodies.

Only west/east frames change. In each pair the original west-A upper body and
tail stay fixed; an explicitly bounded leg crop supplies the generated contact
poses. Original north/south frames and both native RGB555 palettes are retained.
This script performs crop/registration/quantization/native serialization only.
"""
import argparse
import hashlib
import io
import json
import subprocess
from pathlib import Path
from PIL import Image, ImageChops, ImageDraw, ImageOps
from pack_fakemon_followers import FAMILIES, btx_layout, pack_btx, quantize, expand
import struct

ROOT = Path(__file__).resolve().parents[2]
ART = ROOT / "documentation/fakemon/side-gait"
BASELINE = "c020456f4"


def original(path):
    return subprocess.check_output(["git", "show", f"{BASELINE}:{path}"], cwd=ROOT)


def pack(output):
    layout = json.loads((ART / "layout.json").read_text())
    output.mkdir(parents=True, exist_ok=True)
    preview = [Image.new("RGBA", (520, 11*180), "#bdc8cd") for _ in range(2)]
    report = {}
    row = 0
    for family, keys in FAMILIES.items():
        art = Image.open(ART / (family + "-steps.png")).convert("RGBA")
        cw, ch = art.width // 2, art.height // len(keys)
        for n, key in enumerate(keys):
            info = layout[key]
            native = original(f"files/fakemon/{key}/follower.bin")
            records, palette_at = btx_layout(native)
            palettes = []
            for k in range(2):
                values = struct.unpack_from("<16H", native, palette_at + k*32)
                palettes.append([[v&31, v>>5&31, v>>10&31] for v in values])
            source = Image.open(io.BytesIO(original(f"files/fakemon/{key}/source/overworld.png")))
            size = source.width
            frames = [source.crop((0, size*i, size, size*(i+1))) for i in range(8)]
            anchor = frames[4]
            box, region = tuple(info["destination"]), tuple(info["leg_region"])
            assert anchor.getbbox() == box
            for phase in range(2):
                cell = art.crop((phase*cw, n*ch, (phase+1)*cw, (n+1)*ch))
                cell.putalpha(cell.getchannel("A").point(lambda a: 255 if a >= 160 else 0))
                fitted = cell.crop(info["source_union"]).resize((box[2]-box[0],box[3]-box[1]), Image.Resampling.LANCZOS)
                canvas = Image.new("RGBA", (size,size))
                canvas.paste(fitted,box[:2])
                indexed = quantize(canvas,palettes[0])
                frame = anchor.copy()
                frame.paste(indexed.crop(region),region[:2])
                frames[4+phase] = frame
                frames[6+phase] = ImageOps.mirror(frame)
                d = ImageDraw.Draw(preview[phase])
                d.text((8,row*180+8),key,fill="black")
                for column, current in enumerate((frame,frames[6+phase])):
                    im = current.convert("RGBA")
                    im = im.crop(im.getbbox())
                    im = im.resize((im.width*3,im.height*3),Image.Resampling.NEAREST)
                    preview[phase].alpha_composite(im,(160+column*170,row*180+36))
            different = sum(a != b for a,b in zip(frames[4].tobytes(),frames[5].tobytes()))
            assert different >= 6, (key,"step collapsed at native resolution")
            result = pack_btx(native,frames,palettes)
            for i,(_,w,h,start,end) in enumerate(records):
                if i < 4:
                    assert result[start:end] == native[start:end]
            assert result[palette_at:] == native[palette_at:]
            # No upper-body or tail jitter: every A/B difference is inside the leg crop.
            for y in range(size):
                for x in range(size):
                    if not (region[0] <= x < region[2] and region[1] <= y < region[3]):
                        assert frames[4].getpixel((x,y)) == frames[5].getpixel((x,y)) == anchor.getpixel((x,y))
            folder = output / key
            (folder/"source").mkdir(parents=True,exist_ok=True)
            (folder/"follower.bin").write_bytes(result)
            sheet = Image.new("P",(size,size*8));sheet.putpalette(expand(palettes[0]))
            for i,frame in enumerate(frames):sheet.paste(frame,(0,i*size))
            sheet.save(folder/"source/overworld.png",transparency=0)
            report[key] = {"changed_step_pixels":different,"sha256":hashlib.sha256(result).hexdigest(),
                           "north_south_unchanged":True,"palettes_unchanged":True,"body_locked":True}
            row += 1
    for phase,p in enumerate(preview):p.convert("RGB").save(output/f"steps-{phase}.png")
    preview[0].convert("RGB").save(output/"steps.gif",save_all=True,append_images=[preview[1].convert("RGB")],duration=240,loop=0)
    (output/"checks.json").write_text(json.dumps(report,indent=2)+"\n")
    print(json.dumps(report,indent=2))

if __name__ == "__main__":
    parser=argparse.ArgumentParser();parser.add_argument("--output",type=Path,required=True)
    pack(parser.parse_args().output)
