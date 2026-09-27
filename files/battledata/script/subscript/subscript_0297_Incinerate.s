    .include "macros/btlcmd.inc"

    .data

_000:
    TryIncinerate _END
    PrintMessage msg_0197_incinerate, TAG_NICKNAME_ITEM, BATTLER_CATEGORY_DEFENDER, BATTLER_CATEGORY_MSG_TEMP
    Wait
    WaitButtonABTime 30
_END:
    End
