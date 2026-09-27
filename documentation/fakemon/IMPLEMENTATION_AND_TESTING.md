# Stock-based Fakemon port: goal, implementation, and acceptance tests

## Goal

Add the eleven approved Fakemon and seven required newer moves to the source-built US HeartGold/SoulSilver games, preserving original gameplay for canonical species and moves. Keep the hg-engine build separate. Supply matching `fakemon-stock` branches of PKHeX and PKMDS. The additions remain normally unobtainable: no encounters, gifts, starters, trainer parties, or shop changes.

This is a source port, not an application of hg-engine binary hooks. The original source was first built with comparison enabled for both versions; both matched retail byte for byte.

## Implemented design

Species retain IDs 1076–1086: Voltuff, Surguenon, Raijinque, Embernewt, Pyrovaran, Magmalisk, Rimevaran, Fimbulisk, Sedgling, Cragaviar, Ragnaroc. Stock IDs 1–493 and the egg/form entries 494–507 retain their meanings. Reserved gaps are not playable species.

The seven added move IDs are local to this port: 468 Wild Charge, 469 Snarl, 470 Incinerate, 471 Fire Lash, 472 Icicle Crash, 473 Bulldoze, 474 Hurricane. These fit the stock 9-bit learnset format. A Pokémon file with these IDs must be interpreted using this game's profile. Do not exchange it with retail games or the hg-engine edition without explicit conversion.

Data import preserves all stock personal, evolution and learnset entries. New species use the approved 315/405/600 BST spreads, abilities, breeding groups, gender ratios, hatch cycles, EV yields, friendship and catch rates. Final-stage EXP yield 300 is provided by a custom lookup, since the stock personal-data field holds only a byte.

The five Pokéathlon categories use a provisional profile of base 3, minimum 2 and maximum 4 for every addition, with the original nature/day/Aprijuice modifiers. This explicitly bypasses the canonical-only species lookup table. See [Performance](PERFORMANCE.md) for the default and its tests.

First evolutions occur at 16; final evolutions at 49. Base stages use Medium Slow, later stages Slow. On successful base-to-middle species change, EXP is converted to retain the current level and fractional progress, rounded down to the nearest valid EXP point; level 100 remains 100. Canceling an evolution performs no conversion.

Embernewt's level 14 Fire Fang entry becomes Ice Fang when it is learned/reminded while holding Icicle Plate. Its separate level 45 Fire Fang entry is unchanged. The rare evolution requires Embernewt itself to deal the direct Ice KO while holding NeverMeltIce and that same KO's EXP to raise its level to 16+. The event is matched to party slot, PID, OT and victim. Exp Share, allies, passive damage, another victim, earlier KOs, unrelated later level-ups and Rare Candy do not qualify. Ordinary Pyrovaran evolution is the fallback. Neither evolution item is consumed.

The original HGSS TM/HM and tutor inventory remains intact. Compatibility is the intersection of the approved compatibility lists with the stock inventory. `learnset-port.json` explicitly lists excluded modern-machine/tutor-only options. The seven additions remain available through the approved level-up learnsets. No additional modern machines or tutor NPCs are introduced.

Save block dimensions remain retail. The Pokédex's existing unused bits 493–503 store custom caught/seen/gender flags. Deoxys form bits 504–511 are preserved. Unused language bytes 494/495 contain ASCII `FK`, and the trailing dummy byte contains version 1. Old unmarked saves receive this marker and clean custom bits when their Pokédex is accessed. Original completion/diploma criteria remain 493 canonical species. Custom foreign-language capture flags are not stored.

## Test environment and limits

The available computer-control tool explicitly disables native desktop control. A local DeSmuME Python API is available, so automated ROM execution, input, screenshots and save import/export can be exercised without desktop automation. Successful compilation or unit tests alone are not proof of complete in-game behavior. The final validation report must distinguish native tests, archive checks, emulator smoke coverage, and outstanding manual cases.

