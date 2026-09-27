# Side-facing follower steps

The previous side frames changed stance without clearly exchanging the feet. This revision replaces west/east contact poses for all eleven custom species, keeping heads, torsos and tails fixed between the side frames.

[Animated art preview](steps.gif) | [Phase A](steps-0.png) | [Phase B](steps-1.png) | [In-game enlarged frames](runtime/east-details.png)

## Art and reproduction

The built-in `image_gen.imagegen` tool edited the three checked-in `*-reference.png` sheets. Exact prompts: [generation-prompts.json](generation-prompts.json). Selected outputs: `electric-steps.png`, `varan-steps.png`, `bird-steps.png`.

`layout.json` records crop registration and native leg rectangles. The packer extracts those leg pixels, quantizes into the existing palette and serializes native NSBTX files, using commit `c020456f4` as immutable input. Both normal/shiny RGB555 palettes and all north/south frames remain byte-identical. No runtime timing, scale or positioning logic changed.

Regenerate with Pillow installed:

```sh
python3 tools/py_scripts/pack_side_gait.py --output /tmp/side-gait-repacked
```

Compare or copy each species' staged `follower.bin` and `source/overworld.png` into `files/fakemon/<species>/`, refresh follower hashes in `files/fakemon/assets.json`, then run:

```sh
python3 tools/py_scripts/pack_fakemon_followers.py --check-current
./tools/build_starter_trio.sh
```

Apply this pass after the older graphics-revision workflow when reproducing current assets.

## Validation

All 88 source/native frames round-trip correctly: 44 side frames revised, 44 north/south retained. The packer asserts side-pair changes occur only in leg rectangles and both palettes stay identical. Per-species results: [checks.json](checks.json).

Both final ROMs pass 413 packaged-asset checks each: [HeartGold](heartgold-validation.json), [SoulSilver](soulsilver-validation.json). Those reports contain final ROM hashes.

HeartGold was cold-loaded in DeSmuME with isolated copies of an existing gatehouse save, separately placing Voltuff, Embernewt and Sedgling first in the party. Six horizontal captures contain 144 native frames. Visual review confirms movement and changing foot poses. Each species' `runtime/` directory contains inputs, ROM hash, GIFs and contact sheets. Initial turning/start delay and wall contact limit the continuously moving portions of these short clips.

Evolved and shiny followers were checked as native assets, not all played in-game. SoulSilver passed packaged-asset checks; gameplay captures for this revision use HeartGold. Existing saves remain compatible.
