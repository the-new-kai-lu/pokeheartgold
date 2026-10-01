#ifndef POKEHEARTGOLD_SAVE_CAMPAIGN_H
#define POKEHEARTGOLD_SAVE_CAMPAIGN_H

#include "global.h"

#include "save.h"

#define CAMPAIGN_BYTES                   2048
#define CAMPAIGN_HEADER_BYTES            32
#define CAMPAIGN_VERSION                 1
#define CAMPAIGN_EXTENSION_OFFSET        0xF614
#define CAMPAIGN_GENERAL_BYTES           0xFE28
#define CAMPAIGN_LEGACY_GENERAL_BYTES    0xF628
#define CAMPAIGN_MAIN_BYTES              0x23000
#define LOAD_STATUS_UNSUPPORTED_CAMPAIGN 4

enum CampaignRegion {
    CAMPAIGN_HOENN = 0,
    CAMPAIGN_SINNOH = 1
};

/* Byte fields make the on-disk offsets independent of host alignment/endian. */
typedef struct CampaignSave {
    u8 magic[8];
    u8 version[2];
    u8 length[2];
    u8 headerSize[2];
    u8 opaqueHeader[18];
    u8 hoennVars[512];
    u8 hoennFlags[300];
    u8 sinnohVars[576];
    u8 sinnohFlags[364];
    u8 reserved[264];
} CampaignSave;

enum CampaignPartitionFormat {
    CAMPAIGN_PARTITION_BLANK,
    CAMPAIGN_PARTITION_CORRUPT,
    CAMPAIGN_PARTITION_SUPPORTED,
    CAMPAIGN_PARTITION_LEGACY,
    CAMPAIGN_PARTITION_UNSUPPORTED
};

/* Initialization is explicit; validation/getters never repair a header. */
void CampaignSave_Init(CampaignSave *state);
BOOL CampaignSave_HeaderSupported(const CampaignSave *state);
BOOL CampaignSave_GetVar(const CampaignSave *state, u32 region, u32 id, u16 *value);
BOOL CampaignSave_SetVar(CampaignSave *state, u32 region, u32 id, u16 value);
/* Flag zero is the donor sentinel: valid read FALSE, writes are no-ops. */
BOOL CampaignSave_GetFlag(const CampaignSave *state, u32 region, u32 id, BOOL *value);
BOOL CampaignSave_SetFlag(CampaignSave *state, u32 region, u32 id, BOOL value);

u32 Save_TrainerHouseCampaign_sizeof(void);
void Save_TrainerHouseCampaign_Init(void *data);
CampaignSave *Save_Campaign_Get(SaveData *saveData);
const CampaignSave *Save_Campaign_Const_Get(const SaveData *saveData);

/* Call only on a successful flash read, before the read buffer is freed. */
enum CampaignPartitionFormat CampaignSave_ClassifyPartition(const void *data, u32 size);

#endif // POKEHEARTGOLD_SAVE_CAMPAIGN_H
