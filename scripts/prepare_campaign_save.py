#!/usr/bin/env python3
"""Prepare a fresh, opt-in campaign-save v1 SOURCE candidate, never a ROM/save.

No Git, toolchain, emulator, migration, or runtime operation is performed.
The default native tree and all historical artifacts remain untouched.
"""

import argparse
import ctypes
import errno
import hashlib
import json
import os
from pathlib import Path
import shutil
import stat
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = Path(__file__).with_name("campaign_save_templates")
CONTRACT = ROOT / "expansion/campaign-save-v1.json"
STATUS = "unapproved-source-candidate-runtime-unverified"
TRANSACTION_SELECTION = {
    "unit": "same-partition general/storage pair",
    "required": "both native block CRCs and footer schemas valid, supported campaign header, equal native counters",
    "selection": "newest complete pair using native SaveCounterCompare; equal valid counters choose partition 0",
    "rollover": "0 is newer than 4294967295; otherwise unsigned comparison",
    "split_partition_recovery": False,
    "incomplete_partition_policy": "retain its original bytes; never merge its newer general data with another partition's PC data",
}

# Narrow safety preimages, not new acceptance pins for any historical build.
PREIMAGES = {
    "src/save.c": "c3cd84b17b771db6c878289955794c0e55f86fda65b2205a53b2caaae571d2fc",
    "src/save_arrays.c": "c0ccc14c3b01f20f6ee4623345ee1f328cdebbe3b16e38a71a7aabf060b1cd28",
    "include/save.h": "03d45990d01e7b02ffb8b8678f97f666ced23b8eda75b679e18c1447da6b8eff",
    "main.lsf": "65e60fcecfbb9742cc098ea4e54130cd549c6c366589f0a7d2a72df9f6101723",
    "src/main.c": "04176a10788a1786f87362cd3aafb696e775fec1e3b8d6c6e0d106ff43655655",
    "src/save_data_read_error.c": "eec3482b274e5011db78852cf48ed9fa705a67bcae97a078d48f4d3f4e28c832",
    "include/constants/save_arrays.h": "46e04dc80ec47711a74193141dd0a642069a140ae34f4da580495905f00644a3",
    "include/save_trainer_house.h": "666fd1298c10d6855cdc5941f0a3b6549cf3a427eeed4140b39e96ebf7d292db",
    "src/save_trainer_house.c": "50746a99694913915f7a64f751fc6bc39dec5ccc8f85adf5bc707aac960cbf9a",
    "common.mk": "0236aedc5bcb227db188ea1a51268b1eb7ea79ca1a9bcbbd184f7149c041ef02",
}
SOURCE_DIRS = ("src", "include", "asm", "files", "lib", "sub",
               "heartgold.us", "soulsilver.us", "tools")
SOURCE_FILES = (
    "Makefile", "CMakeLists.txt", "binutils.mk", "common.mk", "config.mk",
    "filesystem.mk", "graphics_files_rules.mk", "platform.mk", "charmap.txt",
    "global.inc", "main.lsf", "rom.rsf", "scr_seq.sha1",
)
EXCLUDED_DIRS = frozenset((".git", "build", "__pycache__",
                           ".cache", ".venv", "cmake-build-debug"))
EXCLUDED_SUFFIXES = frozenset((
    ".nds", ".srl", ".sav", ".dsv", ".dst", ".mln", ".o", ".a", ".elf",
    ".exe", ".dll", ".so", ".d", ".pyc", ".lcf", ".response",
))


def sha(data):
    return hashlib.sha256(data).hexdigest()


def guard_path(path):
    path = Path(os.path.abspath(path))
    if any(p.is_symlink() for p in (path, *path.parents)):
        raise ValueError(f"Symlinked source/output forbidden: {path}")
    return path


def read(path):
    path = guard_path(path)
    info = path.stat()
    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
        raise ValueError(f"Nonregular or hardlinked source forbidden: {path}")
    return path.read_bytes()


def replace_once(text, before, after, label):
    if text.count(before) != 1:
        raise ValueError(f"Missing/ambiguous native integration anchor: {label}")
    return text.replace(before, after, 1)


