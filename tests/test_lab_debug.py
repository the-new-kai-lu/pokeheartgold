import os
import json
import re
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
            self.assertEqual(report["rescue_mode"], "simulated")
            self.assertTrue(report["eligibility_injected"])
            self.assertFalse(report["requires_real_rescue_battle"])
            self.assertIsNone(report["rescue_actor"])
            self.assertEqual(json.loads((debug / "lab-debug.json").read_text())["rescue_mode"],
                             "simulated")
            production = (debug / "files/fielddata/script/scr_seq/"
                          "scr_seq_0965_hoenn_reward.s").read_text()
            definitions = re.findall(r"^\s*ScrDef\s+(\w+)\s*$",
                                     production.split("ScrDefEnd", 1)[0], re.M)
            self.assertEqual(definitions[-1], "HoennDebug_Return")
            self.assertEqual(report["return_entry"], len(definitions) - 1)
            # The production rescue added after the claim/menu must remain
            # distinct from the appended debug return.
            self.assertGreaterEqual(report["return_entry"], 3)
            self.assertEqual(report["reward_entry"], 1)
            self.assertEqual(report["map"], 540)
            self.assertEqual((ROOT / "include/constants/maps.h").read_bytes(), stock_maps)
            self.assertIn("#define MAP_ID_MAX 541",
                          (debug / "include/constants/maps.h").read_text())
            self.assertIn("[MAP_HOENN_LAB_DEBUG]",
                          (debug / "src/data/map_headers.h").read_text())
            self.assertIn("SetVar 0x416e, 1\nWarp 540, 0, 16, 19, 0\nEnd",
                          (debug / "files/fielddata/script/scr_seq/"
                           "scr_seq_0843_T20R0101.s").read_text())
            self.assertIn(r"DEBUG LAB: Simulated rescue.\nTest a Hoenn starter reward.",
                          (debug / "files/msgdata/msg/msg_0829_hoenn_reward.gmm").read_text())
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
                                      (index, (report["reward_entry"] if index == 0
                                               else report["return_entry"]) + 1, x, 17))
                    self.assertFalse(struct.unpack_from("<H", terrain,
                                                       2 * (17 * 32 + x))[0] & 0x8000)
                source = debug / "files/fielddata/script/scr_seq/scr_seq_0965_hoenn_reward.s"
                name, _ = native.assemble_bank(source, output, edition, includes)
                bank = (output / name).read_bytes()
                table_offset = 4 * report["return_entry"]
                pc = table_offset + 4 + struct.unpack_from("<I", bank, table_offset)[0]
                rescue_pc = 12 + struct.unpack_from("<I", bank, 8)[0]
                self.assertNotEqual(rescue_pc, pc)
                self.assertNotEqual(struct.unpack_from("<H", bank, rescue_pc)[0], 176)
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

    def test_native_rescue_mode_preserves_earned_state_and_production_entries(self):
        donor = Path(os.environ.get("EMERALD_DONOR", ROOT.parent / "pokeemerald"))
        if not donor.exists():
            self.skipTest("Pinned donor required")
        production_script = ROOT / "files/fielddata/script/scr_seq/scr_seq_0965_hoenn_reward.s"
        production_bytes = production_script.read_bytes()
        elm_source = ROOT / "files/fielddata/script/scr_seq/scr_seq_0843_T20R0101.s"
        elm_bytes = elm_source.read_bytes()
        with tempfile.TemporaryDirectory() as directory:
            temp = Path(directory)
            extract(donor, temp / "pack")
            export(temp / "pack", temp / "assets")
            debug = temp / "native"
            report = prepare(ROOT, temp / "assets", debug, rescue_mode="native")
            self.assertEqual(report["rescue_mode"], "native")
            self.assertFalse(report["eligibility_injected"])
            self.assertTrue(report["requires_real_rescue_battle"])
            self.assertEqual(report["rescue_actor"], [16, 17])
            self.assertEqual(report["return_entry"], 3)
            self.assertEqual(json.loads((debug / "lab-debug.json").read_text()), report)
            self.assertEqual(production_script.read_bytes(), production_bytes)
            self.assertEqual(elm_source.read_bytes(), elm_bytes)
            entry_source = (debug / "files/fielddata/script/scr_seq/"
                            "scr_seq_0843_T20R0101.s").read_text()
            block = entry_source.split("scr_seq_T20R0101_000:", 1)[1].split(
                "HoennDebug_ElmOriginal:", 1)[0]
            self.assertIn("GoToIfUnset FLAG_GOT_STARTER, HoennDebug_ElmOriginal", block)
            self.assertIn("Warp 540, 0, 16, 19, 0\nEnd", block)
            self.assertNotIn("SetVar 0x416e", block)
            self.assertNotIn("SetVar VAR_HOENN_RESCUE_STATE", block)
            message = (debug / "files/msgdata/msg/msg_0829_hoenn_reward.gmm").read_text()
            self.assertIn(r"DEBUG LAB: Rescue completed.\nChoose a Hoenn partner.", message)
            self.assertNotIn("Simulated rescue", message)
            encoder = temp / "msgenc"
            tools = ROOT / "tools/msgenc"
            subprocess.run(["g++", "-std=c++17", "-O2", "-DNDEBUG", "-o", str(encoder),
                            *[str(tools / name) for name in (
                                "msgenc.cpp", "Options.cpp", "MessagesConverter.cpp",
                                "MessagesDecoder.cpp", "MessagesEncoder.cpp",
                                "Gmm.cpp", "pugixml.cpp")]], check=True, capture_output=True)
            encoded = temp / "native-lab-messages.bin"
            subprocess.run([str(encoder), "-e", "-c", str(ROOT / "charmap.txt"),
                            "--gmm", "-k", "0xB461",
                            str(debug / "files/msgdata/msg/msg_0829_hoenn_reward.gmm"),
                            str(encoded)], check=True, capture_output=True)
            self.assertEqual(struct.unpack_from("<H", encoded.read_bytes())[0], 17)
            generated = (debug / "files/fielddata/script/scr_seq/"
                         "scr_seq_0965_hoenn_reward.s").read_text()
            entries = re.findall(r"^\s*ScrDef\s+(\w+)\s*$",
                                 generated.split("ScrDefEnd", 1)[0], re.M)
            self.assertEqual(entries, ["HoennReward_Claim", "HoennReward_Interaction",
                                       "HoennRescue_Interaction", "HoennDebug_Return"])
            events = debug / "files/fielddata/eventdata/zone_event"
            actors = json.loads((events / "491_HOENN_LAB_DEBUG.json").read_text())["objects"]
            self.assertEqual([(a["id"], a["x"], a["z"], a["scriptId"]) for a in actors],
                             [(0, 14, 17, 2), (1, 18, 17, 4), (2, 16, 17, 3)])
            terrain = Land.decode(narc_members(
                (debug / "files/a/0/6/5").read_bytes())[676]).terrain
            for actor in actors:
                self.assertFalse(struct.unpack_from(
                    "<H", terrain, 2 * (actor["z"] * 32 + actor["x"]))[0] & 0x8000)
            self.assertFalse(struct.unpack_from("<H", terrain,
                                                2 * (19 * 32 + 16))[0] & 0x8000)
            subprocess.run([sys.executable, str(ROOT / "scripts/check_expansion_baseline.py"),
                            "--root", str(debug)], check=True, capture_output=True)
            jsonproc = temp / "jsonproc"
            subprocess.run(["g++", "-std=c++11", "-O0", "-I", str(ROOT / "tools/jsonproc"),
                            str(ROOT / "tools/jsonproc/jsonproc.cpp"), "-o", str(jsonproc)],
                           check=True, capture_output=True)
            event = temp / "native-event.s"
            subprocess.run([str(jsonproc), str(events / "491_HOENN_LAB_DEBUG.json"),
                            str(debug / "files/fielddata/eventdata/zone_event.json.txt"),
                            str(event)], check=True, capture_output=True)
            for edition in ("HEARTGOLD", "SOULSILVER"):
                output = temp / edition
                output.mkdir()
                includes = [debug / path for path in ("include", "files", "asm",
                                                      "lib/include", ".")]
                macro = output / "asm/macros/script.inc"
                macro.parent.mkdir(parents=True)
                macro.write_text(native.preprocess(debug / "asm/macros/script.inc",
                                                   edition, includes))
                entry = temp / "native-entrance.s"
                entry.write_text('#include "constants/scrcmd.h"\n'
                                 '.include "asm/macros/script.inc"\n.rodata\n'
                                 + block + "\nHoennDebug_ElmOriginal:\nEnd\n")
                native.assemble_bank(entry, output, edition, includes)
                entrance = (output / "native-entrance.bin").read_bytes()
                self.assertIn(struct.pack("<6H", 176, 540, 0, 16, 19, 0), entrance)
                self.assertNotIn(struct.pack("<HH", 41, 0x416e), entrance)
                native.assemble_bank(event, output, edition, includes)
                data = (output / "native-event.bin").read_bytes()
                self.assertEqual(struct.unpack_from("<II", data), (0, 3))
                self.assertEqual(len(data), 112)
                for index, actor in enumerate(actors):
                    obj = struct.unpack_from("<14Hi", data, 8 + index * 32)
                    self.assertEqual((obj[0], obj[5], obj[12], obj[13]),
                                     (actor["id"], actor["scriptId"], actor["x"], actor["z"]))
                name, _ = native.assemble_bank(production_script, output, edition, includes)
                original = (output / name).read_bytes()
                name, _ = native.assemble_bank(
                    debug / "files/fielddata/script/scr_seq/scr_seq_0965_hoenn_reward.s",
                    output, edition, includes)
                generated_bank = (output / name).read_bytes()
                original_first = 4 + struct.unpack_from("<I", original)[0]
                debug_first = 4 + struct.unpack_from("<I", generated_bank)[0]
                self.assertEqual(original[original_first:],
                                 generated_bank[debug_first:debug_first +
                                                len(original) - original_first])
                rescue_pc = 12 + struct.unpack_from("<I", generated_bank, 8)[0]
                return_pc = 16 + struct.unpack_from("<I", generated_bank, 12)[0]
                self.assertNotEqual(rescue_pc, return_pc)
                self.assertIn(struct.pack("<3HB", 589, 263, 2, 0),
                              generated_bank[rescue_pc:return_pc])
                self.assertEqual(struct.unpack_from("<6H", generated_bank, return_pc),
                                 (176, 61, 0, 6, 12, 1))
            with self.assertRaises(ValueError):
                prepare(ROOT, temp / "assets", temp / "invalid", rescue_mode="unknown")