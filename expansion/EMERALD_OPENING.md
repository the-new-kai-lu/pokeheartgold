# Native HG controlled rescue WIN/FLEE and genuine-save gift (not Route 101)

A separate **private HG flat-lab probe ROM** from game source `51e26be`
has SHA-256 `266f115debfa5019cbaf5762c12244ab2645ceda8a4a655e102d03928e305658`.
Its private manifest at
`/tmp/hg-real-rescue-probe-b1ca40ad-overlay/probe-manifest.json`
records the new center technical rescue actor (script ID 3); **only
the test tree** removes Elm's simulated rescue eligibility assignment.
The actor calls the unchanged native production bank 965 entry 2:
`WildBattle` against level-2 Zigzagoon (263) using the existing Johto
party. It does not create an authentic Route 101 chase or hook exterior
maps. An old gift message still says `DEBUG LAB: Simulated rescue`;
this **stale technical label** does not mean Elm set eligibility in
this ROM. The parent visually verified gift blocking before battle,
rescue cancellation, native battle **WIN**, receipt, Elm return and
revisit with both gift and rescue guards.

Starting from an unmodified genuine HG one-Totodile save, the real
post-WIN, pre-gift native battery has valid four-block CRCs, rescue
`0x416e=1`, receipt `0x416f=0`, battle result `0x4013=1` and Johto
starter 158. Totodile retained its original identity but **ordinary
battle** changed EXP +17, Speed EV +1, HP 21→20 and Scratch PP 35→32.
The real post-gift native battery then contained Totodile and Treecko,
rescue still 1, receipt 252; Totodile's **entire decrypted bytes match
the pre-gift, post-battle save**, not the pre-battle original. All 2,912
event flags remained unchanged; friendship steps and the receipt
varied between pre-gift and post-gift. Both corrected editor cores load
without mutation and no-op/money-plus-one exports reopen, preserving
current party, story, flags and map. No-op rewrites five box-content
flag/checksum bytes; money-plus-one changes eight. **True cold loads**
of independent edited pre- and post-gift copies visually verified
money 3001, injured Totodile, available menu before gift and guards
after receipt. Treecko remains **retail encounter-illegal**, and Core
tests do not establish desktop/browser UI behavior. The private saves,
reports, hashes and capture scope are in `VALIDATION.md`.

An independent **natural FLEE**, not outcome injection, set battle
scratch `0x4013=5` (`PLAYER_FLED`) and produced a valid native save
with rescue/receipt both 0. The original Totodile's decrypted bytes,
flags and PC were unchanged; normal temporary/friendship variables
progressed. Rescue was re-offered and could be cancelled again. This
does **not** test LOSS: a bounded 29-Leer/HP-6/PP-1 attempt did not
reach a conclusive loss. Caught, interrupted, transient state-2 in RAM
and SoulSilver native rescue also remain untested.

This **controlled genuine-party HG test** validates WIN and FLEE native
battle branches and the post-WIN gift/save/editor loop, **not** authentic
Route 101 placement/chase, production warps, full campaign or Stage 1
completion. Earlier notes that rescue entry 2 is unmapped are historical:
only the isolated debug actor reaches it; production remains unmapped.
No private ROM, save or screenshot is distributed.

# Private HG compact Route 101 visual/traversal probe (not a rescue)

A second **private HG** ROM built successfully from pinned game source
`51e26be` and compact exporter `a08fad6`:
`/tmp/hg-vm-share/pokeheartgold-route101-probe-a08fad6.us.nds`,
SHA-256 `f0676f0b90bd01dd8e0b2a117970a13ee23335f13237d789f60695a40c2b7c56`.
Its *disposable debug map 540* replaces the separate town probe's assets
with Route 101 land/texture; it does not connect two production exterior
maps. Private pre-build manifest:
`/tmp/hg-route101-probe-a08fad6-overlay/probe-manifest.json`.
The 20×20 composite is four compact textures (100 KiB total, 512-byte
palette), with a technical spawn (9,15) and gift/return scientists (8,15)/
(10,15), **not** a Zigzagoon chase or authentic rescue trigger.

Conservative terrain has 132 safe cells in three components (72/33/27,
with 70 safe spawn-component cells after excluding actors); 104
grass/ledge/unsupported cells remain blocked. Parent visual inspection
confirmed the textured floor and actors, movement across route tiles
(9,14), (9,15), (9,16) with no obvious seam, and two complete
**Route → Elm → Route** cycles. Entry and both re-entry screenshots
are byte-identical. This trajectory covered **only left texture
quadrants 0 and 2**: quadrants 1 and 3 are not safely reachable.
Coordinates are inferred from event data/controller inputs, **not RAM
telemetry**. The normal Johto assistant/Potion event progressed unsaved
between transitions. The immutable real HG starter battery was not
overwritten; the probe did not save, grant or restore emulator state.
See `VALIDATION.md` for capture ranges and hashes.

This private Route test and the town test below demonstrate specific
**visual render, limited traversal, and return/re-entry** for both
composites, not connected exterior travel, authentic gameplay, rescue or
full campaign. The generic exporter's `RuntimeVerified=false` concerns
**uninstalled production assets**; the private probe manifest was
written before runtime. Neither test measured allocator free-headroom
or validated future prop/NPC allocation, blocked grass/ledge semantics,
perimeter-negative collision or inaccessible right-side quadrants.
The episode and Stage 1 remain incomplete. No private ROM, save or
screenshot is published.

# Private HG compact Littleroot visual/traversal probe (not a campaign)

An isolated **private HeartGold** ROM built successfully from pinned game
source `51e26be` with compact exterior exporter `a08fad6`:
`/tmp/hg-vm-share/pokeheartgold-town-probe-a08fad6.us.nds`, SHA-256
`8579b8d4827f9cc8d35c1fbefe68e1397dd61d32bc41687f2c7567e901dc589b`.
Only this ROM's disposable debug map 540 uses Littleroot land 676 and
texture 106 (four compact textures: 100 KiB plus a 512-byte palette).
Technical reward/return scientists stand near the spawn; they are **not**
authentic town NPCs. The private overlay manifest is
`/tmp/hg-town-probe-a08fad6-overlay/probe-manifest.json`.

