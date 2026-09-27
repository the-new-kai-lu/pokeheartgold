# Native palette corrections

The original approved battle-sprite indices are retained. Follower poses and their pixel indices are revised separately as described in [graphics-revision/README.md](graphics-revision/README.md). This revision changes color tables for Voltuff, Surguenon, Raijinque, Embernewt, Pyrovaran, Magmalisk, Rimevaran and Fimbulisk to make their effects less bright next to stock HGSS creatures. The Sedgling family is unchanged.

The electric family's main yellow now uses Pikachu's exact RGB555 `(30,23,4)` instead of `(31,26,8)`. Its adjacent shades also use Pikachu's gold and pale-yellow entries. The fire family's red/orange anchors now use Cyndaquil's exact follower colors `(16,3,3)`, `(20,5,5)`, `(26,7,6)` and `(30,20,2)`, with softened intermediate and highlight shades. Stock battle and follower palettes differ; the muted follower colors address the observed walking-sprite brightness, and the same corrected ramp is used in the custom battle art for consistency. The ice branch uses less saturated blue midtones informed by Spheal's stock palette. These are native five-bit channel values, not RGB888 display values.

Shiny effects receive smaller brightness reductions while preserving their established identities: cyan electric, white-bodied purple fire, and green ice. Transparent index zero is unchanged, and each variant retains fifteen distinct visible palette entries. Shared canonical menu-icon palettes are untouched.

Each custom follower model contains its own `tsure_poke0` and `tsure_poke1` palette blocks; updating these does not recolor any canonical follower. Battle palettes are the separate native `battle-4.bin` and `battle-5.bin` resources. The imported source-art convention stores the normal palette on `front.png` and the shiny palette on `back.png`; this convention is preserved when updating embedded PNG palette tables.

## Reproduction

The complete before/after RGB555 mapping is recorded in [`palette-corrections.json`](../../files/fakemon/palette-corrections.json). The helper validates the old or already-corrected palettes before writing, and checks that PNG pixel indices and native follower texture bytes stay unchanged:

```sh
python3 tools/py_scripts/correct_fakemon_palettes.py \
  --components battle jasc png follower
```

This needs Pillow for PNG metadata bookkeeping. The helper deliberately does not change `assets.json`; its payload hashes must be refreshed after all graphic changes are finalized. It is safe to rerun after followers are rebuilt with the corrected palettes.

The diagnostic view uses actual indexed texture data decoded from native follower models, with both old and new color tables applied to the same pixels. Generating the diagnostic requires ndspy and Pillow:

```sh
python3 tools/py_scripts/correct_fakemon_palettes.py \
  --diagnostics documentation/fakemon/validation/palette-correction
```

The checked-in [comparison sheet](validation/palette-correction/native-palette-comparison.png) isolates color changes from walking-frame and scale changes. Its first-frame measurements showed mean visible-pixel luminance reductions of 10.2% for Voltuff, 8.4% for Embernewt and 3.2% for Rimevaran; the ice correction primarily reduces saturated blue highlights. The RGB555 palette and unchanged-index audit passed 80 source/stock-anchor checks. These measurements describe asset data, and do not replace inspecting the rebuilt game.

The later [native base-three comparison](validation/palette-correction/staged-base-three-native-comparison.png) shows the original followers, revised gait/size/color assets, and stock Pikachu/Cyndaquil/Pidgey at the same native-pixel scale, including shiny variants. Its [read-only audit](validation/palette-correction/audit_staged_followers.py) verifies all 22 normal/shiny staged palette variants and records their native payload hashes and actual color-index distribution.
