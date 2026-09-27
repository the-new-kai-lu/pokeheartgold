# Pokeathlon performance safety

All eleven custom species currently use a provisional neutral Pokeathlon profile: **base 3, minimum 2, maximum 4** for each of Power, Skill, Speed, Jump and Stamina, before the original modifiers. A distinct performance design has not been supplied, so this is a documented safe default rather than a finalized species-specific balance choice. It does not alter battle stats.

`CalcBoxMonPokeathlonPerformance` handles custom species before accessing the stock `sPokeathlonPerformanceArcIdxs` array. This prevents IDs 1076–1086 from reading past that canonical array and choosing an arbitrary member of `performance.narc`. Nature/personality/date modifiers still use the original calculation; subsequent Aprijuice adjustments, star colors and minimum/maximum clamping remain unchanged. Canonical species follow the original lookup path, with the original archive data and table.

`pms.narc` is a separate breeding-ancestry table. Its custom-species path already returns the appropriate family hatch species and is unrelated to the Performance page.

## Validation

- The complete modified `pokemon.c` compiles with the supplied Metrowerks compiler under Wine.
- `python3 tools/py_scripts/test_fakemon_performance.py` compiles the actual revised calculation alongside the pristine original and passes **24,608 cases**.
- For canonical IDs 0–493 and all 32 serialized form values, the archive-member selection and every output field match the original function. This preserves existing form arithmetic; it does not claim unsupported canonical forms are valid game data.
- For all eleven custom species, all 32 form values and all 25 natures, the neutral profile is correct, daily modifiers match the original calculation, and no performance archive read occurs. Test personalities and dates vary across cases.
- The regression also verifies the canonical index table, nature table and downstream star/Aprijuice functions remain identical to the pristine baseline.

The final HG and SS emulator smoke runs render the Summary Performance page for shiny Ragnaroc and Voltuff respectively. Their original nature/day modifiers still affect the displayed stars. Playing through a Pokeathlon event remains a manual acceptance check. Component tests do not establish that every minigame has been played through.
