# Follower, palette and name revision

This revision addresses playtest reports of mixed-case species names, overly bright colors and oversized followers whose animation looked like bouncing. It applies to both ROMs on `fakemon-starter-trio`.

## In-game names and existing saves

All eleven names are uppercase in the name/message banks and species references in Pokédex prose and Elm dialogue. Human-readable design metadata keeps its original spelling.

An older save can contain title-case default names inside each Pokémon record. Reading an unnicknamed custom Pokémon's name now uppercases it only when the result exactly matches that species' current default. Deliberate nicknames, Eggs, canonical species, unmatched names and invalid-checksum records are preserved. Locked records with pending edits defer normalization until a later valid read. The normal game save operation persists the change; no save-format change or new game is required.

## Native palettes

The graphics remain sixteen-entry RGB555 palettes (five bits each for red, green and blue, stored in sixteen-bit words), with index zero transparent and fifteen visible colors. This is a color-choice correction, not a conversion to unrestricted RGB artwork.

The Electric family uses darker Pikachu golds. The Fire family uses Cyndaquil's muted follower red/orange shades. Ice colors use softer slate blues, with Spheal as an anchor. Shiny identities remain cyan Electric, ivory/purple Fire and green Ice, with less vivid effect highlights. The bird palettes remain unchanged. Battle pixel indices are unchanged; follower indices are newly quantized to these palettes. Every follower has private normal and shiny palettes, so no canonical species is recolored.

Exact values, checks and comparisons are in [PALETTE_CORRECTIONS.md](../PALETTE_CORRECTIONS.md) and [palette-corrections.json](../../../files/fakemon/palette-corrections.json).

## Walking and scale

The original imported frames used body-height changes and nearly filled the available space for every species. Runtime frame order, geometry, movement distance and animation callbacks already matched stock HGSS. The fix replaces the art with alternating-foot poses and reduces occupied pixel bounds while retaining those stock rules.

| Species | Maximum occupied width × height | Native frame canvas |
| --- | --- | --- |
| Voltuff | 21 × 21 | 32 × 32 |
| Embernewt | 21 × 20 | 32 × 32 |
| Sedgling | 18 × 18 | 32 × 32 |
| Surguenon | 24 × 25 | 32 × 32 |
| Pyrovaran / Rimevaran | 26 × 25 | 32 × 32 |
| Cragaviar | 26 × 26 | 32 × 32 |
| Raijinque | 34 × 34 | 64 × 64 |
| Magmalisk / Fimbulisk | 38 × 34 | 64 × 64 |
| Ragnaroc | 48 × 42 | 64 × 64 |

These are limits, not forced dimensions: each facing retains its proportions. For context, native Pikachu's front is 16 × 18 pixels, Cyndaquil's is 14 × 19 and Pidgey's is 13 × 14. The earlier custom base forms approached 26 pixels in both axes. Normal-size frames share stock bottom-exclusive baseline 30; large frames use 62. The smaller silhouettes create the expected visible space around the trainer without moving the follower's map position.

Each direction retains two frames. Native order is north A/B, south A/B, west A/B, east A/B. East mirrors west. Pair cropping and registration preserve a common scale and origin, avoiding independent per-frame resizing. The two repaired lizard side frames use explicit placement/transform metadata to retain the other reviewed frames.

Native frame previews: [Electric PNG](../validation/graphics-revision/electric-preview.png), [Fire/Ice PNG](../validation/graphics-revision/varan-preview.png), [Bird PNG](../validation/graphics-revision/bird-preview.png). Two-frame animations: [Electric GIF](../validation/graphics-revision/electric-preview.gif), [Fire/Ice GIF](../validation/graphics-revision/varan-preview.gif), [Bird GIF](../validation/graphics-revision/bird-preview.gif). These show native pixels enlarged three times; they preserve relative species sizes.

## Art source and reproduction

Walking-pose revisions were made with the built-in `image_gen.imagegen` tool using the existing approved family sheets. The exact prompts are in [generation-prompts.json](generation-prompts.json), selected originals are in [source-sheets](source-sheets/), and reviewed crop/orientation/placement metadata is in [follower-sheet-layout.json](follower-sheet-layout.json). Those source images are working artwork, not directly loadable DS sprites.

