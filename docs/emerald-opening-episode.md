# Opt-in Emerald opening episode: source reproduction

**Source reproducibility is established for the corrected Route 101 opening
candidate (V8r2). Native runtime verification is incomplete: the tested run froze
after its first post-battle step. Full Stage 1 campaigns remain incomplete.**
These tools do not build a ROM, launch a game, install into a build cache, or
establish gameplay success.

The default checkout remains the 540-map baseline with its existing travel-only
behavior and tests. The episode is generated only when explicitly requested.
For earlier probes and their distinct evidence boundaries, see
[current scope and travel preparation](../expansion/EMERALD_OPENING.md#current-scope-private-probes-not-completed-campaigns)
and the [validation record](../expansion/VALIDATION.md).

## Current verification boundary

Owner-local checks passed all 92 source tests without skips, the unchanged
540-map default baseline, and the fresh compiled candidate's archive and script
inventory audits. A cold native run reached the chase, a natural wild-battle
victory, and Birch's thanks without savestates or gameplay-memory changes.

That run then stopped responding after one field step. Its rendered images
remained byte-identical across subsequent direction and menu inputs, and the
emulator reported repeated empty-register-list instructions. This establishes
frozen execution, **not** a diagnosed terrain collision or a proven cause.
The reward, nickname, duplicate-gift guard, and expanded-HeartGold editor
export/cold-reload journey are not certified by this run. Earlier editor tests
and earlier candidates must not be substituted for those missing checks.

The generated manifest deliberately retains `runtime_verified: false`.
Reproducing candidate source bytes does not make this a completed opening or
establish storage capacity for both complete imported campaigns.

## Required owner-local inputs

Use the tracked source checkout and user-owned Emerald donor/source assets.
The donor revision must be
`c925b8482d05fb882d6b64e523653cae599e025f`; relevant native and donor file contents
are also pinned. A matching revision alone does not authorize changed assets.
No donor graphics, ROMs, saves, proprietary tools, or licenses are distributed
by this procedure.

Prepare these inputs with the existing tracked tools:

| Composer option | Required input and producing tools |
| --- | --- |
| `--root` | This tracked source checkout. Defaults to the checkout containing the composer. |
| `--donor` | Owner-local Emerald checkout at the pinned revision. |
| `--lab-assets` | Solid, aligned lab export: extract `LittlerootTown_ProfessorBirchsLab` with `extract_emerald_lab.py --donor … --map … --output …`, then run `export_lab_model.py --pack … --output …`. |
| `--packs` | Parent directory containing exactly named `LittlerootTown-pack` and `Route101-pack` inputs. Generate each with `extract_emerald_lab.py --donor … --map LittlerootTown` or `--map Route101`, respectively, and `--output` pointing to that named directory. |
| `--resources` | Three-map resource overlay from `stage_emerald_opening.py --root … --lab-assets … --town-assets … --route-assets … --output …`. Produce the town/route exports from their packs using `export_emerald_outdoor_model.py --pack … --output …`, with the default **conservative** terrain profile, not a grass-probe profile. |
| `--actor` | The pinned `birch.nsbtx` file produced by `export_birch_actor.py --root … --donor … --output …`. Required here, unlike the optional actor argument of the travel-only preparer. |

See the existing procedures for
[lab extraction](../expansion/EMERALD_OPENING.md#reproducible-lab-donor-graphics),
[lab export](../expansion/EMERALD_OPENING.md#flat-nitro-model-export-checkpoint-unhooked),
[exterior exports](../expansion/EMERALD_OPENING.md#exterior-asset-authoring-checkpoint-uninstalled-flat-prototypes),
[three-map resource staging](../expansion/EMERALD_OPENING.md#three-map-emerald-resource-staging-uninstalled),
and [Birch authoring](../expansion/EMERALD_OPENING.md#birch-actor-texture-authoring-resource-only-exporter).
The episode composer generates the bag, Zigzagoon, and compact map assets itself;
it does not consume a private predecessor episode tree.

## Prepare a fresh episode source tree

Set the shell variables below to your own input locations. Set `PREPARED` and
`OVERLAY` to distinct, **not-yet-existing directories outside the checkout and
all input directories**. Prefer persistent storage. Do not point either output
at an existing source tree or build cache.

```sh
python3 scripts/prepare_emerald_episode.py \
  --root "$ROOT" \
  --donor "$DONOR" \
  --resources "$RESOURCES" \
  --lab-assets "$LAB_ASSETS" \
  --actor "$BIRCH_TEXTURE" \
  --packs "$PACKS" \
  --output "$PREPARED"
```

This reuses the travel preparer and produces a separate source tree plus
`opening-episode.json`. The manifest records producer/input hashes, complete
native-input hashes, archive-member preservation, and explicit
`runtime_verified: false`. It contains no machine-specific input paths.

The corrected map texture goes into **`files/a/0/4/4`, member108**.
The unrelated overworld `mmodel_00000108.NSBTX` remains unchanged. Land678,
the 32768-byte compact atlas, actors, episode scripts/messages, and map labels
are regenerated or applied under content checks.

Publication is atomic and refuses an existing destination, including a
concurrently created empty directory. Hosts without the required atomic
no-replace operation fail closed.

## Stage the complete source overlay

```sh
python3 scripts/stage_emerald_episode.py \
  --root "$ROOT" \
  --prepared "$PREPARED" \
  --output "$OVERLAY"
```

The output contains **29 native/source-metadata deltas** and
`episode-overlay.json`. This is the complete tracked-baseline-to-episode
overlay, not just the incremental changes between private episode versions.
It includes `expansion/baseline.json`, changing the map-count baseline from
540 to **543**. Applying the overlay to its matching baseline has been checked
with the real `scripts/check_expansion_baseline.py`.

The stager does not trust the prepared manifest as an authorization source.
`scripts/episode_templates/approved_deltas.json` independently pins every
approved output and baseline preimage; all other native inputs must match the
baseline. Changing both a prepared source file and its claimed hash is rejected.
Authorization is content-based, not tied to a hardcoded producer Git commit.

Sources are written with honest current modification times. The stager does
**not** apply the overlay to a cache. Any separately approved cache integration
must preserve fresh source mtimes or correctly invalidate dependencies; do not
extract epoch/old timestamps over compiled outputs or touch outputs to simulate
freshness.

Complete source comparison retains one explicit historical distinction: the
current tracked map-matrix incremental-dependency recipe is kept, rather than
reverting to the older private recipe. This is not a gameplay-data exception.

## Optional compiled-script inventory audit

Compilation is a separate operation. The default
`build_native_field_scripts.py` and `scr_seq.sha1` validation policy are unchanged.
The opt-in `verify_compiled_inventory` function checks an already compiled
episode directory; it neither compiles nor discovers trustworthy episode hashes.

Obtain **independently approved SHA-1 values** for exactly these three banks:

- `scr_seq_0843_T20R0101.bin`
- `scr_seq_0965_hoenn_reward.bin`
- `scr_seq_0966_route101_opening_hdr.bin`

Store those name-to-hash pairs in an owner-local JSON object, then call:

```sh
python3 - "$ROOT" "$COMPILED_BANK_DIR" "$APPROVED_BANK_HASHES_JSON" <<'PY'
import json
from pathlib import Path
import sys

root, compiled, pins_file = map(Path, sys.argv[1:])
sys.path.insert(0, str(root / "scripts"))
from episode_source_inventory import verify_compiled_inventory

pins = json.loads(pins_file.read_text())
print(verify_compiled_inventory(compiled, root / "scr_seq.sha1", pins))
PY
```

Do not derive these approval pins from the same unreviewed binaries being
audited. The function requires the pinned original baseline manifest, all
964 unaffected banks to retain their original hashes, and exactly 967 compiled
banks in total. Passing this audit is not runtime or campaign verification.