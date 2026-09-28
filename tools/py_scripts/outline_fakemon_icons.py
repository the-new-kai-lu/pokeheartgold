#!/usr/bin/env python3
"""Add a one-native-pixel stock-dark outline to all custom menu icons.

Shared palette index 15 is the existing darkest stock icon color. Only transparent
pixels neighboring a colored (non-outline) pixel are filled. Existing dark edges
are not dilated, so this is idempotent and does not thicken already outlined limbs.
Each 32x32 animation frame is processed separately; interior pixels are untouched.
"""
import hashlib,json,io,subprocess
from pathlib import Path
from PIL import Image
ROOT=Path(__file__).resolve().parents[2]
BASELINE='47f1377bc'
# Detached vertical remnants in the second frame, outside the bird silhouettes.
# Keep actual detached anatomy (e.g. Sedgling's lifted toe) and flame sparks.
STRAY_PIXELS={
 'cragaviar':[(5,32+y) for y in (22,23,25)],
 'ragnaroc':[(3,32+y) for y in (3,4,6,7,8,9,10,23,24)],
}
NEIGHBORS=[(dx,dy) for dy in (-1,0,1) for dx in (-1,0,1) if dx or dy]
def outline_icon(image):
 assert image.mode=='P' and image.size==(32,64) and image.info.get('transparency')==0
 assert max(image.tobytes())<16
 result=image.copy()
 for frame in range(2):
  for y in range(32):
   for x in range(32):
    value=image.getpixel((x,frame*32+y))
    if value in (0,15):continue
    # There must be room for the complete outline; never silently clip it.
    assert 0<x<31 and 0<y<31,(frame,x,y,'colored pixel touches canvas boundary')
    for dx,dy in NEIGHBORS:
     point=(x+dx,frame*32+y+dy)
     if image.getpixel(point)==0:result.putpixel(point,15)
 return result

def pack_icon(image,original):
 native=bytearray(original);assert len(native)==1072 and native[:4]==b'RGCN'
 pixels=image.load();data=[]
 for ty in range(0,64,8):
  for tx in range(0,32,8):
   for y in range(8):
    for x in range(0,8,2):data.append(pixels[tx+x,ty+y]|pixels[tx+x+1,ty+y]<<4)
 native[48:]=bytes(data)
 # Decode independently to check tile orientation and every palette index.
 decoded=bytearray(2048);offset=48
 for ty in range(8):
  for tx in range(4):
   for y in range(8):
    for pair in range(4):
     value=native[offset];offset+=1;start=(ty*8+y)*32+tx*8+pair*2
     decoded[start]=value&15;decoded[start+1]=value>>4
 assert bytes(decoded)==image.tobytes()
 return bytes(native)

def main():
 path=ROOT/'files/fakemon/assets.json';manifest=json.loads(path.read_text());report={}
 for mon in manifest['species']:
  key=mon['key'];folder=ROOT/'files/fakemon'/key
  source=subprocess.check_output(['git','show',BASELINE+':files/fakemon/'+key+'/source/icon.png'],cwd=ROOT)
  image=Image.open(io.BytesIO(source))
  for point in STRAY_PIXELS.get(key,[]):image.putpixel(point,0)
  result=outline_icon(image)
  assert outline_icon(result).tobytes()==result.tobytes()
  assert result.getpalette()==image.getpalette() and result.info==image.info
  assert all(a==b or (a==0 and b==15) for a,b in zip(image.tobytes(),result.tobytes()))
  native=pack_icon(result,(folder/'icon.bin').read_bytes())
  result.save(folder/'source/icon.png',transparency=0);(folder/'icon.bin').write_bytes(native)
  digest=hashlib.sha256(native).hexdigest()
  for entry in manifest['archives']['a/0/2/0']:
   if entry['file']==key+'/icon.bin':entry['sha256']=digest
  report[key]={'removed_stray_pixels':STRAY_PIXELS.get(key,[]),'added_outline_pixels':sum(a!=b for a,b in zip(image.tobytes(),result.tobytes())),'sha256':digest,'interior_pixels_and_palette_preserved':True,'idempotent':True,'native_roundtrip':True}
 path.write_text(json.dumps(manifest,indent=2)+'\n')
 out=ROOT/'documentation/fakemon/icon-outlines';out.mkdir(exist_ok=True);(out/'checks.json').write_text(json.dumps(report,indent=2)+'\n')
 print('Outlined and verified all 22 custom icon frames.')
if __name__=='__main__':main()
