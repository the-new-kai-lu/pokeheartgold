#!/usr/bin/env python3
"""Differential host test of actual Pokeathlon calculation and custom fallback."""
from pathlib import Path
import re
import subprocess
import tempfile
ROOT=Path(__file__).resolve().parents[2]
BASE='9d8b7591f09b65804da2fb2dfd56f320633e0d36'

def extract(source,signature):
    start=source.index(signature);end=source.index('{',start)+1;depth=1
    while depth:
        depth+=(source[end]=='{')-(source[end]=='}');end+=1
    return source[start:end]

def array(source,name):
    return re.search(r'static const[^;]*\b'+name+r'\[.*?\n};',source,re.S).group(0)

def main():
    source=(ROOT/'src/pokemon.c').read_text()
    baseline=subprocess.check_output(['git','show',f'{BASE}:src/pokemon.c'],cwd=ROOT,text=True)
    signature='void CalcBoxMonPokeathlonPerformance('
    actual=extract(source,signature)
    original=extract(baseline,signature).replace('CalcBoxMonPokeathlonPerformance','OriginalPerformance',1)
    arrays=[]
    for name in ('sPokeathlonPerformanceArcIdxs','sPokeathlonPerformanceNatureMods'):
        current=array(source,name)
        assert current==array(baseline,name),name
        arrays.append(current)
    for signature in ('s16 PokeathlonStatScoreToStars(', 'void CalcBoxmonPokeathlonStars('):
        assert extract(source,signature)==extract(baseline,signature),'downstream star/Aprijuice behavior changed'
    types=(ROOT/'include/pokemon_types_def.h').read_text()
    structs='\n'.join(re.search(r'struct '+name+r' \{.*?\n};',types,re.S).group(0) for name in ('PokeathlonBasePerformance','TodayPerformanceStat','PokeathlonTodayPerformance'))
    harness=r"""
#include <stdint.h>
#include <string.h>
#include <assert.h>
#include <stdio.h>
typedef uint8_t u8;typedef int8_t s8;typedef uint16_t u16;typedef int16_t s16;typedef uint32_t u32;
#include "constants/pokemon.h"
#include "constants/species.h"
#define MI_CpuClear8(p,n) memset(p,0,n)
#define NARC_poketool_personal_performance 1
typedef struct {u16 species,form;u32 pid,nature;} BoxPokemon;
typedef struct {int day;} RTCDate;typedef int RTCTime;
static int day=1,reads;static u32 member;
u32 GetBoxMonData(BoxPokemon*m,int field,void*out){if(field==MON_DATA_SPECIES)return m->species;if(field==MON_DATA_FORM)return m->form;return m->pid;}
u32 GetBoxMonNature(BoxPokemon*m){return m->nature;}
void GF_RTC_CopyDateTime(RTCDate*d,RTCTime*t){d->day=day;*t=0;}
u32 _u32_getDigitN(u32 n,int digit){while(digit--)n/=10;return n%10;}
"""+structs+r"""
void ReadWholeNarcMemberByIdPair(struct PokeathlonBasePerformance*d,int narc,u32 id){int i;reads++;member=id;memset(d,0,sizeof(*d));for(i=0;i<5;i++){d->base[i]=1+(id+i)%5;d->minmax[i][0]=1;d->minmax[i][1]=5;}}
"""+'\n'.join(arrays)+'\n'+actual+'\n'+original+r"""
int main(void){BoxPokemon m={0};struct PokeathlonTodayPerformance a,b;int species,form,nature,i,cases=0,expected;
for(species=0;species<=493;species++)for(form=0;form<32;form++){
 m.species=species;m.form=form;m.nature=(species+form)%25;m.pid=0x12345678u+species*1337u+form;day=(species+form)%31+1;
 memset(&a,0,sizeof(a));memset(&b,0,sizeof(b));reads=0;OriginalPerformance(&m,&a);assert(reads==1);expected=member;
 reads=0;CalcBoxMonPokeathlonPerformance(&m,&b);assert(reads==1&&member==(u32)expected);assert(memcmp(&a,&b,sizeof(a))==0);cases++;
}
for(species=1076;species<=1086;species++)for(form=0;form<32;form++)for(nature=0;nature<25;nature++){
 m.species=species;m.form=form;m.nature=nature;m.pid=0xfedc1234u+species*3997u+form*111u+nature;day=(species+form+nature)%31+1;
 memset(&a,0,sizeof(a));memset(&b,0,sizeof(b));reads=0;CalcBoxMonPokeathlonPerformance(&m,&a);assert(reads==0);
 m.species=1;OriginalPerformance(&m,&b);
 for(i=0;i<5;i++){assert(a.stats[i].base==3&&a.stats[i].lo==2&&a.stats[i].hi==4);assert(a.stats[i].dailyMod==b.stats[i].dailyMod);}cases++;
}
printf("PASS: %d Pokeathlon cases; canonical lookup/modifiers preserved, custom species never access the archive.\n",cases);return 0;}
"""
    with tempfile.TemporaryDirectory(prefix='fakemon-performance-') as temp:
        path=Path(temp);(path/'test.c').write_text(harness)
        subprocess.run(['cc','-std=c99','-Wall','-Wextra','-Wno-unused-parameter','-Wno-sign-compare','-iquote',str(ROOT/'include'),str(path/'test.c'),'-o',str(path/'test')],check=True)
        subprocess.run([str(path/'test')],check=True)

if __name__=='__main__':main()