Using a **cold copy** of the real HG Johto starter battery, with no gift,
in-game save or savestate restore in this run, the parent visually verified
the filled composite town floor and technical actors. Input trajectories
with audited conservative terrain connectivity crossed x 15/16 and z 15/16,
visiting all four compact texture quadrants with no obvious seam or missing
texture in the captured screens. Coordinates are inferred from event and
input data, **not** read from game RAM. Two complete Town → Elm → Town
return/re-entry cycles were visually verified; the first and two re-entry
screenshots are byte-identical. The normal Johto assistant/Potion event
progressed unsaved between transitions. Private captures are under
`/tmp/hg-retroarch/town-seriesNNN/` (001–019), with contact sheets
`town-quadrants.png` and `town-returns.png` under `/tmp/hg-retroarch/`.
`VALIDATION.md` identifies hashes and specific captures.

This **specific private HG probe** establishes a render/traversal/return
slice, not production map installation. The generic exporter's
`RuntimeVerified=false` manifest still describes uninstalled assets; the
probe overlay itself was stamped before testing. Route 101 runtime,
perimeter-negative collision checks, native allocator free-headroom and
future prop/NPC allocation are unverified. The composite remains a flat
prototype, not an authentic 3D town, real rescue, playable exterior
campaign or Stage 1 completion. No ROM/save/screenshot is published.

# Native SoulSilver debug gift and real-save checkpoint (partial)

The **private SoulSilver** debug ROM generated from pinned source `51e26be`
and the runtime-verified solid lab assets is
`/tmp/hg-vm-share/pokesoulsilver-solid-51e26be.us.nds`, SHA-256
`cd12c7da629337d3b4204a04a356425fb026b5b4264e2eb99fb84b014aa0bda4`.
Its native `-DSOULSILVER` script build inventoried 966 banks. From an
entirely blank SS battery, with **no HG save conversion**, boy trainer A started
New Game, chose Totodile and saved. That first authentic save has two valid
CRCs for populated partition 1; partition 0 is still erased. The later
post-gift save has both partitions populated and all four block CRCs valid.
The two private immutable battery copies and their hashes are in
`VALIDATION.md`; neither ROM nor battery is committed.

In native SS gameplay the flat lab floor and scientists rendered, menu
cancel did not grant a reward, Treecko joined the existing Totodile after
selection, and the duplicate receipt guard held immediately and on revisit.
Native save, return to Elm, untouched Johto assistant/Potion sequence, and
debug lab re-entry were visually verified. The corrected PKHeX.Core and
PKMDS.Core load the real post-gift SS save without load-time mutation as
SS version 8 (`IsHGEngine=false`). Totodile's decrypted data, all 2,912
flags, and Johto starter selection match the native starter save; receipt
became Treecko (252). Temporary variables reset and friendship steps advanced
during normal play, so no entire-save byte identity is claimed.

Both editors' no-op and money-plus-one outputs reopen valid and preserve
the current 368 variables, 2,912 flags, party and story. Their outputs match
each other, but even no-op changes five box-content-flag/checksum bytes
relative to the input; money-plus-one changes eight. A **true cold load**
of an isolated money-3001 edited SS copy verified trainer A, textured lab,
Totodile/Treecko party, card ID 64300 and money 3001, and receipt guard.
Treecko's vanilla retail encounter legality still fails: native save/editor
compatibility must not be represented as legal encounter origin.

The debug entrance **simulates** Birch's rescue; the real rescue entry is
not connected. SS full-party/PC capacity branches are **not** tested (the
synthetic capacity fixtures below ran on HG only). Authentic exteriors,
Route 101 rescue, full campaigns and desktop/browser editor UI remain
unimplemented or unverified. Earlier SS-pending notes are historical
checkpoints superseded only for this precise SS starter/gift/runtime/editor
loop; Stage 1 remains incomplete.

# Exterior asset authoring checkpoint (uninstalled flat prototypes)

`scripts/export_emerald_outdoor_model.py --pack <extracted-pack> --output
<fresh-directory>` now exports the authentic 20x20 LittlerootTown and Route101
composites into embedded NSBMD, separate NSBTX, and HGSS land containers. Produce
the input with `extract_emerald_lab.py --map LittlerootTown` or `--map Route101`.
No live map, archive entry, NPC, encounter or travel connection is installed.

The shared lab binary builders gained optional dimensions/bounds; their default
lab BMD, BTX and land outputs remain **byte-identical** to the runtime-verified
solid lab assets. Exterior geometry spans world X/Z -256..64, donor/native
terrain cells 0..19. The compact version uses **four distinct rectangles**,
256x256 + 64x256 + 256x64 + 64x64, four materials and four precisely adjoining
quads with UVs 0..1. This is not four padded 256x256 textures. Materials retain
the corrected non-wireframe SDK flags and share one 512-byte palette.

The previous 512x512 texture layout was **unsafe to install**, not just
unmeasured: its 262144 bytes consumed the entire field texture budget. Native
field setup uses banks A+B (`src/field/fieldmap.c:440-453`); render/VRAM
initialization uses two 128-KiB slots (`src/gf_3d_render.c:42-43`,
`src/gf_3d_vramman.c:7-8,22-25`) with the contiguous manager in
`lib/asm/nnsys.s:2896-3027`. Area texture allocation precedes prop allocations
in the same pool; allocating the entire pool to this map cannot leave room
for them.

The actual TEX0 encoded upload is now **102400 bytes (100 KiB)** and the exporter
enforces that map budget. The field texture pool has 159744 bytes left before
other allocations; that arithmetic is **not proof that props or NPCs fit**.
`RuntimeVerified=false` remains explicit in the generated manifest. Before
production integration, a bounded native allocation probe must measure
simultaneous area/map, props, NPCs, palette and transition allocations,
including failure and cleanup paths. At this **authoring checkpoint**, no
ROM/runtime test was available; later specific private HG Littleroot and
Route 101 render/traversal probes above do not supply that allocator
measurement or validate connected production exteriors.

