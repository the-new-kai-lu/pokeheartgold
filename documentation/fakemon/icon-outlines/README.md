# Party/box icon outlines

All eleven custom species now have consistent one-native-pixel dark contours in both 32x32 menu-icon frames. The outline uses the existing stock palette index 15 (RGB555 8,8,8), the same darkest gray used by the retail icons. Shared palettes are not modified.

[Before/after, both frames](before-after.png) | [Stock comparison](stock-reference.png) | [Surguenon/Rimevaran/Cragaviar in-game](party-0.png) | [Six more custom icons](party-1.png) | [Fimbulisk/Ragnaroc and stock icons](party-2.png)

`outline_fakemon_icons.py` adds dark pixels only in transparent cells within one pixel of existing colored pixels. Existing dark contours are not themselves expanded. This preserves interior colors and detail, avoids thickening already dark legs, and makes the operation idempotent. Each animation frame is processed separately, so the border cannot spill into the other frame. There is room for the complete outline on the existing canvas; no scale, registration or frame-order changes are needed. Surguenon's corrected facing is retained.

Two pre-existing detached vertical artifacts became conspicuous with the added border. Twelve isolated pixels in the second frames of Cragaviar and Ragnaroc were explicitly removed before outlining. Their exact coordinates are recorded in the script and [checks.json](checks.json). Actual detached anatomy, such as Sedgling's lifted toe, is retained.

## Reproduction

The script reads the approved icons at commit `47f1377bc`, applies the documented cleanup and contour pass, writes the indexed PNG/native 4bpp tiled NCGR data, and updates manifest hashes:

```sh
python3 tools/py_scripts/outline_fakemon_icons.py
./tools/build_starter_trio.sh
```

`warm_electric_icons.py` also applies this outline after its color and facing corrections; regenerating the three electric icons reproduces the final native files exactly. Pillow is required for these art scripts.

## Validation

All 22 frames passed checks for unchanged interior pixels (after the two documented artifact cleanups), unchanged palettes/transparency, no clipped outlines, idempotence, and exact indexed-pixel round trips through native tile packing. See [per-species checks](checks.json).

Both rebuilt ROMs pass all 413 packaged-asset checks: [HeartGold](heartgold-validation.json), [SoulSilver](soulsilver-validation.json). These reports contain the current ROM hashes. All eleven custom icons were visually checked in the final HeartGold party screen, with stock comparison icons included in two of the three disposable fixtures. The fixture Pokémon's species/names were changed solely for graphics inspection; their displayed levels/HP are not balance tests. Runtime reports and input sequences accompany the screenshots. SoulSilver was checked at the packaged-asset level.

The HeartGold ROM comparison proves that only the eleven custom icon members (551–561) of `a/0/2/0` changed. Stock icons and shared palettes, battle sprites, followers, game code and other ROM files are byte-identical to the previous delivered build. See [ROM delta](rom-delta.json). Existing saves remain compatible.
