#include "constants/scrcmd.h"
#include "constants/expansion.h"
.include "asm/macros/script.inc"

.rodata

ScrDef HoennReward_Claim
ScrDefEnd

// Dedicated appended bank; no existing NPC or map is redirected here.
// Input: VAR_SPECIAL_x8000 = chosen species, or 0 for cancellation.
// Output: VAR_SPECIAL_RESULT = GIVE_MON_* or HOENN_GIFT_*.
// The lab interaction must lock input before invoking this entry.
HoennReward_Claim:
SetVar VAR_SPECIAL_RESULT, HOENN_GIFT_NOT_ELIGIBLE
Compare VAR_HOENN_RESCUE_STATE, HOENN_RESCUE_COMPLETE
GoToIfNe HoennReward_End
SetVar VAR_SPECIAL_RESULT, HOENN_GIFT_ALREADY_RECEIVED
Compare VAR_HOENN_STARTER_RECEIVED, 0
GoToIfNe HoennReward_End
SetVar VAR_SPECIAL_RESULT, HOENN_GIFT_CANCELLED
Compare VAR_SPECIAL_x8000, SPECIES_TREECKO
GoToIfEq HoennReward_Deliver
Compare VAR_SPECIAL_x8000, SPECIES_TORCHIC
GoToIfEq HoennReward_Deliver
Compare VAR_SPECIAL_x8000, SPECIES_MUDKIP
GoToIfNe HoennReward_End
HoennReward_Deliver:
GiveMonToPartyOrPC VAR_SPECIAL_x8000, 5, ITEM_NONE, 0, 0, VAR_SPECIAL_RESULT
Compare VAR_SPECIAL_RESULT, GIVE_MON_PARTY
GoToIfEq HoennReward_RecordReceipt
Compare VAR_SPECIAL_RESULT, GIVE_MON_PC
GoToIfNe HoennReward_End
HoennReward_RecordReceipt:
// GiveMonToPartyOrPC and these commands do not yield: receipt is recorded
// before any dialogue, menu, save, or other asynchronous operation.
CopyVar VAR_HOENN_STARTER_RECEIVED, VAR_SPECIAL_x8000
HoennReward_End:
End