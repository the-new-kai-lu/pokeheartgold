# Stage 1A validation — 2026-09-26 (America/Los_Angeles)

This is a partial implementation checkpoint, not Stage 1 completion.

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

- Local ROM reproduction: `make -j4` first failed linking `floor`, fixed here.
  Retrying reached asset conversion, where tools segfaulted after Wine assembly
  invocations produced no expected object file (`files/tel/pmtel_book.o`).
  Wine reports experimental WoW64 and no display driver in this Ubuntu 26.04
  sandbox. Root cause is not established: do not attribute the segmentation fault
  to game logic or assume installing a display driver alone will fix it.
- The local sandbox has not produced matching HeartGold/SoulSilver hashes;
  GitHub's successful comparison does not supply local ROM files.
- PKMDS Web Debug build is blocked by NETSDK1147: missing `wasm-tools`.
- No emulator, Windows desktop UI, browser editing loop, real-hardware run,
  versioned in-game milestone save, or imported episode has been tested.
- Earlier Git pushes were rejected with HTTP 403 despite confirmed collaborator
  write access; authenticated API code writes worked. The owner installed the
  Actions workflow separately; it is now present on the game PR branch.

## Reproduce focused editor checks

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