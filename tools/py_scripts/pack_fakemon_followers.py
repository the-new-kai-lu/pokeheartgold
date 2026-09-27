#!/usr/bin/env python3
"""Convert reviewed six-column gait sheets into native HGSS follower resources.

Columns: north A/B, south A/B, west A/B. East is a horizontal mirror of west.
Uses shared crop/scale/origin for each A/B pair, preserving the artist's gait.
No runtime registration, canonical resources, palette design, or manifests change.
Default output is a separate staging directory; callers explicitly install files.
"""
import argparse
import hashlib
import json
import struct
from collections import deque
from functools import lru_cache
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageOps

ROOT = Path(__file__).resolve().parents[2]
FAMILIES = {
    "electric": ["voltuff", "surguenon", "raijinque"],
    "varan": ["embernewt", "pyrovaran", "magmalisk", "rimevaran", "fimbulisk"],
    "bird": ["sedgling", "cragaviar", "ragnaroc"],
}
# Native pixel bounds chosen against the corresponding canonical HGSS followers.
BOUNDS = {
    "voltuff": (21, 21), "surguenon": (24, 25), "raijinque": (34, 34),
    "embernewt": (21, 20), "pyrovaran": (26, 25), "magmalisk": (38, 34),
    "rimevaran": (26, 25), "fimbulisk": (38, 34),
    "sedgling": (18, 18), "cragaviar": (26, 26), "ragnaroc": (48, 42),
}
LARGE = {"raijinque", "magmalisk", "fimbulisk", "ragnaroc"}
NAMES = ["tsure_poke.1", "tsure_poke.10", "tsure_poke.11", "tsure_poke.12",
         "tsure_poke.13", "tsure_poke.14", "tsure_poke.15", "tsure_poke.16"]


def btx_layout(data):
    assert data[:4] == b"BTX0" and data[20:24] == b"TEX0", "expected native BTX0"
    tex = 20
    dictionary = tex + struct.unpack_from("<H", data, tex + 14)[0]
    count = data[dictionary + 1]
    assert count == 8, "expected eight follower textures"
    entries = dictionary + 12 + count * 4 + 4
    names = entries + 8 * count
    texture_start = tex + struct.unpack_from("<I", data, tex + 20)[0]
    palette_start = tex + struct.unpack_from("<I", data, tex + 56)[0]
    assert palette_start + 64 == len(data), "expected two native 16-color palettes"
    records = []
    for i in range(count):
        entry = entries + 8 * i
        offset, params = struct.unpack_from("<HH", data, entry)
        width, height = 8 << ((params >> 4) & 7), 8 << ((params >> 7) & 7)
        name = data[names + 16*i:names + 16*(i+1)].split(b"\0")[0].decode("ascii")
        assert name == (NAMES[i] if width == 32 else f"tsure_poke.{i+1}") and (params >> 10) & 7 == 3
        assert width == height and width in (32, 64) and params & (1 << 13)
        start = texture_start + offset * 8
        end = start + width * height // 2
        assert texture_start <= start < end <= palette_start
        records.append((name, width, height, start, end))
    assert len({(r[3], r[4]) for r in records}) == 8
    return records, palette_start


def pack_palette(palette):
    assert len(palette) == 16 and all(len(c) == 3 and all(0 <= v <= 31 for v in c) for c in palette)
    return struct.pack("<16H", *(r | (g << 5) | (b << 10) for r, g, b in palette))


