# Opt-in Emerald opening episode: source reproduction

**The resume-safe Route 101 candidate (V8r4) passed one owner-local HeartGold
journey through natural rescue victory, party-menu return, Treecko gift,
the in-game nickname LEAF, native save and cold reload. Actual PKHeX and PKMDS
money edits also survived a shared-byte game reload, native Johto resave,
and another cold restart/revisit. A later populated-PC PKMDS nickname edit
passed native readback/resave; the corresponding PKHeX Main-form edit failed
strict met-location preservation and remains unresolved.
Full Stage 1 campaigns remain incomplete.**
These tools do not build a ROM, launch a game, install into a build cache, or
establish gameplay success.

The default checkout remains the 540-map baseline with its existing travel-only
behavior and tests. The episode is generated only when explicitly requested.
For earlier probes and their distinct evidence boundaries, see
[current scope and travel preparation](../expansion/EMERALD_OPENING.md#current-scope-private-probes-not-completed-campaigns)
and the [validation record](../expansion/VALIDATION.md).

## Current verification boundary

The resume-safe V8r4 source passed all 102 owner-local tests without skips and
the unchanged 540-map default baseline. Fresh preparation and staging matched
all 14,882 native inputs against V8r3, with only the reviewed init-header delta.
Actual assembled HG and SS headers differ only in the init-type byte (4 to 3).
Those static checks are separate from the recorded native HeartGold checks:

- The matching native build passed natural rescue victory, Birch's thanks,
  field walking, opening and closing the party screen, the Treecko gift,
  native LEAF nickname entry and in-game Save. An untouched-save cold run
  then verified party, walking and the already-received gift guard.
- Actual PKHeX and PKMDS each independently changed only money 3000→3001,
  exported a new DSV and reopened it. The outputs were byte-identical.
  Read-only comparison preserved identity, position, party, all 540 PC slots,
  all work/flags, both partition story ranges and the DSV footer. The PC was
  empty; this is not a populated-PC test.
- One cold game run of those shared bytes returned normally to Elm and made
  a genuine native save. A fresh cold restart of that game-written save
  verified money 3001, TOTODILE and LEAF, then walked to Elm, revisited Hoenn
  and verified the duplicate-gift guard again.
- A later native travel/heal/PC-deposit/save run established one boxed
  Treecko/LEAF and one party Totodile. Actual PKMDS GUI changed only the boxed
  nickname to LEAF2, exported and reopened it. The strict byte comparison
  passed; a fresh 49-capture native run displayed LEAF2 in Box 1 and saved.
  The game-written file retained all Pokémon data, work and flags with valid
  CRCs, unchanged footer/PC geometry and advancing native save counters.
- The corresponding actual PKHeX Main-form nickname edit was rejected:
  custom met location extended 235 / DP 3002 became 0/0. Its checksums and
  other save data passing do not override that failure. It was not accepted
  or native-tested as a successful export; the comparison gate is unchanged.

See the [validation record](../expansion/VALIDATION.md) for build/save hashes
and the precise scope. The money-only native run covers identical exports,
not two independent game runs. The boxed nickname/native-resave pass is
PKMDS-only; it is not a PKHeX nickname pass, a V8r4 SoulSilver result, or a
full campaign.

Owner-local V8r3 checks passed all 99 source tests without skips and the unchanged
540-map default baseline. Fresh preparation and staging reproduced the approved
source hashes; an independent Nitro model reader decoded the compact model and
texture. These are source/format checks, not native gameplay verification.

The continuous V8r3 native run subsequently passed the chase, ordinary Scratch
victory, Birch's thanks, and three post-battle field steps. Opening the real party
screen worked, but closing it hung before the field returned. Read-only diagnosis
identified an early actor-repair script using a freed terrain manager; normal
party-menu graphics had reused that memory. This is separate from V8r2's model
overrun, and does not justify changing graphics budgets or native allocators.

The earlier V8r2 compiled candidate passed archive and script inventory audits.
A cold native run reached the chase, a natural wild-battle victory, and Birch's
thanks without savestates or gameplay-memory changes. It then stopped responding
after one field step: rendered images remained byte-identical across subsequent
direction and menu inputs. Read-only frozen-memory comparison and an independent
ROM allocator/overlay audit subsequently established that its oversized model
overwrote overlay 2's repel-step routine. This was not a terrain collision or
evidence requiring an anti-piracy workaround.
The reward, nickname, duplicate-gift guard, and expanded-HeartGold editor
export/cold-reload journey are not certified by this run. Earlier editor tests
and earlier candidates must not be substituted for those missing checks.

The generated manifest deliberately retains `runtime_verified: false`.
It describes source reproduction, not automatic sign-off for newly generated
outputs. The recorded HeartGold journey does not certify every opening branch
or establish storage capacity for both complete imported campaigns.

## Model slot safety

The native allocator reserves four **61,440-byte (`0xF000`) model slots**.
V8r2's 94,636-byte serialized Route 101 BMD exceeded its slot by 33,196 bytes.
The loader's `0xE000` read-chunk size is not an aggregate model-size check.

V8r3 packs four GX opcodes per command word and uses one explicit `VTX_16`
followed by three `VTX_XZ` vertices per quad. The serialized BMD is **53,676
bytes**, retaining all 1,024 quads, 4,096 vertices, exact XYZ/UV coordinates,
and unchanged atlas pixels. Terrain, collision, props, scripts, and save layout
are unchanged.

Construction, archive preparation, and final staging enforce a conservative
**57,344-byte (`0xE000`) authoring limit** on the actual serialized model.
This leaves a 4,096-byte policy margin below native slot capacity. A claimed
manifest hash or budget cannot bypass the final archive-member size check.
Independent packed-stream decoding and pixel round-trip tests cover geometry;
V8r3 also passed the continuous native battle-to-field transition and walking.

## Actor repair lifecycle

Script 5 repairs Route 101's actors and uses `MovePersonFacing`, which consults
the dynamic terrain-height manager. Native `FieldMap_Init` invokes OnLoad in
its RESET state, before `FieldSystem_InitMapLoadManager` recreates that manager
in the LOAD state. Returning from a menu can therefore leave OnLoad looking at
freed, reused memory.

The episode init header now selects **OnResume**, after the native manager
initialization and before the first frame-table check. The legacy script label
`Route101_OnLoad` is unchanged; the header selects its actual lifecycle phase.
Regression tests check both the generated header and the native initialization
order. No native allocator, graphics, save format, state allocation, or map
footprint is changed by this correction. The recorded HeartGold build passed
the continuous battle-to-party-return check and the separate save/editor/cold-
reload journey. Static checks alone, and the older separate SoulSilver probe,
do not certify other builds.

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