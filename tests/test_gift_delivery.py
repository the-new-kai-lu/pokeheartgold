"""Host execution of production gift functions with bounded storage API doubles.

This tests routing/metadata/ownership, not encrypted save serialization or the
ARM ABI. No ROM, SDK, or copyrighted binary fixture is needed.
"""
import importlib.util
import json
from pathlib import Path
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import types
import unittest

ROOT = Path(__file__).resolve().parents[1]


def function(path, name):
    source = (ROOT / path).read_text()
    start = re.search(r"^(?:BOOL|u16) " + name + r"\(", source, re.M).start()
    opening = source.index("{", start)
    depth = 1
    end = opening + 1
    while depth:
        depth += (source[end] == "{") - (source[end] == "}")
        end += 1
    return source[start:end]


HARNESS = r"""
#include <assert.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
typedef uint8_t u8;
typedef uint16_t u16;
typedef uint32_t u32;
typedef int BOOL;
enum HeapID { HEAP_ID_FIELD2 };
#define TRUE 1
#define FALSE 0
#define ITEM_POKE_BALL 4
#define NUM_BOXES 18
enum { MON_DATA_HELD_ITEM, MON_DATA_FORM, MON_DATA_ABILITY };
typedef struct { int species, level, form, ability, item, map, encounter, ot; } Pokemon;
typedef Pokemon BoxPokemon;
typedef struct { int count; Pokemon mons[6]; } Party;
typedef struct { int count; Pokemon mons[540]; } PCStorage;
typedef struct { int id; } PlayerProfile;
typedef struct { Party party; PCStorage pc; PlayerProfile profile; int dex; } SaveData;
typedef struct { int mapId; } Location;
typedef struct { SaveData *saveData; Location *location; } FieldSystem;
typedef struct { FieldSystem *fieldSystem; u16 args[6], result; int pos; } ScriptContext;
static int allocations, releases, pc_calls, dex_calls, refuse_pc;
static SaveData save, before;
static PlayerProfile *Save_PlayerData_GetProfile(SaveData *s) { return &s->profile; }
static Party *SaveArray_Party_Get(SaveData *s) { return &s->party; }
static PCStorage *SaveArray_PCStorage_Get(SaveData *s) { return &s->pc; }
static int Party_GetCount(const Party *p) { return p->count; }
static int Party_GetMaxCount(const Party *p) { (void)p; return 6; }
static int PCStorage_FindFirstBoxWithEmptySlot(PCStorage *p) {
    return p->count == 540 ? NUM_BOXES : p->count / 30;
}
static Pokemon *AllocMonZeroed(enum HeapID h) {
    assert(h == HEAP_ID_FIELD2); allocations++; return calloc(1, sizeof(Pokemon));
}
static void ZeroMonData(Pokemon *p) { memset(p, 0, sizeof(*p)); }
static void CreateMon(Pokemon *p, int species, int level, int iv, int fixed,
                      int pid, int otType, int ot) {
    assert(iv == 32 && !fixed && !pid && !otType && !ot);
    p->species = species; p->level = level; p->ability = 65;
}
static void sub_020720FC(Pokemon *p, PlayerProfile *profile, int ball,
                        int map, int encounter, enum HeapID h) {
    assert(ball == ITEM_POKE_BALL && h == HEAP_ID_FIELD2);
    p->map = map; p->encounter = encounter; p->ot = profile->id;
}
static void SetMonData(Pokemon *p, int field, const void *v) {
    if (field == MON_DATA_HELD_ITEM) p->item = *(const u32 *)v;
    else if (field == MON_DATA_FORM) p->form = *(const int *)v;
    else { assert(field == MON_DATA_ABILITY); p->ability = *(const u8 *)v; }
}
static BOOL Party_AddMon(Party *p, Pokemon *m) {
    if (p->count == 6) return FALSE;
    p->mons[p->count++] = *m; return TRUE;
}
static BoxPokemon *Mon_GetBoxMon(Pokemon *m) { return m; }
static BOOL PCStorage_PlaceMonInFirstEmptySlotInAnyBox(PCStorage *p, BoxPokemon *m) {
    pc_calls++;
    if (p->count == 540 || refuse_pc) return FALSE;
    p->mons[p->count++] = *m; return TRUE;
}
static void UpdatePokedexWithReceivedSpecies(SaveData *s, Pokemon *p) {
    dex_calls++; s->dex = p->species;
}
static void Heap_Free(void *p) { releases++; free(p); }
static u32 MapHeader_GetMapSec(int map) { assert(map == 101); return 77; }
static u16 ScriptGetVar(ScriptContext *ctx) { return ctx->args[ctx->pos++]; }
static u16 *ScriptGetVarPointer(ScriptContext *ctx) {
    assert(ctx->pos == 5 && ctx->args[ctx->pos++] == 0x8000);
    return &ctx->result;
}
/* PRODUCTION_FUNCTIONS */
static void reset(int party, int pc) {
    memset(&save, 0, sizeof(save));
    save.party.count = party; save.pc.count = pc; save.profile.id = 12345;
    for (int i = 0; i < party; i++) save.party.mons[i].species = i + 1;
    for (int i = 0; i < pc; i++) save.pc.mons[i].species = i + 10;
    before = save;
    allocations = releases = pc_calls = dex_calls = refuse_pc = 0;
}
static void run(int party, int pc, int expected, int ability) {
    reset(party, pc);
    Location location = {101};
    FieldSystem field = {&save, &location};
    ScriptContext ctx = {&field, {252, 5, 42, 1, ability, 0x8000}, 99, 0};
    assert(ScrCmd_GiveMonToPartyOrPC(&ctx) == FALSE);
    assert(ctx.pos == 6 && ctx.result == expected);
    assert(allocations == (expected != GIVE_MON_NO_SPACE) && releases == allocations);
    assert(memcmp(save.party.mons, before.party.mons, party * sizeof(Pokemon)) == 0);
    assert(memcmp(save.pc.mons, before.pc.mons, pc * sizeof(Pokemon)) == 0);
    assert(save.profile.id == before.profile.id);
    if (expected == GIVE_MON_NO_SPACE) {
        assert(memcmp(&save, &before, sizeof(save)) == 0);
        assert(dex_calls == 0 && pc_calls == 0);
    } else {
        Pokemon *gift = expected == GIVE_MON_PARTY ? &save.party.mons[party] : &save.pc.mons[pc];
        assert(gift->species == 252 && gift->level == 5 && gift->form == 1);
        assert(gift->item == 42 && gift->ability == (ability ? ability : 65));
        assert(gift->ot == 12345 && gift->map == 77 && gift->encounter == 24);
        assert(save.dex == 252 && dex_calls == 1);
        assert(save.party.count == party + (expected == GIVE_MON_PARTY));
        assert(save.pc.count == pc + (expected == GIVE_MON_PC));
        assert(pc_calls == (expected == GIVE_MON_PC));
    }
}
int main(void) {
    run(0, 540, GIVE_MON_PARTY, 0);
    run(5, 540, GIVE_MON_PARTY, 12);
    run(6, 0, GIVE_MON_PC, 0);
    run(6, 539, GIVE_MON_PC, 12);
    run(6, 540, GIVE_MON_NO_SPACE, 0);
    /* Failed receipt stays retryable after a slot is freed. */
    save.pc.count--;
    assert(GiveMonToPartyOrPC(HEAP_ID_FIELD2, &save, 255, 5, 0, 0, 0, 77, 24) == GIVE_MON_PC);
    assert(save.pc.count == 540 && save.dex == 255);
    /* Never mark receipt from preflight alone if insertion rejects it. */
    reset(6, 539);
    refuse_pc = 1;
    assert(GiveMonToPartyOrPC(HEAP_ID_FIELD2, &save, 252, 5, 0, 0, 0, 77, 24) == GIVE_MON_NO_SPACE);
    assert(!dex_calls && allocations == 1 && releases == 1);
    assert(memcmp(&save, &before, sizeof(save)) == 0);
    /* Existing GiveMon stays party-only, even with empty boxes. */
    reset(6, 0);
    assert(!GiveMon(HEAP_ID_FIELD2, &save, 252, 5, 0, 0, 0, 77, 24));
    assert(!pc_calls && !dex_calls && allocations == releases);
    assert(memcmp(&save, &before, sizeof(save)) == 0);
    return 0;
}
"""


