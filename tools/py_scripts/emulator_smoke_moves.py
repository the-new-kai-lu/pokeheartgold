#!/usr/bin/env python3
"""Capture move-summary screens through DeSmuME; inspect images before claiming a pass.

The supplied save must start in the field with the menu visible and the test
Pokemon first in the party, as in the documented smoke fixtures. Run with a
Python environment containing py-desmume. This does not exercise battle effects.
"""
import argparse
import hashlib
import json
import os
import shutil
from pathlib import Path

from desmume.controls import Keys, keymask
from desmume.emulator import DeSmuME

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--rom', type=Path, required=True)
parser.add_argument('--save', type=Path, required=True)
parser.add_argument('--output', type=Path, required=True)
args = parser.parse_args()
rom, save, output = args.rom.resolve(), args.save.resolve(), args.output.resolve()
output.mkdir(parents=True, exist_ok=False)
rom_name = output.name + '.nds'
shutil.copyfile(rom, output / rom_name)
shutil.copyfile(save, output / 'input.sav')
os.chdir(output)
emulator = DeSmuME()
emulator.open(rom_name)
emulator.volume_set(0)
assert emulator.backup.import_file('input.sav')
emulator.reset()


def frames(count):
    for _ in range(count):
        emulator.cycle(False)


def key(button):
    emulator.input.keypad_add_key(keymask(button))
    frames(3)
    emulator.input.keypad_rm_key(keymask(button))
    frames(120)


frames(900)
for _ in range(4):
    key(Keys.KEY_A)
frames(400)
emulator.input.touch_set_pos(43, 77)
frames(3)
emulator.input.touch_release()
frames(160)
key(Keys.KEY_A)
key(Keys.KEY_A)
frames(120)
screenshots = []
for page in range(3):
    name = f'summary-page-{page}.png'
    emulator.screenshot().save(name)
    screenshots.append(name)
    key(Keys.KEY_RIGHT)
(output / 'run.json').write_text(json.dumps({
    'rom_sha256': hashlib.sha256(rom.read_bytes()).hexdigest(),
    'input_save_sha256': hashlib.sha256(save.read_bytes()).hexdigest(),
    'input_save': str(save),
    'status': 'finished_requires_visual_review',
    'scope': 'Summary move names, types and PP; no battle execution',
    'screenshots': screenshots,
}, indent=2) + '\n')
