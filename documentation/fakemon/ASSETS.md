# Approved Fakemon assets in the stock engine

The goal is to render and play the eleven already-approved designs and cries in the stock HeartGold/SoulSilver engine, while preserving every original species resource and sound. This port does not redesign the creatures.

## Imported material

`files/fakemon/` contains the approved indexed PNG sources, normal/shiny follower palettes, the final native graphic payloads, the approved PCM16 cry sources, and the complete approved species metadata. `assets.json` records the source hg-engine ROM SHA-256 and each installed payload SHA-256. The initial native battle/icon/follower payloads were extracted from the previously validated hg-engine build. This branch subsequently corrects palettes and replaces follower walking poses and sizing; see [graphics revision](graphics-revision/README.md). Battle pixel indices and menu icon resources remain unchanged. The source ROM hash records the original import, while each payload hash describes the currently installed asset.

All eleven have actual custom front and back battle art, two 80×80 frames in each facing, normal and shiny palettes, two-frame menu icons, and four-direction/two-frame followers. Male and female resources use the same approved design. Battle palettes have sixteen RGB555 entries; transparent index zero leaves fifteen visible colors. Followers use the approved 32×32 or 64×64 frame sizes. The eleven cries are separate family-related sounds, not canonical Pokémon samples; external environmental sample credits are in `files/fakemon/CRY_SOURCES.md`.

There were no approved novel footprint drawings in hg-engine. This port deliberately shares existing anatomically similar footprints: Meowth for the Voltuff family, Charmander for the Embernewt family, and Pidgey for the Sedgling family. These are donor prints, not newly authored custom graphics. The image frames are custom; the brief movement effect uses stock animation template 2, with approved frame 0 for six ticks and frame 1 for twelve ticks. Shadow sizes are one for base forms and two for evolutions. These choices match the prior hg-engine registration.

## Runtime and resource mapping

The game species IDs remain 1076–1086. Sparse IDs are explicitly mapped to appended resources, without altering the meaning of canonical species, eggs or alternate forms.

| Resource | New indices | Integration |
|---|---:|---|
| Battle pictures/palettes (`a/0/0/4`) | species slots 494–504, six members each | `GetMonSpriteCharAndPlttNarcIdsEx`; custom PBR requests use the same approved HG art |
| Height offsets (`a/0/0/5`) | slots 494–504, four members each | zero baseline offsets, matching approved registration |
| Menu icons (`a/0/2/0`) | 551–561 | `pokemon_icon_idx.c`, stock icon palette 0 or 2 |
| Follower models (`a/0/8/1`) | 863–873 | map-object sprite tags 1050–1060, small/large callbacks |
| Follower behavior (`a/1/4/1`) | 566–576 | `SpeciesToOverworldModelIndexOffset`; evolved large forms cannot enter narrow interiors |
| Footprints (`a/0/6/9`) | species ID + 3 | safe empty footprint records fill the unused ID gap |
| Cry bank and wave archive | 778–788 | appended to stock SDAT; `PlayCry` and `PlayCryEx` resolve custom IDs |
| Names/classifications/measurements | message indices 1076–1086 | original message rows are preserved |
| Dex prose | 1076 + species offset + 11 × page | three lines per page; Fimbulisk has three pages, other species two |

The follower palette selection also recognizes the new map-object tags, so normal and shiny followers select their own palettes. Hall of Fame and certificate model lookup use the same compact follower mapping. Six battle animation record readers share a custom-only record generator; canonical records continue to load from their original archive.

Cry sources are mono PCM16 at 16,384 Hz. Import converts them to signed PCM8, pads to the native four-byte boundary, and stores the original sample rate in each SWAV. The stock sound player uses its existing universal cry sequence with the custom bank. Existing fainting/pitch-modified cry patterns remain stock effects; listen to these patterns as well as ordinary cries during manual review.

`zukan_data.json` retains the original 494 metric records and adds safe gap records through custom species ID 1086. Heights/weights come from the approved metadata. Scale and offset fields match the prior hg-engine registration (scales 256, offsets 8); visual comparison against the trainer still needs review.

## Reproduction and checks

