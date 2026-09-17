#!/usr/bin/env python3
"""Resize the club photos dropped into assets/ into web-sized copies.

Usage:
    python3 tools/make_photos.py

Every photo directly inside assets/ (jpg, jpeg, png, webp) is written to
assets/img/photos/<name>.jpg at most MAX_EDGE px on its long edge. The name
comes from the PHOTOS table below (camera file name -> descriptive name); a
photo that is not in the table keeps its own file name. The originals are
never modified, and pages reference the resized copies, e.g.
``{{root}}assets/img/photos/dubai.jpg``.
Requires Pillow:  python3 -m pip install pillow
"""
import pathlib
import sys

try:
    from PIL import Image, ImageOps
except ImportError:  # pragma: no cover
    sys.exit("Pillow is required: python3 -m pip install pillow")

ROOT = pathlib.Path(__file__).resolve().parent.parent
SRC = ROOT / "assets"
OUT = ROOT / "assets" / "img" / "photos"
MAX_EDGE = 1600
QUALITY = 82
EXTS = {".jpg", ".jpeg", ".png", ".webp"}

# Camera file name -> descriptive name used by the pages.
PHOTOS = {
    "1E823248-C4BE-4EFB-9F31-F5B34751B0F5.jpeg": "washington-dc",        # group in front of the White House
    "1F472505-71C1-484C-BF6B-CCE2F30A06A1.jpeg": "boardroom-presentation",  # long table, firm presentation
    "382EF07C-0962-43BE-980D-D8B052E4038B.jpeg": "site-tour",            # hard hats in an apartment under construction
    "3CFE9AF0-FE52-4FE4-B950-DBFBDBBBFFBF.jpeg": "site-model",           # walking through a scale model of a district
    "4E479199-B4FC-4F30-A642-8E515CBB16BB.jpeg": "new-york",             # group around an executive's desk
    "59A336C2-EFBA-48F7-8047-A1D0DCBC65C1.jpeg": "dubai",                # umbrellas above Palm Jumeirah
    "A049E05D-EC14-4521-AF5E-B720C240EBCE.jpeg": "boardroom-group",      # group at a boardroom table, wood ceiling
    "D069021D-479D-4D8E-BDDF-0255CD7D2DFC.jpeg": "lobby-group",          # group in a lobby, wood-panelled wall
    "D2961D94-C611-4D3B-8919-688B54B03608.jpeg": "los-angeles",          # outside a pink soundstage on a studio lot
}


def main():
    photos = sorted(p for p in SRC.iterdir() if p.is_file() and p.suffix.lower() in EXTS)
    if not photos:
        sys.exit(f"no photos found in {SRC}")
    OUT.mkdir(parents=True, exist_ok=True)
    for path in photos:
        name = PHOTOS.get(path.name, path.stem)
        im = ImageOps.exif_transpose(Image.open(path))
        if im.mode not in ("RGB", "L"):
            im = im.convert("RGB")
        w, h = im.size
        im.thumbnail((MAX_EDGE, MAX_EDGE), Image.LANCZOS)
        out = OUT / f"{name}.jpg"
        im.save(out, "JPEG", quality=QUALITY, optimize=True, progressive=True)
        note = "" if path.name in PHOTOS else "  (not in PHOTOS table; add a descriptive name)"
        print(f"{out.relative_to(ROOT)}  <- {path.name}  ({w}x{h} -> {im.size[0]}x{im.size[1]}){note}")
    print(f"{len(photos)} photos written to {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
