"""Source-only opt-in ABI and narrow host VM tests; no saves/ROMs/native SDK."""

import importlib.util
import json
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("campaign_host_support", ROOT / "tests/test_campaign_save.py")
CAMP = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CAMP)
PREP = CAMP.PREP


def episode_source(root):
    """Reconstruct the real actor opcode profile from published source edits."""
    CAMP.private_source(root)
    for name in PREP.BRIDGE_PREIMAGES:
        CAMP.put(root, name, (ROOT / name).read_bytes())
    recipe = json.loads((ROOT / "scripts/episode_templates/native_edits.json").read_bytes())
    for name in ("include/scrcmd.h", "src/data/fieldmap/script_cmd_table.h",
                 "asm/macros/script.inc", "src/scrcmd_c.c"):
        item = recipe[name]
        before = (ROOT / name).read_bytes()
        if PREP.sha(before) != item["before"]:
            raise AssertionError(f"Published actor fixture preimage mismatch: {name}")
        lines = before.decode().splitlines(keepends=True)
        previous = len(lines) + 1
        for edit in reversed(item["edits"]):
            start, end = edit["start"], edit["end"]
            if not 0 <= start <= end < previous or end > len(lines):
                raise AssertionError(f"Published actor fixture edits overlap: {name}")
            lines[start:end] = edit["lines"]
            previous = start
        after = "".join(lines).encode()
        if PREP.sha(after) != item["after"]:
            raise AssertionError(f"Published actor fixture output mismatch: {name}")
        if name in PREP.BRIDGE_PREIMAGES and item["after"] != PREP.BRIDGE_PREIMAGES[name]:
            raise AssertionError(f"Published actor profile differs from reviewed bridge input: {name}")
        CAMP.put(root, name, after)


HARNESS = r"""
#include "field_system.h"
#include "scrcmd.h"
#include "scrcmd_campaign.h"
#include "save_campaign.h"
#include "save_trainer_house.h"
#include <stdio.h>
#include <stdlib.h>

static SaveData save, before;
static FieldSystem field;
static SaveVarsFlags hostVars, hostBefore;
static unsigned persistentLookups, scratchLookups, rewards;
static u8 operands[8];

static SaveVarsFlags *Save_VarsFlags_Get(SaveData *s) { assert(s == &save); return &hostVars; }
static u16 *Save_VarsFlags_GetVarAddr(SaveVarsFlags *s, u16 id) {
    persistentLookups++; assert(id >= 0x4000 && id <= 0x416F); return &s->vars[id - 0x4000];
}
static void *FieldSysGetAttrAddr(FieldSystem *f, enum ScriptEnvField attr) {
    assert(attr >= SCRIPTENV_SPECIAL_VAR_8000 && attr <= SCRIPTENV_SPECIAL_VAR_LAST_INTERACTED);
    scratchLookups++;
    return &f->scratch[attr - SCRIPTENV_SPECIAL_VAR_8000];
}
u16 GF_CalcCRC16(const void *data, u32 size) { (void)data; (void)size; assert(0); return 0; }
void StringFillEOS(u16 *s, u32 n) { while (n--) *s++ = 0xFFFF; }
BOOL StringNotEqual(const u16 *a, const u16 *b) { return *a != *b; }
void *SaveArray_Get(SaveData *s, int id) { return s->dynamic_region + s->arrayHeaders[id].offset; }
"""


