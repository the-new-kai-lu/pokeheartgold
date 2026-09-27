#!/usr/bin/env python3
"""Execute the actual Dex icon renderer in ARM Thumb with instrumented UI stubs.
Requires Unicorn and ARM binutils; validates preload bounds, not NDS graphics.
"""
from pathlib import Path
import struct
import subprocess
import tempfile
from unicorn import Uc, UC_ARCH_ARM, UC_MODE_THUMB, UC_HOOK_CODE, UC_HOOK_MEM_READ
from unicorn.arm_const import UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_SP, UC_ARM_REG_LR

ROOT = Path(__file__).resolve().parents[2]
CODE, DATA, STACK = 0x01000000, 0x02000000, 0x03000000
STOP = CODE + 0x8000
ROW_START, ROW_COUNT = DATA + 0x1030, 518

def build(directory):
    source = (ROOT/'asm/overlay_18.s').read_text()
    start = source.index('ov18_021F1598:')
    end = source.index('\tthumb_func_end ov18_021F1598', start)
    block = '\n'.join(line.split(';',1)[0] for line in source[start:end].splitlines())
    source = '.thumb\n.global ov18_021F1598\n.thumb_func\n' + block
    for name in ('ManagedSprite_SetDrawFlag', 'Pokedex_GetSeenFormByIdx', 'ov18_021F14FC', 'ov18_021F1160'):
        source += '\n.thumb_func\n'+name+':\n'
        if name == 'Pokedex_GetSeenFormByIdx': source += ' mov r0, #0\n'
        source += ' bx lr\n'
    (directory/'icons.s').write_text(source)
    subprocess.run(['arm-none-eabi-as','-mcpu=arm946e-s','-mthumb','-o',str(directory/'icons.o'),str(directory/'icons.s')],check=True)
    subprocess.run(['arm-none-eabi-ld','-Ttext='+hex(CODE),'-e','ov18_021F1598','-o',str(directory/'icons.elf'),str(directory/'icons.o')],check=True)
    subprocess.run(['arm-none-eabi-objcopy','-O','binary',str(directory/'icons.elf'),str(directory/'icons.bin')],check=True)
    symbols={line.split()[2]:int(line.split()[0],16) for line in subprocess.check_output(['arm-none-eabi-nm',str(directory/'icons.elf')],text=True).splitlines() if len(line.split())==3}
    return (directory/'icons.bin').read_bytes(), symbols

def main():
    with tempfile.TemporaryDirectory(prefix='fakemon-dex-icons-') as temp:
        code,symbols=build(Path(temp))
    machine=Uc(UC_ARCH_ARM,UC_MODE_THUMB)
    for address in (CODE,DATA,STACK): machine.mem_map(address,0x10000)
    machine.mem_write(CODE,code)
    machine.mem_write(DATA,struct.pack('<I',DATA+0xA000))
    machine.mem_write(DATA+0x670,struct.pack('<I',DATA+0xB000))
    draws,icons,reads=[],[],[]
    def call(uc,address,size,unused):
        if address==symbols['ManagedSprite_SetDrawFlag']: draws.append(uc.reg_read(UC_ARM_REG_R1))
        if address==symbols['ov18_021F14FC']: icons.append(uc.reg_read(UC_ARM_REG_R1))
    def read(uc,access,address,size,value,unused): reads.append((address,size))
    machine.hook_add(UC_HOOK_CODE,call)
    machine.hook_add(UC_HOOK_MEM_READ,read,begin=ROW_START,end=ROW_START+0x1000)
    cases=0
    for row in list(range(545))+[65535,0xFFFFFFFF]:
        for species in (0,25,1076):
            draws.clear();icons.clear();reads.clear()
            if row<545: machine.mem_write(ROW_START+row*4,struct.pack('<HH',species,2))
            machine.reg_write(UC_ARM_REG_R0,DATA)
            machine.reg_write(UC_ARM_REG_R1,row)
            machine.reg_write(UC_ARM_REG_R2,0)
            machine.reg_write(UC_ARM_REG_SP,STACK+0x8000)
            machine.reg_write(UC_ARM_REG_LR,STOP|1)
            machine.emu_start(CODE|1,STOP,count=1000)
            visible=row<ROW_COUNT and species!=0
            assert draws==([0,1] if visible else [0]),(row,species,draws)
            assert icons==([species] if visible else []),(row,species,icons)
            assert all(address+size<=ROW_START+ROW_COUNT*4 for address,size in reads),(row,reads)
            if row>=ROW_COUNT: assert reads==[],(row,reads)
            cases+=1
    print(f'PASS: {cases:,} actual ARM Dex icon cases; tail rows remain hidden without species reads.')

if __name__=='__main__': main()
