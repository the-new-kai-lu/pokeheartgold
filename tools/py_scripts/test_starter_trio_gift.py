#!/usr/bin/env python3
"""Exercise actual gift C and assembled Elm scripts without a DS emulator.

Build the Elm script first with COMPARE=0. Rendering, sound, timing, and actual
nickname input remain emulator checks; this checks data and control flow.
"""
import argparse
import itertools
import re
import struct
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_gift_backend():
    source = re.sub(r'^#include[^\n]*\n', '', (ROOT / 'src/choose_starter.c').read_text(), flags=re.M)
    stub = r'''
#include <assert.h>
#include <stdlib.h>
#include <string.h>
#include <stdio.h>
#include "constants/species.h"
#include "constants/pokemon.h"
#include "constants/items.h"
#include "constants/balls.h"
typedef unsigned int u32;
typedef int BOOL;
#define TRUE 1
#define FALSE 0
#define NELEMS(a) (sizeof(a)/sizeof((a)[0]))
#define GF_ASSERT assert
#define HEAP_ID_FIELD2 4
struct TaskManager;
typedef struct Pokemon {int species,level,ball,mapsec,encounter,item,ot;} Pokemon;
typedef struct PlayerProfile {int id;} PlayerProfile;
typedef struct Party {int count; Pokemon mons[6];} Party;
typedef struct SaveData {Party party; PlayerProfile profile;} SaveData;
typedef struct Location {int mapId;} Location;
typedef struct FieldSystem {SaveData *saveData; Location *location; struct TaskManager *taskman;} FieldSystem;
typedef struct TaskManager {FieldSystem *fieldSystem; u32 state;} TaskManager;
static BOOL (*task)(TaskManager *);
static int calls[5], ncall, caught[3], ncaught, allocations;
static FieldSystem *TaskManager_GetFieldSystem(TaskManager *t) {return t->fieldSystem;}
static u32 *TaskManager_GetStatePtr(TaskManager *t) {return &t->state;}
static void TaskManager_Call(TaskManager *t, BOOL (*f)(TaskManager *),void *p) {assert(!p); task=f; t->state=0;}
static void PaletteFadeUntilFinished(TaskManager *t) {(void)t;calls[ncall++]=1;}
static void CallTask_LeaveOverworld(TaskManager *t) {(void)t;calls[ncall++]=2;}
static void CallTask_RestoreOverworld(TaskManager *t) {(void)t;calls[ncall++]=3;}
static void CallTask_FadeFromBlack(TaskManager *t) {(void)t;calls[ncall++]=4;}
static Party *SaveArray_Party_Get(SaveData *s) {return &s->party;}
static PlayerProfile *Save_PlayerData_GetProfile(SaveData *s) {return &s->profile;}
static u32 MapHeader_GetMapSec(int map) {assert(map==42);return 7;}
static Pokemon *AllocMonZeroed(int heap) {assert(heap==HEAP_ID_FIELD2);allocations++;return calloc(1,sizeof(Pokemon));}
static void Heap_Free(void *p) {allocations--;free(p);}
static int Party_GetCount(Party *p) {return p->count;}
static void ZeroMonData(Pokemon *m) {memset(m,0,sizeof(*m));}
static void CreateMon(Pokemon *m,int species,int level,int ivs,int fixed,int pid,int ot,int otid) {
    assert(level==5 && ivs==32 && !fixed && !pid && ot==OT_ID_PLAYER_ID && !otid);
    m->species=species;m->level=level;
}
static void sub_020720FC(Pokemon *m,PlayerProfile *p,int ball,int sec,int encounter,int heap) {
    assert(heap==HEAP_ID_FIELD2);m->ot=p->id;m->ball=ball;m->mapsec=sec;m->encounter=encounter;
}
static void SetMonData(Pokemon *m,int field,void *value) {assert(field==MON_DATA_HELD_ITEM);m->item=*(int*)value;}
static BOOL Party_AddMon(Party *p,Pokemon *m) {assert(p->count<6);p->mons[p->count++]=*m;return TRUE;}
static void UpdatePokedexWithReceivedSpecies(SaveData *s,Pokemon *m) {(void)s;assert(ncaught<3);caught[ncaught++]=m->species;}
'''
    main = r'''
int main(void) {
    SaveData save={0}; Location loc={42}; FieldSystem fs={&save,&loc,NULL}; TaskManager manager={&fs,0};
    const int expected[]={SPECIES_VOLTUFF,SPECIES_EMBERNEWT,SPECIES_SEDGLING};
    save.profile.id=0x12345678; fs.taskman=&manager;
    LaunchStarterChoiceScene(&fs);
    for(int phase=0;phase<4;phase++) assert(!task(&manager));
    assert(task(&manager)); assert(manager.state==4 && ncall==4 && ncaught==3 && !allocations);
    assert(save.party.count==3);
    for(int i=0;i<4;i++) assert(calls[i]==i+1);
    for(int i=0;i<3;i++) {
        Pokemon *m=&save.party.mons[i];
        assert(m->species==expected[i] && caught[i]==expected[i] && m->level==5);
        assert(m->ot==save.profile.id && m->ball==BALL_POKE && m->mapsec==7 && m->encounter==12 && m->item==ITEM_NONE);
    }
    puts("Actual starter task: three Lv.5 starters, own OT/memo/ball, Dex, field lifecycle, heap cleanup pass.");
}
'''
    with tempfile.TemporaryDirectory(prefix='phg-starter-task-') as folder:
        path = Path(folder)
        (path / 'test.c').write_text(stub + source + main)
        subprocess.run(['cc', '-std=c99', '-Wall', '-Wextra', '-Werror', '-iquote', str(ROOT / 'include'),
                        str(path / 'test.c'), '-o', str(path / 'test')], check=True)
        subprocess.run([str(path / 'test')], check=True)


