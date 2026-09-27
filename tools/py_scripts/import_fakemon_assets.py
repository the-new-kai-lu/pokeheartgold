#!/usr/bin/env python3
"""Import the eleven approved graphics from an hg-engine build, preserving their bytes.

Requires ndspy. Normal builds only use apply_fakemon_assets.py (Python stdlib).
The compiled assets are checked in so the stock port does not depend on hg-engine.
"""
import argparse, hashlib, json, shutil, struct
from pathlib import Path
from ndspy.narc import NARC
from ndspy.rom import NintendoDSRom

ROOT = Path(__file__).resolve().parents[2]

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--hg-engine', type=Path, required=True)
    args = ap.parse_args()
    h = args.hg_engine.resolve()
    meta_path = h / 'documentation/fakemon/designs-2026-09/species.json'
    meta = json.loads(meta_path.read_text())
    mons = sorted((m for line in meta['lines'] for m in line['designs']), key=lambda m:m['engine_species_id'])
    rom_path = h / 'test.nds'
    rom = NintendoDSRom.fromFile(rom_path)
    source = {path:NARC(rom.getFileByName(path)).files for path in ['a/0/0/4','a/0/2/0','a/0/8/1']}
    out = ROOT / 'files/fakemon'
    out.mkdir(exist_ok=True)
    manifest = {'source_rom_sha256':hashlib.sha256(rom_path.read_bytes()).hexdigest(), 'source_metadata_sha256':hashlib.sha256(meta_path.read_bytes()).hexdigest(), 'archives':{}, 'species':[]}
    def member(path, index, data, name):
        dest = out / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)
        manifest['archives'].setdefault(path,[]).append({'index':index,'file':name,'sha256':hashlib.sha256(data).hexdigest()})
    for j,m in enumerate(mons):
        sid=m['engine_species_id']; key=m['key']; folder=out/key
        folder.mkdir(exist_ok=True)
        shutil.copytree(h/f'data/graphics/sprites/{key}',folder/'source',dirs_exist_ok=True)
        shutil.copyfile(h/f'sound/cries/{m["cry_archive_id"]}.wav',folder/'cry.wav')
        for k in range(6):
            data=source['a/0/0/4'][sid*6+k]
            assert data[:4] in [b'RGCN',b'RLCN']
            member('a/0/0/4',(494+j)*6+k,data,f'{key}/battle-{k}.bin')
        member('a/0/0/5',(494+j)*4,bytes(1),f'{key}/height.bin')
        # All four gender/facing height records use the approved zero offset.
        for k in range(1,4):
            member('a/0/0/5',(494+j)*4+k,bytes(1),f'{key}/height.bin')
        member('a/0/2/0',551+j,source['a/0/2/0'][sid+7],f'{key}/icon.bin')
        member('a/0/8/1',863+j,source['a/0/8/1'][297+sid],f'{key}/follower.bin')
        large=m['concept_stage']==3
        member('a/1/4/1',566+j,bytes([0,int(large),0,0]),f'{key}/follower-param.bin')
        # Reuse an anatomically similar canonical footprint (no new print design was approved).
        template = 52 if key in ['voltuff','surguenon','raijinque'] else 4 if m['breeding']['hatch_species']=='embernewt' else 16
        stockfeet=NARC((ROOT/'files/poketool/pokefoot/pokefoot.narc').read_bytes()).files
        member('a/0/6/9',sid+3,stockfeet[template+3],f'{key}/footprint.bin')
        manifest['species'].append({'species':sid,'key':key,'battle_slot':494+j,'icon_slot':551+j,'follower_slot':863+j,'follower_param_slot':566+j,'sprite_id':1050+j,'cry_bank':778+j,'footprint_template':template,'cry_source_sha256':hashlib.sha256((folder/'cry.wav').read_bytes()).hexdigest()})
    (out/'assets.json').write_text(json.dumps(manifest,indent=2)+'\n')
    (out/'species.json').write_bytes(meta_path.read_bytes())
    print('Imported eleven approved sprite, icon, follower, cry and reference footprint sets.')

if __name__ == '__main__': main()
