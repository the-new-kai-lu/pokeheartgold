#!/usr/bin/env python3
"""Offline regression checks for the stock-based move port; needs ndspy and cc."""
from pathlib import Path
import hashlib
import re
import struct
import subprocess
import tempfile
import xml.etree.ElementTree as ET
from ndspy.narc import NARC
from port_fakemon_moves import ROOT, MOVES

BASE = '9d8b7591f09b65804da2fb2dfd56f320633e0d36'
def original(path):
    return subprocess.check_output(['git','show',f'{BASE}:{path}'],cwd=ROOT)

def main():
    archive = NARC((ROOT/'files/poketool/waza/waza_tbl.narc').read_bytes())
    stock = NARC(original('files/poketool/waza/waza_tbl.narc'))
    assert archive.files[:468] == stock.files[:468], 'canonical move data changed'
    assert len(archive.files) == 475
    for row in MOVES:
        mid, symbol, name, effect, category, power, mtype, accuracy, pp, chance, target, flags, animation = row
        got = struct.unpack('<H6BHbBBBH',archive.files[mid])
        assert got == (effect, category, power, mtype, accuracy, pp, chance, target, 0, flags, 0, 0, 0), (name,got)
    for bank in ['0749','0750','0751','0197']:
        path = f'files/msgdata/msg/msg_{bank}.gmm'
        before = ET.fromstring(original(path))
        after = ET.parse(ROOT/path).getroot()
        for i, row in enumerate(before):
            row.tail = after[i].tail = None
            assert ET.tostring(row) == ET.tostring(after[i]), (bank,i)
    # The disassembled AI calculates two unrelated fields from the old move base.
    # Those remain at 0x370; only actual move-table reads move to the tail.
    ai=(ROOT/'asm/overlay_10_trainer_ai.s').read_text()
    assert '0x000003DE' not in ai and '0x000003E1' not in ai
    assert ai.count('mov r3, #0x37') == 2
    # Differential checks protect unrelated ability/copy behavior. Me First compares
    # effects, so accidentally adding Snarl there would also ban stock Mist Ball.
    ability_path = 'src/battle/overlay_12_0224E4FC.c'
    ability_before = original(ability_path).decode()
    ability_after = (ROOT/ability_path).read_text()
    def move_array(source, name):
        body = re.search(r'\b' + name + r'\[\]\s*=\s*\{(.*?)\};', source, re.S).group(1)
        return re.findall(r'\bMOVE_[A-Z0-9_]+\b', body)
    assert move_array(ability_after, 'sMeFirstUnuseableMoves') == move_array(ability_before, 'sMeFirstUnuseableMoves'), 'canonical Me First restrictions changed'
    assert move_array(ability_after, 'sSoundMoves') == move_array(ability_before, 'sSoundMoves') + ['MOVE_SNARL'], 'Soundproof move list changed unexpectedly'
    assert ability_after.count('MOVE_SNARL') == 1, 'Snarl leaked into unrelated ability/move lists'
    source=(ROOT/'src/battle/battle_command.c').read_text()
    start=source.index('BOOL BtlCmd_TryIncinerate(')
    opening=source.index('{',start); depth=1; end=opening+1
    while depth:
        depth += (source[end]=='{') - (source[end]=='}'); end+=1
    function=source[start:end]
    harness=r"""
#include <stdint.h>
#include <assert.h>
#include <stdio.h>
typedef int BOOL; typedef uint16_t u16;
#define FALSE 0
#define ITEM_CHERI_BERRY 149
#define ITEM_ROWAP_BERRY 212
#define ITEM_NONE 0
#define MOVE_STATUS_DID_NOT_HIT 1
#define ABILITY_STICKY_HOLD 60
typedef struct {int unused;} BattleSystem;
typedef struct {u16 item;} Mon;
typedef struct {int battlerIdTarget,battlerIdAttacker; Mon battleMons[4]; unsigned moveStatusFlag; u16 itemTemp,recycleItem[4]; int blocked,sticky,jump,copies,pointer;} BattleContext;
void BattleScriptIncrementPointer(BattleContext*c,int n){c->pointer+=n;}
int BattleScriptReadWord(BattleContext*c){return c->jump;}
int BattlerCheckSubstitute(BattleContext*c,int id){return c->blocked;}
int CheckBattlerAbilityIfNotIgnored(BattleContext*c,int a,int b,int ability){return c->sticky;}
void CopyBattleMonToPartyMon(BattleSystem*b,BattleContext*c,int id){c->copies++;}
"""+function+r"""
int main(void){int item,flags,n=0;BattleSystem b={0};
for(item=0;item<=536;item++)for(flags=0;flags<8;flags++){
 BattleContext c={0};int destroy=item>=149&&item<=212&&flags==0;
 c.battlerIdTarget=1;c.battleMons[1].item=item;c.recycleItem[1]=300;c.itemTemp=400;c.jump=17;
 c.blocked=flags&1;c.sticky=flags&2;c.moveStatusFlag=(flags&4)?1:0;
 BtlCmd_TryIncinerate(&b,&c);
 assert(c.battleMons[1].item==(destroy?0:item));
 assert(c.recycleItem[1]==(destroy?0:300));
 assert(c.itemTemp==(destroy?item:400));
 assert(c.copies==destroy);assert(c.pointer==(destroy?1:18));n++;
}printf("Incinerate native cases: %d\n",n);return 0;}
"""
    with tempfile.TemporaryDirectory(prefix='fakemon-moves-') as temp:
        c=Path(temp)/'test.c'; c.write_text(harness)
        subprocess.run(['cc','-std=c99','-Wall','-Wextra','-Wno-unused-parameter',str(c),'-o',str(Path(temp)/'test')],check=True)
        subprocess.run([str(Path(temp)/'test')],check=True)
    print('PASS: 468 stock records and all original move/battle text entries unchanged; seven new records verified.')

if __name__ == '__main__': main()
