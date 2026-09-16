#!/usr/bin/env python3
"""Build the home-page carousel images from the originals in carousel/.

Usage:
    python3 tools/make_carousel.py

For every photo in carousel/ (jpg, jpeg, png, webp) this writes two files to
assets/img/carousel/:

    NN.jpg        the slide, at most MAX_EDGE px on its long edge
    NN-thumb.jpg  a 3:2 centre-cropped thumbnail for the preview strip

NN counts up from 01 in shooting order (EXIF date, falling back to the file
name), and the script prints that order so the <li> list in
src/pages/index.html can be kept in step. The originals are never modified.
Requires Pillow:  python3 -m pip install pillow
"""
import pathlib
import sys

try:
    from PIL import Image, ImageOps
except ImportError:  # pragma: no cover
    sys.exit("Pillow is required: python3 -m pip install pillow")

ROOT = pathlib.Path(__file__).resolve().parent.parent
SRC = ROOT / "carousel"
OUT = ROOT / "assets" / "img" / "carousel"
MAX_EDGE = 1600          # slide: longest side in px
THUMB = (300, 200)       # thumbnail: fixed 3:2 crop
QUALITY = 82
EXTS = {".jpg", ".jpeg", ".png", ".webp"}


def shot_time(path):
    """EXIF DateTimeOriginal (or DateTime) as a sortable string, else ''."""
    try:
        exif = Image.open(path).getexif()
    except Exception:
        return ""
    ifd = exif.get_ifd(0x8769) if hasattr(exif, "get_ifd") else {}
    return str(ifd.get(36867) or exif.get(306) or "")


def main():
    photos = sorted((p for p in SRC.iterdir() if p.suffix.lower() in EXTS),
                    key=lambda p: (shot_time(p), p.name.lower()))
    if not photos:
        sys.exit(f"no photos found in {SRC}")
    OUT.mkdir(parents=True, exist_ok=True)
    for old in OUT.glob("*.jpg"):
        old.unlink()
    for n, path in enumerate(photos, 1):
        im = ImageOps.exif_transpose(Image.open(path))
        if im.mode not in ("RGB", "L"):
            im = im.convert("RGB")
        w, h = im.size
        slide = im.copy()
        slide.thumbnail((MAX_EDGE, MAX_EDGE), Image.LANCZOS)
        slide.save(OUT / f"{n:02d}.jpg", "JPEG", quality=QUALITY, optimize=True, progressive=True)
        thumb = ImageOps.fit(im, THUMB, Image.LANCZOS, centering=(0.5, 0.4))
        thumb.save(OUT / f"{n:02d}-thumb.jpg", "JPEG", quality=78, optimize=True)
        orient = "landscape" if w > h else "portrait" if h > w else "square"
        print(f"{n:02d}.jpg  <- {path.name}  ({w}x{h} {orient}, shot {shot_time(path) or 'unknown'})")
    print(f"{len(photos)} photos written to {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
