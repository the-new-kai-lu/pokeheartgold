"""Host-only campaign v1 checks; no ROMs, actual saves, or native tools.

Compile the actual opt-in template, native TrainerHouse code/structures, and
the actual prepared native layout/status/constructor functions with narrow
SDK/flash stubs. Earlier payload callbacks use the verified aggregate prefix,
not a claim that this host test measures every native compiler struct layout.
"""

import importlib.util
import json
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "campaign_preparer", ROOT / "scripts/prepare_campaign_save.py")
PREP = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PREP)


def function(source, name):
    match = re.search(r"^(?:static )?(?:const )?[\w *]+\b" + re.escape(name) + r"\([^;]*?\)\s*\{",
                      source, re.M)
    if not match:
        raise AssertionError(f"Missing actual native function: {name}")
    start = source.index("{", match.start())
    depth, end = 1, start + 1
    while depth:
        depth += (source[end] == "{") - (source[end] == "}")
        end += 1
    return source[match.start():end]


def put(root, name, data):
    target = root / name
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data if isinstance(data, bytes) else data.encode())


def private_source(root):
    for name in PREP.PREIMAGES:
        put(root, name, (ROOT / name).read_bytes())
    # Authentic unchanged asset/recipe inputs; not generated stand-ins.
    for name in (
        "files/data/mmodel/mmodel/mmodel_00000054.NSBTX",
        "files/fielddata/mapmatrix/map_matrix.mk", "heartgold.us/icon.png",
    ):
        put(root, name, (ROOT / name).read_bytes())


GLOBAL_STUB = r"""
#ifndef HOST_GLOBAL_H
#define HOST_GLOBAL_H
#include <assert.h>
#include <stdint.h>
#include <stddef.h>
#include <string.h>
#include "constants/global.h"
typedef uint8_t u8;
typedef uint16_t u16;
typedef uint32_t u32;
typedef int32_t s32;
typedef int BOOL;
#define TRUE 1
#define FALSE 0
#define GF_ASSERT assert
#define NELEMS(a) (sizeof(a) / sizeof((a)[0]))
#define MI_CpuClear8(p,n) memset((p),0,(n))
#define MI_CpuClearFast(p,n) memset((p),0,(n))
#endif
"""


HOST_SUPPORT = r"""
#include "save_campaign.h"
#include "save_trainer_house.h"
#include "save_arrays.h"
#include "math_util.h"
#include <stdlib.h>
#include <stdio.h>
#include <setjmp.h>

static SaveData *sSaveDataPtr;
static u8 partitions[2][CAMPAIGN_MAIN_BYTES];
static u8 snapshots[2][CAMPAIGN_MAIN_BYTES];
static BOOL readsOK[2];
static unsigned flashReads, flashWrites, frees, loadCalls, frontierCalls;
static unsigned overlayCalls, terminalWaits;
static jmp_buf terminalJump;

/* CCITT polynomial/init are from the actual Nitro header, not editor CRC rules. */
#include "nitro/math/crc.h"
static MATHCRC16Table *sCRC16TablePtr;
u16 MATH_CalcCRC16CCITT(const MATHCRC16Table *table, const void *input, u32 length) {
    const u8 *bytes = input;
    u32 i, bit;
    u16 crc = MATH_CRC16_CCITT_INIT;
    (void)table;
    for (i = 0; i < length; i++) {
        crc ^= (u16)(bytes[i] << 8);
        for (bit = 0; bit < 8; bit++)
            crc = (u16)((crc << 1) ^ ((crc & 0x8000) ? MATH_CRC16_CCITT_POLY : 0));
    }
    return crc;
}

void StringFillEOS(u16 *s, u32 n) { while (n--) *s++ = 0xFFFF; }
BOOL StringNotEqual(const u16 *a, const u16 *b) {
    while (*a == *b && *a != 0xFFFF) { a++; b++; }
    return *a != *b;
}

static void *Heap_Alloc(enum HeapID id, u32 n) {
    void *p = malloc(n); (void)id; assert(p); memset(p, 0xA5, n); return p;
}
static void *Heap_AllocAtEnd(enum HeapID id, u32 n) { return Heap_Alloc(id, n); }
static void Heap_Free(void *p) { frees++; free(p); }
static BOOL SaveDetectFlash(void) { return TRUE; }
static BOOL FlashLoadChunk(u32 offset, void *dest, u32 size) {
    u32 partition = offset / 0x40000;
    u32 local = offset % 0x40000;
    assert(partition < 2 && local + size <= CAMPAIGN_MAIN_BYTES);
    flashReads++;
    if (!readsOK[partition]) {
        /* The unsuccessful read buffer must NEVER be classified. */
        memset(dest, 0xCC, size);
        if (size == CAMPAIGN_MAIN_BYTES) {
            CampaignSave *state = (CampaignSave *)((u8 *)dest + CAMPAIGN_EXTENSION_OFFSET);
            CampaignSave_Init(state); state->version[0] = 99;
        }
        return FALSE;
    }
    memcpy(dest, partitions[partition] + local, size);
    return TRUE;
}
static int FlashClobberChunkFooter(SaveData *s, int a, int b) {
    (void)s; (void)a; (void)b; flashWrites++; return 0;
}
static int _NowWriteFlash(SaveData *s) { (void)s; flashWrites++; return WRITE_STATUS_SUCCESS; }
static void Sys_SetSleepDisableFlag(int n) { (void)n; }
static void Sys_ClearSleepDisableFlag(int n) { (void)n; }
static int Save_GetPCBoxModifiedFlags(SaveData *s) { (void)s; return 0; }
static void Save_CheckFrontierData(SaveData *s, int *a, int *b) {
    (void)s; frontierCalls++; *a = *b = 1;
}
static BOOL Save_LoadDynamicRegion(SaveData *s) {
    loadCalls++;
    memcpy(s->dynamic_region, partitions[s->lastGoodSector], CAMPAIGN_MAIN_BYTES);
    return TRUE;
}
static void SaveFooterDebugPrn(struct SaveChunkFooter *footer) { (void)footer; }
static void DebugPrn_MirrorValid(BOOL value) { (void)value; }

/* Main's actual startup gate is compiled below. The read-error UI's unchanged
 * terminal loop is executed, with the IRQ stub longjmp-ing after three waits. */
static struct { struct { SaveData *saveData; int unk_04; } unk_10; } _02111868;
#define PM_LCD_TOP 0
#define PM_LCD_BOTTOM 1
#define RGB_BLACK 0
#define FS_OVERLAY_ID(n) 0
#define OS_IE_VBLANK 1
static int gApplication_IntroMovie, ov36_App_MainMenu_SelectOption_Continue;
static int OS_GetResetParameter(void) { return 0; }
static void RegisterMainOverlay(int id, void *app) { (void)id; (void)app; overlayCalls++; }
static void sub_0200FBF4(int screen, int color) { (void)screen; (void)color; }
static void HandleDSLidAction(void) {}
static void OS_WaitIrq(BOOL clear, int mask) {
    (void)clear; (void)mask;
    if (++terminalWaits == 3) longjmp(terminalJump, 1);
}
"""


