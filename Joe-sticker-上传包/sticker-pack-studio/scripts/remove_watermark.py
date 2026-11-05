#!/usr/bin/env python3
"""remove_watermark.py - strip the corner "AI生成" watermark from generated images.

The watermark is added by the image-generation service, not by this skill, so the
only reliable fix is post-processing. This script covers the fixed corner mark by
sampling the surrounding clean background and filling the area in; on images with
a transparent background it simply clears the alpha channel there.

Usage:
    python3 scripts/remove_watermark.py <input> [output] [options]
    python3 scripts/remove_watermark.py <input_dir> --outdir <dir> [options]

<input> may be a single image or a directory (batch mode).
In batch mode every supported image inside is processed into --outdir.

Common options:
    --rect X,Y,W,H     explicit region in pixels; overrides corner detection
                       (this is the escape hatch when the watermark sits on hair
                       or another busy area)
    --corner bl|br|tl|tr  which corner holds the mark (default bl, bottom-left)
    --w 0.22           region width as a fraction of image width  (default 0.22)
    --h 0.09           region height as a fraction of image height (default 0.09)
    --pad 0.008        extra padding around the region, as a fraction of the long edge
    --feather 6        edge feathering in px, hides the seam (default 6)
    --sample up|down|left|right  where to sample the fill colour from (default up)
    --color #RRGGBB    force the fill colour instead of sampling
    --outdir DIR       output dir (batch mode)
    --suffix _nw       filename suffix used when no explicit output is given

Examples:
    python3 scripts/remove_watermark.py 表情01.png 01_clean.png
    python3 scripts/remove_watermark.py ./raw --outdir ./clean
    python3 scripts/remove_watermark.py 表情03.png --rect 0,700,260,90
"""

import argparse
import os
import sys
from PIL import Image, ImageDraw, ImageFilter

SUPPORTED = (".png", ".jpg", ".jpeg", ".webp")


def _median_color(pixels):
    """Median RGB of a pixel list - robust against stray strokes/highlights."""
    if not pixels:
        return (255, 255, 255)
    rs = sorted(p[0] for p in pixels)
    gs = sorted(p[1] for p in pixels)
    bs = sorted(p[2] for p in pixels)
    mid = len(rs) // 2
    return (rs[mid], gs[mid], bs[mid])


def _sample_fill(img, rect, direction):
    """Sample a clean background colour from just outside the watermark region."""
    x, y, w, h = rect
    iw, ih = img.size
    band = max(4, h // 2)

    if direction == "up":
        box = (x, max(0, y - band), x + w, y)
    elif direction == "down":
        box = (x, y + h, x + w, min(ih, y + h + band))
    elif direction == "left":
        box = (max(0, x - band), y, x, y + h)
    else:  # right
        box = (x + w, y, min(iw, x + w + band), y + h)

    # degenerate band (region touches the edge) -> fall back to the far corner strip
    if box[2] <= box[0] or box[3] <= box[1]:
        box = (0, 0, min(iw, w), min(ih, band))

    strip = img.crop(box).convert("RGBA")
    pixels = [p for p in strip.getdata() if p[3] > 200]
    return _median_color(pixels)[:3]


def _rect_from_args(img, args):
    if args.rect:
        parts = [int(v.strip()) for v in args.rect.split(",")]
        if len(parts) != 4:
            raise ValueError("--rect expects X,Y,W,H")
        x, y, w, h = parts
    else:
        iw, ih = img.size
        w = int(iw * args.w)
        h = int(ih * args.h)
        pad = int(max(iw, ih) * args.pad)
        if args.corner in ("bl", "tl"):
            x = 0
        else:
            x = iw - w
        if args.corner in ("bl", "br"):
            y = ih - h
        else:
            y = 0
        x = max(0, x - pad)
        y = max(0, y - pad)
        w += pad * 2
        h += pad * 2

    iw, ih = img.size
    w = min(w, iw - x)
    h = min(h, ih - y)
    if w <= 0 or h <= 0:
        raise ValueError("region falls outside the image")
    return (x, y, w, h)


def remove_one(src_path, dst_path, args):
    img = Image.open(src_path).convert("RGBA")
    rect = _rect_from_args(img, args)
    box = (rect[0], rect[1], rect[0] + rect[2], rect[1] + rect[3])

    region = img.crop(box)
    # Transparent background -> the watermark sits on empty space, just clear alpha.
    alphas = list(region.getchannel("A").getdata())
    transparent = (sum(alphas) / max(len(alphas), 1)) < 32

    if args.color:
        hexv = args.color.lstrip("#")
        fill = tuple(int(hexv[i:i + 2], 16) for i in (0, 2, 4))
    else:
        fill = _sample_fill(img, rect, args.sample)

    fill_rgba = (0, 0, 0, 0) if transparent else (fill[0], fill[1], fill[2], 255)

    rw, rh = rect[2], rect[3]
    feather = max(0, min(args.feather, rw // 4, rh // 4))
    mask = Image.new("L", (rw, rh), 0)
    ImageDraw.Draw(mask).rectangle(
        [feather, feather, rw - feather, rh - feather], fill=255
    )
    if feather:
        mask = mask.filter(ImageFilter.GaussianBlur(feather / 2.0))

    patch = Image.new("RGBA", (rw, rh), fill_rgba)
    blended = Image.composite(patch, region, mask)
    img.paste(blended, (rect[0], rect[1]))

    dst_path_dir = os.path.dirname(os.path.abspath(dst_path))
    if dst_path_dir:
        os.makedirs(dst_path_dir, exist_ok=True)
    if dst_path.lower().endswith((".jpg", ".jpeg")):
        img.convert("RGB").save(dst_path, quality=95)
    else:
        img.save(dst_path)
    return rect, transparent


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("input")
    ap.add_argument("output", nargs="?")
    ap.add_argument("--rect", default=None)
    ap.add_argument("--corner", default="bl", choices=["bl", "br", "tl", "tr"])
    ap.add_argument("--w", type=float, default=0.22)
    ap.add_argument("--h", type=float, default=0.09)
    ap.add_argument("--pad", type=float, default=0.008)
    ap.add_argument("--feather", type=int, default=6)
    ap.add_argument("--sample", default="up", choices=["up", "down", "left", "right"])
    ap.add_argument("--color", default=None)
    ap.add_argument("--outdir", default=None)
    ap.add_argument("--suffix", default="_nw")
    args = ap.parse_args()

    if not os.path.exists(args.input):
        print("input not found: %s" % args.input)
        return 1

    jobs = []
    if os.path.isdir(args.input):
        outdir = args.outdir or os.path.join(args.input, "clean")
        names = sorted(f for f in os.listdir(args.input)
                       if f.lower().endswith(SUPPORTED))
        for name in names:
            stem, ext = os.path.splitext(name)
            jobs.append((os.path.join(args.input, name),
                         os.path.join(outdir, stem + args.suffix + ext)))
    else:
        dst = args.output
        if not dst:
            stem, ext = os.path.splitext(args.input)
            dst = stem + args.suffix + ext
        jobs.append((args.input, dst))

    if not jobs:
        print("no images found in %s" % args.input)
        return 1

    for src, dst in jobs:
        rect, transparent = remove_one(src, dst, args)
        note = "transparent bg" if transparent else "filled with background colour"
        print("%s -> %s  region=%s  (%s)"
              % (os.path.basename(src), os.path.basename(dst), rect, note))

    print("done: %d file(s)" % len(jobs))
    return 0


if __name__ == "__main__":
    sys.exit(main())
