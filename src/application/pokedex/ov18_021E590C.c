#include "global.h"
#include "constants/species.h"
#include "constants/charcode.h"
#include "constants/pokemon.h"
#include "application/pokedex/pokedex_internal_constants.h"
#include "fakemon_dex_pages.h"
#include "pokemon.h"
#include "pokedex_util.h"

#include "application/pokedex/pokedex_internal.h"
#include "msgdata/msg.naix"

#include "msgdata.h"
#include "unk_02091278.h"

#if defined(HEARTGOLD)
#define ZUKAN_FLAVOR_GMM (NARC_msg_msg_0803_bin)
#elif defined(SOULSILVER)
#define ZUKAN_FLAVOR_GMM (NARC_msg_msg_0804_bin)
#else
#error "Unable to determine game"
#endif // HGSS

static u16 sFakemonDexPageSpecies;
static u8 sFakemonDexPage;

static int deadstrip_0(int a0);
static String *ov18_021E5A10(int msgBank, int msgNum, enum HeapID heapId);
static void ov18_021E5A50(u16 species, int language, int *pMsgNo, int *pLanguageFlag, int *pLanguageFlagNativeMask);

static const int ov18_021F970C[] = {
    NARC_msg_msg_0828_bin,
    NARC_msg_msg_0823_bin,
    NARC_msg_msg_0824_bin,
    NARC_msg_msg_0825_bin,
    NARC_msg_msg_0826_bin,
    NARC_msg_msg_0827_bin,
};

static const int ov18_021F96F4[] = {
    NARC_msg_msg_0822_bin,
    NARC_msg_msg_0817_bin,
    NARC_msg_msg_0818_bin,
    NARC_msg_msg_0819_bin,
    NARC_msg_msg_0820_bin,
    NARC_msg_msg_0821_bin,
};

static const int ov18_021F9724[] = {
    NARC_msg_msg_0810_bin,
    NARC_msg_msg_0805_bin,
    NARC_msg_msg_0806_bin,
    NARC_msg_msg_0807_bin,
    NARC_msg_msg_0808_bin,
    NARC_msg_msg_0809_bin,
};

String *ov18_021E590C(u16 species, int language, enum HeapID heapId) {
    int languageMsgNum;
    int unused;
    int msgNum;
    int msgBank;

    ov18_021E5A50(species, language, &languageMsgNum, &unused, &msgNum);
    if (msgNum == DEX_LANGUAGE_FLAG_MAX) {
        return GetSpeciesName(species, heapId);
    } else {
        int msgBanks[6];
        ARRAY_ASSIGN(msgBanks, ov18_021F96F4);

        msgBank = msgBanks[msgNum];
        msgNum = languageMsgNum;
    }
    return ov18_021E5A10(msgBank, msgNum, heapId);
}

String *ov18_021E595C(u16 species, int language, enum HeapID heapId) {
    int languageMsgNum;
    int unused;
    int msgNum;
    int msgBank;

    ov18_021E5A50(species, language, &languageMsgNum, &unused, &msgNum);
    if (msgNum == DEX_LANGUAGE_FLAG_MAX) {
        msgNum = species;
        msgBank = NARC_msg_msg_0816_bin;
    } else {
        int msgBanks[6];
        ARRAY_ASSIGN(msgBanks, ov18_021F970C);

        msgBank = msgBanks[msgNum];
        msgNum = languageMsgNum;
    }
    return ov18_021E5A10(msgBank, msgNum, heapId);
}

String *ov18_021E59A8(u16 species, int language, int a2, enum HeapID heapId) {
    int languageMsgNum;
    int unused;
    int msgNum;
    int msgBank;

    FakemonDexSelectSpecies(species);
    if (IsFakemonSpecies(species)) {
        return ov18_021E5A10(ZUKAN_FLAVOR_GMM, species + FAKEMON_COUNT * sFakemonDexPage, heapId);
    }
    ov18_021E5A50(species, language, &languageMsgNum, &unused, &msgNum);
    if (msgNum == DEX_LANGUAGE_FLAG_MAX) {
        GF_ASSERT(a2 < 1);
        msgNum = species + a2;
        msgBank = ZUKAN_FLAVOR_GMM;
    } else {
        int msgBanks[6];
        ARRAY_ASSIGN(msgBanks, ov18_021F9724);

        GF_ASSERT(a2 < 1);
        msgBank = msgBanks[msgNum];
        msgNum = languageMsgNum + a2;
    }
    return ov18_021E5A10(msgBank, msgNum, heapId);
}

