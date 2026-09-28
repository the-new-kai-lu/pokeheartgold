#!/usr/bin/env python3
"""Outline all 88 custom follower frames at native pixel resolution.

Only transparent pixels neighboring a non-outline colored pixel are filled with
existing palette index 1. Existing black contours are not expanded again.
The approved poses and registration are read from a fixed commit. Both RGB555
palettes and all NSBTX metadata are preserved. Default output is staging only.
"""
import argparse,hashlib,io,json,struct,subprocess
from pathlib import Path
from PIL import Image,ImageDraw,ImageOps
from pack_fakemon_followers import FAMILIES,btx_layout,pack_btx,expand
ROOT=Path(__file__).resolve().parents[2]
BASELINE='2f1519a8f'
NEIGHBORS=[(dx,dy) for dy in (-1,0,1) for dx in (-1,0,1) if dx or dy]
def original(path):return subprocess.check_output(['git','show',BASELINE+':'+path],cwd=ROOT)
def outline_frame(frame):
 assert frame.mode=='P' and frame.width==frame.height and frame.width in (32,64)
 result=frame.copy();s=frame.width
 for y in range(s):
  for x in range(s):
   if frame.getpixel((x,y)) in (0,1):continue
   assert 0<x<s-1 and 0<y<s-1,(x,y,'no margin for full outline')
   for dx,dy in NEIGHBORS:
    point=(x+dx,y+dy)
    if frame.getpixel(point)==0:result.putpixel(point,1)
 return result

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--output',type=Path,required=True);args=ap.parse_args();out=args.output;out.mkdir(parents=True,exist_ok=True)
 preview=[Image.new('RGB',(1280,1650),'#4b9362') for _ in range(2)];animated=[Image.new('RGB',(720,1650),'#4b9362') for _ in range(2)]
 checks={};keys=[k for group in FAMILIES.values() for k in group]
 for row,key in enumerate(keys):
  native=original(f'files/fakemon/{key}/follower.bin');records,pa=btx_layout(native)
  palettes=[[[v&31,v>>5&31,v>>10&31] for v in struct.unpack_from('<16H',native,pa+32*i)] for i in range(2)]
  assert all(sum(p[1])==min(sum(c) for c in p[1:]) for p in palettes)
  sheet=Image.open(io.BytesIO(original(f'files/fakemon/{key}/source/overworld.png')));s=sheet.width
  before=[sheet.crop((0,s*i,s,s*(i+1))) for i in range(8)];frames=[outline_frame(f) for f in before]
  for a,b in zip(before,frames):
   assert outline_frame(b).tobytes()==b.tobytes()
   assert all(x==y or (x==0 and y==1) for x,y in zip(a.tobytes(),b.tobytes()))
  assert all(frames[6+i].tobytes()==ImageOps.mirror(frames[4+i]).tobytes() for i in range(2))
  packed=pack_btx(native,frames,palettes)
  assert packed[pa:]==native[pa:] and len(packed)==len(native)
  # All bytes outside the texture payloads (including dictionaries and palettes) stay exact.
  allowed=set(j for _,_,_,a,b in records for j in range(a,b))
  assert all(a==b or i in allowed for i,(a,b) in enumerate(zip(native,packed)))
  folder=out/key;(folder/'source').mkdir(parents=True,exist_ok=True);(folder/'follower.bin').write_bytes(packed)
  result=Image.new('P',sheet.size);result.putpalette(sheet.getpalette())
  for i,frame in enumerate(frames):result.paste(frame,(0,s*i))
  result.save(folder/'source/overworld.png',transparency=0)
  for variant,palette in enumerate(palettes):
   draw=ImageDraw.Draw(preview[variant]);draw.text((5,row*150+4),key,fill='white')
   for i,frame in enumerate(frames):
    im=frame.copy();im.putpalette(expand(palette));im.info['transparency']=0
    rgba=im.convert('RGBA').resize((s*2,s*2),Image.Resampling.NEAREST)
    preview[variant].paste(rgba,(i*160+16,row*150+148-s*2),rgba)
    if variant==0:
     animated[i%2].paste(rgba,((i//2)*180+16,row*150+148-s*2),rgba)
     ImageDraw.Draw(animated[i%2]).text((5,row*150+4),key,fill='white')
  checks[key]={'sha256':hashlib.sha256(packed).hexdigest(),'added_pixels_by_frame':[sum(x!=y for x,y in zip(a.tobytes(),b.tobytes())) for a,b in zip(before,frames)],'existing_pixels_unchanged':True,'both_palettes_and_metadata_unchanged':True,'no_outline_clipping':True,'idempotent':True,'east_west_mirrors':True}
 for variant,name in enumerate(['normal','shiny']):preview[variant].save(out/f'all-frames-{name}.png')
 animated[0].save(out/'walking.gif',save_all=True,append_images=animated[1:],duration=160,loop=0)
 (out/'checks.json').write_text(json.dumps(checks,indent=2)+'\n');print('Outlined all 88 frames; original pixels, palettes and metadata preserved.')
if __name__=='__main__':main()
