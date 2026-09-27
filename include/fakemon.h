#ifndef POKEHEARTGOLD_FAKEMON_H
#define POKEHEARTGOLD_FAKEMON_H
#include "global.h"
#include "pokemon_types_def.h"
u32 FakemonConvertEvolutionExp(u16 oldSpecies, u16 newSpecies, u32 exp);
u16 FakemonHatchSpecies(u16 species);
u8 FakemonEggMoves(u16 species, u16 *dest);
void FakemonTutorMoves(u16 species, u8 *dest);
u16 FakemonLearnMove(Pokemon *mon, u16 entry);
void FakemonBattleReset(void);
void FakemonRecordDirectKO(Pokemon *attacker, int slot, int victim, BOOL opponent, int moveType, BOOL knockout, u16 heldItem);
void FakemonAfterHealthUpdate(int victim, int hp);
void FakemonBeginExp(int victim);
void FakemonEndExp(void);
void FakemonOnBattleLevelUp(Pokemon *mon, int slot);
void FakemonBattleEvolutionScope(BOOL enabled, int slot);
BOOL FakemonConsumeRareEvolution(Pokemon *mon);
#endif
