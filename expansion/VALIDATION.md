# Stage 1A validation — 2026-09-26 (America/Los_Angeles)

This is a partial implementation checkpoint, not Stage 1 completion.

## Private HG compact Route 101 runtime probe — 2026-09-28

- A second **private HeartGold test ROM** built successfully from pinned
  game source `51e26be86a4239d7456301ae4e0a425a64e5a605` and the
  compact exporter at `a08fad6fc150f34878cae28e727e357d1056f14a`:
  `/tmp/hg-vm-share/pokeheartgold-route101-probe-a08fad6.us.nds`
  (128 MiB, SHA-256
  `f0676f0b90bd01dd8e0b2a117970a13ee23335f13237d789f60695a40c2b7c56`).
  This isolated ROM swaps **only its existing debug map 540** to Route 101
  in place of the separate private Littleroot test; see the pre-build
  overlay manifest `/tmp/hg-route101-probe-a08fad6-overlay/probe-manifest.json`.
  Spawn (9,15), technical reward scientist (8,15), and return scientist
  (10,15) are test fixtures, **not** an authentic rescue scene. The
  20×20 donor composite uses four compact textures totaling 102,400 bytes
  (100 KiB) and a 512-byte palette.
- The conservative terrain permits 132 safe cells in three disconnected
  components of 72/33/27 cells, with 70 safe cells in the spawn component
  after excluding actors. It deliberately blocks all 104 unsupported
  grass/ledge/behavior/elevation cells rather than inventing DS behavior.
  The parent visually verified the textured route floor and two test actors
  in private `route101-series002`; captured traversal through tiles
  (9,14), (9,15), (9,16) in `003`–`005` showed no obvious texture seam.
  These witnesses span **only the connected left-side texture quadrants
  0 and 2**, not all four: right-side quadrants 1 and 3 are unreachable
  under these safe collision rules. Coordinates are inferred from event
  data and controller inputs, **not measured in live game RAM**.
- Two complete **Route → Elm → Route** cycles were parent-visually verified
  in captures `006`/`013` and `014`/`015`. Entry screenshots `002`,
  `013`, `015` are byte-identical (SHA-256
  `d5c6b3645385a74b7727236d26535dcd54f3a5126134d3ccabaa9a3e8fee097e`).
  The unchanged Johto assistant/Potion sequence progressed without saving
  in `route101-series007`–`011`. Evidence remains private under
  `/tmp/hg-retroarch/route101-seriesNNN/{screen.png,report.json}`
  (NNN = 001–015), with `route101-seam-contact.png` and
  `route101-transition-contact.png` in `/tmp/hg-retroarch/`.
  The emulator used an **isolated copy** of the real HG Johto starter
  battery (SHA-256
  `42b0d9f1722de15b552d293a4fae404adc82fd259bc5e582a23f8b3b9afc038b`);
  the immutable original remains unchanged. This probe did not save, grant
  a gift, execute rescue or restore an emulator state.
- Taken together, **both private compact exterior probes** now have
  specific HG visual render/traversal/return evidence, but not a connected,
  production-integrated Littleroot–Route 101 journey. The generic
  exporter's `RuntimeVerified=false` still covers uninstalled production
  resources, and the private overlay manifest's `runtime_verified: false`
  was stamped **before** this probe ran; neither flag is a blanket runtime
  gate passed by this test. Native allocator/free-headroom and future
  prop/NPC allocation were **not measured**. Unreachable right quadrants,
  blocked grass/ledges, perimeter-negative collision, authentic chase/
  rescue, proper exteriors, full campaign and Stage 1 completion remain
  unproven. No private ROM, donor binary, save or screenshot is committed.

## Private HG compact Littleroot runtime probe — 2026-09-28

