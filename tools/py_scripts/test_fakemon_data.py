#!/usr/bin/env python3
"""Check preservation, packed-learnset bounds, and optional built-ROM data."""
import argparse,json,subprocess,struct
from pathlib import Path
from ndspy.narc import NARC
from ndspy.rom import NintendoDSRom
ROOT=Path(__file__).resolve().parents[2]
BASE='9d8b7591f09b65804da2fb2dfd56f320633e0d36'
def original(p):return subprocess.check_output(['git','-C',str(ROOT),'show',BASE+':'+p])
a=argparse.ArgumentParser();a.add_argument('--rom',type=Path);args=a.parse_args();checks=0
personal=json.loads((ROOT/'files/poketool/personal/personal.json').read_text())['baseStats']
old=json.loads(original('files/poketool/personal/personal.json'))['baseStats']
assert personal[:len(old)]==old;checks+=len(old)
evo=json.loads((ROOT/'files/poketool/personal/evo.json').read_text())['evoTable']
evo_old=json.loads(original('files/poketool/personal/evo.json'))['evoTable'];assert evo[:len(evo_old)]==evo_old;checks+=len(evo_old)
wotbl=NARC((ROOT/'files/poketool/personal/wotbl.narc').read_bytes());stock=NARC(original('files/poketool/personal/wotbl.narc'))
assert wotbl.files[:len(stock.files)]==stock.files;checks+=len(stock.files)
for sid in range(1076,1087):
 m=personal[sid];assert sum(m[k] for k in ['hp','atk','def','speed','spatk','spdef']) in [315,405,600]
 assert m['catchRate']==45 and m['eggCycles']==20 and m['friendship']==70
 assert len(wotbl.files[sid])<=42
 entries=struct.unpack('<'+'H'*(len(wotbl.files[sid])//2),wotbl.files[sid]);assert entries[-1]==65535
 assert all((v&511)<=474 and (v>>9)<=100 for v in entries[:-1]);checks+=5
report={'checks':checks,'source_validation':'passed'}
if args.rom:
 rom=NintendoDSRom(args.rom.read_bytes())
 for archive,path in [('a/0/0/2','files/poketool/personal/personal.narc'),('a/0/3/3','files/poketool/personal/wotbl.narc'),('a/0/3/4','files/poketool/personal/evo.narc'),('a/0/1/1','files/poketool/waza/waza_tbl.narc')]:
  built=NARC(rom.getFileByName(archive));local=NARC((ROOT/path).read_bytes());assert built.files==local.files,archive
  if 'personal' in path:assert len(built.files)==1087
  checks+=1
 report.update(checks=checks,rom=str(args.rom),rom_archives='passed')
print(json.dumps(report,indent=2))
