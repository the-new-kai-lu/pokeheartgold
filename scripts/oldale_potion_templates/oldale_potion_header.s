#include "constants/scrcmd.h"
#include "constants/init_script_types.h"
.include "asm/macros/script.inc"
.rodata
.option alignment off
// No bridge calls in synchronous callbacks: scratch needs ScriptEnvironment.
InitScriptEntry_OnTransition 3
InitScriptEntry_OnFrameTable Oldale_PotionEntryTable
InitScriptEntryEnd
Oldale_PotionEntryTable:
InitScriptGoToIfEqual VAR_TEMP_x4009, 1, 4
InitScriptFrameTableEnd
InitScriptEnd