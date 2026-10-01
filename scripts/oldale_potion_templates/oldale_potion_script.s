// PRIVATE source candidate. Emerald's TEMP_1 is map-local, NEVER campaign state.
#define OLDALE_POTION_TOUR VAR_TEMP_x4008
#define OLDALE_POTION_ENTRY_PENDING VAR_TEMP_x4009
#define OLDALE_POTION_RECEIPT 0x84
#define OLDALE_POTION_REGION 0
#define OLDALE_POTION_EMPLOYEE 1

// Synchronous map callback: no scratch destinations, actors, messages or yields.
// Native ContinueGame normally restores saved temp vars without OnTransition.
// The candidate's Oldale-only continue hook invokes this same reset on reload.
Oldale_PotionOnTransition:
SetVar OLDALE_POTION_TOUR, 0
SetVar OLDALE_POTION_ENTRY_PENDING, 1
End

// Frame entry creates a real ScriptEnvironment, unlike synchronous load scripts.
// Clear the frame condition before any yield. Menu resumes do NOT re-arm it.
Oldale_PotionOnEntry:
SetVar OLDALE_POTION_ENTRY_PENDING, 0
LockAll
CampaignGetFlag OLDALE_POTION_REGION, OLDALE_POTION_RECEIPT, VAR_SPECIAL_x8000, VAR_SPECIAL_x8001
Compare VAR_SPECIAL_x8001, 1
GoToIfNe Oldale_PotionEntryFailed
Compare VAR_SPECIAL_x8000, 0
GoToIfEq Oldale_PotionEntryUnreceived
MovePersonFacing OLDALE_POTION_EMPLOYEE, 13, 0, 7, DIR_SOUTH
ReleaseAll
End
Oldale_PotionEntryUnreceived:
MovePersonFacing OLDALE_POTION_EMPLOYEE, 13, 0, 14, DIR_SOUTH
ReleaseAll
End
Oldale_PotionEntryFailed:
SetVar OLDALE_POTION_TOUR, 2
NPCMsg 6
GoTo Oldale_PotionClose

Oldale_MartEmployee:
LockAll
FacePlayer
// Check operation status FIRST. A failed read's zero output is not "unreceived".
CampaignGetFlag OLDALE_POTION_REGION, OLDALE_POTION_RECEIPT, VAR_SPECIAL_x8000, VAR_SPECIAL_x8001
Compare VAR_SPECIAL_x8001, 1
GoToIfNe Oldale_PotionReadFailed
Compare VAR_SPECIAL_x8000, 0
GoToIfNe Oldale_PotionExplain
Compare OLDALE_POTION_TOUR, 2
GoToIfEq Oldale_PotionReadFailed
Compare OLDALE_POTION_TOUR, 0
GoToIfNe Oldale_PotionExplain
GetPlayerFacing VAR_SPECIAL_x8002
Compare VAR_SPECIAL_x8002, DIR_SOUTH
GoToIfEq Oldale_PotionStartTour
Compare VAR_SPECIAL_x8002, DIR_NORTH
GoToIfEq Oldale_PotionStartTour
Compare VAR_SPECIAL_x8002, DIR_EAST
GoToIfEq Oldale_PotionStartTour
// Emerald supplies no west-facing escort (the east side is a sealed house).
NPCMsg 9
GoTo Oldale_PotionClose

Oldale_PotionStartTour:
SetVar OLDALE_POTION_TOUR, 1
// Native Cherrygrove's std_play_follow_music uses this sequence, not Emerald PCM.
PlayBGM SEQ_GS_E_TSURETEKE2
NPCMsg 1
WaitABPress
CloseMsg
Compare VAR_SPECIAL_x8002, DIR_SOUTH
GoToIfEq Oldale_PotionTourSouth
Compare VAR_SPECIAL_x8002, DIR_NORTH
GoToIfEq Oldale_PotionTourNorth
ApplyMovement obj_player, Oldale_PotionPlayerEast
ApplyMovement OLDALE_POTION_EMPLOYEE, Oldale_PotionEmployeeEast
WaitMovement
GoTo Oldale_PotionAtMart