The two authentic composites contain 46 and 25 visible colors respectively.
Tests reconstruct every BGR555 pixel losslessly; excessive palette counts fail
instead of silently quantizing. Independent apicula decoding of both embedded
and external-texture variants verifies all four material/texture bindings,
per-quad world vertices, adjoining boundaries and UVs. Multi-entry dictionaries
also pass runtime-style Patricia lookup tests; the decoded TEX0 upload size is
checked independently against the enforced budget.
All 41 host tests pass with APICULA supplied, the baseline
contract reports no errors, and the diff whitespace check passes.

Terrain is deliberately conservative and **not a production traversable port**:
only interior donor cells with collision 0, elevation 3 and ordinary behavior 0
become native ordinary floor. All outer perimeter cells and native padding are
blocked. Unsupported behavior/elevation cells (5 in town, 104 on Route101,
including its grass cells) are enumerated and blocked until native semantics
are authored. GBA grass, ledges, doors and elevations are not copied into HGSS
terrain bits. The eight occluded unavailable lower quadrants in town remain
disclosed; a flat opaque composite cannot reproduce foreground occlusion,
height, animated tiles, or NPCs. These are resource prototypes, not an authentic
playable episode or Stage 1 completion.

Private generated land SHA-256 evidence (no graphics or binaries committed):

- LittlerootTown:
  `f27a2c4acc5b6af30c29e6622faad7dacbc6cb42c7308955353c38b84d5e4831`
- Route101:
  `e5e597c025fe5749cb174a826a87a0ccb6e1b61adc90055aef3650b9a881a2d8`

# Native HG capacity and deferred collection (synthetic disposable fixtures)

Four separate editor-constructed **synthetic disposable** native HGSS battery
fixtures, not real accumulated gameplay saves, each held six Totodile clones,
rescue `0x416e=1` and no receipt (`0x416f=0`). In the same corrected private
HG debug ROM, native gift handling put Treecko in the first empty PC slot:
slot 0 with an empty PC, or slot 539 when the other 539 slots were occupied.
The six existing party Pokémon were unchanged; the last-slot case preserved
the other 539 box Pokémon. Each successful gift recorded receipt 252. With
all 540 slots full, refusal left receipt 0 and all six party/540 box Pokémon
unchanged in the **completed in-game save**. An isolated copy of that saved
full-storage result, with only slot 539 freed, cold-loaded and delivered
Treecko into exactly that slot on retry; the receipt then blocked a repeated
grant. All four output batteries have valid native block CRCs.

Private audit JSON and batteries are at
`/tmp/hg-capacity-runtime/{empty,last,full,retry}/`; for the full-storage
saved evidence use `full/saved-complete`, not the unfinished `full/saved`
capture. The parent visually verified gift, refusal, retry and guard panels
in the private capacity contact sheet. Neither these synthetic inputs nor the
ROM or screenshots are committed. The authentic real Totodile/Treecko battery
save in the later HG checkpoint is separate, untouched. These capacity cases
are **native HG runtime behavior**, not SS capacity or authentic rescue/
Route 101/campaign tests. At that checkpoint the SS build was still in
progress; see the separate completed SS starter/gift evidence above.
See `VALIDATION.md` for exact battery hashes and qualifications.

# Corrected debug HG runtime checkpoint (partial; not authentic rescue)

An isolated, opt-in **HeartGold** debug ROM from source `51e26be` with the
solid lab export was built locally at
`/tmp/hg-vm-share/pokeheartgold-solid-51e26be.us.nds`
(SHA-256 `cf98258b792fa57cc8a318274ac68488c85c0b6c51ddacbdbfbbb120341f3c07`).
This private path is evidence, not a distributed ROM. A cold native battery
save with Johto Totodile, driven through a persistent emulator core **without
savestate restoration**, reached Elm's opt-in debug lab. The lab's donor
texture now visibly covers its flat model, with both technical scientist
actors present. After a cancellable touchscreen offer, a subsequent Treecko
selection placed level-5 Treecko after Totodile; repeat dialogue guarded
against a second gift. Native save, return via the right scientist to Elm,
re-entry and the guarded lab dialogue were observed. The unchanged Johto
assistant/Potion event ran normally on return.

Both corrected PKHeX.Core and PKMDS.Core read that genuine HG battery save
with four valid native block checksums and no load-time byte changes. Decrypted
Totodile data was unchanged from the real pre-gift save; all 2,912 event flags
agreed; Johto starter `0x4030` stayed 158, while rescue `0x416e` became 1 and
received species `0x416f` became 252. Temporary variables and friendship-step
progress also changed during normal play: this is **not** a claim that every
story/save byte was unchanged. Both editors' no-op and money-edited exports
reopen and preserve the current party/story fields. The identical editor
money-3001 export was cold-loaded into the corrected ROM on an isolated save
copy: textured lab, both Pokémon, trainer card and already-received dialogue
were observed. Treecko has **no matching vanilla retail encounter legality**;
valid HGSS save data is not the same as retail encounter legality. See
`VALIDATION.md` for full hashes, scope and reproducibility constraints.

The debug Elm entrance sets rescue eligibility **without** executing rescue
battle entry 2. The latter remains unmapped and untested in-game. The model is
a technical flat prototype; no Littleroot/Route 101 travel or full Hoenn/
Sinnoh episode, SoulSilver runtime, desktop editor or browser UI is claimed.
The full-party PC/no-space branches were tested only in the subsequent
HG capacity checkpoint documented above. The historical checkpoints below are
superseded only where this specific corrected build supplies runtime evidence.

# Rescue encounter implementation (not yet mapped)

Script bank 965 entry 2, paired with message bank 829, runs `WildBattle`
against level-2 Zigzagoon using the existing party. The opponent matches
Emerald `src/battle_controllers.c:70`; help/thanks dialogue is adapted from
`data/maps/Route101/scripts.inc`. The player can decline/cancel before battle.
State is 0 before acceptance, 2 during battle, and 1 only after native WIN
or MON_CAUGHT. Capture counts as removing the threat, an adaptation for an
established trainer. Fleeing and unknown outcomes do not grant eligibility.
Loss/draw reset state before HGSS WhiteOut. An interrupted state 2 is reset
on re-entry for a new attempt; state 1 never launches another battle.

