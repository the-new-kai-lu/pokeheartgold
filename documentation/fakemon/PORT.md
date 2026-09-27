# Stock-based Fakemon port

This branch implements the eleven approved Fakemon and seven newer moves in source-built US HeartGold and SoulSilver. It is independent of hg-engine. Both modified ROM targets build under WSL2 with the locally supplied toolchain. On the base `fakemon-stock` branch, the additions remain normally unobtainable. The separate **`fakemon-starter-trio` edition** gives the player all three first-stage Fakemon and gives Silver all three Johto starters; see [Starter-trio edition](STARTER_TRIO.md) for its distinct ROM names, teams and validation.

Start with [Implementation and testing](IMPLEMENTATION_AND_TESTING.md) for the goal, mechanics, save format, reproduction and full manual acceptance checklist. Component details are in [Moves](MOVES.md), [Assets](ASSETS.md) and [Pokédex UI](DEX_UI.md). The provisional Pokéathlon profile is documented in [Performance](PERFORMANCE.md). `learnset-port.json` records the exact stock TM/tutor intersection and excluded modern-machine-only compatibility. `port-audit.json` is the historical pre-integration audit, not the current implementation status.

## Scope

- Eleven species retain IDs 1076–1086, preserving all canonical species, eggs and forms. National Pokédex display numbers are 494–504; Johto ordering and completion requirements stay stock.
- Seven compact move IDs 468–474: Wild Charge, Snarl, Incinerate, Fire Lash, Icicle Crash, Bulldoze and Hurricane. Original move data and Gen 4 battle mechanics are retained; added moves use the documented effects and existing animation templates.
- Approved stats, abilities, learnsets, evolutions, breeding, EVs, growth transition, artwork, palettes and cries are integrated.
- The Embernewt branch is tied to its own direct Ice KO and that same KO's level-up, with the required held items.
- Save blocks retain their original sizes. Unused Pokédex bits store custom flags; an FK/version 1 marker selects the matching editor profile.
- Matching PKHeX and PKMDS branches are named `fakemon-stock`. Each contains `FAKEMON_STOCK.md`.

## Build environment

The user supplied Metrowerks ARM compiler/assembler/linker versions 2.0/sp2p2, 2.0/sp2p3, 1.2/sp2p3 and the NitroSDK executables/templates described in upstream `INSTALL.md`. Those proprietary tools, license and generated ROMs remain local and ignored by Git.

Ubuntu 24.04 under WSL2 runs the executables through Wine 9.0 with 32-bit support. The missing dependencies were installed with:

```sh
sudo dpkg --add-architecture i386
sudo apt-get update
sudo apt-get install wine wine32:i386 libpugixml-dev
```

GNU ARM binutils, build tools and libpng were already present. The copied `tools/mwccarm` and `tools/bin` folders needed ownership changed from root to the WSL user because the upstream build patches its assembler. `ERROR: No file detected` from that patcher was a write-permissions error. Windows download metadata is ignored.

Before any game changes, both pristine targets matched retail:

- HeartGold SHA-1: `4fcded0e2713dc03929845de631d0932ea2b5a37`.
- SoulSilver SHA-1: `f8dc38ea20c17541a43b58c5e6d18c1732c7e582`.

The upstream WSL2 linker warning did not reproduce. Modified builds intentionally disable retail comparison:

```sh
WINEDEBUG=-all make -j8 COMPARE=0
WINEDEBUG=-all make -j8 soulsilver COMPARE=0
```

Outputs:

- `build/heartgold.us/pokeheartgold.us.nds`
- `build/soulsilver.us/pokesoulsilver.us.nds`

The import/validation scripts requiring `ndspy`/Pillow can use the sibling hg-engine `.venv`. Imports are already checked in; ordinary ROM builds do not require hg-engine or that Python environment.

## Validation evidence

See `validation.json` for final ROM hashes and test status, and `asset-validation*.json` for packaged asset checks. Emulator smoke coverage is explicitly narrower than the complete acceptance checklist. Native desktop control is unavailable in this harness; DeSmuME's Python API provides isolated automated load, UI and save checks. Remaining interactions are documented rather than represented as tested.