Normal `make COMPARE=0` needs Python3 but no external Python package for the asset overlay. After each stock archive is copied to its numbered filesystem path, `apply_fakemon_assets.py` appends only the listed resources. It asserts that no existing member is overwritten and verifies all original members after repacking. Changed custom asset sources trigger a fresh copy and overlay, preventing duplicate appends.

Re-importing from the approved hg-engine working tree requires `ndspy` and one completed stock-port build (which supplies the canonical donor footprint archive):

```sh
python3 -m venv .venv
. .venv/bin/activate
python3 -m pip install ndspy Pillow
python3 tools/py_scripts/import_fakemon_assets.py --hg-engine ../hg-engine
python3 tools/py_scripts/import_fakemon_cries.py
python3 tools/py_scripts/import_fakemon_text.py
```

The asset importer expects the approved `../hg-engine/test.nds` and source art. Re-running it restores the original import and overwrites this branch's later palette/follower corrections; replay the graphics revision afterward. These are provenance/import tools; ongoing stock-port builds use the checked-in assets and do not depend on hg-engine. The cry importer preserves all original sequences, banks and wave archives and checks them after serialization. It is safe to rerun; only the eleven custom trailing sound records are regenerated.

After building:

```sh
python3 tools/py_scripts/validate_fakemon_assets.py \
  --rom build/heartgold.us/pokeheartgold.us.nds \
  --output documentation/fakemon/asset-validation.json
```

The validator checks payload hashes and indices, every original member of the six affected graphics/behavior archives, native palette limits and source dimensions, canonical audio records against upstream commit `9d8b7591f09b65804da2fb2dfd56f320633e0d36`, custom cry links/formats, and reconstruction of the complete approved prose from the message pages. It requires `ndspy` and Pillow. A report without a `rom` value covers generated filesystem assets, not packaged ROM or emulator behavior.

## End-to-end behavior to test

Use disposable copies of saves and ROMs. The base `fakemon-stock` branch leaves the species unobtainable; this `fakemon-starter-trio` edition deliberately gives the three base forms in Elm's introduction. Use the compatible editor branch or a disposable fixture for evolved/shiny cases. See [STARTER_TRIO.md](STARTER_TRIO.md).

1. For each species, inspect both sexes, normal and shiny, in party, summary, PC boxes, battle as player and opponent, evolution preview/success, hatching and Hall of Fame. Verify the intended species image and name, transparent backgrounds, intact outlines, correct shiny colors and both animation frames. Check sprites against HP bars, platforms and shadows for clipping or bad baseline alignment.
2. Walk each follower north/south/east/west, turn while stationary, follow through doors and stairs, ride a bike, Surf, change maps, save/load and swap party leader. Inspect two walking frames, shiny selection, correct small/large display size, and the large-form interior restriction. Verify that the four-armed Raijinque and four-winged Ragnaroc remain visually readable at native resolution.
3. Play cries from the summary, send-out, follower interaction, evolution and fainting paths. Listen for the approved distinct family voices, full duration, correct pitch and loudness, no clipping/clicks or endless loop, and appropriate stock pitch effects on fainting. Confirm Chatot recording and Shaymin Sky cries still work; sample several canonical cries and music/SFX transitions.
4. Open all custom Dex entries. Cycle every page and reconstruct the complete supplied prose, including Fimbulisk's third page. Check line wrapping, classification, height/weight units, body-shape search, size comparison, normal/shiny pictures and donor footprints. Verify canonical pages, species sorting, languages, form controls and Deoxys/Shaymin forms remain intact.
5. Repeat the critical graphics/audio/Dex checks in both HeartGold and SoulSilver. Exercise mixed parties and boxes with canonical and custom species and a save/editor/game/save round trip.

Passing archive checks proves resource placement and isolation; it does not by itself prove animation timing, audio quality, UI layout, map-object behavior or hardware performance. Record emulator/hardware evidence and any failures separately from the static report.

## Cry sample attribution

The approved synthesized varan cries incorporate CC0 fireplace and snowstorm samples. See [`CRY_SOURCES.md`](../../files/fakemon/CRY_SOURCES.md) for author credits and source links. Existing Pokémon cries were comparison references, not samples in the new voices.
