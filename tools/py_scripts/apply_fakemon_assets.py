#!/usr/bin/env python3
"""Append approved Fakemon resources to a freshly copied stock NARC (stdlib only).
Never changes any existing member. Called by filesystem.mk after archive copies.
"""
import argparse, hashlib, json, struct
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]

def read_narc(data):
    assert data[:4]==b'NARC'
    blocks={}; offset=16
    while offset<len(data):
        tag,size=struct.unpack_from('<4sI',data,offset)
        blocks[tag]=data[offset:offset+size];offset+=size
    fat=blocks[b'BTAF']; count=struct.unpack_from('<H',fat,8)[0]
    img=blocks[b'GMIF'][8:]
    files=[img[a:b] for a,b in (struct.unpack_from('<II',fat,12+8*i) for i in range(count))]
    return files,blocks[b'BTNF']

def make_narc(files,names):
    img=bytearray(); entries=bytearray()
    for f in files:
        start=len(img);img+=f
        entries+=struct.pack('<II',start,len(img))
        img+=b'\xff'*(-len(img)%4)
    fat=struct.pack('<4sIHH',b'BTAF',12+len(entries),len(files),0)+entries
    image=struct.pack('<4sI',b'GMIF',8+len(img))+img
    body=fat+names+image
    return struct.pack('<4sHHIHH',b'NARC',0xfffe,0x100,16+len(body),16,3)+body

def apply(path):
    rel=path.resolve().relative_to(ROOT/'files').as_posix()
    manifest=json.loads((ROOT/'files/fakemon/assets.json').read_text())
    additions=manifest['archives'].get(rel)
    if not additions:return
    data=path.read_bytes(); files,names=read_narc(data); original=list(files)
    # A real empty footprint remains safely readable in the sparse ID gap.
    filler=files[3] if rel=='a/0/6/9' else b''
    for addition in additions:
        f=ROOT/'files/fakemon'/addition['file']; blob=f.read_bytes()
        assert hashlib.sha256(blob).hexdigest()==addition['sha256'],f
        index=addition['index']
        assert index>=len(original), (rel,index,'attempt to overwrite canonical member')
        while len(files)<=index:files.append(filler)
        files[index]=blob
    result=make_narc(files,names)
    verify,_=read_narc(result)
    assert verify[:len(original)]==original
    path.write_bytes(result)

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('archive',type=Path)
    apply(parser.parse_args().archive)
