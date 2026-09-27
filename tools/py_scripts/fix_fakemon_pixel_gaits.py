#!/usr/bin/env python3
"""Hand-authored native-pixel side gaits, authorized by the user.

Reads immutable pre-regression art. Replaces complete articulated leg layers;
keeps north/south frames, canvas registration and both RGB555 palettes exact.
Outputs staging files only. No generated/resampled leg strips are used.
"""
import argparse, io, json, hashlib, subprocess, struct
from pathlib import Path
from PIL import Image, ImageDraw, ImageOps
from pack_fakemon_followers import FAMILIES, btx_layout, pack_btx, expand
ROOT=Path(__file__).resolve().parents[2]
BASELINE='c020456f4'
# Hip coordinates, floor, stride, leg width, rectangles erasing the old legs.
BIPEDS={
 'voltuff': ((14,24),(17,24),29,3,3,[(10,25,20,30)]),
 'surguenon': ((13,22),(16,22),29,4,3,[(8,23,20,30)]),
 'raijinque': ((27,52),(31,52),61,5,4,[(19,53,36,62)]),
 'sedgling': ((13,26),(16,26),29,2,2,[(9,26,19,30)]),
 'cragaviar': ((13,24),(17,24),29,3,2,[(9,25,20,30)]),
 'ragnaroc': ((24,52),(29,52),61,5,3,[(17,53,35,62)]),
}
QUADS={
 'embernewt': ((10,25),(18,26),29,2,2,[(8,26,14,30),(16,27,22,30)]),
 'pyrovaran': ((10,24),(20,25),29,3,3,[(6,25,14,30),(17,27,24,30)]),
 'magmalisk': ((25,54),(38,55),61,4,4,[(18,55,29,62),(33,57,43,62)]),
 'rimevaran': ((11,24),(22,25),29,3,3,[(6,25,15,30),(18,26,25,30)]),
 'fimbulisk': ((24,54),(38,55),61,4,4,[(18,55,29,62),(33,57,43,62)]),
}
def original(path):
 return subprocess.check_output(['git','show',BASELINE+':'+path],cwd=ROOT)
