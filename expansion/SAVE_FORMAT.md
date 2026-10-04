# Expanded save contract

Policy revision 2, approved by the owner on 2026-09-30. This is a requirements
change, **not a claim that a new binary save format is implemented**.

## Supported contract

Expanded saves must work with the expanded game and the project's PKHeX and
PKMDS forks. They need not retain an unchanged vanilla HGSS byte layout or work
with unmodified upstream editors.

Reliable in-game saving remains required. Additional Hoenn and Sinnoh campaign
state must survive save/load, cold restart, region travel, and ordinary edits
through the supported editor forks. Changing an unrelated Pokémon field must
not erase campaign progress.

This supersedes the unchanged-layout requirement and the historical stock-save
compatibility matrix in `README.md`. The overall Emerald/Platinum expansion
remains later work; the owner subsequently limited Stage 1 to the foundation
and one playable imported episode. See [the current milestone](STAGE1.md).
Neither policy change by itself establishes Stage 1 completion.

## Format design requirements

- Give expansion state an explicit allocation and detectable schema version.
  Do not treat unnamed variables, padding, or an apparent gap as free storage.
- Preserve the standard Pokémon record format where practical. New campaign
  state does not by itself require a different Pokémon codec.
- Prefer shared format handling in the PKHeX.Core fork consumed by both editor
  frontends. Keep existing vanilla parsing separate from expanded-format parsing.
- Define block boundaries, bounds checks, checksums, backup selection, and
  initialization for each supported version. An unsupported version must not
  silently be interpreted, overwritten, or initialized as a supported one.
- Preserve extension data during unrelated editor operations. Reject an
  unsupported format rather than export a file with missing campaign state.
- Keep original saves untouched when a migration is needed. Vanilla import and
  export back to stock games are optional features, not Stage 1 prerequisites.

Stock games and editors may not safely handle the expanded format. Supported
builds and tools must identify that limitation clearly; do not advertise expanded
saves as vanilla-compatible.

## Focused validation

1. Use a representative game-created save containing campaign progress and
   Pokémon in both the party and PC. Save normally, cold-load it, and check the
   recorded progress and Pokémon.
2. Use each supported editor frontend for a representative unrelated edit.
   Reopen its actual output, load it in the game, and verify the requested edit
   and preservation of campaign state and unrelated Pokémon data.
3. Save that result in-game and cold-load it again. Exercise the relevant
   campaign transition or return journey, not just the title screen.
4. Test version detection, malformed lengths, unsupported versions, checksum
   failure, and backup recovery in focused automated tests. Label synthetic
   fixtures as synthetic; they are not evidence of native gameplay.

Cover HeartGold and SoulSilver before claiming support for both. Reuse passing
evidence while the relevant code and inputs remain unchanged; a new map or
dialogue does not automatically require another complete stock-game playthrough.
When editor outputs are identical, a shared native read-back may cover those
bytes if the record explicitly says so. Each frontend's actual import/edit/export
path still needs its own evidence.

Baseline layout checks remain useful regression tests for the existing default
build. A future expanded layout needs its own reviewed, version-specific checks;
do not silently repin old baselines or remove corruption checks to make it pass.

## Immediate priority

Finish the bounded Emerald opening through Oldale and the return/revisit loop;
subsequent regional story progression is outside Stage 1. Use the existing
versioned allocation where needed. Do not change the format merely to
demonstrate that changing it is allowed, and do not block the episode on further
unchanged-vanilla-format compatibility cases. Reuse passing checks when the
relevant code and inputs have not changed.

The first opt-in implementation is described in
[campaign-state format v1](CAMPAIGN_SAVE_V1.md). Its source and host tests do not
enable it in the tested Oldale build or constitute native-runtime acceptance.