#!/usr/bin/env python3
"""export_wechat.py - export sticker images to WeChat specs.

Usage:
    python3 scripts/export_wechat.py <input_dir> <output_dir> [--size 240]

- scales each image proportionally so the long edge equals --size (default 240)
- centers it on a transparent square canvas, keeping the alpha channel
- names outputs sequentially: 表情01.png 表情02.png ...
- GIF: keeps the animation, resizes every frame, warns if a file exceeds 500KB
- pass --size 120 to generate the thumbnail set
"""

import argparse
import os
import sys
from PIL import Image

SUPPORTED = (".png", ".jpg", ".jpeg", ".webp", ".gif")
GIF_LIMIT = 500 * 1024  # 500KB


def fit_canvas(img, size):
    img = img.copy()
    img.thumbnail((size, size), Image.LANCZOS)
    canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    x = (size - img.width) // 2
    y = (size - img.height) // 2
    canvas.paste(img, (x, y), img if img.mode == "RGBA" else None)
    return canvas


def export_static(src, dst, size):
    img = Image.open(src).convert("RGBA")
    fit_canvas(img, size).save(dst, "PNG")


def export_gif(src, dst, size):
    im = Image.open(src)
    frames = []
    durations = []
    try:
        while True:
            frame = im.convert("RGBA")
            frames.append(fit_canvas(frame, size))
            durations.append(im.info.get("duration", 100))
            im.seek(im.tell() + 1)
    except EOFError:
        pass
    frames[0].save(dst, save_all=True, append_images=frames[1:],
                   duration=durations, loop=0, disposal=2, optimize=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("input_dir")
    ap.add_argument("output_dir")
    ap.add_argument("--size", type=int, default=240)
    args = ap.parse_args()

    files = sorted(f for f in os.listdir(args.input_dir)
                   if f.lower().endswith(SUPPORTED))
    if not files:
        print("no images found in %s" % args.input_dir)
        return 1

    os.makedirs(args.output_dir, exist_ok=True)
    for i, name in enumerate(files, 1):
        src = os.path.join(args.input_dir, name)
        is_gif = name.lower().endswith(".gif")
        dst = os.path.join(args.output_dir, "表情%02d.%s" % (i, "gif" if is_gif else "png"))
        if is_gif:
            export_gif(src, dst, args.size)
        else:
            export_static(src, dst, args.size)
        kb = os.path.getsize(dst) / 1024
        warn = ""
        if is_gif and os.path.getsize(dst) > GIF_LIMIT:
            warn = "  WARNING: GIF exceeds 500KB!"
        print("%s -> %s (%.0fKB)%s" % (name, os.path.basename(dst), kb, warn))

    print("done: %d files -> %s (%dx%d)" % (len(files), args.output_dir, args.size, args.size))
    return 0


if __name__ == "__main__":
    sys.exit(main())
