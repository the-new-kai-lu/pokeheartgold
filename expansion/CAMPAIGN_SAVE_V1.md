# Campaign-state format v1 — implementation in progress

This is the first explicit allocation under the
[expanded save contract](SAVE_FORMAT.md). It is not yet a native-tested format,
and it is not enabled in the tested Oldale build.

The machine-readable contract is `campaign-save-v1.json`. Its 2,048-byte block
contains a 32-byte versioned header, separate Emerald and Platinum persistent
variable/flag namespaces, and 264 reserved bytes. It does not claim to port all
donor save subsystems, such as contests or rematch scheduling.

## Allocation

Append the block to the aligned payload of the last general entry, Trainer
House (ID 40), through an opt-in size/initialization wrapper. Preserve the
original Trainer House structure and bytes. Do not add an entry, renumber PC
storage, change `SaveData`, or use unnamed existing flags.

| Component | Existing layout | Activated v1 layout |
| --- | --- | --- |
| General block size | `0xF628` | `0xFE28` |
| Campaign block start | Not allocated | `0xF614` |
| PC block start | `0xF700` | `0xFF00` |
| PC block size | `0x12310` | `0x12310` |
| End of main data | `0x21A10` | `0x22210` |
| Extra blocks start | `0x23000` | `0x23000` |

Native `SaveData_InitSubstructs` appends four bytes to each aligned entry and a
16-byte chunk footer. `SaveData_InitSlotSpecs` aligns each block boundary to
`0x100` and separately rounds its page requirement to `0x1000`. Both constraints
matter: the proposed general/PC blocks still use 16 + 19 = 35 pages, and fit the
existing `0x23000` main region. The six extra blocks are not moved or reclaimed.

The campaign block is inserted before the last entry's trailing four bytes and
the general footer. Those 20 bytes move together. Pokémon records, all earlier
general-record offsets, save-entry IDs/count, and allocated save-RAM size remain
unchanged. The physical file remains 512 KiB; its layout is intentionally no
longer vanilla.

## Interpretation and safety

The header is `EHGSCAMP`, little-endian version 1, length `0x800`, and header
size `0x20`. General-block CRC protection covers the added state. Reserved
header/tail bytes are initialized only for a new allocation and preserved
during unrelated edits.

Emerald provides variables `0x4000..0x40FF` and 2,400 persistent flags. Platinum
provides variables `0x4000..0x411F` and 2,912 persistent flags. These are separate
namespaces: a Hoenn flag must never alias a Johto or Sinnoh flag. Ephemeral
special flags/variables are not part of this persistent allocation.

An activated native build must reject incompatible legacy saves and unsupported
tagged versions before allowing gameplay or writing, rather than treating them
as a new empty game. A corrupt supported backup may still use the normal
same-format recovery path. Native activation is not accepted without that guard.

The PKHeX.Core fork will expose a normal Pokémon-editing view while retaining the
full expanded file, including opaque/reserved bytes. Both editor frontends must
consume that same implementation. Loading, cloning, copying changes, exporting,
backup selection and unknown-version rejection need focused regression coverage.
Vanilla and hg-engine paths remain separate and must continue to work.

Transaction selection must match the native game: choose a complete
general/PC pair from the same partition, with matching counters and valid block
checksums/header schemas. Do not independently combine a newer general block
with another partition's PC block. The native counter comparison treats zero as
newer than `0xFFFFFFFF` at rollover, otherwise compares unsigned counters, and
chooses partition 0 on a valid tie. Preserve incomplete partitions rather than
silently repairing or mixing them. The v1 footer magic is exactly `0x20060623`;
additional regional/container variants are not established by this contract.

No existing save is converted by this document or by creating these source
files. Any later migration must be explicit, produce a separate output, and
preserve the original gameplay records without manufacturing progress.

## Opt-in source preparation and current checks

The default game sources remain unchanged. Prepare a separate candidate from
the owner-local Oldale source tree:

```sh
python3 scripts/prepare_campaign_save.py \
  --root "$OLDALE_SOURCE" \
  --output "$CAMPAIGN_SOURCE"
python3 -m unittest discover -s tests -p test_campaign_save.py -v
```

The output must be fresh and outside either source checkout. The preparer
changes only the save loader, entry-40 callbacks, linker registration, and two
new campaign source/header files. It verifies unchanged assets and unrelated
sources, records before/after hashes, and marks its output unapproved and
runtime-unverified. It does not compile a ROM, inspect a save, or migrate data.
Publication currently requires Linux's atomic no-replace rename support.

The 23 host tests pass. They compile the actual template, Trainer House code,
and extracted native layout/load/save-refusal functions with bounded stubs.
The first 40 payload callbacks use the verified aggregate prefix; this is not
a full native-compiler measurement. Coverage includes allocation, endian/bounds,
reserved bytes, version/legacy/corruption rejection, proven-blank initialization,
same-format recovery, and counter-zero/rollover transaction selection.

Unsupported or unrecoverable nonblank files reach the existing terminal
read-error screen; they cannot silently become writable new games. Its generic
read-error wording is a known limitation, not a custom compatibility message.

The shared editor implementation has separate synthetic preservation tests.
Native compilation, real flash save/load, story-command integration, and actual
editor UI export/reopen checks remain required before this format is released.