def check_contract():
    contract = json.loads(read(CONTRACT))
    native = contract["native_allocation"]
    expected = {
        "entry_id": 40, "entry_count": 42, "extension_bytes": 2048,
        "footer_magic": 0x20060623,
        "extension_offset": 0xF614, "general_size": 0xFE28,
        "storage_start": 0xFF00, "storage_size": 0x12310,
        "main_region_limit": 0x23000, "native_page_bytes": 0x1000,
        "native_page_count": 35, "extra_blocks_start": 0x23000,
    }
    if (contract["version"] != 1 or contract["endianness"] != "little"
            or contract["file_bytes"] != 0x80000 or contract["partition_bytes"] != 0x40000
            or any(native.get(key) != value for key, value in expected.items())
            or contract.get("transaction_selection") != TRANSACTION_SELECTION
            or contract["header"] != {
                "magic_ascii": "EHGSCAMP", "magic_offset": 0,
                "version_offset": 8, "length_offset": 10,
                "header_size_offset": 12, "header_bytes": 32,
                "reserved_offset": 14, "reserved_bytes": 18,
                "reserved_policy": "zero only at explicit initialization; preserve when loaded",
            }
            or [(r["id"], r["variable_id_start"], r["variable_count"],
                 r["variable_offset"], r["variable_bytes"],
                 r["flag_count"], r["flag_offset"], r["flag_bytes"])
                for r in contract["regions"]] != [
                    (0, 0x4000, 256, 32, 512, 2400, 544, 300),
                    (1, 0x4000, 288, 844, 576, 2912, 1420, 364)]
            or contract["reserved_tail"]["offset"] != 1784
            or contract["reserved_tail"]["bytes"] != 264
            or contract["legacy_view"]["general_size"] != 0xF628
            or contract["legacy_view"]["storage_start"] != 0xF700
            or contract["legacy_view"]["unchanged_general_prefix_bytes"] != 0xF614
            or contract["legacy_view"]["relocated_general_trailer_bytes"] != 20):
        raise ValueError("Parent-owned campaign-save v1 contract differs")
    return contract


