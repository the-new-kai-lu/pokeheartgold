#!/usr/bin/env python3
"""Extract the pinned Emerald lab into inspectable graphics and semantic cells.

This is a donor resource pack, NOT an HGSS land-data/NSBMD exporter.
No Pillow or donor build toolchain is required.
"""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import subprocess
import zlib


DONOR = "c925b8482d05fb882d6b64e523653cae599e025f"
LAYOUT = "LittlerootTown_ProfessorBirchsLab"


def indexed_png(data):
    """Decode noninterlaced indexed PNGs; preserve indices, not preview colors."""
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError("Not PNG")
    pos, compressed, header = 8, bytearray(), None
    while pos < len(data):
        size = struct.unpack_from(">I", data, pos)[0]
        tag = data[pos + 4:pos + 8]
        payload = data[pos + 8:pos + 8 + size]
        crc = struct.unpack_from(">I", data, pos + 8 + size)[0]
        if zlib.crc32(tag + payload) != crc:
            raise ValueError("PNG CRC mismatch")
        if tag == b"IHDR":
            header = struct.unpack(">IIBBBBB", payload)
        elif tag == b"IDAT":
            compressed.extend(payload)
        elif tag == b"IEND":
            break
        pos += size + 12
    if header is None:
        raise ValueError("Missing PNG header")
    width, height, depth, color, compression, filtering, interlace = header
    if depth not in (4, 8) or color != 3 or compression or filtering or interlace:
        raise ValueError("Only noninterlaced 4/8-bit indexed PNG supported")
    stride = (width * depth + 7) // 8
    raw = zlib.decompress(compressed)
    if len(raw) != height * (stride + 1):
        raise ValueError("PNG decompressed size mismatch")
    previous, pixels = bytearray(stride), []
    for y in range(height):
        offset = y * (stride + 1)
        mode, row = raw[offset], bytearray(raw[offset + 1:offset + 1 + stride])
        if mode > 4:
            raise ValueError("Unknown PNG filter")
        for x in range(stride):
            a, b, c = row[x - 1] if x else 0, previous[x], previous[x - 1] if x else 0
            p = a + b - c
            pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
            predictor = a if pa <= pb and pa <= pc else b if pb <= pc else c
            row[x] = (row[x] + (0, a, b, (a + b) // 2, predictor)[mode]) & 255
        unpacked = list(row) if depth == 8 else [v for byte in row for v in (byte >> 4, byte & 15)]
        if any(v > 15 for v in unpacked[:width]):
            raise ValueError("GBA tile index exceeds 4bpp")
        pixels.extend(unpacked[:width])
        previous = row
    return width, height, pixels


def png_rgba(width, height, pixels):
    def chunk(tag, payload):
        return struct.pack(">I", len(payload)) + tag + payload + struct.pack(">I", zlib.crc32(tag + payload))
    if len(pixels) != width * height * 4:
        raise ValueError("RGBA size mismatch")
    raw = b"".join(b"\0" + pixels[y * width * 4:(y + 1) * width * 4] for y in range(height))
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b""))


