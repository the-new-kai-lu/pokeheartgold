#!/usr/bin/env python3
"""User-authorized indexed-pixel revision: close-up backs and shaped walking legs.

Pinned inputs make this repeatable. Outputs staging files only. Both palettes,
keys, north/south poses and all native metadata stay unchanged.
"""
import argparse,io,json,struct,subprocess
from pathlib import Path
from PIL import Image,ImageDraw,ImageOps
from pack_fakemon_followers import FAMILIES,btx_layout,pack_btx
from outline_fakemon_followers import outline_frame
from fix_fakemon_pixel_gaits import BIPEDS as OLD_BIPEDS,QUADS as OLD_QUADS
ROOT=Path(__file__).resolve().parents[2]
BASE='ece5bf66b';BODY_BASE='c020456f4'
# Magnification, original focal x and top; shared across both frames.
CAMERAS={'voltuff':(1.70,40,28),'surguenon':(1.72,41,16),'raijinque':(1.45,40,6),'embernewt':(1.75,43,29),'pyrovaran':(1.80,49,25),'magmalisk':(1.70,50,17),'rimevaran':(1.80,47,24),'fimbulisk':(1.75,49,19),'sedgling':(1.85,40,27),'cragaviar':(1.75,44,11),'ragnaroc':(1.65,43,4)}
# Each explicit pose: hip, knee, ankle, thigh radius, calf radius, paw width, raised.
BIPEDS={
 'voltuff':[((15,24),(13,26),(13,28),1,0,3,False),((15,24),(18,25),(17,26),1,0,2,True)],
 'surguenon':[((14,22),(11,25),(12,28),1,0,3,False),((14,22),(18,25),(17,26),1,0,3,True)],
 'raijinque':[((29,52),(24,56),(25,60),2,1,4,False),((29,52),(34,56),(32,57),2,1,3,True)],
 'sedgling':[((14,26),(13,27),(12,28),1,0,3,False),((15,26),(17,27),(17,27),1,0,2,True)],
 'cragaviar':[((15,24),(16,26),(12,28),1,0,3,False),((16,24),(19,26),(19,26),1,0,2,True)],
 'ragnaroc':[((26,52),(29,55),(24,60),1,0,4,False),((27,52),(33,55),(32,57),1,0,3,True)],
}
QUADS={
 'embernewt':[[((11,24),(10,26),(9,28),1,1,3,False),((19,25),(21,26),(20,27),2,1,3,True)],[((11,24),(13,26),(12,27),1,1,3,True),((19,25),(17,26),(18,28),2,1,4,False)]],
 'pyrovaran':[[((11,23),(11,26),(8,28),2,1,4,False),((21,24),(24,26),(22,27),3,1,4,True)],[((11,23),(14,25),(13,27),2,1,4,True),((21,24),(18,26),(20,28),3,1,4,False)]],
 'rimevaran':[[((11,23),(11,26),(8,28),2,1,4,False),((22,24),(25,26),(23,27),3,1,4,True)],[((11,23),(14,25),(13,27),2,1,4,True),((22,24),(19,26),(21,28),3,1,4,False)]],
 'magmalisk':[[((25,53),(25,57),(21,60),3,2,6,False),((39,54),(43,57),(40,59),4,2,5,True)],[((25,53),(29,56),(27,59),3,2,5,True),((39,54),(35,57),(37,60),4,2,6,False)]],
 'fimbulisk':[[((24,53),(24,57),(20,60),3,2,6,False),((38,54),(42,57),(39,59),4,2,5,True)],[((24,53),(28,56),(26,59),3,2,5,True),((38,54),(34,57),(36,60),4,2,6,False)]],
}
def original(path,base=BASE):return subprocess.check_output(['git','show',base+':'+path],cwd=ROOT)
def indexed(path,base=BASE):return Image.open(io.BytesIO(original(path,base)))
def mask(im):return im.point(lambda x:255 if x else 0,'L')
def rgba(im):
 result=im.convert('RGBA');result.putalpha(mask(im));return result