def source_edits(root):
    """Validate all guard/registration preimages before producing any output."""
    baseline = {}
    for name, expected in PREIMAGES.items():
        data = read(root / name)
        if sha(data) != expected:
            raise ValueError(f"Safety preimage mismatch (guard/registration/layout): {name}")
        baseline[name] = data
    for name in ("include/save_campaign.h", "src/save_campaign.c",
                 "campaign-save-source.json"):
        if (root / name).exists() or (root / name).is_symlink():
            raise ValueError(f"Append-only candidate file already exists: {name}")

    save = baseline["src/save.c"].decode()
    save = replace_once(save, '#include "save_arrays.h"\n',
                        '#include "save_arrays.h"\n#include "save_campaign.h"\n', "save include")
    save = replace_once(save,
                        "    case LOAD_STATUS_TOTAL_FAIL:\n"
                        "        ret->statusFlags |= 2;\n"
                        "        // fallthrough\n"
                        "    case LOAD_STATUS_NOT_EXIST:\n"
                        "        Save_InitDynamicRegion(ret);\n"
                        "        break;\n",
                        "    case LOAD_STATUS_UNSUPPORTED_CAMPAIGN:\n"
                        "    case LOAD_STATUS_TOTAL_FAIL:\n"
                        "        // Safe RAM for early sound/options users; never repair/migrate flash.\n"
                        "        Save_InitDynamicRegion(ret);\n"
                        "        ret->flashChipDetected = FALSE;\n"
                        "        ret->statusFlags |= 2;\n"
                        "        break;\n"
                        "    case LOAD_STATUS_NOT_EXIST:\n"
                        "        Save_InitDynamicRegion(ret);\n"
                        "        break;\n", "unsupported/corrupt load result")
    save = replace_once(
        save,
        "    return SaveArray_CalcCRC16MinusFooter(saveData, (u8 *)data + offset, spec->size) == footer->crc;\n",
        "    if (idx == 0 && !CampaignSave_HeaderSupported((const CampaignSave *)"
        "((const u8 *)data + CAMPAIGN_EXTENSION_OFFSET))) {\n"
        "        return FALSE;\n"
        "    }\n"
        "    return SaveArray_CalcCRC16MinusFooter(saveData, (u8 *)data + offset, spec->size) == footer->crc;\n",
        "general footer requires supported header")
    save = replace_once(save, "    u32 __newer_main;\n",
                        "    u32 __newer_main;\n"
                        "    BOOL campaignUnsupported = FALSE;\n"
                        "    BOOL campaignNonblank = FALSE;\n"
                        "    u32 campaignSuccessfulReads = 0;\n"
                        "    enum CampaignPartitionFormat campaignFormat;\n", "guard locals")
    for index in (0, 1):
        buffer = f"data{index + 1}"
        anchor = f"        SaveSlotCheck_InitFromSavedat(&checks_main[{index}], saveData, {buffer}, 0);\n"
        guard = (
            f"        campaignFormat = CampaignSave_ClassifyPartition({buffer}, SAVE_PAGE_MAX * SAVE_SECTOR_SIZE);\n"
            "        campaignSuccessfulReads++;\n"
            "        if (campaignFormat != CAMPAIGN_PARTITION_BLANK) {\n"
            "            campaignNonblank = TRUE;\n"
            "        }\n"
            "        if (campaignFormat == CAMPAIGN_PARTITION_LEGACY\n"
            "            || campaignFormat == CAMPAIGN_PARTITION_UNSUPPORTED) {\n"
            "            campaignUnsupported = TRUE;\n"
            "        }\n")
        save = replace_once(save, anchor, guard + anchor, f"successful-read guard {index}")
    save = replace_once(save, "    Heap_Free(data1);\n    Heap_Free(data2);\n",
                        "    Heap_Free(data1);\n    Heap_Free(data2);\n"
                        "    if (campaignUnsupported) {\n"
                        "        return LOAD_STATUS_UNSUPPORTED_CAMPAIGN;\n"
                        "    }\n"
                        "    // Nonblank input needs at least one complete, same-counter bank.\n"
                        "    // In particular, do not rely on the native one-pair GF_ASSERT.\n"
                        "    if (campaignNonblank\n"
                        "        && !(checks_main[0].valid && checks_sub[0].valid\n"
                        "             && checks_main[0].count == checks_sub[0].count)\n"
                        "        && !(checks_main[1].valid && checks_sub[1].valid\n"
                        "             && checks_main[1].count == checks_sub[1].count)) {\n"
                        "        return LOAD_STATUS_TOTAL_FAIL;\n"
                        "    }\n", "fail closed after freeing both read buffers")
    save = replace_once(save,
                        "    if (numGood_main == 0 && numGood_sub == 0) {\n"
                        "        return LOAD_STATUS_NOT_EXIST;\n"
                        "    }\n",
                        "    if (numGood_main == 0 && numGood_sub == 0) {\n"
                        "        // A new game requires two successful, genuinely blank reads.\n"
                        "        // Nonblank or unread banks are not proof of an empty chip.\n"
                        "        return !campaignNonblank && campaignSuccessfulReads == 2\n"
                        "            ? LOAD_STATUS_NOT_EXIST : LOAD_STATUS_TOTAL_FAIL;\n"
                        "    }\n", "only proven blank reads may initialize a writable new game")
    # Keep the native counter comparator and recovery outcomes. In the 2/1
    # branch, an invalid storage check has dummy counter zero; after rollover
    # that must not compare equal to a valid newer general counter zero.
    for main_count, storage_count in ((2, 2), (1, 2), (2, 1)):
        before = (
            f"    if (numGood_main == {main_count} && numGood_sub == {storage_count}) {{\n"
            "        if (checks_main[__newer_main].count == checks_sub[__newer_main].count) {\n")
        after = (
            f"    if (numGood_main == {main_count} && numGood_sub == {storage_count}) {{\n"
            "        if (checks_main[__newer_main].valid && checks_sub[__newer_main].valid\n"
            "            && checks_main[__newer_main].count == checks_sub[__newer_main].count) {\n")
        save = replace_once(save, before, after,
                            f"newer complete transaction validity {main_count}/{storage_count}")
    save = replace_once(
        save,
        "        if (checks_main[__older_main].count == checks_sub[__older_main].count) {\n",
        "        if (checks_main[__older_main].valid && checks_sub[__older_main].valid\n"
        "            && checks_main[__older_main].count == checks_sub[__older_main].count) {\n",
        "older complete transaction validity")

    arrays = baseline["src/save_arrays.c"].decode()
    arrays = replace_once(arrays, '#include "save_trainer_house.h"\n',
                          '#include "save_trainer_house.h"\n#include "save_campaign.h"\n',
                          "registry include")
    arrays = replace_once(
        arrays,
        "     SAVE_TRAINER_HOUSE,\n     0,\n"
        "     (SAVESIZEFN)Save_TrainerHouse_sizeof,\n"
        "     (SAVEINITFN)Save_TrainerHouse_Init,\n",
        "     SAVE_TRAINER_HOUSE,\n     0,\n"
        "     (SAVESIZEFN)Save_TrainerHouseCampaign_sizeof,\n"
        "     (SAVEINITFN)Save_TrainerHouseCampaign_Init,\n", "only entry 40 callbacks")
    linker = baseline["main.lsf"].decode()
    linker = replace_once(linker, "    Object src/save_trainer_house.o\n",
                          "    Object src/save_trainer_house.o\n"
                          "    Object src/save_campaign.o\n", "native linker object")
    return {
        "src/save.c": save.encode(),
        "src/save_arrays.c": arrays.encode(),
        "main.lsf": linker.encode(),
        "include/save_campaign.h": read(TEMPLATES / "save_campaign.h"),
        "src/save_campaign.c": read(TEMPLATES / "save_campaign.c"),
    }


