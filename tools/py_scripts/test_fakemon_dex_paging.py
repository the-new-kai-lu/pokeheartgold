#!/usr/bin/env python3
"""Test actual page/input routines and guard against the cover-screen hook regression."""
from pathlib import Path
import subprocess
import tempfile
from test_fakemon_dex_ui import extract
ROOT=Path(__file__).resolve().parents[2]
def main():
    text=(ROOT/'src/application/pokedex/ov18_021E590C.c').read_text()
    ui=(ROOT/'src/application/pokedex/ov18_021E8BF4.c').read_text()
    for state,expected in [(6,False),(11,True),(57,True)]:
        function=extract(ui,f'static int PokedexApp_MainSeq_{state:02d}(PokedexAppData *pokedexApp) {{')
        assert ('FakemonDexHandlePageInput(pokedexApp)' in function)==expected, f'Paging attached to wrong UI state {state}'
    code=r"""
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
typedef uint8_t u8; typedef uint16_t u16; typedef int BOOL;
#define TRUE 1
#define FALSE 0
#define SPECIES_NONE 0
#define SPECIES_VOLTUFF 1076
#define SPECIES_RAGNAROC 1086
#define IsFakemonSpecies(x) ((x)>=SPECIES_VOLTUFF&&(x)<=SPECIES_RAGNAROC)
#define PAD_BUTTON_SELECT 4
#include "fakemon_dex_pages.h"
static u16 sFakemonDexPageSpecies;static u8 sFakemonDexPage;
struct {unsigned newKeys;} gSystem;
typedef struct {void *pokedex;} Args;
typedef struct {Args *args;u16 species;BOOL caught;} PokedexAppData;
static PokedexAppData app;
u16 ov18_021F8838(PokedexAppData *a){return a->species;}
BOOL Pokedex_CheckMonCaughtFlag(void *dex,u16 species){(void)dex;(void)species;return app.caught;}
"""
    for signature,source in [('void FakemonDexResetPage(void)',text),('void FakemonDexSelectSpecies(u16 species)',text),('BOOL FakemonDexCyclePage(u16 species)',text),('static BOOL FakemonDexHandlePageInput(PokedexAppData *pokedexApp)',ui)]:
        code+='\n'+extract(source,signature)
    code+=r"""
int main(void){int n=0;Args args={0};app.args=&args;app.caught=1;
for(int species=1076;species<=1086;species++){
  FakemonDexResetPage();app.species=species;
  int count=species==1083?3:2;assert(sFakemonDexPageCounts[species-1076]==count);
  for(int i=1;i<=count*3;i++){
    gSystem.newKeys=PAD_BUTTON_SELECT;assert(FakemonDexHandlePageInput(&app));
    assert(sFakemonDexPageSpecies==species&&sFakemonDexPage==i%count);n++;
    gSystem.newKeys=1;assert(!FakemonDexHandlePageInput(&app));assert(sFakemonDexPage==i%count);n++;
  }
}
FakemonDexResetPage();app.species=1083;app.caught=0;gSystem.newKeys=PAD_BUTTON_SELECT;
assert(!FakemonDexHandlePageInput(&app));assert(sFakemonDexPage==0&&sFakemonDexPageSpecies==1083);n++;
app.caught=1;app.species=1;assert(!FakemonDexHandlePageInput(&app));assert(sFakemonDexPageSpecies==1);n++;
app.species=1083;assert(FakemonDexHandlePageInput(&app));assert(sFakemonDexPage==1);
FakemonDexResetPage();assert(sFakemonDexPage==0&&sFakemonDexPageSpecies==0);n++;
for(int caught=0;caught<=1;caught++){
 app.species=1083;app.caught=1;gSystem.newKeys=PAD_BUTTON_SELECT;assert(FakemonDexHandlePageInput(&app));assert(sFakemonDexPage==1);
 app.species=1;app.caught=caught;gSystem.newKeys=0;assert(!FakemonDexHandlePageInput(&app));assert(sFakemonDexPage==0&&sFakemonDexPageSpecies==1);n++;
 app.species=1083;app.caught=1;assert(!FakemonDexHandlePageInput(&app));assert(sFakemonDexPage==0&&sFakemonDexPageSpecies==1083);n++;
}
printf("Dex paging/input cases: %d; cover/grid state binding checks: 3\n",n);return 0;}
"""
    with tempfile.TemporaryDirectory(prefix='fakemon-dex-paging-') as tmp:
        source=Path(tmp)/'test.c';source.write_text(code)
        exe=Path(tmp)/'test'
        subprocess.run(['cc','-std=c99','-Wall','-Wextra','-iquote',str(ROOT/'include'),str(source),'-o',str(exe)],check=True)
        subprocess.run([str(exe)],check=True)
if __name__=='__main__':main()
