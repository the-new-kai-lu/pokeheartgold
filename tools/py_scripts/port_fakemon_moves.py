#!/usr/bin/env python3
"""Install the seven approved moves, preserving stock entries 0..467 byte for byte.

Run with a Python environment containing ndspy (the sibling hg-engine .venv works).
This is idempotent and intentionally does not change canonical learnsets or TMs.
"""
from pathlib import Path
import hashlib
import json
import struct
import xml.etree.ElementTree as ET
from ndspy.narc import NARC

ROOT = Path(__file__).resolve().parents[2]
# id, symbol, display, effect, category, power, type, accuracy, PP, chance, range, flags, old animation
MOVES = [
    (468, "WILD_CHARGE", "Wild Charge", 48, 0, 90, 13, 100, 15, 0, 0, 19, 344),
    (469, "SNARL", "Snarl", 71, 1, 55, 17, 95, 15, 100, 4, 18, 304),
    (470, "INCINERATE", "Incinerate", 277, 1, 60, 10, 100, 15, 100, 4, 18, 53),
    (471, "FIRE_LASH", "Fire Lash", 69, 0, 80, 10, 100, 15, 100, 0, 19, 7),
    (472, "ICICLE_CRASH", "Icicle Crash", 31, 0, 85, 15, 90, 10, 30, 0, 18, 333),
    (473, "BULLDOZE", "Bulldoze", 70, 0, 60, 4, 100, 20, 100, 8, 18, 89),
    (474, "HURRICANE", "Hurricane", 278, 1, 110, 2, 70, 10, 30, 0, 18, 239),
]
DESCRIPTIONS = [
    "The user charges\\nwith electricity.\\nIt takes a quarter of\\nthe damage in recoil.\\n",
    "The user snarls at\\nthe opposing team,\\nlowering their\\nSp. Atk stats.\\n",
    "The user scorches\\nthe opposing team.\\nTheir held Berries\\nare destroyed.\\n",
    "The foe is struck\\nwith a lash of fire.\\nIt also lowers the\\nfoe’s Defense.\\n",
    "Large icicles fall\\non the foe.\\nIt may also make\\nthe foe flinch.\\n",
    "The user stomps the\\nground, damaging\\nnearby Pokémon and\\nlowering their Speed.\\n",
    "A fierce wind hits\\nthe foe. It may\\ncause confusion. Its\\naim changes in rain.\\n",
]

def set_row(path, index, label, text):
    source = path.read_text()
    root = ET.fromstring(source)
    rows = list(root)
    if index < len(rows):
        old = rows[index]
        # Replace just this row; do not reformat thousands of stock text rows.
        start = source.index('\t<row ', source.index(f'id="{old.attrib["id"]}"') - 10)
        end = source.index('\t</row>', start) + len('\t</row>')
    else:
        assert index == len(rows), (path, index, len(rows))
        start = end = source.rindex('</body>')
    escaped = text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
    row = f'\t<row id="{label}" index="{index}">\n\t\t<attribute name="window_context_name">used</attribute>\n\t\t<language name="English">{escaped}</language>\n\t</row>'
    if start == end:
        row += '\n'
    path.write_text(source[:start] + row + source[end:])


def main():
    path = ROOT / 'files/poketool/waza/waza_tbl.narc'
    archive = NARC(path.read_bytes())
    stock = archive.files[:468]
    archive.files = list(stock)
    report = []
    for row, description in zip(MOVES, DESCRIPTIONS):
        mid, symbol, name, effect, category, power, mtype, accuracy, pp, chance, target, flags, animation = row
        record = struct.pack('<H6BHbBBBH', effect, category, power, mtype, accuracy, pp, chance, target, 0, flags, 0, 0, 0)
        assert len(record) == 16 and len(archive.files) == mid
        archive.files.append(record)
        for bank, display in [('0749', description), ('0750', name), ('0751', name.upper())]:
            set_row(ROOT / f'files/msgdata/msg/msg_{bank}.gmm', mid, f'msg_{bank}_{symbol.lower()}', display)
        report.append({'id':mid,'name':name,'effect':effect,'power':power,'accuracy':accuracy,'pp':pp,'animation':animation})
    path.write_bytes(archive.save())
    assert NARC(path.read_bytes()).files[:468] == stock
    set_row(ROOT / 'files/msgdata/msg/msg_0197.gmm', 1276, 'msg_0197_incinerate', '{STRVAR_1 1, 0, 0}’s {STRVAR_1 8, 1, 0}\\nwas burned up!')
    out = ROOT / 'documentation/fakemon/moves-validation.json'
    out.write_text(json.dumps({'stock_records_sha256':hashlib.sha256(b''.join(stock)).hexdigest(),'count':len(archive.files),'moves':report},indent=2)+'\n')
    print(f'Installed {len(MOVES)} moves; stock entries unchanged; {out.relative_to(ROOT)}')

if __name__ == '__main__':
    main()
