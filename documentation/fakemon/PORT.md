# Stock-based Fakemon port — audit and prerequisites

Status: **stock HeartGold and SoulSilver build and match retail; no Fakemon are registered and no functional modified ROM has been built.** This branch is separate from hg-engine. Existing game source/data is untouched at this stage.

Base: `9d8b7591f09b65804da2fb2dfd56f320633e0d36`. Approved species/assets are sourced from `the-new-kai-lu/hg-engine`; their source revision, data and asset hashes are captured in `port-audit.json`.

## Feasibility and scope

This is feasible in principle as a source-level expansion, not a copy of hg-engine's binary hooks. Preserve the original canonical species, moves, items, battle formulas, encounters, trainer parties, story, inventory and 18-box PC. The eleven additions remain normally unobtainable. Both US HeartGold and SoulSilver are upstream targets; establish HeartGold first, then build/test SoulSilver separately.

Required integration work:

1. Species validation, personal/evolution/breeding data, names, icons, battle sprites/animations, follower tables, cries, footprints and Dex text/sort/display data. Stock IDs 494–507 already mean eggs and alternate forms. Retaining source IDs 1076–1086 is a candidate, but requires sparse lookup/validation rather than treating every intermediate ID as a species.
2. Stock learnset archives and TM/HM/tutor/egg compatibility. Audit reports seven post-Gen-4 level-up moves: Wild Charge, Snarl, Incinerate, Fire Lash, Icicle Crash, Bulldoze and Hurricane. Machine compatibility also contains modern moves and moves not assigned to stock HGSS machines. Smokescreen is only a symbol spelling difference (`MOVE_SMOKESCREEN` / `MOVE_SMOKE_SCREEN`), not a missing move. No moves have been silently removed or replaced.
3. EXP growth conversion at successful base-to-middle evolution, preserving level and fractional progress. `src/pokemon.c` owns species writes, growth/EXP helpers, `GetMonEvolution` and `MonTryLearnMoveOnLevelUp`.
4. The level-14 Fire Fang/Icicle Plate substitution and reminder behavior (`src/move_relearner.c`). The rare Rimevaran evolution must require Embernewt's own direct Ice KO while holding NeverMeltIce, with that same KO's EXP causing the level-up to 16+. `src/battle/battle_command.c` contains the real `Task_GetExp`; track causality per battle event and clear eligibility after that EXP distribution, rather than setting a persistent "has ever used Ice" flag. Otherwise ordinary Pyrovaran evolution applies. Finals evolve at 49.
5. The approved final-stage base EXP yield of 300 exceeds stock `BaseStats.expYield`'s byte. Use a custom-species lookup in EXP-award logic; do not truncate to 44 or change canonical yields/formulas.
6. Audit hardcoded species bounds, assembly overlay offsets, table indices and archive sizes. Raising a single `MAX_SPECIES` define is insufficient.

## Possible save layout preservation

The stock `Pokedex` is 0x340 bytes. Each caught/seen/gender region has 512 bits. Canonical species consume indices 0–492, and Deoxys form history uses bits 504–511 (`src/pokedex.c`, `SetDex4Flag`). That leaves **exactly eleven bits, 493–503**, available for the eleven Fakemon without enlarging those regions.

Investigate a separate species-to-Dex-slot mapping using those bits. Keep canonical indices and Deoxys history unchanged. Do not blindly expand `NATIONAL_DEX_COUNT`: this also sizes the language array, controls completion checks, and drives UI buffers. Custom language flags, a reliable editor profile marker, display ordering, and old-save initialization still need design/testing. This is a candidate design, not a verified save-format guarantee. Stock diploma/completion conditions should remain attainable without the unobtainable additions.

Only after the ROM layout and round-trip behavior are established should new `fakemon-stock` branches in PKHeX and PKMDS implement its profile. Do not reuse hg-engine's 0xFDB0/0xFE00 save adapter without proof: this port should avoid inheriting its unrelated save expansions.

## Build environment

The user supplied the proprietary build tools and templates required by this build system:

- MWCC/MWAS/MWLD 2.0/sp2p2 for ARM9; 2.0/sp2p3 for ARM7 and supporting libraries; the 1.2/sp2p3 assembler for `asm/nitrocrypto.o`.
- Nitro SDK `makerom.exe`, `makelcf.exe`, `makebanner.exe`, `ntrcomp.exe`, and the link/response templates named in `INSTALL.md`.
- The locally supplied compiler license and a working executable runner (normally Wine under WSL2).

`INSTALL.md` describes setup. The supplied files are local-only and ignored by Git; neither the compiler, SDK, license nor generated ROM is committed. The license contents are never read or included in the audit.

Verified on Ubuntu 24.04 under WSL2, using Ubuntu Wine 9.0 with 32-bit support. Installed the missing dependencies with:

```sh
sudo dpkg --add-architecture i386
sudo apt-get update
sudo apt-get install wine wine32:i386 libpugixml-dev
```

The ARM GNU binutils, build tools and libpng development package were already present. The copied `tools/mwccarm` and `tools/bin` folders initially belonged to root; ownership was changed to the WSL user so the upstream assembler patcher could open its executable for writing. Its misleading `ERROR: No file detected` message was a permissions error. No source/build-system changes were needed to run the supplied executables. Windows `:Zone.Identifier` metadata is ignored.

The stock HeartGold build completed with `WINEDEBUG=-all make -j8 COMPARE=1`, including ARM7/ARM9 compilation, linking, ROM packaging and the final retail SHA-1 check:

- `build/heartgold.us/pokeheartgold.us.nds`: `4fcded0e2713dc03929845de631d0932ea2b5a37`.
- `build/soulsilver.us/pokesoulsilver.us.nds`: `f8dc38ea20c17541a43b58c5e6d18c1732c7e582` (built with `WINEDEBUG=-all make -j8 soulsilver COMPARE=1`).
- Local build logs: `/tmp/pokeheartgold-stock-build.log` and `/tmp/pokesoulsilver-stock-build.log`.

The WSL2 linker issue mentioned in upstream `INSTALL.md` did not occur in this environment.

Both unchanged baselines have passed comparison. Modified builds will use `COMPARE=0`; validate canonical data separately and test new game, save/load, all eleven species in party/boxes/daycare/followers/battles, custom cries, reminders, both evolution branches, EXP transitions and unchanged canonical battle behavior.

## Reproduce the audit

```sh
python3 tools/py_scripts/audit_fakemon_port.py \
  --hg-engine ../hg-engine \
  --output documentation/fakemon/port-audit.json
```

The audit checks all eleven stat totals, records approved data and asset hashes, compares move IDs (not merely spelling), and reports missing toolchain inputs. It does not modify game assets, ROMs, saves, or either editor.