HOST_TESTS = r"""
static void write16(u8 *p, u16 v) { p[0] = (u8)v; p[1] = (u8)(v >> 8); }
static void write32(u8 *p, u32 v) {
    p[0] = (u8)v; p[1] = (u8)(v >> 8); p[2] = (u8)(v >> 16); p[3] = (u8)(v >> 24);
}
static CampaignSave *stateAt(u8 *p) { return (CampaignSave *)(p + CAMPAIGN_EXTENSION_OFFSET); }
static void footer(u8 *data, u32 offset, u32 size, u16 slot, u32 count) {
    u8 *f = data + offset + size - sizeof(struct SaveChunkFooter);
    write32(f, count); write32(f + 4, size); write32(f + 8, SAVE_CHUNK_MAGIC);
    write16(f + 12, slot); write16(f + 14, GF_CalcCRC16(data + offset, size - 16));
}
static void expanded(u8 *data, u32 count) {
    memset(data, 0, CAMPAIGN_MAIN_BYTES);
    CampaignSave_Init(stateAt(data));
    footer(data, 0, CAMPAIGN_GENERAL_BYTES, 0, count);
    footer(data, 0xFF00, 0x12310, 1, count);
}
static void legacy(u8 *data, u32 count) {
    memset(data, 0, CAMPAIGN_MAIN_BYTES);
    data[100] = 73;
    footer(data, 0, CAMPAIGN_LEGACY_GENERAL_BYTES, 0, count);
    footer(data, 0xF700, 0x12310, 1, count);
}
static void resetFlash(void) {
    memset(partitions, 0xFF, sizeof(partitions));
    readsOK[0] = readsOK[1] = TRUE;
    flashReads = flashWrites = frees = loadCalls = frontierCalls = 0;
    overlayCalls = terminalWaits = 0;
}
static void assertNoMutation(void) {
    assert(!memcmp(partitions, snapshots, sizeof(partitions)));
    assert(flashWrites == 0);
}
static void initializeLayout(SaveData *s) {
    memset(s, 0, sizeof(*s));
    SaveData_InitSubstructs(s->arrayHeaders);
    SaveData_InitSlotSpecs(s->saveSlotSpecs, s->arrayHeaders);
}

static void test_contract(void) {
    CampaignSave s;
    const u8 *bytes = (const u8 *)&s;
    u32 i;
    assert(sizeof(CampaignSave) == 2048);
    assert(offsetof(CampaignSave, version) == 8 && offsetof(CampaignSave, length) == 10);
    assert(offsetof(CampaignSave, headerSize) == 12 && offsetof(CampaignSave, opaqueHeader) == 14);
    assert(offsetof(CampaignSave, hoennVars) == 32 && offsetof(CampaignSave, hoennFlags) == 544);
    assert(offsetof(CampaignSave, sinnohVars) == 844 && offsetof(CampaignSave, sinnohFlags) == 1420);
    assert(offsetof(CampaignSave, reserved) == 1784);
    assert(sizeof(SaveData) == 0x2330C);
    assert(SAVE_CHUNK_MAGIC == 0x20060623);
    memset(&s, 0xA5, sizeof(s));
    assert(!CampaignSave_HeaderSupported(&s));
    CampaignSave_Init(&s);
    assert(!memcmp(s.magic, "EHGSCAMP", 8));
    assert(bytes[8] == 1 && bytes[9] == 0 && bytes[10] == 0 && bytes[11] == 8);
    assert(bytes[12] == 32 && bytes[13] == 0);
    for (i = 14; i < sizeof(s); i++) assert(bytes[i] == 0);
    assert(CampaignSave_HeaderSupported(&s));
    assert(GF_CalcCRC16("123456789", 9) == 0x29B1);
}

static void test_ranges(void) {
    CampaignSave s, copy;
    u32 region, id, i;
    u16 value;
    BOOL flag;
    CampaignSave_Init(&s);
    for (i = 0; i < sizeof(s.opaqueHeader); i++) s.opaqueHeader[i] = (u8)(i + 1);
    for (i = 0; i < sizeof(s.reserved); i++) s.reserved[i] = (u8)(i * 17 + 1);
    /* Bit zero is opaque on load; sentinel access must not normalize it. */
    s.hoennFlags[0] = s.sinnohFlags[0] = 1;
    for (region = 0; region < 2; region++) {
        u32 varCount = region == 0 ? 256 : 288;
        u32 flagCount = region == 0 ? 2400 : 2912;
        for (id = 0; id < varCount; id++) {
            assert(CampaignSave_SetVar(&s, region, id + 0x4000, (u16)(id + 0xA100 + region)));
            assert(CampaignSave_GetVar(&s, region, id + 0x4000, &value));
            assert(value == (u16)(id + 0xA100 + region));
        }
        for (id = 1; id < flagCount; id++) {
            assert(CampaignSave_SetFlag(&s, region, id, TRUE));
            assert(CampaignSave_GetFlag(&s, region, id, &flag) && flag);
            assert(CampaignSave_SetFlag(&s, region, id, FALSE));
            assert(CampaignSave_GetFlag(&s, region, id, &flag) && !flag);
        }
        copy = s;
        assert(CampaignSave_SetFlag(&s, region, 0, TRUE));
        assert(CampaignSave_SetFlag(&s, region, 0, FALSE));
        assert(CampaignSave_GetFlag(&s, region, 0, &flag) && !flag);
        assert(!memcmp(&s, &copy, sizeof(s)));
        for (id = 0; id < 0x10000; id++) {
            if (id < 0x4000 || id >= 0x4000 + varCount) {
                value = 0x7777;
                assert(!CampaignSave_SetVar(&s, region, id, 99));
                assert(!CampaignSave_GetVar(&s, region, id, &value) && value == 0x7777);
            }
            if (id >= flagCount) {
                flag = 73;
                assert(!CampaignSave_SetFlag(&s, region, id, TRUE));
                assert(!CampaignSave_GetFlag(&s, region, id, &flag) && flag == 73);
            }
        }
        assert(!CampaignSave_SetVar(&s, region, UINT32_MAX, 7));
        assert(!CampaignSave_SetFlag(&s, region, UINT32_MAX, TRUE));
        assert(!memcmp(&s, &copy, sizeof(s)));
    }
    assert(CampaignSave_GetVar(&s, CAMPAIGN_HOENN, 0x4000, &value) && value == 0xA100);
    assert(CampaignSave_GetVar(&s, CAMPAIGN_SINNOH, 0x4000, &value) && value == 0xA101);
    assert(s.hoennVars[0] == 0 && s.hoennVars[1] == 0xA1);
    assert(s.hoennVars[510] == 0xFF && s.hoennVars[511] == 0xA1);
    assert(s.sinnohVars[0] == 1 && s.sinnohVars[1] == 0xA1);
    assert(s.sinnohVars[574] == 0x20 && s.sinnohVars[575] == 0xA2);
    assert(CampaignSave_SetFlag(&s, CAMPAIGN_HOENN, 2399, TRUE));
    assert(s.hoennFlags[299] == 0x80);
    assert(CampaignSave_GetFlag(&s, CAMPAIGN_SINNOH, 2399, &flag) && !flag);
    assert(CampaignSave_SetFlag(&s, CAMPAIGN_SINNOH, 2911, TRUE));
    assert(s.sinnohFlags[363] == 0x80);
    for (i = 0; i < sizeof(s.opaqueHeader); i++) assert(s.opaqueHeader[i] == (u8)(i + 1));
    for (i = 0; i < sizeof(s.reserved); i++) assert(s.reserved[i] == (u8)(i * 17 + 1));
    copy = s;
    assert(!CampaignSave_GetVar(&s, 0, 0x4000, NULL));
    assert(!CampaignSave_GetFlag(&s, 0, 1, NULL));
    assert(!CampaignSave_SetVar(&s, 2, 0x4000, 7));
    assert(!CampaignSave_SetFlag(&s, 2, 1, TRUE));
    assert(!CampaignSave_SetVar(&s, UINT32_MAX, 0x4000, 7));
    assert(!CampaignSave_SetFlag(&s, UINT32_MAX, 1, TRUE));
    value = 0x7777; flag = 73;
    assert(!CampaignSave_GetVar(&s, 2, 0x4000, &value) && value == 0x7777);
    assert(!CampaignSave_GetFlag(&s, 2, 1, &flag) && flag == 73);
    assert(!CampaignSave_GetVar(&s, UINT32_MAX, 0x4000, &value) && value == 0x7777);
    assert(!CampaignSave_GetFlag(&s, UINT32_MAX, 1, &flag) && flag == 73);
    assert(!CampaignSave_GetVar(&s, 0, UINT32_MAX, &value) && value == 0x7777);
    assert(!CampaignSave_GetFlag(&s, 0, UINT32_MAX, &flag) && flag == 73);
    assert(!memcmp(&s, &copy, sizeof(s)));
}

static void test_invalid_headers(void) {
    CampaignSave s, copy;
    u32 index;
    u16 value = 0x7777;
    BOOL flag = 73;
    assert(!CampaignSave_HeaderSupported(NULL));
    assert(!CampaignSave_GetVar(NULL, 0, 0x4000, &value));
    assert(!CampaignSave_SetVar(NULL, 0, 0x4000, 1));
    assert(!CampaignSave_GetFlag(NULL, 0, 1, &flag));
    assert(!CampaignSave_SetFlag(NULL, 0, 1, TRUE));
    CampaignSave_Init(NULL);
    for (index = 0; index < 14; index++) {
        CampaignSave_Init(&s);
        ((u8 *)&s)[index] ^= 0x80;
        copy = s;
        assert(!CampaignSave_HeaderSupported(&s));
        assert(!CampaignSave_GetVar(&s, 0, 0x4000, &value) && value == 0x7777);
        assert(!CampaignSave_SetVar(&s, 1, 0x411F, 1));
        assert(!CampaignSave_GetFlag(&s, 0, 0, &flag) && flag == 73);
        assert(!CampaignSave_SetFlag(&s, 1, 2911, TRUE));
        assert(!memcmp(&s, &copy, sizeof(s)));
    }
}

static void test_wrappers_getter(void) {
    SaveData s, copy;
    TrainerHouse original;
    u8 allocation[0x1704];
    u32 prefix = Save_TrainerHouse_sizeof();
    assert(prefix == 0xF00);
    assert(Save_TrainerHouseCampaign_sizeof() == 0x1700);
    memset(allocation, 0xA5, sizeof(allocation));
    Save_TrainerHouse_Init(&original);
    Save_TrainerHouseCampaign_Init(allocation);
    assert(!memcmp(allocation, &original, sizeof(original)));
    assert(CampaignSave_HeaderSupported((CampaignSave *)(allocation + prefix)));
    assert(allocation[0x1700] == 0xA5 && allocation[0x1703] == 0xA5);
    initializeLayout(&s);
    s.arrayHeaders[40].size = prefix + 4;  /* default tree must not read extension */
    memset(s.dynamic_region, 0xCC, sizeof(s.dynamic_region));
    copy = s;
    assert(Save_Campaign_Get(&s) == NULL && !memcmp(&s, &copy, sizeof(s)));
    initializeLayout(&s);
    CampaignSave_Init(stateAt(s.dynamic_region));
    s.dynamic_region[0xE714 + 27] = 0x6D; /* loaded original TrainerHouse byte */
    copy = s;
    assert(Save_Campaign_Get(&s) == stateAt(s.dynamic_region));
    assert(Save_Campaign_Const_Get(&s) == stateAt(s.dynamic_region));
    assert(!memcmp(&s, &copy, sizeof(s)));
    assert(CampaignSave_SetVar(Save_Campaign_Get(&s), 0, 0x4000, 0x1234));
    assert(!memcmp(s.dynamic_region + 0xE714, copy.dynamic_region + 0xE714, prefix));
    s.arrayHeaders[40].size++; copy = s;
    assert(!Save_Campaign_Get(&s) && !memcmp(&s, &copy, sizeof(s)));
    s.arrayHeaders[40].size--; s.arrayHeaders[40].offset = UINT32_MAX; copy = s;
    assert(!Save_Campaign_Get(&s) && !memcmp(&s, &copy, sizeof(s)));
    initializeLayout(&s); s.arrayHeaders[40].slot = 1; assert(!Save_Campaign_Get(&s));
    initializeLayout(&s); s.arrayHeaders[40].id = 39; assert(!Save_Campaign_Get(&s));
    initializeLayout(&s); CampaignSave_Init(stateAt(s.dynamic_region));
    stateAt(s.dynamic_region)->version[0] = 2; copy = s;
    assert(!Save_Campaign_Get(&s) && !memcmp(&s, &copy, sizeof(s)));
    assert(!Save_Campaign_Get(NULL));
}

static void test_layout(void) {
    SaveData s;
    struct SaveArrayHeader legacyHeaders[43];
    struct SaveSlotSpec legacySlots[2];
    u32 i;
    assert(SAVE_BLOCK_NUM == 42 && gNumSaveChunkHeaders == 42);
    assert(SAVE_PAGE_MAX == 35 && SAVE_SECTOR_SIZE == 0x1000);
    initializeLayout(&s);
    assert(s.arrayHeaders[40].id == 40 && s.arrayHeaders[41].id == 41);
    assert(s.arrayHeaders[40].offset + Save_TrainerHouse_sizeof() == 0xF614);
    assert(s.arrayHeaders[40].size == 0x1704);
    assert(s.saveSlotSpecs[0].offset == 0 && s.saveSlotSpecs[0].size == 0xFE28);
    assert(s.saveSlotSpecs[1].offset == 0xFF00 && s.saveSlotSpecs[1].size == 0x12310);
    assert(s.saveSlotSpecs[0].numPages == 16 && s.saveSlotSpecs[1].numPages == 19);
    assert(s.saveSlotSpecs[1].firstPage == 16);
    assert(s.saveSlotSpecs[1].offset + s.saveSlotSpecs[1].size == 0x22210);
    assert(0x22210 <= sizeof(s.dynamic_region));
    legacyLayout = TRUE;
    memset(legacyHeaders, 0, sizeof(legacyHeaders));
    SaveData_InitSubstructs(legacyHeaders);
    SaveData_InitSlotSpecs(legacySlots, legacyHeaders);
    legacyLayout = FALSE;
    assert(legacySlots[0].size == 0xF628 && legacySlots[1].offset == 0xF700);
    assert(legacySlots[1].size == s.saveSlotSpecs[1].size);
    for (i = 0; i <= 40; i++) {
        assert(legacyHeaders[i].offset == s.arrayHeaders[i].offset);
        if (i < 40) assert(legacyHeaders[i].size == s.arrayHeaders[i].size);
    }
    assert(s.arrayHeaders[41].offset - legacyHeaders[41].offset == 2048);
}

static void test_classification(void) {
    SaveData s;
    u32 i;
    initializeLayout(&s); resetFlash();
    memcpy(snapshots, partitions, sizeof(partitions));
    assert(CampaignSave_ClassifyPartition(partitions[0], CAMPAIGN_MAIN_BYTES) == CAMPAIGN_PARTITION_BLANK);
    assertNoMutation();
    memset(partitions[0], 0, CAMPAIGN_MAIN_BYTES);
    assert(CampaignSave_ClassifyPartition(partitions[0], CAMPAIGN_MAIN_BYTES) == CAMPAIGN_PARTITION_BLANK);
    legacy(partitions[0], 17);
    assert(CampaignSave_ClassifyPartition(partitions[0], CAMPAIGN_MAIN_BYTES) == CAMPAIGN_PARTITION_LEGACY);
    expanded(partitions[0], 18);
    assert(CampaignSave_ClassifyPartition(partitions[0], CAMPAIGN_MAIN_BYTES) == CAMPAIGN_PARTITION_SUPPORTED);
    assert(ValidateSaveSectorFooter(&s, partitions[0], 0));
    assert(ValidateSaveSectorFooter(&s, partitions[0], 1));
    for (i = 14; i < 32; i++) ((u8 *)stateAt(partitions[0]))[i] = (u8)i;
    stateAt(partitions[0])->reserved[263] = 77;
    footer(partitions[0], 0, CAMPAIGN_GENERAL_BYTES, 0, 18);
    memcpy(snapshots, partitions, sizeof(partitions));
    assert(CampaignSave_ClassifyPartition(partitions[0], CAMPAIGN_MAIN_BYTES) == CAMPAIGN_PARTITION_SUPPORTED);
    assertNoMutation();
    partitions[0][100] ^= 1;
    assert(CampaignSave_ClassifyPartition(partitions[0], CAMPAIGN_MAIN_BYTES) == CAMPAIGN_PARTITION_CORRUPT);
    assert(!ValidateSaveSectorFooter(&s, partitions[0], 0));
    stateAt(partitions[0])->version[0] = 2;
    assert(CampaignSave_ClassifyPartition(partitions[0], CAMPAIGN_MAIN_BYTES) == CAMPAIGN_PARTITION_UNSUPPORTED);
    expanded(partitions[0], 18);
    stateAt(partitions[0])->magic[0] = 'X';
    footer(partitions[0], 0, CAMPAIGN_GENERAL_BYTES, 0, 18);
    assert(CampaignSave_ClassifyPartition(partitions[0], CAMPAIGN_MAIN_BYTES) == CAMPAIGN_PARTITION_UNSUPPORTED);
    assert(!ValidateSaveSectorFooter(&s, partitions[0], 0)); /* CRC-valid footer is not enough */
    assert(CampaignSave_ClassifyPartition(NULL, CAMPAIGN_MAIN_BYTES) == CAMPAIGN_PARTITION_UNSUPPORTED);
    assert(CampaignSave_ClassifyPartition(partitions[0], CAMPAIGN_MAIN_BYTES - 1) == CAMPAIGN_PARTITION_UNSUPPORTED);
    assert(CampaignSave_ClassifyPartition(partitions[0], UINT32_MAX) == CAMPAIGN_PARTITION_UNSUPPORTED);
}

static void test_footer_semantics(void) {
    SaveData s;
    u32 field;
    initializeLayout(&s); resetFlash(); expanded(partitions[0], 9);
    for (field = 4; field < 16; field++) {
        expanded(partitions[0], 9);
        partitions[0][CAMPAIGN_GENERAL_BYTES - 16 + field] ^= 1;
        assert(!ValidateSaveSectorFooter(&s, partitions[0], 0));
        assert(CampaignSave_ClassifyPartition(partitions[0], CAMPAIGN_MAIN_BYTES) == CAMPAIGN_PARTITION_CORRUPT);
    }
    expanded(partitions[0], 9);
    partitions[0][CAMPAIGN_GENERAL_BYTES - 16] ^= 1; /* count is outside CRC, native semantics */
    assert(ValidateSaveSectorFooter(&s, partitions[0], 0));
    assert(CampaignSave_ClassifyPartition(partitions[0], CAMPAIGN_MAIN_BYTES) == CAMPAIGN_PARTITION_SUPPORTED);
    expanded(partitions[0], 9);
    stateAt(partitions[0])->reserved[0] ^= 1; /* reserved bytes ARE protected */
    assert(!ValidateSaveSectorFooter(&s, partitions[0], 0));
}

static void test_native_status(void) {
    SaveData s;
    initializeLayout(&s); resetFlash();
    assert(Save_GetSaveFilesStatus(&s) == LOAD_STATUS_NOT_EXIST);
    assert(flashReads == 2 && frees == 2);
    resetFlash(); legacy(partitions[1], 7);
    memcpy(snapshots, partitions, sizeof(partitions));
    assert(Save_GetSaveFilesStatus(&s) == LOAD_STATUS_UNSUPPORTED_CAMPAIGN);
    assert(frees == 2); assertNoMutation();
    resetFlash(); expanded(partitions[0], 8); expanded(partitions[1], 7);
    memcpy(snapshots, partitions, sizeof(partitions));
    assert(Save_GetSaveFilesStatus(&s) == LOAD_STATUS_IS_GOOD && s.lastGoodSector == 0);
    assertNoMutation();
    /* Same-format CRC/backup recovery still selects the older supported slot. */
    partitions[0][100] ^= 1;
    memcpy(snapshots, partitions, sizeof(partitions));
    assert(Save_GetSaveFilesStatus(&s) == LOAD_STATUS_SLOT_FAIL && s.lastGoodSector == 1);
    assertNoMutation();
    /* Count mismatch recovery is the actual native selection code, not a replacement. */
    resetFlash(); expanded(partitions[0], 8); expanded(partitions[1], 7);
    footer(partitions[0], 0xFF00, 0x12310, 1, 6);
    assert(Save_GetSaveFilesStatus(&s) == LOAD_STATUS_SLOT_FAIL && s.lastGoodSector == 1);
    /* Unsupported younger or older tags cannot downgrade to a good backup,
     * even when their CRC is corrupt. Nor may legacy mix with expanded data. */
    resetFlash(); expanded(partitions[0], 8); expanded(partitions[1], 7);
    stateAt(partitions[0])->version[0] = 2;
    memcpy(snapshots, partitions, sizeof(partitions));
    assert(Save_GetSaveFilesStatus(&s) == 4); assertNoMutation();
    resetFlash(); expanded(partitions[0], 8); expanded(partitions[1], 7);
    stateAt(partitions[1])->version[0] = 2;
    footer(partitions[1], 0, CAMPAIGN_GENERAL_BYTES, 0, 7);
    assert(Save_GetSaveFilesStatus(&s) == 4);
    legacy(partitions[1], 7);
    assert(Save_GetSaveFilesStatus(&s) == 4);
    /* Malformed tagged length/header size also fail closed. */
    resetFlash(); expanded(partitions[0], 8);
    stateAt(partitions[0])->length[0] = 1;
    assert(Save_GetSaveFilesStatus(&s) == 4);
    expanded(partitions[0], 8); stateAt(partitions[0])->headerSize[0] = 31;
    assert(Save_GetSaveFilesStatus(&s) == 4);
}

static void test_failed_reads(void) {
    SaveData s;
    initializeLayout(&s); resetFlash();
    legacy(partitions[0], 9); readsOK[0] = FALSE;
    assert(Save_GetSaveFilesStatus(&s) == LOAD_STATUS_TOTAL_FAIL); /* unread legacy ignored, not proven blank */
    assert(frees == 2 && flashReads == 2);
    expanded(partitions[1], 7);
    assert(Save_GetSaveFilesStatus(&s) == LOAD_STATUS_IS_GOOD && s.lastGoodSector == 1);
    readsOK[1] = FALSE;
    assert(Save_GetSaveFilesStatus(&s) == LOAD_STATUS_TOTAL_FAIL);
}

static void assertClosedConstructor(void) {
    SaveData *s;
    unsigned previousFrees = frees;
    memcpy(snapshots, partitions, sizeof(partitions));
    s = SaveData_New();
    assert(!s->flashChipDetected && s->isNewGame && !s->saveFileExists);
    assert(s->statusFlags & 2);
    assert(loadCalls == 0 && frontierCalls == 0 && frees == previousFrees + 2);
    assert(Save_Campaign_Get(s)); /* safe RAM only; no migration or disk repair */
    assert(SaveGameNormal(s) == WRITE_STATUS_TOTAL_FAIL);
    assertNoMutation();
    _02111868.unk_10.saveData = s;
    if (!setjmp(terminalJump)) nativeStartupGate();
    assert(terminalWaits == 3 && overlayCalls == 0);
    assertNoMutation();
    Heap_Free(s);
}

static void test_blank_proof(void) {
    SaveData state;
    volatile u32 mode;
    for (mode = 0; mode < 7; mode++) {
        initializeLayout(&state); resetFlash();
        if (mode == 1) memset(partitions, 0, sizeof(partitions));
        if (mode == 2) memset(partitions[0], 0, CAMPAIGN_MAIN_BYTES);
        if (mode == 3) {
            legacy(partitions[0], 9);
            readsOK[0] = FALSE;
        }
        if (mode == 4) {
            expanded(partitions[0], 9); expanded(partitions[1], 8);
            readsOK[0] = readsOK[1] = FALSE;
        }
        if (mode == 5) readsOK[1] = FALSE;
        if (mode == 6) readsOK[0] = readsOK[1] = FALSE;
        memcpy(snapshots, partitions, sizeof(partitions));
        assert(Save_GetSaveFilesStatus(&state) ==
               (mode < 3 ? LOAD_STATUS_NOT_EXIST : LOAD_STATUS_TOTAL_FAIL));
        assertNoMutation();
        if (mode < 3) {
            SaveData *s = SaveData_New();
            assert(s->flashChipDetected && s->isNewGame && !s->saveFileExists);
            assert(s->statusFlags == 0 && Save_Campaign_Get(s));
            assert(loadCalls == 0 && frontierCalls == 0);
            assertNoMutation();
            Heap_Free(s);
        } else {
            assertClosedConstructor();
        }
    }
}

static void test_nonblank_no_pair_failclosed(void) {
    SaveData s;
    volatile u32 mode;
    for (mode = 0; mode < 4; mode++) {
        initializeLayout(&s); resetFlash();
        if (mode == 0) {
            /* Both complete v1 banks exist, but both general AND storage CRCs fail. */
            expanded(partitions[0], 9); expanded(partitions[1], 8);
            partitions[0][100] ^= 1; partitions[0][0xFF00 + 100] ^= 1;
            partitions[1][100] ^= 1; partitions[1][0xFF00 + 100] ^= 1;
        } else if (mode == 1) {
            /* One nonblank v1 bank with both CRCs broken, other bank genuinely blank. */
            expanded(partitions[0], 9);
            partitions[0][100] ^= 1; partitions[0][0xFF00 + 100] ^= 1;
        } else if (mode == 2) {
            /* Unrecognized nonblank data must not be mistaken for an empty chip. */
            partitions[0][123] = 0x37;
        } else {
            /* No alternate footer magic is supported by this native contract. */
            expanded(partitions[0], 9);
            write32(partitions[0] + CAMPAIGN_GENERAL_BYTES - 16 + 8, SAVE_CHUNK_MAGIC + 1);
            write32(partitions[0] + 0xFF00 + 0x12310 - 16 + 8, SAVE_CHUNK_MAGIC + 1);
        }
        assert(CampaignSave_ClassifyPartition(partitions[0], CAMPAIGN_MAIN_BYTES)
               == CAMPAIGN_PARTITION_CORRUPT);
        memcpy(snapshots, partitions, sizeof(partitions));
        assert(Save_GetSaveFilesStatus(&s) == LOAD_STATUS_TOTAL_FAIL);
        assertNoMutation();
        assertClosedConstructor();
    }
}

static void test_total_fail_constructor(void) {
    SaveData s;
    volatile u32 mode;
    for (mode = 0; mode < 7; mode++) {
        initializeLayout(&s); resetFlash();
        expanded(partitions[0], 9);
        if (mode == 0) {
            /* Supported general bank, but no usable storage bank. */
            partitions[0][0xFF00 + 100] ^= 1;
        } else if (mode == 1) {
            /* Supported storage bank, but no usable general bank. */
            partitions[0][100] ^= 1;
        } else if (mode == 2) {
            /* Both sets validate individually; neither complete pair shares a counter. */
            expanded(partitions[1], 8);
            footer(partitions[0], 0xFF00, 0x12310, 1, 7);
            footer(partitions[1], 0xFF00, 0x12310, 1, 6);
        } else if (mode == 3) {
            /* One pair with a counter mismatch must fail even without GF_ASSERT. */
            footer(partitions[0], 0xFF00, 0x12310, 1, 8);
        } else if (mode == 4) {
            /* Individually good general/storage chunks in different banks are no pair. */
            expanded(partitions[1], 8);
            partitions[0][0xFF00 + 100] ^= 1;
            partitions[1][100] ^= 1;
        } else if (mode == 5) {
            /* Even equal counters may not join chunks from different banks. */
            expanded(partitions[0], 0); expanded(partitions[1], 0);
            partitions[0][0xFF00 + 100] ^= 1;
            partitions[1][100] ^= 1;
        } else {
            /* Counter rollover orders pairs; it never makes unequal counters a pair. */
            expanded(partitions[0], 0); expanded(partitions[1], UINT32_MAX);
            footer(partitions[0], 0xFF00, 0x12310, 1, UINT32_MAX);
            footer(partitions[1], 0xFF00, 0x12310, 1, 0);
        }
        memcpy(snapshots, partitions, sizeof(partitions));
        assert(Save_GetSaveFilesStatus(&s) == LOAD_STATUS_TOTAL_FAIL);
        assertNoMutation();
        assertClosedConstructor();
    }
}

static void test_good_backup_after_corrupt_or_unread(void) {
    SaveData state;
    SaveData *s;
    u32 mode;
    for (mode = 0; mode < 3; mode++) {
        initializeLayout(&state); resetFlash();
        expanded(partitions[0], 9); expanded(partitions[1], 8);
        partitions[0][100] ^= 1;
        if (mode == 1) partitions[0][0xFF00 + 100] ^= 1;
        if (mode == 2) readsOK[0] = FALSE;
        memcpy(snapshots, partitions, sizeof(partitions));
        assert(Save_GetSaveFilesStatus(&state) ==
               (mode == 0 ? LOAD_STATUS_SLOT_FAIL : LOAD_STATUS_IS_GOOD));
        assert(state.lastGoodSector == 1);
        s = SaveData_New();
        assert(s->flashChipDetected && !s->isNewGame && s->saveFileExists);
        assert(s->lastGoodSector == 1 && loadCalls == 1 && frontierCalls == 1);
        assert((s->statusFlags & 2) == 0 && overlayCalls == 0);
        assert(Save_Campaign_Get(s));
        assertNoMutation();
        Heap_Free(s);
    }
}

static void test_rollover_incomplete_newer_transaction(void) {
    SaveData state;
    SaveData *s;
    int status;
    initializeLayout(&state); resetFlash();
    expanded(partitions[0], 0);
    expanded(partitions[1], UINT32_MAX);
    partitions[0][0xFF00 + 100] ^= 1;
    /* Failed storage validation substitutes dummy counter zero, equal to the
     * rolled-over newer general counter. Equality alone must never select it. */
    assert(ValidateSaveSectorFooter(&state, partitions[0], 0));
    assert(!ValidateSaveSectorFooter(&state, partitions[0], 1));
    memcpy(snapshots, partitions, sizeof(partitions));
    status = Save_GetSaveFilesStatus(&state);
    if (status != LOAD_STATUS_SLOT_FAIL || state.lastGoodSector != 1)
        fprintf(stderr, "incomplete rollover: status=%d bank=%u counter=%08x\n",
                status, state.lastGoodSector, state.saveCounter);
    assert(status == LOAD_STATUS_SLOT_FAIL && state.lastGoodSector == 1);
    assert(state.saveCounter == UINT32_MAX);
    assertNoMutation();
    s = SaveData_New();
    assert(s->flashChipDetected && !s->isNewGame && s->saveFileExists);
    assert(s->lastGoodSector == 1 && s->saveCounter == UINT32_MAX);
    assert(loadCalls == 1 && frontierCalls == 1 && s->statusFlags == 1);
    assert(!memcmp(s->dynamic_region, partitions[1], CAMPAIGN_MAIN_BYTES));
    assertNoMutation();
    Heap_Free(s);
}

static int expectedCounterCompare(u32 first, u32 second) {
    if (first == UINT32_MAX && second == 0) return -1;
    if (first == 0 && second == UINT32_MAX) return 1;
    return (first > second) - (first < second);
}

static void test_native_counter_transaction_selection(void) {
    const u32 counters[] = {0, 1, 0x7FFFFFFF, 0x80000000, UINT32_MAX - 1, UINT32_MAX};
    SaveData state;
    SaveData *s;
    u32 first, second;
    for (first = 0; first < NELEMS(counters); first++) {
        for (second = 0; second < NELEMS(counters); second++) {
            int comparison = expectedCounterCompare(counters[first], counters[second]);
            u32 selected = comparison >= 0 ? 0 : 1;
            assert(SaveCounterCompare(counters[first], counters[second]) == comparison);
            initializeLayout(&state); resetFlash();
            expanded(partitions[0], counters[first]);
            expanded(partitions[1], counters[second]);
            partitions[0][100] = 0x11; partitions[1][100] = 0x22;
            partitions[0][0xFF00 + 100] = 0x33; partitions[1][0xFF00 + 100] = 0x44;
            footer(partitions[0], 0, CAMPAIGN_GENERAL_BYTES, 0, counters[first]);
            footer(partitions[1], 0, CAMPAIGN_GENERAL_BYTES, 0, counters[second]);
            footer(partitions[0], 0xFF00, 0x12310, 1, counters[first]);
            footer(partitions[1], 0xFF00, 0x12310, 1, counters[second]);
            memcpy(snapshots, partitions, sizeof(partitions));
            assert(Save_GetSaveFilesStatus(&state) == LOAD_STATUS_IS_GOOD);
            assert(state.lastGoodSector == selected);
            assert(state.saveCounter == (selected == 0 ? counters[first] : counters[second]));
            s = SaveData_New();
            assert(s->flashChipDetected && !s->isNewGame && s->saveFileExists);
            assert(s->lastGoodSector == selected && s->saveCounter == state.saveCounter);
            assert(loadCalls == 1 && frontierCalls == 1 && s->statusFlags == 0);
            assert(!memcmp(s->dynamic_region, partitions[selected], CAMPAIGN_MAIN_BYTES));
            assertNoMutation();
            Heap_Free(s);
        }
    }
}

static void test_incomplete_newer_transaction_counter_boundaries(void) {
    const u32 pairs[][2] = {
        {UINT32_MAX, UINT32_MAX - 1},
        {0, UINT32_MAX},
        {UINT32_MAX - 1, 0},
        {0x80000000, 0x7FFFFFFF}
    };
    SaveData state;
    SaveData *s;
    u32 pair, incomplete, side;
    for (pair = 0; pair < NELEMS(pairs); pair++) {
        assert(SaveCounterCompare(pairs[pair][0], pairs[pair][1]) > 0);
        for (incomplete = 0; incomplete < 2; incomplete++) {
            u32 complete = 1 - incomplete;
            for (side = 0; side < 2; side++) {
                initializeLayout(&state); resetFlash();
                expanded(partitions[incomplete], pairs[pair][0]);
                expanded(partitions[complete], pairs[pair][1]);
                if (side == 0) partitions[incomplete][0xFF00 + 100] ^= 1;
                else partitions[incomplete][100] ^= 1;
                memcpy(snapshots, partitions, sizeof(partitions));
                assert(Save_GetSaveFilesStatus(&state) == LOAD_STATUS_SLOT_FAIL);
                assert(state.lastGoodSector == complete && state.saveCounter == pairs[pair][1]);
                s = SaveData_New();
                assert(s->flashChipDetected && !s->isNewGame && s->saveFileExists);
                assert(s->lastGoodSector == complete && s->saveCounter == pairs[pair][1]);
                assert(loadCalls == 1 && frontierCalls == 1 && s->statusFlags == 1);
                assert(!memcmp(s->dynamic_region, partitions[complete], CAMPAIGN_MAIN_BYTES));
                assertNoMutation();
                Heap_Free(s);
            }
        }
    }
    /* Native tie outcome is retained where safe: complete bank 0 remains GOOD,
     * but incomplete bank 0 must fall back to complete bank 1 with SLOT_FAIL. */
    for (incomplete = 0; incomplete < 2; incomplete++) {
        u32 complete = 1 - incomplete;
        initializeLayout(&state); resetFlash();
        expanded(partitions[0], 0); expanded(partitions[1], 0);
        partitions[incomplete][0xFF00 + 100] ^= 1;
        assert(Save_GetSaveFilesStatus(&state) ==
               (complete == 0 ? LOAD_STATUS_IS_GOOD : LOAD_STATUS_SLOT_FAIL));
        assert(state.lastGoodSector == complete && state.saveCounter == 0);
    }
}

static void test_failclosed(void) {
    SaveData *s;
    volatile u32 mode;
    for (mode = 0; mode < 3; mode++) {
        resetFlash();
        if (mode == 0) legacy(partitions[0], 9);
        else {
            expanded(partitions[0], 9);
            if (mode == 1) stateAt(partitions[0])->version[0] = 2;
            else {
                stateAt(partitions[0])->magic[0] = 'X';
                footer(partitions[0], 0, CAMPAIGN_GENERAL_BYTES, 0, 9);
            }
        }
        memcpy(snapshots, partitions, sizeof(partitions));
        s = SaveData_New();
        assert(!s->flashChipDetected && s->isNewGame && !s->saveFileExists);
        assert(s->statusFlags & 2);
        assert(loadCalls == 0 && frontierCalls == 0 && frees == 2);
        assert(Save_Campaign_Get(s)); /* safe initialized RAM, NOT a migration */
        assert(SaveGameNormal(s) == WRITE_STATUS_TOTAL_FAIL);
        assertNoMutation();
        _02111868.unk_10.saveData = s;
        if (!setjmp(terminalJump)) nativeStartupGate();
        assert(terminalWaits == 3 && overlayCalls == 0);
        assertNoMutation();
        Heap_Free(s);
    }
    resetFlash();
    s = SaveData_New();
    assert(s->flashChipDetected && s->isNewGame && Save_Campaign_Get(s));
    assert(flashWrites == 0);
    Heap_Free(s);
    resetFlash(); expanded(partitions[0], 9); expanded(partitions[1], 8);
    s = SaveData_New();
    assert(s->flashChipDetected && !s->isNewGame && s->saveFileExists);
    assert(loadCalls == 1 && frontierCalls == 1 && flashWrites == 0);
    Heap_Free(s);
}

int main(int argc, char **argv) {
    assert(argc == 2);
    if (!strcmp(argv[1], "contract")) test_contract();
    else if (!strcmp(argv[1], "ranges")) test_ranges();
    else if (!strcmp(argv[1], "headers")) test_invalid_headers();
    else if (!strcmp(argv[1], "wrapper")) test_wrappers_getter();
    else if (!strcmp(argv[1], "layout")) test_layout();
    else if (!strcmp(argv[1], "classification")) test_classification();
    else if (!strcmp(argv[1], "footer")) test_footer_semantics();
    else if (!strcmp(argv[1], "status")) test_native_status();
    else if (!strcmp(argv[1], "reads")) test_failed_reads();
    else if (!strcmp(argv[1], "nonblank")) test_nonblank_no_pair_failclosed();
    else if (!strcmp(argv[1], "totalfail")) test_total_fail_constructor();
    else if (!strcmp(argv[1], "blankproof")) test_blank_proof();
    else if (!strcmp(argv[1], "goodbackup")) test_good_backup_after_corrupt_or_unread();
    else if (!strcmp(argv[1], "rollover-incomplete")) test_rollover_incomplete_newer_transaction();
    else if (!strcmp(argv[1], "counter-transactions")) test_native_counter_transaction_selection();
    else if (!strcmp(argv[1], "incomplete-counters")) test_incomplete_newer_transaction_counter_boundaries();
    else if (!strcmp(argv[1], "failclosed")) test_failclosed();
    else assert(0);
    puts("host campaign-save checks passed");
    return 0;
}
"""


