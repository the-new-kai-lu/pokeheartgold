# Stage 1: regional campaign integration

**Status: in progress. The foundation / opening-episode checkpoint is complete;
the full regional import is not.**

The owner has resumed the original Stage 1 roadmap and selected **all of Hoenn,
using Emerald as the donor**, as the next import target. The previously accepted
foundation-plus-one-episode scope is a completed checkpoint (approximately
original stages 1A/1B), not completion of the original full Stage 1.

The original roadmap puts regional campaign integration in Stage 1, meaningful
progression and a limited advanced-form experiment in Stage 2, broader playtest
and production validation in Stage 3, and scale/polish in Stage 4. It does not
assign a new unified storyline to Stage 3 or 4. Preserve the regional stories;
do not substitute a generic sequence of gyms.

## Current work: bulk Hoenn import

Generalize the opening's conversion process and apply it to the region rather
than individually certifying every map. Include a coverage report separating
converted resources from unsupported scripts, mechanics and dynamic state.
Compilation is a build check, not evidence that a story event works.

The owner and friends will perform the broad gameplay testing. The delivery
gate is focused importer checks, reference/resource-bound validation, and a
successful HeartGold ROM build. Reuse the small-scale checks whose relevant
inputs are unchanged; do not repeat a full gameplay, editor, edition or hardware
matrix. An unimplemented conversion is an implementation gap, not merely an
untested feature, and must be named as such.

Sinnoh/Platinum remains part of the original roadmap, but is not part of this
Hoenn batch. Stage 2 is not started by this work.

## Completed opening checkpoint

The opt-in HeartGold prototype below is the retained regression checkpoint,
not a four-region release or a polished town. See its
[build and play guide](STAGE1_GUIDE.md).

## Episode boundary

The completed checkpoint covers:

- Enter Hoenn from Johto using the documented prototype travel entrance.
- Traverse Littleroot, Birch's lab and Route 101; complete the actual rescue
  battle and receive one Hoenn starter.
- Reach Oldale's exterior and complete the existing one-time Potion interaction.
- Return to Johto and revisit without losing earned progress or duplicating
  rewards. Native saving and cold Continue must preserve that progress.

The prototype entrance is not the final integrated-story travel system.
Oldale interiors, Routes 102/103, the rival sequence, gyms and the remainder of
Emerald/Platinum are outside that completed checkpoint. They are not implicitly
implemented by its passing results.

## Foundation

Use the explicitly allocated, versioned expanded-save format and the project's
PKHeX/PKMDS forks. Preserve ordinary Pokemon data and saved episode progress.
Vanilla-layout compatibility and unmodified upstream-editor compatibility are
not requirements; see [the save contract](SAVE_FORMAT.md).

Deliver reproducible source/build instructions and known limitations, not ROMs,
saves, donor assets, proprietary tools or licenses in the repositories. Name the
edition actually checked; HeartGold evidence does not certify SoulSilver or
physical hardware.

## Opening checkpoint completion checklist

- [x] The corrected Oldale HeartGold native build completed successfully (R5).
- [x] An earlier matching gameplay run earned the Johto and Hoenn partners,
  completed the rescue, and received one Potion.
- [x] The Potion survived native saving and fresh Continue; repeat interaction
  did not grant another. These are retained R3 results, not a claim that R5's
  corrected dialogue was already observed.
- [x] Check the corrected dialogue's advance/scroll/dismiss behavior once in R5.
- [x] Close the episode's return/revisit check with expanded progress, reusing
  already-passing steps whose relevant code and inputs are unchanged.
- [x] Confirm a representative editor round trip preserves nonzero episode
  progress. Reuse the existing frontend evidence where applicable; identify
  shared-byte native readback explicitly rather than replaying identical exports.
- [x] Finish the owner-facing reproduction/entry/exit instructions and list
  remaining prototype and edition limitations.

## Retained opening checkpoint evidence

The corrected R5 build completed with all 15 required new outputs. Its actual
ROM ARM9 bytes equal the previously checked R3 code, so unchanged gameplay/save
checks were reused rather than replayed. In a fresh process, the genuine saved
Oldale checkpoint loaded; one deliberate dialogue advance displayed the final
clause, and a separate advance dismissed it normally.

That same session walked back through Route 101 and Littleroot, used the lab's
prototype return NPC to reach Johto, then revisited Hoenn through Elm. Birch
gave the already-received partner response. A normal in-game save completed,
followed by normal emulator shutdown. The original checkpoint was untouched.
The ordinary Johto lab assistant also gave his Potions during this journey;
that is not a duplicate Oldale reward.

The resulting genuine save had nonzero Hoenn progress, Cyndaquil and Treecko,
and native counters 4/3. A focused check through the retained shared editor
codec covered load, no-edit export, trainer-name-only edit, clone/copy, export
and reopen. Both campaign allocations, the entire inactive bank, all Pokemon
bytes and the DSV footer were preserved; only the requested name and ordinary
dirty-mask/checksum bytes changed. Potion flag 132 remained set.

A separate fresh game process loaded that edited export as `V1TEST`, continued
at the saved Birch-lab location and retained the already-received response.
Normal shutdown left the whole editor export unchanged.

This last regression exercised the shared codec, **not new browser and desktop
GUI runs**. The earlier independent real frontend import/edit/export/reopen
checks are reused alongside it. The current native fixture has two party
Pokemon and an empty PC; populated-PC codec coverage remains the separately
labelled synthetic tests, not a new native populated-PC journey.

The current source/build/player instructions were checked against the tracked
producers and the completed build. No additional full build or unchanged
source-test suite was run for these documentation-only changes. Private ROMs,
saves and captures remain outside the repositories.

## Lean verification policy

- Test changed behavior, not every previously tested feature after every edit.
- For dialogue-only changes, use the relevant encoder/source check, a successful
  build and one focused in-game display check. Reuse unrelated gameplay/save
  evidence unless its relevant inputs change.
- For persistent-state changes, use focused integrity tests and native save/load
  coverage. Protect original saves and keep normal gameplay outcomes genuine.
- Reuse existing source/build records. Do not make a new full provenance package,
  unchanged-input audit or complete playthrough a routine gate for a small edit.
- Broad gameplay testing of the new regional import is owner-led. Exhaustive
  direction/failure matrices and hardware qualification are not blockers for
  the experimental Hoenn build.

Do not use savestates or gameplay-memory/outcome injection as evidence of
ordinary progression. Preserve failures and label unverified cases honestly.