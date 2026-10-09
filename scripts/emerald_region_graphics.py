"""Bounded, lossless static Emerald textures and flat HGSS land models.

Reuse the opening's Nitro dictionary/container/GX encoders. Palette-bin packing
allows larger towns without increasing the native field texture reservation.
No donor assets are checked into the repository.
"""
from collections import defaultdict
import struct

from episode_assets import MAX_FIELD_MODEL_BYTES, pack_gx
from export_lab_model import FLOOR_MATERIAL_FLAGS, container, dictionary
from outdoor_nitro import MAP_TEXTURE_BUDGET, resource_dictionary


def texture_pages(tiles):
    """Pack exact pixel colors into 16/256-color pages, each a power-of-two.

    Splitting each bin by its population's binary representation avoids the
    otherwise almost 2x padding of one large atlas. A texture is point-sampled;
    each cell has exact integer UV boundaries, not a filtered/scaled thumbnail.
    """
    unique = list(dict.fromkeys(tiles))
    if any(len(tile) != 256 or any(not 0 <= c < 32768 for c in tile) for tile in unique):
        raise ValueError("Expected opaque 16x16 BGR555 metatiles")
    bins = []
    for tile in sorted(unique, key=lambda t: (-len(set(t)), t)):
        colors = set(tile)
        capacity = 16 if len(colors) <= 16 else 256
        candidates = [(len(colors - b["colors"]), i)
                      for i, b in enumerate(bins)
                      if b["capacity"] == capacity and len(b["colors"] | colors) <= capacity]
        if candidates:
            _, index = min(candidates)
        else:
            index = len(bins)
            bins.append(dict(capacity=capacity, colors=set(), tiles=[]))
        bins[index]["colors"].update(colors)
        bins[index]["tiles"].append(tile)
    pages, mapping, image, palettes = [], {}, bytearray(), bytearray()
    for b in bins:
        colors = sorted(b["colors"])
        pal_offset = len(palettes)
        colors += [0] * (b["capacity"] - len(colors))
        palettes.extend(struct.pack(f"<{len(colors)}H", *colors))
        lookup = {c: i for i, c in reversed(list(enumerate(colors)))}
        remaining = b["tiles"]
        while remaining:
            count = min(256, 1 << (len(remaining).bit_length() - 1))
            selected, remaining = remaining[:count], remaining[count:]
            columns = 1 << ((count.bit_length() - 1 + 1) // 2)
            width, height = columns * 16, count // columns * 16
            fmt = 3 if b["capacity"] == 16 else 4
            param = (len(image) // 8 | (width.bit_length() - 4) << 20 |
                     (height.bit_length() - 4) << 23 | fmt << 26)
            indices = bytearray(width * height)
            page_index = len(pages)
            for i, tile in enumerate(selected):
                x, y = i % columns * 16, i // columns * 16
                mapping[tile] = (page_index, x, y)
                for row in range(16):
                    indices[(y + row) * width + x:(y + row) * width + x + 16] = bytes(
                        lookup[c] for c in tile[row * 16:row * 16 + 16])
                # Check the encoder's physical palette/index output, not hashes.
                if tuple(colors[indices[(y + py) * width + x + px]]
                         for py in range(16) for px in range(16)) != tile:
                    raise ValueError("Texture palette reconstruction changed pixels")
            if fmt == 3:
                image.extend(indices[i] | indices[i + 1] << 4
                             for i in range(0, len(indices), 2))
            else:
                image.extend(indices)
            pages.append(dict(param=param, width=width, height=height,
                              palette_offset=pal_offset, palette_colors=len(colors)))
    if len(pages) > 254 or len(image) > MAP_TEXTURE_BUDGET or len(palettes) > 8192:
        raise ValueError(f"Native texture budget exceeded: {len(pages)} pages, "
                         f"{len(image)} image bytes, {len(palettes)} palette bytes")
    texdict = resource_dictionary([
        (f"page{i}", struct.pack("<II", p["param"], 0)) for i, p in enumerate(pages)])
    paldict = resource_dictionary([
        (f"pal{i}", struct.pack("<HH", p["palette_offset"] // 8, 0))
        for i, p in enumerate(pages)])
    texoff = 60 + len(texdict) + len(paldict)
    paloff = texoff + len(image)
    header = (b"TEX0" + struct.pack("<I", paloff + len(palettes))
              + struct.pack("<IHHHHI", 0, len(image) // 8, 60, 0, 0, texoff)
              + struct.pack("<IHHHHII", 0, 0, 60, 0, 0, texoff, texoff)
              + struct.pack("<IHHHHI", 0, len(palettes) // 8, 0,
                            60 + len(texdict), 0, paloff))
    tex = container(b"BTX0", (header + texdict + paldict + image + palettes,))
    return tex, mapping, pages, dict(unique_tiles=len(unique), pages=len(pages),
                                   texture_bytes=len(image), palette_bytes=len(palettes))


def map_model(tile_cells, mapping, pages):
    """One material/shape per used texture page, under the existing slot limit."""
    if len(tile_cells) != 1024:
        raise ValueError("A land model must have exactly 32x32 cells")
    groups = defaultdict(list)
    for i, tile in enumerate(tile_cells):
        page, u, v = mapping[tile]
        groups[page].append((i % 32, i // 32, u, v))
    used = sorted(groups)
    n = len(used)
    node = dictionary("root", struct.pack("<I", 40)) + struct.pack("<HH", 7, 0)
    sbc = bytes((0x26, 0, 0, 0, 0, 2, 0, 1, 0x0B))
    sbc += b"".join(bytes((4, i, 5, i)) for i in range(n)) + b"\1"
    sbc += bytes((-len(sbc)) % 4)

    def matdict(offset):
        return resource_dictionary([(f"mat{i}", struct.pack("<I", offset + 44 * i))
                                    for i in range(n)])

    def bindings(prefix, offset):
        return resource_dictionary([(f"{prefix}{page}", struct.pack("<HBB", offset + i, 1, 0))
                                    for i, page in enumerate(used)])

    tex_offset = 4 + len(matdict(0))
    pal_offset = tex_offset + len(bindings("page", 0))
    mat_offset = pal_offset + len(bindings("pal", 0))
    pair_offset = mat_offset + 44 * n
    mats = (struct.pack("<HH", tex_offset, pal_offset) + matdict(mat_offset)
            + bindings("page", pair_offset) + bindings("pal", pair_offset))
    for page in used:
        p = pages[page]
        mats += struct.pack("<HH6I4H2i", 0, 44, 0x7FFFFFFF, 0, 0x1F00C0,
                            0xFFFFFFFF, p["param"], 0xFFFFFFFF, 0,
                            FLOOR_MATERIAL_FLAGS, p["width"], p["height"], 4096, 4096)
    mats += bytes(range(n))
    mats += bytes((-len(mats)) % 4)
    offsets, shape_data = [], bytearray()
    for page in used:
        commands = [(0x20, (0x7FFF,)), (0x40, (1,))]
        first = True
        for x, z, u, v in groups[page]:
            for dx, dz in ((0, 0), (0, 16), (16, 16), (16, 0)):
                commands.append((0x22, ((u + dx) * 16 | (v + dz) * 16 << 16,)))
                vx, vz = (x * 16 + dx - 256) * 64, (z * 16 + dz - 256) * 64
                commands.append((0x23, (vx & 0xFFFF, vz & 0xFFFF)) if first else
                                (0x26, ((vx & 0xFFFF) | (vz & 0xFFFF) << 16,)))
                first = False
        commands.append((0x41, ()))
        packed = pack_gx(commands)
        offsets.append(len(shape_data))
        shape_data.extend(struct.pack("<HHIII", 0, 16, 0, 16, len(packed)) + packed)
    dict_size = len(resource_dictionary([(f"shape{i}", bytes(4)) for i in range(n)]))
    shapes = resource_dictionary([(f"shape{i}", struct.pack("<I", dict_size + off))
                                  for i, off in enumerate(offsets)]) + shape_data
    sbcoff = 64 + len(node)
    matoff, shpoff = sbcoff + len(sbc), sbcoff + len(sbc) + len(mats)
    size = shpoff + len(shapes)
    info = (bytes((0, 0, 0, 1, n, n, 1, 0))
            + struct.pack("<ii4H6hii", 64 * 4096, 64, 4096, 1024, 0, 1024,
                          -16384, 0, -16384, 16384, 0, 16384, 64 * 4096, 64))
    body = struct.pack("<5I", size, sbcoff, matoff, shpoff, size) + info
    body += node + sbc + mats + shapes
    if len(body) != size:
        raise ValueError("Model offsets do not cover encoded data")
    model = container(b"BMD0", (
        b"MDL0" + struct.pack("<I", size + 48)
        + dictionary("hoenn_flat", struct.pack("<I", 48)) + body,))
    if len(model) > MAX_FIELD_MODEL_BYTES:
        raise ValueError(f"Land model exceeds unchanged field slot: {len(model)}")
    return model
