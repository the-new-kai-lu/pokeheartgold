#!/usr/bin/env python3
"""Validate installed custom archives, canonical isolation, audio and complete Dex text.
Run after make; --rom also checks the actual packaged ROM instead of just files/.
Requires ndspy and Pillow; does not mutate assets or save files.
"""
import argparse,hashlib,json,re,struct,subprocess,wave,xml.etree.ElementTree as ET
from pathlib import Path
from PIL import Image
from ndspy.narc import NARC
from ndspy.rom import NintendoDSRom
from ndspy.soundArchive import SDAT
ROOT=Path(__file__).resolve().parents[2]
SOURCES={'a/0/0/4':'poketool/pokegra/pokegra.narc','a/0/0/5':'poketool/pokegra/height.narc','a/0/2/0':'poketool/icongra/poke_icon/poke_icon.narc','a/0/6/9':'poketool/pokefoot/pokefoot.narc','a/0/8/1':'data/mmodel/mmodel.narc','a/1/4/1':'fielddata/tsurepoke/tp_param.narc'}
STOCK_REVISION='9d8b7591f09b65804da2fb2dfd56f320633e0d36'

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--rom',type=Path);ap.add_argument('--output',type=Path)
    args=ap.parse_args();rom=NintendoDSRom.fromFile(args.rom) if args.rom else None
    def read(path):return rom.getFileByName(path) if rom else (ROOT/'files'/path).read_bytes()
    manifest=json.loads((ROOT/'files/fakemon/assets.json').read_text())
    results=[]
    def check(test,name):
        assert test,name
        results.append(name)
    for path,additions in manifest['archives'].items():
        actual=NARC(read(path)).files
        stock=NARC((ROOT/'files'/SOURCES[path]).read_bytes()).files
        check(actual[:len(stock)]==stock,path+' all canonical members unchanged')
        for entry in additions:
            check(hashlib.sha256(actual[entry['index']]).hexdigest()==entry['sha256'],entry['file']+' installed at correct index')
    for row in manifest['species']:
        folder=ROOT/'files/fakemon'/row['key']
        for gender in ['male','female']:
            for facing in ['front','back']:
                im=Image.open(folder/f'source/{gender}/{facing}.png')
                check(im.size==(160,80) and im.mode=='P',row['key']+f' {gender} {facing} 80x80 two-frame indexed art')
                check(max(im.tobytes())<16,row['key']+f' {gender} {facing} <=16 color indices')
        im=Image.open(folder/'source/icon.png')
        check(im.size==(32,64),row['key']+' two-frame menu icon')
        im=Image.open(folder/'source/overworld.png')
        check(im.size in [(32,256),(64,512)],row['key']+' four-direction two-frame follower')
        for pal in [4,5]:
            data=(folder/f'battle-{pal}.bin').read_bytes()
            check(data[:4]==b'RLCN' and len(data)==72 and all(c<0x8000 for c in struct.unpack('<16H',data[40:])),row['key']+f' palette{pal} native RGB555')
        check(hashlib.sha256((folder/'cry.wav').read_bytes()).hexdigest()==row['cry_source_sha256'],row['key']+' approved source cry hash')
        with wave.open(str(folder/'cry.wav'),'rb') as w:
            check(w.getnchannels()==1 and w.getsampwidth()==2 and w.getframerate()==16384,row['key']+' approved source cry format')
    original_sdat=subprocess.check_output(['git','show',STOCK_REVISION+':files/data/sound/gs_sound_data.sdat'],cwd=ROOT)
    stock=SDAT(original_sdat);actual=SDAT(read('data/sound/gs_sound_data.sdat'))
    def saved(entries):return [(n,o.save() if o else None) for n,o in entries]
    for attr in ['sequences','sequenceArchives','banks','waveArchives','sequencePlayers','streamPlayers','streams']:
        old=getattr(stock,attr);new=getattr(actual,attr)
        check(saved(new[:len(old)])==saved(old),'SDAT canonical '+attr+' preserved')
    check(len(actual.banks)==789 and len(actual.waveArchives)==789,'eleven appended SDAT banks and waves')
    for row in manifest['species']:
        idx=row['cry_bank'];check(actual.banks[idx][1].waveArchiveIDs==[idx],row['key']+' cry bank references own wave')
        wav=actual.waveArchives[idx][1].waves[0]
        check(wav.sampleRate==16384 and not wav.isLooped and wav.waveType==0,row['key']+' cry uses native nonlooping PCM8')
        with wave.open(str(ROOT/'files/fakemon'/row['key']/'cry.wav'),'rb') as source:
            samples=struct.unpack('<'+'h'*source.getnframes(),source.readframes(source.getnframes()))
        pcm=bytes((max(-128,min(127,round(x/256)))&255) for x in samples)
        pcm+=bytes(-len(pcm)%4)
        check(wav.data==pcm,row['key']+' exact approved cry PCM conversion installed')
    meta=json.loads((ROOT/'files/fakemon/species.json').read_text());mons=[m for line in meta['lines'] for m in line['designs']]
    metricdata=NARC(read('a/0/7/4')).files
    stockmetrics=json.loads(subprocess.check_output(['git','show',STOCK_REVISION+':files/application/zukanlist/zkn_data/zukan_data.json'],cwd=ROOT))['mon_stats']
    for idx,field,fmt in [(0,'height','<I'),(1,'weight','<I'),(2,'body_style','<B')]:
        width=struct.calcsize(fmt)
        expected=[row[field]['altered'] if isinstance(row[field],dict) else row[field] for row in stockmetrics]
        check([struct.unpack_from(fmt,metricdata[idx],i*width)[0] for i in range(494)]==expected,'canonical Dex '+field+' preserved')
    for m in mons:
        sid=m['engine_species_id'];details=m['pokedex_details']
        check(struct.unpack_from('<I',metricdata[0],sid*4)[0]==details['height_decimetres'],m['key']+' installed Dex height')
        check(struct.unpack_from('<I',metricdata[1],sid*4)[0]==details['weight_hectograms'],m['key']+' installed Dex weight')
        shape=2 if sid<=1078 else 0 if sid<=1083 else 4 if sid==1086 else 5
        check(metricdata[2][sid]==shape,m['key']+' stock-ordered Dex body shape')
    for bank in [803,804]:
        tree=ET.parse(ROOT/f'files/msgdata/msg/msg_{bank:04}.gmm').getroot()
        texts={int(row.get('index')):(row.find('language').text or '') for row in tree}
        for m in mons:
            sid=m['engine_species_id'];parts=[]
            for page in range(3):
                text=texts.get(sid+11*page,'')
                if text:parts.extend(text.split('\\n'))
            expected=m['pokedex_details']['entry_text']
            # Game text follows HGSS uppercase species names; design metadata
            # retains its readable spelling. All other prose must match exactly.
            for species in mons:
                expected=re.sub(r'\b'+re.escape(species['name'])+r'\b',species['name'].upper(),expected)
            check(' '.join(parts)==expected,m['key']+f' bank{bank} complete entry preserved across pages')
    report={'checks_passed':len(results),'rom':str(args.rom) if args.rom else None,'rom_sha256':hashlib.sha256(args.rom.read_bytes()).hexdigest() if args.rom else None,'checks':results}
    if args.output:args.output.write_text(json.dumps(report,indent=2)+'\n')
    print(f'{len(results)} asset checks passed.')

if __name__=='__main__':main()