CASES = r"""
static CampaignSave *campaign(void) { return (CampaignSave *)(save.dynamic_region + 0xF614); }
static void initialize(void) {
    u32 i;
    memset(&save, 0, sizeof(save)); memset(&field, 0, sizeof(field));
    save.arrayHeaders[40].id = 40; save.arrayHeaders[40].slot = 0;
    save.arrayHeaders[40].offset = 0xE714; save.arrayHeaders[40].size = 0x1704;
    memset(save.dynamic_region + 0xE714, 0xDD, 0xF00);
    CampaignSave_Init(campaign()); save.flashChipDetected = TRUE;
    memset(campaign()->opaqueHeader, 0x67, sizeof(campaign()->opaqueHeader));
    memset(campaign()->reserved, 0x98, sizeof(campaign()->reserved));
    for (i = 0; i < NELEMS(hostVars.vars); i++) hostVars.vars[i] = (u16)(0x9100 + i);
    for (i = 0; i < 14; i++) field.scratch[i] = (u16)(0xA100 + i);
    field.saveData = &save;
    before = save; hostBefore = hostVars;
    persistentLookups = scratchLookups = rewards = 0;
}
static void word(u8 *p, u16 v) { p[0] = (u8)v; p[1] = (u8)(v >> 8); }
static ScriptContext context(u16 region, u16 id, u16 third, u16 status) {
    ScriptContext ctx;
    memset(&ctx, 0, sizeof(ctx)); ctx.mode = SCRIPT_MODE_BYTECODE;
    ctx.fieldSystem = &field; ctx.script_ptr = operands;
    word(operands, region); word(operands + 2, id); word(operands + 4, third); word(operands + 6, status);
    return ctx;
}
static ScrCmdFunc handlers[] = {
    ScrCmd_CampaignGetFlag, ScrCmd_CampaignSetFlag, ScrCmd_CampaignGetVar, ScrCmd_CampaignSetVar
};
static ScriptContext call(u32 which, u16 region, u16 id, u16 third, u16 status) {
    ScriptContext ctx = context(region, id, third, status);
    assert(handlers[which](&ctx) == FALSE); /* operation success is NOT VM yield */
    if (ctx.mode != SCRIPT_MODE_STOPPED) assert(ctx.script_ptr == operands + 8);
    assert(!memcmp(&hostVars, &hostBefore, sizeof(hostVars)));
    assert(persistentLookups == 0); /* donor IDs must never resolve stock saved vars */
    return ctx;
}
static void assertNoSavedMutation(void) { assert(!memcmp(&save, &before, sizeof(save))); }

static void test_success_and_literal_ids(void) {
    u16 value; BOOL flag;
    u32 region;
    initialize();
    for (region = 0; region < 2; region++) {
        u16 lastVar = region == 0 ? 0x40FF : 0x411F;
        u16 lastFlag = region == 0 ? 2399 : 2911;
        field.scratch[12] = 0xCAFE;
        call(3, region, 0x4000, 0x800C, 0x800C); /* value/status alias resolved before clobber */
        assert(field.scratch[12] == 1);
        assert(CampaignSave_GetVar(campaign(), region, 0x4000, &value) && value == 0xCAFE);
        call(3, region, lastVar, 0x1234, 0x800B);
        assert(field.scratch[11] == 1);
        call(2, region, lastVar, 0x8000, 0x800C);
        assert(field.scratch[0] == 0x1234 && field.scratch[12] == 1);
        call(1, region, lastFlag, 1, 0x800C);
        assert(field.scratch[12] == 1);
        call(0, region, lastFlag, 0x800A, 0x800C);
        assert(field.scratch[10] == 1 && field.scratch[12] == 1);
        assert(CampaignSave_GetFlag(campaign(), region, lastFlag, &flag) && flag);
        call(1, region, lastFlag, 0, 0x800C);
        call(0, region, lastFlag, 0x800A, 0x800C);
        assert(field.scratch[10] == 0 && field.scratch[12] == 1);
    }
    call(3, 0, 0x4000, 17, 0x800C);
    call(3, 1, 0x4000, 29, 0x800C);
    assert(CampaignSave_GetVar(campaign(), 0, 0x4000, &value) && value == 17);
    assert(CampaignSave_GetVar(campaign(), 1, 0x4000, &value) && value == 29);
    for (region = 0; region < 13; region++) {
        u16 status = (u16)(0x8000 + ((region + 1) % 13));
        call(2, 0, 0x4000, (u16)(0x8000 + region), status);
        assert(field.scratch[region] == 17 && field.scratch[status - 0x8000] == 1);
    }
    assert(!memcmp(save.dynamic_region + 0xE714, before.dynamic_region + 0xE714, 0xF00));
    assert(!memcmp(campaign()->opaqueHeader, ((CampaignSave *)(before.dynamic_region + 0xF614))->opaqueHeader, 18));
    assert(!memcmp(campaign()->reserved, ((CampaignSave *)(before.dynamic_region + 0xF614))->reserved, 264));
}

static void test_bounds_zero_and_bad_headers(void) {
    const u16 badRegions[] = {2, 0x8000, 0xFFFF};
    u32 region, which, i;
    initialize();
    campaign()->hoennFlags[0] = campaign()->sinnohFlags[0] = 1;
    before = save;
    for (region = 0; region < 2; region++) {
        call(1, region, 0, 1, 0x800C);
        assert(field.scratch[12] == 1);
        call(0, region, 0, 0x8000, 0x800C);
        assert(field.scratch[0] == 0 && field.scratch[12] == 1);
        call(1, region, 0, 0, 0x800C);
        assertNoSavedMutation();
        for (which = 0; which < 4; which++) {
            u16 id = which < 2 ? (region == 0 ? 2400 : 2912) : (region == 0 ? 0x4100 : 0x4120);
            call(which, region, id, (which % 2 == 0 ? 0x8000 : 3), 0x800C);
            assert(field.scratch[12] == 0); assertNoSavedMutation();
            call(which, region, 0xFFFF, (which % 2 == 0 ? 0x8000 : 3), 0x800C);
            assert(field.scratch[12] == 0); assertNoSavedMutation();
        }
        call(2, region, 0x3FFF, 0x8000, 0x800C);
        assert(field.scratch[0] == 0 && field.scratch[12] == 0); assertNoSavedMutation();
    }
    for (i = 0; i < NELEMS(badRegions); i++) {
        for (which = 0; which < 4; which++) {
            call(which, badRegions[i], (which < 2 ? 0x84 : 0x4000),
                 (which % 2 == 0 ? 0x8000 : 3), 0x800C);
            assert(field.scratch[12] == 0); assertNoSavedMutation();
        }
    }
    for (i = 0; i < 16; i++) {
        initialize();
        if (i < 14) ((u8 *)campaign())[i] ^= 0x80;
        else if (i == 14) save.arrayHeaders[40].size = 0xF04;
        else field.saveData = NULL;
        before = save;
        for (which = 0; which < 4; which++) {
            ScriptContext ctx = call(which, 0, (which < 2 ? 0x84 : 0x4000),
                                     (which % 2 == 0 ? 0x8000 : 3), 0x800C);
            if (i == 15) {
                assert(ctx.mode == SCRIPT_MODE_STOPPED && ctx.script_ptr == NULL);
                assertNoSavedMutation();
                continue;
            }
            assert(field.scratch[12] == 0); assertNoSavedMutation();
            if (which % 2 == 0) assert(field.scratch[0] == 0);
        }
    }
}

static void test_destinations_and_set_values(void) {
    const u16 invalid[] = {0, 0x3FFF, 0x4000, 0x4160, 0x7FFF, 0x800D, 0x800E, 0xFFFF};
    u16 scratches[14], value;
    u32 which, i;
    for (i = 0; i < NELEMS(invalid); i++) {
        for (which = 0; which < 4; which++) {
            ScriptContext ctx;
            initialize(); memcpy(scratches, field.scratch, sizeof(scratches));
            ctx = call(which, 0, (which < 2 ? 0x84 : 0x4000),
                       (which % 2 == 0 ? 0x8000 : 3), invalid[i]);
            assert(ctx.mode == SCRIPT_MODE_STOPPED && ctx.script_ptr == NULL);
            assert(!memcmp(scratches, field.scratch, sizeof(scratches))); assertNoSavedMutation();
        }
        for (which = 0; which < 4; which += 2) {
            initialize(); field.scratch[12] = 99;
            call(which, 0, (which == 0 ? 0x84 : 0x4000), invalid[i], 0x800C);
            assert(field.scratch[12] == 0); assertNoSavedMutation();
        }
    }
    for (which = 0; which < 4; which += 2) {
        initialize();
        call(which, 0, (which == 0 ? 0x84 : 0x4000), 0x800C, 0x800C);
        assert(field.scratch[12] == 0); assertNoSavedMutation();
    }
    for (i = 2; i < NELEMS(invalid); i++) {
        initialize();
        call(3, 0, 0x4000, invalid[i], 0x800C);
        assert(field.scratch[12] == 0); assertNoSavedMutation();
    }
    initialize(); field.scratch[0] = 0xFFFF;
    call(3, 0, 0x4000, 0x8000, 0x800C);
    assert(field.scratch[12] == 1);
    assert(CampaignSave_GetVar(campaign(), 0, 0x4000, &value) && value == 0xFFFF);
    call(3, 0, 0x4000, 0x3FFF, 0x800C);
    assert(field.scratch[12] == 1);
    assert(CampaignSave_GetVar(campaign(), 0, 0x4000, &value) && value == 0x3FFF);
    /* Aliased status is not clobbered before a valid value is resolved, even
     * when the donor ID subsequently fails validation. */
    initialize(); field.scratch[12] = 0xCAFE;
    call(3, 0, 0x4100, 0x800C, 0x800C);
    assert(field.scratch[12] == 0); assertNoSavedMutation();
}

static BOOL reward(ScriptContext *ctx) { rewards++; StopScript(ctx); return FALSE; }
static BOOL checkedReward(ScriptContext *ctx) {
    if (field.scratch[12] == 1) rewards++;
    StopScript(ctx); return FALSE;
}
static void test_actual_vm_stop_and_failure_status(void) {
    ScrCmdFunc table[859] = {0};
    u8 script[12];
    ScriptContext ctx;
    u32 which;
    table[0] = reward; table[1] = checkedReward;
    assert(CAMPAIGN_SCRIPT_FIRST_OPCODE == 855 && CAMPAIGN_SCRIPT_OPCODE_COUNT == 4);
    for (which = 0; which < 4; which++) table[855 + which] = handlers[which];
    for (which = 0; which < 4; which++) {
        initialize();
        ctx = context(0, (which < 2 ? 0x84 : 0x4000),
                      (which % 2 == 0 ? 0x8000 : 3), 0x800D);
        word(script, (u16)(855 + which)); memcpy(script + 2, operands, 8); word(script + 10, 0);
        ctx.cmdTable = table; ctx.cmd_count = 859; ctx.script_ptr = script;
        assert(RunScriptCommand(&ctx) == FALSE);
        assert(ctx.mode == SCRIPT_MODE_STOPPED && ctx.script_ptr == NULL && rewards == 0);
        assertNoSavedMutation();
        /* A valid status reports an operation failure synchronously, so the
         * following bytecode can explicitly check it before any reward. */
        initialize();
        ctx = context(2, (which < 2 ? 0x84 : 0x4000),
                      (which % 2 == 0 ? 0x8000 : 3), 0x800C);
        memcpy(script + 2, operands, 8); word(script + 10, 1);
        ctx.cmdTable = table; ctx.cmd_count = 859; ctx.script_ptr = script;
        assert(RunScriptCommand(&ctx) == FALSE);
        assert(field.scratch[12] == 0 && rewards == 0); assertNoSavedMutation();
    }
}

int main(int argc, char **argv) {
    assert(argc == 2);
    if (!strcmp(argv[1], "success")) test_success_and_literal_ids();
    else if (!strcmp(argv[1], "bounds")) test_bounds_zero_and_bad_headers();
    else if (!strcmp(argv[1], "destinations")) test_destinations_and_set_values();
    else if (!strcmp(argv[1], "vm")) test_actual_vm_stop_and_failure_status();
    else assert(0);
    puts("host campaign script bridge checks passed"); return 0;
}
"""