def verify_candidate(candidate, root):
    """Reject missing/altered guards, callback swaps, or linker registration."""
    expected = source_edits(guard_path(root))
    for name, data in expected.items():
        if read(candidate / name) != data:
            raise ValueError(f"Candidate guard/registration/template mismatch: {name}")
    for name, expected_hash in PREIMAGES.items():
        if name not in expected and sha(read(candidate / name)) != expected_hash:
            raise ValueError(f"Candidate changed protected layout/control flow: {name}")
    return {name: sha(data) for name, data in expected.items()}


def excluded_file(name):
    path = Path(name)
    return (path.suffix.lower() in EXCLUDED_SUFFIXES
            or path.name.startswith("baserom.")
            or path.name.endswith((".lcf.template", ".response.template"))
            or path.suffix.lower() in {f".ds{i}" for i in range(10)}
            or path.suffix.lower() in {f".ml{i}" for i in range(10)})


def copy_sources(root, tree):
    """Copy only source roots/assets; never open saves, ROMs, or executables."""
    inventory = {}
    excluded = []

    def copy(path):
        name = path.relative_to(root).as_posix()
        if excluded_file(name):
            excluded.append(name)
            return
        data = read(path)
        # Native host executables sometimes have no suffix. Do not consume them.
        if data[:4] in (b"\x7fELF", b"\xcf\xfa\xed\xfe", b"\xce\xfa\xed\xfe") or data[:2] == b"MZ":
            raise ValueError(f"Executable is not a source input: {name}")
        target = tree / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, target)
        shutil.copymode(path, target)
        inventory[name] = sha(data)

    for name in SOURCE_FILES:
        if (root / name).exists():
            copy(root / name)
    for name in SOURCE_DIRS:
        directory = root / name
        if not directory.exists():
            continue
        guard_path(directory)
        for current, dirs, files in os.walk(directory, followlinks=False):
            current = Path(current)
            for child in sorted(dirs):
                path = current / child
                if (child in EXCLUDED_DIRS or child.startswith("cmake-build-")
                        or path.relative_to(root).as_posix() in ("tools/bin", "tools/mwccarm")):
                    dirs.remove(child)
                    excluded.append(path.relative_to(root).as_posix() + "/")
                elif path.is_symlink():
                    raise ValueError(f"Symlinked source directory forbidden: {path}")
            dirs.sort()
            for child in sorted(files):
                copy(current / child)
    return inventory, sorted(excluded)