Oldale_PotionTourSouth:
ApplyMovement OLDALE_POTION_EMPLOYEE, Oldale_PotionEmployeeSouth
ApplyMovement obj_player, Oldale_PotionPlayerSouth
WaitMovement
GoTo Oldale_PotionAtMart
Oldale_PotionTourNorth:
ApplyMovement OLDALE_POTION_EMPLOYEE, Oldale_PotionEmployeeNorth
ApplyMovement obj_player, Oldale_PotionPlayerNorth
WaitMovement
GoTo Oldale_PotionAtMart

Oldale_PotionAtMart:
NPCMsg 2
WaitABPress
CloseMsg
// The introduction yields. Re-read immediately before delivery, fail closed.
CampaignGetFlag OLDALE_POTION_REGION, OLDALE_POTION_RECEIPT, VAR_SPECIAL_x8000, VAR_SPECIAL_x8001
Compare VAR_SPECIAL_x8001, 1
GoToIfNe Oldale_PotionTourReadFailed
Compare VAR_SPECIAL_x8000, 0
GoToIfNe Oldale_PotionTourExplain
// Native opcode125 calls Bag_AddItem; VAR_SPECIAL_RESULT is actual VAR_RESULT800C.
// Delivery/commit/rollback are synchronous: no message, movement or wait between.
GiveItem ITEM_POTION, 1, VAR_SPECIAL_RESULT
Compare VAR_SPECIAL_RESULT, 1
GoToIfNe Oldale_PotionBagFull
CampaignSetFlag OLDALE_POTION_REGION, OLDALE_POTION_RECEIPT, 1, VAR_SPECIAL_x8001
Compare VAR_SPECIAL_x8001, 1
GoToIfNe Oldale_PotionRollback
PlayFanfare SEQ_ME_ITEM
NPCMsg 5
WaitFanfare
WaitABPress
CloseMsg
BufferPlayersName 0
NPCMsg 10
WaitABPress
CloseMsg
Oldale_PotionTourExplain:
NPCMsg 3
GoTo Oldale_PotionTourClose

Oldale_PotionRollback:
// Native opcode126 calls Bag_TakeItem. Nothing can consume the added unit here.
TakeItem ITEM_POTION, 1, VAR_SPECIAL_RESULT
Compare VAR_SPECIAL_RESULT, 1
GoToIfNe Oldale_PotionQuarantine
NPCMsg 7
GoTo Oldale_PotionTourClose
Oldale_PotionBagFull:
NPCMsg 4
GoTo Oldale_PotionTourClose
Oldale_PotionTourReadFailed:
NPCMsg 6
Oldale_PotionTourClose:
WaitABPress
CloseMsg
FadeOutBGM 0, 16
ResetBGM
FadeInBGM 16
ReleaseAll
End

Oldale_PotionExplain:
NPCMsg 3
GoTo Oldale_PotionClose
Oldale_PotionReadFailed:
NPCMsg 6
Oldale_PotionClose:
WaitABPress
CloseMsg
ReleaseAll
End

Oldale_PotionQuarantine:
// Unreachable under verified native bag semantics after a successful add.
// Do NOT release or permit saving/re-entry with an unreceipted reward if corrupt.
NPCMsg 8
WaitABPress
CloseMsg
Oldale_PotionQuarantineWait:
Wait 60, VAR_SPECIAL_x8003
GoTo Oldale_PotionQuarantineWait

.balign 4, 0
Oldale_PotionEmployeeEast:
WalkNormalNorth 7
WalkOnSpotFasterSouth
EndMovement
Oldale_PotionEmployeeSouth:
WalkNormalWest
WalkNormalNorth 2
WalkNormalEast
WalkNormalNorth 5
WalkOnSpotFasterSouth
EndMovement
Oldale_PotionEmployeeNorth:
WalkNormalNorth 7
WalkOnSpotFasterSouth
EndMovement
Oldale_PotionPlayerEast:
WalkNormalEast
WalkNormalNorth 6
EndMovement
Oldale_PotionPlayerSouth:
Delay16 4
WalkNormalNorth 5
EndMovement
Oldale_PotionPlayerNorth:
WalkNormalNorth 7
EndMovement