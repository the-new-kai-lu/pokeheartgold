"""Read Emerald's region without running donor code or requiring a donor ROM.

The renderer is a static, flat representation, not an emulation of GBA field
effects. Unsupported gameplay semantics belong in the import coverage report.
"""
from functools import lru_cache
import json
from pathlib import Path
import re
import struct
import subprocess

from extract_emerald_lab import indexed_png, palette


DONOR_COMMIT = "c925b8482d05fb882d6b64e523653cae599e025f"


class Emerald:
    def __init__(self, root, *, verify=True):
        self.root = Path(root).resolve()
        if verify:
            head = subprocess.check_output(
                ["git", "-C", str(self.root), "rev-parse", "HEAD"], text=True).strip()
            if head != DONOR_COMMIT:
                raise ValueError("Use the selected Emerald donor revision")
            # One bounded source-cleanliness check, not thousands of git-show calls.
            subprocess.run(["git", "-C", str(self.root), "diff", "--quiet", "HEAD",
                            "--", "data", "src", "include"], check=True)
        groups = self.json("data/maps/map_groups.json")
        self.maps = {}
        for group in groups["group_order"]:
            for name in groups[group]:
                record = self.json(f"data/maps/{name}/map.json")
                if record["id"] in self.maps:
                    raise ValueError("Duplicate donor map ID")
                self.maps[record["id"]] = dict(record, name=name, group=group)
        self.layouts = {row["id"]: row for row in
                        self.json("data/layouts/layouts.json")["layouts"]}
        self.headers = {}
        for name, body in re.findall(
                r"const struct Tileset (\w+)\s*=\s*\{(.*?)\};",
                self.text("src/data/tilesets/headers.h"), re.S):
            self.headers[name] = dict(re.findall(r"\.(\w+)\s*=\s*(\w+)", body))
        gfx = (self.text("src/graphics.c") + "\n" +
               self.text("src/data/tilesets/graphics.h"))
        self.sheets = dict(re.findall(
            r"const u32 (\w+)\[\]\s*=\s*INCGFX_U32\(\"([^\"]+)\"", gfx))
        self.palettes = {
            name: re.findall(r'INCGFX_U16\("([^"]+)"', body)
            for name, body in re.findall(
                r"const u16 (\w+)\[\]\[16\]\s*=\s*\{(.*?)\};", gfx, re.S)
        }
        self.tile_files = dict(re.findall(
            r'const u16 (\w+)\[\]\s*=\s*INCBIN_U16\("([^"]+)"',
            self.text("src/data/tilesets/metatiles.h")))
        self.occluded_missing = set()

    @lru_cache(maxsize=None)
    def read(self, relative):
        path = (self.root / relative).resolve()
        if not path.is_relative_to(self.root):
            raise ValueError("Donor source escapes checkout")
        return path.read_bytes()

    def text(self, relative):
        return self.read(relative).decode()

    def json(self, relative):
        return json.loads(self.read(relative))

    @lru_cache(maxsize=None)
    def tileset(self, name):
        header = self.headers[name]
        sheet = indexed_png(self.read(self.sheets[header["tiles"]]))
        paths = self.palettes[header["palettes"]]
        if len(paths) != 16:
            raise ValueError(f"Expected 16 source palettes: {name}")
        colors = [[sum(round(c[i] * 31 / 255) << (i * 5) for i in range(3))
                   for c in palette(self.read(path))] for path in paths]
        tiles = self.read(self.tile_files[header["metatiles"]])
        attributes = self.read(self.tile_files[header["metatileAttributes"]])
        if len(tiles) % 16 or len(attributes) * 8 != len(tiles):
            raise ValueError(f"Invalid metatile/attribute lengths: {name}")
        return sheet, colors, tiles, attributes

    @lru_cache(maxsize=None)
    def metatile(self, primary, secondary, tile):
        """Composite one exact 16x16 BGR555 tile; no lossy color quantization."""
        banks = (self.tileset(primary), self.tileset(secondary))
        bank, local = (0, tile) if tile < 512 else (1, tile - 512)
        if local * 16 + 16 > len(banks[bank][2]):
            raise ValueError(f"Missing metatile {primary}/{secondary}/{tile}")
        words = struct.unpack_from("<8H", banks[bank][2], local * 16)
        attribute = struct.unpack_from("<H", banks[bank][3], local * 2)[0]
        layer = attribute >> 12
        if layer not in (0, 1, 2):
            raise ValueError(f"Unsupported metatile layer {layer}")
        palettes = banks[0][1][:6] + banks[1][1][6:13]

        def pixel(word, x, y):
            number, slot = word & 1023, word >> 12
            which, index = (0, number) if number < 512 else (1, number - 512)
            width, height, pixels = banks[which][0]
            if slot >= len(palettes) or index >= width * height // 64:
                return None
            x = 7 - x if word & 1024 else x
            y = 7 - y if word & 2048 else y
            value = pixels[(index // (width // 8) * 8 + y) * width +
                           index % (width // 8) * 8 + x]
            return palettes[slot][value], value != 0

        result = []
        for y in range(16):
            for x in range(16):
                q = (y // 8) * 2 + x // 8
                lower = pixel(words[q], x % 8, y % 8)
                upper = pixel(words[4 + q], x % 8, y % 8)
                if upper is None:
                    raise ValueError(f"Visible missing upper tile: {primary}/{secondary}/{tile}")
                if lower is None:
                    if not upper[1]:
                        raise ValueError(f"Visible missing lower tile: {primary}/{secondary}/{tile}")
                    self.occluded_missing.add((primary, secondary, tile))
                color = palettes[0][0]
                if lower is not None and lower[1]:
                    color = lower[0]
                if upper[1]:
                    color = upper[0]
                result.append(color)
        return tuple(result), attribute

    @lru_cache(maxsize=None)
    def layout(self, layout_id):
        layout = self.layouts[layout_id]
        width, height = layout["width"], layout["height"]
        blocks = self.read(layout["blockdata_filepath"])
        border = self.read(layout["border_filepath"])
        if len(blocks) != width * height * 2 or len(border) != 8:
            raise ValueError(f"Invalid layout size: {layout_id}")
        blocks = tuple(v[0] for v in struct.iter_unpack("<H", blocks))
        border = tuple(v[0] for v in struct.iter_unpack("<H", border))
        tiles = {tile: self.metatile(layout["primary_tileset"], layout["secondary_tileset"], tile)
                 for tile in sorted({b & 1023 for b in blocks + border})}
        return dict(layout, blocks=blocks, border=border, tiles=tiles)


# Explicit correspondences only. Flat decorative floor is not collision.
# Water, bridges, dive, currents, cycling puzzles, ash and dynamic floors are
# deliberately not approximated as ordinary walkable ground.
GROUND = frozenset((0x00, 0x04, 0x05, 0x07, 0x08, 0x0A, 0x0B, 0x16,
                    0x17, 0x21, 0x25, 0x28))
NATIVE_BEHAVIOR = {0x02: 2, 0x03: 3, 0x08: 8, 0x0B: 8, 0x16: 22,
                   0x17: 23, 0x21: 33, 0x38: 56, 0x39: 57,
                   0x3A: 58, 0x3B: 59}


def terrain_word(block, attribute):
    collision, behavior = (block >> 10) & 3, attribute & 255
    if behavior in GROUND or behavior in NATIVE_BEHAVIOR:
        # Collision and behavior are independent. In particular Emerald's
        # cardinal ledges have collision=1: discarding their low behavior byte
        # turns every imported ledge into an ordinary impassable wall.
        return (0x8000 if collision else 0) | NATIVE_BEHAVIOR.get(behavior, 0), None
    if collision:
        return 0x8000, None
    return 0x8000, behavior


def split_chunks(width, height):
    if not (0 < width <= 255 and 0 < height <= 255):
        raise ValueError("Donor dimensions outside supported field coordinates")
    return [(x, y) for y in range((height + 31) // 32)
            for x in range((width + 31) // 32)]
