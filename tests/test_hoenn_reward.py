"""Execute compiled claim-bank branches; storage itself has separate C tests."""
import hashlib
from pathlib import Path
import shutil
import struct
import subprocess
import tempfile
import unittest

from test_native_field_scripts import native, ROOT


def execute(data, variables, delivery, entry=0, choice=0, messages=None,
            battle_result=1, battles=None):
    """Bounded interpreter for the exact production opcodes in this bank."""
    pc = 4 * entry + 4 + struct.unpack_from("<I", data, 4 * entry)[0]
    stack = []
    menu_items = []
    menu_var = None
    comparison = 0
    calls = []
    def value(v):
        return variables.get(v, 0) if v >= 0x4000 else v
    for _ in range(100):
        opcode = struct.unpack_from("<H", data, pc)[0]
        pc += 2
        if opcode == 2:
            return variables.get(0x800c), calls
        if opcode in (22, 26):
            relative = struct.unpack_from("<i", data, pc)[0]
            pc += 4
            if opcode == 26:
                stack.append(pc)
            pc += relative
        elif opcode == 27:
            pc = stack.pop()
        elif opcode in (45,):
            if messages is not None:
                messages.append(data[pc])
            pc += 1
        elif opcode in (49, 53, 96, 97, 104):
            pass
        elif opcode == 750:
            menu_var = struct.unpack_from("<H", data, pc + 4)[0]
            pc += 6
        elif opcode == 751:
            message, unused, result = struct.unpack_from("<HHH", data, pc)
            menu_items.append(result)
            pc += 6
        elif opcode == 752:
            assert menu_items in ([252, 255, 258, 0], [1, 0])
            variables[menu_var] = choice
        elif opcode == 589:
            species, level, shiny = struct.unpack_from("<HHB", data, pc)
            pc += 5
            if battles is not None:
                battles.append((species, level, shiny, variables[0x416e]))
        elif opcode == 683:
            dest = struct.unpack_from("<H", data, pc)[0]
            pc += 2
            variables[dest] = battle_result
        elif opcode == 219:
            assert variables[0x416e] == 0
            if battles is not None:
                battles.append("blackout")
        elif opcode in (17, 18, 41, 42):
            a, b = struct.unpack_from("<HH", data, pc)
            pc += 4
            if opcode in (17, 18):
                rhs = b if opcode == 17 else variables.get(b, 0)
                comparison = (variables.get(a, 0) > rhs) - (variables.get(a, 0) < rhs)
            else:
                variables[a] = b if opcode == 41 else variables.get(b, 0)
        elif opcode == 28:
            condition, relative = struct.unpack_from("<Bi", data, pc)
            pc += 5
            if condition not in (1, 5):
                raise AssertionError("unreviewed branch condition")
            if (condition == 1 and comparison == 0) or (condition == 5 and comparison != 0):
                pc += relative
        elif opcode == 853:
            args = struct.unpack_from("<6H", data, pc)
            pc += 12
            calls.append(tuple(value(v) for v in args[:5]))
            variables[args[5]] = delivery
        else:
            raise AssertionError(f"unreviewed opcode {opcode}")
    raise AssertionError("script did not terminate")


class HoennRewardTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which("g++"), "native message encoder needs g++")
    def test_lab_messages_encode_and_append_without_reindexing(self):
        banks = sorted((ROOT / "files/msgdata/msg").glob("*.gmm"))
        # Bank 729 is generated from trainer data by msg.mk, not tracked.
        names = sorted({p.name for p in banks} | {"msg_0729.gmm"})
        self.assertEqual(len(names), 830)
        self.assertEqual(names[829], "msg_0829_hoenn_reward.gmm")
        with tempfile.TemporaryDirectory() as temp:
            encoder = Path(temp) / "msgenc"
            tools = ROOT / "tools/msgenc"
            subprocess.run(["g++", "-std=c++17", "-O2", "-DNDEBUG", "-o", str(encoder),
                            *[str(tools / name) for name in (
                                "msgenc.cpp", "Options.cpp", "MessagesConverter.cpp",
                                "MessagesDecoder.cpp", "MessagesEncoder.cpp",
                                "Gmm.cpp", "pugixml.cpp")]], check=True)
            output = Path(temp) / "lab.bin"
            subprocess.run([str(encoder), "-e", "-c", str(ROOT / "charmap.txt"),
                            "--gmm", "-k", "0xB461", str(banks[-1]),
                            str(output)], check=True)
            self.assertEqual(struct.unpack_from("<H", output.read_bytes())[0], 17)

    def test_frontier_archive_cannot_name_reserved_variables(self):
        # Loader: frontier_system.s ov80_0222AA40 loads NARC ID 0xb6.
        # filesystem_files_def.h maps it to a/1/8/2, shared by both editions.
        raw = (ROOT / "files/a/1/8/2").read_bytes()
        digest = hashlib.sha1(raw).hexdigest()
        for edition in ("heartgold", "soulsilver"):
            self.assertIn(digest + " *files/a/1/8/2",
                          (ROOT / f"{edition}.us/filesystem.sha1").read_text())
        self.assertEqual(b"NARC", raw[:4])
        chunks = {}
        offset = 16
        while offset < len(raw):
            tag, length = struct.unpack_from("<4sI", raw, offset)
            self.assertGreaterEqual(length, 8)
            chunks[tag] = offset
            offset += length
        self.assertEqual(offset, len(raw))
        fat, img = chunks[b"BTAF"], chunks[b"GMIF"] + 8
        count = struct.unpack_from("<H", raw, fat + 8)[0]
        self.assertEqual(11, count)
        for i in range(count):
            start, end = struct.unpack_from("<II", raw, fat + 12 + 8 * i)
            self.assertLessEqual(img + end, len(raw))
            member = raw[img + start:img + end]
            for candidate in (0x416e, 0x416f):
                self.assertNotIn(struct.pack("<H", candidate), member)

    @unittest.skipUnless(all(shutil.which(t) for t in
                            ("gcc", "arm-none-eabi-as", "arm-none-eabi-objcopy")),
                         "native ARM binutils required")
    def test_compiled_reward_guard_retry_and_receipt(self):
        with tempfile.TemporaryDirectory() as tmp:
            for edition in ("HEARTGOLD", "SOULSILVER"):
                directory = Path(tmp) / edition
                directory.mkdir()
                includes = [ROOT / "include", ROOT / "files", ROOT / "asm",
                            ROOT / "lib/include", ROOT]
                macro = directory / "asm/macros/script.inc"
                macro.parent.mkdir(parents=True)
                macro.write_text(native.preprocess(ROOT / "asm/macros/script.inc",
                                                   edition, includes))
                bank, digest = native.assemble_bank(
                    ROOT / native.SCRIPT_DIR / "scr_seq_0965_hoenn_reward.s",
                    directory, edition, includes)
                self.assertIn(digest, (ROOT / "scr_seq.sha1").read_text())
                data = (directory / bank).read_bytes()
                for initial in (0, 2):
                    for outcome in range(8):
                        state = {0x416e: initial, 0x416f: 0, 0x4050: 123}
                        battles = []
                        _, gifts = execute(data, state, 1, entry=2, choice=1,
                                           battle_result=outcome, battles=battles)
                        self.assertEqual(battles[0], (263, 2, 0, 2))
                        self.assertEqual("blackout" in battles, outcome in (2, 3))
                        self.assertEqual(state[0x416e], int(outcome in (1, 4)))
                        self.assertEqual(state[0x416f], 0)
                        self.assertEqual(state[0x4050], 123)
                        self.assertEqual(gifts, [])
                for initial, choice in ((0, 0), (2, 65534), (1, 1)):
                    state = {0x416e: initial, 0x416f: 258}
                    battles = []
                    execute(data, state, 1, entry=2, choice=choice, battles=battles)
                    self.assertEqual(battles, [])
                    self.assertEqual(state[0x416e], int(initial == 1))
                    self.assertEqual(state[0x416f], 258)
                for rescue, receipt, choice, delivery, message in (
                    (0, 0, 252, 1, 9), (2, 0, 252, 1, 9),
                    (1, 252, 255, 1, 10), (1, 999, 252, 1, 10),
                    (1, 0, 0, 1, 8), (1, 0, 65534, 1, 8),
                    (1, 0, 252, 0, 7), (1, 0, 255, 1, 5),
                    (1, 0, 258, 2, 6),
                ):
                    state = {0x416e: rescue, 0x416f: receipt}
                    messages = []
                    execute(data, state, delivery, entry=1, choice=choice,
                            messages=messages)
                    self.assertEqual(messages[-1], message)
                    self.assertEqual(state[0x416f],
                                     choice if message in (5, 6) else receipt)
                for species in (252, 255, 258):
                    for outcome in (0, 1, 2):
                        state = {0x416e: 1, 0x416f: 0, 0x8000: species}
                        result, calls = execute(data, state, outcome)
                        self.assertEqual(result, outcome)
                        self.assertEqual(calls, [(species, 5, 0, 0, 0)])
                        self.assertEqual(state[0x416f], species if outcome else 0)
                        # Reload-equivalent copy: no transient Python state retained.
                        state = dict(state)
                        result, calls = execute(data, state, 2)
                        self.assertEqual(result, 4 if outcome else 2)
                        self.assertEqual(len(calls), 0 if outcome else 1)
                for rescue, receipt, choice, expected in (
                    (0, 0, 252, 3), (2, 0, 252, 3), (1, 252, 255, 4),
                    (1, 0, 0, 5), (1, 0, 1, 5), (1, 0, 65535, 5),
                ):
                    state = {0x416e: rescue, 0x416f: receipt, 0x8000: choice}
                    result, calls = execute(data, state, 1)
                    self.assertEqual((result, calls), (expected, []))
                    self.assertEqual(state[0x416f], receipt)