class ElmScript:
    """Strict interpreter for commands used by the assembled gift route."""
    def __init__(self, data, entry, x=4, names=(False, False, False), retry=False, flags=()):
        self.data = data
        self.pc = 4 * entry + 4 + struct.unpack_from('<i', data, 4 * entry)[0]
        self.stack, self.vars, self.flags = [], {}, set(flags)
        self.cmp = 0
        self.x, self.names, self.retry = x, names, retry
        self.gifts, self.named, self.messages = 0, [], []
        self.starter, self.unlocked = None, False

    def read(self, fmt='H'):
        val = struct.unpack_from('<' + fmt, self.data, self.pc)[0]
        self.pc += struct.calcsize('<' + fmt)
        return val

    def var(self, raw):
        return self.vars.get(raw, 0) if raw >= 0x4000 else raw

    def condition(self, op):
        return (self.cmp < 0, self.cmp == 0, self.cmp > 0,
                self.cmp <= 0, self.cmp >= 0, self.cmp != 0)[op]

    def run(self):
        for _ in range(1000):
            op = self.read()
            if op == 2:
                assert not self.stack
                return self
            if op in (22, 26):
                delta = self.read('i')
                if op == 26:
                    self.stack.append(self.pc)
                self.pc += delta
            elif op == 27:
                self.pc = self.stack.pop()
            elif op in (28, 29):
                cond, delta = self.read('B'), self.read('i')
                if self.condition(cond):
                    if op == 29:
                        self.stack.append(self.pc)
                    self.pc += delta
            elif op == 17:
                a, b = self.read(), self.read()
                self.cmp = self.var(a) - b
            elif op in (30, 31, 32):
                flag = self.read()
                if op == 30:
                    self.flags.add(flag)
                elif op == 31:
                    self.flags.discard(flag)
                else:
                    self.cmp = 0 if flag in self.flags else -1
            elif op == 41:
                key, value = self.read(), self.read()
                self.vars[key] = value
            elif op == 45:
                self.messages.append(self.read('B'))
            elif op == 105:
                vx, vy = self.read(), self.read()
                self.vars[vx], self.vars[vy] = self.x, 10
            elif op == 131:
                self.starter = self.var(self.read())
            elif op == 167:
                self.gifts += 1
            elif op == 173:
                slot, result = self.var(self.read()), self.read()
                self.named.append(slot)
                self.vars[result] = 1
            elif op == 748:
                out = self.read()
                if self.messages[-1] == 8:
                    self.vars[out] = 0 if self.names[self.vars[0x4002]] else 1
                elif self.messages[-1] == 9:
                    self.vars[out] = 1 if self.retry else 0
                    self.retry = False
                else:
                    raise AssertionError('Unexpected menu')
            elif op == 97:
                self.unlocked = True
            else:
                sizes = {3:4, 50:0, 53:0, 73:2, 78:2, 79:0, 94:6, 95:0, 96:0,
                         104:0, 132:2, 174:8, 175:0, 190:1, 193:3, 199:3, 609:0, 746:0, 747:0}
                assert op in sizes, f'Unsupported opcode {op} at {self.pc - 2:#x}'
                self.pc += sizes[op]
        raise AssertionError('Gift script did not terminate')


