# Oldale outdoor candidate

This is a **partial, opt-in Emerald segment**, not a completed town, campaign, or
Stage 1 release. It adds Oldale's exterior, a stateless girl NPC, and reciprocal
travel with Route 101. Default production maps remain unchanged.

The [expanded save contract](../expansion/SAVE_FORMAT.md) permits future
versioned campaign storage and matching editor changes. This particular segment
does not need additional state and does not change the save format.

## Source and reproduction

`scripts/prepare_oldale_candidate.py` consumes the independently approved R5
opening source and the owner-local Emerald donor. It authors a separate source
tree; it does not install assets into the default tree or build a ROM.

```sh
python3 scripts/prepare_oldale_candidate.py \
  --root "$PWD" \
  --episode "$R5_EPISODE_SOURCE" \
  --donor "$EMERALD_SOURCE" \
  --output "$OLDALE_SOURCE" \
  --author-unapproved-oldale

OLDALE_CANDIDATE="$OLDALE_SOURCE" \
OLDALE_R5_SOURCE="$R5_EPISODE_SOURCE" \
python3 -m unittest discover -s tests -p 'test_oldale_candidate.py' -v
```

Use a fresh output directory. The Emerald revision remains
`c925b8482d05fb882d6b64e523653cae599e025f`. Extraction checks the actual donor
files, not only the checkout revision. The result retains an unapproved-candidate
status and `runtime_verified: false`: a source manifest does not certify every
subsequent build.

The generator adds map 543, its own terrain/model/texture resources, event member
494, script bank 967, message bank 830, and the Oldale map-section label. Existing
Route 101 rescue and gift gates remain. Only the independently checked ordinary
donor grass cells needed for the northbound corridor are opened; unsupported
terrain and exterior rims remain sealed. The 53,676-byte model remains below
the 57,344-byte authoring limit.

The script's `.rodata` directive and the message's supported UTF-8 apostrophe
are tested against the reconciled native inputs. No donor graphics, ROMs, saves,
proprietary tools, or licenses are included in this repository.

## South-exit defect and regression

The first native Oldale run exposed a genuine return-path defect. The walkable
south-warp tiles were on row 18, but the departure events incorrectly used
row 19, which is the sealed rim.

The game's `FieldSystem_CheckMapTransition` uses **standing coordinates** for
`WARP_SOUTH`. Its north-facing path uses facing coordinates, so copying the
north-boundary convention to the south boundary was incorrect.

The fix moves only Oldale departure events 0 and 1 from row 19 to row 18.
It leaves both row-17 arrival anchors, the sealed rim, Route 101 events, story
gates, and all native C/save code unchanged.

The regression host-compiles the actual transition caller, coordinate helpers,
metatile predicates, map connection, and event lookup with bounded stubs. It
checks both lanes across 20 rescue/gift combinations, direction restrictions,
arrival anchors, and state preservation. A negative control restores only the
two old row-19 events and must fail. This is a caller/terrain/event composition
test, not merely a changed expected coordinate.

## Recorded owner-local runtime

The retained R6 HeartGold build
`fc8ef9cca2b4879123cd0d6f8dd27d24d8363471bbbb45e12a114ea919da9fb3`
passed normal Johto-to-Hoenn travel, Oldale entry, visible town rendering, the
girl's dialogue, party-menu return, field walking, and native saving.
Both south-exit lanes failed. That failure remains retained.

The corrected R7 diagnostic image
`092fb8ea11868352366a41c99f8a728fc7bb9b6c14d5747e199102bf8ecb9283`
was a **source-driven resource-only rebuild**, not a fresh C compilation:
the old 96-byte event member was reproduced exactly from the native JSON
template, then the corrected generated member replaced it at the same length.
Only two coordinate bytes changed in the entire image. Header, file tables,
ARM9, ARM7, all 129 overlays, all other resources, and the original ELF remained
byte-identical.

In a fresh R7 process, ordinary Continue loaded the genuine R6 Oldale save at
map 543, tile (15,12). Both south lanes then returned to Route 101, and normal
northward travel revisited Oldale through each matching lane. Another genuine
native save completed at Oldale (11,17).

The post-revisit save has valid native block checksums, counters 12/13, the
expected saved location, the original party Totodile identity, and unchanged
complete PC records, including LEAF and the captured Hoothoot. Its private
SHA-256 is `9a2e5876c2fec2bd7b9c3a770989d0d17aa416bbf8bfb828847339a50ffab282`.
This new R7 resave has not itself been cold-loaded; the recorded cold load used
the earlier genuine R6 save.

These observations used ordinary inputs without savestates, gameplay-memory
changes, or injected outcomes. They are bounded libretro diagnostic evidence,
not hardware/secure-card/production certification or a SoulSilver result.
One Route 101 north-edge capture shows a black band above the terrain; its cause
has not been established. These captures are not complete rendering/VRAM
acceptance or a claim of polished map boundaries.

## Validation and remaining scope

- Configured Oldale source suite: nine tests passed, no skips; the old row-19
  fixture failed the new caller regression as expected.
- Outdoor extraction suite: four tests passed. Default discovery reported
  107 tests and 18 opt-in/tool skips; it was not an all-tests/no-skips result.
- Default baseline and whitespace checks passed. The source candidate contains
  544 maps; the default tree still contains 540.
- Oldale interiors, Route 102/103, the rival sequence, Mart reward, other town
  interactions, and subsequent Emerald/Platinum campaign progression remain
  unimplemented. Their future state needs an explicit allocation under the
  expanded-save contract, not guessed reuse of existing variables.