# Native-pixel walking and battle-facing correction

> The side-walking poses have since been revised. See [close-up backs and jointed walking](../closeup-backs-and-gaits/README.md) for the current assets and reproduction instructions.

This revision replaces the earlier generated foot-strip edit, which made the side gaits stiff and failed to show clear alternate steps on the evolved forms. The user authorized direct pixel editing after reviewing that regression.

## Walking

All eleven species now use hand-authored hip/knee/ankle/toe poses at the actual 32- or 64-pixel canvas size. The near leg is lighter than the far leg. Bipeds exchange the leading/trailing foot; quadrupeds exchange diagonal pairs. Foot baselines, canvas registration, normal/shiny RGB555 palettes, and all north/south texture data are retained. East is the exact mirrored west pose. No AI-generated leg crops or resampling are used in this pass.

[Two-frame walking preview](walking.gif) | [Phase A](phase-0.png) | [Phase B](phase-1.png) | [In-game frames for all eleven](all-runtime-steps.png) | [Large followers outdoors](large-runtime-steps.png)

Reproduce from the immutable pre-regression art (commit `c020456f4`):

```sh
python3 tools/py_scripts/fix_fakemon_pixel_gaits.py --output /tmp/pixel-gaits
```

The script stages each species' `follower.bin` and `source/overworld.png`; copy them into the corresponding `files/fakemon/<species>/` folders and refresh follower hashes in `files/fakemon/assets.json`. Joint coordinates, rectangles removing the old legs, and palette indices are explicit in the script. `checks.json` records the resulting joints and native hashes. The bottom row assertions prevent a one-pixel increase in follower height.

This script supersedes `pack_side_gait.py` and the west/east output of the original graphics-revision workflow. Those files remain historical evidence, not the current regeneration procedure.

## Battle facing

Surguenon's front view faced right and its back view faced left, away from the respective opponent. Both 80x80 frames in each male/female front/back sheet are now individually mirrored. Frame order, colors, encryption keys and NCGR headers are preserved. The other ten species were visually audited in both views and did not show the same obvious reversal; their battle art remains unchanged. This is an art correction, with no runtime mirroring logic change.

[Before/after art](surguenon-before-after.png) | [Actual player-side battle](surguenon-battle.png)

Reproduce the battle patch from commit `293b55002`:

```sh
python3 tools/py_scripts/fix_surguenon_battle_facing.py --output /tmp/battle-facing
```

Copy the four staged `battle-0.bin` through `battle-3.bin` files and four PNG sheets into Surguenon's asset folder; refresh their manifest hashes. The existing `.png.key` files and battle palettes do not change. Nitrogfx converts the indexed sheets with the stock `-scanfronttoback -handleempty` options.

## Verification

- All 88 source/native follower frames round-trip, including unchanged north/south frames and both unchanged palettes.
- All eight corrected Surguenon battle frames decode exactly to their indexed PNG sources. [Battle round-trip report](battle-roundtrip.json). Nitrogfx's palette-free decode emits inverted grayscale; comparison maps it back to indices before asserting equality.
- Both final starter ROMs pass 413 packaged-asset checks each: [HeartGold](heartgold-validation.json), [SoulSilver](soulsilver-validation.json). Reports include exact ROM hashes.
- All eleven normal-color followers were exercised left and right in HeartGold. Seven were checked in the gatehouse; the four large final forms were taken outside through the actual gate transition because stock indoor rules hide them. The saved 22 clips contain 592 native frames. Review the moving portions: the starts include turning or a follower emerging from its ball. [Per-species captures and inputs](runtime/).
- The final HeartGold ROM was also cold-loaded for a real Silver battle using a disposable fixture with Surguenon leading. Its back sprite faces the opposing Chikorita. [Run metadata](battle-runtime.json). The fixture retains the stored name Voltuff because its species was changed solely to inspect the graphics; it is not a natural evolution test.
- Shiny followers and the female/enemy-facing battle views were checked as native assets, not all played in battle. SoulSilver passed packaged checks; gameplay evidence uses HeartGold.
- Compared with the previously delivered HeartGold ROM, code, overlay tables and every filesystem file except the battle/follower archives are byte-identical. Only Surguenon's four battle members and eleven follower members changed. [ROM delta](rom-delta.json). Story events, items, stats, moves and save layout remain intact.

Build both editions with `./tools/build_starter_trio.sh`. Use an ordinary in-game save when checking replacement graphics; an emulator save state can restore cached old sprite data.

## Follow-up: Surguenon party/box icon

The party icon is a separate 32x64, two-frame resource and was missed by the battle-facing patch. Both frames now face left. The shared palette, warmed colors, transparency, frame order and NCGR header are unchanged. `warm_electric_icons.py` now includes this reflection after its color correction, so regeneration preserves the fix.

[Before/after](surguenon-icon-before-after.png) | [Actual battle party menu](surguenon-party-icon.png) | [Native checks](icon-facing-checks.json)

Both rebuilt ROMs pass 413 asset checks: [HeartGold](icon-heartgold-validation.json), [SoulSilver](icon-soulsilver-validation.json). These icon reports supersede the prior final ROM hashes. The new HeartGold battle party-menu capture uses the exact rebuilt ROM ([runtime report](icon-runtime.json)). Compared with the preceding walking/battle build, only Surguenon's icon member 552 in `a/0/2/0` changes; battle graphics, followers, code and other files remain identical ([delta](icon-rom-delta.json)).

## Later icon outline pass

The current party/box icons also include [one-pixel stock-dark contours](../icon-outlines/README.md). That page contains the latest ROM hashes and party-screen evidence; the walking and battle-facing corrections here remain unchanged.

## Later walking-sprite outlines

The latest build also applies [one-pixel dark outlines to all walking frames](../follower-outlines/README.md). That page contains current ROM hashes and in-game evidence. The menu icons and battle-facing corrections are preserved.