def build_host(directory):
    put, extract = CAMP.put, CAMP.function
    source = directory / "episode-source"
    source.mkdir()
    episode_source(source)
    changes = PREP.source_edits(source, script_bridge=True)
    for name in ("save.h", "save_trainer_house.h"):
        put(directory, name, (ROOT / "include" / name).read_bytes())
    put(directory, "global.h", CAMP.GLOBAL_STUB)
    globals_source = (ROOT / "include/constants/global.h").read_text()
    put(directory, "constants/global.h", "\n".join(
        re.search(r"^#define " + name + r"\s+\d+", globals_source, re.M).group()
        for name in ("PLAYER_NAME_LENGTH", "POKEMON_NAME_LENGTH", "PARTY_SIZE")) + "\n")
    put(directory, "heap.h", '#include "global.h"\nenum HeapID { HEAP_ID_DEFAULT = 0 };\n')
    pokemon = (ROOT / "include/pokemon_types_def.h").read_text()
    mail = re.search(r"typedef struct MailMessage \{.*?\} MailMessage;", pokemon, re.S).group()
    put(directory, "pokemon_types_def.h", '#include "global.h"\n#define MAILMSG_FIELDS_MAX 2\n' + mail)
    put(directory, "string_util.h", '#include "global.h"\nvoid StringFillEOS(u16 *, u32);\nBOOL StringNotEqual(const u16 *, const u16 *);\n')
    put(directory, "math_util.h", '#include "global.h"\nu16 GF_CalcCRC16(const void *, u32);\n')
    put(directory, "field_system.h", '#ifndef HOST_FIELD_H\n#define HOST_FIELD_H\n#include "save.h"\n'
        'typedef struct FieldSystem { SaveData *saveData; u16 scratch[14]; } FieldSystem;\n'
        'typedef struct SaveVarsFlags { u16 vars[0x170]; } SaveVarsFlags;\n#endif\n')
    script_source = (ROOT / "include/script.h").read_text()
    environment_enum = re.search(r"typedef enum ScriptEnvField \{.*?\} ScriptEnvField;", script_source, re.S).group()
    context_struct = re.search(r"struct ScriptContext \{.*?\};", script_source, re.S).group()
    put(directory, "script.h", '#ifndef HOST_SCRIPT_H\n#define HOST_SCRIPT_H\n#include "field_system.h"\n'
        '#include "constants/vars.h"\n#define SCRIPT_MODE_STOPPED 0\n#define SCRIPT_MODE_BYTECODE 1\n'
        '#define SCRIPT_MODE_NATIVE 2\n#define ScriptReadByte(ctx) *(ctx->script_ptr++)\n'
        'typedef struct TaskManager TaskManager;\ntypedef struct MsgData MsgData;\n'
        'typedef struct ScriptContext ScriptContext;\ntypedef BOOL (*ScrCmdFunc)(ScriptContext *);\n'
        + environment_enum + "\n" + context_struct + '\nvoid StopScript(ScriptContext *);\n'
        'u16 ScriptReadHalfword(ScriptContext *);\n#endif\n')
    native_header = (ROOT / "include/scrcmd.h").read_text()
    put(directory, "scrcmd.h", '#include "script.h"\nu16 *GetVarPointer(FieldSystem *, u16);\n'
        'u16 FieldSystem_VarGet(FieldSystem *, u16);\n' + extract(native_header, "ScriptGetVar"))
    for name in ("save_campaign", "scrcmd_campaign"):
        for suffix in ("h", "c"):
            put(directory, f"{name}.{suffix}", changes[f"{'include' if suffix == 'h' else 'src'}/{name}.{suffix}"])
    put(directory, "save_trainer_house.c", (ROOT / "src/save_trainer_house.c").read_bytes())
    manager = (ROOT / "src/script_manager.c").read_text()
    vm = (ROOT / "src/script.c").read_text()
    native_functions = "\n".join(extract(manager, name) for name in ("GetVarPointer", "FieldSystem_VarGet"))
    native_functions += "\n" + "\n".join(extract(vm, name) for name in ("ScriptReadHalfword", "StopScript", "RunScriptCommand"))
    put(directory, "bridge_host.c", HARNESS + native_functions + CASES)
    binary = directory / "bridge_host"
    command = ["cc", "-std=c99", "-O1", "-Wall", "-Wextra", "-Werror", "-Wno-unknown-pragmas",
               "-iquote", str(directory), "-iquote", str(ROOT / "include"),
               *(str(directory / name) for name in ("bridge_host.c", "scrcmd_campaign.c", "save_campaign.c", "save_trainer_house.c")),
               "-o", str(binary)]
    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode:
        raise AssertionError("Host bridge compiler failed:\n" + result.stdout + result.stderr)
    return binary


