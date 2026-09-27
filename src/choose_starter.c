#include "choose_starter.h"

#include "constants/balls.h"
#include "constants/items.h"
#include "constants/species.h"

#include "field_system.h"
#include "map_header.h"
#include "task.h"
#include "unk_02055244.h"
#include "unk_020552A4.h"
#include "update_dex_received.h"

static BOOL GiveStarterTrio(TaskManager *taskManager);

// Keep the script command entry point, but this edition has no choice screen.
void LaunchStarterChoiceScene(FieldSystem *fieldSystem) {
    TaskManager_Call(fieldSystem->taskman, GiveStarterTrio, NULL);
}

static BOOL GiveStarterTrio(TaskManager *taskManager) {
    FieldSystem *fieldSystem = TaskManager_GetFieldSystem(taskManager);
    u32 *state = TaskManager_GetStatePtr(taskManager);

    switch (*state) {
    case 0:
        PaletteFadeUntilFinished(taskManager);
        (*state)++;
        break;
    case 1:
        CallTask_LeaveOverworld(taskManager);
        (*state)++;
        break;
    case 2: {
        static const int species[] = {
            SPECIES_VOLTUFF,
            SPECIES_EMBERNEWT,
            SPECIES_SEDGLING,
        };
        Party *party = SaveArray_Party_Get(fieldSystem->saveData);
        PlayerProfile *profile = Save_PlayerData_GetProfile(fieldSystem->saveData);
        u32 mapsec = MapHeader_GetMapSec(fieldSystem->location->mapId);
        Pokemon *mon = AllocMonZeroed(HEAP_ID_FIELD2);
        int i;

        // The initial Elm scene runs before the player can obtain any Pokemon.
        GF_ASSERT(Party_GetCount(party) == 0);
        for (i = 0; i < (int)NELEMS(species); i++) {
            int item = ITEM_NONE;
            ZeroMonData(mon);
            CreateMon(mon, species[i], 5, 32, FALSE, 0, OT_ID_PLAYER_ID, 0);
            // Preserve the original starter's trainer memo and encounter type.
            sub_020720FC(mon, profile, BALL_POKE, mapsec, 12, HEAP_ID_FIELD2);
            SetMonData(mon, MON_DATA_HELD_ITEM, &item);
            if (Party_AddMon(party, mon)) {
                UpdatePokedexWithReceivedSpecies(fieldSystem->saveData, mon);
            }
        }
        Heap_Free(mon);
        // Reloading the field creates the lead Pokemon's follower map object.
        CallTask_RestoreOverworld(taskManager);
        (*state)++;
        break;
    }
    case 3:
        CallTask_FadeFromBlack(taskManager);
        (*state)++;
        break;
    case 4:
        return TRUE;
    }

    return FALSE;
}
