# Fakemon starter-trio edition

This separate `fakemon-starter-trio` branch builds on the stock-based Fakemon port. Professor Elm gives the player Voltuff, Embernewt and Sedgling, while Silver steals all three original Johto starters. The underlying eleven species, seven added moves and save format are the same as `fakemon-stock`.

## Play this edition

Start a **new game** to receive the trio during Elm's opening conversation. Each is level 5, in a Poké Ball, with your trainer identity, random IVs and its normal starting moves. Voltuff starts in the lead slot and becomes the follower. You can nickname each Pokémon separately.

There is no starter selection screen. Elm's device still contains Chikorita, Cyndaquil and Totodile after the gift; all three balls disappear after the first Silver encounter. The gift, theft investigation and Silver's later attempt to return the Pokémon have matching dialogue. Existing saves that already received a starter are not retroactively given the trio.

The edition uses Chikorita as the internal legacy starter-choice value so stock story scripts continue to have a valid stock value. Every Silver team variant now has the same party, so this value does not choose a different rival team.

## ROMs and build

Run from the repository root under the configured WSL toolchain:

```sh
./tools/build_starter_trio.sh
```

The script builds both US versions and overrides only the final ROM filename:

- `build/heartgold.us/heartgold-fakemon-starters.nds`
- `build/soulsilver.us/soulsilver-fakemon-starters.nds`

It leaves the existing `pokeheartgold.us.nds` and `pokesoulsilver.us.nds` files untouched. Intermediate objects are shared with the normal build directories; running an ordinary `make` on this branch would deliberately build this edition under the ordinary filename. Use the helper above to keep the filenames separate.

The existing PKHeX and PKMDS **`fakemon-stock` branches** read and edit these saves. This edition needs no additional save format or editor changes. Save files, ROMs and proprietary build tools stay local and are not committed.

## Graphics and name corrections

The current build uses uppercase in-game species names, subdued Electric/Fire/Ice palettes and new follower walking poses at species-specific sizes. Existing saves remain compatible: older unnicknamed Fakemon defaults normalize to uppercase when read, while deliberate nicknames remain unchanged. Save normally afterward to retain the normalized defaults. You do not need a new game for these corrections. See [revision details and previews](graphics-revision/README.md).

## Silver's teams

All 27 records were updated: the three unnamed Passerby Boy variants actually used for the first battle, three legacy first-battle records, and all later rival/partner variants. The other trainers are unchanged.

| Encounter | Other retained Pokémon | Johto starter trio |
| --- | --- | --- |
| Cherrygrove / legacy first battle | None | Chikorita, Cyndaquil, Totodile: Lv. 5 |
| Azalea Town | Gastly 14, Zubat 16 | Bayleef, Quilava, Croconaw: Lv. 18 |
| Burned Tower | Gastly 20, Magnemite 18, Zubat 20 | Bayleef, Quilava, Croconaw: Lv. 22 |
| Goldenrod Underground | Golbat 32, Magnemite 30, Haunter 32 | Meganium, Quilava, Feraligatr: Lv. 34 |
| Victory Road | Golbat 38, Magneton 37, Haunter 37 | Meganium, Typhlosion, Feraligatr: Lv. 40 |
| Mt. Moon | Golbat 47, Magneton 46, Gengar 48 | Meganium, Typhlosion, Feraligatr: Lv. 50 |
| Indigo Plateau rematch | Crobat 58, Magneton 55, Gengar 56 | Meganium, Typhlosion, Feraligatr: Lv. 60 |
| Dragon's Den partner battle | Crobat 58, Gengar 56 | Meganium, Typhlosion, Feraligatr: Lv. 60 |

Sneasel is removed first when a party needs space; Kadabra/Alakazam is removed next from parties that originally had six members. This preserves the bat's friendship progression, Ghost coverage and Electric coverage. Existing species-specific moves, held items and trainer metadata are retained.

The Underground's original Water-starter variant used level 32, versus level 34 for the other two. This edition consistently uses 34; Quilava remains unevolved until its normal level 36. Dragon's Den has five Pokémon on Silver's side: the NPC multi-battle path uses independent parties with six available slots, so it can retain Crobat and Gengar alongside all three starters.

The exact before/after record inventory is in [starter-trio-rival-teams.json](starter-trio-rival-teams.json).

## Verification

Both ROMs built successfully. The original two ROM files retain their previous SHA-256 hashes. Build hashes and results are recorded in [starter-trio-validation.json](starter-trio-validation.json).

The detailed opening-event and first-rival captures below come from the initial starter edition. Current graphics/name checks, save compatibility, walking captures and exact build hashes are recorded separately in [graphics-revision/README.md](graphics-revision/README.md).

Run the targeted checks after building:

