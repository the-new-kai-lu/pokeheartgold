#!/usr/bin/env python3
"""Drive DeSmuME through its Python API; screenshots/save are evidence, not blanket assertions.
Run with hg-engine/.venv/bin/python. Always uses a fresh temporary ROM/save copy.
"""
import argparse,json,shutil,os,hashlib,subprocess
from pathlib import Path
from desmume.emulator import DeSmuME
from desmume.controls import Keys,keymask
p=argparse.ArgumentParser();p.add_argument('--rom',type=Path,required=True);p.add_argument('--save',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--elf',type=Path,help='Matching build ELF for allocation-failure and Dex heap telemetry.');p.add_argument('--dex-browse',action='store_true',help='Exercise custom entries; requires a fixture with all 504 National entries caught.');a=p.parse_args()
rom=a.rom.resolve();save=a.save.resolve();elf=a.elf.resolve() if a.elf else None;out=a.output.resolve();out.mkdir(parents=True,exist_ok=False)
# DeSmuME can share its battery directory across processes: a unique ROM basename is required.
rom_name=out.name+'.nds'
shutil.copyfile(rom,out/rom_name);shutil.copyfile(save,out/'input.sav');os.chdir(out)
e=DeSmuME();e.open(rom_name);e.volume_set(0)
assert e.backup.import_file('input.sav');e.reset()
heap_audit={'allocation_failures':0,'minimum_free_bytes':None,'minimum_largest_block_bytes':None}
if elf:
 symbols={parts[2]:int(parts[0],16) for line in subprocess.check_output(['arm-none-eabi-nm','-n',str(elf)],text=True).splitlines() if len(parts:=line.split())==3}
 def allocation_failure(address,size):heap_audit['allocation_failures']+=1
 def allocation_request(address,size):
  if e.memory.register_arm9[0]!=37:return
  mem=e.memory.unsigned;info=symbols['sHeapInfo']
  indices=mem.read_long(info+16);handles=mem.read_long(info)
  if not indices or not handles:return
  heap=mem.read_long(handles+4*mem.read_byte(indices+37))
  if not heap:return
  block=mem.read_long(heap+0x24);total=largest=0;seen=set()
  while block and block not in seen:
   seen.add(block);length=mem.read_long(block+4);total+=length;largest=max(largest,length);block=mem.read_long(block+12)
  for field,value in [('minimum_free_bytes',total),('minimum_largest_block_bytes',largest)]:
   previous=heap_audit[field];heap_audit[field]=value if previous is None else min(previous,value)
 e.memory.register_exec(symbols['AllocFail'],allocation_failure)
 e.memory.register_exec(symbols['Heap_Alloc'],allocation_request)
 e.memory.register_exec(symbols['Heap_AllocAtEnd'],allocation_request)
def frames(n):
 for _ in range(n):e.cycle(False)
def key(k):
 e.input.keypad_add_key(keymask(k));frames(3);e.input.keypad_rm_key(keymask(k));frames(120)
def touch(x,y):
 e.input.touch_set_pos(x,y);frames(3);e.input.touch_release();frames(160)
frames(900)
for _ in range(4):key(Keys.KEY_A)
frames(400);e.screenshot().save('loaded.png')
touch(43,77);e.screenshot().save('party.png')
key(Keys.KEY_A);e.screenshot().save('party-menu.png')
key(Keys.KEY_A);frames(120);e.screenshot().save('summary.png')
key(Keys.KEY_RIGHT);key(Keys.KEY_RIGHT);e.screenshot().save('summary-performance.png')
key(Keys.KEY_LEFT);key(Keys.KEY_LEFT)
key(Keys.KEY_B);key(Keys.KEY_B);frames(100);touch(120,77)
for _ in range(4):key(Keys.KEY_A);frames(120)
frames(2400);e.screenshot().save('saved.png')
assert e.backup.export_file('game-saved.sav')
e.reset();frames(900)
for _ in range(4):key(Keys.KEY_A)
frames(400);e.screenshot().save('reloaded.png')
touch(43,77);e.screenshot().save('reloaded-party.png')
key(Keys.KEY_B);touch(43,47);frames(300);e.screenshot().save('dex.png')
if a.dex_browse:
 key(Keys.KEY_A);frames(300);e.screenshot().save('dex-list.png')
 # Grab the scrollbar near its end, then advance one15-entry page.
 touch(242,124);touch(242,130);touch(128,104);e.screenshot().save('dex-arceus493.png')
 key(Keys.KEY_RIGHT);e.screenshot().save('dex-voltuff494.png')
 key(Keys.KEY_SELECT);e.screenshot().save('dex-voltuff-page2.png')
 touch(242,124);touch(242,130);touch(242,134);e.screenshot().save('dex-custom-tail.png')
 key(Keys.KEY_SELECT);e.screenshot().save('dex-raijinque-page2.png')
 touch(48,64);e.screenshot().save('dex-fimbulisk-page1.png')
 key(Keys.KEY_SELECT);e.screenshot().save('dex-fimbulisk-page2.png')
 key(Keys.KEY_SELECT);e.screenshot().save('dex-fimbulisk-page3.png')
 key(Keys.KEY_SELECT);e.screenshot().save('dex-fimbulisk-wrap.png')
 key(Keys.KEY_RIGHT);e.screenshot().save('dex-sedgling-page1.png')
 key(Keys.KEY_SELECT);e.screenshot().save('dex-sedgling-page2.png')
 key(Keys.KEY_LEFT);e.screenshot().save('dex-fimbulisk-reset.png')
 key(Keys.KEY_A);e.screenshot().save('dex-area.png')
 touch(96,176);frames(300);e.screenshot().save('dex-size.png')
 key(Keys.KEY_B);key(Keys.KEY_SELECT)
 key(Keys.KEY_B);key(Keys.KEY_B);frames(200)
 touch(43,47);frames(300);key(Keys.KEY_A);frames(200);e.screenshot().save('dex-reopened.png')
 # Text-region comparisons catch the original wrong-state hook even when the app stays responsive.
 from PIL import Image
 def text_pixels(name):return Image.open(name).crop((8,136,248,184)).tobytes()
 pages=[text_pixels(f'dex-fimbulisk-page{i}.png') for i in (1,2,3)]
 assert len(set(pages))==3, 'SELECT did not render three distinct Fimbulisk pages'
 assert pages[0]==text_pixels('dex-fimbulisk-wrap.png'), 'Fimbulisk pages failed to wrap'
 assert pages[0]==text_pixels('dex-fimbulisk-reset.png'), 'Species change did not reset page'
 touch(30,178);frames(300);touch(128,176);frames(400);e.screenshot().save('dex-search-results.png')
 touch(242,124);e.screenshot().save('dex-search-canonical.png')
 touch(242,130);touch(242,134);e.screenshot().save('dex-search-tail.png')
 touch(88,64);e.screenshot().save('dex-search-fimbulisk-page1.png')
 key(Keys.KEY_SELECT);e.screenshot().save('dex-search-fimbulisk-page2.png')
 key(Keys.KEY_SELECT);e.screenshot().save('dex-search-fimbulisk-page3.png')
 search_pages=[text_pixels(f'dex-search-fimbulisk-page{i}.png') for i in (1,2,3)]
 assert search_pages==pages, 'Search-result entry paging failed or rendered the wrong species'
 key(Keys.KEY_B);touch(30,178);frames(300);touch(128,176);frames(400)
 touch(242,124);e.screenshot().save('dex-search-repeat-canonical.png')
 touch(242,130);touch(242,134);touch(88,64);e.screenshot().save('dex-search-repeat-reset.png')
 assert pages[0]==text_pixels('dex-search-repeat-reset.png'), 'Canonical entry change did not reset custom page'
 key(Keys.KEY_SELECT);e.screenshot().save('dex-search-repeat-page2.png')
 assert pages[1]==text_pixels('dex-search-repeat-page2.png'), 'Repeated search stopped responding'
 key(Keys.KEY_B);key(Keys.KEY_B);frames(200);e.screenshot().save('dex-search-exited.png')
key(Keys.KEY_B)
assert heap_audit['allocation_failures']==0, 'Emulator encountered a heap allocation failure'
(out/'run.json').write_text(json.dumps({'rom_sha256':hashlib.sha256(rom.read_bytes()).hexdigest(),'input_save':str(save),'status':'script_finished_review_screenshots_and_reopen_exported_save','dex_browse':a.dex_browse,'heap_audit':heap_audit if elf else None,'screenshots':sorted(p.name for p in out.glob('*.png'))},indent=2)+'\n')
print('Script completed; review screenshots and validate game-saved.sav with matching editor.')
