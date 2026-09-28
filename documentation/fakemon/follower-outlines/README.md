# Walking-sprite outline pass

All eleven custom followers now have a consistent one-native-pixel dark outline across all four directions and both animation frames (88 frames). The same indexed outlines work with both existing normal and shiny palettes.

[Before/after side views](before-after-side.png) | [All normal frames](all-frames-normal.png) | [All shiny frames](all-frames-shiny.png) | [Animated four-direction preview](walking.gif) | [In-game side steps](runtime-side-steps.png) | [Settled facings](settled-directions.png)

## Pixel treatment

The pass fills only transparent pixels adjacent to an existing non-outline colored pixel, using the existing darkest palette index 1. It does not expand pixels that already form a dark outline, so rerunning it cannot make the border thicker. No existing sprite pixel is moved, recolored or removed. Step poses, frame order, east/west mirroring, native canvas sizes, registration and animation timing are retained. The added contour can extend the occupied silhouette by one pixel into its existing transparent margin; the art is not scaled or shifted.

Normal/shiny RGB555 palette bytes and all NSBTX metadata are unchanged. The border therefore uses the already-approved dark color for each variant, rather than introducing another color or replacing its palette. Menu icons and battle sprites are unchanged by this pass.

## Reproduction

The script reads the approved follower assets at commit `2f1519a8f` and stages the final files:

```sh
python3 tools/py_scripts/outline_fakemon_followers.py --output /tmp/follower-outlines
```

Copy each species' `follower.bin` and `source/overworld.png` into its `files/fakemon/<species>/` directory, refresh follower hashes in `files/fakemon/assets.json`, then run:

```sh
python3 tools/py_scripts/pack_fakemon_followers.py --check-current
./tools/build_starter_trio.sh
```

This is the final follower art pass, after the native-pixel gait revision. The historical gait script by itself reproduces the earlier unoutlined frames. Pillow is required for sprite processing.

## Validation

- All 88 native/source frames round-trip correctly. Every pre-existing indexed pixel remains identical; only transparent pixels become outline pixels. Both palettes and every byte outside the native texture payloads remain unchanged. No added outline is clipped. The operation is idempotent and east/west frame pairs remain exact mirrors. [Per-species checks](checks.json).
- All normal and shiny native frames were visually reviewed. Normal-color followers for all eleven species were then exercised outdoors in HeartGold using east/west/north/south inputs: 44 clips and 1,056 native captured frames. Clips include turn/ball-emergence delays; review the moving portion. The emulator used the game's night lighting. [Per-species runtime GIFs and metadata](runtime/).
- Both final starter ROMs pass all 413 packaged-asset checks: [HeartGold](heartgold-validation.json), [SoulSilver](soulsilver-validation.json). These reports contain current ROM hashes. SoulSilver was validated at the packaged-asset level; gameplay captures use HeartGold. Shiny variants were checked as native assets, not separately played on every map.
- Compared with the previous delivered HeartGold build, only custom follower members 863–873 in `a/0/8/1` changed. Code, stock followers, menu icons, battle art and all other ROM files are byte-identical. [ROM delta](rom-delta.json). Existing game saves remain compatible.