Native `CheckBattleWon` accepts fleeing, so this scene reads the exact result
through `GetStaticEncounterOutcome` instead. The starter receipt is untouched.
Party members undergo ordinary battle damage/EXP; no Johto flags, starter
choice, or party replacement occurs. Completion is recorded before dialogue.

Compiled-byte tests cover both editions, all native outcomes, unknown outcome,
cancel, interruption/retry, completed guard, and no gift during rescue.
Outcomes are injected: these tests do not execute the native battle engine.
Route 101 chase movement, actor assets, map trigger, lab warp and scene
choreography remain unimplemented. This is NPC-ready archive content, not
a reachable authentic episode. The isolated debug lab still simulates
eligibility explicitly; the running VM's older generated build is untouched.

# Opt-in debug lab hookup

The isolated debug-build generator now attaches map 540 to area/texture 106,
land 676, matrix 288, event bank 491, script 965 and message 829. It clones
Elm's indoor header with followers/phone/radio disabled and no encounters.
Map-count consumers were audited: map-header storage is inferred from its
initializer; map-marking validation compares the limit without changing saved
storage; Pokemon Talk's iteration excludes this no-encounter map. Matrix 288
does not alias special matrix IDs after the existing u8 cache truncation.
No save layout, region bit width or default-game map count is changed.

Generate a **separate disposable tree**:

```sh
python3 scripts/prepare_lab_debug.py \
  --assets /tmp/emerald-lab-aligned --output /tmp/hg-lab-debug
```

Install/link your existing authorized local toolchain into that generated tree
as described in `INSTALL.md` (it is intentionally not copied with `git archive`).
Build there using `make COMPARE=0` for HG or
`make GAME_VERSION=SOULSILVER COMPARE=0`. Never use a valuable save.
The generator refuses an existing output directory and does not edit this
checkout. A regular build of this checkout remains without the test entrance.

In that debug build, talking to Elm **after obtaining the Johto starter**
simulates rescue eligibility and warps to the flat lab at tile (16,19).
Before obtaining the starter, his original script remains available.
The left scientist at (14,17) is explicitly a technical Birch placeholder:
dialogue says `DEBUG LAB: Simulated rescue`. It offers the tested reward menu.
The right scientist at (18,17) warps back to Elm's lab at (6,12).
Returning and re-entering does not clear the gift receipt. Both door tiles stay
blocked; use the return scientist rather than an unfinished exterior warp.
No authentic rescue battle, travel episode, or campaign is implied.

Tests assemble the generated entrance, reward/return bank and actual event JSON
through the repository's native template renderer for both editions, check
script IDs/warp destinations and walkable actor/spawn tiles, and execute reward
delivery against bounded test storage. This is source/compiled-resource hookup,
**not an emulator-tested room**. Full-ROM build, rendering/VRAM, collision and
save/editor round trips in this debug build remain required.

# Archive staging checkpoint

`scripts/stage_lab_archives.py --assets /path/to/aligned-export --output /new/path`
produces an opt-in filesystem overlay: appended land member 676, texture member
106, area member 106 and single-cell matrix 288. All original NARC members
remain byte-identical after packing. Area parameters clone indoor member 1,
retaining prop-list, lighting and flags while selecting the new texture.
Tests validate real references and reject changed asset hashes.

This overlay is **not installed or reachable**: no map header, event bank,
entrance or return warp is attached. It writes only a fresh output directory,
not source archives. The area template's native prop list remains, although the
new land has no prop placements. Texture VRAM and transitions need runtime tests.
The matrix loader takes a u16 index but caches it as u8; 288 becomes 32.
Current special-matrix comparisons are 0 and 212, so neither is triggered.
The sole assembly getter caller passes that value to `MapMatrix_GetMapAltitude`,
which ignores it. No matrix-struct or save ABI change was made.

# Aligned collision checkpoint

Exporter bounds are now -112..96, aligning donor cells to native terrain
cells 9..21. Model, bounding box and BDHC use the same transform. The
manifest-verified 169 cells map collision to native bit15 only: 58 blocked,
109 ordinary floor and two exits held blocked until real return warps
exist. Outside cells are blocked. Exit metadata includes donor, terrain and
world-center coordinates; no GBA elevation or exit behavior is copied raw.
Independent apicula decoding verifies shifted vertices and unchanged UVs.
All 33 local tests pass including all-cell coordinate/collision checks.
This remains an unhooked flat prototype, not tested in-game walkability.

Next binding traced in `asm/overlay_01_021FB878.s`: AreaDataManager_Alloc
loads archive 0x2a into fields at 0x8b0. AreaDataManager_Load uses the first
halfword for archive 0x2b prop list and 0x46 prop textures; second halfword
selects archive 0x2c map texture. The latter undergoes NNS_G3dGetTex and
VRAM allocation. A future appended area must set these references together.
No map/header/archive indices were added here: VRAM, matrix, events and
entrance integration are still unvalidated.

## Previous independent model decode checkpoint

Apicula `3d4e91e14045392a49c89e86dab8cb936225588c`, built from source,
successfully decodes the generated embedded-texture NSBMD and the land model
paired with its separate NSBTX. Both convert to glTF plus a decoded texture.
The external decoder reports one model/material, opaque 256-color texture,
no culling, and unlit/double-sided material. Its decoded vertex positions are
(-104,0,-104), (-104,0,104), (104,0,104), (104,0,-104), with UVs spanning
0 through 208/256 on each axis. This independently validates the resource
tables, separate texture names and display list; it is not an emulator render,
camera test, VRAM allocation test or proof of area-bank runtime binding.
Reproduce the optional external regression with
`APICULA=/path/to/apicula python3 -m unittest discover -s tests -p test_apicula_lab.py`.
Without that executable the external check explicitly skips.

Terrain follow-up: `asm/unk_02054648.s:375-401` reads bit 15 as the
collision result (`sub_020548C0`), while `GetMetatileBehavior` reads the low
byte and `sub_020548EC` reads bits 8–14. Field-control and Blackthorn collision
consumers confirm this is a blocking query, not a raw GBA collision value.
The donor lab has 58 blocked cells, 109 ordinary floor cells, and two
passable behavior-101 exit cells. Do not copy GBA elevation 3 into DS
attribute bits or behavior 101 into the DS low byte. The exit needs a
separately authored warp. Also resolve alignment before emitting live terrain:
the current 208-unit plane has edges at +/-104, whereas a 32-cell land block
has 16-unit cell edges starting at -256. A 13-cell rectangle must be offset
by eight units to align to that grid (for example -112 through 96).
Zero-filled terrain is still a prototype; these findings do not certify
walkability or justify hooking the current plane into a map.

