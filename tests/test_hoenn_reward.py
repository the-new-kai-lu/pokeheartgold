"""Execute compiled claim-bank branches; storage itself has separate C tests."""
import hashlib
from pathlib import Path
import shutil
import struct
import tempfile
import unittest

from test_native_field_scripts import native, ROOT


def execute(data, variables, delivery):
    """Bounded interpreter for the exact production opcodes in this bank."""
    pc = 4 + struct.unpack_from("<I", data)[0]
    comparison = 0
    calls = []
    def value(v):
        return variables.get(v, 0) if v >= 0x4000 else v
    for _ in range(100):
        opcode = struct.unpack_from("<H", data, pc)[0]
        pc += 2
        if opcode == 2:
            return variables[0x800c], calls
        if opcode in (17, 18, 41, 42):
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