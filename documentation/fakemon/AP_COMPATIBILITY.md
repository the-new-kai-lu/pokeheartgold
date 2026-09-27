# Stock protection checks and emulator save probe

The custom build retains the original DSProt code. A headless DeSmuME probe completed the save flow without entering the monitored emulator-detection penalty callbacks or `GF_AssertFail`. The field and green menu were restored after saving. The empty right-hand menu pane in that final screenshot is not evidence of a stuck save operation.

## Source audit

- `src/touch_save_app.c`, `ov30_0225D64C`: protection checks run during save-UI teardown. Failure paths intentionally leak heap memory; the checks do not directly draw a blank pane or change save serialization.
- `src/application/pokedex/ov18_021E5AA0.c`, `Pokedex_Exit`: analogous checks run on Dex exit.
- `src/overlay_124.c`: field initialization has a penalty callback that allocates memory based on badge count. Repeated detection could therefore exhaust memory, but this was not observed in the probe.
- `src/field_system.c`, `Task_AntipiracyRandom`: advances the random generator twice; it does not draw UI.
- `lib/dsprot/src/mac_owner.c`: the emulator fingerprint checks a particular MAC address together with empty owner-name/January 1 birthday, or an all-zero MAC. It does not reject every emulator configuration.
- `lib/dsprot/src/rom_test.c`: compares cartridge read patterns at selected addresses. It does not compare a checksum of the entire ROM with the original retail image.

No protection bypass was added because the tested save path completed normally. This result covers this emulator configuration, not every firmware profile, flashcart, or physical device.

## Execution evidence

The probe used ARM9 execution hooks resolved from the corresponding `main.elf`, a private input-save copy, and the unique ROM basename `ap-probe-fakemon-20260926.nds`. Unique basenames matter: DeSmuME can otherwise reuse a backup file across test working directories.

Tested HeartGold ROM SHA-256 (before the later Summary display-number fix):
`bbbc8b8ab9062fc5f1374a7522e76ddd56a87308457ae45b55b5f245bf00b9c7`

| Hook | Hit count | First frame |
| --- | ---: | ---: |
| `TouchSaveApp_SaveGame` | 1 | 3051 |
| `TouchSaveApp_PrintSavedMessage` | 1 | 3975 |
| `TouchSaveApp_CloseApp` | 31 | 4065 |
| `ov30_0225D64C` (teardown) | 1 | 4135 |
| `GF_AssertFail` | 0 | — |
| `Task_AntipiracyRandom` | 0 | — |
| `ov30_0225DC08` (save emulator penalty) | 0 | — |
| `ov124_02260D1C` (field initialization penalty) | 0 | — |
| `ov124_02260D58` | 0 | — |

This instrumentation verifies that saving reached its success message and normal UI teardown. It does not independently validate save checksums; save-file round-trip checks are tracked separately. The flashcart-detection return value and every heap allocation were not individually instrumented, so the absence of these callback hits is not a blanket claim that every protection predicate was inspected.
