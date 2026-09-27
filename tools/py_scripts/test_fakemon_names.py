#!/usr/bin/env python3
"""Check HGSS names and actual nickname reads over encrypted/locked PK4 records.

Extract the real data layouts, normalization, nickname cases, public getters,
locks, checksum and block shuffle from pokemon.c. Stub only the platform cipher,
message-bank reads, and String/mail APIs for host execution.
"""
import argparse
import hashlib
import json
import re
import subprocess
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
META = json.loads((ROOT / 'files/fakemon/species.json').read_text())
MONS = sorted((m for line in META['lines'] for m in line['designs']), key=lambda m: m['engine_species_id'])
SOURCE = (ROOT / 'src/pokemon.c').read_text()


def function(name):
    match = re.search(r'^.*\b' + name + r'\([^;\n]*\) \{', SOURCE, re.M)
    assert match, name
    end = SOURCE.index('{', match.start()) + 1
    depth = 1
    while depth:
        depth += (SOURCE[end] == '{') - (SOURCE[end] == '}')
        end += 1
    return SOURCE[match.start():end] + '\n'


def check_text():
    checks = 0
    for bank in [237, 238, 817, 818, 819, 820, 821, 822]:
        path = ROOT / f'files/msgdata/msg/msg_{bank:04}.gmm'
        rows = {int(r.attrib['index']): r.find("language[@name='English']").text for r in ET.parse(path).findall('.//row')}
        for mon in MONS:
            expected = mon['name'].upper()
            if bank == 238:
                expected = ('an' if mon['name'][0] in 'AEIOU' else 'a') + ' {COLOR 255}' + expected + '{COLOR 0}'
            assert rows[mon['engine_species_id']] == expected, (bank, mon['name'])
            checks += 1
    for path in (ROOT / 'files/msgdata/msg').glob('*.gmm'):
        text = path.read_text()
        for mon in MONS:
            assert not re.search(r'\b' + mon['name'] + r'\b', text), (path, mon['name'])
    prose = 0
    for bank in range(803, 812):
        path = ROOT / f'files/msgdata/msg/msg_{bank:04}.gmm'
        rows = {int(r.attrib['index']): r.find("language[@name='English']").text or '' for r in ET.parse(path).findall('.//row')}
        for mon in MONS:
            expected = mon['pokedex_details']['entry_text']
            for species in MONS:
                expected = re.sub(r'\b' + re.escape(species['name']) + r'\b', species['name'].upper(), expected)
            sid = mon['engine_species_id']
            actual = ' '.join(rows.get(sid + 11 * page, '').replace('\\n', ' ') for page in range(3)).strip()
            assert actual == expected, (bank, mon['name'])
            prose += 1
    print(f'{checks} species-name rows, {prose} complete Dex entries and all in-game dialogue casing passed.')
    return checks, prose