# Candidate episode: Emerald's Birch rescue (gift foundation; episode not imported)

## Reproducible lab donor graphics

`python3 scripts/extract_emerald_lab.py --donor ../pokeemerald --output /tmp/emerald-lab`
extracts the actual 13x13 lab layout (208x208 pixels), three RGBA background
layers, composite preview, all 169 semantic cells and original event definitions.
Output must be a fresh directory. The manifest fingerprints every input and
output; it names the expected donor revision but does not assert an arbitrary
checkout is clean. Building/Lab tilesets use primary tile/metatile cutoff 512,
primary palette slots 0–5 and secondary slots 6–12. Extraction preserves GBA
flips, transparent color zero, BGR555 quantization and background assignments
from Emerald `src/field_camera.c:DrawMetatile`. The preview excludes NPCs and
animation; separate layers retain occlusion information. Collision/elevation/
behavior values are **donor semantics**, not HGSS terrain attributes. Generated
graphics are not committed. Three new tests cover PNG filters/corruption,
tile banks/flips and real donor extraction with lossless cell reconstruction.

The conversion boundary is now concrete: HGSS land archive `files/a/0/6/5`
(`NARC_fielddata_landdata_land_data = 65`) contains 676 members. Its first four
little-endian words are section lengths (terrain, object section, BMD,
collision); HGSS has a further four-byte header word. Member 1 is 15,858 bytes:
lengths 2048/48/13676/66, BMD0 at offset 2116 and BDHC at 15792.
`include/terrain_attributes.h` independently establishes terrain start 0x14
and length 0x800 (32x32 u16 cells). These observations locate the template
boundary, **not** a verified NSBMD/BDHC exporter. Material/texture references,
geometry scale, height planes and collision behavior still need decoding and
runtime validation before appending a playable land member/header. Do not wrap
the PNG in a guessed DS container or rename Elm's lab as an imported map.

## NPC-ready lab interaction (not yet reachable)

Bank 965 now has two entries: zero-based entry 0 retains the preselected claim
API; entry 1 locks input, checks eligibility and receipt, offers Treecko,
Torchic, Mudkip or Choose later (including B cancellation), and calls the same
non-yielding receipt transaction. Separate dialogue handles party delivery, PC
delivery, full storage, cancellation, ineligibility and prior receipt. Full
storage leaves eligibility intact so the player may return and choose again.
Selection does not change Johto starter flags or existing party slots.

The future lab map must pair script bank 965 with message bank 829 and reference
entry 1 using the host event-script numbering convention. No existing NPC or
map is redirected. Appended `msg_0829_hoenn_reward.gmm` contains eleven original
English messages. Nitroarc lexically sorts inputs; `msg.mk` generates otherwise
absent bank 729 from trainer data, making the new archive member 829, not 828.
Field scripts use the current map message bank, not a matching script-bank ID.
All original message sources and original 965 script hashes remain unchanged.

Both editions' assembled interaction branches pass the bounded interpreter
tests; real msgenc encodes all messages. All 21 host tests and the baseline audit
pass. Full native field rebuild: 966/966 hashes per edition match, with bank 965
intentionally updated for this interaction. These tests do not validate DS menu
rendering, NPC positioning, encrypted saves or emulator behavior. A real lab
map/Birch object, rescue scene, travel and runtime tests remain required.

## Current implementation: appended claim bank

This supersedes the historical allocation-blocked notes below. Bank 965,
`scr_seq_0965_hoenn_reward.s`, is included by the existing script archive's
wildcard build without renumbering original banks. It is an executable reward
transaction, **not a reachable lab or imported map**. The selection UI and
rescue scene are not connected yet.

`constants/expansion.h` names existing slots 0x416e/0x416f for rescue state and
received species. Capacity/save layout are unchanged. The claim entry requires
rescue state exactly 1, rejects an existing nonzero receipt, accepts only
Treecko/Torchic/Mudkip in VAR_SPECIAL_x8000, and returns the delivery outcome in
VAR_SPECIAL_RESULT. Zero/invalid choice cancels. It records species only after
confirmed party/PC insertion, without yielding. No-space retains eligibility;
repeated claims after receipt never invoke the gift command. A future lab caller
must lock input and display the outcome. Never reset these slots on map entry.

Candidate-specific review: sys_vars computed accesses cover 0x4036–4039,
0x4043–4044, and 0x4045–4048. Field calls of ScrCmd_530/546 use index zero.
Trainer House's only SetTrainerHouseSprite loop is 0..9 in bank 952.
Object graphics and temporary-variable reset ranges are below these slots.
`test_native_variable_ranges.py` executes the real accessors against bounded
storage; assertion-only checks are not mistaken for release runtime bounds.

Frontier VM review: frontier_system.s's ov80_0222AA40 loads NARC ID 0xb6,
`files/a/1/8/2`. SHA-1 84f012feb89ad18ccba589457d3026b89104f1c6 matches
both edition filesystem manifests. All 11 members lack either candidate
halfword at every byte offset. FrtCmd_061/062 read the saved-variable address
directly from a script halfword. Other Frontier pointers (ov80_0222BE24)
resolve only VM-local ranges 0x8000–0x8013, not saved variables.
Original field banks were independently built/hash-matched for both editions
before this append. This review applies to the pinned source/archive set,
not arbitrary third-party modified saves.

`test_hoenn_reward.py` executes actual compiled claim bytes in a bounded opcode
interpreter for HG/SS: eligibility, all species, invalid/cancel choices,
party/PC/no-space, retry and duplicate receipt after state-copy reload.
Storage uses the separately tested production gift helper. This is not an
ARM/emulator or encrypted-save round trip.

