# Custom Pokédex entries

The eleven species are visible in the National Pokédex after they have been seen. They have no Johto regional slots. Original species order and all stock completion/diploma checks remain unchanged.

Save and Pokémon records continue to use species IDs 1076–1086. Within the National Pokédex, Summary and storage interfaces, their consecutive display numbers are **494–504**. The shared display-only mapping is in the main executable so Summary and storage do not depend on the Pokédex overlay being loaded. This keeps the list compact and prevents the stock interface from indexing thousands of empty rows.

The National list supports all 493 canonical entries plus all eleven additions simultaneously. To preserve the assembly interface, the old list storage remains reserved and an expanded list is appended at `PokedexAppData` offset `0x1910`; its count fields are at `0x20F0` and `0x20F2`. All original fields retain their positions, and the original 518-row display buffer is sufficient. Compile-time assertions protect those offsets. The list renderer has a bounds check before populating each display row. Both the50-row search tile window and30-icon preload window reject indices beyond the518-row buffer; the final page otherwise reads into unrelated app fields. The Dex heap grows from0x61000 to0x71000 because expanded resident data exhausted the stock heap during search-entry text loading. The emulator regression records allocation failures and minimum free space.

The stock search first processes canonical species using its original temporary buffers. A wrapper then includes custom seen species, applying name-letter, type, body, height, weight and area filters and inserting them into the selected ordering. Height/weight searches and measurement sorting require caught entries, as in stock. Their encounter-area display is unknown/empty: it allocates an empty area list instead of indexing the stock encounter archive with a sparse species ID.

Approved entry prose is preserved across two or three pages. **Press SELECT on the standard Pokédex entry screen to advance the custom entry’s text page.** Switching species resets to the first page; opening the Pokédex resets the paging state. Canonical entries retain their original text and controls. Native English names/categories/text are used for the additions.

## Validation

- All four affected Pokédex C translation units and overlay 18 assembly compile with Metrowerks under Wine, including the original-offset and expanded-list assertions.
- `python3 tools/py_scripts/test_fakemon_dex_ui.py` compiles the actual display-number and row-builder functions in a host harness. It checks 1,030 row/number cases, the full 504-entry list, numbered and sorted views, empty-list clearing, no regional numbers for additions and unchanged guard values around the display buffer.

- `../hg-engine/.venv/bin/python tools/py_scripts/test_fakemon_dex_icons.py` runs the real Thumb icon renderer for1,641 cases, including the full final-page preload and wrapped/oversized indices. Invalid indices remain hidden without reading species data.
- `python3 tools/py_scripts/test_fakemon_dex_paging.py` checks145 page/input cases using the actual paging routines, plus three hook-state checks. The normal entry grid uses MainSeq11 and the search grid uses MainSeq57; MainSeq06 is the closed cover and must not handle entry pagination.

The final HeartGold build was exercised with headless DeSmuME using an all504-caught fixture. [Evidence and ROM hash](validation/dex/run.json) record the successful run. Screenshots verify the493 Arceus→494 Voltuff boundary, the custom tail grid, Fimbulisk's name/category/types/footprint/dimensions, all three complete prose pages in normal and search-result grids, page wrapping, species-change reset and close/reopen reset. Repeated search covers the final page and a canonical-species interlude before returning to Fimbulisk. The unknown-area map and size-comparison tabs also opened successfully. The final instrumented run recorded zero allocation failures,52,248 bytes minimum total free heap and52,036 bytes minimum largest free block; repeated search exited back to the overworld. The shiny Ragnaroc Performance page rendered all five star rows. Caught canonical-interlude reset was tested in-game; both caught and uncaught cases also pass host tests. The smoke helper's `--dex-browse` option reproduces this route and checks that all three Fimbulisk text regions differ, then wrap/reset correctly, including repeated search. It requires the all504-caught fixture. Supply `--elf build/heartgold.us/main.elf` to collect allocation-failure and free-heap telemetry against that exact build.

The cover shows504 seen/obtained for that fixture. This is a display count, not evidence of diploma or canonical-completion behavior. Size-comparison silhouettes retain the prior registration's template scales and still need calibration of relative physical height. Audio quality and the remaining cases below have not been verified by these screenshots.

Remaining emulator/hardware acceptance cases:

1. Only seen additions appear in the National list; none appear in Johto. Test with one seen addition, all eleven, and all 493 canonical species plus all eleven additions.
2. Scroll across 493→494 and through 504; open each entry, close/reopen the Dex, and change to/from Johto view. The remembered selection should remain valid.
3. Caught flags, names, category, height, weight, footprint, front sprite, gender and cry should be correct. Open height/weight comparison, form/cry tabs and the unknown-area map without freezes or invalid archive reads.
4. Press SELECT through every full text page, especially Fimbulisk’s three pages; switch species and verify page one resets. Canonical entry SELECT behavior must remain unchanged.
5. Exercise every sort order and filters for the custom names, both types, body shape, height, weight and unknown area. Verify canonical results keep their original relative ordering.
6. Confirm diploma/completion rewards still depend only on stock species and no custom species becomes obtainable from ordinary encounters or gifts.
