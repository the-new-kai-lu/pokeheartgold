#include "constants/scrcmd.h"
#include "constants/expansion.h"
.include "asm/macros/script.inc"

.rodata

ScrDef HoennReward_Claim
ScrDef HoennReward_Interaction
ScrDefEnd

// Dedicated appended bank; no existing NPC or map is redirected here.
// Input: VAR_SPECIAL_x8000 = chosen species, or 0 for cancellation.
// Output: VAR_SPECIAL_RESULT = GIVE_MON_* or HOENN_GIFT_*.
// The lab interaction must lock input before invoking this entry.
HoennReward_Claim:
Call HoennReward_Transaction
End
HoennReward_Transaction:
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
Return

// NPC entry 1 requires message bank 829 in the future lab map header.
// No existing NPC/map is redirected. Entry 0 remains the claim API.
HoennReward_Interaction:
LockAll
FacePlayer
Compare VAR_HOENN_RESCUE_STATE, HOENN_RESCUE_COMPLETE
GoToIfNe HoennReward_NotEligible
Compare VAR_HOENN_STARTER_RECEIVED, 0
GoToIfNe HoennReward_AlreadyReceived
NPCMsg 0
MenuInit 1, 1, 0, 1, VAR_SPECIAL_x8000
MenuItemAdd 1, 255, SPECIES_TREECKO
MenuItemAdd 2, 255, SPECIES_TORCHIC
MenuItemAdd 3, 255, SPECIES_MUDKIP
MenuItemAdd 4, 255, 0
MenuExec
CloseMsg
Call HoennReward_Transaction
Compare VAR_SPECIAL_RESULT, GIVE_MON_PARTY
GoToIfEq HoennReward_Party
Compare VAR_SPECIAL_RESULT, GIVE_MON_PC
GoToIfEq HoennReward_PC
Compare VAR_SPECIAL_RESULT, GIVE_MON_NO_SPACE
GoToIfEq HoennReward_Full
NPCMsg 8
GoTo HoennReward_Close
HoennReward_Party:
NPCMsg 5
GoTo HoennReward_Close
HoennReward_PC:
NPCMsg 6
GoTo HoennReward_Close
HoennReward_Full:
NPCMsg 7
GoTo HoennReward_Close
HoennReward_NotEligible:
NPCMsg 9
GoTo HoennReward_Close
HoennReward_AlreadyReceived:
NPCMsg 10
HoennReward_Close:
WaitABPress
CloseMsg
ReleaseAll
End