static String *ov18_021E5A10(int msgBank, int msgNum, enum HeapID heapId) {
    MsgData *msgData = NewMsgDataFromNarc(MSGDATA_LOAD_LAZY, NARC_msgdata_msg, msgBank, heapId);
    if (msgData != NULL) {
        String *ret = String_New(256, heapId);
        if (ret != NULL) {
            ReadMsgDataIntoString(msgData, msgNum, ret);
        }
        DestroyMsgData(msgData);
        return ret;
    }

    return NULL;
}

static inline int ov18_021E5A50_sub(int languageFlag) {
    GF_ASSERT(languageFlag < DEX_LANGUAGE_FLAG_MAX);
    if (languageFlag == DEX_LANGUAGE_FLAG_NATIVE) {
        languageFlag = DEX_LANGUAGE_FLAG_MAX;
    }
    return languageFlag;
}

static inline BOOL ov18_021E5A50_sub2(int species, int languageFlag) {
    if (species > MAX_SPECIES && languageFlag != DEX_LANGUAGE_FLAG_MAX) {
        return FALSE;
    } else {
        return TRUE;
    }
}

static void ov18_021E5A50(u16 species, int language, int *pMsgNo, int *pLanguageFlag, int *pLanguageFlagNativeMask) {
    *pLanguageFlag = LanguageToDexFlag(language);
    GF_ASSERT(*pLanguageFlag < DEX_LANGUAGE_FLAG_MAX);
    *pMsgNo = species;
    *pLanguageFlagNativeMask = IsFakemonSpecies(species) ? DEX_LANGUAGE_FLAG_MAX : ov18_021E5A50_sub(*pLanguageFlag);
    GF_ASSERT(ov18_021E5A50_sub2(*pMsgNo, *pLanguageFlagNativeMask));
}

// Keep the stock overlay ABI and the 518-row display allocation intact.
typedef char FakemonDexListOffsetCheck[(offsetof(PokedexAppData, unk_0878) == 0x1910) ? 1 : -1];
typedef char FakemonDexRowsOffsetCheck[(offsetof(PokedexAppData, unk_1030) == 0x1030) ? 1 : -1];
typedef char FakemonDexListCountOffsetCheck[(offsetof(PokedexAppData_UnkSub0878, unk_7B4) == 0x7E0) ? 1 : -1];

void FakemonDexResetPage(void) {
    sFakemonDexPageSpecies = SPECIES_NONE;
    sFakemonDexPage = 0;
}

void FakemonDexSelectSpecies(u16 species) {
    if (sFakemonDexPageSpecies != species) {
        sFakemonDexPageSpecies = species;
        sFakemonDexPage = 0;
    }
}

BOOL FakemonDexCyclePage(u16 species) {
    if (!IsFakemonSpecies(species)) return FALSE;
    FakemonDexSelectSpecies(species);
    sFakemonDexPage = (sFakemonDexPage + 1) % sFakemonDexPageCounts[species - SPECIES_VOLTUFF];
    return TRUE;
}

void ov18_021F8884(PokedexAppData *app, int numbered) {
    u32 i;
    MI_CpuClear32(app->unk_1030, sizeof(app->unk_1030));
    for (i = 0; i < app->unk_0878.unk_7B4; i++) {
        u16 species = app->unk_0878.unk_000[i][0];
        u32 row = numbered == 1 ? FakemonDexDisplayNumber(app->unk_1858, species) - 1 : i + 1;
        GF_ASSERT(row < NELEMS(app->unk_1030));
        if (row < NELEMS(app->unk_1030)) {
            app->unk_1030[row].unk_0 = species;
            app->unk_1030[row].unk_2 = app->unk_0878.unk_000[i][1];
        }
    }
}

void ov18_021F7ED4_Stock(PokedexAppData *app, u8 national, u32 order, u32 letter, u32 type1, u32 type2, u32 hmin, u32 hmax, u32 wmin, u32 wmax, u32 area, u32 body);

static BOOL FakemonDexMatchesType(u16 species, u32 type) {
    if (type == DEX_SEARCH_TYPE_ALL) return TRUE;
    if (type >= 9) type++; // The type picker omits the unused Mystery type.
    return GetMonBaseStat(species, BASE_TYPE1) == type || GetMonBaseStat(species, BASE_TYPE2) == type;
}