The owner selected **Emerald** for Hoenn and **Platinum** for Sinnoh. This
candidate uses pret/pokeemerald at `c925b8482d05fb882d6b64e523653cae599e025f`;
the future Sinnoh audit is pinned to pret/pokeplatinum at
`c248fb3f8cc9934ded800e489567c5c0eeee92eb`. The HGSS host checkpoint
audited here is `f699b3c01b769f95c07e7d802dd5b7369bb142b2`. These are
**audit revisions**, not imported assets or a change to the original source
pins in `baseline.json`.

## Minimum recognizable flow and evidence

Approved first slice: reach Littleroot, witness Birch pursued on Route 101,
**fight the rescue battle with the existing Johto party**, then return to
Birch's Lab to choose and receive a Hoenn starter. Leave and revisit without
resetting Johto progress. The original Emerald bag-selection flow below is
donor evidence, not the approved reward timing.
Emerald's `data/maps/LittlerootTown/scripts.inc` and
`data/maps/Route101/scripts.inc:19-65,214-239` control rescue setup, exit
blocking, bag interaction, object visibility, route state, and lab warp.
`data/maps/LittlerootTown_ProfessorBirchsLab/scripts.inc:98-142` handles
the lab follow-up; `data/scripts/prof_birch.inc:1-33` governs Birch's later
locations. `src/battle_setup.c:911-953` proves `ChooseStarter` grants a
level-5 Pokémon **and launches `BATTLE_TYPE_FIRST_BATTLE`** via a C callback;
the battle is not a mere scripted chase. The donor's `FLAG_RESCUED_BIRCH`,
`VAR_ROUTE101_STATE`, and `VAR_BIRCH_LAB_STATE` are story semantics, not
numbers to copy into HGSS.

The owner wants the existing Johto party and progress retained **plus** a
Hoenn starter. The HGSS Elm starter path is *not reusable as-is*:
`files/fielddata/script/scr_seq/scr_seq_0843_T20R0101.s:164-213` calls
`ChooseStarter`, sets global `FLAG_GOT_STARTER`, then assumes the new
starter occupies party slot 0 (`GetPartyMonSpecies 0`) and overwrites the
Johto starter choice (`SetStarterChoice`). `src/choose_starter.c:44-84`
hardcodes Chikorita/Cyndaquil/Totodile, tries `Party_AddMon`, ignores a
full-party failure, and marks slot 0 as caught. Do not call this flow for
Birch or change Elm's flag/starter choice.

HGSS `src/scrcmd_party.c:19-34` exposes `GiveMon`'s success result to a
script; `src/script_pokemon_util.c:21-47` creates a Pokémon, tries
`Party_AddMon`, and updates the Pokédex only on success.
`src/party.c:46-53` rejects an occupied party without overwriting it.
`src/pokemon_storage_system.c:54-72,126-141` has an existing first-empty
PC-box placement API and a no-space result, but `GiveMon` does **not**
automatically deposit gifts in the PC. A full party cannot be treated as
successful delivery. The vanilla catch path in
`src/battle/battle_command.c:6990-7030` demonstrates PC storage for
captured Pokémon, not a tested gift transaction.

## Episode transaction and safety gates (caller not implemented)

Use separate rescue-completed and gift-received states, with **no reuse of
Elm's starter flag or `SetStarterChoice`**. Preserve all existing party members,
badges, story flags, following Pokémon, and save partition layout. A full
party must NOT block the rescue. The earlier free-party-slot rescue fallback
is rejected. Rescue completion unlocks the lab aftermath and onward/return
travel independently of reward delivery.

At the lab, let the player choose Treecko, Torchic, or Mudkip. Proposed delivery
result contract (delivery results implemented; episode states not allocated):

| Outcome | Required behavior |
| --- | --- |
| PARTY | Append to party; leave existing slots unchanged; record receipt once |
| PC | Party full: deposit in an empty PC slot; report destination; record receipt once |
| NO_SPACE | Party and all boxes full: Birch retains the reward; no receipt, overwrite, or story lock |
| Cancel | No grant and no receipt; return to the offer later |
| Already received | Dialogue only; never create another starter |

Receipt must follow a successful insertion, not a capacity prediction. Set
Pokédex ownership only after insertion. Retain a pending chosen species on
NO_SPACE; retry must not reroll an already-created Pokémon or duplicate one.
The exact choice/receipt encoding, creation timing, and whether pending gifts
need a Pokémon object must be resolved within existing audited save storage;
no new save block or raw donor flag numbers are authorized. Avoid an asynchronous
save/UI boundary between insertion and receipt. Test save/reload at every
reachable boundary; do not call this transaction atomic without runtime evidence.

The rescue battle uses HGSS battle startup/return plumbing with the existing
party, not Emerald's callback that grants a starter before fighting. A loss
or blackout must not award rescue completion or a starter; retry behavior and
safe return position need explicit HG/SS tests. Johto starter selection remains
untouched. Link the route, lab, and Johto return
with verified bidirectional warps, collision, NPC movement and persistent
Birch placement. Allocate event IDs only after auditing all compiled
scripts/assembly and both game versions; a symbolic gap is not proof of a
free slot. Inventory maps, tilesets, scripts, text, music, trainers,
encounters, species and asset provenance before porting. No donor resource,
game script, save migration, or executable episode is included here.

Test both HG and SS with one and six party members, the last free PC slot,
full PC, selection cancellation, repeated interaction, battle loss/retry,
save/reload before and after receipt, deferred collection after freeing space, return
to Johto and revisit, plus PKHeX and PKMDS export/edit/reopen on disposable
real saves. CI's matching vanilla ROMs do not establish those behaviors.

## Integration boundary: do not repurpose existing opcodes

`ScrCmd_GiveMon` (`src/scrcmd_party.c:19-34`) has an existing operand layout
and Boolean return. Changing failure into successful PC delivery globally
would change every existing caller's assumptions about party indices.
Keep it unchanged. The superficially relevant `ScrCmd_510`
(`src/scrcmd_12.c:57-75`) is Pal Park's six-migrant deposit: it asserts
insertion, clears migration data and has no per-gift no-space result.
It is used by `scr_seq_0812_T08R0201.s` and cannot become Birch's opcode.