- A **private HeartGold test ROM**, generated from pinned game source
  `51e26be86a4239d7456301ae4e0a425a64e5a605` and the compact exterior
  exporter at `a08fad6fc150f34878cae28e727e357d1056f14a`, built
  successfully at `/tmp/hg-vm-share/pokeheartgold-town-probe-a08fad6.us.nds`
  (128 MiB; SHA-256
  `8579b8d4827f9cc8d35c1fbefe68e1397dd61d32bc41687f2c7567e901dc589b`).
  Private guest source is `/root/debug-town-probe-a08fad6`; the overlay
  provenance/bindings are recorded at
  `/tmp/hg-town-probe-a08fad6-overlay/probe-manifest.json`. **Only this
  disposable ROM's existing debug map 540** was changed to use compact
  Littleroot texture member 106 and land member 676. Its debug spawn is
  (13,12), reward scientist (12,12), return scientist (14,12). Route 101
  was **not** installed or tested. The four distinct compact textures
  total 102,400 bytes (100 KiB) plus a 512-byte palette.
- The emulator **cold-loaded an isolated copy** of the authentic HG Johto
  starter battery (SHA-256
  `42b0d9f1722de15b552d293a4fae404adc82fd259bc5e582a23f8b3b9afc038b`);
  the immutable original remains unchanged. No in-game save, gift, rescue,
  state restoration or editor round trip was run on this town-probe ROM.
  Parent visually verified the composite town floor and both technical
  placeholder actors in private `town-series002`. Audited conservative
  terrain connectivity and input trajectories across tiles with x 15/16
  and z 15/16 reached all **four compact texture quadrants**, with no
  obvious missing texture or seam in captures `town-series004`–`009`.
  Coordinates derive from event data plus controller input, **not live
  game-RAM telemetry**; do not claim pixel-perfect camera bounds or full
  navigation coverage from these witnesses.
- Two complete **Town → Elm → Town** return/re-entry cycles were visually
  verified in private captures `town-series010`/`017` and
  `town-series018`/`019`. Entry screenshots `002`, `017`, `019` are
  byte-identical (SHA-256
  `2de7cf3cb85046960eb052a3bc0cdd41b850bdc75d37de379226705f34db7f7e`).
  The ordinary Johto assistant/Potion sequence progressed unsaved in
  `town-series011`–`015`. Evidence is private at
  `/tmp/hg-retroarch/town-seriesNNN/{screen.png,report.json}`
  (NNN = 001–019), plus `town-quadrants.png` and `town-returns.png`.
- The **specific private Littleroot probe** establishes rendered geometry,
  cross-quadrant traversal and these two transitions; it does **not** make
  the generic exporter's `RuntimeVerified=false` manifest inaccurate for
  uninstalled production assets. No bounded native allocator/free-headroom
  measurement, future prop/NPC allocations, perimeter-negative collision
  validation or Route 101 runtime was established at this **Littleroot-only
  checkpoint**; the separate Route 101 probe above now has limited runtime
  evidence. This is a flat visual prototype, not authentic multi-height 3D
  town, native exterior/episode integration, real rescue, full campaign or
  completed Stage 1. Earlier
  exterior authoring notes below are historical and superseded only for
  this particular isolated HG test. No ROM, private assets or screenshots
  are committed.

## Native SoulSilver starter, debug gift and real-save editor loop — 2026-09-28

- A separate **private, opt-in SoulSilver debug ROM**, built from the pinned
  `51e26be86a4239d7456301ae4e0a425a64e5a605` source and the same
  runtime-verified solid lab assets, is
  `/tmp/hg-vm-share/pokesoulsilver-solid-51e26be.us.nds` (128 MiB; SHA-256
  `cd12c7da629337d3b4204a04a356425fb026b5b4264e2eb99fb84b014aa0bda4`).
  Its native script build used `-DSOULSILVER`, with all 966 banks inventoried
  in private `/tmp/hg-ss-native-51e26be/ss-bank-manifest.json`. This is not a
  ROM from the later documentation/exterior commits and is not distributed.
- Starting from **blank SoulSilver battery data**, not an HG-converted save,
  boy trainer A proceeded through native New Game, chose Totodile and saved.
  The immutable first-save copy
  `/tmp/hg-retroarch/pre-save-backup/ss-native-after-johto-starter.dsv`
  has SHA-256 `a6f2dcbcfdc7dccfe614882f813527cffb8c20f86fc5cc434a2ccbbe0414ebf1`.
  At this first save **only partition 1 is populated**, with its two valid
  native block CRCs; partition 0 is still erased (`FF`). Do not report all
  four blocks as populated at this stage.