static BOOL FakemonDexSortBefore(PokedexAppData *app, u16 first, u16 second, u32 order) {
    u32 a, b;
    if (order == DEX_ORDER_ALPHABETICAL) {
        String *left = GetSpeciesName(first, HEAP_ID_POKEDEX_APP);
        String *right = GetSpeciesName(second, HEAP_ID_POKEDEX_APP);
        const u16 *l = String_cstr(left);
        const u16 *r = String_cstr(right);
        BOOL before;
        for (;;) {
            u16 lc = *l++;
            u16 rc = *r++;
            if (lc >= CHAR_a && lc <= CHAR_z) lc -= CHAR_a - CHAR_A;
            if (rc >= CHAR_a && rc <= CHAR_z) rc -= CHAR_a - CHAR_A;
            if (lc == EOS || rc == EOS || lc != rc) {
                before = lc == EOS ? rc != EOS : (rc != EOS && lc < rc);
                break;
            }
        }
        String_Delete(left);
        String_Delete(right);
        return before;
    }
    if (order == DEX_ORDER_HEAVIEST || order == DEX_ORDER_LIGHTEST) {
        a = ((u32 *)app->weights)[first];
        b = ((u32 *)app->weights)[second];
        if (a != b) return order == DEX_ORDER_HEAVIEST ? a > b : a < b;
    } else if (order == DEX_ORDER_TALLEST || order == DEX_ORDER_SHORTEST) {
        a = ((u32 *)app->heights)[first];
        b = ((u32 *)app->heights)[second];
        if (a != b) return order == DEX_ORDER_TALLEST ? a > b : a < b;
    }
    return FakemonDexDisplayNumber(TRUE, first) < FakemonDexDisplayNumber(TRUE, second);
}

void ov18_021F7ED4(PokedexAppData *app, u8 national, u32 order, u32 letter, u32 type1, u32 type2, u32 hmin, u32 hmax, u32 wmin, u32 wmax, u32 area, u32 body) {
    u16 species;
    ov18_021F7ED4_Stock(app, national, order, letter, type1, type2, hmin, hmax, wmin, wmax, area, body);
    // The additions have no Johto slots, encounters, or regional completion requirements.
    if (!national || order == DEX_ORDER_JOHTO) return;
    for (species = SPECIES_VOLTUFF; species <= SPECIES_RAGNAROC; species++) {
        BOOL caught;
        u32 count, pos;
        if (!Pokedex_CheckMonSeenFlag(app->args->pokedex, species)) continue;
        caught = Pokedex_CheckMonCaughtFlag(app->args->pokedex, species);
        if (!FakemonDexMatchesType(species, type1) || !FakemonDexMatchesType(species, type2)) continue;
        if (body != DEX_SEARCH_BODYTYPE_ALL && app->unk_1854[species] != body) continue;
        if (!(area & ((1 << DEX_SEARCH_AREA_ALL) | (1 << DEX_SEARCH_AREA_UNKNOWN)))) continue;
        if (letter != DEX_SEARCH_LETTERS_ALL) {
            String *name = GetSpeciesName(species, HEAP_ID_POKEDEX_APP);
            u16 initial = String_cstr(name)[0];
            String_Delete(name);
            if (initial != CHAR_A + letter) continue;
        }
        if (hmin != 0 || hmax != 152) {
            u32 height = ((u32 *)app->heights)[species];
            if (!caught || height < app->unk_1850[hmin].unk_0 || height > app->unk_1850[hmax].unk_0) continue;
        }
        if (wmin != 0 || wmax != 152) {
            u32 weight = ((u32 *)app->weights)[species];
            if (!caught || weight < app->unk_1850[wmin].unk_2 || weight > app->unk_1850[wmax].unk_2) continue;
        }
        if (order >= DEX_ORDER_HEAVIEST && !caught) continue;
        count = app->unk_0878.unk_7B4;
        GF_ASSERT(count < NELEMS(app->unk_0878.unk_000));
        if (count >= NELEMS(app->unk_0878.unk_000)) continue;
        pos = count;
        while (pos && FakemonDexSortBefore(app, species, app->unk_0878.unk_000[pos - 1][0], order)) {
            app->unk_0878.unk_000[pos][0] = app->unk_0878.unk_000[pos - 1][0];
            app->unk_0878.unk_000[pos][1] = app->unk_0878.unk_000[pos - 1][1];
            pos--;
        }
        app->unk_0878.unk_000[pos][0] = species;
        app->unk_0878.unk_000[pos][1] = caught ? 2 : 1;
        app->unk_0878.unk_7B4++;
        if (caught) app->unk_0878.unk_7B6++;
    }
}