def build_harness(directory):
    changes = PREP.source_edits(ROOT)
    save = changes["src/save.c"].decode()
    arrays = changes["src/save_arrays.c"].decode()
    for name in ("save.h", "save_trainer_house.h"):
        put(directory, name, (ROOT / "include" / name).read_bytes())
    put(directory, "global.h", GLOBAL_STUB)
    global_constants = (ROOT / "include/constants/global.h").read_text()
    put(directory, "constants/global.h", "\n".join(
        re.search(r"^#define " + name + r"\s+\d+", global_constants, re.M).group()
        for name in ("PLAYER_NAME_LENGTH", "POKEMON_NAME_LENGTH", "PARTY_SIZE")) + "\n")
    put(directory, "nitro/math/crc.h", (ROOT / "lib/include/nitro/math/crc.h").read_bytes())
    put(directory, "heap.h", '#include "global.h"\n'
        'enum HeapID { HEAP_ID_1 = 1, HEAP_ID_3 = 3, HEAP_ID_DEFAULT = 0 };\n')
    # Actual MailMessage declaration; no complete donor/Pokemon subsystem stubs.
    pokemon = (ROOT / "include/pokemon_types_def.h").read_text()
    mail = re.search(r"typedef struct MailMessage \{.*?\} MailMessage;", pokemon, re.S).group()
    put(directory, "pokemon_types_def.h",
        '#include "global.h"\n#define MAILMSG_FIELDS_MAX 2\n' + mail)
    put(directory, "math_util.h", '#include "global.h"\nu16 GF_CalcCRC16(const void *, u32);\n')
    put(directory, "string_util.h", '#include "global.h"\n'
        'void StringFillEOS(u16 *, u32);\nBOOL StringNotEqual(const u16 *, const u16 *);\n')
    # Use the actual native registry types, not every unrelated subsystem header.
    registry_header = (ROOT / "include/save_arrays.h").read_text()
    declarations = registry_header[registry_header.index("typedef u32 (*SAVESIZEFN)"):
                                   registry_header.index("struct ExtraSaveChunkHeader")]
    put(directory, "save_arrays.h", '#include "save.h"\n' + declarations +
        '\nextern const struct SaveChunkHeader gSaveChunkHeaders[];\n'
        'extern const int gNumSaveChunkHeaders;\n')
    put(directory, "save_campaign.h", changes["include/save_campaign.h"])
    put(directory, "save_campaign.c", changes["src/save_campaign.c"])
    put(directory, "save_trainer_house.c", (ROOT / "src/save_trainer_house.c").read_bytes())

    registry = re.search(r"const struct SaveChunkHeader gSaveChunkHeaders\[\] = \{.*?\n\};",
                         arrays, re.S).group()
    entries = re.findall(r"\{\s*(SAVE_\w+),\s*([01]),\s*"
                         r"\(SAVESIZEFN\)(\w+),\s*\(SAVEINITFN\)(\w+),\s*\}", registry)
    assert len(entries) == 42
    # All native IDs/order/block membership come from the actual registry.
    # Only earlier-size SDK stand-ins aggregate to the verified 0xE714 prefix.
    earlier_total = 0xF614 - 0xF00
    callbacks = ["static BOOL legacyLayout;"]
    for index, (_, block, size, init) in enumerate(entries):
        assert int(block) == (index == 41)
        if index < 40:
            payload = 0 if index < 39 else earlier_total - 40 * 4
            callbacks.append(f"static u32 {size}(void) {{ return {payload}; }}")
            callbacks.append(f"static void {init}(void *p) {{ (void)p; }}")
        elif index == 41:
            callbacks.append(f"static u32 {size}(void) {{ return 0x12310 - 16 - 4; }}")
            callbacks.append(f"static void {init}(void *p) {{ (void)p; }}")
    # Preserve callback registration while permitting vanilla comparison in this harness only.
    registry = registry.replace("(SAVESIZEFN)Save_TrainerHouseCampaign_sizeof",
                                "(SAVESIZEFN)hostTrainerHouseSize")
    callbacks.append("static u32 hostTrainerHouseSize(void) { return legacyLayout "
                     "? Save_TrainerHouse_sizeof() : Save_TrainerHouseCampaign_sizeof(); }")
    functions = [
        "SaveArray_Get", "GetSaveChunkSizePlusCRC", "SaveData_InitSubstructs",
        "SaveData_InitSlotSpecs", "Save_InitDynamicRegion_Internal", "Save_InitDynamicRegion",
        "SaveSlotCheck_InitDummy", "SaveArray_CalcCRC16MinusFooter", "GetSaveSectorFooterPtr",
        "ValidateSaveSectorFooter", "SaveSlotCheck_InitFromSavedat", "SaveCounterCompare",
        "SaveSlotCheckCompare", "Save_RecordWhichLatestGoodSector", "Save_GetSaveFilesStatus",
        "SaveData_New", "SaveGameNormal", "Save_FlashChipIsDetected",
    ]
    bodies = "\n\n".join(function(save, name) for name in functions)
    crc = function((ROOT / "src/math_util.c").read_text(), "GF_CalcCRC16")
    main = (ROOT / "src/main.c").read_text()
    start = main.index("    if (!Save_FlashChipIsDetected(")
    end = main.index("    gSystem.unk70", start)
    startup = "static void nativeStartupGate(void) {\n" + main[start:end] + "}\n"
    error = function((ROOT / "src/save_data_read_error.c").read_text(), "ShowSaveDataReadError")
    loop = error[error.index("    while (TRUE)"): -1]
    assert not re.search(r"\b(return|break|goto)\b", loop)
    terminal = "static void ShowSaveDataReadError(enum HeapID id) {\n(void)id;\n" + loop + "}\n"
    harness = (HOST_SUPPORT + crc + "\n" + "\n".join(callbacks) + "\n" + registry
               + "\nconst int gNumSaveChunkHeaders = NELEMS(gSaveChunkHeaders);\n"
               + bodies + "\n" + terminal + startup + HOST_TESTS)
    put(directory, "campaign_host.c", harness)
    binary = directory / "campaign_host"
    command = [
        "cc", "-std=c99", "-O1", "-Wall", "-Wextra", "-Werror",
        "-Wno-unknown-pragmas", "-Wno-unused-parameter", "-Wno-sign-compare",
        "-iquote", str(directory), "-iquote", str(ROOT / "include"),
        str(directory / "campaign_host.c"), str(directory / "save_campaign.c"),
        str(directory / "save_trainer_house.c"), "-o", str(binary),
    ]
    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode:
        raise AssertionError("Host compiler failed:\n" + result.stdout + result.stderr)
    return binary