def scale2x(src):
 """Reconstruct diagonal corners using adjacent indices, without new colors."""
 w,h=src.size;dst=Image.new('P',(w*2,h*2));dst.putpalette(src.getpalette());p=src.load();q=dst.load()
 for y in range(h):
  for x in range(w):
   e=p[x,y];b=p[x,max(y-1,0)];d=p[max(x-1,0),y];f=p[min(x+1,w-1),y];h_=p[x,min(y+1,h-1)];v=[e]*4
   if b!=h_ and d!=f:v=[d if d==b else e,f if b==f else e,d if d==h_ else e,f if h_==f else e]
   for i,c in enumerate(v):q[2*x+i%2,2*y+i//2]=c
 return dst

def remove_clipped_fragments(im):
 p=im.load();seen=set();groups=[]
 for y in range(77):
  for x in range(80):
   if not p[x,y] or (x,y) in seen:continue
   group={(x,y)};todo=[(x,y)];seen.add((x,y))
   while todo:
    xx,yy=todo.pop()
    for dx,dy in ((-1,-1),(0,-1),(1,-1),(-1,0),(1,0),(-1,1),(0,1),(1,1)):
     nx,ny=xx+dx,yy+dy
     if 0<=nx<80 and 0<=ny<77 and p[nx,ny] and (nx,ny) not in seen:seen.add((nx,ny));group.add((nx,ny));todo.append((nx,ny))
   groups.append(group)
 largest=max(groups,key=len);removed=0
 for group in groups:
  if group is not largest and any(x in (0,79) for x,y in group):
   for point in group:p[point]=0;removed+=1
 return removed

def back_frame(im,key):
 sc,cx,top=CAMERAS[key];enlarged=scale2x(im).resize((round(80*sc),round(80*sc)),Image.Resampling.NEAREST)
 result=Image.new('P',(80,80));result.putpalette(im.getpalette());result.paste(enlarged,(round(40-cx*sc),round(6-top*sc)))
 ImageDraw.Draw(result).rectangle((0,77,79,79),fill=0)
 return result,remove_clipped_fragments(result)

def limb(layer,pose,key,near):
 hip,knee,ankle,thigh,calf,foot,lifted=pose;hx,hy=hip;kx,ky=knee;ax,ay=ankle;d=ImageDraw.Draw(layer)
 electric=key in FAMILIES['electric'];bird=key in FAMILIES['bird']
 if key in QUADS:
  large=layer.width==64
  fore=hx < (30 if large else 16)
  thigh=(2 if large else 1) if fore else (3 if large else 2)
  calf=1 if large else 0;foot=3 if large else 2
  if lifted:ay-=1
 base=7 if electric else (5 if bird else 3);light=9 if electric else (7 if bird else 4)
 if not near:base=5 if electric else 2;light=6 if electric else 3
 # Tapered thigh and calf silhouettes; knees are explicitly bent off the hip/ankle axis.
 d.polygon([(hx-thigh,hy),(hx+thigh,hy),(kx+thigh,ky),(kx+calf,ky+1),(ax+calf,ay),(ax-calf,ay),(kx-calf,ky+1),(kx-thigh,ky)],fill=base)
 d.polygon([(hx-thigh+1,hy),(hx,hy),(kx,ky),(kx-thigh+1,ky)],fill=light)
 d.line([(kx,ky),(kx+max(1,thigh-1),ky)],fill=2,width=1)
 d.polygon([(kx-calf,ky+1),(kx+calf,ky+1),(ax+calf,ay),(ax-calf,ay)],fill=3 if near else 2)
 if near and ay>ky+1:d.line([(kx,ky+1),(ax,ay)],fill=4,width=1)
 if lifted:
  d.polygon([(ax-calf,ay-1),(ax+calf,ay-1),(ax+calf,ay),(ax-1,ay+1),(ax-foot+2,ay)],fill=2);d.point((ax-1,ay),fill=4 if near else 3)
 else:
  d.polygon([(ax-calf,ay-1),(ax+calf,ay-1),(ax,ay+1),(ax-foot+1,ay+1),(ax-foot+1,ay)],fill=2)
  d.line([(ax-foot+2,ay),(ax,ay)],fill=4 if near else 3,width=1)
  if near and not electric and foot>=4:d.point((ax-foot+1,ay),fill=5 if not bird else 4)
 return {'hip':hip,'knee':knee,'ankle':ankle,'lifted':lifted}

def side_pair(key,anchor):
 body=anchor.copy();d=ImageDraw.Draw(body)
 for x0,y0,x1,y1 in (OLD_BIPEDS|OLD_QUADS)[key][-1]:d.rectangle((x0,y0,x1-1,y1-1),fill=0)
 frames=[];joints=[]
 for phase in range(2):
  far=Image.new('P',body.size);near=Image.new('P',body.size);records=[]
  nearposes=[BIPEDS[key][phase]] if key in BIPEDS else QUADS[key][phase]
  farposes=[BIPEDS[key][1-phase]] if key in BIPEDS else QUADS[key][1-phase]
  for p in farposes:
   pose=list(tuple((v[0]+1,v[1]) if i<3 else v for i,v in enumerate(p)))
   if phase==1:
    # Passing frame: the supporting far foot moves underneath the body.
    # It must not merely duplicate phase A's silhouette in a darker color.
    hip,knee,ankle=pose[:3]
    if key in BIPEDS:
     pose[1]=(hip[0],knee[1]);pose[2]=(hip[0]-1,ankle[1])
    else:
     shift=2 if body.width==32 else 3
     pose[1]=(knee[0]+shift//2,knee[1]);pose[2]=(ankle[0]+shift,ankle[1])
   records.append(limb(far,pose,key,False))
  for p in nearposes:records.append(limb(near,p,key,True))
  result=far.copy();result.putpalette(anchor.getpalette());result.paste(body,(0,0),mask(body));result.paste(near,(0,0),mask(near))
  frames.append(outline_frame(result));joints.append(records)
 return frames,joints

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--output',type=Path,required=True);args=ap.parse_args();out=args.output;out.mkdir(parents=True,exist_ok=True)
 report={};backs=Image.new('RGB',(850,len(CAMERAS)*265),'#8bb5b5');walks=[Image.new('RGB',(1000,len(CAMERAS)*210),'#71a67e') for _ in range(2)]
 for row,key in enumerate(CAMERAS):
  folder=out/key;(folder/'source').mkdir(parents=True,exist_ok=True);rel=f'files/fakemon/{key}';report[key]={}
  normal=[c for v in struct.unpack_from('<16H',original(rel+'/battle-4.bin'),40) for c in ((v&31)*255//31,((v>>5)&31)*255//31,((v>>10)&31)*255//31)]
  for gender,member in [('female',0),('male',1)]:
   before=indexed(rel+f'/source/{gender}/back.png');result=before.copy();removed=[]
   for phase in range(2):b,n=back_frame(before.crop((phase*80,0,(phase+1)*80,80)),key);result.paste(b,(phase*80,0));removed.append(n)
   target=folder/'source'/gender/'back.png';target.parent.mkdir(parents=True,exist_ok=True);result.save(target,transparency=0);target.with_suffix('.png.key').write_bytes(original(rel+f'/source/{gender}/back.png.key'))
   ncgr=folder/f'back-{member}.NCGR';subprocess.run([str(ROOT/'tools/nitrogfx/nitrogfx'),str(target),str(ncgr),'-scanfronttoback','-handleempty'],check=True)
   native=ncgr.read_bytes();old=original(rel+f'/battle-{member}.bin');assert native[:48]==old[:48] and len(native)==len(old)
   decoded=folder/f'back-{member}-decoded.png';subprocess.run([str(ROOT/'tools/nitrogfx/nitrogfx'),str(ncgr),str(decoded),'-scanfronttoback','-width','20'],check=True)
   assert bytes(15-v//17 for v in Image.open(decoded).convert('L').tobytes())==result.tobytes()
   (folder/f'battle-{member}.bin').write_bytes(native);ncgr.unlink();decoded.unlink();decoded.with_suffix('.png.key').unlink(missing_ok=True)
   if gender=='male':
    for col,im in enumerate([before,result]):
     im=im.crop((0,0,80,80));im.putpalette(normal);r=rgba(im).resize((240,240),Image.Resampling.NEAREST);backs.paste(r,(col*300+180,row*265),r)
    ImageDraw.Draw(backs).text((8,row*265+10),key,fill='black')
   report[key][gender]={'roundtrip':True,'camera':CAMERAS[key],'clipped_fragment_pixels_removed':removed}
  current=indexed(rel+'/source/overworld.png');s=current.width;frames=[current.crop((0,s*i,s,s*(i+1))) for i in range(8)]
  anchor=indexed(rel+'/source/overworld.png',BODY_BASE).crop((0,s*4,s,s*5));oldpair=frames[4:6];pair,joints=side_pair(key,anchor);frames[4:6]=pair;frames[6:8]=[ImageOps.mirror(f) for f in pair]
  native=original(rel+'/follower.bin');records,pa=btx_layout(native);palettes=[[[v&31,v>>5&31,v>>10&31] for v in struct.unpack_from('<16H',native,pa+32*i)] for i in range(2)]
  packed=pack_btx(native,frames,palettes);assert packed[pa:]==native[pa:]
  for _,_,_,a,b in records[:4]:assert packed[a:b]==native[a:b]
  allowed={i for _,_,_,a,b in records[4:] for i in range(a,b)};assert all(a==b or i in allowed for i,(a,b) in enumerate(zip(native,packed)))
  assert frames[4].tobytes()!=frames[5].tobytes();(folder/'follower.bin').write_bytes(packed);sheet=current.copy()
  for i,f in enumerate(frames):sheet.paste(f,(0,s*i))
  sheet.save(folder/'source/overworld.png',transparency=0);report[key]['follower']={'joints':joints,'north_south_palettes_metadata_unchanged':True,'east_west_mirrored':True,'bounds':[mask(f).getbbox() for f in pair]}
  for phase in range(2):
   for col,f in enumerate([oldpair[phase],pair[phase],frames[6+phase]]):
    r=rgba(f).resize((s*3,s*3),Image.Resampling.NEAREST);walks[phase].paste(r,(180+col*250,row*210+205-s*3),r)
   ImageDraw.Draw(walks[phase]).text((8,row*210+10),key,fill='black')
 backs.save(out/'back-before-after.png')
 for phase,im in enumerate(walks):im.save(out/f'walking-phase-{phase}.png')
 walks[0].save(out/'walking-before-after.gif',save_all=True,append_images=walks[1:],duration=180,loop=0)
 (out/'checks.json').write_text(json.dumps(report,indent=2)+'\n');print('Staged 44 rear battle frames and 44 side follower frames; native checks passed.')
if __name__=='__main__':main()