```sh
# Use a Python environment with ndspy installed for packaged-ROM checks.
python3 tools/py_scripts/test_starter_trio_gift.py \
  --rom build/heartgold.us/heartgold-fakemon-starters.nds \
  --rom build/soulsilver.us/soulsilver-fakemon-starters.nds
python3 tools/py_scripts/test_starter_trio_rival.py --rom build/heartgold.us/heartgold-fakemon-starters.nds
python3 tools/py_scripts/test_starter_trio_rival.py --rom build/soulsilver.us/soulsilver-fakemon-starters.nds
```

The gift check compiles the real starter-task C code with host stubs and interprets the assembled Elm script. It verifies the three species, level, trainer/memo/ball metadata, Pokédex update calls, field-task sequence, memory cleanup and 69 script paths covering approach position, nickname choice/retry, device interaction and repeated entry. The packaged script and two changed dialogue banks match both ROMs byte for byte. This check does not emulate graphics, real nickname input or asynchronous field tasks.

The rival check makes 1,604 assertions per ROM, covering all 27 changed records, equal variants, levels/evolutions, party limits, preserved moves/items and trainer metadata, unchanged unrelated trainers and the exact packaged trainer archives.

HeartGold's actual Elm event was exercised using DeSmuME's Python API. The input was a genuine new-game battery save created in the base port before entering Elm's lab, with no edited Pokémon or story state. The variant awarded all three starters, showed each nickname prompt, resumed field control and displayed Voltuff as the follower. The party UI showed three level-5 Pokémon. An actual game save loaded in a separate emulator process; talking to Elm again produced ordinary dialogue and no additional Pokémon. Screenshots and exact input logs are in [elm-emulator.json](validation/starter-trio/elm-emulator.json).

The real game-created save passed 71 PKHeX checks: party contents, level/EXP, moves/PP, abilities, player OT/ID, Poké Balls and met data, health, EVs, Pokédex flags, the starter flag and save/Pokémon checksums. An editor write/reload retained every Pokémon byte; see [elm-gift-save.json](validation/starter-trio/elm-gift-save.json). The post-reload, repeated-interaction save passed the same 71 checks with all three original PIDs and Pokémon details unchanged; see [elm-repeat-save.json](validation/starter-trio/elm-repeat-save.json).

SoulSilver independently booted to its responsive title screen using a fresh isolated ROM copy. Its Elm scripts, dialogue and rival archives match the verified build inputs. SoulSilver's full opening event was not separately played; see [soulsilver-boot.json](validation/starter-trio/soulsilver-boot.json).

HeartGold's first Silver battle also passed. A separate copy of the real gift save was moved to the Cherrygrove trigger with documented story/location edits, leaving all Pokémon bytes unchanged. The real event generated trainer 496 with Chikorita, Cyndaquil and Totodile at level 5. Normal battle menus were used to switch Pokémon and defeat all three; Silver departed, field control resumed, and an actual game save retained Cherrygrove scene 4 and the encounter-complete flag. Runtime hooks recorded zero assertions and zero allocation failures over 34,337 frames. See [first-silver-emulator.json](validation/starter-trio/first-silver-emulator.json) for fixture edits, inputs, screenshots and saved-state checks.

Still unplayed: nickname keyboard acceptance/retry, the full uninterrupted Mr. Pokémon errand, losing the first battle, returning for the theft investigation, later Silver encounters and Dragon's Den. All later team records are source/package-validated, but those battles have not been played. Audio was muted during these smoke tests.

## Playthrough acceptance checklist

- Receive exactly three level-5 Fakemon during Elm's introduction; nickname each independently, including retrying a nickname.
- Leave/re-enter the lab, talk to Elm and the device again, and confirm no duplicate gifts, follower placement problems or movement locks.
- Save and restart; confirm all three party members, their original-trainer identity, moves, abilities and follower persist.
- Complete Mr. Pokémon's errand. Fight all three of Silver's level-5 Johto starters, including changing opponents after each faint, and finish the event on either a win or a loss.
- Return to the lab. Confirm the investigation and rival-name entry continue normally, the device has no balls and dialogue describes all three stolen Pokémon.
- At each later encounter, verify the table above, full-party switching and normal post-battle story progress.
- In Dragon's Den, verify Silver can use all five party members, the party indicators render correctly, and the Lance/Clair multi battle finishes normally.
- Confirm the late Elm dialogue about Silver returning the three Pokémon is coherent.

The complete species/move/evolution acceptance checklist remains in [IMPLEMENTATION_AND_TESTING.md](IMPLEMENTATION_AND_TESTING.md).

## Early ice-branch items and menu portraits

See [the item and artwork revision](secret-items/README.md) for the Route 46 Icicle Plate, Ethan/Lyra NeverMeltIce gift, older-save recovery, warmer electric icons, and validation.

## Side-facing follower correction

All eleven custom followers have revised alternating left/right foot poses. See [art, reproduction and validation](side-gait/README.md). Existing saves are compatible.
