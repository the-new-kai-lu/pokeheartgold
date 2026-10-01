#include "save_campaign.h"

#include "math_util.h"
#include "save_trainer_house.h"

#include <stddef.h>

typedef char CampaignSizeCheck[sizeof(CampaignSave) == CAMPAIGN_BYTES ? 1 : -1];
typedef char CampaignHoennVarsCheck[offsetof(CampaignSave, hoennVars) == 32 ? 1 : -1];
typedef char CampaignHoennFlagsCheck[offsetof(CampaignSave, hoennFlags) == 544 ? 1 : -1];
typedef char CampaignSinnohVarsCheck[offsetof(CampaignSave, sinnohVars) == 844 ? 1 : -1];
typedef char CampaignSinnohFlagsCheck[offsetof(CampaignSave, sinnohFlags) == 1420 ? 1 : -1];
typedef char CampaignReservedCheck[offsetof(CampaignSave, reserved) == 1784 ? 1 : -1];
typedef char CampaignFooterSizeCheck[sizeof(struct SaveChunkFooter) == 16 ? 1 : -1];
typedef char CampaignCRCExclusionCheck[sizeof(struct SaveArrayFooter) == 16 ? 1 : -1];
typedef char CampaignNativeMagicCheck[SAVE_CHUNK_MAGIC == 0x20060623 ? 1 : -1];

static const u8 sCampaignMagic[8] = { 'E', 'H', 'G', 'S', 'C', 'A', 'M', 'P' };

static u16 ReadLE16(const u8 *data) {
    return (u16)(data[0] | (data[1] << 8));
}

static u32 ReadLE32(const u8 *data) {
    return (u32)data[0] | ((u32)data[1] << 8) | ((u32)data[2] << 16) | ((u32)data[3] << 24);
}

static void WriteLE16(u8 *data, u16 value) {
    data[0] = (u8)value;
    data[1] = (u8)(value >> 8);
}

static BOOL CampaignSave_HasTag(const CampaignSave *state) {
    u32 i;
    if (state == NULL) {
        return FALSE;
    }
    for (i = 0; i < sizeof(sCampaignMagic); i++) {
        if (state->magic[i] != sCampaignMagic[i]) {
            return FALSE;
        }
    }
    return TRUE;
}

BOOL CampaignSave_HeaderSupported(const CampaignSave *state) {
    return CampaignSave_HasTag(state)
        && ReadLE16(state->version) == CAMPAIGN_VERSION
        && ReadLE16(state->length) == CAMPAIGN_BYTES
        && ReadLE16(state->headerSize) == CAMPAIGN_HEADER_BYTES;
}

void CampaignSave_Init(CampaignSave *state) {
    u32 i;
    if (state == NULL) {
        return;
    }
    MI_CpuClear8(state, sizeof(*state));
    for (i = 0; i < sizeof(sCampaignMagic); i++) {
        state->magic[i] = sCampaignMagic[i];
    }
    WriteLE16(state->version, CAMPAIGN_VERSION);
    WriteLE16(state->length, CAMPAIGN_BYTES);
    WriteLE16(state->headerSize, CAMPAIGN_HEADER_BYTES);
}

static BOOL CampaignSave_VarOffset(const CampaignSave *state, u32 region, u32 id, u32 *offset) {
    u32 count;
    u32 base;
    if (!CampaignSave_HeaderSupported(state)) {
        return FALSE;
    }
    if (region == CAMPAIGN_HOENN) {
        count = 256;
        base = offsetof(CampaignSave, hoennVars);
    } else if (region == CAMPAIGN_SINNOH) {
        count = 288;
        base = offsetof(CampaignSave, sinnohVars);
    } else {
        return FALSE;
    }
    if (id < 0x4000 || id - 0x4000 >= count) {
        return FALSE;
    }
    *offset = base + (id - 0x4000) * 2;
    return TRUE;
}

BOOL CampaignSave_GetVar(const CampaignSave *state, u32 region, u32 id, u16 *value) {
    u32 offset;
    if (value == NULL || !CampaignSave_VarOffset(state, region, id, &offset)) {
        return FALSE;
    }
    *value = ReadLE16((const u8 *)state + offset);
    return TRUE;
}

BOOL CampaignSave_SetVar(CampaignSave *state, u32 region, u32 id, u16 value) {
    u32 offset;
    if (!CampaignSave_VarOffset(state, region, id, &offset)) {
        return FALSE;
    }
    WriteLE16((u8 *)state + offset, value);
    return TRUE;
}

static BOOL CampaignSave_FlagOffset(const CampaignSave *state, u32 region, u32 id, u32 *offset) {
    u32 count;
    u32 base;
    if (!CampaignSave_HeaderSupported(state)) {
        return FALSE;
    }
    if (region == CAMPAIGN_HOENN) {
        count = 2400;
        base = offsetof(CampaignSave, hoennFlags);
    } else if (region == CAMPAIGN_SINNOH) {
        count = 2912;
        base = offsetof(CampaignSave, sinnohFlags);
    } else {
        return FALSE;
    }
    if (id >= count) {
        return FALSE;
    }
    *offset = base + id / 8;
    return TRUE;
}

