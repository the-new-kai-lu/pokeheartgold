import os
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest

from test_native_field_scripts import native, ROOT
from test_hoenn_reward import execute
sys.path.insert(0, str(ROOT / "scripts"))
from extract_emerald_lab import extract
from export_lab_model import export
from prepare_lab_debug import prepare
from hgss_land import Land, narc_members


@unittest.skipUnless(all(shutil.which(t) for t in
                        ("git", "tar", "g++", "gcc", "arm-none-eabi-as",
                         "arm-none-eabi-objcopy")), "native build tools required")
class LabDebugTests(unittest.TestCase):
    def test_generated_build_hooks_and_real_compiled_events(self):
        donor = Path(os.environ.get("EMERALD_DONOR", ROOT.parent / "pokeemerald"))
        if not donor.exists():
            self.skipTest("Pinned donor required")
        stock_maps = (ROOT / "include/constants/maps.h").read_bytes()
        with tempfile.TemporaryDirectory() as temp:
            temp = Path(temp)
            extract(donor, temp / "pack")
            export(temp / "pack", temp / "assets")
            debug = temp / "debug"
            report = prepare(ROOT, temp / "assets", debug)
            self.assertEqual(report["map"], 540)
            self.assertEqual((ROOT / "include/constants/maps.h").read_bytes(), stock_maps)
            self.assertIn("#define MAP_ID_MAX 541",
                          (debug / "include/constants/maps.h").read_text())
            self.assertIn("[MAP_HOENN_LAB_DEBUG]",
                          (debug / "src/data/map_headers.h").read_text())
            self.assertIn("SetVar 0x416e, 1\nWarp 540, 0, 16, 19, 0\nEnd",
                          (debug / "files/fielddata/script/scr_seq/"
                           "scr_seq_0843_T20R0101.s").read_text())
            subprocess.run([sys.executable, str(ROOT / "scripts/check_expansion_baseline.py"),
                            "--root", str(debug)], check=True, capture_output=True)
            # Native template renderer: tests use the SAME JSON format and
            # template as ROM builds, not a parallel event serializer.
            jsonproc = temp / "jsonproc"
            subprocess.run(["g++", "-std=c++11", "-O0", "-I", str(ROOT / "tools/jsonproc"),
                            str(ROOT / "tools/jsonproc/jsonproc.cpp"), "-o",
                            str(jsonproc)], check=True, capture_output=True)
            event = temp / "event.s"
            subprocess.run([str(jsonproc),
                            str(debug / "files/fielddata/eventdata/zone_event/"
                                "491_HOENN_LAB_DEBUG.json"),
                            str(debug / "files/fielddata/eventdata/zone_event.json.txt"),
                            str(event)], check=True, capture_output=True)
            terrain = Land.decode(narc_members(
                (debug / "files/a/0/6/5").read_bytes())[676]).terrain
            for edition in ("HEARTGOLD", "SOULSILVER"):
                output = temp / edition
                output.mkdir()
                includes = [debug / p for p in ("include", "files", "asm",
                                                "lib/include", ".")]
                macro = output / "asm/macros/script.inc"
                macro.parent.mkdir(parents=True)
                macro.write_text(native.preprocess(debug / "asm/macros/script.inc",
                                                   edition, includes))
                # Compile the actual inserted entrance block, including its
                # pre-starter fallback branch, without unrelated Elm dialogue.
                elm = (debug / "files/fielddata/script/scr_seq/"
                       "scr_seq_0843_T20R0101.s").read_text()
                block = elm.split("scr_seq_T20R0101_000:", 1)[1].split(
                    "HoennDebug_ElmOriginal:", 1)[0]
                entry = temp / "entrance.s"
                entry.write_text('#include "constants/scrcmd.h"\n'
                                 '.include "asm/macros/script.inc"\n.rodata\n'
                                 + block + "\nHoennDebug_ElmOriginal:\nEnd\n")
                native.assemble_bank(entry, output, edition, includes)
                self.assertIn(struct.pack("<6H", 176, 540, 0, 16, 19, 0),
                              (output / "entrance.bin").read_bytes())
                native.assemble_bank(event, output, edition, includes)
                data = (output / "event.bin").read_bytes()
                self.assertEqual(struct.unpack_from("<II", data), (0, 2))
                self.assertEqual(len(data), 80)  # counts16 + two ObjectEvents32
                for index, x in ((0, 14), (1, 18)):
                    obj = struct.unpack_from("<14Hi", data, 8 + index * 32)
                    self.assertEqual((obj[0], obj[5], obj[12], obj[13]),
                                     (index, index + 2, x, 17))
                    self.assertFalse(struct.unpack_from("<H", terrain,
                                                       2 * (17 * 32 + x))[0] & 0x8000)
                source = debug / "files/fielddata/script/scr_seq/scr_seq_0965_hoenn_reward.s"
                name, _ = native.assemble_bank(source, output, edition, includes)
                bank = (output / name).read_bytes()
                pc = 12 + struct.unpack_from("<I", bank, 8)[0]
                # Return entry is real assembled Warp + End, and
                # returns to safe Elm-lab coordinates rather than map zero.
                self.assertEqual(struct.unpack_from("<6H", bank, pc),
                                 (176, 61, 0, 6, 12, 1))
                state = {0x416e: 1, 0x416f: 0}
                execute(bank, state, 2, entry=1, choice=252)
                self.assertEqual(state[0x416f], 252)
            self.assertFalse(struct.unpack_from("<H", terrain,
                                               2 * (19 * 32 + 16))[0] & 0x8000)
            with self.assertRaises(ValueError):
                prepare(ROOT, temp / "assets", debug)