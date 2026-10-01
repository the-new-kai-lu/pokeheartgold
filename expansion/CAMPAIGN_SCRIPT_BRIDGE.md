# Opt-in campaign script bridge

This is a source-only interface to [campaign-save v1](CAMPAIGN_SAVE_V1.md).
It does not enable new commands in the default game build, add an NPC, or prove
native gameplay. Generate a separate candidate from the verified Oldale/R7
episode source:

```sh
python3 scripts/prepare_campaign_save.py \
  --root "$OLDALE_SOURCE" --output "$BRIDGED_SOURCE" --script-bridge
```

The input must contain the existing episode command `EnsureRoute101Actors`.
That command already owns opcode **854**, with one halfword result destination.
It remains unchanged. Stock-only input with `--script-bridge` is refused rather
than reserving or taking over that opcode. Format-only preparation without this
option retains its existing five-file native scope.

## ABI

The four added commands each consume four little-endian halfwords:

| Opcode | Command | Operands |
| --- | --- | --- |
| 855 | `CampaignGetFlag` | region, donor flag ID, output, status |
| 856 | `CampaignSetFlag` | region, donor flag ID, value, status |
| 857 | `CampaignGetVar` | region, donor variable ID, output, status |
| 858 | `CampaignSetVar` | region, donor variable ID, value, status |

Region and donor ID are **literal operands**, not host-variable lookups. Region
0 is Hoenn; region 1 is Sinnoh. The allocation's existing bounds and flag-zero
behavior still apply.

Output and status must be valid native scratch IDs `0x8000..0x800C`. Read output
and status must differ. `0x800D` is last-talked, not a scratch destination.
Persistent or undefined destination IDs are refused.

Set values use the native immediate-or-scratch convention. Direct immediates
are below `0x4000`; larger 16-bit values must first be placed in a valid scratch
variable. A value is resolved before status is written, including when those
operands name the same scratch variable.

Status is **1 for success, 0 for failure**. The handler's `BOOL` return is the
native VM's yield signal, not operation success. An invalid status destination
or missing context stops the script. Other checked failures return status zero
without initializing, repairing or changing campaign state.

Callers must check status before interpreting a zero read result as “not set.”
In particular, check before granting an item; set a receipt flag only after
actual item delivery succeeds, and handle any unexpected write failure safely.
The bridge itself does not grant or remove items.

Donor map-local state is not translated by this interface. Emerald's
`FLAG_TEMP_1`, for example, must not acquire permanent behavior merely because
a persistent namespace exists.

## Source scope and validation

The opt-in candidate has eleven changed/added native paths, including the five
save-format paths. It adds one script-command object, declarations, four table
entries and assembler macros. The native table grows from 855 to 859 entries.
The older JSON command metadata was missing the existing actor command; the
candidate adds its accurate opcode-854 record with one halfword argument before
the four new records. Original metadata `0..853` and argument types remain intact.

The focused source suite passed 31 tests: eight bridge tests and the existing
23 campaign-save tests. Tests reconstruct the episode input from the published
episode edits, verify actor-command preservation and stock-profile refusal,
and exercise actual extracted operand resolution, script stopping and dispatch
with narrow host stubs. The actual R7 source-anchor check also passes.

Native SDK compilation, runtime script dispatch, faithful NPC implementation,
map-local lifecycle behavior and real game-created save round trips remain
separate acceptance gates. No migration or native runtime approval is supplied.