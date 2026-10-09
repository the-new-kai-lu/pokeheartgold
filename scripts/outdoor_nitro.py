"""Compact lossless outdoor resource builders; independent of lab defaults."""
import struct

from export_lab_model import FLOOR_MATERIAL_FLAGS, dictionary, gx_command

RECTANGLES = ((0, 0, 256, 256), (256, 0, 64, 256),
              (0, 256, 256, 64), (256, 256, 64, 64))
MAP_TEXTURE_BUDGET = 102400


def resource_dictionary(items):
    """Build the SDK's descending-bit Patricia lookup tree, not just a table."""
    if not items or len(items) > 254:
        raise ValueError("Invalid dictionary count")
    names = [name.encode("ascii").ljust(16, b"\0") for name, _ in items]
    if any(not name or len(name.encode("ascii")) > 16 or "\0" in name for name, _ in items):
        raise ValueError("Invalid resource name")
    keys = [int.from_bytes(name, "little") for name in names]
    if len(set(keys)) != len(keys) or any(key >> 127 for key in keys):
        raise ValueError("Duplicate or unsupported dictionary key")
    unit = len(items[0][1])
    if any(len(value) != unit for _, value in items):
        raise ValueError("Inconsistent dictionary entry size")
    nodes = [[127, 0, 0, 0]]
    node_keys = [0]

    def bit(key, index):
        return (key >> index) & 1

    for entry, key in enumerate(keys):
        parent, child = 0, nodes[0][1]
        while nodes[parent][0] > nodes[child][0]:
            parent, child = child, nodes[child][1 + bit(key, nodes[child][0])]
        split = (key ^ node_keys[child]).bit_length() - 1
        parent, child = 0, nodes[0][1]
        while nodes[parent][0] > nodes[child][0] and nodes[child][0] > split:
            parent, child = child, nodes[child][1 + bit(key, nodes[child][0])]
        index = len(nodes)
        direction = bit(key, split)
        node = [split, child, child, entry]
        node[1 + direction] = index
        nodes.append(node)
        node_keys.append(key)
        nodes[parent][1 + bit(key, nodes[parent][0])] = index
    offset = 8 + 4 * len(nodes)
    size = offset + 4 + (unit + 16) * len(items)
    return (struct.pack("<BBHHH", 0, len(items), size, 8, offset)
            + b"".join(bytes(node) for node in nodes)
            + struct.pack("<HH", unit, 4 + unit * len(items))
            + b"".join(value for _, value in items) + b"".join(names))