Use disposable copies of saves. Preserve the existing hg-engine saves and ROM. Do not load a custom save into retail HGSS or attempt link trades with unmodified games. This port's stock-sized saves and hg-engine's expanded saves are different formats.

## Reproduction

Build with the locally supplied Metrowerks/Nitro tools (not included in Git):

```sh
WINEDEBUG=-all make -j8 COMPARE=0
WINEDEBUG=-all make -j8 soulsilver COMPARE=0
python3 tools/py_scripts/test_fakemon_runtime.py
python3 tools/py_scripts/test_fakemon_dex_ui.py
python3 tools/py_scripts/test_fakemon_dex_paging.py
python3 tools/py_scripts/test_fakemon_performance.py
../hg-engine/.venv/bin/python tools/py_scripts/test_fakemon_moves.py
../hg-engine/.venv/bin/python tools/py_scripts/test_fakemon_recordings.py
../hg-engine/.venv/bin/python tools/py_scripts/test_fakemon_dex_icons.py
../hg-engine/.venv/bin/python tools/py_scripts/test_fakemon_data.py --rom build/heartgold.us/pokeheartgold.us.nds
../hg-engine/.venv/bin/python tools/py_scripts/validate_fakemon_assets.py --rom build/heartgold.us/pokeheartgold.us.nds
```

For emulator smoke checks, install `py-desmume` in the chosen Python environment. Use a disposable save made with the matching editor, starting in the field with the menu visible and the test species first in the party. These helpers drive that fixture layout; they do not automatically assert the meaning of screenshots:

```sh
../hg-engine/.venv/bin/python tools/py_scripts/emulator_smoke_fakemon.py \
  --rom build/heartgold.us/pokeheartgold.us.nds \
  --save /path/to/disposable-test.sav --output /tmp/unique-fakemon-smoke
../hg-engine/.venv/bin/python tools/py_scripts/emulator_smoke_moves.py \
  --rom build/heartgold.us/pokeheartgold.us.nds \
  --save /path/to/disposable-move-test.sav --output /tmp/unique-move-smoke
```

Each output directory must be new. Each run gets a unique ROM basename because DeSmuME can otherwise share its battery-save file between working directories. Review the screenshots and reopen the exported save in the matching editor. The `validation/` directory contains selected reviewed screenshots and machine-readable save audits; ROMs and save fixtures are deliberately excluded from Git.

The recorded-battle validator test additionally uses `Unicorn` to execute the real ARM validator instructions across every 16-bit species, item and move value. It does not play a full recorded battle.

The host runtime tests compile the actual `src/fakemon.c` with minimal platform stubs. They exhaustively test EXP conversion over the full base growth curve and exercise the causal KO state machine, learning substitution and hatch mapping. They cannot prove battle hooks are reached correctly on hardware; that is the purpose of the emulator/manual cases below.

## End-to-end acceptance checklist

Record the ROM hash, game version, editor commit, save fixture, result, and screenshots/logs for each pass. Use all eleven species, both genders, both normal/shiny palettes, and both games where practical.