def publish(source, output):
    """Linux atomic no-replace publication; fail closed on unsupported hosts."""
    libc = ctypes.CDLL(None, use_errno=True)
    if not sys.platform.startswith("linux") or not hasattr(libc, "renameat2"):
        raise OSError(errno.ENOTSUP, "Atomic exclusive source publication unavailable")
    rename = libc.renameat2
    rename.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
    rename.restype = ctypes.c_int
    if rename(-100, os.fsencode(source), -100, os.fsencode(output), 1):
        error = ctypes.get_errno()
        raise OSError(error, os.strerror(error), str(output))


def prepare(root, output):
    root, output = map(guard_path, (root, output))
    if not root.is_dir():
        raise ValueError("Source root must be a real directory")
    if output.exists():
        raise ValueError("Campaign source output must be fresh")
    for source in (root, ROOT):
        if output.is_relative_to(source) or source.is_relative_to(output):
            raise ValueError("Campaign source output overlaps an input/template checkout")
    check_contract()
    changes = source_edits(root)
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".campaign-source-", dir=output.parent) as tmp:
        tree = Path(tmp) / "tree"
        tree.mkdir()
        inventory, excluded = copy_sources(root, tree)
        for name, data in changes.items():
            target = tree / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
        verify_candidate(tree, root)
        # Verify preserved assets and every unrelated copied source, not just edits.
        for name, before in inventory.items():
            if sha(read(tree / name)) != (sha(changes[name]) if name in changes else before):
                raise ValueError(f"Copied source/asset preservation mismatch: {name}")
            if sha(read(root / name)) != before:
                raise ValueError(f"Source input changed during preparation: {name}")
        report = {
            "schema_version": 1, "status": STATUS, "approved": False,
            "runtime_verified": False, "migration_performed": False,
            "contract_sha256": sha(read(CONTRACT)),
            "changes": {
                name: {"before": inventory.get(name), "after": sha(data)}
                for name, data in sorted(changes.items())
            },
            "copied_source_sha256": inventory,
            "excluded_without_copy": excluded,
            "producer_sha256": sha(read(Path(__file__))),
            "layout": {
                "entry_count": 42, "extension_offset": 0xF614,
                "general_size": 0xFE28, "storage_start": 0xFF00,
                "storage_size": 0x12310, "main_end": 0x22210,
                "main_limit": 0x23000, "pages": [16, 19],
                "save_data_struct_unchanged": True,
            },
            "guard": {
                "unsupported_result": 4,
                "legacy_and_unknown_tags_rejected_before_backup_selection": True,
                "classification_only_after_successful_reads": True,
                "new_game_requires_two_successful_blank_reads": True,
                "nonblank_or_unread_without_usable_pair_rejected": True,
                "all_total_fail_results_disable_flash": True,
                "positive_same_index_selections_require_both_checks_valid": True,
                "native_counter_compare_unchanged": True,
                "safe_ram_initialization_no_flash_mutation": True,
                "terminal_ui": "src/main.c -> ShowSaveDataReadError; while(TRUE) waits for IRQ, no return",
                "normal_save_refuses_false_flash_flag": True,
            },
            "transaction_selection": TRANSACTION_SELECTION,
            "limits": [
                "Source foundation only; no native compile, ROM, save, or emulator was accessed.",
                "The existing generic native read-error text is not a custom incompatibility message.",
                "Native linker/SDK compatibility, actual flash behavior, and gameplay remain unverified.",
                "No donor script integration or migration is supplied.",
            ],
        }
        (tree / "campaign-save-source.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
        publish(tree, output)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    try:
        report = prepare(args.root, args.output)
    except (ValueError, OSError) as error:
        parser.exit(1, f"Campaign source preparation refused: {error}\n")
    print(json.dumps({"status": report["status"], "changes": report["changes"]},
                     indent=2, sort_keys=True))


if __name__ == "__main__":
    main()