#!/usr/bin/env python3
"""Append approved cries to stock SDAT without replacing canonical sounds.
Requires ndspy only when regenerating the checked-in sound archive.
"""
import copy, json, struct, wave
from pathlib import Path
from ndspy.soundArchive import SDAT
from ndspy.soundWave import SWAV
from ndspy.soundWaveArchive import SWAR
ROOT=Path(__file__).resolve().parents[2]
path=ROOT/'files/data/sound/gs_sound_data.sdat'
sdat=SDAT.fromFile(path)
assert len(sdat.banks) in (778,789) and len(sdat.waveArchives) in (778,789)
def saved(entries):
    return [(name, obj.save() if obj is not None else None) for name,obj in entries]
original={attr:saved(getattr(sdat,attr)[:778] if attr in ('banks','waveArchives') else getattr(sdat,attr)) for attr in ('sequences','sequenceArchives','banks','waveArchives')}
sdat.banks=sdat.banks[:778]; sdat.waveArchives=sdat.waveArchives[:778]
manifest=json.loads((ROOT/'files/fakemon/assets.json').read_text())
for row in manifest['species']:
    with wave.open(str(ROOT/'files/fakemon'/row['key']/'cry.wav'),'rb') as w:
        assert w.getnchannels()==1 and w.getsampwidth()==2
        rate=w.getframerate(); samples=struct.unpack('<'+'h'*w.getnframes(),w.readframes(w.getnframes()))
    # The stock special cry player reads PCM8 samples from the SWAR directly.
    pcm=bytes((max(-128,min(127,round(x/256)))&255) for x in samples)
    pcm+=bytes(-len(pcm)%4)
    wav=SWAV.fromData(pcm,sampleRate=rate,time=int(16756991/rate),totalLength=len(pcm)//4)
    archive=SWAR();archive.waves=[wav]
    bank=copy.deepcopy(sdat.banks[1][1]);bank.waveArchiveIDs=[row['cry_bank']]
    name='FAKEMON_'+row['key'].upper()
    sdat.banks.append(('BANK_'+name,bank));sdat.waveArchives.append(('WAVE_ARC_'+name,archive))
result=sdat.save(); check=SDAT(result)
for attr,expected in original.items():
    current=getattr(check,attr)
    if attr in ('banks','waveArchives'): current=current[:778]
    assert saved(current)==expected,attr
path.write_bytes(result)
print('Appended eleven cries at bank/wave IDs778–788; all original sequences, banks and waves preserved.')