def expand(palette):
    return [v * 255 // 31 for color in palette for v in color]


def palettes_for(key, plan, source_root):
    for group in plan["groups"]:
        if key in group["species"]:
            rows = {row["variant"]: row["after_rgb555"] for row in group["palettes"]}
            return [rows["normal"], rows["shiny"]]
    # Bird colors are deliberately unchanged by the correction plan.
    result = []
    for i in range(2):
        lines = (source_root / key / "source" / f"overworld-tsure_poke{i}.pal").read_text().splitlines()
        assert lines[:3] == ["JASC-PAL", "0100", "16"]
        result.append([[round(int(v) * 31 / 255) for v in line.split()] for line in lines[3:]])
    return result


def isolate_cell(cell, background, alpha_threshold=128):
    """Keep real alpha, or remove only an explicit edge-connected background."""
    cell = cell.convert("RGBA")
    # Hardware has binary transparency. Ignore generation halos before fitting.
    cell.putalpha(cell.getchannel("A").point(lambda value: 255 if value >= alpha_threshold else 0))
    if background is None:
        assert cell.getchannel("A").getextrema()[0] == 0, "RGB sheet requires --background RRGGBB"
        return cell
    pixels = list(cell.get_flattened_data() if hasattr(cell, "get_flattened_data") else cell.getdata())
    w, h = cell.size
    bg = tuple(bytes.fromhex(background.lstrip("#")))
    assert len(bg) == 3
    def is_background(i):
        return pixels[i][3] == 0 or max(abs(pixels[i][c] - bg[c]) for c in range(3)) <= 28
    queue = deque(i for i in set(list(range(w)) + list(range(w*(h-1),w*h)) + list(range(0,w*h,w)) + list(range(w-1,w*h,w))) if is_background(i))
    seen = set(queue)
    while queue:
        i = queue.popleft()
        pixels[i] = pixels[i][:3] + (0,)
        x, y = i % w, i // w
        for j in (i-1 if x else -1, i+1 if x+1<w else -1, i-w if y else -1, i+w if y+1<h else -1):
            if j >= 0 and j not in seen and is_background(j):
                seen.add(j); queue.append(j)
    cell.putdata(pixels)
    return cell


def quantize(image, palette):
    rgb = [tuple(expand([c])) for c in palette]
    @lru_cache(maxsize=None)
    def nearest(r, g, b):
        return min(range(1,16), key=lambda i: (r-rgb[i][0])**2 + (g-rgb[i][1])**2 + (b-rgb[i][2])**2)
    values = [0 if a < 128 else nearest(r,g,b) for r,g,b,a in (image.get_flattened_data() if hasattr(image, "get_flattened_data") else image.getdata())]
    result = Image.new("P", image.size)
    result.putpalette(expand(palette))
    result.putdata(values)
    result.info["transparency"] = 0
    return result


def fit_pair(pair, key, palette, fixed_transform=None):
    """The union crop and common transform prevent independent-frame wobble."""
    assert pair[0].size == pair[1].size
    bounds = ImageChops.lighter(pair[0].getchannel("A"), pair[1].getchannel("A")).getbbox()
    assert bounds, f"empty pose pair for {key}"
    w, h = bounds[2]-bounds[0], bounds[3]-bounds[1]
    max_w, max_h = BOUNDS[key]
    scale = min(max_w/w, max_h/h, 1)
    width, height = max(1,round(w*scale)), max(1,round(h*scale))
    size = 64 if key in LARGE else 32
    origin = ((size-width)//2, size-2-height)
    if fixed_transform is not None:
        bounds = tuple(fixed_transform["source_pair_bbox"])
        width,height = fixed_transform["fitted_size"]
        origin = tuple(fixed_transform["origin"])
        scale = fixed_transform["scale"]
        assert 0 <= bounds[0] < bounds[2] <= pair[0].width and 0 <= bounds[1] < bounds[3] <= pair[0].height
        assert width <= max_w and height <= max_h
    frames = []
    for cell in pair:
        # A frozen reviewed transform must still contain every opaque source pixel.
        opaque = cell.getchannel("A").getbbox()
        assert opaque is not None and all((opaque[0]>=bounds[0],opaque[1]>=bounds[1],opaque[2]<=bounds[2],opaque[3]<=bounds[3])), "pose outside reviewed pair transform"
        fitted = cell.crop(bounds).resize((width,height), Image.Resampling.LANCZOS)
        canvas = Image.new("RGBA", (size,size))
        canvas.paste(fitted, origin)
        frames.append(quantize(canvas,palette))
    return frames, {"source_pair_bbox": bounds, "scale": scale, "origin": origin, "fitted_size": [width,height]}


def pack_btx(original, frames, palettes):
    records, palette_start = btx_layout(original)
    assert len(frames) == 8
    result = bytearray(original)
    changed_regions = []
    for frame, (_,width,height,start,end) in zip(frames,records):
        assert frame.size == (width,height) and frame.mode == "P"
        indices = frame.tobytes()
        assert max(indices) < 16
        packed = bytes(indices[i] | (indices[i+1] << 4) for i in range(0,len(indices),2))
        assert len(packed) == end-start
        result[start:end] = packed
        changed_regions.append((start,end))
        # Independent decode proves source order and 4bpp nibble orientation.
        decoded = bytes(v for b in result[start:end] for v in (b & 15,b >> 4))
        assert decoded == indices
    result[palette_start:] = b"".join(pack_palette(p) for p in palettes)
    changed_regions.append((palette_start,len(result)))
    allowed = set(i for start,end in changed_regions for i in range(start,end))
    assert all(a == b or i in allowed for i,(a,b) in enumerate(zip(original,result))), "BTX metadata changed"
    assert len(result) == len(original)
    return bytes(result)


def save_species(key, frames, palettes, output_root, source_root):
    folder = output_root / key
    (folder / "source").mkdir(parents=True,exist_ok=True)
    size = frames[0].width
    sheet = Image.new("P",(size,size*8))
    sheet.putpalette(expand(palettes[0]))
    for i,frame in enumerate(frames): sheet.paste(frame,(0,size*i))
    sheet.save(folder/"source/overworld.png",transparency=0)
    for i,pal in enumerate(palettes):
        flat = expand(pal)
        text = "JASC-PAL\r\n0100\r\n16\r\n" + "".join("%d %d %d\r\n" % tuple(flat[j:j+3]) for j in range(0,48,3))
        (folder/"source"/f"overworld-tsure_poke{i}.pal").write_bytes(text.encode("ascii"))
    original = (source_root/key/"follower.bin").read_bytes()
    native = pack_btx(original,frames,palettes)
    (folder/"follower.bin").write_bytes(native)
    return hashlib.sha256(native).hexdigest()


def validate_current(source_root):
    """Compare every existing source PNG to its independently decoded native BTX."""
    checked = 0
    for keys in FAMILIES.values():
        for key in keys:
            native = (source_root/key/"follower.bin").read_bytes()
            records,palette_start = btx_layout(native)
            sheet = Image.open(source_root/key/"source/overworld.png")
            assert sheet.mode == "P" and sheet.size == (records[0][1],records[0][2]*8)
            frames = []
            for i,(_,w,h,start,end) in enumerate(records):
                frame = sheet.crop((0,i*h,w,(i+1)*h)); frames.append(frame)
                decoded = bytes(v for b in native[start:end] for v in (b&15,b>>4))
                assert frame.tobytes() == decoded, (key,i,"source/native mismatch")
            palettes = [[(value&31,(value>>5)&31,(value>>10)&31) for value in struct.unpack_from("<16H",native,palette_start+32*i)] for i in range(2)]
            assert pack_btx(native,frames,palettes) == native, (key,"lossless native round trip")
            checked += 8
    return checked


def review_previews(family, keys, output):
    """Diagnostic composites only: native pixels are enlarged with nearest-neighbor."""
    scale, tile, label = 3, 64*3, 110
    row_height = tile+20
    still = Image.new("RGB", (label+tile*8,30+row_height*len(keys)), "#e3e5e7")
    draw = ImageDraw.Draw(still)
    for col,text in enumerate(["North A","North B","South A","South B","West A","West B","East A","East B"]):
        draw.text((label+col*tile+6,8),text,fill="black")
    animation = [Image.new("RGB", (label+tile*4,30+row_height*len(keys)),"#e3e5e7") for _ in range(2)]
    for image in animation:
        d=ImageDraw.Draw(image)
        for col,text in enumerate(["North","South","West","East"]): d.text((label+col*tile+6,8),text,fill="black")
    for row,key in enumerate(keys):
        source = Image.open(output/key/"source/overworld.png").convert("RGBA")
        size=source.width; y=30+row*row_height
        draw.text((3,y+tile//2),key,fill="black")
        for image in animation: ImageDraw.Draw(image).text((3,y+tile//2),key,fill="black")
        for col in range(8):
            frame=source.crop((0,col*size,size,(col+1)*size))
            display=Image.new("RGBA",(64,64))
            display.paste(frame,((64-size)//2,64-size))
            display=display.resize((tile,tile),Image.Resampling.NEAREST)
            x=label+col*tile
            draw.rectangle((x,y,x+tile-1,y+tile-1),fill="#d2d9ce",outline="#9fa79c")
            still.paste(display,(x,y),display)
            animated=animation[col%2];d=ImageDraw.Draw(animated);x=label+(col//2)*tile
            d.rectangle((x,y,x+tile-1,y+tile-1),fill="#d2d9ce",outline="#9fa79c")
            animated.paste(display,(x,y),display)
    still.save(output/f"{family}-preview.png")
    animation[0].save(output/f"{family}-preview.gif",save_all=True,append_images=animation[1:],duration=167,loop=0)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--source-root",type=Path,default=ROOT/"files/fakemon")
    ap.add_argument("--palette-plan",type=Path,default=ROOT/"files/fakemon/palette-corrections.json")
    ap.add_argument("--family",choices=FAMILIES)
    ap.add_argument("--sheet",type=Path)
    ap.add_argument("--output",type=Path)
    ap.add_argument("--layout",type=Path,help="Reviewed JSON half-open crop rectangles and per-cell flip_x flags")
    ap.add_argument("--background",help="Explicit solid RGB background to edge-flood, e.g. FFFFFF; otherwise require alpha")
    ap.add_argument("--check-current",action="store_true")
    args = ap.parse_args()
    if args.check_current:
        print(json.dumps({"native_source_frames_verified":validate_current(args.source_root)}))
        return
    if not args.family or not args.sheet or not args.output: ap.error("--family, --sheet, and --output are required")
    assert args.output.resolve() != args.source_root.resolve(), "stage output separately, review it, then explicitly install"
    plan = json.loads(args.palette_plan.read_text())
    sheet = Image.open(args.sheet).convert("RGBA")
    keys = FAMILIES[args.family]
    digest = hashlib.sha256(args.sheet.read_bytes()).hexdigest()
    layout = json.loads(args.layout.read_text()) if args.layout else None
    spec = layout["families"][args.family] if layout else None
    if spec:
        assert spec["sheet_size"] == list(sheet.size), "layout image dimensions mismatch"
        assert spec.get("sha256",digest) == digest, "layout source digest mismatch"
        assert [r["species"] for r in spec["rows"]] == keys, "layout species order mismatch"
    report = {"family":args.family,"sheet":str(args.sheet),"sheet_sha256":digest,"layout":str(args.layout) if args.layout else None,"external_images":[],"species":[]}
    external_images = {}
    for row,key in enumerate(keys):
        cell_specs = spec["rows"][row]["cells"] if spec else [{"box":[round(i*sheet.width/6),round(row*sheet.height/len(keys)),round((i+1)*sheet.width/6),round((row+1)*sheet.height/len(keys))]} for i in range(6)]
        assert len(cell_specs) == 6, "expected north/south/west A/B cells"
        cells = []
        for cell_spec in cell_specs:
            cell_source = sheet
            if cell_spec.get("source_image"):
                assert args.layout, "external images require explicit layout metadata"
                source_path = (args.layout.parent / cell_spec["source_image"]).resolve()
                if source_path not in external_images:
                    source_digest = hashlib.sha256(source_path.read_bytes()).hexdigest()
                    assert cell_spec.get("source_sha256",source_digest) == source_digest, "external cell source digest mismatch"
                    external_images[source_path] = Image.open(source_path).convert("RGBA")
                    report["external_images"].append({"path":str(source_path),"sha256":source_digest})
                cell_source = external_images[source_path]
            box = cell_spec["box"]
            assert len(box) == 4 and 0 <= box[0] < box[2] <= cell_source.width and 0 <= box[1] < box[3] <= cell_source.height
            cell = cell_source.crop(box)
            if cell_spec.get("flip_x",False): cell = ImageOps.mirror(cell)
            cells.append(cell)
        # A replacement can be registered into an explicitly reviewed source camera.
        isolated_cells = []
        for cell,cell_spec in zip(cells,cell_specs):
            isolated = isolate_cell(cell,args.background,layout.get("alpha_threshold",128) if layout else 128)
            if cell_spec.get("placement"):
                placement = cell_spec["placement"]
                box = placement["fit_box"]
                art = isolated.crop(isolated.getbbox())
                factor = (box[3]-box[1])/art.height if placement.get("mode") == "height" else min((box[2]-box[0])/art.width,(box[3]-box[1])/art.height)
                dimensions = (max(1,round(art.width*factor)),max(1,round(art.height*factor)))
                art = art.resize(dimensions,Image.Resampling.LANCZOS)
                art.putalpha(art.getchannel("A").point(lambda value:255 if value>=128 else 0))
                isolated = Image.new("RGBA",tuple(placement["canvas_size"]))
                origin = (box[0]+((box[2]-box[0])-dimensions[0])//2,box[3]-dimensions[1])
                assert origin[0] >= 0 and origin[1] >= 0 and origin[0]+dimensions[0] <= isolated.width and origin[1]+dimensions[1] <= isolated.height, "registered replacement clips camera"
                isolated.paste(art,origin)
            isolated_cells.append(isolated)
        # Rounding can differ by one pixel for non-divisible image dimensions.
        natural = (max(c.width for c in isolated_cells),max(c.height for c in isolated_cells))
        common = tuple(spec["rows"][row].get("cell_canvas_size",natural)) if spec else natural
        assert common[0] >= natural[0] and common[1] >= natural[1]
        normalized = []
        for isolated in isolated_cells:
            pad = Image.new("RGBA",common); pad.paste(isolated,((common[0]-isolated.width)//2,0)); normalized.append(pad)
        palettes = palettes_for(key,plan,args.source_root)
        frames,transforms = [],[]
        for i in range(0,6,2):
            fixed = spec["rows"][row].get("pair_transforms",{}).get(str(i//2)) if spec else None
            pair,transform = fit_pair(normalized[i:i+2],key,palettes[0],fixed); frames.extend(pair); transforms.append(transform)
        frames.extend([ImageOps.mirror(frame) for frame in frames[4:6]])
        digest = save_species(key,frames,palettes,args.output,args.source_root)
        report["species"].append({"key":key,"bounds":BOUNDS[key],"cells":cell_specs,"transforms":transforms,"native_sha256":digest,"frame_bboxes":[f.convert("RGBA").getbbox() for f in frames]})
    args.output.mkdir(parents=True,exist_ok=True)
    (args.output/f"{args.family}-packing-report.json").write_text(json.dumps(report,indent=2)+"\n")
    review_previews(args.family,keys,args.output)
    print(json.dumps(report,indent=2))


if __name__ == "__main__": main()
