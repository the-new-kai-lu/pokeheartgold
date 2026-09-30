# Battle contours and anatomy repairs

All eleven custom species now have a consistent one-native-pixel dark battle contour, plus selected internal anatomical seams. Ragnaroc's back wings fit the view without the previous straight cuts. Fimbulisk's first back frame has its missing cheek/lower-jaw/throat surface restored. The same issue in Rimevaran's second back frame is repaired.

[Reported defects: both frames before/after](reported-issues-before-after.png) | [In-game before/after](in-game-before-after.png) | [All normal frames](all-battle-frames-normal.png) | [All shiny frames](all-battle-frames-shiny.png) | [All HeartGold battle captures](runtime-battles.png)

## Art changes

- Front and back sprites use the existing darkest palette index, 1, for a one-pixel contour at native 80 x 80 resolution. Four-neighbor edge coverage avoids thickening already-dark edges. Reapplying the contour is verified to be idempotent.
- Internal lines mark body/element interfaces, selected shoulders and limbs, bird wing roots and neck boundaries. They do not surround every shading color or every ice/flame facet.
- Ragnaroc retains an enlarged central head/neck while the complete wings are brought inward into a more upright arc. Both frames retain transparent top/side margins around their wing contours.
- Fimbulisk frame 1 restores 69 missing surface pixels from its intact alternate head pose within the cheek/throat region. Rimevaran frame 2 receives the corresponding repair (78 pixels). Normal and shiny versions use the same repaired indices.
- The framing audit also restores Surguenon's second-frame crest, Raijinque's cloud-arm edge, Embernewt's tail flame and the evolved lizards' snouts. Lower torsos still meet the bottom of the close-up view. Body dimensions/facing remain aligned with the existing art; no runtime sprite offsets or scaling code change.

Both male/female resources and both animation frames are updated. RGB555 palettes, keys, archive sizes and headers remain unchanged. Followers, menu icons, stats, level-45 final evolutions, learnsets and game logic are untouched.

## Checks and scope

The repaired 88 frames round-trip exactly through the game's NCGR encoding. Checks cover palette-index range, stable native headers/keys, contour idempotence, safe top/side colored pixels and Ragnaroc's wing margins. Both normal and shiny contact sheets were visually reviewed.

Both starter-trio builds pass 413 asset checks. Exact ROM comparison shows that only the 44 custom picture members of `a/0/0/4` changed; every other file (including unnamed overlays), ARM9 and ARM7 is byte-identical. The four level-45 final-evolution entries were checked again. See [ROM delta and hashes](rom-delta.json).

DeSmuME captures cover the normal back sprites of all eleven species in HeartGold, and the reported Ragnaroc/Fimbulisk cases in SoulSilver. The comparison views use the same first-rival scene. Per-species run records contain the tested ROM hash and input-save hash; snapshots are under `runtime/`. These are disposable level-5 rendering fixtures, not tests of species stats or evolution. Front sprites, shiny variants and both animation frames were checked from the decoded/source art sheets; those checks are distinct from the captured normal back-sprite runtime views.

## Reproduction

This script supersedes the battle-sprite output of `revise_fakemon_backs_and_gaits.py`. Its follower output remains unchanged.

```sh
python3 tools/py_scripts/repair_fakemon_battle_contours.py --output /tmp/battle-contours-staged
```

It reads immutable `2f1f8db77` inputs and uses the uncropped back art at `ece5bf66b` to recover lost edges. Copy the staged `battle-0.bin` through `battle-3.bin` and `source/{male,female}/{front,back}.png` files for each species into `files/fakemon/<species>/`. Refresh those hashes in `files/fakemon/assets.json`, then rebuild:

```sh
./tools/build_starter_trio.sh
python3 tools/py_scripts/validate_fakemon_assets.py --rom build/heartgold.us/heartgold-fakemon-starters.nds --output /tmp/hg-assets.json
python3 tools/py_scripts/validate_fakemon_assets.py --rom build/soulsilver.us/soulsilver-fakemon-starters.nds --output /tmp/ss-assets.json
```

Reopen the rebuilt ROM and load an ordinary in-game save to avoid retaining old graphics in an emulator savestate.
