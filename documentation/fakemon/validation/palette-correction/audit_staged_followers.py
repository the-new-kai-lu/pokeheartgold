#!/usr/bin/env python3
"""Read-only staged follower color audit; renders native data, never edits game assets."""
import argparse, collections, hashlib, json, subprocess
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
from ndspy.texture import NSBTX

ROOT = Path(__file__).resolve().parents[4]
ORIGINAL_REF = "8f94b0e256f6f81caea28d5f280fe82862d1892a"
CANONICAL = {"pikachu":322,"cyndaquil":454,"pidgey":313,"spheal":693}

def read_tex(data):
    return NSBTX(data)

def colors(tex, shiny=0):
    return [list(c[:3]) for c in tex.palettes[shiny][1].colors]

def indices(texture):
    assert texture.width * texture.height // 2 == len(texture.data1)
    return [i for value in texture.data1 for i in (value & 15, value >> 4)]

def luma(c):
    return sum(v*w for v,w in zip(c,[.2126,.7152,.0722]))

def metrics(tex, shiny, effect_range=None):
    counts = collections.Counter(i for _,t in tex.textures for i in indices(t) if i)
    pal = colors(tex,shiny)
    n = sum(counts.values())
    result = {"visible_pixels_all_eight_frames":n,"mean_visible_luma_rgb555":round(sum(luma(pal[i])*v for i,v in counts.items())/n,4),"bright_pixels_luma_at_least_24_percent":round(sum(v for i,v in counts.items() if luma(pal[i])>=24)*100/n,3),"palette_rgb555":pal,"visible_index_histogram":dict(sorted(counts.items()))}
    if effect_range:
        effect_n = sum(counts[i] for i in effect_range)
        result["effect_mean_luma_rgb555"] = round(sum(luma(pal[i])*counts[i] for i in effect_range)/effect_n,4)
        result["effect_visible_percent"] = round(100*effect_n/n,3)
    return result

def frame(tex, shiny, index):
    texture = tex.textures[index][1]; pal=colors(tex,shiny)
    image=Image.new("RGBA",(texture.width,texture.height))
    image.putdata([tuple(v*255//31 for v in pal[i])+(255 if i else 0,) for i in indices(texture)])
    return image

def main():
    ap=argparse.ArgumentParser();ap.add_argument("--staging",type=Path,default=Path("/tmp/fakemon-followers-review"));ap.add_argument("--output",type=Path,default=Path(__file__).parent);args=ap.parse_args()
    plan=json.loads((ROOT/"files/fakemon/palette-corrections.json").read_text())
    groups={key:g for g in plan["groups"] for key in g["species"]}
    originals={}; staged={}; stock={}; entries={}
    for path in sorted(args.staging.glob("*/follower.bin")):
        key=path.parent.name
        old=subprocess.check_output(["git","show",f"{ORIGINAL_REF}:files/fakemon/{key}/follower.bin"],cwd=ROOT)
        new=path.read_bytes();originals[key]=read_tex(old);staged[key]=read_tex(new)
        rows=[]
        for shiny in (0,1):
            group=groups.get(key)
            expected=group["palettes"][shiny]["after_rgb555"] if group else colors(originals[key],shiny)
            assert colors(staged[key],shiny)==expected,(key,shiny,"wrong staged palette")
            effect_range=range(5,11) if group and group["family"]=="electric" else range(6,13) if group and group["family"]=="fire" else range(8,13) if group else None
            old_m=metrics(originals[key],shiny,effect_range);new_m=metrics(staged[key],shiny,effect_range)
            rows.append({"variant":"shiny" if shiny else "normal","original":old_m,"staged":new_m,"mean_visible_luma_change_percent":round(100*(new_m["mean_visible_luma_rgb555"]/old_m["mean_visible_luma_rgb555"]-1),3)})
        entries[key]={"staged_sha256":hashlib.sha256(new).hexdigest(),"original_sha256":hashlib.sha256(old).hexdigest(),"palettes_match_reviewed_plan":True,"variants":rows}
    canonical={}
    for key,idx in CANONICAL.items():
        data=(ROOT/f"files/data/mmodel/mmodel/mmodel_{idx:08}.NSBTX").read_bytes(); stock[key]=read_tex(data)
        canonical[key]={"mmodel_index":idx,"sha256":hashlib.sha256(data).hexdigest(),"normal":metrics(stock[key],0),"shiny":metrics(stock[key],1)}
    font=ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",17)
    small=ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",14)
    image=Image.new("RGB",(1135,1060),"#e5e6e1");draw=ImageDraw.Draw(image)
    draw.text((18,12),"Native follower comparison: original / staged revision / canonical",font=font,fill="black")
    draw.text((18,39),"Each group: north, south, west. Same 3x native-pixel scale; all images decoded directly from NSBTX.",font=small,fill="#303630")
    for x,label in [(180,"Original"),(500,"Staged revision"),(820,"Canonical reference")]:
        draw.text((x,72),label,font=font,fill="black")
    for row,(key,donor) in enumerate([("voltuff","pikachu"),("embernewt","cyndaquil"),("sedgling","pidgey")]):
        for shiny in (0,1):
            y=104+(row*2+shiny)*152
            draw.text((15,y+23),key.upper(),font=font,fill="black")
            draw.text((15,y+49),"SHINY" if shiny else "NORMAL",font=small,fill="#414441")
            for col,tex in enumerate([originals[key],staged[key],stock[donor]]):
                x=180+col*320
                if col==2:draw.text((x,y-2),donor.upper(),font=small,fill="#303630")
                for i,native_index in enumerate([0,2,4]):
                    f=frame(tex,shiny,native_index)
                    assert f.size==(32,32)
                    f=f.resize((96,96),Image.Resampling.NEAREST)
                    draw.rectangle((x+i*100,y+18,x+i*100+95,y+113),fill="#d0d8cc")
                    image.paste(f,(x+i*100,y+18),f)
    draw.text((18,1026),"Battle and follower palettes differ in stock HGSS; the fire comparison uses Cyndaquil's actual follower colors.",font=small,fill="#303630")
    image.save(args.output/"staged-base-three-native-comparison.png")
    report={"original_ref":ORIGINAL_REF,"staging":str(args.staging),"palette_variants_verified":len(entries)*2,"species":entries,"canonical":canonical,"notes":["The staged geometry and color-index distribution differ from the original: total luminance changes are not palette-only measures.","Pikachu follower yellow is (31,26,10), while revised Voltuff main yellow is (30,23,4).","Revised Embernewt flame reds/orange now exactly use Cyndaquil follower (16,3,3)/(20,5,5)/(26,7,6)/(30,20,2) instead of its more saturated battle colors.","All staged normal and shiny palette values exactly match the reviewed plan, including the unchanged bird palettes."]}
    (args.output/"staged-native-color-audit.json").write_text(json.dumps(report,indent=2)+"\n")
    print(f"Verified {len(entries)*2} palette variants from native staged models.")
    for key in ("voltuff","embernewt","rimevaran","sedgling"):
        v=entries[key]["variants"][0];print(key,v["original"]["mean_visible_luma_rgb555"],v["staged"]["mean_visible_luma_rgb555"],v["mean_visible_luma_change_percent"])

if __name__=="__main__":main()
