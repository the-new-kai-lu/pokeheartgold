#include "fakemon.h"
#include "constants/items.h"
#include "constants/moves.h"
#include "constants/species.h"
#include "pokemon.h"
#include "fakemon_data.h"
#include "fakemon_rules.h"

u32 FakemonConvertEvolutionExp(u16 oldSpecies, u16 newSpecies, u32 exp) {
    int level;
    if (!((oldSpecies == SPECIES_VOLTUFF && newSpecies == SPECIES_SURGUENON)
       || (oldSpecies == SPECIES_EMBERNEWT && (newSpecies == SPECIES_PYROVARAN || newSpecies == SPECIES_RIMEVARAN))
       || (oldSpecies == SPECIES_SEDGLING && newSpecies == SPECIES_CRAGAVIAR))) return exp;
    level = CalcLevelBySpeciesAndExp(oldSpecies, exp);
    if (level >= 100) return GetMonExpBySpeciesAndLevel(newSpecies, 100);
    return FakemonMapExpProgress(exp,
        GetMonExpBySpeciesAndLevel(oldSpecies, level), GetMonExpBySpeciesAndLevel(oldSpecies, level + 1),
        GetMonExpBySpeciesAndLevel(newSpecies, level), GetMonExpBySpeciesAndLevel(newSpecies, level + 1));
}
u16 FakemonHatchSpecies(u16 species) {
    return IsFakemonSpecies(species) ? sFakemonHatchSpecies[species - SPECIES_VOLTUFF] : species;
}
u8 FakemonEggMoves(u16 species, u16 *dest) {
    u8 i = 0;
    if (!IsFakemonSpecies(species)) return 0;
    while (i < 16 && sFakemonEggMoves[species - SPECIES_VOLTUFF][i] != 0xFFFF) {
        dest[i] = sFakemonEggMoves[species - SPECIES_VOLTUFF][i]; i++;
    }
    return i;
}
void FakemonTutorMoves(u16 species, u8 *dest) {
    MI_CpuCopy8(sFakemonTutorMoves[species - SPECIES_VOLTUFF], dest, 8);
}
u16 FakemonLearnMove(Pokemon *mon, u16 entry) {
    if (GetMonData(mon, MON_DATA_SPECIES, NULL) == SPECIES_EMBERNEWT
        && LEVEL_UP_LEARNSET_LVL(entry) == 14 && LEVEL_UP_LEARNSET_MOVE(entry) == MOVE_FIRE_FANG
        && GetMonData(mon, MON_DATA_HELD_ITEM, NULL) == ITEM_ICICLE_PLATE) return MOVE_ICE_FANG;
    return LEVEL_UP_LEARNSET_MOVE(entry);
}

typedef struct FakemonKOIdentity {
    u32 pid, ot;
    u8 slot;
    BOOL valid;
} FakemonKOIdentity;
static FakemonKOIdentity sPendingKO[4];
static FakemonKOIdentity sExpKO;
static FakemonKOIdentity sRareEvolution[6];
static BOOL sBattleEvolutionScope;
static int sEvolutionSlot;
static BOOL SameIdentity(const FakemonKOIdentity *identity, Pokemon *mon) {
    return identity->valid && GetMonData(mon, MON_DATA_SPECIES, NULL) == SPECIES_EMBERNEWT
        && identity->pid == GetMonData(mon, MON_DATA_PERSONALITY, NULL)
        && identity->ot == GetMonData(mon, MON_DATA_OT_ID, NULL);
}
void FakemonBattleReset(void) {
    MI_CpuClear8(sPendingKO, sizeof(sPendingKO));
    MI_CpuClear8(sRareEvolution, sizeof(sRareEvolution));
    MI_CpuClear8(&sExpKO, sizeof(sExpKO));
    sBattleEvolutionScope = FALSE;
    sEvolutionSlot = -1;
}
void FakemonRecordDirectKO(Pokemon *attacker, int slot, int victim, BOOL opponent, int moveType, BOOL knockout, u16 heldItem) {
    FakemonKOIdentity *record;
    if (victim < 0 || victim >= 4) return;
    record = &sPendingKO[victim];
    record->valid = FALSE;
    if (!opponent || !knockout || slot < 0 || slot >= 6 || moveType != TYPE_ICE
        || heldItem != ITEM_NEVERMELTICE || GetMonData(attacker, MON_DATA_SPECIES, NULL) != SPECIES_EMBERNEWT) return;
    record->pid = GetMonData(attacker, MON_DATA_PERSONALITY, NULL);
    record->ot = GetMonData(attacker, MON_DATA_OT_ID, NULL);
    record->slot = slot;
    record->valid = TRUE;
}
void FakemonAfterHealthUpdate(int victim, int hp) {
    if (victim >= 0 && victim < 4 && hp > 0) sPendingKO[victim].valid = FALSE;
}
void FakemonBeginExp(int victim) {
    sExpKO.valid = FALSE;
    if (victim >= 0 && victim < 4) {
        sExpKO = sPendingKO[victim];
        sPendingKO[victim].valid = FALSE;
    }
}
void FakemonEndExp(void) { sExpKO.valid = FALSE; }
void FakemonOnBattleLevelUp(Pokemon *mon, int slot) {
    if (slot < 0 || slot >= 6) return;
    /* A later level-up from another KO invalidates earlier eligibility. */
    sRareEvolution[slot].valid = FALSE;
    if (sExpKO.slot == slot && SameIdentity(&sExpKO, mon)
        && GetMonData(mon, MON_DATA_LEVEL, NULL) >= 16
        && GetMonData(mon, MON_DATA_HELD_ITEM, NULL) == ITEM_NEVERMELTICE) sRareEvolution[slot] = sExpKO;
}
void FakemonBattleEvolutionScope(BOOL enabled, int slot) {
    sBattleEvolutionScope = enabled;
    sEvolutionSlot = slot;
}
BOOL FakemonConsumeRareEvolution(Pokemon *mon) {
    BOOL found;
    if (!sBattleEvolutionScope || sEvolutionSlot < 0 || sEvolutionSlot >= 6) return FALSE;
    found = SameIdentity(&sRareEvolution[sEvolutionSlot], mon)
        && sRareEvolution[sEvolutionSlot].slot == sEvolutionSlot;
    sRareEvolution[sEvolutionSlot].valid = FALSE;
    return found;
}
