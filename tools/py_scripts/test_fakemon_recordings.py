#!/usr/bin/env python3
"""Execute the actual replay validation instructions in Unicorn (ARM Thumb).
Requires unicorn and the ARM binutils already used by the ROM build.
The CRC/signature preamble is intentionally excluded: this tests record bounds.
"""
from pathlib import Path
import struct
import subprocess
import tempfile
from unicorn import Uc, UC_ARCH_ARM, UC_MODE_THUMB
from unicorn.arm_const import UC_ARM_REG_R0, UC_ARM_REG_R4, UC_ARM_REG_SP, UC_ARM_REG_LR

ROOT = Path(__file__).resolve().parents[2]
CODE = 0x01000000
DATA = 0x02000000
STACK = 0x03000000
STOP = CODE + 0x8000

def assemble_validator(directory):
    source = (ROOT / 'asm/unk_0202FBCC.s').read_text()
    start = source.index('_020301DA:\n')
    end = source.index('\tthumb_func_end sub_0203018C', start)
    block = source[start:end]
    # Semicolon comments are Metrowerks syntax; GAS uses @.
    block = '\n'.join(line.split(';', 1)[0] for line in block.splitlines())
    source = '#include "constants/moves.h"\n#include "constants/species.h"\n.thumb\n.global test_bounds\n.thumb_func\ntest_bounds:\n push {r3, r4, r5, r6, r7, lr}\n mov r4, r0\n' + block + '\n'
    path = directory / 'bounds.S'
    path.write_text(source)
    subprocess.run(['cc', '-E', '-P', '-x', 'assembler-with-cpp', '-I', str(ROOT/'include'), str(path), '-o', str(directory/'bounds.s')], check=True)
    subprocess.run(['arm-none-eabi-as', '-mcpu=arm946e-s', '-mthumb', '-o', str(directory/'bounds.o'), str(directory/'bounds.s')], check=True)
    subprocess.run(['arm-none-eabi-ld', '-Ttext='+hex(CODE), '-e', 'test_bounds', '-o', str(directory/'bounds.elf'), str(directory/'bounds.o')], check=True)
    subprocess.run(['arm-none-eabi-objcopy', '-O', 'binary', str(directory/'bounds.elf'), str(directory/'bounds.bin')], check=True)
    return (directory/'bounds.bin').read_bytes()

def main():
    with tempfile.TemporaryDirectory(prefix='fakemon-recordings-') as temp:
        code = assemble_validator(Path(temp))
    machine = Uc(UC_ARCH_ARM, UC_MODE_THUMB)
    for address in (CODE, DATA, STACK):
        machine.mem_map(address, 0x10000)
    machine.mem_write(CODE, code)
    def accepted():
        machine.reg_write(UC_ARM_REG_R0, DATA)
        machine.reg_write(UC_ARM_REG_SP, STACK+0x8000)
        machine.reg_write(UC_ARM_REG_LR, STOP|1)
        machine.emu_start(CODE|1, STOP, count=3000)
        return machine.reg_read(UC_ARM_REG_R0) == 1
    def halfword(offset, value):
        machine.mem_write(DATA+offset, struct.pack('<H', value))
    assert accepted()
    cases = 0
    # Exhaust the entire serialized halfword domain, including the sparse gap.
    for field, expected in ((6, lambda v: v <= 495 or 1076 <= v <= 1086),
                            (8, lambda v: v <= 536),
                            (0x1C, lambda v: v <= 474)):
        for value in range(65536):
            halfword(0x1154+field, value)
            assert accepted() == expected(value), (field, value)
            cases += 1
        halfword(0x1154+field, 0)
    # Every team/party/move slot must be inspected, not just the first record.
    for team in range(4):
        for slot in range(6):
            record = 0x1154 + team*0x2A4 + slot*0x70
            for value in (495, 496, 1075, 1076, 1086, 1087):
                halfword(record+6, value)
                assert accepted() == (value <= 495 or 1076 <= value <= 1086)
                cases += 1
            halfword(record+6, 0)
            for move_slot in range(4):
                offset = record+0x1C+move_slot*2
                for value in (467, 468, 474, 475, 65535):
                    halfword(offset, value)
                    assert accepted() == (value <= 474)
                    cases += 1
                halfword(offset, 0)
    # The selected-move playback guard must use the same compiled move cap.
    playback = (ROOT/'asm/overlay_12_battle_controller_opponent.s').read_text()
    assert '_0225E564: .word NUM_MOVES' in playback
    print(f'PASS: {cases:,} actual ARM replay-bound cases; canonical species/item bounds preserved.')

if __name__ == '__main__':
    main()