- In a persistent native SS emulator session, the debug entrance reached the
  filled-texture flat lab with both actors. The touchscreen menu worked;
  cancellation awarded nothing; the subsequent Treecko choice added a
  level-5 party member; immediate re-interaction gave the receipt guard.
  The player completed a native save, used the return scientist to reach Elm,
  ran the unchanged Johto assistant/Potion sequence and re-entered the lab;
  the receipt guard persisted. The parent visually verified the private
  lab/menu/cancel/gift/guard/save/return/Johto/revisit captures. Debug Elm
  **simulates rescue eligibility**: authentic rescue entry 2 is not mapped or
  proven in SS gameplay.
- The separate immutable post-gift battery copy
  `/tmp/hg-retroarch/pre-save-backup/ss-native-after-treecko.dsv` has SHA-256
  `6003bd7b2235833dae7e8005c3602ed1ad6776001c233a4d83aa3e88f4a14bf9`.
  **Both partitions are now populated**, all four native block CRCs valid.
  Corrected PKHeX.Core and PKMDS.Core load it with zero load mutation as
  `SAV4HGSS` **SoulSilver** (version 8, `IsHGEngine=false`). Both see
  Totodile (158) then Treecko (252); all decrypted bytes of the original
  Totodile and all 2,912 flags match the true SS starter save. Starter
  `0x4030` remains 158; debug rescue/receipt `0x416e`/`0x416f` are 1/252.
  Ordinary play also reset temporary variables `0x4000` 4→0 and `0x4001`
  158→0, and advanced friendship steps `0x404b` 45→49. This is **not** a
  claim of byte-for-byte preservation of the entire save.
- Both editors' no-op and money-3000-to-3001 exports reopen with valid
  checksums, preserving the **current** 368 variables, 2,912 flags, both
  Pokémon, story values, map 540 and trainer A (ID32 3299343148, TID 64300,
  SID 50343). The two editors' respective exports are identical, **but the
  no-op output is not byte-identical to the input**: five bytes changed in
  box content flags/checksum; the money edit changes eight bytes. Their
  identical money-edited battery SHA-256 is
  `e997f62b005cdef28495368b04495f1d2ed016bc5f8cf2f3d183c2e5e7793f39`.
  A **true cold load** of an isolated edited copy under the SS ROM verified
  trainer A at Continue, the textured lab and actors, both level-5 party
  Pokémon (HP 21/21 and 19/19), trainer-card money 3001 / ID 64300 and
  already-received dialogue. The parent inspected five private contact
  panels at `/tmp/hg-real-save-validation/ss-native-treecko-edited-cold-contact.png`;
  evidence JSON is under `/tmp/hg-real-save-validation/ss-native-treecko/`.
  Original batteries remain unchanged. These are Core API editor checks,
  **not** desktop/browser UI tests. Treecko fails retail encounter legality
  (new origin/type); save compatibility does not confer retail legality.
- The SS runtime daemon was stopped cleanly. This **SS one-party-slot gift**
  does not establish full-party PC fallback/refusal/retry on SS; those native
  capacity cases below used **HG synthetic disposable fixtures**. Neither
  edition has authentic mapped rescue/exterior travel, full Hoenn/Sinnoh
  campaigns or completed Stage 1. Historical SS-pending notes below are
  superseded only by this specific native build/runtime/save-editor evidence.
  No ROM, save, screenshot, SDK or key is committed.

## Native HG capacity and deferred gift — disposable fixtures, 2026-09-28

The **same corrected private HG debug ROM** (SHA-256
`cf98258b792fa57cc8a318274ac68488c85c0b6c51ddacbdbfbbb120341f3c07`)
ran four separate capacity cases. Their inputs are **synthetic disposable
editor fixtures**, not naturally accumulated parties or authentic game
progress: each starts with six Totodile clones, rescue variable `0x416e=1`
and receipt `0x416f=0`. The first three inputs differ in PC occupancy (0,
539, or 540); retry instead derives from the completed full-storage save.
These cases test native gift/storage behavior; the genuine Totodile/Treecko
post-gift save described below is separate and remains unchanged.

