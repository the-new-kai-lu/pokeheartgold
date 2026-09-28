#!/usr/bin/env python3
"""Warm the three electric menu icons within HGSS's shared icon palette.

Do not edit palette 0: retail Pokemon use it too. Mix its orange (30,18,5)
and yellow (30,30,5) in a 7:5 ratio, averaging (30,23,5), close to the
approved battle gold (30,23,4). Preserve the silhouette and both frames.
Read the pre-correction source from the recorded commit for repeatability.
"""
import hashlib
import io
import json
import subprocess
from pathlib import Path
from PIL import Image, ImageOps

ROOT = Path(__file__).resolve().parents[2]
SOURCE_COMMIT = "227b8d954"

def main():
    manifest_path = ROOT / "files/fakemon/assets.json"
    manifest = json.loads(manifest_path.read_text())
    for key in ("voltuff", "surguenon", "raijinque"):
        folder = ROOT / "files/fakemon" / key
        source = subprocess.check_output(["git", "show", f"{SOURCE_COMMIT}:files/fakemon/{key}/source/icon.png"], cwd=ROOT)
        image = Image.open(io.BytesIO(source))
        assert image.mode == "P" and image.size == (32, 64)
        pixels = image.load()
        for y in range(64):
            for x in range(32):
                if pixels[x, y] == 5 and (x + 3 * (y % 32)) % 12 < 7:
                    pixels[x, y] = 7
        # Party/box icons have their own graphics, separate from battle art.
        # Surguenon's original icon faces right; match HGSS's left-facing icons.
        if key == "surguenon":
            image = ImageOps.mirror(image)  # Vertical frame order is unchanged.
            pixels = image.load()
        image.save(folder / "source/icon.png", transparency=0)
        path = folder / "icon.bin"
        native = bytearray(path.read_bytes())
        assert native[:4] == b"RGCN" and len(native) == 1072
        tiled = []
        for ty in range(0, 64, 8):
            for tx in range(0, 32, 8):
                for y in range(8):
                    for x in range(0, 8, 2):
                        tiled.append(pixels[tx + x, ty + y] | pixels[tx + x + 1, ty + y] << 4)
        native[48:] = bytes(tiled)
        path.write_bytes(native)
        for row in manifest["archives"]["a/0/2/0"]:
            if row["file"] == f"{key}/icon.bin":
                row["sha256"] = hashlib.sha256(native).hexdigest()
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")

if __name__ == "__main__":
    main()
