#!/usr/bin/env python3
"""Lossless HGSS land-container codec and checked BDHC flat-plane authoring.

The fifth header word is two halfwords, not a size/offset:
ov01_021F4AAC reads four bytes then consumes its high halfword BEFORE terrain.
BDHC layout follows ov01_021FB04C and its six typed array readers.
No renderer, material conversion or walkability equivalence is claimed.
"""

import argparse
import json
import struct
from dataclasses import dataclass
from pathlib import Path


def narc_members(data):
    if data[:4] != b"NARC" or len(data) != struct.unpack_from("<I", data, 8)[0]:
        raise ValueError("Invalid NARC header/length")
    pos = struct.unpack_from("<H", data, 12)[0]
    blocks = {}
    for _ in range(struct.unpack_from("<H", data, 14)[0]):
        tag, size = struct.unpack_from("<4sI", data, pos)
        if size < 8 or pos + size > len(data) or tag in blocks:
            raise ValueError("Invalid NARC block")
        blocks[tag] = data[pos + 8:pos + size]
        pos += size
    if pos != len(data):
        raise ValueError("Trailing NARC data")
    fat, image = blocks[b"BTAF"], blocks[b"GMIF"]
    count = struct.unpack_from("<H", fat)[0]
    if len(fat) != 4 + count * 8:
        raise ValueError("Invalid FAT length")
    result = []
    end = 0
    for i in range(count):
        start, stop = struct.unpack_from("<II", fat, 4 + i * 8)
        if not end <= start <= stop <= len(image):
            raise ValueError("Invalid member range")
        result.append(image[start:stop])
        end = stop
    return result


def bdhc_sections(data):
    if len(data) < 16 or data[:4] != b"BDHC":
        raise ValueError("Invalid BDHC header")
    counts = struct.unpack_from("<6H", data, 4)
    sizes = (8, 12, 4, 8, 8, 2)
    if len(data) != 16 + sum(n * s for n, s in zip(counts, sizes)):
        raise ValueError("Invalid BDHC array sizes")
    pos, sections = 16, []
    for count, size in zip(counts, sizes):
        sections.append(data[pos:pos + count * size])
        pos += count * size
    return counts, sections


def flat_bdhc(x0, z0, x1, z1, height=0):
    """Author one horizontal plate in DS world units (fx32, not tile units).

    Separate terrain attributes still determine blocked cells. This function
    only describes height; it does not make walls/furniture passable or blocked.
    """
    if not x0 < x1 or not z0 < z1:
        raise ValueError("Empty/reversed plane")
    def fx(value):
        scaled = value * 4096
        if scaled != int(scaled) or not -(1 << 31) <= scaled < (1 << 31):
            raise ValueError("Unrepresentable fx32 coordinate")
        return int(scaled)
    # Plane equation n dot p + constant = 0, normal points upwards.
    data = (b"BDHC" + struct.pack("<6H", 2, 1, 1, 1, 1, 1)
            + struct.pack("<4i", fx(x0), fx(z0), fx(x1), fx(z1))
            + struct.pack("<3i", 0, 4096, 0)
            + struct.pack("<i", -fx(height))
            + struct.pack("<4H", 0, 1, 0, 0)
            + struct.pack("<iHH", fx(z1), 1, 0)
            + struct.pack("<H", 0))
    bdhc_sections(data)
    return data


@dataclass
class Land:
    marker: int
    extra: bytes
    terrain: bytes
    props: bytes
    model: bytes
    collision: bytes

    @classmethod
    def decode(cls, data):
        if len(data) < 20:
            raise ValueError("Truncated land header")
        sizes = struct.unpack_from("<4I", data)
        marker, extra_size = struct.unpack_from("<HH", data, 16)
        if len(data) != 20 + extra_size + sum(sizes):
            raise ValueError("Land section lengths do not cover member")
        pos = 20
        extra = data[pos:pos + extra_size]
        pos += extra_size
        parts = []
        for size in sizes:
            parts.append(data[pos:pos + size])
            pos += size
        terrain, props, model, collision = parts
        if len(terrain) != 2048 or model[:4] != b"BMD0":
            raise ValueError("Unsupported terrain/model")
        if struct.unpack_from("<I", model, 8)[0] != len(model):
            raise ValueError("Model size mismatch")
        if collision:
            bdhc_sections(collision)
        return cls(marker, extra, terrain, props, model, collision)

    def encode(self):
        parts = (self.terrain, self.props, self.model, self.collision)
        data = (struct.pack("<4IHH", *(len(p) for p in parts),
                            self.marker, len(self.extra))
                + self.extra + b"".join(parts))
        self.decode(data)
        return data


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path)
    args = parser.parse_args()
    members = narc_members(args.archive.read_bytes())
    report = []
    for index, data in enumerate(members):
        land = Land.decode(data)
        if land.encode() != data:
            raise ValueError(f"Non-lossless member {index}")
        report.append({"member": index, "extra_size": len(land.extra),
                       "model_size": len(land.model),
                       "bdhc_size": len(land.collision)})
    print(json.dumps({"lossless_members": len(report), "members": report}, indent=2))


if __name__ == "__main__":
    main()