- Full party, empty PC: Treecko went to box slot 0; PC occupancy became 1,
  receipt became 252, and all six original party Pokémon were unchanged.
- Full party, **last available PC slot 539**: Treecko went to that slot,
  occupancy became 540, receipt became 252, and the six party Pokémon and
  other 539 occupied box slots were unchanged.
- Full party and all 540 PC slots occupied: the scientist displayed the
  no-space refusal; **after completing the native save** the receipt was
  still 0, with all six party Pokémon and all 540 box Pokémon unchanged.
  The finished-save evidence is `full/saved-complete`, **not** the earlier
  incomplete `full/saved` capture, which missed the second save-message page.
- Deferred retry: a **copy of that saved full-storage result** was edited
  to free only PC slot 539, then cold-loaded. The native gift filled exactly
  that slot and recorded receipt 252; another interaction was guarded against
  duplication. The original saved full-storage result was not overwritten.

All four native output batteries pass all four HGSS block CRCs. Audits and
private batteries are under `/tmp/hg-capacity-runtime/{empty,last,full,retry}/`;
the exact audit JSON filenames are `audit.json` in each case. The output
SHA-256s are respectively `9213d44102fca0b63d26ff767cc7f6c55a3999788134ef8c2bf744e9091535b6`,
`61d33c009548a0ff45b70242e177da0d13fc0e72712ef6802abff891cf003307`,
`6f10437082d77cbebc2d1eaed0de7713673ee6bc115ab812f57036b041872d55`
and `a26e1f431a9ba4c119d57d2e3373534c915c0ddc4f2dd0f9c5574ff6248d383d`.
The parent visually verified delivery, refusal, retry and guard panels in
private `/tmp/hg-capacity-runtime/capacity-contact.png`; no private ROM,
save or screenshot is published. These **capacity cases are HG only**; no
SS capacity result or authentic rescue/battle/travel is established here.
At this earlier checkpoint, the SS build was still in progress; the separate
completed SS starter/gift/real-save evidence is documented above. No full
campaign or desktop/browser editor UI is claimed. Historical pending-capacity
statements below apply only to their earlier checkpoints.

## Corrected debug HG runtime and real-save editor loop — 2026-09-28

- A **private, opt-in HeartGold debug ROM** built from generated source at
  `51e26be86a4239d7456301ae4e0a425a64e5a605` with the solid lab assets:
  `/tmp/hg-vm-share/pokeheartgold-solid-51e26be.us.nds`, 128 MiB,
  SHA-256 `cf98258b792fa57cc8a318274ac68488c85c0b6c51ddacbdbfbbb120341f3c07`.
  This is a local evidence path, not a committed or distributed ROM. The
  separate earlier ROM (`a41ba778…`) and disposable saves were not overwritten.
  The authorized Ubuntu 22.04 guest used its proven one-vCPU, 512-MiB/swap
  configuration; the fresh build needed the private NitroSDK linker templates
  at their prescribed locations and, with `NODEP=1`, an explicit
  `PROJECT_ROOT_NT=Z:/root/debug-solid-51e26be` for the Windows linker
  response template. The host sandbox's larger tier is not a ROM requirement.
- A persistent DeSmuME libretro 0.9.11 session cold-loaded an **actual
  in-game save** containing the original Johto Totodile. It does not restore
  emulator savestates: repeated restore with this old core corrupted graphics,
  whereas native battery cold loads rendered normally. The corrected debug
  map 540 visibly renders its donor-textured **flat technical lab**, player
  and both scientists, replacing the earlier black floor. The touchscreen
  menu now responds. B cancellation gave no reward; a later Treecko choice
  delivered a level-5 party member; immediate repeat interaction reported
  already received, with no second grant. An in-game save completed; the
  return scientist warped to Elm's lab; after an ordinary untouched Johto
  assistant/Potion event, Elm re-entry returned to the same lab and the reward
  guard still held. The debug entrance **simulates** rescue eligibility;
  compiled rescue battle entry 2 was not entered or tested in gameplay.
