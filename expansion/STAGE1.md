# Stage 1: foundation and one playable episode

The owner confirmed this boundary: **engine/save foundation plus one playable
imported episode**. This supersedes older statements that Stage 1 requires the
full Emerald and Platinum campaigns.

Full original regional story imports and the new integrated cross-region
storyline are later work. Their phase numbers are not established by this
document. "Campaign state" in the implementation means persistent story flags
and variables; it does not imply that a new integrated storyline is being built.

## Episode boundary

Finish the existing Hoenn opening slice rather than starting more regions:

- Enter Hoenn from Johto using the documented prototype travel entrance.
- Traverse Littleroot, Birch's lab and Route 101; complete the actual rescue
  battle and receive one Hoenn starter.
- Reach Oldale's exterior and complete the existing one-time Potion interaction.
- Return to Johto and revisit without losing earned progress or duplicating
  rewards. Native saving and cold Continue must preserve that progress.

The prototype entrance is not the final integrated-story travel system.
Oldale interiors, Routes 102/103, the rival sequence, gyms and the remainder of
Emerald/Platinum are outside this milestone. Record closed borders and other
prototype limitations instead of implying a finished region.

## Foundation

Use the explicitly allocated, versioned expanded-save format and the project's
PKHeX/PKMDS forks. Preserve ordinary Pokemon data and saved episode progress.
Vanilla-layout compatibility and unmodified upstream-editor compatibility are
not requirements; see [the save contract](SAVE_FORMAT.md).

Deliver reproducible source/build instructions and known limitations, not ROMs,
saves, donor assets, proprietary tools or licenses in the repositories. Name the
edition actually checked; HeartGold evidence does not certify SoulSilver or
physical hardware.

## Current completion checklist

- [x] The corrected Oldale HeartGold native build completed successfully (R5).
- [x] An earlier matching gameplay run earned the Johto and Hoenn partners,
  completed the rescue, and received one Potion.
- [x] The Potion survived native saving and fresh Continue; repeat interaction
  did not grant another. These are retained R3 results, not a claim that R5's
  corrected dialogue was already observed.
- [ ] Check the corrected dialogue's advance/scroll/dismiss behavior once in R5.
- [ ] Close the episode's return/revisit check with expanded progress, reusing
  already-passing steps whose relevant code and inputs are unchanged.
- [ ] Confirm a representative editor round trip preserves nonzero episode
  progress. Reuse the existing frontend evidence where applicable; identify
  shared-byte native readback explicitly rather than replaying identical exports.
- [ ] Finish the owner-facing reproduction/entry/exit instructions and list
  remaining prototype and edition limitations.

These unchecked items remain completion gates. Reducing scope or test overhead
does not turn an untested behavior into a pass.

## Lean verification policy

- Test changed behavior, not every previously tested feature after every edit.
- For dialogue-only changes, use the relevant encoder/source check, a successful
  build and one focused in-game display check. Reuse unrelated gameplay/save
  evidence unless its relevant inputs change.
- For persistent-state changes, use focused integrity tests and native save/load
  coverage. Protect original saves and keep normal gameplay outcomes genuine.
- Reuse existing source/build records. Do not make a new full provenance package,
  unchanged-input audit or complete playthrough a routine gate for a small edit.
- Broader direction/failure matrices, full regional completion and hardware
  qualification belong at their relevant later delivery milestone.

Do not use savestates or gameplay-memory/outcome injection as evidence of
ordinary progression. Preserve failures and label unverified cases honestly.