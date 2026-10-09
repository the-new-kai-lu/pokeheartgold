# Building and entering the Stage 1 prototype

This guide is for the completed opening checkpoint described in
[STAGE1.md](STAGE1.md), not the full Hoenn/Sinnoh import. Stage 1 has resumed
bulk regional integration; the checkpoint remains available independently.
The default checkout still builds its baseline maps; the episode is an explicit
opt-in source build.

## Inputs

- Use this expansion fork, not an unmodified upstream checkout.
- Supply your own Emerald donor checkout at
  `c925b8482d05fb882d6b64e523653cae599e025f`.
- Prepare the lab, town/route packs, resource overlay and Birch texture using
  the tracked procedures in
  [the opening episode guide](../docs/emerald-opening-episode.md#required-owner-local-inputs).
  Its composer generates a fresh opening source tree without requiring a
  private predecessor episode. Use that tree as `OPENING_SOURCE` below.
- Use the already working native toolchain setup. The supplied baseline uses
  NitroSDK **3.2**; do not substitute the 4.2 version mentioned in the inherited
  installation guide. Keep compiler, SDK and license material private. The
  source preparers do not install a toolchain or copy a license.

All output variables below must name fresh directories outside the repository
and input trees. Do not overwrite an existing save, source tree or build cache.

## Compose the bounded episode

From the expansion checkout, set `ROOT` to that checkout and set the other
variables to your own input/output paths:

```sh
ROOT="$PWD"

python3 "$ROOT/scripts/prepare_oldale_candidate.py" \
  --root "$ROOT" \
  --episode "$OPENING_SOURCE" \
  --donor "$DONOR" \
  --output "$OLDALE_SOURCE" \
  --author-unapproved-oldale

python3 "$ROOT/scripts/prepare_campaign_save.py" \
  --root "$OLDALE_SOURCE" \
  --output "$CAMPAIGN_SOURCE" \
  --script-bridge

python3 "$ROOT/scripts/prepare_oldale_potion.py" \
  --episode "$OLDALE_SOURCE" \
  --campaign-source "$CAMPAIGN_SOURCE" \
  --donor "$DONOR" \
  --output "$STAGE1_SOURCE" \
  --author-unapproved-oldale-potion
```

The preparers deliberately label newly generated outputs unapproved and
runtime-unverified. The recorded R5 observations apply to the particular tested
build, not automatically to every future output. Do not edit old manifests to
claim that a different build was tested.

## Build

Use the generated `STAGE1_SOURCE` in the configured SDK-equipped build
environment, with the source-relative tools required by `INSTALL.md` available.
Use the existing license location; do not add a license to the repository.

```sh
cd "$STAGE1_SOURCE"
WINEDEBUG=-all make -j4 \
  GAME_VERSION=HEARTGOLD GAME_LANGUAGE=ENGLISH GAME_REMASTER=0 COMPARE=0 \
  LM_LICENSE_FILE="$SDK_LICENSE_FILE"
```

The image is `build/heartgold.us/pokeheartgold.us.nds`. Retail comparison is
disabled because this is an expanded build. Preserve honest source timestamps
and let the build regenerate affected outputs; do not substitute an old ROM
or change hashes to make a failed build pass.

The known-good native build ran in the configured compiler VM. A previous
host-only Wine/WoW64 attempt did not work; that failure is not a reason to
reinstall or change the working toolchain for every small edit.

## Play the episode

1. Start a disposable new expanded-format game and obtain a Johto starter
   normally. Do not import an old vanilla save as if it were this format.
2. Talk to Elm after receiving the starter. The prototype entrance takes you
   to the Hoenn lab. This is a development entrance, not final story integration.
3. Use the ordinary lab door and walk through Littleroot to Route 101. Complete
   the rescue battle using the existing Johto party, then return to Birch's lab
   for a Hoenn starter. The recorded native path chose Treecko.
4. Travel north to Oldale. Approach the Mart employee from the south for the
   recorded escort/Potion path. The grant is one-time and persists through
   native saving and Continue.
5. Walk back through Route 101 and Littleroot to the lab. The right-hand
   assistant is the prototype return to Elm's lab in Johto. Ordinary Johto
   events, including the lab assistant's own Potion gift, can still occur.
6. Talk to Elm to revisit Hoenn. Previously received rewards should remain
   received. Save normally and close the emulator before copying the save.

The route's open path bends around trees and ledges; it is not a straight
north/south corridor. Do not walk through sealed tiles or use debug state
changes to substitute for the actual battle, rewards or travel.

## Supported editing and limits

Use the project's PKHeX/PKMDS forks with the expanded-format Core, never stock
upstream editors. The exercised source revisions are PKHeX
`b7c732fd64d80f77ac947c5ec101b6ba3f2b9de0` and PKMDS
`d2ac478a2a723116a72e16d4bc0bf4da13ce5d47`.
For a PKMDS source build, use its documented `UseLocalPKHeX=true` /
`PKHeXSourcePath` override to consume that fork, rather than the stock package.
Keep the original save and export edits to a separate file.

Known prototype limits:

- HeartGold is the current native completion target. Earlier SoulSilver
  evidence does not certify this expanded build; hardware is not qualified.
- Oldale interiors, other town interactions, Routes 102/103, rival events and
  full regional campaigns are not included. Closed borders are intentional.
- Travel entrances, some dialogue and actor placement remain prototype/debug
  presentation. The Route 101 north-edge rendering has a known black band.
- The recorded Potion escort used the south approach. Other approach directions,
  bag-full/failure paths and broader release matrices are not newly certified.
- The latest progressed-save regression used the shared editor codec plus a
  native cold readback, reusing earlier real GUI checks. It was not another full
  two-frontend or populated-PC gameplay test.

For unchanged code, retain the existing evidence. A dialogue edit needs a
focused text check, not another complete playthrough or compatibility matrix.