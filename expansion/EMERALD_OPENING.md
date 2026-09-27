# Candidate episode: Emerald's Birch rescue (design audit only)

The owner selected **Emerald** for Hoenn and **Platinum** for Sinnoh. This
candidate uses pret/pokeemerald at `c925b8482d05fb882d6b64e523653cae599e025f`;
the future Sinnoh audit is pinned to pret/pokeplatinum at
`c248fb3f8cc9934ded800e489567c5c0eeee92eb`. The HGSS host checkpoint
audited here is `f699b3c01b769f95c07e7d802dd5b7369bb142b2`. These are
**audit revisions**, not imported assets or a change to the original source
pins in `baseline.json`.

## Minimum recognizable flow and evidence

Approved first slice: reach Littleroot, witness Birch pursued on Route 101,
**fight the rescue battle with the existing Johto party**, then return to
Birch's Lab to choose and receive a Hoenn starter. Leave and revisit without
resetting Johto progress. The original Emerald bag-selection flow below is
donor evidence, not the approved reward timing.
Emerald's `data/maps/LittlerootTown/scripts.inc` and
`data/maps/Route101/scripts.inc:19-65,214-239` control rescue setup, exit
blocking, bag interaction, object visibility, route state, and lab warp.
`data/maps/LittlerootTown_ProfessorBirchsLab/scripts.inc:98-142` handles
the lab follow-up; `data/scripts/prof_birch.inc:1-33` governs Birch's later
locations. `src/battle_setup.c:911-953` proves `ChooseStarter` grants a
level-5 Pokémon **and launches `BATTLE_TYPE_FIRST_BATTLE`** via a C callback;
the battle is not a mere scripted chase. The donor's `FLAG_RESCUED_BIRCH`,
`VAR_ROUTE101_STATE`, and `VAR_BIRCH_LAB_STATE` are story semantics, not
numbers to copy into HGSS.

The owner wants the existing Johto party and progress retained **plus** a
Hoenn starter. The HGSS Elm starter path is *not reusable as-is*:
`files/fielddata/script/scr_seq/scr_seq_0843_T20R0101.s:164-213` calls
`ChooseStarter`, sets global `FLAG_GOT_STARTER`, then assumes the new
starter occupies party slot 0 (`GetPartyMonSpecies 0`) and overwrites the
Johto starter choice (`SetStarterChoice`). `src/choose_starter.c:44-84`
hardcodes Chikorita/Cyndaquil/Totodile, tries `Party_AddMon`, ignores a
full-party failure, and marks slot 0 as caught. Do not call this flow for
Birch or change Elm's flag/starter choice.

HGSS `src/scrcmd_party.c:19-34` exposes `GiveMon`'s success result to a
script; `src/script_pokemon_util.c:21-47` creates a Pokémon, tries
`Party_AddMon`, and updates the Pokédex only on success.
`src/party.c:46-53` rejects an occupied party without overwriting it.
`src/pokemon_storage_system.c:54-72,126-141` has an existing first-empty
PC-box placement API and a no-space result, but `GiveMon` does **not**
automatically deposit gifts in the PC. A full party cannot be treated as
successful delivery. The vanilla catch path in
`src/battle/battle_command.c:6990-7030` demonstrates PC storage for
captured Pokémon, not a tested gift transaction.

## Proposed transaction and safety gates (not implemented)

Use separate rescue-completed and gift-received states, with **no reuse of
Elm's starter flag or `SetStarterChoice`**. Preserve all existing party members,
badges, story flags, following Pokémon, and save partition layout. A full
party must NOT block the rescue. The earlier free-party-slot rescue fallback
is rejected. Rescue completion unlocks the lab aftermath and onward/return
travel independently of reward delivery.

At the lab, let the player choose Treecko, Torchic, or Mudkip. Proposed delivery
result contract (semantic names, not allocated opcode/result IDs):

| Outcome | Required behavior |
| --- | --- |
| PARTY | Append to party; leave existing slots unchanged; record receipt once |
| PC | Party full: deposit in an empty PC slot; report destination; record receipt once |
| NO_SPACE | Party and all boxes full: Birch retains the reward; no receipt, overwrite, or story lock |
| Cancel | No grant and no receipt; return to the offer later |
| Already received | Dialogue only; never create another starter |

Receipt must follow a successful insertion, not a capacity prediction. Set
Pokédex ownership only after insertion. Retain a pending chosen species on
NO_SPACE; retry must not reroll an already-created Pokémon or duplicate one.
The exact choice/receipt encoding, creation timing, and whether pending gifts
need a Pokémon object must be resolved within existing audited save storage;
no new save block or raw donor flag numbers are authorized. Avoid an asynchronous
save/UI boundary between insertion and receipt. Test save/reload at every
reachable boundary; do not call this transaction atomic without runtime evidence.

