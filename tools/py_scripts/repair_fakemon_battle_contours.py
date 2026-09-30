#!/usr/bin/env python3
"""Repair clipped battle anatomy and add one-native-pixel battle contours.

User-authorized indexed pixel editing; staging only. Preserve both RGB555
palettes, NCGR headers/keys, genders, facing and two-frame order. Uses pinned
pre-edit sources so repeated runs cannot accumulate thicker outlines.
"""
import argparse,io,json,struct,subprocess
from pathlib import Path
from PIL import Image,ImageDraw
from revise_fakemon_backs_and_gaits import scale2x,remove_clipped_fragments,CAMERAS,mask,rgba
ROOT=Path(__file__).resolve().parents[2]
BASE='2f1f8db77';BACK_BASE='ece5bf66b'
CAMERA=dict(CAMERAS)
CAMERA.update(surguenon=(1.62,42,12),raijinque=(1.30,40,4),embernewt=(1.55,40,29),pyrovaran=(1.80,52,25),magmalisk=(1.70,54,17),rimevaran=(1.80,49,24))
KEYS=list(CAMERA)
DIRS=[(-1,0),(1,0),(0,-1),(0,1)]

def original(path,base=BASE):return subprocess.check_output(['git','show',base+':'+path],cwd=ROOT)
def indexed(path,base=BASE):return Image.open(io.BytesIO(original(path,base)))
def battle_palette(key,variant):
 return [c for v in struct.unpack_from('<16H',original(f'files/fakemon/{key}/battle-{4+variant}.bin'),40) for c in ((v&31)*255//31,((v>>5)&31)*255//31,((v>>10)&31)*255//31)]

def compose_back(src,key):
 sc,cx,top=CAMERA[key];big=scale2x(src);result=Image.new('P',(80,80));result.putpalette(src.getpalette())
 if key=='ragnaroc':
  # Re-pose the full wings in a more upright arc, retaining the enlarged neck.
  # Source/destination x knots keep both complete tips within the native frame.
  knots=[(2,3),(26,18),(53,61),(78,76)]
  for y in range(77):
   sy=(y-6)/1.5+4
   if not 0<=sy<80:continue
   for x in range(80):
    for (a,b),(c,d) in zip(knots,knots[1:]):
     if b<=x<=d:
      sx=a+(x-b)*(c-a)/(d-b)
      result.putpixel((x,y),big.getpixel((int(sx*2),int(sy*2))));break
 else:
  yscale=1.75 if key=='embernewt' else sc
  big=big.resize((round(80*sc),round(80*yscale)),Image.Resampling.NEAREST)
  result.paste(big,(round(40-cx*sc),round(6-top*yscale)))
  ImageDraw.Draw(result).rectangle((0,77,79,79),fill=0)
  remove_clipped_fragments(result)
 return result

def repair_throat(frames,key):
 # Restore an absent cheek/lower-jaw/throat surface from the same species'
 # intact alternate pose. Only the documented anatomical region is touched.
 if key=='fimbulisk':recipient,donor,box=0,1,(62,39,76,51)
 elif key=='rimevaran':recipient,donor,box=1,0,(56,38,75,56)
 else:return 0
 count=0;a=frames[recipient];b=frames[donor]
 for y in range(box[1],box[3]):
  for x in range(box[0],box[2]):
   if a.getpixel((x,y))==0 and b.getpixel((x,y))!=0:
    a.putpixel((x,y),b.getpixel((x,y)));count+=1
 return count

# Paths lie on anatomical folds, not all color transitions. One native pixel.
# Bird wing roots and electric shoulders/forearms need explicit separation
# because adjacent body parts can share the same palette ramp.
SEAMS={
 ('voltuff','front'):[[(30,49),(31,52),(30,55)],[(44,49),(43,53),(45,56)]],
 ('voltuff','back'):[[(50,47),(54,48),(57,51)],[(38,52),(36,58),(33,62)]],
 ('surguenon','front'):[[(27,35),(29,38),(27,42)],[(44,38),(46,43),(48,45)],[(32,51),(35,54),(37,53)]],
 ('surguenon','back'):[[(32,48),(30,53),(32,58)],[(51,53),(55,56),(57,61)]],
 ('raijinque','front'):[[(21,37),(24,40),(25,44)],[(50,37),(48,41),(49,45)],[(29,52),(33,55),(37,54)]],
 ('raijinque','back'):[[(22,49),(26,52),(27,56)],[(49,49),(46,53),(46,58)]],
 ('sedgling','front'):[[(43,56),(45,59),(44,63),(40,65)]],
 ('sedgling','back'):[[(41,60),(47,58),(55,61),(59,65)],[(30,62),(32,67),(30,70)]],
 ('cragaviar','front'):[[(38,46),(43,46),(49,50),(54,53)],[(45,55),(49,57),(52,59)]],
 ('cragaviar','back'):[[(27,67),(33,64),(39,66),(45,69)],[(19,70),(24,72),(30,73)]],
 ('ragnaroc','front'):[[(13,32),(17,36),(22,39),(27,40)],[(49,40),(54,36),(59,31)],[(12,51),(18,49),(25,51),(29,55)],[(49,51),(55,50),(62,53),(67,58)]],
 ('ragnaroc','back'):[[(10,45),(13,51),(19,56),(27,59),(32,60)],[(68,43),(67,49),(65,55),(62,61)],[(21,67),(28,66),(35,68),(41,72)]],
}
NECK_BOXES={
 ('sedgling','front'):(28,40,43,61),('sedgling','back'):(43,28,69,55),
 ('cragaviar','front'):(27,26,43,60),('cragaviar','back'):(38,26,66,69),
 ('ragnaroc','front'):(30,24,47,54),('ragnaroc','back'):(43,25,63,71),
}

def anatomical_seams(src,key,facing):
 result=src.copy();p=src.load();q=result.load()
 electric=key in ('voltuff','surguenon','raijinque');ice=key in ('rimevaran','fimbulisk');fire=key in ('embernewt','pyrovaran','magmalisk')
 # Body/element interfaces: ice facets and flame interiors keep their colors.
 if electric:body={2,3,4};element=set(range(5,16))
 elif ice:body={2,3,4,5};element={8,9,10,11,12}
 elif fire:body={2,3,4,5};element={6,7,8,9,10,11,12}
 else:body=set();element=set()
 for y in range(1,79):
  for x in range(1,79):
   if p[x,y] in body and any(p[x+dx,y+dy] in element for dx,dy in DIRS):q[x,y]=1
 box=NECK_BOXES.get((key,facing))
 if box:
  for y in range(box[1],box[3]):
   for x in range(box[0],box[2]):
    if p[x,y] in (2,3,4,5,6,7,8) and any(p[x+dx,y+dy] in (12,13) for dx,dy in DIRS):q[x,y]=1
 # Paths are clipped to the existing body so no floating dark marks can appear.
 stencil=Image.new('1',src.size);d=ImageDraw.Draw(stencil)
 for path in SEAMS.get((key,facing),[]):d.line(path,fill=1,width=1)
 for y in range(80):
  for x in range(80):
   if stencil.getpixel((x,y)) and p[x,y]!=0:q[x,y]=1
 return result

def contour(src):
 # Four-neighbor contour produces a single native-pixel line. Existing darkest
 # edge pixels are not dilated, preventing a second thick black ring.
 result=src.copy()
 for y in range(80):
  for x in range(80):
   if src.getpixel((x,y)) in (0,1):continue
   for dx,dy in DIRS:
    xx,yy=x+dx,y+dy
    if 0<=xx<80 and 0<=yy<80 and src.getpixel((xx,yy))==0:result.putpixel((xx,yy),1)
 return result

def cleanup_fragments(src,key,facing):
 # Remove detached dark specks, plus the cropped tail island beside Raijinque.
 result=src.copy();seen=set();groups=[]
 for y in range(80):
  for x in range(80):
   if src.getpixel((x,y))==0 or (x,y) in seen:continue
   group={(x,y)};todo=[(x,y)];seen.add((x,y))
   while todo:
    xx,yy=todo.pop()
    for dy in (-1,0,1):
     for dx in (-1,0,1):
      nx,ny=xx+dx,yy+dy
      if 0<=nx<80 and 0<=ny<80 and (nx,ny) not in seen and src.getpixel((nx,ny)):
       seen.add((nx,ny));group.add((nx,ny));todo.append((nx,ny))
   groups.append(group)
 largest=max(groups,key=len)
 for group in groups:
  if group is largest:continue
  dark_speck=len(group)<=12 and all(src.getpixel(point) in (1,2,3) for point in group)
  tail_island=key=='raijinque' and facing=='back' and any(y==76 for x,y in group)
  if dark_speck or tail_island:
   for point in group:result.putpixel(point,0)
 return result

def inset_sides(src):
 # The bottom is an intentional torso crop. Side/top borders must have room
 # for a contour; any small lower-body edge is inset without moving the head.
 result=src.copy()
 for y in range(80):
  if result.getpixel((0,y))!=0:result.putpixel((1,y),result.getpixel((0,y)));result.putpixel((0,y),0)
  if result.getpixel((79,y))!=0:result.putpixel((78,y),result.getpixel((79,y)));result.putpixel((79,y),0)
 return result

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--output',type=Path,required=True);args=ap.parse_args();out=args.output;out.mkdir(parents=True,exist_ok=True)
 previews=[Image.new('RGB',(1000,len(KEYS)*260),'#99b897') for _ in range(2)];beforeafter=Image.new('RGB',(1000,len(KEYS)*260),'#99b897');checks={}
 for row,key in enumerate(KEYS):
  folder=out/key;checks[key]={}
  for gender in ['female','male']:
   back_source=indexed(f'files/fakemon/{key}/source/{gender}/back.png',BACK_BASE)
   backs=[compose_back(back_source.crop((i*80,0,(i+1)*80,80)),key) for i in range(2)]
   repair_count=repair_throat(backs,key)
   for facing in ['back','front']:
    source=indexed(f'files/fakemon/{key}/source/{gender}/{facing}.png');result=source.copy();frames=[]
    for i in range(2):
     src=backs[i] if facing=='back' else source.crop((i*80,0,(i+1)*80,80))
     frame=contour(anatomical_seams(cleanup_fragments(inset_sides(src),key,facing),key,facing));frames.append(frame);result.paste(frame,(i*80,0))
     assert max(frame.tobytes())<16
     assert contour(frame).tobytes()==frame.tobytes(),(key,facing,i,'outline not idempotent')
     if key=='ragnaroc' and facing=='back':
      bounds=mask(frame).getbbox();assert bounds[0]>=2 and bounds[2]<=78 and bounds[1]>=2,(key,i,'wing contour clipped')
     # No colored pixels can be clipped at the top or side canvas boundary.
     assert all(frame.getpixel((x,0)) in (0,1) for x in range(80)),(key,facing,i,'top')
     assert all(frame.getpixel((x,y)) in (0,1) for x in (0,79) for y in range(80)),(key,facing,i,'sides')
    target=folder/'source'/gender/f'{facing}.png';target.parent.mkdir(parents=True,exist_ok=True);result.save(target,transparency=0);target.with_suffix('.png.key').write_bytes(original(f'files/fakemon/{key}/source/{gender}/{facing}.png.key'))
    member=(0 if facing=='back' else 2)+(gender=='male');native=folder/f'battle-{member}.NCGR'
    subprocess.run([str(ROOT/'tools/nitrogfx/nitrogfx'),str(target),str(native),'-scanfronttoback','-handleempty'],check=True)
    blob=native.read_bytes();old=original(f'files/fakemon/{key}/battle-{member}.bin');assert len(blob)==len(old) and blob[:48]==old[:48]
    decoded=folder/'decoded.png';subprocess.run([str(ROOT/'tools/nitrogfx/nitrogfx'),str(native),str(decoded),'-scanfronttoback','-width','20'],check=True)
    assert bytes(15-v//17 for v in Image.open(decoded).convert('L').tobytes())==result.tobytes()
    native.rename(folder/f'battle-{member}.bin');decoded.unlink();decoded.with_suffix('.png.key').unlink(missing_ok=True)
    checks[key][gender+'_'+facing]={'native_roundtrip':True,'header_and_key_unchanged':True,'bounds':[mask(f).getbbox() for f in frames],'restored_throat_pixels':repair_count if facing=='back' else 0}
    if gender=='male':
     for variant in range(2):
      palette=battle_palette(key,variant)
      for i,frame in enumerate(frames):
       frame=frame.copy();frame.putpalette(palette);render=rgba(frame).resize((240,240),Image.Resampling.NEAREST);col=(2 if facing=='back' else 0)+i;previews[variant].paste(render,(col*250,row*260+18),render)
     if facing=='back':
      for i in range(2):
       for j,f in enumerate([source.crop((i*80,0,(i+1)*80,80)),frames[i]]):
        f=f.copy();f.putpalette(battle_palette(key,0));render=rgba(f).resize((240,240),Image.Resampling.NEAREST);beforeafter.paste(render,((i*2+j)*250,row*260+18),render)
  for im in previews+[beforeafter]:ImageDraw.Draw(im).text((4,row*260+3),key,fill='black')
 for variant,name in enumerate(['normal','shiny']):previews[variant].save(out/f'all-battle-frames-{name}.png')
 beforeafter.save(out/'back-before-after.png')
 for i,(a,b) in enumerate([(0,4),(4,8),(8,11)]):previews[0].crop((0,a*260,1000,b*260)).save(out/f'review-{i}.png')
 (out/'checks.json').write_text(json.dumps(checks,indent=2)+'\n');print('Staged all 88 battle frames; native round-trip, palette-index and edge checks passed.')
if __name__=='__main__':main()
