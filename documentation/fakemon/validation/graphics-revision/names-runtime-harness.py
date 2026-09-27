#!/usr/bin/env python3
import argparse,hashlib,json,os,shutil
from pathlib import Path
from http.server import HTTPServer,BaseHTTPRequestHandler
from desmume.emulator import DeSmuME
from desmume.controls import Keys,keymask
p=argparse.ArgumentParser();p.add_argument('--rom',type=Path,required=True);p.add_argument('--rom-sha256',required=True);p.add_argument('--save',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--port',type=int,default=8053);args=p.parse_args()
rom=args.rom.resolve();save=args.save.resolve();out=args.out.resolve()
rom_hash=hashlib.sha256(rom.read_bytes()).hexdigest();assert rom_hash==args.rom_sha256,'Wrong ROM build'
out.mkdir(exist_ok=False);shutil.copyfile(rom,out/(out.name+'.nds'));shutil.copyfile(save,out/'input.sav');os.chdir(out)
e=DeSmuME();e.open(out.name+'.nds');e.volume_set(0);assert e.backup.import_file(str(out/'input.sav'));e.reset()
def frames(n):
 for _ in range(n):e.cycle(False)
def key(name,hold=3,wait=120):
 mask=keymask(getattr(Keys,'KEY_'+name));e.input.keypad_add_key(mask);frames(hold);e.input.keypad_rm_key(mask);frames(wait)
def touch(x,y,hold=3,wait=120):
 e.input.touch_set_pos(x,y);frames(hold);e.input.touch_release();frames(wait)
frames(900);e.screenshot().save('000-start.png')
(out/'run.json').write_text(json.dumps({'rom':str(rom),'rom_sha256':rom_hash,'input_save':str(save),'input_sha256':hashlib.sha256(save.read_bytes()).hexdigest(),'status':'in_progress'},indent=2)+'\n')
class Handler(BaseHTTPRequestHandler):
 def do_POST(self):
  try:
   c=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
   with open('inputs.jsonl','a') as f:f.write(json.dumps(c)+'\n')
   for v in c.get('keys',[]):key(*(v if isinstance(v,list) else [v]))
   for v in c.get('touches',[]):touch(*v)
   frames(c.get('frames',0))
   screenshot=c.get('name','step')+'.png';e.screenshot().save(screenshot)
   result={'screenshot':str(out/screenshot)}
   if 'save' in c:result['exported']=e.backup.export_file(str(out/c['save']))
   if c.get('reset'):e.reset()
   payload=json.dumps(result).encode();self.send_response(200)
  except Exception as ex:
   payload=json.dumps({'error':str(ex)}).encode();self.send_response(500)
  self.send_header('Content-Type','application/json');self.end_headers();self.wfile.write(payload)
 def log_message(self,*a):pass
print('READY',out,args.port,flush=True)
HTTPServer(('127.0.0.1',args.port),Handler).serve_forever()