The rescue battle uses HGSS battle startup/return plumbing with the existing
party, not Emerald's callback that grants a starter before fighting. A loss
or blackout must not award rescue completion or a starter; retry behavior and
safe return position need explicit HG/SS tests. Johto starter selection remains
untouched. Link the route, lab, and Johto return
with verified bidirectional warps, collision, NPC movement and persistent
Birch placement. Allocate event IDs only after auditing all compiled
scripts/assembly and both game versions; a symbolic gap is not proof of a
free slot. Inventory maps, tilesets, scripts, text, music, trainers,
encounters, species and asset provenance before porting. No donor resource,
game script, save migration, or executable episode is included here.

Test both HG and SS with one and six party members, the last free PC slot,
full PC, selection cancellation, repeated interaction, battle loss/retry,
save/reload before and after receipt, deferred collection after freeing space, return
to Johto and revisit, plus PKHeX and PKMDS export/edit/reopen on disposable
real saves. CI's matching vanilla ROMs do not establish those behaviors.

## Integration boundary: do not repurpose existing opcodes

`ScrCmd_GiveMon` (`src/scrcmd_party.c:19-34`) has an existing operand layout
and Boolean return. Changing failure into successful PC delivery globally
would change every existing caller's assumptions about party indices.
Keep it unchanged. The superficially relevant `ScrCmd_510`
(`src/scrcmd_12.c:57-75`) is Pal Park's six-migrant deposit: it asserts
insertion, clears migration data and has no per-gift no-space result.
It is used by `scr_seq_0812_T08R0201.s` and cannot become Birch's opcode.

An eventual dedicated command needs coordinated review of
`src/data/fieldmap/script_cmd_table.h`, `include/scrcmd.h`,
`asm/macros/script.inc`, and `tools/py_scripts/scrcmd.json`, plus an actual
episode caller and runtime tests. No unused ID has been proven safe here.
Therefore this checkpoint adds no uncallable C helper, opcode, global gift
behavior change, or story ID. PC insertion exists, but integration is not yet
implemented. `PCStorage_PlaceMonInFirstEmptySlotInAnyBox`
(`src/pokemon_storage_system.c:54-68`) scans from the active box, wraps,
restores PP and returns FALSE if all boxes are occupied. Its success result
does not report a destination box; that needs explicit handling for the UI.

## Three-map resource inventory

Source: each map's `data/maps/<name>/map.json` and
`data/layouts/layouts.json` at the Emerald audit revision above. Counts include
donor events that must be omitted or adapted, not a proposed HGSS allocation.

| Map | GBA layout dimensions | Objects / warps / coordinate / background events | Tilesets | Music |
| --- | --- | --- | --- | --- |
| LittlerootTown | 20 x 20 | 8 / 3 / 9 / 4 | General + Petalburg | MUS_LITTLEROOT |
| Route101 | 20 x 20 | 6 / 0 / 9 / 1 | General + Petalburg | MUS_ROUTE101 |
| LittlerootTown_ProfessorBirchsLab | 13 x 13 | 6 / 2 / 0 / 15 | Building + Lab | MUS_BIRCH_LAB |

Each layout references `data/layouts/<name>/{map,border}.bin`; these are
GBA metatile data, not DS geometry. Town connects north to Route 101;
Route 101 connects north to Oldale and south to town. Town's three warps
lead to May's house, Brendan's house, and the lab. The lab's two exit tiles
both target town warp 2. **The three maps are not a closed import unit**:
Oldale and the two houses require explicit boundary handling or additional
resources. Do not leave dangling warps or pretend those interiors were imported.
The Johto arrival/return connection is new and is not specified by donor data.

Required object graphics include Birch, his bag, Zigzagoon, the town truck,
mother, twin, fat man, boy, youngster, scientist, item balls and variable
rival graphics. The lab's item balls/hide flags include Emerald's postgame
Johto-starter gifts; exclude that subsystem rather than importing it into
Birch's new Hoenn-starter reward. Likewise audit the moving-truck/new-game
and rival callbacks before retaining town initialization scripts.

DS integration needs map headers and IDs; matrix/land data, geometry,
textures, collision and movement permissions; zone-event objects/triggers/warps;
script banks and message banks; NPC sprite resources; music mapping;
encounter/battle configuration; and map-section/region presentation.
Use `src/data/map_headers.h`, `files/fielddata/mapmatrix`,
`files/fielddata/eventdata/zone_event`,
`files/fielddata/script/scr_seq` and `files/msgdata` as host entry points.
Route 101's ordinary encounter data is in
`src/data/wild_encounters.json`; the rescue first-battle setup is separate.
Do not substitute a vanilla Johto map's name or copy GBA coordinates directly.