def check_records():
    declarations = (ROOT / 'include/pokemon_types_def.h').read_text()
    declarations = declarations[declarations.index('// Structs'):declarations.index('struct UnkPokemonStruct_02072A98')]
    macros = SOURCE[SOURCE.index('#define ENCRY_ARGS_PTY'):SOURCE.index('#define SHINY_CHECK')]
    cases = SOURCE[SOURCE.index('    case MON_DATA_NICKNAME:\n'):SOURCE.index('    case MON_DATA_UNUSED_121:\n')]
    program = r'''
#include <assert.h>
#include <stddef.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#define PLAYER_NAME_LENGTH 7
#define POKEMON_NAME_LENGTH 10
#include "constants/pokemon.h"
#include "constants/species.h"
#include "constants/charcode.h"
typedef uint8_t u8; typedef int8_t s8; typedef uint16_t u16;
typedef uint32_t u32; typedef uint64_t u64; typedef int BOOL;
#define TRUE 1
#define FALSE 0
#define HEAP_ID_DEFAULT 0
#define GF_ASSERT assert
typedef struct {u8 data[24];} CAPSULE;
#pragma pack(push,4)
''' + declarations + '\n#pragma pack(pop)\n' + macros + r'''
typedef struct {u16 text[POKEMON_NAME_LENGTH+1];} String;
static const char *names[] = {NAMES};
static unsigned name_reads;
static void encode(const char *s,u16 *dest) {
    int i=0;
    for(;s[i];i++) dest[i]=(s[i]>='a'&&s[i]<='z')?CHAR_a+s[i]-'a':CHAR_A+s[i]-'A';
    dest[i]=EOS;
}
static void GetSpeciesNameIntoArray(u16 species,int heap,u16 *dest) {
    (void)heap; name_reads++;
    if(species==SPECIES_MANAPHY_EGG) {encode("EGG",dest);return;}
    assert(IsFakemonSpecies(species));encode(names[species-SPECIES_VOLTUFF],dest);
}
static int StringNotEqual(const u16 *a,const u16 *b) {
    for(int i=0;i<=POKEMON_NAME_LENGTH;i++) {if(a[i]!=b[i])return 1;if(a[i]==EOS)return 0;}
    assert(0);return 1;
}
static void CopyU16ArrayToString(String *s,const u16 *in) {
    for(int i=0;i<=POKEMON_NAME_LENGTH;i++) {s->text[i]=in[i];if(in[i]==EOS)return;}
}
static String *GetSpeciesName(u16 species,int heap) {
    static String s;GetSpeciesNameIntoArray(species,heap,s.text);return &s;
}
static void String_Copy(String *out,String *in) {*out=*in;}
static void String_Delete(String *s) {(void)s;}
static void Mail_Copy(Mail *in,void *out) {memcpy(out,in,sizeof(*in));}
static void CopyCapsule(CAPSULE *in,void *out) {memcpy(out,in,sizeof(*in));}
// Symmetric DS cipher: XOR words against successive LCRNG high words.
static void MonEncryptSegment(void *data,u32 size,u32 seed) {
    u16 *p=data;
    for(u32 i=0;i<size/2;i++) {seed=seed*0x41C64E6Du+0x6073u;p[i]^=(u16)(seed>>16);}
}
static void MonDecryptSegment(void *data,u32 size,u32 seed) {MonEncryptSegment(data,size,seed);}
static u32 GetMonDataInternal(Pokemon *,int,void *);
static u32 GetBoxMonDataInternal(BoxPokemon *,int,void *);
'''
    program = program.replace('NAMES', ','.join(json.dumps(m['name'].upper()) for m in MONS))
    for name in ['CalcMonChecksum', 'GetSubstruct', 'AcquireMonLock', 'ReleaseMonLock', 'AcquireBoxMonLock', 'ReleaseBoxMonLock', 'NormalizeFakemonDefaultNickname', 'GetMonData', 'GetBoxMonData', 'GetMonDataInternal']:
        program += function(name)
    program += '''static u32 GetBoxMonDataInternal(BoxPokemon *boxMon,int attr,void *dest) {
    u32 ret=0;
    PokemonDataBlockA *blockA=&GetSubstruct(boxMon,boxMon->personality,0)->blockA;
    PokemonDataBlockB *blockB=&GetSubstruct(boxMon,boxMon->personality,1)->blockB;
    PokemonDataBlockC *blockC=&GetSubstruct(boxMon,boxMon->personality,2)->blockC;
    switch(attr) {
''' + cases + '''    default: assert(0);
    }
    return ret;
}
'''
    program += r'''
int main(void) {
    assert(sizeof(BoxPokemon)==136 && sizeof(Pokemon)==236 && sizeof(PartyPokemon)==100);
    unsigned tests=0;
    const int attrs[]={MON_DATA_NICKNAME,MON_DATA_NICKNAME_STRING,MON_DATA_NICKNAME_STRING_AND_FLAG};
    for(int sid=SPECIES_VOLTUFF;sid<=SPECIES_RAGNAROC;sid++)
    for(unsigned shuffle=0;shuffle<32;shuffle++)
    for(int mode=0;mode<4;mode++)
    for(int ai=0;ai<3;ai++)
    for(int scenario=0;scenario<9;scenario++) {
        int party=(mode<2),locked=(mode&1);
        if(scenario==8 && !locked)continue; // Public unlocked getters assert on a bad checksum.
        Pokemon mon={0};
        mon.box.personality=(shuffle<<13)|0x123;
        PokemonDataBlockA *a=&GetSubstruct(&mon.box,mon.box.personality,0)->blockA;
        PokemonDataBlockB *b=&GetSubstruct(&mon.box,mon.box.personality,1)->blockB;
        PokemonDataBlockC *c=&GetSubstruct(&mon.box,mon.box.personality,2)->blockC;
        a->species=(scenario==6?SPECIES_PIKACHU:sid);
        a->heldItem=123;a->otID=0x12345678;a->exp=999;a->ability=9;
        b->moves[0]=84;b->moveCurrentPPs[0]=30;b->hpIV=31;
        // Nonzero trash after EOS must remain untouched during normalization.
        for(int i=0;i<11;i++)c->nickname[i]=CHAR_x;
        encode(names[sid-SPECIES_VOLTUFF],c->nickname);
        if(scenario!=1) for(int i=1;c->nickname[i]!=EOS;i++)c->nickname[i]+=CHAR_a-CHAR_A;
        if(scenario==2 || scenario==7) {encode("Sparky",c->nickname);b->hasNickname=scenario==2;}
        if(scenario==3)b->hasNickname=1; // Intentionally nicknamed title-case species name.
        if(scenario==4)b->isEgg=1;
        if(scenario==5)mon.box.checksumFailed=1;
        mon.party.hp=19;mon.party.maxHP=23;mon.party.level=5;mon.party.status=8;
        Pokemon plain=mon;
        mon.box.checksum=CHECKSUM(&mon.box)+(scenario==8);
        ENCRYPT_BOX(&mon.box);ENCRYPT_PTY(&mon);
        if(locked) {if(party)AcquireMonLock(&mon);else AcquireBoxMonLock(&mon.box);}
        u16 raw[11]={0};String text={0};
        void *out=(ai==0?(void *)raw:(void *)&text);
        unsigned reads=name_reads;
        u32 result=party?GetMonData(&mon,attrs[ai],out):GetBoxMonData(&mon.box,attrs[ai],out);
        if(scenario!=0)assert(name_reads==reads+(scenario==5||scenario==7||scenario==8));
        if(scenario==8)assert(mon.box.checksum!=CHECKSUM(&mon.box));
        if(locked) {if(party)ReleaseMonLock(&mon,TRUE);else ReleaseBoxMonLock(&mon.box,TRUE);}
        DECRYPT_BOX(&mon.box);DECRYPT_PTY(&mon);
        assert(mon.box.checksum==CHECKSUM(&mon.box));
        assert(!mon.box.partyDecrypted && !mon.box.boxDecrypted);
        if(ai==2)assert(result==GetSubstruct(&plain.box,plain.box.personality,1)->blockB.hasNickname);
        u16 expected[11];
        if(scenario==0) {
            encode(names[sid-SPECIES_VOLTUFF],expected);
            PokemonDataBlockC *pc=&GetSubstruct(&plain.box,plain.box.personality,2)->blockC;
            for(int i=0;expected[i]!=EOS;i++)pc->nickname[i]=expected[i];
        } else if(scenario==5)encode("EGG",expected);
        else memcpy(expected,GetSubstruct(&plain.box,plain.box.personality,2)->blockC.nickname,sizeof(expected));
        assert(!StringNotEqual(ai==0?raw:text.text,expected));
        assert(!memcmp(mon.box.dataBlocks,plain.box.dataBlocks,sizeof(plain.box.dataBlocks)));
        assert(!memcmp(&mon.party,&plain.party,sizeof(plain.party)));
        // Reading the migrated record a second time must preserve its exact bytes.
        mon.box.checksum=CHECKSUM(&mon.box);ENCRYPT_BOX(&mon.box);ENCRYPT_PTY(&mon);
        Pokemon saved=mon;
        if(party)GetMonData(&mon,attrs[ai],out);else GetBoxMonData(&mon.box,attrs[ai],out);
        if(scenario==8) {
            // ReleaseLock finalized the caller's pending checksum, so migration
            // can safely occur on this subsequent unlocked read.
            encode(names[sid-SPECIES_VOLTUFF],expected);
            assert(!StringNotEqual(ai==0?raw:text.text,expected));
            DECRYPT_BOX(&mon.box);
            assert(mon.box.checksum==CHECKSUM(&mon.box));
        } else assert(!memcmp(&mon,&saved,sizeof(mon)));
        tests++;
    }
    printf("%u encrypted/locked party/box nickname cases passed.\n",tests);
    return 0;
}
'''
    with tempfile.TemporaryDirectory(prefix='fakemon-names-') as temp:
        source = Path(temp) / 'test.c'
        source.write_text(program)
        binary = Path(temp) / 'test'
        subprocess.run(['cc', '-std=c99', '-O2', '-Wall', '-Wextra', '-Werror', '-Wno-sign-compare', '-Wno-unused-variable', '-iquote', str(ROOT / 'include'), str(source), '-o', str(binary)], check=True)
        result = subprocess.run([str(binary)], check=True, text=True, capture_output=True)
        print(result.stdout, end='')
        return int(re.search(r'(\d+) encrypted/', result.stdout).group(1))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report', type=Path, help='Write reproducible JSON evidence for this source revision.')
    args = parser.parse_args()
    rows, prose = check_text()
    cases = check_records()
    if args.report:
        inputs = ['src/pokemon.c', 'include/pokemon_types_def.h', 'tools/py_scripts/test_fakemon_names.py', 'tools/py_scripts/import_fakemon_text.py']
        report = {
            'result': 'passed',
            'command': 'python3 tools/py_scripts/test_fakemon_names.py --report ' + str(args.report),
            'species_name_rows': rows,
            'complete_dex_entries': prose,
            'encrypted_record_cases': cases,
            'tested_species': [m['engine_species_id'] for m in MONS],
            'tested_apis': ['GetMonData', 'GetBoxMonData'],
            'tested_attributes': ['MON_DATA_NICKNAME', 'MON_DATA_NICKNAME_STRING', 'MON_DATA_NICKNAME_STRING_AND_FLAG'],
            'coverage': [
                'All 32 PID block-shuffle indexes, encrypted party and box records, and both lock states',
                'Title-case defaults become uppercase; already uppercase names remain unchanged',
                'Genuine nicknames, explicitly nicknamed title-case species names, Eggs, and stock species stay unchanged',
                'Checksum-failed records retain stored data and show the stock Egg fallback',
                'Unflagged non-default names stay unchanged',
                'Stale-checksum locked records defer normalization until the caller finalizes its checksum',
                'Stored nickname tail bytes and all unrelated decrypted party/box fields are preserved',
                'Updated checksums match stored records; subsequent reads preserve exact encrypted bytes',
                'All generated species-name rows and all custom species references in game prose/dialogue are uppercase',
            ],
            'limitations': ['Host cipher, message-bank and String APIs are stubs; actual emulator validation is separate.'],
            'source_sha256': {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in inputs},
        }
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, indent=2) + '\n')