- The immutable post-gift battery copy is
  `/tmp/hg-retroarch/pre-save-backup/after-solid-treecko-save.dsv`,
  SHA-256 `6956efbca751e7bfaed3026e557f09f8a90f307da8809275bf8d3726869fb736`.
  Its real HGSS save has all four native block checksums valid. With the
  separate, corrected PKHeX loader (`the-new-kai-lu/PKHeX` draft PR 1,
  `9a5ed35e0df1bc65c3900bcab03cddfa581aa1d7`), **both PKHeX.Core and
  PKMDS.Core load without changing any bytes**. Both report party
  Totodile (158) then Treecko (252); every decrypted byte of the original
  Totodile agrees with the authentic pre-gift starter save. All 2,912
  existing event flags agree, Johto starter variable `0x4030` remains 158,
  and debug rescue/receipt variables `0x416e`/`0x416f` are 1/252. Do not
  claim all save bytes stayed unchanged: temporary variables `0x4000/0x4001`
  reset and friendship-step variable `0x404b` advanced 51 to 55 during real
  play. Both editors' no-op and money-3000-to-3001 exports reopen with valid
  checksums and preserve all **current** 368 variables, 2,912 flags, map 540,
  trainer identity and both Pokémon's decrypted bytes.
- An isolated copy of the editors' identical post-gift money-edited export
  (`735cb8f5d14dd1e84f5ab06b8e15eb10e29b5fad63917536ba9d075e46fa83be`)
  was **cold-loaded** by the corrected ROM without restoring an emulator
  state. The Continue screen identified trainer A; the textured lab rendered;
  the party UI showed Totodile and Treecko; the trainer card showed money
  3001 and ID 45489; the scientist still gave the already-received dialogue.
  The original battery copy remains unchanged. These are actual HG Core API
  save/edit/export/cold-game checks, **not** desktop or browser UI tests.
  Treecko fails vanilla retail encounter legality (new origin/encounter
  type); save compatibility must not be misrepresented as retail legality.
- At this earlier checkpoint, SoulSilver had no corrected private ROM build
  or real runtime/editor evidence; full-party/PC fallback and no-space had
  host tests but no real runtime proof (now superseded by the HG-only capacity
  checkpoint above). The lab is a flat prototype without authentic
  furniture, and Littleroot/Route 101 are donor extractions, not playable
  exteriors. Actual rescue entry, travel, both full regional campaigns and
  full Stage 1 completion remain unimplemented/unverified. Sections below
  retain their historical checkpoint scope; their earlier pending-runtime
  statements are superseded **only** by the specific evidence above.

## Runtime-discovered floor material defect — 2026-09-28

The older private debug ROM documented below reached map 540 in a persistent
DeSmuME libretro session without savestate restoration. The player and two
technical scientists appeared, but the lab background was black. Johto rooms
rendered correctly in that same session. Reading the actual ROM confirmed
appended area 106, texture 106 and land 676; its land model is byte-identical
to the aligned exporter output. External model decoding did not establish
successful native rendering.

Material flags were incorrectly emitted as `0x1ff`, which includes
`NNS_G3D_MATFLAG_WIREFRAME` (`0x20`) in the repository's SDK header.
Native material handling in `lib/asm/nnsys.s` at `_020C03DC` and `_020C2204`
clears polygon alpha for that flag, selecting wireframe instead of a filled
floor. The exporter now explicitly combines the intended identity-texture
and diffuse/ambient/vertex-color flags, excluding wireframe. A regression
checks serialized flags and effective native alpha, including the historical
failing flag combination.

Focused model tests and independent apicula decoding pass. Regenerated private
assets are `/tmp/emerald-lab-solid`, with archive overlay at
`/tmp/emerald-lab-solid-overlay`. These are not committed assets. A new ROM and
persistent-session lab rendering test remain required: this source correction
does not establish that all runtime rendering/binding defects are fixed.

