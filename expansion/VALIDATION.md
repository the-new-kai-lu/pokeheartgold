# Stage 1A validation — 2026-09-26 (America/Los_Angeles)

This is a partial implementation checkpoint, not Stage 1 completion.

## Passed

- Supplied compiler and NitroSDK archive SHA-256 hashes exactly match the
  archives referenced by the host's devcontainer setup; see `baseline.json`.
- Seven Python baseline/mutation tests and the live source contract audit.
- Native host utilities compile after correcting `gen_fx_consts` libm link order.
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

- Full matching ROM: `make -j4` first failed linking `floor`, fixed here.
  Retrying reached asset conversion, where tools segfaulted after Wine assembly
  invocations produced no expected object file (`files/tel/pmtel_book.o`).
  Wine reports experimental WoW64 and no display driver in this Ubuntu 26.04
  sandbox. Root cause is not established: do not attribute the segmentation fault
  to game logic or assume installing a display driver alone will fix it.
- Matching HeartGold and SoulSilver hashes have not been produced.
- PKMDS Web Debug build is blocked by NETSDK1147: missing `wasm-tools`.
- No emulator, Windows desktop UI, browser editing loop, real-hardware run,
  versioned in-game milestone save, or imported episode has been tested.
- Git pushes were rejected with HTTP 403, denied to `kai-lu-replit`, although
  GitHub independently confirms collaborator write access. Authenticated GitHub
  API writes work: PKHeX regression tests are published in draft PR #1.
  This game checkpoint is being published through that route without the new
  Actions workflow: uploading that file returns 404 and the token lacks
  `workflow` scope. The CI file remains in the original local branch and patch
  archive. Run the documented Python commands manually until CI is installed.

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

Before continuing imports, reproduce the matched vanilla ROM in a working
32-bit-compatible Wine/toolchain environment, select donor editions with the
owner, and obtain one disposable real game save per supported ROM variant.