#!/usr/bin/env python3
"""Apply reviewed native RGB555 palette corrections without changing pixel indices.

The JSON retains both old and new palette values so this is idempotent, auditable,
and rejects unexpected source palettes. Native palette writes never touch NDS
texture data. Requires Pillow for PNG bookkeeping; ndspy for diagnostic rendering.
The asset manifest is deliberately left to the caller after all graphic edits.
"""
import argparse
import json
import struct
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PLAN = ROOT / "files/fakemon/palette-corrections.json"


def pack_palette(colors):
    assert len(colors) == 16
    assert all(len(c) == 3 and all(0 <= v <= 31 for v in c) for c in colors)
    return struct.pack("<16H", *(r | (g << 5) | (b << 10) for r, g, b in colors))


def expand_palette(colors):
    # Same floor(255*v/31) expansion as the imported JASC and indexed PNG data.
    return [v * 255 // 31 for color in colors for v in color]


def patch_png_palette(path, before, after, superseded=()):
    from PIL import Image
    with Image.open(path) as source:
        assert source.mode == "P", path
        image = source.copy()
    old_indices = image.tobytes()
    palette = image.getpalette()
    # Quantize the embedded RGB888 data back to hardware values when validating.
    actual = [round(v * 31 / 255) for v in palette[:48]]
    assert actual in [[v for c in pal for v in c] for pal in [before, after, *superseded]], path
    updated = expand_palette(after)
    if palette[:48] != updated:
        palette[:48] = updated
        image.putpalette(palette)
        image.save(path, transparency=0)
    with Image.open(path) as check:
        assert check.tobytes() == old_indices, (path, "pixel index mutation")
        assert check.getpalette()[:48] == updated, path


def patch_follower(data, rows):
    """Patch only the two trailing NSBTX palette blocks, preserving every texture byte."""
    assert data[:4] == b"BTX0", "expected follower texture archive"
    result = bytearray(data)
    for i, row in enumerate(rows):
        old = pack_palette(row["before_rgb555"])
        new = pack_palette(row["after_rgb555"])
        offset = len(data) - 64 + 32 * i
        accepted = [old, new, *(pack_palette(p) for p in row.get("superseded_rgb555", []))]
        assert data[offset:offset + 32] in accepted, "unexpected follower palette layout"
        result[offset:offset + 32] = new
    assert bytes(result[:-64]) == data[:-64]
    return bytes(result)


def apply(group, components):
    changes = []
    for key in group["species"]:
        folder = ROOT / "files/fakemon" / key
        rows = group["palettes"]
        for i, row in enumerate(rows):
            before, after = row["before_rgb555"], row["after_rgb555"]
            assert before[0] == after[0], "transparent slot must remain unchanged"
            assert len({tuple(c) for c in after}) == 16, "retain distinct palette indices"
            old, new = pack_palette(before), pack_palette(after)
            accepted = [old, new, *(pack_palette(p) for p in row.get("superseded_rgb555", []))]
            if "battle" in components:
                path = folder / f"battle-{4 + i}.bin"
                data = path.read_bytes()
                assert len(data) == 72 and data[:4] == b"RLCN" and data[40:] in accepted, path
                result = data[:40] + new
                assert result[:40] == data[:40]
                path.write_bytes(result)
                changes.append(str(path.relative_to(ROOT)))
            if "jasc" in components:
                path = folder / "source" / f"overworld-tsure_poke{i}.pal"
                lines = path.read_text().splitlines()
                actual = [[round(int(v) * 31 / 255) for v in line.split()] for line in lines[3:]]
                assert lines[:3] == ["JASC-PAL", "0100", "16"] and actual in [before, after, *row.get("superseded_rgb555", [])], path
                values = expand_palette(after)
                text = "JASC-PAL\r\n0100\r\n16\r\n" + "".join("%d %d %d\r\n" % tuple(values[j:j + 3]) for j in range(0, 48, 3))
                path.write_bytes(text.encode("ascii"))
                changes.append(str(path.relative_to(ROOT)))
        if "png" in components:
            for path in sorted((folder / "source").glob("*/*.png")) + [folder / "source/overworld.png"]:
                # hg-engine source convention stores shiny colors on back.png.
                row = rows[1 if path.name == "back.png" else 0]
                patch_png_palette(path, row["before_rgb555"], row["after_rgb555"], row.get("superseded_rgb555", []))
                changes.append(str(path.relative_to(ROOT)))
        if "follower" in components:
            path = folder / "follower.bin"
            path.write_bytes(patch_follower(path.read_bytes(), rows))
            changes.append(str(path.relative_to(ROOT)))
    return changes


def diagnostics(plan, output):
    """Render original native follower indices with each palette for visual review."""
    from PIL import Image, ImageDraw, ImageFont
    from ndspy.texture import NSBTX
    output.mkdir(parents=True, exist_ok=True)
    font_path = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
    font = ImageFont.truetype(font_path, 16)
    keys = [(group, key) for group in plan["groups"] for key in group["species"]]
    sheet = Image.new("RGB", (1120, 72 + len(keys) * 208), "#e9e7df")
    draw = ImageDraw.Draw(sheet)
    draw.text((18, 12), "Native follower palette comparison (same pixel indices)", font=font, fill="black")
    for x, title in [(210, "Normal before"), (410, "Normal after"), (690, "Shiny before"), (890, "Shiny after")]:
        draw.text((x, 44), title, font=font, fill="black")
    measurements = []
    for idx, (group, key) in enumerate(keys):
        y = 74 + idx * 208
        tex = NSBTX((ROOT / "files/fakemon" / key / "follower.bin").read_bytes())
        # First native texture; rendering is data visualization, not sprite editing.
        texture = tex.textures[0][1]
        draw.text((18, y + 16), key.upper(), font=font, fill="black")
        for shiny, row in enumerate(group["palettes"]):
            for after in (False, True):
                colors = row["after_rgb555" if after else "before_rgb555"]
                assert len(texture.data1) == texture.width * texture.height // 2
                indices = [i for value in texture.data1 for i in (value & 15, value >> 4)]
                rendered = [(*colors[i], 0 if i == 0 and texture.isColor0Transparent else 31) for i in indices]
                image = Image.new("RGBA", (texture.width, texture.height))
                image.putdata([(r * 255 // 31, g * 255 // 31, b * 255 // 31, a * 255 // 31) for r, g, b, a in rendered])
                factor = 4 if texture.width == 32 else 2
                image = image.resize((texture.width * factor, texture.height * factor), Image.Resampling.NEAREST)
                x = (210 if not shiny else 690) + (200 if after else 0)
                sheet.paste(image, (x, y + 4), image)
                for j, c in enumerate(colors):
                    cx = x + (j % 8) * 19
                    cy = y + 143 + (j // 8) * 24
                    rgb = tuple(v * 255 // 31 for v in c)
                    draw.rectangle((cx, cy, cx + 17, cy + 17), fill=rgb)
                # Average visible-pixel luma in RGB555 space, native texture pixels weighted.
                pixels = [p for p in rendered if p[3]]
                luma = sum(.2126 * r + .7152 * g + .0722 * b for r, g, b, a in pixels) / len(pixels)
                measurements.append({"species": key, "variant": row["variant"], "palette": "after" if after else "before", "native_frame": tex.textures[0][0], "mean_visible_luma_rgb555": round(luma, 3), "visible_pixels": len(pixels)})
    sheet.save(output / "native-palette-comparison.png")
    (output / "native-palette-measurements.json").write_text(json.dumps(measurements, indent=2) + "\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--components", nargs="+", choices=["battle", "jasc", "png", "follower"], default=[])
    parser.add_argument("--diagnostics", type=Path)
    args = parser.parse_args()
    plan = json.loads(PLAN.read_text())
    if args.diagnostics:
        diagnostics(plan, args.diagnostics)
    changed = []
    for group in plan["groups"]:
        changed += apply(group, args.components)
    print(json.dumps({"palette_files_processed": len(changed), "manifest_update_required": bool(changed)}, indent=2))


if __name__ == "__main__":
    main()
