#include "pokedex_util.h"

#include "global.h"

#include "pokemon.h"
#include "constants/species.h"

BOOL SaveArray_IsNatDexEnabled(SaveData *saveData) {
    return Pokedex_IsNatDexEnabled(Save_Pokedex_Get(saveData));
}

BOOL Pokedex_IsNatDexEnabled(const Pokedex *pokedex) {
    return Pokedex_GetNatDexFlag(pokedex) == TRUE;
}

u32 Pokedex_ConvertToCurrentDexNo(BOOL natDexFlag, u32 species) {
    if (natDexFlag == FALSE) {
        return SpeciesToJohtoDexNo((u16)species);
    }
    return species;
}

// Shared by the National Dex, Summary, and storage display; species IDs stay sparse.
u32 FakemonDexDisplayNumber(BOOL natDexFlag, u32 species) {
    if (IsFakemonSpecies(species)) {
        return natDexFlag ? NATIONAL_DEX_COUNT + 1 + species - SPECIES_VOLTUFF : 0;
    }
    return Pokedex_ConvertToCurrentDexNo(natDexFlag, species);
}
