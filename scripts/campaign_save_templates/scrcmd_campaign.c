#include "scrcmd_campaign.h"

#include "field_system.h"
#include "save_campaign.h"
#include "scrcmd.h"

static BOOL IsCampaignScratch(u16 id) {
    return id >= CAMPAIGN_SCRIPT_SCRATCH_FIRST && id <= CAMPAIGN_SCRIPT_SCRATCH_LAST;
}

static u16 *CampaignScratchDestination(ScriptContext *ctx, u16 id) {
    if (ctx->fieldSystem == NULL || ctx->fieldSystem->saveData == NULL || !IsCampaignScratch(id)) {
        return NULL;
    }
    return GetVarPointer(ctx->fieldSystem, id);
}

static BOOL CampaignRead(ScriptContext *ctx, BOOL isFlag) {
    u16 region = ScriptReadHalfword(ctx);
    u16 id = ScriptReadHalfword(ctx);
    u16 outputID = ScriptReadHalfword(ctx);
    u16 statusID = ScriptReadHalfword(ctx);
    u16 *status = CampaignScratchDestination(ctx, statusID);
    u16 *output;
    CampaignSave *state;
    BOOL flag;

    if (status == NULL) {
        StopScript(ctx);
        return FALSE;
    }
    *status = 0;
    if (outputID == statusID) {
        return FALSE;
    }
    output = CampaignScratchDestination(ctx, outputID);
    if (output == NULL || output == status) {
        return FALSE;
    }
    *output = 0;
    state = Save_Campaign_Get(ctx->fieldSystem->saveData);
    if (isFlag) {
        if (CampaignSave_GetFlag(state, region, id, &flag)) {
            *output = flag != FALSE;
            *status = 1;
        }
    } else if (CampaignSave_GetVar(state, region, id, output)) {
        *status = 1;
    }
    return FALSE;
}

static BOOL CampaignWrite(ScriptContext *ctx, BOOL isFlag) {
    u16 region = ScriptReadHalfword(ctx);
    u16 id = ScriptReadHalfword(ctx);
    const u8 *valueOperand = ctx->script_ptr;
    u16 valueID = ScriptReadHalfword(ctx);
    u16 statusID = ScriptReadHalfword(ctx);
    const u8 *resume = ctx->script_ptr;
    u16 *status = CampaignScratchDestination(ctx, statusID);
    u16 value;
    CampaignSave *state;

    if (status == NULL) {
        StopScript(ctx);
        return FALSE;
    }
    if (valueID >= 0x4000 && !IsCampaignScratch(valueID)) {
        /* Never pass persistent/undefined/last-talked IDs to native resolution. */
        *status = 0;
        return FALSE;
    }
    /* Read the validated value through the native helper, then restore the
     * already-consumed operand cursor. A value/status alias must retain its
     * original value until resolution completes. */
    ctx->script_ptr = valueOperand;
    value = ScriptGetVar(ctx);
    ctx->script_ptr = resume;
    *status = 0;
    state = Save_Campaign_Get(ctx->fieldSystem->saveData);
    if (isFlag) {
        *status = CampaignSave_SetFlag(state, region, id, value != 0) ? 1 : 0;
    } else {
        *status = CampaignSave_SetVar(state, region, id, value) ? 1 : 0;
    }
    return FALSE;
}

BOOL ScrCmd_CampaignGetFlag(ScriptContext *ctx) {
    return CampaignRead(ctx, TRUE);
}

BOOL ScrCmd_CampaignSetFlag(ScriptContext *ctx) {
    return CampaignWrite(ctx, TRUE);
}

BOOL ScrCmd_CampaignGetVar(ScriptContext *ctx) {
    return CampaignRead(ctx, FALSE);
}

BOOL ScrCmd_CampaignSetVar(ScriptContext *ctx) {
    return CampaignWrite(ctx, FALSE);
}