1. Boot a new game and a preexisting retail save. Save, reboot and continue. Check ordinary party, bag, PC 18 boxes, Pokédex, story, wild battles and trainer battles. Stock species/moves/items must remain unchanged.
2. Create base-stage Pokémon with the matching editor profile. Load them in party and PC. Verify names, typing, stats, ability, EXP, gender, moves/PP, icons and summary pages. Move them between boxes, withdraw/deposit, reorder party, save, reopen in both editors, edit, and load again. Check all eleven, especially IDs 1082–1086 and compact move IDs 468–474.
3. View front/back battle sprites, both animation frames, palettes, cries and followers. Enter/exit buildings, turn/walk/run in each direction, toggle follower visibility, open summary/PC/daycare/Hall of Fame and Pokéathlon screens, and check that canonical forms and eggs retain their graphics. Listen to every custom cry, including repeated playback and simultaneous battle sounds.
4. Check custom Pokédex seen/caught/gender flags, entry text/pages, names, dimensions, footprints and browsing. Confirm custom entries do not affect stock diploma completion. Check Deoxys history and canonical foreign-language flags before/after repeated custom writes and editor round-trips.
5. Evolve each base at 16 and each middle at 49. Test delayed evolutions, cancellation, Everstone, Rare Candy, near-boundary fractional EXP, and level 100 behavior. Verify stats and ability after evolution, no unintended level loss/jump, and correct next-level threshold.
6. For the rare Embernewt branch: learn level 14 Fire Fang normally; repeat holding Icicle Plate and verify Ice Fang. Relearn both conditions; verify level 45 Fire Fang is unaffected. Give NeverMeltIce, arrange exact KO EXP to cross level 16, and KO directly with Ice Fang. Expect Rimevaran and item retained. Repeat with wrong held item, Fire KO, poison/weather KO, ally KO, previous Ice KO without level-up, Exp Share, different victim, switched party slot, later unrelated level-up, Rare Candy, and canceled evolution; expect Pyrovaran or no evolution as appropriate. Repeat in doubles and with multiple levels from one KO.
7. Exercise Wild Charge recoil including Rock Head/substitute/fainting interactions; Snarl spread damage and Sp.Atk drops/Soundproof; Incinerate berry destruction versus nonberries, substitutes, immunity and fainting; Fire Lash's defense drop; Icicle Crash's flinch chance/contact behavior; Bulldoze spread/ally hits/Speed drop/immunity; Hurricane normal/rain/sun accuracy, confusion and airborne targets. Check PP Ups, move reminder, disabling/encoring, AI evaluation, Metronome/Assist/Mimic/Sketch where applicable. Canonical Thunder, recoil, sound and berry moves must retain their original behavior. The canonical Metronome pool intentionally remains unchanged. Record and replay battles containing custom species and new moves; invalid species gaps and move IDs must still be rejected.
8. Breed compatible parents from each line. Check egg species (both varan branches yield Embernewt), approved egg moves, hatch cycles, inherited moves/IVs, gender ratio and hatch graphics/cry. Test stock TMs/HMs and every approved stock tutor, including refusal cases and move deletion.
9. Finish a battle against a final custom species in a controlled fixture and verify base EXP 300 enters the original Gen 4 EXP formula. Check EV yields for all stages. Do not add permanent encounters merely to test this.
10. Editor profile isolation: ordinary retail saves remain ordinary; hg-engine saves remain hg-engine; marked stock-port saves use this profile. Repeated clone/export edits preserve custom flags and unrelated bytes. Save-copy counter rollover/corrupt backup behavior should follow existing stock save selection. Both editors should clearly state that retail legality checks do not certify the Fakemon.

## Delivery status

Both ROM targets build and packaged data/resource checks pass. Native tests cover EXP conversion, the rare-evolution event state, move-command logic, Dex list/page helpers and recorded-battle ID validation. DeSmuME smoke runs verify rendering, save/reload, and the seven new moves' names, types and PP in the summary. Matching editor checks preserve party records and all eleven boxed species. Final HeartGold Dex checks verify the 493/494 boundary, custom browsing, normal and search-result Fimbulisk pagination/wrap/reset, repeated search, final-page scrolling, and opening custom area/size tabs. The instrumented run reports zero allocation failures. Both games render the corrected Performance page.

PKMDS CI passes all 475 tests. PKHeX reports 608 passes, one skip and one preexisting upstream failure (`EffortExpLegalityTests.ZeroEVs_ReturnsZero`, also reproduced on the pristine baseline). The custom profile tests pass.

See [the validation report](validation.json) for exact ROM hashes and coverage, [save round-trip evidence](validation/editor-roundtrips.json), and [Pokédex UI results](DEX_UI.md). The full battle/evolution/breeding/audio checklist above remains manual acceptance work; it is not represented as completed gameplay testing.