The dedicated `GiveMonToPartyOrPC` command is appended at **853 (0x355)**;
existing indices 0–852 are unchanged. The table and decompiler had 853
entries (including `UnsetPhoneCallTrigger`, whose name lacks `ScrCmd_`).
`src/script.c` reads an unsigned 16-bit opcode and checks the context's
32-bit count; `src/script_manager.c` supplies the table's `NELEMS` count,
now 854. No dispatcher limit, save layout, or existing command is changed.
The header, macro, and decompiler metadata use the same six halfword operands
as `GiveMon`: species, level, held item, form, ability, result variable.
Variable resolution and level/form/ability narrowing match that command.
Trusted scripts must supply valid species, levels, forms, items and variables;
this is not an untrusted-bytecode validator.

`GiveMonToPartyOrPC` constructs the gift with the existing met-data/OT
routine, tries the party, then the PC, and updates the Pokédex only after
successful insertion. It returns `GIVE_MON_NO_SPACE` (0), `GIVE_MON_PARTY`
(1), or `GIVE_MON_PC` (2). A full-storage preflight avoids creating a random
Pokémon when no space exists; insertion success remains authoritative.
It does not set any story flag or save the game. Every successful invocation
creates a gift: the caller must guard against duplicate collection.
`PCStorage_PlaceMonInFirstEmptySlotInAnyBox`
(`src/pokemon_storage_system.c:54-68`) scans from the active box, wraps,
restores PP and returns FALSE if all boxes are occupied. Its success result
does not report a destination box; that needs explicit handling for the UI.
The current result supports a generic "sent to your PC" message, not a box name.

Caller template (pseudocode; intentionally no invented story IDs):

```text
if not rescue_completed or gift_received: show appropriate dialogue; return
offer/restore pending Hoenn species; if cancelled: return
GiveMonToPartyOrPC chosen_species, 5, ITEM_NONE, 0, 0, scratch_result
if scratch_result == GIVE_MON_NO_SPACE: retain eligibility; explain space; return
if scratch_result == GIVE_MON_PARTY or scratch_result == GIVE_MON_PC:
    set gift_received immediately, before yielding to dialogue/save/UI
    show party/PC receipt message
```

`tests/test_gift_delivery.py` compiles and executes the production helper and
script adapter with bounded party/PC API doubles. It covers party preference,
last party/PC slot, total-full no-op, retry, metadata, default/override ability,
balanced allocation and unchanged legacy `GiveMon`. It also assembles the
actual macro, decodes it with the repository parser, and reassembles identical
bytes. These are host logic/tooling tests, not encrypted-save or ARM runtime
tests. No episode caller, selection UI, state allocation or map import exists.

This extension changes ROM code, so retail SHA-1 matching is no longer a valid
gate for the current expanded tree. The retail hashes remain unchanged as
baseline evidence; do not regenerate them to bless an expanded ROM. Build
the extension with `make COMPARE=0` and `make soulsilver COMPARE=0`, then run
the pending manual tests. The owner changed CI to `COMPARE=0` in
`7411b88312b838c9fc2d61797322568d1c611bc2`; that workflow change is preserved.

## Persistent-state allocation gate (implemented inventory, no allocation)

`scripts/audit_expansion_state.py` inventories candidate **variable** IDs
without reserving them. Example (the two IDs below are probes, NOT Birch IDs):

```sh
python3 scripts/audit_expansion_state.py \
  --candidate 0x416e --candidate 0x416f --output /tmp/state-audit.json
```

The initial scan covered 4,752 tracked source/header/assembly/event-JSON files
and identified 965 expected compiled script banks per edition. Neither probe
had a literal/alias use outside definitions in that scan. **This is not proof
they are free.** The subsequent native script build compiled all 965 banks
independently for each edition, with all 1,930 outputs matching the tracked
`scr_seq.sha1` manifest. Neither probe occurred in either edition's binaries.
Source branches for both editions are scanned together; separate builds use
the actual HEARTGOLD/SOULSILVER preprocessor defines.

Reproduce without Wine (installed gcc, g++, and ARM GNU binutils required):

```sh
python3 scripts/build_native_field_scripts.py --output /tmp/hgss-scripts
python3 scripts/audit_expansion_state.py \
  --candidate 0x416e --candidate 0x416f \
  --heartgold /tmp/hgss-scripts/heartgold \
  --soulsilver /tmp/hgss-scripts/soulsilver --output /tmp/state-audit.json
```

The output directory must not already exist. The helper uses the repository's
native `msgenc` generator, the config.mk edition/SDK/assembly defines, and
objcopy's script make-rule extraction. GNU compatibility conversions handle
MW comments, `.rodata`, alignment-mode syntax, and two redundant zero macro
arguments; **every bank must match its tracked SHA-1** or the build fails.
The script-only output is not a ROM and does not fix the Windows compiler.
The audit reports complete binary coverage but still exits 2: no literal
references found, allocation not approved. It inventories 1,565 native/dynamic
access sites for review; that count is not 1,565 proven candidate references.

Supply independently built directories with `--heartgold <HG-scr_seq-dir>`
and `--soulsilver <SS-scr_seq-dir>` to inventory every byte offset for candidate
halfwords (including odd offsets), record SHA-256 fingerprints, and detect
missing, empty and unexpected banks. Do not pass the same/stale directory as
both editions. Byte matches are conservative evidence, not decoded references.
This does not require ROM uploads or store ROM/save data in Git.

The report always says `allocation_approved: false`. Exit 1 means an observed
reference; exit 2 means no literal reference was found but manual/dataflow
review is still required. The test suite verifies that even complete
literal-free binary fixtures cannot authorize an allocation.

Concrete remaining review paths:

- `src/save_vars_flags.c:57-59` indexes the persistent array using a runtime
  variable ID, so no symbolic name is necessary for a reference.
- `src/script_manager.c` routes IDs through `GetVarPointer`/`FieldSystem_VarGet`
  and resets map-temporary variables through an indexed loop. Range/alias
  reasoning is required in addition to literal scanning.
- `src/sys_vars.c:22-42` wraps reads/writes with runtime `var_id` parameters.
  Its callers and native/assembly accesses are listed in the report for review.
- `src/scrcmd_c.c` supports variable-selected flag checks/sets/clears; reserving
  a flag based solely on its absence in constant operands would be unsafe.
- Incoming existing saves, event/mystery-gift scripts, and opaque assets need
  explicit compatibility policy/review; unknown variables are not promised
  zero on all existing saves.

