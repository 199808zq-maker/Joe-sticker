#!/usr/bin/env python3
"""add_text.py - give a sticker image a caption, sticker style.

Usage:
    python3 scripts/add_text.py input.png output.png --text "hello world" --position top

Params:
    --text       caption; a space splits it into two lines
    --pos        top | bottom (default top); --position works too
    --size       font size in px (default: auto, based on image size and text length)
    --color      text color hex (default #FFFFFF white)
    --outline    outline color hex (default #5B3A29 dark brown, sticker style)
    --no-outline draw text without outline
"""

import argparse
import os
import sys
from PIL import Image, ImageDraw, ImageFont

FONT_CANDIDATES = [
    "C:/Windows/Fonts/msyhbd.ttc",   # Microsoft YaHei Bold
    "C:/Windows/Fonts/msyh.ttc",     # Microsoft YaHei
    "C:/Windows/Fonts/simhei.ttf",   # SimHei
    "C:/Windows/Fonts/simsun.ttc",   # SimSun
    "/System/Library/Fonts/PingFang.ttc",
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc",
]


def find_font(size):
    for path in FONT_CANDIDATES:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                continue
    return ImageFont.load_default()


def auto_size(img_w, lines):
    longest = max(len(line) for line in lines)
    # aim for the longest line to take ~80% of image width
    size = int(img_w * 0.8 / max(longest, 1))
    return max(20, min(size, int(img_w * 0.28)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("input")
    ap.add_argument("output")
    ap.add_argument("--text", required=True)
    ap.add_argument("--pos", "--position", dest="pos", default="top",
                    choices=["top", "bottom"])
    ap.add_argument("--size", type=int, default=0)
    ap.add_argument("--color", default="#FFFFFF")
    ap.add_argument("--outline", default="#5B3A29")
    ap.add_argument("--no-outline", action="store_true")
    args = ap.parse_args()

    img = Image.open(args.input).convert("RGBA")
    w, h = img.size

    lines = args.text.split(" ")
    font_size = args.size or auto_size(w, lines)
    font = find_font(font_size)
    stroke_w = 0 if args.no_outline else max(2, font_size // 12)

    draw = ImageDraw.Draw(img)
    line_h = font_size * 1.25
    total_h = line_h * len(lines)
    margin = h * 0.04
    y0 = margin if args.pos == "top" else h - total_h - margin

    for i, line in enumerate(lines):
        bbox = draw.textbbox((0, 0), line, font=font,
                             stroke_width=stroke_w)
        tw = bbox[2] - bbox[0]
        x = (w - tw) / 2
        y = y0 + i * line_h
        draw.text((x, y), line, font=font, fill=args.color,
                  stroke_width=stroke_w, stroke_fill=args.outline)

    img.save(args.output)
    print("ok: %s (%dx%d, font %d, pos %s)" % (args.output, w, h, font_size, args.pos))


if __name__ == "__main__":
    sys.exit(main())