The packing script only performs technical extraction, alpha conversion, alignment, resizing, indexed-color conversion and native serialization. Generated low-alpha halos are discarded before measurement; hardware transparency is binary. No image-generated labels or backgrounds enter the game. Pyrovaran and Fimbulisk's erroneous side-B poses were separately regenerated to keep one tail and the same left-facing view.

From the repository root, with Pillow and ndspy installed:

```sh
for family in electric varan bird; do
  python3 tools/py_scripts/pack_fakemon_followers.py \
    --family "$family" \
    --sheet "documentation/fakemon/graphics-revision/source-sheets/$family.png" \
    --layout documentation/fakemon/graphics-revision/follower-sheet-layout.json \
    --output /tmp/fakemon-followers-review
done
```

Review the native-size PNG/GIF previews before copying the staged `follower.bin`, `source/overworld.png` and palette files into their corresponding `files/fakemon/<species>/` directories. Then finalize palette bookkeeping:

```sh
python3 tools/py_scripts/correct_fakemon_palettes.py --components png follower
python3 tools/py_scripts/pack_fakemon_followers.py --check-current
```

Refresh `assets.json` payload SHA-256 values after an intentional asset update, and build with `./tools/build_starter_trio.sh`. The manifest's original source-ROM hash remains import provenance; the revision record identifies these later modifications.

## Validation

Evidence for this revision is under [validation/graphics-revision](../validation/graphics-revision/). The original starter-event evidence in [STARTER_TRIO.md](../STARTER_TRIO.md) retains the hashes of the build actually tested at that time. Both the source/native checks and packaged-ROM checks must pass before release. Emulator screenshots and walking captures supplement these checks; still images and archive equality alone cannot establish motion quality.

The installed follower files reproduce byte for byte from the checked-in art/layout/palette plan: 44 files covering all 88 frames. Name tests cover 35,904 encrypted/locked party and box cases, 88 name-bank rows and 99 complete Pokédex entries. An independent review found no blocking checksum/encryption or native serialization issue.

Both revised ROMs build successfully and pass 413 asset checks each, 1,604 rival-team checks each and the starter gift/backend/69-script-path checks. All 19 updated compiled message banks match each packaged ROM. The preserved base-port ROMs retain their original hashes. See [build-validation.json](../validation/graphics-revision/build-validation.json).

HeartGold loaded the genuine earlier gift save, displayed all three defaults in uppercase, saved normally and reopened the result in a separate emulator process. A second fixture retained the deliberate nicknames Cinder and Sedgling through the same save/reload cycle. PKHeX verified 68 runtime-save assertions: valid save and Pokémon checksums, exact preservation of unrelated Pokémon bytes, and entirely unchanged deliberately nicknamed records. See [names-runtime.json](../validation/graphics-revision/names-runtime.json). SoulSilver separately passed a fresh boot and responsive title screen; full SoulSilver gameplay was not replayed.

All three base forms were walked through north/south/west/east in HeartGold, changing leaders through the real party UI. Fourteen valid clips cover 288 native frames, including longer straight walks for Embernewt and Sedgling. The captures show alternating foot poses, correct facing and normal one-tile following at the reduced sizes. The scene uses the game's night/rain lighting. See [walking review](../validation/graphics-revision/walking/runtime-review.json), [settled size/spacing comparison](../validation/graphics-revision/walking/settled-followers-4x.png) and [extended gait frames](../validation/graphics-revision/walking/straight-cycle-details-6x.png). Evolved/shiny followers were reviewed as native assets; they were not all played on every map.

After the emulator runs, two newly written story lines were also corrected to CHIKORITA, CYNDAQUIL and TOTODILE. The final rebuild differs from the emulator-tested ROMs only in message banks 543 and 550. ARM9/ARM7 code, overlays, every species-name bank, all graphics and every other filesystem file are byte-identical. The [HeartGold](../validation/graphics-revision/heartgold-final-text-delta.json) and [SoulSilver](../validation/graphics-revision/soulsilver-final-text-delta.json) comparisons retain both exact hashes; emulator reports retain the hashes actually exercised. Final packaged assets and gift/dialogue checks were repeated successfully.
