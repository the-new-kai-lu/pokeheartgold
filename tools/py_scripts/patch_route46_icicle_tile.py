#!/usr/bin/env python3
"""Clear the marked northwest grass tile: Route 46 (612,358), land member 114.

The collision/encounter grid and the raised grass mesh are separate. Clip the
four affected grass display lists, revealing the existing plain ground below.
Every other NARC member and all textures/buildings/BDHC remain byte-identical.
Read the recorded pre-edit commit, so regeneration is deterministic.
"""
import hashlib
import struct
import subprocess
from pathlib import Path
from apply_fakemon_assets import read_narc, make_narc
ROOT = Path(__file__).resolve().parents[2]
SOURCE_COMMIT = "227b8d954"


def signed(v, bits):
    return v - (1 << bits) if v & (1 << (bits - 1)) else v


def decode_quads(data):
    counts = {0: 0, 0x40: 1, 0x41: 0, 0x21: 1, 0x22: 1,
              0x23: 2, 0x24: 1, 0x25: 1, 0x26: 1, 0x27: 1}
    off = 0
    pos = [0., 0., 0.]
    verts = []
    while off < len(data):
        ids = data[off:off+4]
        off += 4
        for op in ids:
            n = counts[op]
            words = struct.unpack_from("<" + "I" * n, data, off)
            off += n * 4
            if op == 0x40:
                assert words[0] == 1, "Expected independent quads"
            elif op == 0x21:
                assert words[0] == 524283, "Expected ground normal"
            elif op == 0x22:
                uv = [signed(words[0] >> k & 65535, 16) / 16 for k in (0, 16)]
            elif op == 0x24:
                pos = [signed(words[0] >> k & 1023, 10) / 64 for k in (0, 10, 20)]
            elif op == 0x23:
                pos = [signed(words[0] & 65535, 16) / 4096,
                       signed(words[0] >> 16, 16) / 4096,
                       signed(words[1] & 65535, 16) / 4096]
            elif op in (0x25, 0x26, 0x27):
                for axis, k in zip({0x25: (0, 1), 0x26: (0, 2), 0x27: (1, 2)}[op], (0, 16)):
                    pos[axis] = signed(words[0] >> k & 65535, 16) / 4096
            if 0x23 <= op <= 0x27:
                verts.append((*pos, *uv))
    assert len(verts) % 4 == 0
    return [verts[i:i+4] for i in range(0, len(verts), 4)]


def clip(poly, axis, edge, keep_less):
    result = []
    for a, b in zip(poly, poly[1:] + poly[:1]):
        ina = a[axis] <= edge if keep_less else a[axis] >= edge
        inb = b[axis] <= edge if keep_less else b[axis] >= edge
        if ina:
            result.append(a)
        if ina != inb:
            t = (edge - a[axis]) / (b[axis] - a[axis])
            result.append(tuple(x + t * (y - x) for x, y in zip(a, b)))
    return result


def subtract_tile(quad):
    # Include the decorative north/west fringe of this corner grass tile.
    remaining = quad
    result = []
    for axis, edge, keep_less in ((0, -3.125, True), (0, -2.75, False),
                                  (2, -2.625, True), (2, -2.25, False)):
        outside = clip(remaining, axis, edge, keep_less)
        if outside:
            xs = [v[0] for v in outside]; zs = [v[2] for v in outside]
            if max(xs) > min(xs) and max(zs) > min(zs):
                # Axis-aligned quads clipped against axis-aligned bounds.
                unique = list(dict.fromkeys(outside))
                assert len(unique) == 4
                result.append(unique)
        remaining = clip(remaining, axis, edge, not keep_less)
        if not remaining:
            break
    return result


def encode(quads):
    commands = [(0x40, (1,)), (0x21, (524283,))]
    for quad in quads:
        for x, y, z, u, v in quad:
            commands.append((0x22, ((round(u * 16) & 65535) | (round(v * 16) & 65535) << 16,)))
            commands.append((0x23, ((round(x * 4096) & 65535) | (round(y * 4096) & 65535) << 16,
                                      round(z * 4096) & 65535)))
    commands.append((0x41, ()))
    while len(commands) % 4:
        commands.append((0, ()))
    output = bytearray()
    for i in range(0, len(commands), 4):
        block = commands[i:i+4]
        output += bytes(op for op, words in block)
        for op, words in block:
            output += struct.pack("<" + "I" * len(words), *words)
    return output


def main():
    original = subprocess.check_output(["git", "show", f"{SOURCE_COMMIT}:files/a/0/6/5"], cwd=ROOT)
    files, names = read_narc(original)
    old = files[114]
    collision_size, objects_size, model_size, bdhc_size = struct.unpack_from("<4I", old)
    assert (collision_size, objects_size, model_size, bdhc_size) == (2048, 48, 30260, 228)
    head = bytearray(old[:20 + collision_size + objects_size])
    tile = 20 + 2 * (6 * 32 + 4)
    assert struct.unpack_from("<H", head, tile)[0] == 2
    struct.pack_into("<H", head, tile, 0)  # ordinary walkable, non-encounter ground
    model = bytearray(old[len(head):len(head)+model_size])
    model_base = 20 + 48
    shape_base = model_base + 3620
    delta_quads = 0
    for index in (9, 10, 12, 13):
        shape = shape_base + 592 + 16 * index
        rel, size = struct.unpack_from("<II", model, shape+8)
        old_quads = decode_quads(model[shape+rel:shape+rel+size])
        new_quads = [part for quad in old_quads for part in subtract_tile(quad)]
        delta_quads += len(new_quads) - len(old_quads)
        data = encode(new_quads)
        struct.pack_into("<II", model, shape+8, len(model)-shape, len(data))
        model += data
    for off in (0, 16):  # model size and model end offset
        struct.pack_into("<I", model, model_base+off, len(model)-model_base)
    for off, delta in ((36, delta_quads*4), (38, delta_quads), (42, delta_quads)):
        old_count = struct.unpack_from("<H", model, model_base+off)[0]
        struct.pack_into("<H", model, model_base+off, old_count+delta)
    struct.pack_into("<I", model, 8, len(model))
    struct.pack_into("<I", model, 24, len(model)-20)
    struct.pack_into("<I", head, 8, len(model))
    files[114] = bytes(head + model) + old[-bdhc_size:]
    result = make_narc(files, names)
    check, _ = read_narc(result)
    assert all(check[i] == data for i, data in enumerate(read_narc(original)[0]) if i != 114)
    (ROOT / "files/a/0/6/5").write_bytes(result)
    print("Route 46 tile (612,358) cleared; archive SHA256", hashlib.sha256(result).hexdigest())

if __name__ == "__main__":
    main()