Accordingly no state constants, live lab script, archive entry or vanilla NPC
were changed in this checkpoint. The duplicate guard and deferred-choice
transaction cannot be integrated safely until that allocation is reviewed.
The gift helper itself was checked against existing party/PC APIs; no new
defect requiring a change was established in this audit.

## Three-map resource inventory

Source: each map's `data/maps/<name>/map.json` and
`data/layouts/layouts.json` at the Emerald audit revision above. Counts include
donor events that must be omitted or adapted, not a proposed HGSS allocation.

| Map | GBA layout dimensions | Objects / warps / coordinate / background events | Tilesets | Music |
| --- | --- | --- | --- | --- |
| LittlerootTown | 20 x 20 | 8 / 3 / 9 / 4 | General + Petalburg | MUS_LITTLEROOT |
| Route101 | 20 x 20 | 6 / 0 / 9 / 1 | General + Petalburg | MUS_ROUTE101 |
| LittlerootTown_ProfessorBirchsLab | 13 x 13 | 6 / 2 / 0 / 15 | Building + Lab | MUS_BIRCH_LAB |

Each layout references `data/layouts/<name>/{map,border}.bin`; these are
GBA metatile data, not DS geometry. Town connects north to Route 101;
Route 101 connects north to Oldale and south to town. Town's three warps
lead to May's house, Brendan's house, and the lab. The lab's two exit tiles
both target town warp 2. **The three maps are not a closed import unit**:
Oldale and the two houses require explicit boundary handling or additional
resources. Do not leave dangling warps or pretend those interiors were imported.
The Johto arrival/return connection is new and is not specified by donor data.

Required object graphics include Birch, his bag, Zigzagoon, the town truck,
mother, twin, fat man, boy, youngster, scientist, item balls and variable
rival graphics. The lab's item balls/hide flags include Emerald's postgame
Johto-starter gifts; exclude that subsystem rather than importing it into
Birch's new Hoenn-starter reward. Likewise audit the moving-truck/new-game
and rival callbacks before retaining town initialization scripts.

DS integration needs map headers and IDs; matrix/land data, geometry,
textures, collision and movement permissions; zone-event objects/triggers/warps;
script banks and message banks; NPC sprite resources; music mapping;
encounter/battle configuration; and map-section/region presentation.
Use `src/data/map_headers.h`, `files/fielddata/mapmatrix`,
`files/fielddata/eventdata/zone_event`,
`files/fielddata/script/scr_seq` and `files/msgdata` as host entry points.
Route 101's ordinary encounter data is in
`src/data/wild_encounters.json`; the rescue first-battle setup is separate.
Do not substitute a vanilla Johto map's name or copy GBA coordinates directly.

### Verified HGSS land-container and height-plane authoring

### Flat Nitro model export checkpoint (unhooked)

`scripts/export_lab_model.py --pack /tmp/emerald-lab-pack --output
/tmp/emerald-lab-nitro` now authors a real BMD0/MDL0 model, TEX0 texture,
standalone BTX0 texture file, and separate-texture HGSS land container.
It verifies the extraction manifest before consuming the preview and refuses
to overwrite evidence. Generated binary/art assets remain outside Git.

The one-quad model uses a root node, SBC material/shape commands, GPU display
list, material/texture/palette associations and single-entry Patricia resource
dictionaries. Its 256x256 indexed texture and 256-color BGR555 palette preserve
every visible source pixel without color loss (208x208 used area).
Model scale 64 maps fixed-point vertices to world X/Z `[-104,104]`, matching
13 cells of 16 units and the flat BDHC bounds. The texture consumes 64 KiB
plus 512 palette bytes; in-game VRAM availability has not been established.

Layouts were checked against `lib/include/nnsys/g3d/binres/res_struct.h`
and independently described reader layouts in apicula revision
`3d4e91e14045392a49c89e86dab8cb936225588c`
(`src/nitro/{model,tex,info_block,render_cmds}.rs`). No apicula source was
copied, and its renderer has **not** been run. Offset-following tests decode
the generated dictionary bindings, materials, display-list vertices/UVs,
and texture pixels; actual renderer/SDK acceptance is still unverified.

This is a **flat rendering prototype, not the faithful 3D lab import**.
Flattening the preview loses foreground occlusion and furniture heights.
Terrain is explicitly zero-initialized, not a mapping of donor walkability.
The output is deliberately not appended to a live map archive: area texture
binding, movement/collision attributes, camera, objects, events and rendering
must be validated first. The existing 540 maps, script-bank indices, and
save ABI are unchanged. The exporter does not imply a playable episode.

All 31 local tests pass, including full real-donor texture pixel equality.
The confirmed clang-format-19 violation in the new expansion header
(missing final newline) is corrected; no unrelated source was reformatted.

### Land-container reference

`scripts/hgss_land.py` losslessly decodes/re-encodes all 676 members of
`files/a/0/6/5`. The first four words are terrain, prop, model and BDHC sizes.
The fifth word is **two halfwords**: marker `0x1234` and extra-data length.
`asm/overlay_01_021F4704.s`, `ov01_021F4AAC`, reads that extra data **before**
terrain; its callers then read terrain, props, model and BDHC in order.
Member 0 has 88 extra bytes, so its terrain starts at 108 and its BMD0 at
2972. The fixed-offset reader in `src/terrain_attributes.c` is not sufficient
to decode extended members; do not build an exporter around that shortcut.

The BDHC reader is `asm/overlay_01_021FB04C.s`: signature followed by six u16
counts, then points (8 bytes), normals (12), constants (4), plates (8),
strips (8), and access indices (2). The new flat-plane writer reproduces
member 1's complete 66-byte BDHC byte-for-byte for bounds -256..256 and
height 16. A 208-by-208-unit zero-height lab plane can now be authored,
but this is height geometry only, not terrain walkability or render proof.
Four regression tests validate all original container/model block lengths,
round trips, the known retail plane, and malformed input rejection.

Still missing: faithful NSBMD geometry/material/texture generation, lab
terrain behavior mapping and model/BDHC coordinate alignment verified in
the actual field renderer. No new land member/map header is enabled yet.