class GiftDeliveryTests(unittest.TestCase):
    def test_production_delivery_and_script_adapter(self):
        self.assertIsNotNone(shutil.which("cc"), "Host C compiler required for gift tests")
        constants = "\n".join(re.findall(
            r"^#define GIVE_MON_\w+\s+\d+", (ROOT / "include/constants/scrcmd.h").read_text(), re.M))
        functions = "\n".join([
            function("src/script_pokemon_util.c", "GiveMon"),
            function("src/script_pokemon_util.c", "GiveMonToPartyOrPC"),
            function("src/scrcmd_party.c", "ScrCmd_GiveMonToPartyOrPC"),
        ])
        source = HARNESS.replace("/* PRODUCTION_FUNCTIONS */", constants + "\n" + functions)
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp)
            (path / "gift.c").write_text(source)
            subprocess.run(["cc", "-std=c99", "-Wall", "-Wextra", "-Werror",
                            str(path / "gift.c"), "-o", str(path / "gift")], check=True)
            subprocess.run([str(path / "gift")], check=True)

    def test_opcode_assembly_and_decompiler_roundtrip(self):
        self.assertIsNotNone(shutil.which("as"), "Host assembler required for script encoding test")
        macros = (ROOT / "asm/macros/script.inc").read_text()
        macro = re.search(r"^\.macro GiveMonToPartyOrPC .*?^\.endm", macros, re.M | re.S).group()
        commands = json.loads((ROOT / "tools/py_scripts/scrcmd.json").read_text())["commands"]
        table = (ROOT / "src/data/fieldmap/script_cmd_table.h").read_text().split("= {", 1)[1].split("};", 1)[0]
        entries = [entry.strip() for entry in table.split(",") if entry.strip()]
        self.assertEqual(854, len(entries))
        self.assertEqual("ScrCmd_GiveMonToPartyOrPC", entries[853])
        self.assertEqual("GiveMonToPartyOrPC", commands[853]["name"])
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp)
            def assemble(instruction):
                (path / "script.s").write_text(macro + "\n" + instruction + "\n.short 2\n")
                subprocess.run(["as", "-o", str(path / "script.o"), str(path / "script.s")], check=True)
                subprocess.run(["objcopy", "-O", "binary", "-j", ".text", str(path / "script.o"), str(path / "script.bin")], check=True)
                return (path / "script.bin").read_bytes()
            binary = assemble("GiveMonToPartyOrPC 252, 5, 0, 0, 0, 32768")
            self.assertEqual(struct.pack("<8H", 853, 252, 5, 0, 0, 0, 32768, 2), binary)
            # Only the CLI progress display dependency is stubbed; decode with
            # the repository's real parser and real opcode/argument metadata.
            progress = types.ModuleType("progressbar")
            progress.progressbar = lambda items, **kwargs: items
            previous = sys.modules.get("progressbar")
            sys.modules["progressbar"] = progress
            try:
                spec = importlib.util.spec_from_file_location("gift_script_dump", ROOT / "tools/py_scripts/dump_scrcmds.py")
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                parser = module.NormalScriptParser("", binary, "", "")
                # Keep decoded arguments numeric so reassembly needs no SDK headers.
                parser.constants = {key: {} for key in parser.constants}
                parser.parse_script(0)
                name, args, end = parser.lines[0]
                self.assertEqual(14, end)
                self.assertEqual(binary, assemble(name + " " + ", ".join(map(str, args))))
                self.assertEqual("End", parser.lines[end][0])
            finally:
                if previous is None:
                    del sys.modules["progressbar"]
                else:
                    sys.modules["progressbar"] = previous