"""Run the production GNU pipeline on real banks and edition-sensitive input."""
import importlib.util
from pathlib import Path
import shutil
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "native_scripts", ROOT / "scripts/build_native_field_scripts.py"
)
native = importlib.util.module_from_spec(spec)
spec.loader.exec_module(native)


class NativeScriptTests(unittest.TestCase):
    @unittest.skipUnless(
        all(shutil.which(tool) for tool in ("gcc", "arm-none-eabi-as", "arm-none-eabi-objcopy")),
        "Native ARM script regression requires gcc and binutils-arm-none-eabi",
    )
    def test_real_header_banks_match_both_editions(self):
        expected = {
            Path(name.lstrip("*")).name: digest
            for digest, name in (line.split() for line in (ROOT / "scr_seq.sha1").read_text().splitlines())
        }
        includes = [ROOT / "include", ROOT / "files", ROOT / "asm", ROOT / "lib/include", ROOT]
        with tempfile.TemporaryDirectory() as temp:
            for edition in ("HEARTGOLD", "SOULSILVER"):
                directory = Path(temp) / edition
                macro = directory / "asm/macros/script.inc"
                macro.parent.mkdir(parents=True)
                macro.write_text(native.preprocess(ROOT / "asm/macros/script.inc", edition, includes))
                for name in ("scr_seq_0266_D01R0101_hdr", "scr_seq_0286_D22R0101_hdr"):
                    bank, digest = native.assemble_bank(
                        ROOT / native.SCRIPT_DIR / (name + ".s"), directory, edition, includes
                    )
                    self.assertEqual(expected[bank], digest)
                # Ensure independent edition preprocessing, even though retail
                # field banks currently have identical tracked output.
                source = Path(temp) / "edition.s"
                source.write_text(
                    ".rodata\n#ifdef HEARTGOLD\n.byte 1\n"
                    "#elif defined(SOULSILVER)\n.byte 2\n#else\n#error missing edition\n#endif\n"
                )
                native.assemble_bank(source, directory, edition, includes)
                self.assertEqual(bytes([1 if edition == "HEARTGOLD" else 2]),
                                 (directory / "edition.bin").read_bytes())

    def test_refuse_stale_output_and_unsupported_strings(self):
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaisesRegex(ValueError, "must not exist"):
                native.build(ROOT, Path(temp))
        with self.assertRaisesRegex(ValueError, "String directive"):
            native.gas_syntax('.ascii "not;a;comment"\n')