The same older debug ROM also froze after the reward NPC's opening dialogue.
Native `MenuInit`/`MenuExec` require the overlay-27 menu context established by
`TouchscreenMenuHide`; `LockAll` does not establish it. Both gift and rescue
menus now bracket menu construction/execution with hide/show, restoring the
ordinary field menu before gift handling or battle. The compiled-byte test
models this precondition and rejects a mutated script missing the transition.
Only appended bank 965's hash changes. This is a source regression fix; the
fixed reward menu still requires a rebuilt-ROM runtime check.

## Debug return regression and exterior extraction — 2026-09-28

- Adding production rescue entry 2 exposed a real debug-generation regression:
  the right scientist still selected script ID 3, which now starts rescue
  instead of returning. The generator now derives the appended return index
  from the production entry table. Currently return is entry 3 / object script
  ID 4; reward remains entry 1 / ID 2, and rescue entry 2 is preserved.
  Both editions' compiled event/command tests check these actual bindings and
  the return Warp to Elm's lab. Regenerate debug trees before a new ROM build;
  the older `0db3ba85` ROM predates this regression and is not changed here.
- All 38 host tests pass with the independent APICULA decoder enabled; the
  baseline checker reports no errors and `git diff --check` passes. The
  previously failing generated-return assertion is now fixed, not waived.
- The shared donor extractor now supports Littleroot Town and Route 101 with
  `--map LittlerootTown` or `--map Route101`. Each is 20 by 20 donor cells
  (320 by 320 pixels). Tests check all 400 cells, source events/connections,
  artifact hashes and a 32-cell-grid coordinate plan. Existing lab pixel
  regression tests remain unchanged and pass.
- These are donor extraction artifacts, **not imported DS exterior maps**.
  Animated tiles/palettes are not replayed. Eight unavailable lower-quadrant
  references in Littleroot are omitted only where every actual upper pixel
  is proven opaque, and recorded in `chunk-plan.json`; the separated lower
  layers are therefore incomplete. Visible missing pixels fail explicitly.
  Collision/elevation fields retain donor semantics, not HGSS walkability.
- No new ROM, lab gameplay, save/editor round trip or Stage 1 completion is
  established by this checkpoint. Earlier sections below are historical
  checkpoints and retain their narrower scope.

## Local ROM toolchain recovery and debug build — 2026-09-28

- A private, opt-in debug **HeartGold** ROM built successfully with
  `make COMPARE=0` from the generated lab test tree at `0db3ba85`. This
  tree adds test-only map 540, an Elm entrance, a technical scientist starter
  interaction, and a return warp; it simulates Birch's rescue. The newer
  real-rescue script at `abf724e` was **not** in the built snapshot. Neither
  SoulSilver nor the default branch build is established by this run.
- Private ROM: `/tmp/hg-vm-share/pokeheartgold.us.nds`, 128 MiB, SHA-256
  `a41ba778bf085737f41faace92d0717fb96f5410cf4311d2718332a7a84a870f`.
  The generated source archive was
  `/tmp/hg-build-vm/debug-source.tar.gz`, SHA-256
  `e241b1362502556492374836eb1384d992cf96c19064810a71bd92ba1caafc3d`.
  These private local paths are evidence, **not** downloadable or committed
  ROMs, saves, tools, or license files.
- The sandbox's native ELF32 Wine loader fails with `Exec format error`;
  default Wine64 still segfaults. This is a host execution limitation, not a
  demonstrated game defect. A checksum-verified official Ubuntu 22.04 image
  running in KVM with one vCPU, 512 MiB RAM and 2 GiB guest swap succeeded
  with Ubuntu Wine 6 (32-bit packages), a win32 prefix and Xvfb. Four guest
  vCPUs stalled in this environment. The guest received the locally
  authorized Metrowerks/NitroSDK tools; no toolchain or license was published.
