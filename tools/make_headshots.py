#!/usr/bin/env python3
"""Make the Executive Board headshots in exec-board/pictures/.

Usage:
    python3 tools/make_headshots.py SOURCE_DIR [--size 512] [--quality 85] [--dry-run]

Reads every .png / .jpg / .jpeg / .webp in SOURCE_DIR, trims any flat-coloured
frame along the edges (the source portraits carry a thin blue border on the
left and right), centre-crops to a square, resizes to SIZE x SIZE and writes
<same name>.webp into exec-board/pictures/. Needs Pillow:

    python3 -m pip install pillow

tools/sync_board.py uses the same crop (``headshot()``) on the photos in the
club's Google Drive folder, so this script is only needed for local portraits.

The original PNGs are not kept in the working tree; they are in git history
(commit 0ef33a2, exec-board/pictures/*.png). To re-run on them:

    git archive 0ef33a2 exec-board/pictures | tar -x -C /tmp/headshots
    python3 tools/make_headshots.py /tmp/headshots/exec-board/pictures
"""
import argparse
import pathlib
import sys

try:
    from PIL import Image, ImageStat
except ImportError:  # pragma: no cover
    sys.exit("Pillow is required: python3 -m pip install pillow")

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "exec-board" / "pictures"
SOURCES = {".png", ".jpg", ".jpeg", ".webp"}

# A frame is a run of edge rows/columns that are (a) almost one colour and
# (b) the same colour as the outermost row/column. It is never wider than
# MAX_FRAME of the image, so a flat studio backdrop can only lose a sliver.
MAX_FRAME = 0.04
FLAT_STDDEV = 10
COLOUR_TOLERANCE = 24
SAFETY_MARGIN = 0.01  # extra trim so no anti-aliased edge of the frame survives


def edge_line(img, side, i):
    w, h = img.size
    if side == "left":
        box = (i, 0, i + 1, h)
    elif side == "right":
        box = (w - 1 - i, 0, w - i, h)
    elif side == "top":
        box = (0, i, w, i + 1)
    else:
        box = (0, h - 1 - i, w, h - i)
    return ImageStat.Stat(img.crop(box))


def frame_width(img, side):
    """Number of flat, edge-coloured rows/columns on `side`."""
    w, h = img.size
    limit = int((w if side in ("left", "right") else h) * MAX_FRAME)
    edge = edge_line(img, side, 0).mean
    n = 0
    for i in range(limit):
        stat = edge_line(img, side, i)
        if max(stat.stddev) > FLAT_STDDEV:
            break
        if max(abs(a - b) for a, b in zip(stat.mean, edge)) > COLOUR_TOLERANCE:
            break
        n += 1
    return n


def headshot(source, size=512):
    """Open a portrait (path or file object), trim its frame and centre-crop it
    to a size x size square. Returns (image, note) where note describes the crop."""
    img = Image.open(source)
    img.load()
    img = img.convert("RGB")
    w, h = img.size
    frame = {side: frame_width(img, side) for side in ("left", "right", "top", "bottom")}
    margin = max(2, round(w * SAFETY_MARGIN))
    trim = {side: (n + margin if n else 0) for side, n in frame.items()}
    img = img.crop((trim["left"], trim["top"], w - trim["right"], h - trim["bottom"]))
    cw, ch = img.size
    side = min(cw, ch)
    left, top = (cw - side) // 2, (ch - side) // 2
    img = img.crop((left, top, left + side, top + side)).resize((size, size), Image.LANCZOS)
    frame_note = ", ".join(f"{s} {n}px" for s, n in frame.items() if n) or "none"
    return img, f"{w}x{h}, frame: {frame_note}, square {side}px"


def save_webp(img, out, quality=85):
    out.parent.mkdir(parents=True, exist_ok=True)
    img.save(out, "WEBP", quality=quality, method=6)


def process(src, size, quality, dry_run):
    img, note = headshot(src, size)
    out = OUT / (src.stem + ".webp")
    if not dry_run:
        save_webp(img, out, quality)
    print(f"{'would write' if dry_run else 'wrote'} {out.relative_to(ROOT)}  ({note})")


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("source", type=pathlib.Path, help="directory of source portraits")
    parser.add_argument("--size", type=int, default=512, help="output width/height in px (default 512)")
    parser.add_argument("--quality", type=int, default=85, help="WebP quality 0-100 (default 85)")
    parser.add_argument("--dry-run", action="store_true", help="report the crops without writing files")
    args = parser.parse_args()
    files = sorted(p for p in args.source.iterdir() if p.suffix.lower() in SOURCES)
    if not files:
        sys.exit(f"no images found in {args.source}")
    OUT.mkdir(parents=True, exist_ok=True)
    for src in files:
        process(src, args.size, args.quality, args.dry_run)
    print(f"{len(files)} headshots {'checked' if args.dry_run else 'written'}")


if __name__ == "__main__":
    main()
