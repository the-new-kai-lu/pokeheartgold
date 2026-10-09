# Bulk Hoenn import — experimental source candidate

This continues original Stage 1, not Stage 2. The completed four-map opening
remains the small-scale checkpoint. The batch importer adds the other Emerald
maps and reports what it can and cannot translate.

**A converted layout is not a converted campaign.** This candidate includes
static region resources and supported interactions, but is not yet a complete
Emerald story playthrough. Unsupported reachable script operations block the
whole interaction with a visible diagnostic. They are not emitted as successful
no-ops or replaced by a generic gym sequence.

## Generate the region

First compose the expanded opening source using [STAGE1_GUIDE.md](STAGE1_GUIDE.md).
Then, from this expansion fork:

```sh
python3 scripts/prepare_hoenn_region.py \
  --episode "$STAGE1_SOURCE" \
  --donor "$DONOR" \
  --output "$HOENN_SOURCE"
```

Use the selected Emerald source revision
`c925b8482d05fb882d6b64e523653cae599e025f`. The output must be fresh and outside
both inputs. The producer does not consume ROMs, saves, compiler binaries or
licenses. Generated donor assets remain owner-local, not in Git.

The generator checks resource bounds, static warp targets, coordinate ranges,
NARC serialization and the unchanged per-model/texture memory reservations.
It splits large maps into 32×32 chunks and uses lossless BGR555 texture pages;
it does not scale towns into a thumbnail or remove detail to fit the opening's
old 20×20 constraint. Sidecar tables handle larger area/encounter IDs without
widening `MapHeader`'s packed binary layout.

The generated tree uses a **2 Gbit / 256 MiB ROM capacity**, including matching
header templates. The region exceeded the retail 1 Gbit packaging limit; this
is ROM storage capacity, not an increase in DS RAM. The default retail checkout
and its matching-build settings remain unchanged.

The output contains:

- `hoenn-import-report.json`: per-map IDs, supported interactions, blocked
  scripts/terrain/warps, adaptation notes and explicit completion limits.
- `hoenn-build-files.json`: changed source/resource files for an incremental
  build on the existing private SDK-equipped cache.
- The source/resource tree for the same HeartGold build command used by the
  opening checkpoint.

## What the first batch does

Retain the four opening maps and their authored rescue/reward logic. Append
the other maps, their static graphics, ordinary terrain, supported door/ground
connections, NPC/sign text, supported interaction-driven trainer battles and
one-time item pickups. Trainer parties retain donor species, levels, held
items and explicit moves by **name**, never by reusing Emerald numeric IDs.
They run in the native HGSS battle system with stock class artwork and AI.
Imported trainer checks/sets/clears use the expanded Hoenn defeat-flag namespace;
their larger trainer IDs must not address the host's ordinary story-flag array.

Wild land/surf/fishing tables use native encounter structures. The report
discloses differences such as fixed walking-slot levels and native fishing
probabilities. Unsupported Rock Smash tables are not claimed as converted.
Stock NPC stand-ins are stationary; donor actor artwork, movement, music,
animation, elevation, occlusion and field effects are not reproduced by the
flat-map converter.

## Remaining implementation, not merely testing

Story-coordinate triggers, map-load/frame callbacks and regional initial state
still need translation. C specials, shops, dynamic warps, water traversal,
Dive, currents, bridges and puzzles are not made functional by a successful
ROM build. The report is the implementation work list; the complete Emerald
campaign is **not** declared done.

The overworld map/Fly screen is not expanded to Hoenn. New maps use a generic
Hoenn met-location label and disabled Fly/phone/radio, rather than squeezing
unrepresentable IDs into the host's packed fields. Field/HM integration remains
part of Stage 1, not progression tuning for Stage 2.

In Oldale, the new assistant at **(10, 15)** opens an alphabetized, paged
test-travel directory. Entries include the native map ID so bug reports can
identify an area unambiguously. Only maps with an empty ordinary-ground landing
are offered. The assistant beside each landing returns to Oldale.

This is development travel, not evidence of legitimate story completion; it
does not grant badges, wins or quest flags. If continuing an old save already
in Oldale, leave and reenter so its new map actors are loaded.

## Lean verification and human playtests

Run `python3 -m unittest discover -s tests -p test_hoenn_region.py -v` for the
new converter contracts, then generate the complete source and build HeartGold.
Reuse unchanged opening/save/editor evidence. Do not add an exhaustive regional
playthrough, editor matrix, SoulSilver build or hardware run as an alpha gate.

The owner and friends provide broad gameplay feedback. Test on disposable
expanded-format saves and keep originals backed up. A save made on a newly
imported map must not be opened in an older four-map ROM. Use the project's
expanded-format editor forks, not unmodified upstream editors.

For a useful report, record the build, map name, entrance/coordinates, NPC or
story step, expected behavior and observed behavior. Distinguish a known
blocked conversion in the manifest from a bug in converted content.