BOOL CampaignSave_GetFlag(const CampaignSave *state, u32 region, u32 id, BOOL *value) {
    u32 offset;
    if (value == NULL || !CampaignSave_FlagOffset(state, region, id, &offset)) {
        return FALSE;
    }
    *value = id != 0 && ((((const u8 *)state)[offset] & (1 << (id % 8))) != 0);
    return TRUE;
}

BOOL CampaignSave_SetFlag(CampaignSave *state, u32 region, u32 id, BOOL value) {
    u32 offset;
    u8 mask;
    if (!CampaignSave_FlagOffset(state, region, id, &offset)) {
        return FALSE;
    }
    if (id == 0) {
        return TRUE;
    }
    mask = (u8)(1 << (id % 8));
    if (value) {
        ((u8 *)state)[offset] |= mask;
    } else {
        ((u8 *)state)[offset] &= (u8)~mask;
    }
    return TRUE;
}

u32 Save_TrainerHouseCampaign_sizeof(void) {
    return ((Save_TrainerHouse_sizeof() + 3) & ~3u) + CAMPAIGN_BYTES;
}

void Save_TrainerHouseCampaign_Init(void *data) {
    u32 prefix = (Save_TrainerHouse_sizeof() + 3) & ~3u;
    Save_TrainerHouse_Init((TrainerHouse *)data);
    CampaignSave_Init((CampaignSave *)((u8 *)data + prefix));
}

const CampaignSave *Save_Campaign_Const_Get(const SaveData *saveData) {
    const struct SaveArrayHeader *header;
    const CampaignSave *state;
    u32 prefix = (Save_TrainerHouse_sizeof() + 3) & ~3u;
    u32 expectedSize = Save_TrainerHouseCampaign_sizeof() + 4;
    if (saveData == NULL) {
        return NULL;
    }
    header = &saveData->arrayHeaders[SAVE_TRAINER_HOUSE];
    /* Check allocation BEFORE even forming a pointer to the extension. */
    if (header->id != SAVE_TRAINER_HOUSE || header->slot != 0
        || header->size != expectedSize || header->offset > CAMPAIGN_MAIN_BYTES
        || header->size > CAMPAIGN_MAIN_BYTES - header->offset
        || header->offset + prefix != CAMPAIGN_EXTENSION_OFFSET) {
        return NULL;
    }
    state = (const CampaignSave *)(saveData->dynamic_region + header->offset + prefix);
    return CampaignSave_HeaderSupported(state) ? state : NULL;
}

CampaignSave *Save_Campaign_Get(SaveData *saveData) {
    return (CampaignSave *)Save_Campaign_Const_Get(saveData);
}

static BOOL CampaignSave_GeneralFooterValid(const u8 *data, u32 size) {
    const u8 *footer = data + size - sizeof(struct SaveChunkFooter);
    /* Match ValidateSaveSectorFooter, including its 16-byte CRC exclusion. */
    return ReadLE32(footer + 4) == size
        && ReadLE32(footer + 8) == SAVE_CHUNK_MAGIC
        && ReadLE16(footer + 12) == 0
        && ReadLE16(footer + 14) == GF_CalcCRC16(data, size - sizeof(struct SaveArrayFooter));
}

enum CampaignPartitionFormat CampaignSave_ClassifyPartition(const void *data, u32 size) {
    const u8 *bytes = (const u8 *)data;
    const CampaignSave *state;
    u32 i;
    BOOL allZero = TRUE;
    BOOL allErased = TRUE;
    if (data == NULL || size != CAMPAIGN_MAIN_BYTES) {
        return CAMPAIGN_PARTITION_UNSUPPORTED;
    }
    state = (const CampaignSave *)(bytes + CAMPAIGN_EXTENSION_OFFSET);
    /* Unknown tags refuse even with a damaged CRC or a supported older backup. */
    if (CampaignSave_HasTag(state) && !CampaignSave_HeaderSupported(state)) {
        return CAMPAIGN_PARTITION_UNSUPPORTED;
    }
    if (CampaignSave_GeneralFooterValid(bytes, CAMPAIGN_LEGACY_GENERAL_BYTES)) {
        return CAMPAIGN_PARTITION_LEGACY;
    }
    if (CampaignSave_GeneralFooterValid(bytes, CAMPAIGN_GENERAL_BYTES)) {
        return CampaignSave_HeaderSupported(state)
            ? CAMPAIGN_PARTITION_SUPPORTED : CAMPAIGN_PARTITION_UNSUPPORTED;
    }
    for (i = 0; i < size; i++) {
        allZero = allZero && bytes[i] == 0;
        allErased = allErased && bytes[i] == 0xFF;
    }
    return allZero || allErased ? CAMPAIGN_PARTITION_BLANK : CAMPAIGN_PARTITION_CORRUPT;
}