def stroke(layer,hip,ankle,width,near,electric=False,quadruped=False):
 """Articulated hip/knee/ankle and a separate toe. Palette indices only."""
 draw=ImageDraw.Draw(layer)
 hx,hy=hip; ax,ay=ankle
 # Knee leads the shin; feet retain their width and point toward travel.
 knee=(hx+(ax-hx)//2,hy+max(1,(ay-hy)//2))
 points=[hip,knee,ankle]
 draw.line(points,fill=1,width=width,joint='curve')
 if near:
  draw.line(points,fill=4 if not electric else 3,width=max(1,width-2),joint='curve')
  if electric:draw.line([hip,knee],fill=8,width=max(1,width-2))
 else:
  draw.line(points,fill=2,width=max(1,width-2))
  if electric:draw.line([hip,knee],fill=5,width=max(1,width-2))
 toe=max(2,width)
 draw.rectangle((ax-toe+1,ay-(width>=3),ax+1,ay),fill=1)
 if near:draw.line([(ax-toe+2,ay-1 if width>=3 else ay),(ax,ay-1 if width>=3 else ay)],fill=3,width=1)
 return {'hip':hip,'knee':knee,'ankle':ankle,'near':near}
def make_pair(key,anchor):
 s=anchor.width;electric=key in FAMILIES['electric'];poses=[];records=[]
 if key in BIPEDS:
  nearhip,farhip,floor,stride,width,erase=BIPEDS[key]
 else:
  fore,hind,floor,stride,width,erase=QUADS[key]
 body=anchor.copy();draw=ImageDraw.Draw(body)
 for x0,y0,x1,y1 in erase:draw.rectangle((x0,y0,x1-1,y1-1),fill=0)
 for phase in range(2):
  far=Image.new('P',(s,s));near=Image.new('P',(s,s));joints=[]
  sign=-1 if phase==0 else 1
  if key in BIPEDS:
   # Near foot plants forward in A, swings behind in B; far does the reverse.
   center=(nearhip[0]+farhip[0])//2
   joints.append(stroke(far,(center,farhip[1]),(center-sign*stride,floor-(phase==0)),width,False,electric))
   joints.append(stroke(near,(center,nearhip[1]),(center+sign*stride,floor-(phase==1)),width,True,electric))
  else:
   # Diagonal contact pairs, with opposite near fore/hind travel.
   for hip,travel in [(fore,sign),(hind,-sign)]:
    fhip=(hip[0]+1,hip[1])
    joints.append(stroke(far,fhip,(fhip[0]-travel*stride,floor-1),max(2,width-1),False,quadruped=True))
    joints.append(stroke(near,hip,(hip[0]+travel*stride,floor-(phase==1 and hip==fore)),width,True,quadruped=True))
  frame=far.copy();frame.putpalette(anchor.getpalette())
  frame.paste(body,(0,0),body.point(lambda x:255 if x else 0, 'L'))
  frame.paste(near,(0,0),near.point(lambda x:255 if x else 0, 'L'))
  ImageDraw.Draw(frame).rectangle((0,floor+1,s-1,s-1),fill=0)
  assert frame.getbbox()[3] == floor+1
  poses.append(frame);records.append(joints)
 return poses,records

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--output',type=Path,required=True);args=ap.parse_args();out=args.output;out.mkdir(parents=True,exist_ok=True)
 previews=[Image.new('RGB',(660,180*11),'#bdc8cd') for _ in range(2)];report={}
 for row,key in enumerate(k for group in FAMILIES.values() for k in group):
  native=original(f'files/fakemon/{key}/follower.bin');rec,pa=btx_layout(native)
  palettes=[[[v&31,v>>5&31,v>>10&31] for v in struct.unpack_from('<16H',native,pa+32*i)] for i in range(2)]
  source=Image.open(io.BytesIO(original(f'files/fakemon/{key}/source/overworld.png')));s=source.width
  frames=[source.crop((0,s*i,s,s*(i+1))) for i in range(8)]
  pair,joints=make_pair(key,frames[4]);frames[4:6]=pair;frames[6:8]=[ImageOps.mirror(im) for im in pair]
  result=pack_btx(native,frames,palettes)
  assert result[pa:]==native[pa:]
  for _,_,_,a,b in rec[:4]:assert result[a:b]==native[a:b]
  folder=out/key;(folder/'source').mkdir(parents=True,exist_ok=True)
  (folder/'follower.bin').write_bytes(result)
  sheet=Image.new('P',(s,s*8));sheet.putpalette(expand(palettes[0]))
  for i,im in enumerate(frames):sheet.paste(im,(0,s*i))
  sheet.save(folder/'source/overworld.png',transparency=0)
  for phase in range(2):
   draw=ImageDraw.Draw(previews[phase]);draw.text((8,row*180+5),key,fill='black')
   for col,im in enumerate([frames[4+phase],frames[6+phase]]):
    rgba=im.convert('RGBA');rgba.putalpha(im.point(lambda x:255 if x else 0, 'L'))
    # Fixed canvas origin, never crop each phase independently.
    rgba=rgba.resize((s*3,s*3),Image.Resampling.NEAREST)
    previews[phase].paste(rgba,(120+col*250,row*180+174-s*3),rgba)
  report[key]={'sha256':hashlib.sha256(result).hexdigest(),'joints':joints,'palettes_unchanged':True,'north_south_unchanged':True}
 for phase,im in enumerate(previews):im.save(out/f'phase-{phase}.png')
 previews[0].save(out/'walking.gif',save_all=True,append_images=previews[1:],duration=160,loop=0)
 (out/'checks.json').write_text(json.dumps(report,indent=2)+'\n')
 print('Packed eleven hand-authored native-pixel gait pairs.')
if __name__=='__main__':main()
