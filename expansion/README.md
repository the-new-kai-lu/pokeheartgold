# ExpandedHeartGold — Stage 1 evidence

This remains **partial Stage 1 work, not a four-region ROM**. An opt-in
technical debug build adds a flat Birch-lab test map and starter interaction,
but it simulates the rescue and is not an imported playable Hoenn episode.
The default source build does not contain that debug map. No full Hoenn or
Sinnoh campaign, new save format, species, or battle mechanic is implemented.
The host is pokeheartgold; hg-engine is reference-only. The owner’s vision
v0.2 requires a complete imported episode and persistent return travel before
scaling to either full campaign.

## Reproduce the baseline

The appended gift command is the first executable extension; it does not
import an episode. The retail comparison commands below apply to the vanilla
checkpoint `f699b3c01b769f95c07e7d802dd5b7369bb142b2`, not this expanded tree.
For this tree use `make COMPARE=0` and `make soulsilver COMPARE=0`.
Retail hashes and save-layout tripwires remain unchanged. See
`EMERALD_OPENING.md` for the new command, host tests and remaining runtime gates.
`VALIDATION.md` records the private Ubuntu 22.04 VM recovery and one successful
debug HeartGold build, not a complete episode or SoulSilver debug build.

`baseline.json` records exact starting revisions, expected retail ROM hashes,
and SHA-256 hashes of the supplied toolchain archives. It is a baseline contract,
not a release manifest or claim that the pinned editors passed runtime tests.

Follow `INSTALL.md` for host dependencies and compiler placement. The repository's
`.devcontainer/setup-devcontainer.sh` uses NitroSDK **3.2**, matching the supplied
archive; `INSTALL.md` instead names 4.2. Do not silently substitute versions.
Install only the SDK `tools/bin` and three linker templates described there.
Keep archives, compiler binaries, licenses, ROMs, saves, and savestates out of Git.

```sh
export LM_LICENSE_FILE="$PWD/tools/mwccarm/license.dat"
python3 scripts/check_expansion_baseline.py
python3 -m unittest discover -s tests -v
make -j4 COMPARE=0
make soulsilver -j4 COMPARE=0
# Retail comparisons apply only to the pinned vanilla checkpoint.
# There, separately: make compare_heartgold && make compare_soulsilver
python3 scripts/check_expansion_baseline.py \
  --rom build/heartgold.us/pokeheartgold.us.nds --game heartgold
python3 scripts/check_expansion_baseline.py \
  --rom build/soulsilver.us/pokesoulsilver.us.nds --game soulsilver
```

The Python gate checks contiguous map IDs and header coverage, current region
assignments, and unchanged capacity/layout source anchors. Mutation tests ensure
the gate fails on representative drift. It does **not** parse arbitrary C,
validate every asset reference, prove free story IDs, measure RAM, or run scripts.
The layout hashes are deliberately conservative review tripwires, not a complete
save ABI proof. When a later stage changes this contract, review and version it
with editor migrations/tests rather than blindly regenerating expected values.
The owner installed the Actions workflow on the PR branch. The expansion
contract and upstream HG/SS matching-build jobs passed at
`f699b3c01b769f95c07e7d802dd5b7369bb142b2`; see `VALIDATION.md`.
This does not replace the manual ROM/editor loop below.

## Capacity audit and allocation policy

| Resource | Verified host representation | Stage 1 implication |
| --- | --- | --- |
| Maps | 540 headers, IDs 0–539; `MAP_ID_MAX` is exclusive | New maps require complete assets and updated consumers, not only constants |
| Region | One bit in `MapHeader.regionNo`; Johto/Kanto enum only | Writing 2/3 truncates; audit packed C/assembly ABI and every consumer first |
| Encounter bank | `u8 wildEncounterBank` | Audit both HG/SS encounter tables before extending |
| Map section | Eight-bit `mapsec`, independent of region | Existing Sinnoh section labels do not imply a playable Sinnoh |
| Story variables | 368 `u16` values starting at `0x4000` | Naming holes are not proof of unused storage |
| Persistent flags | 2912 bits; flag 0 is special | Audit compiled scripts and assembly as well as symbolic references |

Source entry points: `include/map_header.h`, `src/data/map_headers.h`,
`src/map_header.c`, `src/unk_0202F370.c`, `include/constants/{maps,vars,flags}.h`,
`include/save_vars_flags.h`, `src/save_vars_flags.c`. `pokemon_talk.c` loops over
all map IDs. Widening a bitfield can shift every following field; do not widen
`regionNo` in isolation.

No new IDs are reserved yet. The catalogue/import inventory starts empty
(`imported_episodes` in the manifest). Before importing, record donor repository
and commit, edition, original/new map/resource IDs, every flag/variable/trainer
remap, asset provenance, and any story omissions. The owner selected Emerald
and Platinum. `EMERALD_OPENING.md` audits the proposed first Birch-rescue
slice, not an import or a completed region. Do not replace recognizable plots
with generic gym sequences.

## Required manual ROM and editor loop

Run separately for HeartGold and SoulSilver, on **copies**, not a valuable save.
Record ROM SHA-1, game/editor commits, emulator version, platform, and settings.
Use native in-game battery saves; savestates alone do not establish persistence.

1. Boot the matching baseline ROM. Start a disposable game, obtain a starter,
   complete a battle, capture another Pokémon, and reach a PC.
2. Put one Pokémon in the PC and retain another in the party. Record species,
   nickname, level/EXP, ability, moves/PP, held item, trainer IDs, money, location,
   and a recently completed story event.
3. Save in-game twice, close the emulator fully, and back up the raw 512 KiB
   `.sav`. DeSmuME `.dsv` contains emulator metadata: export raw backup memory
   rather than renaming/truncating files.
4. Open a copy in the pinned PKHeX fork. Verify it is vanilla HGSS, **not**
   hg-engine; no custom-species profile should be selected. Export without edits
   to a different filename. Reopen, load in game, and verify party, PC and story.
5. Repeat with a fresh original copy in PKMDS built against the same PKHeX.Core
   checkout. Never test two different Core versions while calling them equivalent.
6. In each editor separately, change only a nickname on a copy. Reopen in the
   editor, then load in game; verify the edit, unrelated party/box data, money,
   location and story. Save in-game, cold restart, then inspect the new save in
   both editors. Keep before/after files locally with hashes.
7. Verify ordinary Johto/Kanto travel and return once available. For Stage 1B,
   additionally execute the actual imported episode: exterior/interior travel,
   NPC interaction, battle, story transition, aftermath, return to Johto, save,
   cold restart, revisit. Debug state setup must not bypass the tested trigger.

Classify results separately: source checks, matching build, synthetic serializer
tests, game/editor loop, visual review, hardware test. Do not claim a region or
save format is supported from synthetic tests or a title-screen boot alone.
Expanded-ROM legality checks will need an explicit project policy later.

## Next gate

Finish the selected episode's resource, story-ID and battle/return-state audit.
Then implement a reproducible import and test it alongside
one high-risk scene/traversal mechanic. Keep stock save storage until an explicit
capacity requirement justifies a migration. Stage 1 completion still requires
the full chosen campaigns and a documented end-to-end completion record.