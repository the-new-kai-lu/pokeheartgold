# Candidate episode: Emerald's Birch rescue (design audit only)

The owner selected **Emerald** for Hoenn and **Platinum** for Sinnoh. This
candidate uses pret/pokeemerald at `c925b8482d05fb882d6b64e523653cae599e025f`;
the future Sinnoh audit is pinned to pret/pokeplatinum at
`c248fb3f8cc9934ded800e489567c5c0eeee92eb`. The HGSS host checkpoint
audited here is `f699b3c01b769f95c07e7d802dd5b7369bb142b2`. These are
**audit revisions**, not imported assets or a change to the original source
pins in `baseline.json`.

## Minimum recognizable flow and evidence

Proposed first slice: reach Littleroot, witness Birch pursued on Route 101,
interact with his bag, select a Hoenn starter, **fight the rescue battle**,
return to Birch's Lab for acknowledgment/nickname, then leave and revisit.
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

Use a separate Hoenn episode state and choice, with **no reuse of Elm's
starter flag or `SetStarterChoice`**. Preserve all existing party members,
badges, story flags, following Pokémon, and save partition layout. Check
party space before any irreversible starter grant or rescue battle. Safest
first implementation: if all six slots are occupied, stop before the bag
selection/battle and ask the player to free a party slot at a PC; leave the
scene retryable. This is a deliberate full-party fallback, **not** a claim
that direct-to-PC gifts already work. If the episode later requires a
full-party award, implement and test a separate verified PC-space check,
deposit path and receipt. If party and boxes are both full, defer the
reward without clearing eligibility or overwriting a Pokémon.

On confirmed successful delivery, persist a distinct Hoenn-starter
received state and chosen species exactly once; a repeated bag interaction
must not duplicate the gift. The rescue battle must use HGSS's battle
startup/return plumbing and continue to lab only after its outcome is
handled. Define behavior on blackout, interrupted selection, and reload
before implementing; never set the completion/visibility flags before
receipt and battle outcome are safe. Link the route, lab, and Johto return
with verified bidirectional warps, collision, NPC movement and persistent
Birch placement. Allocate event IDs only after auditing all compiled
scripts/assembly and both game versions; a symbolic gap is not proof of a
free slot. Inventory maps, tilesets, scripts, text, music, trainers,
encounters, species and asset provenance before porting. No donor resource,
game script, save migration, or executable episode is included here.

Test both HG and SS with one and six party members, full PC, repeated
interaction, battle loss/retry, save/reload before and after receipt, return
to Johto and revisit, plus PKHeX and PKMDS export/edit/reopen on disposable
real saves. CI's matching vanilla ROMs do not establish those behaviors.