@unittest.skipUnless(shutil.which("cc"), "host C compiler required")
class CampaignNativeHostTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory(prefix="campaign-host-tests-")
        cls.binary = build_harness(Path(cls.temporary.name))

    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()

    def run_case(self, case):
        result = subprocess.run([str(self.binary), case], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_exact_block_and_native_struct_sizes(self):
        self.run_case("contract")

    def test_all_id_boundaries_flag_zero_regions_and_opaque_bytes(self):
        self.run_case("ranges")

    def test_invalid_headers_never_initialize_or_mutate(self):
        self.run_case("headers")

    def test_wrapper_prefix_preservation_and_allocation_checked_getter(self):
        self.run_case("wrapper")

    def test_actual_native_layout_functions_42_entries_35_pages(self):
        self.run_case("layout")

    def test_blank_legacy_supported_unknown_corrupt_classification(self):
        self.run_case("classification")

    def test_actual_footer_and_crc_exclusion_semantics(self):
        self.run_case("footer")

    def test_actual_native_status_and_same_format_backup_recovery(self):
        self.run_case("status")

    def test_only_successful_reads_are_classified(self):
        self.run_case("reads")

    def test_result_four_ram_only_terminal_startup_and_write_refusal(self):
        self.run_case("failclosed")

    def test_nonblank_without_usable_pair_cannot_become_a_writable_new_game(self):
        self.run_case("nonblank")

    def test_native_total_fail_also_disables_gameplay_and_writes(self):
        self.run_case("totalfail")

    def test_only_two_successfully_read_blank_banks_allow_new_game(self):
        self.run_case("blankproof")

    def test_good_same_format_backup_recovers_after_corruption_or_read_failure(self):
        self.run_case("goodbackup")

    def test_rollover_incomplete_newer_pair_never_selects_dummy_storage(self):
        self.run_case("rollover-incomplete")

    def test_native_counter_comparison_rollover_unsigned_and_equal_pair_selection(self):
        self.run_case("counter-transactions")

    def test_incomplete_newer_transaction_counter_boundaries_and_both_bank_orders(self):
        self.run_case("incomplete-counters")


class CampaignPreparationTests(unittest.TestCase):
    def test_parent_contract_and_only_trainer_house_callback_swap(self):
        contract = PREP.check_contract()
        self.assertEqual(contract["native_allocation"]["entry_count"], 42)
        self.assertEqual(contract["native_allocation"]["footer_magic"], 0x20060623)
        self.assertEqual(contract["transaction_selection"], PREP.TRANSACTION_SELECTION)
        before = (ROOT / "src/save_arrays.c").read_bytes()
        edits = PREP.source_edits(ROOT)
        after = edits["src/save_arrays.c"]
        reversed_delta = after.replace(b'#include "save_campaign.h"\n', b"").replace(
            b"Save_TrainerHouseCampaign_sizeof", b"Save_TrainerHouse_sizeof").replace(
            b"Save_TrainerHouseCampaign_Init", b"Save_TrainerHouse_Init")
        self.assertEqual(before, reversed_delta)
        self.assertNotIn("include/save.h", edits)
        self.assertNotIn("src/save_trainer_house.c", edits)
        self.assertEqual(function(edits["src/save.c"].decode(), "SaveCounterCompare"),
                         function((ROOT / "src/save.c").read_text(), "SaveCounterCompare"))
        self.assertEqual(edits["main.lsf"].count(b"Object src/save_campaign.o"), 1)
        self.assertEqual((ROOT / "common.mk").read_text().count(
            "$(call rwildcard,src,*.c)"), 1)

    def test_footer_magic_and_exact_transaction_contract_facts_are_required(self):
        contract = PREP.check_contract()
        wrong_magic = json.loads(json.dumps(contract))
        wrong_magic["native_allocation"]["footer_magic"] = 0x20060624
        missing_magic = json.loads(json.dumps(contract))
        del missing_magic["native_allocation"]["footer_magic"]
        missing_transactions = json.loads(json.dumps(contract))
        del missing_transactions["transaction_selection"]
        invalid = [wrong_magic, missing_magic, missing_transactions]
        for key, value in PREP.TRANSACTION_SELECTION.items():
            edited = json.loads(json.dumps(contract))
            edited["transaction_selection"][key] = not value if isinstance(value, bool) else value + " incorrect"
            invalid.append(edited)
        for edited in invalid:
            with patch.object(PREP, "read", return_value=json.dumps(edited).encode()):
                with self.assertRaisesRegex(ValueError, "Parent-owned campaign-save v1 contract differs"):
                    PREP.check_contract()

    def test_fresh_candidate_before_after_and_asset_preservation(self):
        with tempfile.TemporaryDirectory(prefix="campaign-prepare-tests-") as tmp:
            base = Path(tmp)
            source, output = base / "source", base / "candidate"
            source.mkdir()
            private_source(source)
            before = {p.relative_to(source).as_posix(): p.read_bytes()
                      for p in source.rglob("*") if p.is_file()}
            report = PREP.prepare(source, output)
            self.assertEqual(report["status"], PREP.STATUS)
            self.assertFalse(report["approved"])
            self.assertFalse(report["runtime_verified"])
            self.assertFalse(report["migration_performed"])
            self.assertEqual(json.loads((output / "campaign-save-source.json").read_text()), report)
            self.assertEqual(set(report["changes"]), {
                "src/save.c", "src/save_arrays.c", "main.lsf",
                "src/save_campaign.c", "include/save_campaign.h"})
            for name, data in before.items():
                self.assertEqual((source / name).read_bytes(), data)
                delta = report["changes"].get(name)
                if delta:
                    self.assertEqual(delta["before"], PREP.sha(data))
                    self.assertEqual(delta["after"], PREP.sha((output / name).read_bytes()))
                else:
                    self.assertEqual((output / name).read_bytes(), data)
            self.assertIsNone(report["changes"]["src/save_campaign.c"]["before"])
            PREP.verify_candidate(output, source)
            # Missing guard, size/init callback misregistration, and missing linker
            # object are rejected independently. No old acceptance hash is changed.
            mutations = (
                ("src/save.c", b"return LOAD_STATUS_UNSUPPORTED_CAMPAIGN;", b"return LOAD_STATUS_NOT_EXIST;"),
                ("src/save.c", b"ret->flashChipDetected = FALSE;", b"ret->flashChipDetected = TRUE;"),
                ("src/save.c", b"campaignNonblank = TRUE;", b"campaignNonblank = FALSE;"),
                ("src/save.c", b"campaignSuccessfulReads == 2", b"campaignSuccessfulReads >= 0"),
                ("src/save.c", b"    case LOAD_STATUS_TOTAL_FAIL:\n", b""),
                ("src/save.c",
                 b"checks_main[__newer_main].valid && checks_sub[__newer_main].valid",
                 b"TRUE"),
                ("src/save.c",
                 b"checks_main[__older_main].valid && checks_sub[__older_main].valid",
                 b"TRUE"),
                ("src/save.c", b"idx == 0 && !CampaignSave_HeaderSupported", b"idx == 1 && !CampaignSave_HeaderSupported"),
                ("src/save_arrays.c", b"Save_TrainerHouseCampaign_sizeof", b"Save_TrainerHouse_sizeof"),
                ("src/save_arrays.c", b"Save_TrainerHouseCampaign_Init", b"Save_TrainerHouse_Init"),
                ("main.lsf", b"    Object src/save_campaign.o\n", b""),
            )
            for name, old, new in mutations:
                original = (output / name).read_bytes()
                self.assertIn(old, original)
                (output / name).write_bytes(original.replace(old, new))
                with self.assertRaisesRegex(ValueError, "guard/registration/template mismatch"):
                    PREP.verify_candidate(output, source)
                (output / name).write_bytes(original)
            with self.assertRaisesRegex(ValueError, "fresh"):
                PREP.prepare(source, output)

    def test_overlap_rejected_without_mutation(self):
        with tempfile.TemporaryDirectory(prefix="campaign-overlap-tests-") as tmp:
            source = Path(tmp) / "source"
            source.mkdir()
            for output in (source / "candidate", ROOT / "candidate-never-created", Path(tmp)):
                with self.assertRaisesRegex(ValueError, "fresh|overlaps"):
                    PREP.prepare(source, output)
                self.assertFalse((source / "candidate").exists())
                self.assertFalse((ROOT / "candidate-never-created").exists())

    def test_wrong_input_registration_and_missing_guard_preimages_rejected(self):
        with tempfile.TemporaryDirectory(prefix="campaign-preimage-tests-") as tmp:
            base = Path(tmp)
            source = base / "source"
            source.mkdir()
            private_source(source)
            for name, old, new in (
                ("src/save.c", b"if (!saveData->flashChipDetected)", b"if (FALSE)"),
                ("src/main.c", b"ShowSaveDataReadError(HEAP_ID_DEFAULT);", b";"),
                ("src/save_data_read_error.c", b"while (TRUE)", b"while (FALSE)"),
                ("src/save_arrays.c", b"SAVE_TRAINER_HOUSE,", b"SAVE_PCSTORAGE,"),
                ("main.lsf", b"Object src/save_trainer_house.o", b"Object src/not_the_wrapper.o"),
            ):
                original = (source / name).read_bytes()
                self.assertIn(old, original)
                (source / name).write_bytes(original.replace(old, new))
                with self.assertRaisesRegex(ValueError, "Safety preimage mismatch"):
                    PREP.prepare(source, base / "candidate")
                self.assertFalse((base / "candidate").exists())
                (source / name).write_bytes(original)

    def test_symlinks_hardlinks_and_existing_append_paths_rejected(self):
        with tempfile.TemporaryDirectory(prefix="campaign-path-tests-") as tmp:
            base = Path(tmp)
            source = base / "source"
            source.mkdir()
            private_source(source)
            link = base / "source-link"
            link.symlink_to(source, target_is_directory=True)
            with self.assertRaisesRegex(ValueError, "Symlinked"):
                PREP.prepare(link, base / "candidate")
            put(source, "src/save_campaign.c", b"existing historical source\n")
            with self.assertRaisesRegex(ValueError, "Append-only"):
                PREP.prepare(source, base / "candidate")
            (source / "src/save_campaign.c").unlink()
            import os
            os.link(source / "src/main.c", base / "hardlink")
            with self.assertRaisesRegex(ValueError, "hardlinked"):
                PREP.prepare(source, base / "candidate")
            self.assertFalse((base / "candidate").exists())


if __name__ == "__main__":
    unittest.main()