def test_packaged_content(rom_path):
    import ndspy.narc
    import ndspy.rom
    rom = ndspy.rom.NintendoDSRom.fromFile(str(rom_path))
    scripts = ndspy.narc.NARC(rom.getFileByName('a/0/1/2'))
    messages = ndspy.narc.NARC(rom.getFileByName('a/0/2/7'))
    assert scripts.files[843] == (ROOT / 'files/fielddata/script/scr_seq/scr_seq_0843_T20R0101.bin').read_bytes(), 'Packaged Elm script differs'
    for number, stem in ((543, 'msg_0543_T20R0101'), (550, 'msg_0550_T21')):
        assert messages.files[number] == (ROOT / 'files/msgdata/msg' / (stem + '.bin')).read_bytes(), f'Packaged dialogue {number} differs'
    print(f'{rom_path}: packaged Elm script and both dialogue banks match the tested build.')


def test_compiled_script():
    script = ROOT / 'files/fielddata/script/scr_seq/scr_seq_0843_T20R0101.bin'
    source = script.with_suffix('.s')
    assert script.exists() and script.stat().st_mtime >= source.stat().st_mtime, 'Build the Elm script first.'
    data = script.read_bytes()
    cases = 0
    for x in (3, 4, 5, 6):
        for names in itertools.product((False, True), repeat=3):
            for retry in (False, True):
                state = ElmScript(data, 11, x=x, names=names, retry=retry).run()
                assert state.gifts == 1 and state.starter == 152
                assert 0x6A in state.flags and 0x160 not in state.flags
                assert state.vars[0x4108] == 1 and state.vars[0x4072] == 1 and state.unlocked
                expected = [i for i, name in enumerate(names) if name]
                if retry and expected:
                    expected.insert(0, expected[0])
                assert state.named == expected
                cases += 1
    for flags, message in (((), 6), ((0x6A,), 15), ((0x6A, 0x99), 16), ((0x6A, 0x99, 0x73), 17)):
        state = ElmScript(data, 12, flags=flags).run()
        assert state.gifts == 0 and state.messages == [message] and state.unlocked
        cases += 1
    state = ElmScript(data, 11, flags=(0x6A,)).run()
    assert state.gifts == 0 and state.unlocked
    print(f'Compiled Elm script: {cases + 1} gift/nickname/retry/table/re-entry flow cases pass.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--rom', type=Path, action='append', default=[], help='Also verify the packaged script/dialogue; requires ndspy. Repeat for both versions.')
    args = parser.parse_args()
    test_gift_backend()
    test_compiled_script()
    for rom_path in args.rom:
        test_packaged_content(rom_path)
