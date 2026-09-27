#!/usr/bin/env python3
"""Compile the actual fakemon.c against minimal host SDK stubs; test rules/state."""
import subprocess,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
with tempfile.TemporaryDirectory(prefix='phg-fakemon-test-') as tmp:
    t=Path(tmp)
    (t/'fakemon.h').write_text((ROOT/'include/fakemon.h').read_text())
    (t/'global.h').write_text("""#pragma once
#include <stdint.h>
#include <stddef.h>
#include <string.h>
typedef uint8_t u8; typedef uint16_t u16; typedef uint32_t u32; typedef int BOOL;
#define TRUE 1
#define FALSE 0
#define MI_CpuClear8(p,s) memset(p,0,s)
#define MI_CpuCopy8(s,d,n) memcpy(d,s,n)
""")
    (t/'pokemon_types_def.h').write_text("""#pragma once
#include "global.h"
typedef struct Pokemon {u32 pid,ot; u16 species,item;u8 level;} Pokemon;
""")
    (t/'pokemon.h').write_text("""#pragma once
#include "pokemon_types_def.h"
#include "constants/pokemon.h"
#include "constants/species.h"
#define LEVEL_UP_LEARNSET_LVL(e) ((e) >> 9)
#define LEVEL_UP_LEARNSET_MOVE(e) ((e) & 511)
u32 GetMonData(Pokemon *, int, void *);
int CalcLevelBySpeciesAndExp(u16,u32);
u32 GetMonExpBySpeciesAndLevel(int,int);
""")
    (t/'test.c').write_text(r'''#include <assert.h>
#include <stdio.h>
#include "fakemon.h"
#include "pokemon.h"
#include "constants/items.h"
#include "constants/moves.h"
u32 GetMonData(Pokemon *m, int attr, void *unused) {
    (void)unused;
    switch(attr) {
      case MON_DATA_SPECIES:return m->species;
      case MON_DATA_HELD_ITEM:return m->item;
      case MON_DATA_PERSONALITY:return m->pid;
      case MON_DATA_OT_ID:return m->ot;
      case MON_DATA_LEVEL:return m->level;
      default:assert(0);return 0;
    }
}
u32 GetMonExpBySpeciesAndLevel(int s,int l) {
    if(l==1)return 0;
    if(s==SPECIES_VOLTUFF || s==SPECIES_EMBERNEWT || s==SPECIES_SEDGLING) return 6*l*l*l/5-15*l*l+100*l-140;
    return 5*l*l*l/4;
}
int CalcLevelBySpeciesAndExp(u16 s,u32 exp) {int l=1; while(l<100 && exp>=GetMonExpBySpeciesAndLevel(s,l+1))l++;return l;}
int main(void) {
    Pokemon m={0x12345678,0x87654321,SPECIES_EMBERNEWT,ITEM_NEVERMELTICE,16};
    unsigned long checks=0;
    const u16 from[]={SPECIES_VOLTUFF,SPECIES_EMBERNEWT,SPECIES_EMBERNEWT,SPECIES_SEDGLING};
    const u16 to[]={SPECIES_SURGUENON,SPECIES_PYROVARAN,SPECIES_RIMEVARAN,SPECIES_CRAGAVIAR};
    for(int j=0;j<4;j++) {
      for(unsigned x=0;x<=GetMonExpBySpeciesAndLevel(from[j],100);x++) {
        unsigned mapped=FakemonConvertEvolutionExp(from[j],to[j],x);
        int l=CalcLevelBySpeciesAndExp(from[j],x);
        assert(CalcLevelBySpeciesAndExp(to[j],mapped)==l);
        unsigned lo=GetMonExpBySpeciesAndLevel(from[j],l), nlo=GetMonExpBySpeciesAndLevel(to[j],l);
        if(l<100) {
          unsigned hi=GetMonExpBySpeciesAndLevel(from[j],l+1), nhi=GetMonExpBySpeciesAndLevel(to[j],l+1);
          unsigned expected=nlo+(uint64_t)(x-lo)*(nhi-nlo)/(hi-lo);
          assert(mapped==expected);
        }
        checks++;
      }
    }
    assert(FakemonConvertEvolutionExp(SPECIES_BULBASAUR,SPECIES_IVYSAUR,12345)==12345);
    assert(FakemonConvertEvolutionExp(SPECIES_SURGUENON,SPECIES_RAIJINQUE,12345)==12345);
    assert(FakemonConvertEvolutionExp(SPECIES_VOLTUFF,SPECIES_SURGUENON,9999999)==1250000);
    assert(FakemonHatchSpecies(SPECIES_FIMBULISK)==SPECIES_EMBERNEWT);
    assert(FakemonHatchSpecies(SPECIES_RAGNAROC)==SPECIES_SEDGLING);
    m.item=ITEM_ICICLE_PLATE;
    assert(FakemonLearnMove(&m,(14<<9)|MOVE_FIRE_FANG)==MOVE_ICE_FANG);
    assert(FakemonLearnMove(&m,(45<<9)|MOVE_FIRE_FANG)==MOVE_FIRE_FANG);
    m.item=ITEM_NEVERMELTICE;
    for(int slot=0;slot<6;slot++) for(int victim=0;victim<4;victim++) {
      FakemonBattleReset();
      FakemonRecordDirectKO(&m,slot,victim,TRUE,TYPE_ICE,TRUE,m.item);
      FakemonBeginExp(victim);
      FakemonOnBattleLevelUp(&m,slot);
      FakemonEndExp();
      assert(!FakemonConsumeRareEvolution(&m)); /* outside battle evolution */
      FakemonBattleEvolutionScope(TRUE, slot);
      assert(FakemonConsumeRareEvolution(&m));
      assert(!FakemonConsumeRareEvolution(&m)); /* consume/cancel cannot persist */
      checks+=3;
    }
    /* Exhaustively reject a missing causal predicate. */
    for(int correctType=0;correctType<2;correctType++)
    for(int correctItem=0;correctItem<2;correctItem++)
    for(int opponent=0;opponent<2;opponent++)
    for(int knockout=0;knockout<2;knockout++)
    for(int sameSlot=0;sameSlot<2;sameSlot++)
    for(int samePID=0;samePID<2;samePID++)
    for(int sameOT=0;sameOT<2;sameOT++)
    for(int sameVictim=0;sameVictim<2;sameVictim++)
    for(int reaches16=0;reaches16<2;reaches16++) {
      Pokemon levelMon=m; levelMon.pid+=!samePID;levelMon.ot+=!sameOT;levelMon.level=reaches16?16:15;
      FakemonBattleReset();
      FakemonRecordDirectKO(&m,0,1,opponent,correctType?TYPE_ICE:TYPE_FIRE,knockout,correctItem?ITEM_NEVERMELTICE:ITEM_ICICLE_PLATE);
      FakemonBeginExp(sameVictim?1:3);
      FakemonOnBattleLevelUp(&levelMon,sameSlot?0:1);
      FakemonBattleEvolutionScope(TRUE, sameSlot?0:1);
      assert(FakemonConsumeRareEvolution(&levelMon)==(correctType&&correctItem&&opponent&&knockout&&sameSlot&&samePID&&sameOT&&sameVictim&&reaches16));
      checks++;
    }
    FakemonBattleReset();FakemonRecordDirectKO(&m,0,1,TRUE,TYPE_ICE,TRUE,m.item);
    FakemonAfterHealthUpdate(1,1);FakemonBeginExp(1);FakemonOnBattleLevelUp(&m,0);
    FakemonBattleEvolutionScope(TRUE, 0);assert(!FakemonConsumeRareEvolution(&m));
    FakemonBattleReset();FakemonRecordDirectKO(&m,0,1,TRUE,TYPE_ICE,TRUE,m.item);
    FakemonBeginExp(1);FakemonEndExp();FakemonBeginExp(3);FakemonOnBattleLevelUp(&m,0);
    FakemonBattleEvolutionScope(TRUE, 0);assert(!FakemonConsumeRareEvolution(&m));
    FakemonBattleReset();FakemonRecordDirectKO(&m,2,1,TRUE,TYPE_ICE,TRUE,m.item);
    FakemonBeginExp(1);FakemonOnBattleLevelUp(&m,2);FakemonEndExp();
    FakemonBattleEvolutionScope(TRUE,0);assert(!FakemonConsumeRareEvolution(&m));
    FakemonBattleEvolutionScope(TRUE,2);assert(FakemonConsumeRareEvolution(&m));
    printf("%lu EXP/KO assertions plus targeted learning/hatching/reset cases passed\n",checks);
}
''')
    subprocess.run(['gcc','-std=c99','-O2','-Wall','-Wextra','-Werror','-I'+str(t),'-idirafter',str(ROOT/'include'),str(ROOT/'src/fakemon.c'),str(t/'test.c'),'-o',str(t/'test')],check=True)
    subprocess.run([str(t/'test')],check=True)
