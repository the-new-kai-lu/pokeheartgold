# Seven-move port

The stock-based ROM keeps original HGSS move IDs 0–467 and their data, scripts and text. The seven additions use compact IDs so the original nine-bit packed learnset format remains usable. Editors must use this profile’s mapping rather than hg-engine or modern retail IDs.

| ID | Move | Category | Power | Accuracy | PP | Effect |
|---:|---|---|---:|---:|---:|---|
| 468 | Wild Charge | Physical Electric | 90 | 100 | 15 | One quarter of damage dealt in recoil |
| 469 | Snarl | Special Dark | 55 | 95 | 15 | Both opponents; lower Special Attack one stage |
| 470 | Incinerate | Special Fire | 60 | 100 | 15 | Both opponents; destroy held Berries |
| 471 | Fire Lash | Physical Fire | 80 | 100 | 15 | Lower Defense one stage |
| 472 | Icicle Crash | Physical Ice | 85 | 90 | 10 | 30% flinch chance |
| 473 | Bulldoze | Physical Ground | 60 | 100 | 20 | All adjacent Pokémon; lower Speed one stage |
| 474 | Hurricane | Special Flying | 110 | 70 | 10 | 30% confusion; rain always hits, sun has 50% base accuracy |

Wild Charge uses stock Take Down’s quarter-recoil effect, including Rock Head and Reckless handling. Snarl is added to Soundproof’s blocked moves; sound/Substitute interactions retain HGSS rules. Fire Lash and Bulldoze use the existing stat-drop scripts. Hurricane has its own confusion script and permits hitting Fly/Bounce; weather accuracy respects Air Lock and Cloud Nine. Protect and ordinary immunity checks remain in place.

Incinerate has a new effect, subscript and command. Successful hits destroy held Berries without activating their healing/status effects and without making them recoverable by Recycle. Sticky Hold and a hit absorbed by Substitute prevent destruction, including when the Substitute breaks. Non-Berry items are unaffected. HGSS has no Gems. Berries already consumed before this step (for example an Occa Berry) cannot be destroyed afterward.

Graphics reuse native battle animations: Volt Tackle, Hyper Voice, Flamethrower, Fire Punch, Icicle Spear, Earthquake and Twister, respectively. The move names and mechanics remain those of the new moves. No modern graphical animation assets are claimed.

## Implementation

`tools/py_scripts/port_fakemon_moves.py` installs the data and text idempotently. Run it using a Python environment containing `ndspy`; the sibling hg-engine `.venv` is suitable. It preserves every canonical move record and text entry, replacing unused move-table tail records 468–470 and appending through 474.

The stock battle context embeds its move table before many fields still used by assembly. Increasing that array would silently shift all following fields. Instead, its original allocation remains reserved, and the expanded table is appended at offset `0x3158`. C access and the disassembled AI/display reads use this appended table. Compiler assertions check the table offset and original battle-status offset. Two AI accesses derived from the former table address were separately kept at their original `0x370` offset. This adds 7,600 bytes to the battle context, without changing its existing fields.

The names/descriptions are in message banks 749–751, with one additional Incinerate battle message in bank 197. Battle effect scripts 277/278, subscript 297 and opcode 225 are appended; all original script and command IDs remain unchanged.

Recorded-battle validation accepts moves 0–474 and the original species range 0–495 plus exactly 1076–1086. The unused sparse species gap remains invalid, the held-item maximum remains 536, and the playback selected-move guard accepts 1–474. Record layouts and CRC handling are unchanged. Metronome retains its stock 1–467 selection pool.

## Checks completed

- Compiled the affected C objects and assembly objects with the supplied Metrowerks tools under Wine, including the ABI assertions.
- Assembled both new effect scripts and the Incinerate subscript.
- Encoded all new move/battle text with the game’s real message encoder.
- `tools/py_scripts/test_fakemon_moves.py`: verified all 468 canonical move records and every original entry in the affected message banks against the pristine repository baseline; verified all seven new records. It also compares the Me First forbidden list against that baseline and verifies Soundproof adds only Snarl. Final review found and removed an unintended Snarl addition to Me First; because Me First compares effects, that mistake would also have blocked the canonical move Mist Ball.
- The same test compiles and executes the actual Incinerate command in a native stub harness: 4,296 combinations of held item, Substitute-hit flag, miss flag and Sticky Hold pass. This checks command behavior; it does not emulate the battle scheduler.
- `tools/py_scripts/test_fakemon_recordings.py` assembles and executes the actual replay-bound validation instructions in Unicorn: 197,232 cases cover every 16-bit species, item and move value, plus all 24 party slots and all four move slots. It preserves every original species/item acceptance and rejects the sparse species gap and moves above 474. This test excludes the unchanged CRC/signature preamble and does not claim full replay playback was tested. Run using the sibling `.venv` with `unicorn` installed and ARM binutils available.

See the overall testing handoff for integrated ROM test status. These component checks alone do not establish that every move works end to end in the emulator.

## Emulator acceptance cases

1. Teach each move, save/reload, inspect its name, type, power, PP and description; use it with animations both on and off. Repeat through the compatible save editor and reopen the game save.
2. Wild Charge: verify quarter recoil, minimum recoil, target Substitute damage, Rock Head immunity, Reckless boost, no recoil on Protect or Ground immunity, and recoil after a knockout.
3. Snarl: in doubles hit both opponents, lower each surviving target’s Special Attack once, and leave the ally untouched. Verify Soundproof, Substitute, Clear Body and Protect separately.
4. Incinerate: Berry disappears with its message and no healing; Recycle fails afterward. Test Sticky Hold, Substitute (intact and broken), Protect, misses, Fire immunity, non-Berry held items, a target knocked out by the hit, an Occa Berry and two different opposing Berries in doubles. Confirm consumed player-held items remain removed after saving.
5. Fire Lash: one Defense stage per successful hit; Clear Body, Substitute, Protect and fainted-target handling remain correct.
6. Icicle Crash: can flinch a slower target, never flinches an already-acted target, and respects Inner Focus.
7. Bulldoze: affects an adjacent ally as well as opponents, applies the stock spread-damage reduction, and leaves Flying/Levitate targets untouched. Each surviving affected target loses one Speed stage.
8. Hurricane: repeat under neutral weather, rain and sun; rain cannot miss through accuracy/evasion stages, sun starts from 50%; Cloud Nine/Air Lock suppress both weather changes. Verify confusion, Own Tempo, Protect, Fly/Bounce targets and that Dig/Dive still evade it.
9. Give a new move to an AI-controlled trainer or wild Pokémon and exercise selection, execution, damage displays and switching. Check a canonical move from the same battle for regressions.
