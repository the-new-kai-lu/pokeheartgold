#!/usr/bin/env python3
"""Compile and execute real compact Dex-number/row-building routines on the host."""
from pathlib import Path
import subprocess
import tempfile
ROOT=Path(__file__).resolve().parents[2]
def extract(source, signature):
    a=source.index(signature); b=source.index('{',a)+1; depth=1
    while depth:
        depth+=(source[b]=='{')-(source[b]=='}'); b+=1
    return source[a:b]
def main():
    source=(ROOT/'src/application/pokedex/ov18_021E590C.c').read_text()
    functions=extract((ROOT/'src/pokedex_util.c').read_text(),'u32 FakemonDexDisplayNumber(')+'\n'+extract(source,'void ov18_021F8884(')
    functions=functions.replace('\\n','\n')
    harness=r"""
#include <stdint.h>
#include <string.h>
#include <assert.h>
#include <stdio.h>
typedef uint16_t u16; typedef uint32_t u32; typedef int BOOL;
#define NATIONAL_DEX_COUNT 493
#define SPECIES_VOLTUFF 1076
#define SPECIES_RAGNAROC 1086
#define IsFakemonSpecies(x) ((x)>=SPECIES_VOLTUFF&&(x)<=SPECIES_RAGNAROC)
#define NELEMS(x) (sizeof(x)/sizeof((x)[0]))
#define GF_ASSERT(x) assert(x)
#define MI_CpuClear32(p,n) memset(p,0,n)
typedef struct {u16 unk_0,unk_2;} Row;
typedef struct {u32 before;Row unk_1030[518];u32 after;int unk_1858;struct {u16 unk_000[504][2];u16 unk_7B4,unk_7B6;}unk_0878;}PokedexAppData;
u32 Pokedex_ConvertToCurrentDexNo(BOOL national,u32 species){return national?species:species;}
"""+functions+r"""
int main(void){PokedexAppData a={0};int i,n=0;
a.before=0x12345678;a.after=0x87654321;a.unk_1858=1;a.unk_0878.unk_7B4=504;
for(i=0;i<504;i++){a.unk_0878.unk_000[i][0]=i<493?i+1:1076+i-493;a.unk_0878.unk_000[i][1]=i%2+1;}
ov18_021F8884(&a,1);
for(i=0;i<504;i++){assert(a.unk_1030[i].unk_0==a.unk_0878.unk_000[i][0]);assert(a.unk_1030[i].unk_2==a.unk_0878.unk_000[i][1]);n++;}
for(i=504;i<518;i++)assert(a.unk_1030[i].unk_0==0);
assert(a.before==0x12345678&&a.after==0x87654321);
ov18_021F8884(&a,0);assert(a.unk_1030[0].unk_0==0);
for(i=0;i<504;i++){assert(a.unk_1030[i+1].unk_0==a.unk_0878.unk_000[i][0]);n++;}
for(i=1076;i<=1086;i++){assert(FakemonDexDisplayNumber(1,i)==(u32)(494+i-1076));assert(FakemonDexDisplayNumber(0,i)==0);n+=2;}
a.unk_0878.unk_7B4=0;ov18_021F8884(&a,1);for(i=0;i<518;i++)assert(a.unk_1030[i].unk_0==0);
assert(a.before==0x12345678&&a.after==0x87654321);printf("Dex row/number cases: %d, plus empty-list and guard checks\n",n);return 0;}
"""
    with tempfile.TemporaryDirectory(prefix='fakemon-dex-') as temp:
        path=Path(temp)/'test.c';path.write_text(harness)
        subprocess.run(['cc','-std=c99','-Wall','-Wextra',str(path),'-o',str(Path(temp)/'test')],check=True)
        subprocess.run([str(Path(temp)/'test')],check=True)
if __name__=='__main__':main()
