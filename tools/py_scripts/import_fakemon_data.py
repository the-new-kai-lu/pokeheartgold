#!/usr/bin/env python3
"""Import approved data while preserving every stock member and stock TM/tutor inventory.
Run using hg-engine/.venv/bin/python (ndspy is required).
"""
import copy,json,re,struct,subprocess
from pathlib import Path
import ndspy.narc
ROOT=Path(__file__).resolve().parents[2]
SOURCE=ROOT.parent/'hg-engine'
BASE='9d8b7591f09b65804da2fb2dfd56f320633e0d36'
def original(path):
    return subprocess.check_output(['git','-C',str(ROOT),'show',BASE+':'+path])
def constants(path):
    return {k:int(v,0) for k,v in re.findall(r'^#define\s+(MOVE_\w+)\s+(0x[0-9a-fA-F]+|[0-9]+)\b',path.read_text(),re.M)}
meta=json.loads((SOURCE/'documentation/fakemon/designs-2026-09/species.json').read_text())
mons=[m for line in meta['lines'] for m in line['designs']]
learn=json.loads((SOURCE/'data/learnsets/learnsets.json').read_text())
oldmoves=constants(SOURCE/'include/constants/moves.h')
stockmoves=constants(ROOT/'include/constants/moves.h')
stockmoves.update({ 'MOVE_'+m:468+i for i,m in enumerate(['WILD_CHARGE','SNARL','INCINERATE','FIRE_LASH','ICICLE_CRASH','BULLDOZE','HURRICANE']) })
byid={v:k for k,v in stockmoves.items() if v<=467}
def moveid(name):
    if name in stockmoves: return stockmoves[name]
    if oldmoves[name] <=467: return oldmoves[name]
    return None
machine_table=re.findall(r'MOVE_\w+',(ROOT/'src/item.c').read_text().split('sTMHMMoves[] = {')[1].split('};')[0])
tutor_table=re.findall(r'\{ (MOVE_\w+),',(ROOT/'src/field/scrcmd_move_tutor.c').read_text().split('sTutorMoves[] = {')[1].split('};')[0])
statkeys={'hp':'hp','attack':'atk','defense':'def','speed':'speed','sp_attack':'spatk','sp_defense':'spdef'}
egggroups={'Field':'FIELD','Human-Like':'HUMAN_LIKE','Monster':'MONSTER','Dragon':'DRAGON','Water 1':'WATER_1','Flying':'FLYING'}
personal=json.loads(original('files/poketool/personal/personal.json'))
assert len(personal['baseStats'])==508
while len(personal['baseStats'])<1087:
    filler=copy.deepcopy(personal['baseStats'][0]); filler['species']='RESERVED_'+str(len(personal['baseStats'])); personal['baseStats'].append(filler)