def textures(pixels):
    if len(pixels) != 320 * 320 * 4 or any(pixels[i] != 255 for i in range(3, len(pixels), 4)):
        raise ValueError("Expected opaque 320x320 RGBA")
    colors = [sum(round(pixels[i + c] * 31 / 255) << (5 * c)
                  for c in range(3)) for i in range(0, len(pixels), 4)]
    palette = sorted(set(colors))
    if len(palette) > 256:
        raise ValueError("Image exceeds lossless palette budget")
    lookup = {color: i for i, color in enumerate(palette)}
    image, params = bytearray(), []
    for x, y, width, height in RECTANGLES:
        param = (len(image) // 8 | ((width.bit_length() - 4) << 20)
                 | ((height.bit_length() - 4) << 23) | (4 << 26))
        params.append(param)
        for row in range(y, y + height):
            image.extend(lookup[color] for color in colors[row * 320 + x:row * 320 + x + width])
    if len(image) > MAP_TEXTURE_BUDGET:
        raise ValueError("Encoded map texture exceeds reserved budget")
    texdict = resource_dictionary([(f"tile{i}", struct.pack("<II", p, 0)) for i, p in enumerate(params)])
    paldict = dictionary("outdoorpal", struct.pack("<HH", 0, 0))
    texoff = 60 + len(texdict) + len(paldict)
    paloff = texoff + len(image)
    header = (b"TEX0" + struct.pack("<I", paloff + 512)
              + struct.pack("<IHHHHI", 0, len(image) // 8, 60, 0, 0, texoff)
              + struct.pack("<IHHHHII", 0, 0, 60, 0, 0, texoff, texoff)
              + struct.pack("<IHHHHI", 0, 64, 0, 60 + len(texdict), 0, paloff))
    palette += [0] * (256 - len(palette))
    tex = header + texdict + paldict + image + struct.pack("<256H", *palette)
    # Enforce the encoded upload size, not merely a manifest estimate.
    if struct.unpack_from("<H", tex, 12)[0] * 8 != MAP_TEXTURE_BUDGET:
        raise ValueError("Unexpected encoded texture allocation")
    return tex, params


def model(params):
    if len(params) != 4:
        raise ValueError("Expected four texture bindings")
    node = dictionary("root", struct.pack("<I", 40)) + struct.pack("<HH", 7, 0)
    sbc = bytes((0x26, 0, 0, 0, 0, 2, 0, 1, 0x0b))
    for i in range(4):
        sbc += bytes((4, i, 5, i))
    sbc += bytes((1, 0, 0))

    def matdict(offset):
        return resource_dictionary([(f"mat{i}", struct.pack("<I", offset + 44 * i)) for i in range(4)])

    def texdict(offset):
        return resource_dictionary([(f"tile{i}", struct.pack("<HBB", offset + i, 1, 0)) for i in range(4)])

    tex_offset = 4 + len(matdict(0))
    pal_offset = tex_offset + len(texdict(0))
    material_offset = pal_offset + len(dictionary("outdoorpal", struct.pack("<HBB", 0, 4, 0)))
    pair_offset = material_offset + 44 * 4
    mats = (struct.pack("<HH", tex_offset, pal_offset) + matdict(material_offset)
            + texdict(pair_offset)
            + dictionary("outdoorpal", struct.pack("<HBB", pair_offset, 4, 0)))
    for p, (_, _, width, height) in zip(params, RECTANGLES):
        mats += struct.pack("<HH6I4H2i", 0, 44, 0x7fffffff, 0, 0x1f00c0,
                            0xffffffff, p, 0xffffffff, 0, FLOOR_MATERIAL_FLAGS,
                            width, height, 4096, 4096)
    mats += bytes(range(4))
    shape_data, offsets = b"", []
    for x, z, width, height in RECTANGLES:
        offsets.append(len(shape_data))
        commands = gx_command(0x20, 0x7fff) + gx_command(0x40, 1)
        for dx, dz in ((0, 0), (0, height), (width, height), (width, 0)):
            commands += gx_command(0x22, dx * 16 | ((dz * 16) << 16))
            commands += gx_command(0x23, ((x + dx - 256) * 64) & 0xffff,
                                   ((z + dz - 256) * 64) & 0xffff)
        commands += gx_command(0x41)
        shape_data += struct.pack("<HHIII", 0, 16, 0, 16, len(commands)) + commands
    shape_dict_size = len(resource_dictionary([(f"quad{i}", bytes(4)) for i in range(4)]))
    shapes = resource_dictionary([(f"quad{i}", struct.pack("<I", shape_dict_size + offset))
                                  for i, offset in enumerate(offsets)]) + shape_data
    sbcoff = 64 + len(node)
    matoff = sbcoff + len(sbc)
    shpoff = matoff + len(mats)
    size = shpoff + len(shapes)
    info = (bytes((0, 0, 0, 1, 4, 4, 1, 0))
            + struct.pack("<ii4H6hii", 64 * 4096, 64, 16, 4, 0, 4,
                          -16384, 0, -16384, 20480, 0, 20480, 64 * 4096, 64))
    data = struct.pack("<5I", size, sbcoff, matoff, shpoff, size) + info + node + sbc + mats + shapes
    return (b"MDL0" + struct.pack("<I", size + 48)
            + dictionary("emerald_outdoor", struct.pack("<I", 48)) + data)