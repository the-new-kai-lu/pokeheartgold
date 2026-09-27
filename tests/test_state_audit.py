"""Fail-closed inventory tests using assembled bytecode and source fixtures."""
import importlib.util
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "audit_expansion_state", ROOT / "scripts/audit_expansion_state.py")
AUDIT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(AUDIT)


class StateAuditTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.paths = []
        self.write("include/constants/vars.h",
                   "#define VAR_UNK_416E 0x416E\n#define ALIAS VAR_UNK_416E\n")
        self.write("files/fielddata/script/scr_seq/scr_seq_0000.s", "End\n")
        self.hg = self.root / "hg"
        self.ss = self.root / "ss"
        self.hg.mkdir()
        self.ss.mkdir()

    def write(self, name, text):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
        self.paths.append(name)

    def report(self):
        return AUDIT.audit(self.root, [0x416E], self.hg, self.ss, self.paths)

    def test_missing_and_empty_banks_never_approve(self):
        result = self.report()
        self.assertFalse(result["compiled_coverage_complete"])
        self.assertFalse(result["allocation_approved"])
        (self.hg / "scr_seq_0000.bin").write_bytes(b"")
        (self.ss / "scr_seq_0000.bin").write_bytes(b"\x02\0")
        result = self.report()
        self.assertEqual(["scr_seq_0000.bin"], result["builds"]["heartgold"]["empty"])
        self.assertFalse(result["compiled_coverage_complete"])

    def test_compiled_unaligned_literal_in_either_game_is_reported(self):
        self.assertIsNotNone(shutil.which("as"), "host assembler required")
        self.assertIsNotNone(shutil.which("objcopy"), "host objcopy required")
        # An actual little-endian script operand, including an odd byte offset.
        source = self.root / "bank.s"
        source.write_text(".byte 0\n.short 0x416e\n.short 2\n")
        subprocess.run(["as", "-o", str(self.root / "bank.o"), str(source)], check=True)
        subprocess.run(["objcopy", "-O", "binary", "-j", ".text",
                        str(self.root / "bank.o"), str(self.ss / "scr_seq_0000.bin")], check=True)
        (self.hg / "scr_seq_0000.bin").write_bytes(b"\x02\0")
        result = self.report()
        self.assertTrue(result["compiled_coverage_complete"])
        candidate = result["candidates"]["0x416E"]
        self.assertTrue(candidate["literal_reference_found"])
        self.assertEqual([1], candidate["binary_hits"]["soulsilver"][0]["offsets"])
        self.assertFalse(candidate["binary_hits"]["heartgold"])
        self.assertFalse(result["allocation_approved"])

    def test_unexpected_bank_prevents_coverage_claim(self):
        for directory in (self.hg, self.ss):
            (directory / "scr_seq_0000.bin").write_bytes(b"\x02\0")
        (self.hg / "stale.bin").write_bytes(b"\x02\0")
        result = self.report()
        self.assertFalse(result["compiled_coverage_complete"])
        self.assertEqual(["stale.bin"], result["builds"]["heartgold"]["unexpected"])

    def test_alias_decimal_and_both_branches_reported(self):
        self.write("src/access.c",
                   "#ifdef HEARTGOLD\nuse(ALIAS);\n#else\nuse(16750U);\n#endif\n")
        result = self.report()
        hits = result["candidates"]["0x416E"]["source_hits"]
        self.assertEqual([2, 4], [hit["line"] for hit in hits])
        self.assertEqual(["ALIAS", "VAR_UNK_416E"],
                         result["candidates"]["0x416E"]["aliases"])

    def test_computed_access_remains_explicit_review_blocker(self):
        self.write("src/dynamic.c", "FieldSystem_VarGet(fs, base + index);\n")
        for directory in (self.hg, self.ss):
            (directory / "scr_seq_0000.bin").write_bytes(b"\x02\0")
        result = self.report()
        self.assertTrue(result["compiled_coverage_complete"])
        self.assertFalse(result["candidates"]["0x416E"]["literal_reference_found"])
        self.assertEqual("src/dynamic.c", result["access_sites_requiring_review"][0]["path"])
        self.assertFalse(result["allocation_approved"])

    def test_input_changes_are_fingerprinted(self):
        first = self.report()
        (self.root / "include/constants/vars.h").write_text("#define VAR_UNK_416E 0x416E\n")
        self.assertNotEqual(first["source_sha256"], self.report()["source_sha256"])
        (self.hg / "scr_seq_0000.bin").write_bytes(b"\x02\0")
        first_hash = self.report()["builds"]["heartgold"]["sha256"]["scr_seq_0000.bin"]
        (self.hg / "scr_seq_0000.bin").write_bytes(b"\x02\0\0")
        self.assertNotEqual(first_hash, self.report()["builds"]["heartgold"]["sha256"]["scr_seq_0000.bin"])


if __name__ == "__main__":
    unittest.main()