wotbl=ndspy.narc.NARC(original('files/poketool/personal/wotbl.narc'))
while len(wotbl.files)<1087: wotbl.files.append(b'\xff\xff\x00\x00')
evo=json.loads(original('files/poketool/personal/evo.json'))
evolutions={'voltuff':('surguenon',16),'surguenon':('raijinque',49),'embernewt':('pyrovaran',16),'pyrovaran':('magmalisk',49),'rimevaran':('fimbulisk',49),'sedgling':('cragaviar',16),'cragaviar':('ragnaroc',49)}
report={'scope':'stock HGSS machines/tutors; seven additional level-up moves', 'species':[]}
ctutor=[]; cegg=[]; chatch=[]
for m in mons:
    key=m['key']; sid=m['engine_species_id']; ls=learn['SPECIES_'+key.upper()]
    mon=copy.deepcopy(personal['baseStats'][0]); mon['species']=key.upper()
    for k,v in statkeys.items(): mon[v]=m['base_stats'][k]; mon[v+'_yield']=m['ev_yield'][k]
    mon['types']=['TYPE_'+t.upper() for t in m['types']]; mon['types']=(mon['types']*2)[:2]
    mon.update(catchRate=45,expYield={1:64,2:142,3:255}[m['concept_stage']],genderRatio=0.5,eggCycles=20,friendship=70,growthRate=m['growth_rate'].upper().replace(' ','_'))
    mon['eggGroups']=['EGG_GROUP_'+egggroups[g] for g in m['breeding']['egg_groups']]
    mon['abilities']=['ABILITY_'+m['abilities']['primary'].upper().replace(' ','_'),'ABILITY_NONE']
    mon['color']={'voltuff':4,'surguenon':4,'raijinque':4,'embernewt':0,'pyrovaran':0,'magmalisk':0,'rimevaran':2,'fimbulisk':2,'sedgling':5,'cragaviar':5,'ragnaroc':5}[key]
    machineids={moveid(v) for v in ls.get('MachineMoves',[])}
    mon['tms']=[i+1 for i,n in enumerate(machine_table[:92]) if stockmoves[n] in machineids]
    mon['hms']=[i+1 for i,n in enumerate(machine_table[92:]) if stockmoves[n] in machineids]
    personal['baseStats'][sid]=mon
    packed=[]
    for v in ls['LevelMoves']:
        mid=moveid(v['Move']); assert mid is not None and mid<512,v
        packed.append((v['Level']<<9)|mid)
    packed.append(65535)
    assert len(packed) <= 21
    blob=struct.pack('<'+'H'*len(packed),*packed); wotbl.files[sid]=blob
    if key in evolutions:
        nxt,level=evolutions[key]; evo['evoTable'].append({'baseSpecies':'SPECIES_'+key.upper(),'evos':[{'method':'EVO_LEVEL','param':level,'target':'SPECIES_'+nxt.upper()}]})
    tmoves={moveid(v) for v in ls.get('TutorMoves',[])}
    bits=sum(1<<i for i,n in enumerate(tutor_table) if stockmoves[n] in tmoves)
    ctutor.append('    { '+', '.join('0x%02X'%v for v in bits.to_bytes(8,'little'))+' },')
    eggs=[moveid(v) for v in ls.get('EggMoves',[])]; assert None not in eggs and len(eggs)<=16
    cegg.append('    { '+', '.join(map(str,eggs+[65535]))+' },')
    chatch.append('    SPECIES_'+m['breeding']['hatch_species'].upper()+',')
    report['species'].append({'species_id':sid,'name':m['name'],'tms':mon['tms'],'hms':mon['hms'],'level_moves':ls['LevelMoves'],'omitted_machine_moves':[v for v in ls.get('MachineMoves',[]) if moveid(v) not in {stockmoves[n] for n in machine_table}], 'omitted_tutor_moves':[v for v in ls.get('TutorMoves',[]) if moveid(v) not in {stockmoves[n] for n in tutor_table}]})
(ROOT/'files/poketool/personal/personal.json').write_text(json.dumps(personal,indent=2)+'\n')
(ROOT/'files/poketool/personal/evo.json').write_text(json.dumps(evo,indent=2)+'\n')
(ROOT/'files/poketool/personal/wotbl.narc').write_bytes(wotbl.save())
p=ROOT/'files/poketool/personal/evo.json.txt'; p.write_text(p.read_text().replace('[NUM_SPECIES + 1]','[FAKEMON_DATA_COUNT]'))
(ROOT/'include/fakemon_data.h').write_text('// Generated by import_fakemon_data.py.\nstatic const u8 sFakemonTutorMoves[FAKEMON_COUNT][8] = {\n'+'\n'.join(ctutor)+'\n};\nstatic const u16 sFakemonEggMoves[FAKEMON_COUNT][17] = {\n'+'\n'.join(cegg)+'\n};\nstatic const u16 sFakemonHatchSpecies[FAKEMON_COUNT] = {\n'+'\n'.join(chatch)+'\n};\n')
(ROOT/'documentation/fakemon/learnset-port.json').write_text(json.dumps(report,indent=2)+'\n')
print('Imported 11 species, evolutions, learnsets and stock machine/tutor compatibility.')
