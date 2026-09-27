#!/usr/bin/env python3
"""Build US HG/SS field scripts with GNU tools, not the Windows ROM toolchain.

This is a script-only evidence build. Every bank must match scr_seq.sha1;
it does not build a ROM or approve save-state allocations.
"""
import argparse
import concurrent.futures
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]
SCRIPT_DIR = Path("files/fielddata/script/scr_seq")
DEFINES = [
    "GAME_REMASTER=0", "ENGLISH", "PM_KEEP_ASSERTS", "SDK_ARM9",
    "SDK_CODE_ARM", "SDK_FINALROM", "SDK_ASM", "PM_ASM",
]


def run(args, cwd=ROOT):
    return subprocess.check_output([str(a) for a in args], cwd=cwd, stderr=subprocess.PIPE)


def gas_syntax(text):
    # This bank format contains data directives, not string literals. Fail rather
    # than incorrectly treating a future quoted semicolon as a MW comment.
    if re.search(r'^\s*\.(?:ascii|asciz|string)\b', text, re.M):
        raise ValueError("String directive needs explicit GNU conversion review")
    text = re.sub(r";[^\n]*", "", text)
    # GNU macro calls split on spaces as well as commas; MW accepts spaced
    # arithmetic operands. Keep an expression a single argument.
    text = re.sub(r"[ \t]*([+])[ \t]*", r"\1", text)
    # D22R0101's header supplies a redundant zero to these one-argument MW
    # macros. GNU rejects surplus arguments; Fixed itself already emits zero.
    text = re.sub(
        r"^([ \t]*InitScriptEntry_On(?:Resume|Transition)[ \t]+[^,\n]+),[ \t]*0[ \t]*$",
        r"\1", text, flags=re.M,
    )
    # MW's explicit unaligned data mode is GNU as's default for data directives.
    text = re.sub(r"^\s*\.option alignment off\s*$", "", text, flags=re.M)
    return re.sub(r"^\s*\.rodata\s*$", '.section .rodata', text, flags=re.M)


def preprocess(path, edition, includes):
    return gas_syntax(run([
        "gcc", "-E", "-P", "-x", "assembler-with-cpp",
        *["-D" + d for d in [edition, *DEFINES]],
        *[arg for p in includes for arg in ("-I", p)], path,
    ]).decode())


def assemble_bank(source, directory, edition, includes):
    stem = directory / source.stem
    stem.with_suffix(".s").write_text(preprocess(source, edition, includes))
    run(["arm-none-eabi-as", "-I", directory, "-o", stem.with_suffix(".o"),
         stem.with_suffix(".s")], cwd=directory)
    run(["arm-none-eabi-objcopy", "-O", "binary", "--file-alignment", "4",
         stem.with_suffix(".o"), stem.with_suffix(".bin")])
    digest = hashlib.sha1(stem.with_suffix(".bin").read_bytes()).hexdigest()
    return stem.with_suffix(".bin").name, digest


def build(root, output, jobs=4):
    global ROOT
    ROOT = root.resolve()
    output = output.resolve()
    if output.exists():
        raise ValueError("Output directory must not exist (prevents stale evidence)")
    for tool in ("gcc", "g++", "arm-none-eabi-as", "arm-none-eabi-objcopy"):
        if not shutil.which(tool):
            raise ValueError(f"Required installed tool missing: {tool}")
    sources = sorted((ROOT / SCRIPT_DIR).glob("*.s"))
    expected = {}
    for line in (ROOT / "scr_seq.sha1").read_text().splitlines():
        digest, name = line.split()
        expected[Path(name.lstrip("*")).name] = digest
    if {p.with_suffix(".bin").name for p in sources} != set(expected):
        raise ValueError("Source inventory differs from tracked script hash inventory")
    output.mkdir(parents=True)
    generated = output / "headers"
    generated.mkdir()
    # Build the repository's actual message header generator, not an XML substitute.
    msgenc = output / "msgenc"
    tool_dir = ROOT / "tools/msgenc"
    run(["g++", "-std=c++17", "-O2", "-DNDEBUG", "-o", msgenc, *[
        tool_dir / name for name in (
            "msgenc.cpp", "Options.cpp", "MessagesConverter.cpp",
            "MessagesDecoder.cpp", "MessagesEncoder.cpp", "Gmm.cpp", "pugixml.cpp"
        )
    ]])
    headers = sorted(set(re.findall(
        r'#include "(msgdata/msg/[^"]+\.h)"',
        "\n".join(p.read_text() for p in sources),
    )))
    for name in headers:
        header = generated / name
        header.parent.mkdir(parents=True, exist_ok=True)
        run([msgenc, "-e", "-c", ROOT / "charmap.txt", "--gmm",
             "-H", header, ROOT / "files" / Path(name).with_suffix(".gmm"),
             header.with_suffix(".bin")])
    report = {
        "editions": {}, "tools": {}, "defines": DEFINES,
        "source_commit": run(["git", "rev-parse", "HEAD"]).decode().strip(),
        "tracked_hash_manifest_sha256": hashlib.sha256((ROOT / "scr_seq.sha1").read_bytes()).hexdigest(),
    }
    for tool in ("gcc", "g++", "arm-none-eabi-as", "arm-none-eabi-objcopy"):
        report["tools"][tool] = run([tool, "--version"]).decode().splitlines()[0]
    for edition in ("HEARTGOLD", "SOULSILVER"):
        directory = output / edition.lower()
        directory.mkdir()
        includes = [generated, ROOT / "include", ROOT / "files",
                    ROOT / "asm", ROOT / "lib/include", ROOT]
        macro = directory / "asm/macros/script.inc"
        macro.parent.mkdir(parents=True)
        macro.write_text(preprocess(ROOT / "asm/macros/script.inc", edition, includes))

        with concurrent.futures.ThreadPoolExecutor(max_workers=jobs) as pool:
            hashes = dict(pool.map(
                lambda source: assemble_bank(source, directory, edition, includes), sources
            ))
        mismatches = [name for name in expected if hashes[name] != expected[name]]
        report["editions"][edition] = {
            "edition_define": edition,
            "bank_count": len(hashes), "sha1_matches": len(hashes) - len(mismatches),
            "mismatches": mismatches, "hashes": hashes,
        }
    (output / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    if any(e["mismatches"] for e in report["editions"].values()):
        raise ValueError(f"Script hash mismatch; see {output / 'report.json'}")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--jobs", type=int, default=4)
    args = parser.parse_args()
    if args.jobs < 1:
        parser.error("--jobs must be positive")
    try:
        result = build(ROOT, args.output, args.jobs)
    except subprocess.CalledProcessError as error:
        parser.exit(1, f"Command failed: {error.cmd}\n{error.stderr.decode()}")
    except ValueError as error:
        parser.exit(1, f"{error}\n")
    for edition, data in result["editions"].items():
        print(f"{edition}: {data['sha1_matches']}/{data['bank_count']} tracked SHA-1 matches")


if __name__ == "__main__":
    main()