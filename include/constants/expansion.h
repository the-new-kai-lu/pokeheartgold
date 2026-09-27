#ifndef POKEHEARTGOLD_CONSTANTS_EXPANSION_H
#define POKEHEARTGOLD_CONSTANTS_EXPANSION_H

#include "constants/vars.h"

// Existing, unused vanilla storage: no save partition or capacity change.
// See expansion/EMERALD_OPENING.md for the source/archive audit.
#define VAR_HOENN_RESCUE_STATE     VAR_UNK_416E
#define VAR_HOENN_STARTER_RECEIVED VAR_UNK_416F
#define HOENN_RESCUE_COMPLETE      1

// Gift command results 0..2 retain their existing meanings.
#define HOENN_GIFT_NOT_ELIGIBLE     3
#define HOENN_GIFT_ALREADY_RECEIVED 4
#define HOENN_GIFT_CANCELLED        5

#endif