- The reproducible local route was: prepare the isolated lab source with
  `scripts/prepare_lab_debug.py`; assemble its 966 script banks for HG using
  `scripts/build_native_field_scripts.py`; transfer the generated source and
  banks into the Ubuntu 22.04 guest; place the authorized compiler/SDK in the
  repository-prescribed `tools` paths; set `LM_LICENSE_FILE`, `WINEARCH=win32`
  and a guest-private `WINEPREFIX`; run `xvfb-run -a make COMPARE=0`. The
  generated debug Elm/reward banks 843/965 intentionally differ from their
  retail hashes. VM disk, snapshot and session helper remain private under
  `/tmp/hg-build-vm/`; that helper uses a local private SSH key and is not a
  portable installation script. Use `INSTALL.md` and the pinned archive
  hashes in `baseline.json` when reproducing in another authorized VM.
- DeSmuME 0.9.13 at `/usr/games/desmume-cli` launched the debug ROM under
  Xvfb with software rendering and dummy audio. A boot screenshot showed
  the opening city scene. This is **not** proof of the debug lab's rendering,
  travel, gift transaction, in-game saving, cold restart, editor round trip,
  or completion of a Hoenn episode. Those runtime checks remain in progress.

## Appended reward transaction checkpoint

- Supersedes earlier "no allocation/caller" notes below: two existing variable
  slots are now named for Hoenn rescue and reward receipt; native range review
  and the 11-member Frontier script archive check are recorded in
  `EMERALD_OPENING.md`. No save-size/layout change.
- Appended bank 965 implements guarded starter receipt and retry, with no
  existing script index or NPC overwritten. It is not connected to a map yet.
- Twenty host tests pass, including actual compiled claim-byte execution for
  HG/SS, existing production gift-helper tests, native range tests, Frontier
  archive checks, and all baseline/mutation tests.
- Full native script rebuild: 966/966 tracked hashes match separately for
  HeartGold and SoulSilver (1,932 outputs). The appended bank has a new pinned
  hash; original 965 hashes remain unchanged.
- No selection UI, rescue battle, imported map, emulator or save/editor
  round trip is claimed. Full Stage 1 campaigns remain unimplemented.

## Gift-command extension checkpoint

- Appended opcode 853 (`GiveMonToPartyOrPC`); existing opcodes, `GiveMon`,
  save storage and retail-baseline hashes are unchanged.
- Baseline source audit and all nine host tests pass: seven original mutation
  tests, compiled gift/adapter logic against storage doubles, and actual
  macro/decompiler/reassembly round trip. These do not validate ARM execution,
  encrypted Pokémon data, real save serialization, or a playable episode.
- This is intentionally no longer a retail-matching ROM. Existing CI uses
  `COMPARE=1` and will reject changed ROM hashes; the workflow was not edited.
  Historical matching-build success below applies only to its stated commit.
- A complete expanded ROM build and in-game/editor testing remain unverified.

## Passed

- Supplied compiler and NitroSDK archive SHA-256 hashes exactly match the
  archives referenced by the host's devcontainer setup; see `baseline.json`.
- Seven Python baseline/mutation tests and the live source contract audit.
- Native host utilities compile after correcting `gen_fx_consts` libm link order.
- GitHub Actions on PR head `f699b3c01b769f95c07e7d802dd5b7369bb142b2`:
  expansion-baseline contract passed on push and PR; build run
  `36337502454` passed both HeartGold and SoulSilver steps. The build
  workflow sets `COMPARE=1`, and the Makefile checks each ROM against its
  pinned SHA-1 when that variable is set. Raw run-log retrieval returned
  HTTP 403, so individual hash output was not inspected. No ROM artifacts
  were retained by that run.
- PKHeX: nine focused HGSSBaselineTests/HGEngineTests pass. Four new cases cover
  vanilla HG/SS-origin Pokémon, independent general/storage partition selection,
  checksums, every story variable/flag byte, and isolated box EXP/ability edits.
  The other five are existing hg-engine tests.
- PKMDS.Core Debug build against the sibling PKHeX fork succeeds with zero
  warnings/errors after installing `libicu78`.
- Full PKHeX suite with ICU: 605 passed, one skipped, one failed out of 607.
  `EffortExpLegalityTests.ZeroEVs_ReturnsZero` also fails on untouched commit
  `94033cce0caf90dcc04bbacdbe991233bb3bef9f` in a separate worktree. It was
  not changed as part of this save-compatibility work.

