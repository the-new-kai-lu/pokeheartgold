"""Deterministic source-derived opening actors and compact map geometry.

Pure encoders ported from the reviewed private experiments. No private paths,
installation, native compilation or runtime operations are present here.
"""
import hashlib
import struct
from extract_emerald_lab import indexed_png, palette, tile_pixel
from export_lab_model import dictionary, FLOOR_MATERIAL_FLAGS, gx_command

ATLAS_W, ATLAS_H = 128, 256
SLOT, COLS = 18, 5
MAX_MAP_TEXTURE = 102400

def sha(data):
    return hashlib.sha256(data).hexdigest()

def cells(pixels):
    assert len(pixels) == 512 * 512 * 4
    return [b"".join(pixels[((z * 16 + y) * 512 + x * 16) * 4:
                           ((z * 16 + y) * 512 + x * 16 + 16) * 4]
                     for y in range(16)) for z in range(32) for x in range(32)]


def rgba_to_555(rgba):
    assert rgba[3] == 255
    return sum(round(rgba[c] * 31 / 255) << (5 * c) for c in range(3))


def atlas_for(source):
    """Stable first-occurrence mapping, full 16x16 BGR555 equality only."""
    signatures = [b"".join(struct.pack("<H", rgba_to_555(tile[i:i + 4]))
                           for i in range(0, len(tile), 4)) for tile in cells(source)]
    unique = list(dict.fromkeys(signatures))
    assert len(unique) <= COLS * (ATLAS_H // SLOT)
    indices = [unique.index(sig) for sig in signatures]
    assert [unique[i] for i in indices] == signatures
    palette = sorted({value[0] for tile in unique for value in struct.iter_unpack("<H", tile)})
    assert len(palette) <= 256
    palette_index = {color: i for i, color in enumerate(palette)}
    image = bytearray(ATLAS_W * ATLAS_H)
    for i, tile in enumerate(unique):
        x0, y0 = i % COLS * SLOT, i // COLS * SLOT
        assert x0 + SLOT <= ATLAS_W and y0 + SLOT <= ATLAS_H
        for y in range(SLOT):
            for x in range(SLOT):
                src_x, src_y = min(15, max(0, x - 1)), min(15, max(0, y - 1))
                rgb555 = struct.unpack_from("<H", tile, (src_y * 16 + src_x) * 2)[0]
                image[(y0 + y) * ATLAS_W + x0 + x] = palette_index[rgb555]
    # Prove every atlas cell resolves back to the input BGR555 tile.
    for i, tile in enumerate(unique):
        x0, y0 = i % COLS * SLOT + 1, i // COLS * SLOT + 1
        for y in range(16):
            for x in range(16):
                assert palette[image[(y0 + y) * ATLAS_W + x0 + x]] == struct.unpack_from(
                    "<H", tile, (y * 16 + x) * 2)[0]
    return image, palette, indices, unique


def texture(image, palette):
    """Identical TEX0 8bpp fields as trusted export_lab_model.texture/outdoor_nitro."""
    assert len(image) == ATLAS_W * ATLAS_H and len(image) <= MAX_MAP_TEXTURE
    assert len(image) % 8 == 0 and len(palette) <= 256
    params = ((ATLAS_W.bit_length() - 4) << 20
              | (ATLAS_H.bit_length() - 4) << 23 | (4 << 26))
    texdict = dictionary("atlas", struct.pack("<II", params, 0))
    paldict = dictionary("outdoorpal", struct.pack("<HH", 0, 0))
    texoff = 60 + len(texdict) + len(paldict)
    paloff = texoff + len(image)
    header = (b"TEX0" + struct.pack("<I", paloff + 512)
              + struct.pack("<IHHHHI", 0, len(image) // 8, 60, 0, 0, texoff)
              + struct.pack("<IHHHHII", 0, 0, 60, 0, 0, texoff, texoff)
              + struct.pack("<IHHHHI", 0, 64, 0, 60 + len(texdict), 0, paloff))
    assert len(header) == 60
    return header + texdict + paldict + image + struct.pack(
        "<256H", *(palette + [0] * (256 - len(palette)))), params


def commands_for(indices):
    """Emit literal BEGIN QUADS, four TEXCOORD/VTX_XZ pairs, END per cell."""
    commands = gx_command(0x20, 0x7fff)
    audit = []
    for z in range(32):
        for x in range(32):
            index = indices[z * 32 + x]
            u0, v0 = (index % COLS * SLOT + 1) * 16, (index // COLS * SLOT + 1) * 16
            x0, z0 = (x * 16 - 256) * 64, (z * 16 - 256) * 64
            commands += gx_command(0x40, 1)
            for dx, dz in ((0, 0), (0, 16), (16, 16), (16, 0)):
                u, v = u0 + dx * 16, v0 + dz * 16
                vx, vz = x0 + dx * 64, z0 + dz * 64
                assert 0 <= u <= 32767 and 0 <= v <= 32767
                assert -32768 <= vx <= 32767 and -32768 <= vz <= 32767
                commands += gx_command(0x22, u | (v << 16))
                commands += gx_command(0x23, vx & 0xffff, vz & 0xffff)
            commands += gx_command(0x41)
            audit.append((x, z, index, u0, v0))
    # Parse the actual command stream, not just the generator loop/counters.
    cursor = 0
    def take(opcode, nparams):
        nonlocal cursor
        words = struct.unpack_from("<" + "I" * (1 + nparams), commands, cursor)
        assert words[0] == opcode, (cursor, words[0], opcode)
        cursor += 4 * (1 + nparams)
        return words[1:]
    assert take(0x20, 1) == (0x7fff,)
    begin = texcoord = vertex = end = 0
    for x, z, index, u0, v0 in audit:
        assert take(0x40, 1) == (1,)
        begin += 1
        for dx, dz in ((0, 0), (0, 16), (16, 16), (16, 0)):
            assert take(0x22, 1) == ((u0 + dx * 16) | ((v0 + dz * 16) << 16),)
            texcoord += 1
            actual_x, actual_z = take(0x23, 2)
            assert struct.unpack("<h", struct.pack("<H", actual_x))[0] == (x * 16 + dx - 256) * 64
            assert struct.unpack("<h", struct.pack("<H", actual_z))[0] == (z * 16 + dz - 256) * 64
            vertex += 1
        take(0x41, 0)
        end += 1
    assert cursor == len(commands) and (begin, texcoord, vertex, end) == (1024, 4096, 4096, 1024)
    assert begin < 2048 and vertex < 6144
    return commands, dict(actual_stream_bytes=cursor, begin_quads=begin,
                          texcoords=texcoord, vertices=vertex, end_quads=end,
                          available_polygons_before_2048=2048-begin,
                          available_vertices_before_6144=6144-vertex)


def model(params, commands):
    """Trusted single-material model envelope; substitute audited quad stream."""
    node = dictionary("root", struct.pack("<I", 40)) + struct.pack("<HH", 7, 0)
    sbc = bytes((0x26, 0, 0, 0, 0, 2, 0, 1, 0x0b, 4, 0, 5, 0, 1, 0, 0))
    # Same dictionary/pairing and material struct as export_lab_model.model.
    material = struct.pack("<HH6I4H2i", 0, 44, 0x7fffffff, 0,
                           0x1f00c0, 0xffffffff, params, 0xffffffff,
                           0, FLOOR_MATERIAL_FLAGS, ATLAS_W, ATLAS_H, 4096, 4096)
    # Names above differ in length from the original single-material encoder:
    # compute all offsets from actual dictionaries, not its fixed-size constants.
    matdict = dictionary("labmat", struct.pack("<I", 0))
    texdict = dictionary("atlas", struct.pack("<HBB", 0, 1, 0))
    paldict = dictionary("outdoorpal", struct.pack("<HBB", 0, 1, 0))
    tex_offset = 4 + len(matdict)
    pal_offset = tex_offset + len(texdict)
    mat_offset = pal_offset + len(paldict)
    pair_offset = mat_offset + 44
    mats = (struct.pack("<HH", tex_offset, pal_offset)
            + dictionary("labmat", struct.pack("<I", mat_offset))
            + dictionary("atlas", struct.pack("<HBB", pair_offset, 1, 0))
            + dictionary("outdoorpal", struct.pack("<HBB", pair_offset, 1, 0))
            + material + b"\0" * 4)
    shapes = (dictionary("floor", struct.pack("<I", 40))
              + struct.pack("<HHIII", 0, 16, 0, 16, len(commands)) + commands)
    sbcoff = 64 + len(node)
    matoff = sbcoff + len(sbc)
    shpoff = matoff + len(mats)
    size = shpoff + len(shapes)
    # bbox extrema are DS vertex units; field model scale is 64.
    info = (bytes((0, 0, 0, 1, 1, 1, 1, 0))
            + struct.pack("<ii4H6hii", 64 * 4096, 64, 4096, 1024, 0, 1024,
                          -16384, 0, -16384, 16384, 0, 16384, 64 * 4096, 64))
    data = struct.pack("<5I", size, sbcoff, matoff, shpoff, size) + info + node + sbc + mats + shapes
    assert len(data) == size
    return b"MDL0" + struct.pack("<I", size + 48) + dictionary(
        "emerald_outdoor", struct.pack("<I", 48)) + data


def border_pixels(border, sources, source):
    """The same two BG layers, palette and metatile decoder as donor extraction."""
    roots = ("data/tilesets/primary/general", "data/tilesets/secondary/petalburg")
    sheets = [indexed_png(source(r + "/tiles.png", sources[r + "/tiles.png"])) for r in roots]
    pals = [palette(source(roots[0 if i < 6 else 1] + f"/palettes/{i:02}.pal",
                           sources[roots[0 if i < 6 else 1] + f"/palettes/{i:02}.pal"]))
            for i in range(13)]
    out = bytearray(bytes((*pals[0][0], 255)) * (32 * 32))
    for by in range(2):
        for bx in range(2):
            tile = border[bx + by * 2] & 1023
            bank, local = (0, tile) if tile < 512 else (1, tile - 512)
            raw = source(roots[bank] + "/metatiles.bin", sources[roots[bank] + "/metatiles.bin"])
            attrs = source(roots[bank] + "/metatile_attributes.bin",
                           sources[roots[bank] + "/metatile_attributes.bin"])
            words = struct.unpack_from("<8H", raw, local * 16)
            layer = struct.unpack_from("<H", attrs, local * 2)[0] >> 12
            assert layer in (0, 1, 2)
            destinations = ((1, 2), (0, 1), (0, 2))[layer]
            # BG3, BG2, BG1 compositing; reproduce extraction's layer ordering.
            layers = [bytearray(16 * 16 * 4) for _ in range(3)]
            for half in range(2):
                for quadrant in range(4):
                    for py in range(8):
                        for px in range(8):
                            color = tile_pixel(words[half * 4 + quadrant], px, py, sheets, pals)
                            off = ((quadrant // 2 * 8 + py) * 16 + quadrant % 2 * 8 + px) * 4
                            layers[destinations[half]][off:off + 4] = bytes(color)
            for py in range(16):
                for px in range(16):
                    src = (py * 16 + px) * 4
                    dest = ((by * 16 + py) * 32 + bx * 16 + px) * 4
                    for image in layers:
                        if image[src + 3]:
                            out[dest:dest + 4] = image[src:src + 4]
    return bytes(out)


def decode(template):
    if template[:4] != b"BTX0":
        raise ValueError("Not NSBTX")
    base = struct.unpack_from("<I", template, 16)[0]
    if template[base:base + 4] != b"TEX0":
        raise ValueError("Not TEX0")
    image = base + struct.unpack_from("<I", template, base + 20)[0]
    paloff = base + struct.unpack_from("<I", template, base + 56)[0]
    dictionary = base + struct.unpack_from("<H", template, base + 14)[0]
    entries = dictionary + struct.unpack_from("<H", template, dictionary + 6)[0]
    unit, names = struct.unpack_from("<HH", template, entries)
    if (template[dictionary + 1], unit) != (16, 8):
        raise ValueError("Expected 16 frames of native texture")
    slots = {}
    for index in range(16):
        name = template[entries + names + index * 16:entries + names + (index + 1) * 16].rstrip(b"\0").decode("ascii")
        suffix = int(name.split(".")[1])
        param = struct.unpack_from("<I", template, entries + 4 + index * unit)[0]
        if (param >> 26) & 7 != 3 or ((param >> 20) & 7) != 2 or ((param >> 23) & 7) != 2:
            raise ValueError("Not native 32x32 4bpp frame " + name)
        offset = image + (param & 65535) * 8
        if offset + 512 > len(template) or suffix in slots:
            raise ValueError("Invalid frame offset / duplicate suffix")
        slots[suffix] = offset
    aliases = {(1, 3), (5, 7), (9, 11), (13, 15)}
    if set(slots) != set(range(1, 17)) or len(set(slots.values())) != 12 or {
        tuple(sorted((a, b))) for a in slots for b in slots if a < b and slots[a] == slots[b]
    } != aliases:
        raise ValueError("Unexpected native idle alias map")
    return slots, paloff


def unpack_frame(data):
    return [v for byte in data for v in (byte & 15, byte >> 4)]


def convert(template, source, color, frame_map, size, anchor):
    w, h, pixels = indexed_png(source)
    fw, fh = size
    if (w, h) != (9 * fw, fh) and (w, h) != (fw, fh):
        raise ValueError("Unexpected donor sheet dimensions")
    if len(frame_map) != 16 or any(i < 0 or i >= w // fw for i, _ in frame_map):
        raise ValueError("Bad frame mapping")
    colors = palette(color)
    slots, paloff = decode(template)
    result = bytearray(template)
    native_colors = [sum((v >> 3) << (5 * channel) for channel, v in enumerate(rgb)) for rgb in colors]
    struct.pack_into("<16H", result, paloff, *native_colors)
    sheet = bytearray(16 * 32 * 32)
    mappings = []
    written = {}
    for suffix, (donor_frame, flip) in enumerate(frame_map, 1):
        canvas = bytearray(32 * 32)
        ox, oy = anchor
        for y in range(fh):
            for x in range(fw):
                donor_x = fw - 1 - x if flip else x
                canvas[(y + oy) * 32 + x + ox] = pixels[y * w + donor_frame * fw + donor_x]
        packed = bytes(canvas[i] | (canvas[i + 1] << 4) for i in range(0, len(canvas), 2))
        if slots[suffix] in written and written[slots[suffix]] != packed:
            raise ValueError("Native alias conflicts with donor frames")
        written[slots[suffix]] = packed
        result[slots[suffix]:slots[suffix] + 512] = packed
        if unpack_frame(result[slots[suffix]:slots[suffix] + 512]) != list(canvas):
            raise AssertionError("NSBTX encode/decode frame roundtrip failed")
        sheet[(suffix - 1) * 1024:suffix * 1024] = canvas
        mappings.append(dict(suffix=suffix, donor_frame=donor_frame, horizontal_mirror=flip,
                             native_offset=slots[suffix], source_sha256=sha(bytes(canvas))))
    result = bytes(result)
    decoded, native_pal = decode(result)
    if decoded != slots or struct.unpack_from("<16H", result, native_pal) != tuple(native_colors):
        raise AssertionError("NSBTX dictionary/palette roundtrip failed")
    return result
