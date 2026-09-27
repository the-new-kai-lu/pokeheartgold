# Candidate episode: Emerald's Birch rescue (gift foundation; episode not imported)

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

## Episode transaction and safety gates (caller not implemented)

Use separate rescue-completed and gift-received states, with **no reuse of
Elm's starter flag or `SetStarterChoice`**. Preserve all existing party members,
badges, story flags, following Pokémon, and save partition layout. A full
party must NOT block the rescue. The earlier free-party-slot rescue fallback
is rejected. Rescue completion unlocks the lab aftermath and onward/return
travel independently of reward delivery.

At the lab, let the player choose Treecko, Torchic, or Mudkip. Proposed delivery
result contract (delivery results implemented; episode states not allocated):

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

The dedicated `GiveMonToPartyOrPC` command is appended at **853 (0x355)**;
existing indices 0–852 are unchanged. The table and decompiler had 853
entries (including `UnsetPhoneCallTrigger`, whose name lacks `ScrCmd_`).
`src/script.c` reads an unsigned 16-bit opcode and checks the context's
32-bit count; `src/script_manager.c` supplies the table's `NELEMS` count,
now 854. No dispatcher limit, save layout, or existing command is changed.
The header, macro, and decompiler metadata use the same six halfword operands
as `GiveMon`: species, level, held item, form, ability, result variable.
Variable resolution and level/form/ability narrowing match that command.
Trusted scripts must supply valid species, levels, forms, items and variables;
this is not an untrusted-bytecode validator.

`GiveMonToPartyOrPC` constructs the gift with the existing met-data/OT
routine, tries the party, then the PC, and updates the Pokédex only after
successful insertion. It returns `GIVE_MON_NO_SPACE` (0), `GIVE_MON_PARTY`
(1), or `GIVE_MON_PC` (2). A full-storage preflight avoids creating a random
Pokémon when no space exists; insertion success remains authoritative.
It does not set any story flag or save the game. Every successful invocation
creates a gift: the caller must guard against duplicate collection.
`PCStorage_PlaceMonInFirstEmptySlotInAnyBox`
(`src/pokemon_storage_system.c:54-68`) scans from the active box, wraps,
restores PP and returns FALSE if all boxes are occupied. Its success result
does not report a destination box; that needs explicit handling for the UI.
The current result supports a generic "sent to your PC" message, not a box name.

Caller template (pseudocode; intentionally no invented story IDs):

```text
if not rescue_completed or gift_received: show appropriate dialogue; return
offer/restore pending Hoenn species; if cancelled: return
GiveMonToPartyOrPC chosen_species, 5, ITEM_NONE, 0, 0, scratch_result
if scratch_result == GIVE_MON_NO_SPACE: retain eligibility; explain space; return
if scratch_result == GIVE_MON_PARTY or scratch_result == GIVE_MON_PC:
    set gift_received immediately, before yielding to dialogue/save/UI
    show party/PC receipt message
```

`tests/test_gift_delivery.py` compiles and executes the production helper and
script adapter with bounded party/PC API doubles. It covers party preference,
last party/PC slot, total-full no-op, retry, metadata, default/override ability,
balanced allocation and unchanged legacy `GiveMon`. It also assembles the
actual macro, decodes it with the repository parser, and reassembles identical
bytes. These are host logic/tooling tests, not encrypted-save or ARM runtime
tests. No episode caller, selection UI, state allocation or map import exists.

This extension changes ROM code, so retail SHA-1 matching is no longer a valid
gate for the current expanded tree. The retail hashes remain unchanged as
baseline evidence; do not regenerate them to bless an expanded ROM. Build
the extension with `make COMPARE=0` and `make soulsilver COMPARE=0`, then run
the pending manual tests. The owner changed CI to `COMPARE=0` in
`7411b88312b838c9fc2d61797322568d1c611bc2`; that workflow change is preserved.

## Persistent-state allocation gate (implemented inventory, no allocation)

`scripts/audit_expansion_state.py` inventories candidate **variable** IDs
without reserving them. Example (the two IDs below are probes, NOT Birch IDs):

```sh
python3 scripts/audit_expansion_state.py \
  --candidate 0x416e --candidate 0x416f --output /tmp/state-audit.json
```

The initial scan covered 4,752 tracked source/header/assembly/event-JSON files
and identified 965 expected compiled script banks per edition. Neither probe
had a literal/alias use outside definitions in that scan. **This is not proof
they are free.** No local compiled script banks were available, so coverage
of both HG and SS binaries remains missing. Source branches for both editions
are scanned together, not treated as a substitute for compiled variants.

Supply independently built directories with `--heartgold <HG-scr_seq-dir>`
and `--soulsilver <SS-scr_seq-dir>` to inventory every byte offset for candidate
halfwords (including odd offsets), record SHA-256 fingerprints, and detect
missing, empty and unexpected banks. Do not pass the same/stale directory as
both editions. Byte matches are conservative evidence, not decoded references.
This does not require ROM uploads or store ROM/save data in Git.

The report always says `allocation_approved: false`. Exit 1 means an observed
reference; exit 2 means no literal reference was found but manual/dataflow
review is still required. The test suite verifies that even complete
literal-free binary fixtures cannot authorize an allocation.

Concrete remaining review paths:

- `src/save_vars_flags.c:57-59` indexes the persistent array using a runtime
  variable ID, so no symbolic name is necessary for a reference.
- `src/script_manager.c` routes IDs through `GetVarPointer`/`FieldSystem_VarGet`
  and resets map-temporary variables through an indexed loop. Range/alias
  reasoning is required in addition to literal scanning.
- `src/sys_vars.c:22-42` wraps reads/writes with runtime `var_id` parameters.
  Its callers and native/assembly accesses are listed in the report for review.
- `src/scrcmd_c.c` supports variable-selected flag checks/sets/clears; reserving
  a flag based solely on its absence in constant operands would be unsafe.
- Incoming existing saves, event/mystery-gift scripts, and opaque assets need
  explicit compatibility policy/review; unknown variables are not promised
  zero on all existing saves.

Accordingly no state constants, live lab script, archive entry or vanilla NPC
were changed in this checkpoint. The duplicate guard and deferred-choice
transaction cannot be integrated safely until that allocation is reviewed.
The gift helper itself was checked against existing party/PC APIs; no new
defect requiring a change was established in this audit.

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