# Close-up battle backs and revised side walking

> Battle art has since received [contour and anatomy repairs](../battle-contours/README.md), including complete Ragnaroc wings and repaired Fimbulisk/Rimevaran heads. Use the newer battle-art script when reproducing current sprites. This revision remains the source for the follower poses.

The custom battle backs previously fit nearly the entire Pokemon into an 80 x 80 frame. Stock HGSS backs commonly devote that space to the head and upper body. This revision enlarges and reframes all eleven backs individually, and replaces the straight follower leg strokes with shaped, bent legs and a distinct passing step.

[Before/after backs](back-before-after.png) | [Both frames, normal and shiny](back-frames-normal-shiny.png) | [Actual battle captures](runtime-battles.png) | [Before/after walking animation](walking-before-after.gif) | [Actual walking steps](runtime-walking-steps.png)

## Changes

Back sprites use a species-specific 1.45-1.85x close-up. Lower bodies, long tails and outer wings can extend beyond the view, as appropriate for a close camera. Both animation frames share one transform. Indexed edge-aware enlargement reconstructs diagonal corners with existing colors; it does not add new palette entries or invent higher-resolution painted detail. Disconnected tail fragments at cropped edges are removed. Surguenon's previously corrected facing is retained.

Side followers have individually specified hip, knee/hock and ankle positions, tapered thighs, folded joints and separate planted/lifted paws. Lizards have broader hindquarters, birds have bent legs, and the electric line has shaped thighs. The second frame brings the supporting foot beneath the body, so the silhouette changes rather than just exchanging foreground/background shading. East remains an exact mirror of west. The existing dark outline is applied to the new leg contours.

Normal/shiny RGB555 palettes, native dimensions, texture metadata, runtime positions and timing are unchanged. A new toe contour can extend the visible foot by one native pixel within the existing canvas. North/south walking pixels, menu icons and battle fronts are unchanged.

## Validation

- Both starter-trio ROMs built successfully; **413 asset checks passed per ROM**.
- All 44 back frames (11 species x 2 genders x 2 frames) round-trip through native NCGR encoding with their original keys and headers.
- All 88 follower frames round-trip between authoring PNG and NSBTX textures. Both palettes and all non-texture bytes are preserved; only the 44 side-facing frames changed.
- Both side silhouettes differ for every species, and east/west pairs mirror exactly.
- DeSmuME captures cover all eleven normal species entering a real battle and walking east/west outdoors in HeartGold. Per-species screenshots, GIFs, input-save hashes, ROM hashes and run logs are under `runtime/`.
- The HeartGold ROM comparison against `ece5bf66b` changes exactly 22 custom back members in `a/0/0/4` and 11 custom follower members in `a/0/8/1`. ARM code, overlays and all other archived files are identical.

Battle fixtures are disposable copies of the pre-rival save with the lead species/name changed; their level and HP are fixture data, not tests of stats or evolution. Walking fixtures exit the gatehouse normally before capturing the followers. Early westward frames include turning/catching up to the player. Captures use nighttime lighting. SoulSilver was built and asset-validated; the emulator captures are from HeartGold. These checks establish correct packing/rendering and provide visual evidence; the animation's artistic quality remains a visual judgment.

## Reproduction

The current revision supersedes the side-leg output of `fix_fakemon_pixel_gaits.py` and the back composition in `fix_surguenon_battle_facing.py`. Do not reinstall those older staged outputs over these files.

```sh
python3 tools/py_scripts/revise_fakemon_backs_and_gaits.py --output /tmp/closeup-gaits-staged
```

The script reads immutable `ece5bf66b` assets and uses the pre-regression body art from `c020456f4`. Copy each species' `battle-0.bin`, `battle-1.bin`, `follower.bin`, `source/{female,male}/back.png` and `source/overworld.png` into `files/fakemon/<species>/`. Refresh the corresponding hashes in `files/fakemon/assets.json`, then:

```sh
python3 tools/py_scripts/pack_fakemon_followers.py --check-current
./tools/build_starter_trio.sh
python3 tools/py_scripts/validate_fakemon_assets.py --rom build/heartgold.us/heartgold-fakemon-starters.nds --output /tmp/hg-assets.json
python3 tools/py_scripts/validate_fakemon_assets.py --rom build/soulsilver.us/soulsilver-fakemon-starters.nds --output /tmp/ss-assets.json
```

The build updates only the two starter-trio ROMs. Load an ordinary in-game save after reopening the ROM; an old emulator savestate may retain the previous graphics in memory.

## Built ROM SHA-256

- `heartgold-fakemon-starters.nds`: `812ac4d198c71e6243cea389175ccc0c4f6757f9dfad491ed5c881043a60b951`
- `soulsilver-fakemon-starters.nds`: `f2581160a2499dd004b2a95b65ba699c0a70a1fb197e4c8ec7c7be8e3ce03230`
