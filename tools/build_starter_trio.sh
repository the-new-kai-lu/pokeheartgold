#!/usr/bin/env bash
# Build the starter-trio edition without overwriting the normal ROM filenames.
set -euo pipefail
variant_root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
cd -- "$variant_root"
export WINEDEBUG="${WINEDEBUG:--all}"
make -j "${STARTER_TRIO_JOBS:-8}" GAME_VERSION=HEARTGOLD COMPARE=0 \
    ROM=build/heartgold.us/heartgold-fakemon-starters.nds
make -j "${STARTER_TRIO_JOBS:-8}" GAME_VERSION=SOULSILVER COMPARE=0 \
    ROM=build/soulsilver.us/soulsilver-fakemon-starters.nds
