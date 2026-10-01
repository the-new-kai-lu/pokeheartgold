#ifndef POKEHEARTGOLD_SCRCMD_CAMPAIGN_H
#define POKEHEARTGOLD_SCRCMD_CAMPAIGN_H

#include "script.h"

#define CAMPAIGN_SCRIPT_FIRST_OPCODE  855
#define CAMPAIGN_SCRIPT_OPCODE_COUNT  4
#define CAMPAIGN_SCRIPT_SCRATCH_FIRST 0x8000
#define CAMPAIGN_SCRIPT_SCRATCH_LAST  0x800C

/* Four halfwords: raw region, raw donor ID, output/value, scratch status.
 * Status is 1 on success, 0 on error. BOOL is VM yield, not operation status.
 * Get outputs must be distinct from status. Invalid status stops the script.
 * Set values use native immediate-or-scratch resolution, before writing status.
 * Map-local donor state is not translated into these persistent commands. */
BOOL ScrCmd_CampaignGetFlag(ScriptContext *ctx);
BOOL ScrCmd_CampaignSetFlag(ScriptContext *ctx);
BOOL ScrCmd_CampaignGetVar(ScriptContext *ctx);
BOOL ScrCmd_CampaignSetVar(ScriptContext *ctx);

#endif // POKEHEARTGOLD_SCRCMD_CAMPAIGN_H
