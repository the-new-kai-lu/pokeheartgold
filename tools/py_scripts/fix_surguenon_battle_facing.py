#!/usr/bin/env python3
"""Mirror each Surguenon battle frame independently, preserving frame order.
Staging only. Original indexed art and keys are read from a fixed pre-fix commit.
"""
import argparse,hashlib,io,json,subprocess
from pathlib import Path
from PIL import Image,ImageOps
ROOT=Path(__file__).resolve().parents[2]
BASELINE='293b55002'
def original(path):return subprocess.check_output(['git','show',BASELINE+':'+path],cwd=ROOT)
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--output',type=Path,required=True);args=ap.parse_args();out=args.output/'surguenon';report={}
 for index,(gender,side) in enumerate([('female','back'),('male','back'),('female','front'),('male','front')]):
  relative=f'files/fakemon/surguenon/source/{gender}/{side}.png'
  image=Image.open(io.BytesIO(original(relative)));fixed=image.copy()
  for frame in range(2):
   box=(frame*80,0,(frame+1)*80,80);a=image.crop(box);b=ImageOps.mirror(a)
   assert ImageOps.mirror(b).tobytes()==a.tobytes()
   fixed.paste(b,box[:2])
  folder=out/'source'/gender;folder.mkdir(parents=True,exist_ok=True)
  png=folder/(side+'.png');fixed.save(png,transparency=0)
  Path(str(png)+'.key').write_bytes(original(relative+'.key'))
  dest=out/f'battle-{index}.NCGR'
  subprocess.run([str(ROOT/'tools/nitrogfx/nitrogfx'),str(png),str(dest),'-scanfronttoback','-handleempty'],check=True)
  data=dest.read_bytes();dest.rename(out/f'battle-{index}.bin')
  old=original(f'files/fakemon/surguenon/battle-{index}.bin')
  assert data[:48]==old[:48] and len(data)==len(old)
  report[f'{gender}/{side}']={'sha256':hashlib.sha256(data).hexdigest(),'frames_mirrored_independently':True,'palette_preserved':fixed.getpalette()==image.getpalette()}
 (args.output/'battle-facing-checks.json').write_text(json.dumps(report,indent=2)+'\n')
 print('Mirrored four indexed battle sheets, two frames each.')
if __name__=='__main__':main()
