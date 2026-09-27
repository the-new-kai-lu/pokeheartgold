#!/usr/bin/env python3
"""Exercise compiled item-event control flow and verify the actual ROM payloads.
Rendering, movement and standard inventory UI are additionally emulator-tested.
"""
import argparse
import itertools
import struct
from pathlib import Path
from collections import Counter
from ndspy.rom import NintendoDSRom
from ndspy.narc import NARC
from test_starter_trio_gift import ElmScript

ROOT = Path(__file__).resolve().parents[2]

class ItemScript(ElmScript):
    def __init__(self, data, entry, full=False, gender=0, y=6, following=0, flags=(), progress=0):
        super().__init__(data, entry, flags=flags)
        self.full, self.gender, self.y, self.following = full, gender, y, following
        self.vars[0x4132] = progress
        self.items = Counter()
        self.hidden = []

    def run(self):
        for _ in range(1000):
            op = self.read()
            if op == 2:
                assert not self.stack
                return self
            if op in (22, 26):
                delta = self.read("i")
                if op == 26:
                    self.stack.append(self.pc)
                self.pc += delta
            elif op == 27:
                self.pc = self.stack.pop()
            elif op in (28, 29):
                cond, delta = self.read("B"), self.read("i")
                if self.condition(cond):
                    if op == 29:
                        self.stack.append(self.pc)
                    self.pc += delta
            elif op == 17:
                a, b = self.read(), self.read()
                self.cmp = self.var(a) - b
            elif op in (30, 32):
                flag = self.read()
                if op == 30:
                    self.flags.add(flag)
                else:
                    self.cmp = 0 if flag in self.flags else -1
            elif op == 41:
                key, value = self.read(), self.read()
                self.vars[key] = value
            elif op == 20:
                standard = self.read()
                if standard in (2008, 2033):
                    item, qty = self.vars[0x8004], self.vars[0x8005]
                    assert item == 465 or not self.full, "Gift attempted with a full Bag"
                    self.items[item] += qty
            elif op == 127:
                item, qty, target = self.read(), self.read(), self.read()
                self.vars[target] = int(not self.full)
            elif op == 105:
                x, y = self.read(), self.read()
                self.vars[x], self.vars[y] = 5, self.y
            elif op == 729:
                self.vars[self.read()] = self.following
            elif op == 101:
                self.hidden.append(self.read())
            elif op == 132:
                male, female = self.read("B"), self.read("B")
                self.messages.append(female if self.gender else male)
            elif op == 45:
                self.messages.append(self.read("B"))
            elif op == 97:
                self.unlocked = True
            else:
                sizes = {3:4, 50:0, 53:0, 73:2, 75:2, 78:2, 79:0, 94:6, 95:0,
                         96:0, 104:0, 190:1, 339:10, 609:0}
                assert op in sizes, f"Unsupported opcode {op} at {self.pc-2:#x}"
                self.pc += sizes[op]
        raise AssertionError("Script did not terminate")


def test(rom_path):
    rom = NintendoDSRom.fromFile(str(rom_path))
    scripts = NARC(rom.getFileByName("a/0/1/2")).files
    events = NARC(rom.getFileByName("a/0/3/2")).files
    for index, stem in ((231, "scr_seq_0231_R31R0101"), (259, "scr_seq_0259_R46")):
        assert scripts[index] == (ROOT / "files/fielddata/script/scr_seq" / (stem + ".bin")).read_bytes()
    assert events[45] == (ROOT / "files/fielddata/eventdata/zone_event/045_R46.bin").read_bytes()
    assert NARC(rom.getFileByName("a/0/2/7")).files[379] == (ROOT / "files/msgdata/msg/msg_0379_R31R0101.bin").read_bytes()
    assert rom.getFileByName("a/0/6/5") == (ROOT / "files/a/0/6/5").read_bytes()
    cases = 0
    for full in (False, True):
        pickup = ItemScript(scripts[259], 3, full=full).run()
        assert pickup.unlocked
        assert pickup.items[302] == (0 if full else 1)
        assert (0x8FE in pickup.flags) == (not full)
        assert pickup.hidden == ([] if full else [7])
        retry = ItemScript(scripts[259], 3, flags=pickup.flags).run()
        assert retry.items[302] == (1 if full else 0)
        cases += 2
    for full, gender, y, following in itertools.product((False, True), (0, 1), (6, 7, 8), (0, 1)):
        gift = ItemScript(scripts[231], 0, full=full, gender=gender, y=y, following=following).run()
        assert gift.items[465] == 1
        assert gift.items[246] == (0 if full else 1)
        assert (0x8FF in gift.flags) == (not full)
        assert gift.vars[0x4132] == 1 and gift.unlocked
        assert (3 if gender else 2) in gift.messages
        claim = ItemScript(scripts[231], 2, flags=gift.flags, progress=1).run()
        assert claim.items[246] == (1 if full else 0)
        again = ItemScript(scripts[231], 2, flags=claim.flags, progress=1).run()
        assert not again.items
        cases += 3
    for progress in (0, 1):
        old = ItemScript(scripts[231], 2, progress=progress).run()
        assert old.items[246] == progress
        full = ItemScript(scripts[231], 2, progress=progress, full=True).run()
        assert not full.items and 0x8FF not in full.flags
        cases += 2
    land = NARC(rom.getFileByName("a/0/6/5")).files[114]
    assert struct.unpack_from("<H", land, 20 + 2*(6*32+4))[0] == 0
    assert struct.unpack_from("<H", land, 20 + 2*(6*32+5))[0] == 2
    print(f"PASS: {cases} compiled item-event paths; packaged events, map, scripts and messages match: {rom_path}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(); parser.add_argument("--rom", type=Path, required=True)
    test(parser.parse_args().rom)