@unittest.skipUnless(shutil.which("cc"), "host C compiler required")
class CampaignScriptBridgeHostTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(prefix="campaign-bridge-host-")
        cls.binary = build_host(Path(cls.tmp.name))

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def run_case(self, name):
        result = subprocess.run([str(self.binary), name], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_literal_ids_regions_values_and_scratch_alias_resolution(self):
        self.run_case("success")

    def test_bounds_zero_flag_and_invalid_allocation_header_never_repair(self):
        self.run_case("bounds")

    def test_destinations_aliases_and_bounded_native_value_resolution(self):
        self.run_case("destinations")

    def test_actual_native_stop_prevents_reward_and_failure_status_is_checkable(self):
        self.run_case("vm")


class CampaignScriptBridgeProducerTests(unittest.TestCase):
    def test_default_five_file_scope_and_opt_in_eleven_file_abi(self):
        default = PREP.source_edits(ROOT)
        with tempfile.TemporaryDirectory(prefix="campaign-bridge-abi-") as tmp:
            source = Path(tmp)
            episode_source(source)
            bridged = PREP.source_edits(source, script_bridge=True)
            original_table = (source / "src/data/fieldmap/script_cmd_table.h").read_text()
            original_assembly = (source / "asm/macros/script.inc").read_bytes()
            original_header = (source / "include/scrcmd.h").read_bytes()
            actor_function = CAMP.function((source / "src/scrcmd_c.c").read_text(), "ScrCmd_EnsureRoute101Actors")
            self.assertEqual(actor_function.count("ScriptGetVarPointer(ctx)"), 1)
        self.assertEqual(len(default), 5)
        self.assertEqual(len(bridged), 11)
        for name, data in default.items():
            if name != "main.lsf":
                self.assertEqual(bridged[name], data)
        table = bridged["src/data/fieldmap/script_cmd_table.h"].decode()
        names = re.findall(r"^\s+([A-Za-z_]\w*),$", table, re.M)
        original_names = re.findall(r"^\s+([A-Za-z_]\w*),$", original_table, re.M)
        self.assertEqual(len(original_names), 855)
        self.assertEqual(original_names[854], "ScrCmd_EnsureRoute101Actors")
        self.assertEqual(names[:-4], original_names)
        self.assertEqual(names[-4:], ["ScrCmd_" + name for name in PREP.BRIDGE_COMMANDS])
        self.assertIn("sNumScriptCmds = NELEMS(gScriptCmdTable)", table)
        schema = json.loads(bridged["tools/py_scripts/scrcmd.json"])
        original = json.loads((ROOT / "tools/py_scripts/scrcmd.json").read_bytes())
        self.assertEqual(schema["commands"][:-5], original["commands"])
        self.assertEqual(schema["commands"][854], {"name": "EnsureRoute101Actors", "args": [2]})
        self.assertEqual(len(schema["commands"]), 859)
        self.assertEqual(schema["argtypes"], original["argtypes"])
        restored_assembly = bridged["asm/macros/script.inc"]
        restored_header = bridged["include/scrcmd.h"]
        for opcode, name in enumerate(PREP.BRIDGE_COMMANDS, 855):
            self.assertEqual(schema["commands"][opcode], {"name": name, "args": [2, 2, 2, 2]})
            third = "out" if "Get" in name else "value"
            macro = (f".macro {name} region, id, {third}, status\n.short {opcode}\n"
                     f".short \\region\n.short \\id\n.short \\{third}\n.short \\status\n.endm\n")
            self.assertIn(macro.encode(), bridged["asm/macros/script.inc"])
            self.assertIn(f"BOOL ScrCmd_{name}(ScriptContext *ctx);".encode(), bridged["include/scrcmd.h"])
            restored_assembly = restored_assembly.replace(macro.encode() + b"\n", b"", 1)
            restored_header = restored_header.replace(f"BOOL ScrCmd_{name}(ScriptContext *ctx);\n".encode(), b"", 1)
        self.assertEqual(restored_assembly, original_assembly)
        self.assertEqual(restored_header, original_header)
        self.assertIn(b".macro EnsureRoute101Actors result\n.short 854\n.short \\result\n.endm\n", original_assembly)
        self.assertEqual(bridged["main.lsf"].count(b"Object src/scrcmd_campaign.o"), 1)
        self.assertNotIn(b"Object src/scrcmd_campaign.o", default["main.lsf"])

    def test_stock_bridge_is_refused_without_changing_default_preparation(self):
        with self.assertRaisesRegex(ValueError, "known opt-in R7 episode source profile; stock input is refused"):
            PREP.source_edits(ROOT, script_bridge=True)
        with tempfile.TemporaryDirectory(prefix="campaign-stock-refusal-") as tmp:
            base = Path(tmp)
            source = base / "stock"; source.mkdir()
            CAMP.private_source(source)
            for name in PREP.BRIDGE_PREIMAGES:
                CAMP.put(source, name, (ROOT / name).read_bytes())
            with self.assertRaisesRegex(ValueError, "stock input is refused"):
                PREP.prepare(source, base / "refused", script_bridge=True)
            self.assertFalse((base / "refused").exists())
            report = PREP.prepare(source, base / "format-only")
            self.assertEqual(len(report["changes"]), 5)
            self.assertNotIn("script_bridge", report)
            self.assertEqual((base / "format-only/src/data/fieldmap/script_cmd_table.h").read_bytes(),
                             (source / "src/data/fieldmap/script_cmd_table.h").read_bytes())

    def test_disposable_opt_in_manifest_preservation_and_negative_guards(self):
        with tempfile.TemporaryDirectory(prefix="campaign-bridge-source-") as tmp:
            base = Path(tmp); source = base / "source"; source.mkdir()
            episode_source(source)
            source_bytes = {p.relative_to(source).as_posix(): p.read_bytes()
                            for p in source.rglob("*") if p.is_file()}
            plain = base / "plain"; candidate = base / "bridge"
            plain_report = PREP.prepare(source, plain)
            self.assertEqual(len(plain_report["changes"]), 5)
            self.assertNotIn("script_bridge", plain_report)
            self.assertFalse((plain / "src/scrcmd_campaign.c").exists())
            report = PREP.prepare(source, candidate, script_bridge=True)
            self.assertEqual(len(report["changes"]), 11)
            self.assertEqual(report["script_bridge"]["native_command_count_after"], 859)
            self.assertEqual(report["script_bridge"]["native_command_count_before"], 855)
            self.assertEqual(report["script_bridge"]["command_metadata_count_before"], 854)
            self.assertEqual(report["script_bridge"]["command_metadata_count_after"], 859)
            self.assertEqual(report["script_bridge"]["input_profile"], PREP.BRIDGE_INPUT_PROFILE)
            self.assertEqual(report["script_bridge"]["actor_opcode_reconciliation"], {
                "opcode": 854, "name": "EnsureRoute101Actors", "args": [2],
                "metadata_added": True, "native_source_preserved": True,
            })
            self.assertEqual([item["opcode"] for item in report["script_bridge"]["commands"]], [855, 856, 857, 858])
            self.assertEqual(report["script_bridge"]["scratch_destination_range"], [0x8000, 0x800C])
            self.assertFalse(report["script_bridge"]["runtime_verified"])
            PREP.verify_candidate(candidate, source, script_bridge=True)
            for name, data in source_bytes.items():
                self.assertEqual((source / name).read_bytes(), data)
                if name not in report["changes"]:
                    self.assertEqual((candidate / name).read_bytes(), data)
            for name, old in (
                ("src/data/fieldmap/script_cmd_table.h", b"    ScrCmd_CampaignGetFlag,\n"),
                ("include/scrcmd.h", b"BOOL ScrCmd_CampaignGetFlag(ScriptContext *ctx);\n"),
                ("main.lsf", b"    Object src/scrcmd_campaign.o\n"),
                ("asm/macros/script.inc", b".short 855\n"),
                ("src/scrcmd_campaign.c", b"        StopScript(ctx);\n"),
            ):
                original = (candidate / name).read_bytes()
                (candidate / name).write_bytes(original.replace(old, b"", 1))
                with self.assertRaisesRegex(ValueError, "guard/registration/template mismatch"):
                    PREP.verify_candidate(candidate, source, script_bridge=True)
                (candidate / name).write_bytes(original)
            actor_table = source / "src/data/fieldmap/script_cmd_table.h"
            original_actor_table = actor_table.read_bytes()
            actor_table.write_bytes(original_actor_table.replace(b"    ScrCmd_EnsureRoute101Actors,\n", b""))
            with self.assertRaisesRegex(ValueError, "Script bridge safety preimage mismatch for known R7 episode profile"):
                PREP.prepare(source, base / "partial-profile", script_bridge=True)
            self.assertFalse((base / "partial-profile").exists())
            actor_table.write_bytes(original_actor_table)
            original = (source / "tools/py_scripts/scrcmd.json").read_bytes()
            (source / "tools/py_scripts/scrcmd.json").write_bytes(original + b"\n")
            with self.assertRaisesRegex(ValueError, "Script bridge safety preimage mismatch"):
                PREP.prepare(source, base / "rejected", script_bridge=True)
            self.assertFalse((base / "rejected").exists())

    @unittest.skipUnless(shutil.which("clang-format-19"), "repository clang-format 19 required")
    def test_new_templates_match_repository_clang_format_19(self):
        subprocess.run(["clang-format-19", "--dry-run", "--Werror",
                        str(PREP.TEMPLATES / "scrcmd_campaign.h"),
                        str(PREP.TEMPLATES / "scrcmd_campaign.c")], check=True, capture_output=True)


if __name__ == "__main__":
    unittest.main()