## Blocked / not demonstrated

- Direct host ROM reproduction: `make -j4` first failed linking `floor`,
  fixed here. Retrying reached asset conversion, where tools segfaulted after
  Wine assembly invocations produced no expected object file
  (`files/tel/pmtel_book.o`). A working Ubuntu 22.04 VM path for a private
  debug HG build is now documented above; direct host Wine remains unusable.
- The local sandbox has not produced matching HeartGold/SoulSilver hashes;
  GitHub's historical retail comparison does not supply local retail ROMs.
- PKMDS Web Debug build is blocked by NETSDK1147: missing `wasm-tools`.
- The emulator only reached the opening city screen. No debug lab gameplay,
  Windows desktop UI, browser editing loop, real-hardware run, versioned
  in-game milestone save, or complete imported episode has been tested.
- Earlier Git pushes were rejected with HTTP 403 despite confirmed collaborator
  write access; authenticated API code writes worked. The owner installed the
  Actions workflow separately; it is now present on the game PR branch.

## State-allocation inventory checkpoint

- Added a fail-closed candidate-variable inventory over tracked C/header,
  assembly, script sources and event JSON, with optional independently built
  HG/SS script-bank directories. It fingerprints inputs and reports missing,
  empty or unexpected banks and conservative unaligned halfword matches.
- Six new host tests cover assembled binary evidence in either edition,
  missing/empty/stale banks, decimal and alias references, computed accesses
  and evidence fingerprint changes. Together with existing tests, 15 pass.
- Probes `0x416e`/`0x416f` found no literal source uses outside definitions;
  they are **not allocated or certified free**. Subsequent native builds now
  provide both editions' compiled banks; native/dynamic accesses require review. No Birch caller or
  runtime story transition is claimed implemented.
- The owner's `COMPARE=0` workflow change at `7411b883` is preserved.

## Reproduce focused checks

### Native field-script evidence checkpoint

- `scripts/build_native_field_scripts.py` independently preprocesses/assembles
  965 field banks for HG and 965 for SS without Wine. All 1,930 outputs match
  the existing tracked SHA-1 manifest. No ROM or message asset is committed.
- Uses actual native `msgenc` and GNU ARM tools; the output report records tool
  versions, edition defines and bank hashes. Existing-output refusal prevents
  stale-bank reuse. Header-bank regression tests exercise real assembly and
  hashes, including the MW/GNU surplus-argument compatibility case; an
  edition-sensitive test ensures the two define paths are actually distinct.
- All 17 host tests passed locally. The native ARM regression explicitly skips
  when GNU ARM binutils are absent (for example in the Python-only CI job);
  the full script-build helper instead fails on missing tools.
- State audit now has complete binary coverage: probes `0x416e` and `0x416f`
  have no literal hits in either edition. Exit 2 remains intentional, with
  1,565 native/dynamic access sites inventoried for manual/dataflow review.
  No persistent IDs are allocated and no reachable Birch interaction exists.

### Editor checks

Clone the editor forks alongside the game fork. In PKHeX, using .NET 10.0.401:

```sh
dotnet test Tests/PKHeX.Core.Tests/PKHeX.Core.Tests.csproj \
  --filter 'FullyQualifiedName~HGSSBaselineTests|FullyQualifiedName~HGEngineTests'
```

The initial focused tests used `DOTNET_SYSTEM_GLOBALIZATION_INVARIANT=1` because
ICU was absent. After installing `libicu78`, the full suite ran without that
override, including all nine focused cases. The initial full invariant run had
one additional culture-dependent learnability failure, resolved by ICU.
This does not validate browser behavior. No serializer production code was changed. These fixtures
are synthetic and do not substitute for the in-game/editor loop in `README.md`.

Before claiming an imported episode works, obtain disposable real game saves
for both variants and perform the ROM/editor round trip. The owner selected
Emerald and Platinum donors; the Birch-rescue design audit is
`EMERALD_OPENING.md`, not an implemented episode.