def palette(data):
    lines = data.decode("ascii").splitlines()
    if lines[:3] != ["JASC-PAL", "0100", "16"]:
        raise ValueError("Unexpected palette format")
    colors = [tuple(map(int, line.split())) for line in lines[3:]]
    if len(colors) != 16 or any(len(c) != 3 or min(c) < 0 or max(c) > 255 for c in colors):
        raise ValueError("Invalid palette")
    # Emerald's 24-bit palette sources are quantized to BGR555 by the donor build.
    return [tuple((v >> 3) * 255 // 31 for v in c) for c in colors]


def tile_pixel(word, x, y, sheets, palettes):
    tile, pal = word & 1023, word >> 12
    bank, local = (0, tile) if tile < 512 else (1, tile - 512)
    width, height, indices = sheets[bank]
    if width % 8 or height % 8 or local >= width * height // 64:
        raise ValueError("Tile reference outside sheet")
    if word & 1024:
        x = 7 - x
    if word & 2048:
        y = 7 - y
    index = indices[(local // (width // 8) * 8 + y) * width + local % (width // 8) * 8 + x]
    if pal >= len(palettes):
        raise ValueError("Palette reference outside loaded slots")
    return (*palettes[pal][index], 255 if index else 0)


def extract(donor, output, map_name=LAYOUT):
    sources = {}
    if map_name == "OldaleTown":
        revision = subprocess.check_output(
            ["git", "-C", str(donor), "rev-parse", "HEAD"], text=True).strip()
        if revision != DONOR:
            raise ValueError("Oldale donor revision mismatch")

    def read(relative):
        data = (donor / relative).read_bytes()
        if map_name == "OldaleTown":
            # The pinned donor uses CRLF palette checkouts. Compare that exact
            # representation without executing configurable Git content filters.
            pinned = subprocess.check_output(
                ["git", "-C", str(donor), "show", f"{DONOR}:{relative}"])
            if relative.endswith(".pal"):
                pinned = pinned.replace(b"\n", b"\r\n")
            if data != pinned:
                raise ValueError(f"Oldale donor source drift: {relative}")
        sources[relative] = hashlib.sha256(data).hexdigest()
        return data

    contracts = {
        LAYOUT: (13, 13, "gTileset_Building", "gTileset_Lab",
                 "data/tilesets/primary/building", "data/tilesets/secondary/lab"),
        "LittlerootTown": (20, 20, "gTileset_General", "gTileset_Petalburg",
                          "data/tilesets/primary/general", "data/tilesets/secondary/petalburg"),
        "Route101": (20, 20, "gTileset_General", "gTileset_Petalburg",
                     "data/tilesets/primary/general", "data/tilesets/secondary/petalburg"),
        "OldaleTown": (20, 20, "gTileset_General", "gTileset_Petalburg",
                       "data/tilesets/primary/general", "data/tilesets/secondary/petalburg"),
    }
    if map_name not in contracts:
        raise ValueError("Unsupported episode map")
    layouts = json.loads(read("data/layouts/layouts.json"))["layouts"]
    contract = contracts[map_name]
    layout = next(x for x in layouts if x["name"] == map_name + "_Layout")
    if (layout["width"], layout["height"], layout["primary_tileset"], layout["secondary_tileset"]) != (
            *contract[:4],):
        raise ValueError("Donor map contract changed")
    width, height = contract[:2]
    pixel_width, pixel_height = width * 16, height * 16
    roots = list(contract[4:])
    sheets = [indexed_png(read(root + "/tiles.png")) for root in roots]
    metatiles = [read(root + "/metatiles.bin") for root in roots]
    attributes = [read(root + "/metatile_attributes.bin") for root in roots]
    palettes = [palette(read(roots[0 if slot < 6 else 1] + f"/palettes/{slot:02}.pal")) for slot in range(13)]
    blocks = read(layout["blockdata_filepath"])
    border = read(layout["border_filepath"])
    if len(blocks) != width * height * 2 or len(border) != 8:
        raise ValueError("Invalid map block/border length")
    cells, layers = [], [bytearray(pixel_width * pixel_height * 4) for _ in range(3)]
    occluded_unavailable = []
    for cell, (block,) in enumerate(struct.iter_unpack("<H", blocks)):
        tile = block & 1023
        bank, local = (0, tile) if tile < 512 else (1, tile - 512)
        if (local + 1) * 16 > len(metatiles[bank]) or (local + 1) * 2 > len(attributes[bank]):
            raise ValueError("Metatile reference outside tileset")
        words = struct.unpack_from("<8H", metatiles[bank], local * 16)
        attribute = struct.unpack_from("<H", attributes[bank], local * 2)[0]
        layer_type = attribute >> 12
        if layer_type not in (0, 1, 2):
            raise ValueError("Unsupported metatile layer type")
        x, y = cell % width, cell // width
        cells.append(dict(x=x, y=y, raw=block, metatile=tile, collision=(block >> 10) & 3,
                          elevation=block >> 12, attribute=attribute, behavior=attribute & 255,
                          layer_type=layer_type, tile_words=list(words)))
        # Indices are bottom BG3, middle BG2, top BG1 (DrawMetatile).
        destinations = ((1, 2), (0, 1), (0, 2))[layer_type]
        for half in range(2):
            for quadrant in range(4):
                for py in range(8):
                    for px in range(8):
                        try:
                            rgba = tile_pixel(words[half * 4 + quadrant], px, py, sheets, palettes)
                        except ValueError:
                            # Two outdoor source metatiles contain unavailable lower
                            # tiles. Only omit pixels PROVEN fully covered by the
                            # actual upper tile, and disclose that lower-layer hole.
                            if (map_name == LAYOUT or half != 0
                                    or tile_pixel(words[4 + quadrant], px, py, sheets, palettes)[3] != 255):
                                raise
                            reference = dict(x=x, y=y, quadrant=quadrant, word=words[quadrant])
                            if reference not in occluded_unavailable:
                                occluded_unavailable.append(reference)
                            continue
                        dest_x, dest_y = x * 16 + quadrant % 2 * 8 + px, y * 16 + quadrant // 2 * 8 + py
                        offset = (dest_y * pixel_width + dest_x) * 4
                        layers[destinations[half]][offset:offset + 4] = bytes(rgba)
    # Transparent indices expose lower BGs; backdrop is palette slot 0 color 0.
    composite = bytearray(bytes((*palettes[0][0], 255)) * (pixel_width * pixel_height))
    for layer in layers:
        for offset in range(0, len(layer), 4):
            if layer[offset + 3]:
                composite[offset:offset + 4] = layer[offset:offset + 4]
    events = json.loads(read(f"data/maps/{map_name}/map.json"))
    artifacts = {
        "preview.png": png_rgba(pixel_width, pixel_height, composite),
        **{f"bg{3 - i}.png": png_rgba(pixel_width, pixel_height, layer) for i, layer in enumerate(layers)},
        "cells.json": (json.dumps(dict(width=width, height=height, cells=cells,
                                       border=list(struct.unpack("<4H", border))), indent=2) + "\n").encode(),
        "donor-events.json": (json.dumps(events, indent=2) + "\n").encode(),
    }
    if map_name != LAYOUT:
        # This is a coordinate plan, not DS terrain or authored map resources.
        # Origin is donor (0,0), native grid (0,0), world boundary (-256,-256).
        chunks = []
        for cy in range((height + 31) // 32):
            for cx in range((width + 31) // 32):
                chunks.append(dict(matrix_x=cx, matrix_y=cy,
                                   donor_origin=[cx * 32, cy * 32],
                                   valid_size=[min(32, width - cx * 32), min(32, height - cy * 32)],
                                   world_origin=[cx * 512 - 256, cy * 512 - 256]))
        plan = dict(status="coordinate-plan-only", cell_units=16, chunk_cells=32,
                    dimensions=[width, height], matrix_size=[(width + 31) // 32, (height + 31) // 32],
                    chunks=chunks, padding="outside donor bounds; no inferred walkability",
                    connections=events.get("connections"), warps=events.get("warp_events"),
                    animation="Unanimated source tiles.png snapshot; runtime tile/palette updates not applied",
                    occluded_unavailable_lower_tiles=occluded_unavailable,
                    lower_layer_limitation="Unavailable lower pixels omitted ONLY under proven opaque upper pixels")
        artifacts["chunk-plan.json"] = (json.dumps(plan, indent=2) + "\n").encode()
    if map_name == "OldaleTown":
        route = json.loads(read("data/maps/Route101/map.json"))
        scripts = read("data/maps/OldaleTown/scripts.inc").decode()
        route_connection = dict(map="MAP_OLDALE_TOWN", offset=0, direction="up")
        town_connection = dict(map="MAP_ROUTE101", offset=0, direction="down")
        girl = next(event for event in events["object_events"]
                    if event["script"] == "OldaleTown_EventScript_Girl")
        script = ("OldaleTown_EventScript_Girl::\n"
                  "\tmsgbox OldaleTown_Text_SavingMyProgress, MSGBOX_NPC\n\tend\n")
        text = ('OldaleTown_Text_SavingMyProgress:\n'
                '\t.string "I want to take a rest, so I\'m saving my\\n"\n'
                '\t.string "progress.$"\n')
        if (route_connection not in route["connections"] or
                town_connection not in events["connections"] or
                girl["flag"] != "0" or (girl["x"], girl["y"]) != (16, 11) or
                script not in scripts or text not in scripts):
            raise ValueError("Oldale stateless arrival donor anchor changed")
        candidate = dict(
            status="CANDIDATE_PENDING_INDEPENDENT_PARENT_REVIEW",
            native_staging=False, native_play_verified=False,
            additional_save_allocation=0,
            interaction=dict(donor_event=girl, donor_script=script, donor_text=text),
            boundary=dict(route=route_connection, town=town_connection,
                          donor_pairs=[dict(route=[x, 0], oldale=[x, 19])
                                       for x in range(20)],
                          explanation="Zero horizontal offset preserves x. North of Route101 "
                          "row 0 is Oldale row 19; south of Oldale row 19 is Route101 row 0. "
                          "These are donor coordinates, NOT approved walkable DS warp tiles."),
            unresolved=["Native map/header/event/resource IDs and reciprocal warp tiles",
                        "DS terrain/collision and model/archive integration",
                        "Town transition, rival, Mart reward and other interactions not imported",
                        "Independent native-output contract review and runtime verification"])
        artifacts["arrival-candidate.json"] = (
            json.dumps(candidate, indent=2) + "\n").encode()
    # Refuse silently overwriting evidence from a previous extraction.
    output.mkdir(parents=True, exist_ok=False)
    for name, data in artifacts.items():
        (output / name).write_bytes(data)
    manifest = dict(schema=1, expected_donor_revision=DONOR, layout=map_name,
                    status="donor-extraction-only", sources=sources,
                    outputs={name: hashlib.sha256(data).hexdigest() for name, data in artifacts.items()},
                    limitations=["No DS model/collision conversion", "No NPC sprites or animation",
                                 "Donor behavior/collision values are not HGSS terrain attributes"])
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--donor", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--map", choices=[LAYOUT, "LittlerootTown", "Route101", "OldaleTown"], default=LAYOUT)
    args = parser.parse_args()
    try:
        manifest = extract(args.donor, args.output, args.map)
    except (ValueError, OSError, KeyError, struct.error, StopIteration) as error:
        parser.exit(1, f"Lab extraction failed: {error}\n")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()