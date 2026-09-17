#!/usr/bin/env python3
"""Generate the brand images: favicon, touch icon, logo and link-preview images.

Usage:
    python3 tools/make_brand.py

Writes
    assets/img/favicon.svg           black tile with a Cormorant Garamond "W"
    assets/img/favicon-32.png        PNG fallback for browsers without SVG icons
    assets/img/apple-touch-icon.png  180x180 home-screen icon
    assets/img/logo.png              512x512 wordmark tile (the logo in structured data)
    assets/img/og/<page>.jpg         1200x630 link preview per page: the page's
                                     ``hero:`` photo from src/pages/ with the wordmark

The fonts (Cormorant Garamond and Jost, both under the SIL Open Font License)
are downloaded once from the Google Fonts repository into tools/.fonts/, which
git ignores. Requires Pillow and fontTools:
    python3 -m pip install pillow fonttools
"""
import pathlib
import re
import sys
import urllib.request

try:
    from PIL import Image, ImageDraw, ImageFont, ImageOps
except ImportError:  # pragma: no cover
    sys.exit("Pillow is required: python3 -m pip install pillow")

ROOT = pathlib.Path(__file__).resolve().parent.parent
IMG = ROOT / "assets" / "img"
OG_DIR = IMG / "og"
PAGES = ROOT / "src" / "pages"
FONT_DIR = ROOT / "tools" / ".fonts"
FONTS = {
    "CormorantGaramond[wght].ttf": "https://raw.githubusercontent.com/google/fonts/main/ofl/cormorantgaramond/CormorantGaramond%5Bwght%5D.ttf",
    "Jost[wght].ttf": "https://raw.githubusercontent.com/google/fonts/main/ofl/jost/Jost%5Bwght%5D.ttf",
}
DISPLAY, BODY = "CormorantGaramond[wght].ttf", "Jost[wght].ttf"
BLACK, WHITE = (0, 0, 0), (255, 255, 255)
CAPTION, GREY, HAIRLINE = (175, 194, 216), (152, 152, 152), (71, 71, 71)   # #afc2d8 #989898 #474747
WORDMARK_TRACK = 0.42   # em, the letter-spacing of .site-title in site.css
FRONT_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*\n", re.S)


def fetch_fonts():
    FONT_DIR.mkdir(exist_ok=True)
    for name, url in FONTS.items():
        path = FONT_DIR / name
        if path.exists():
            continue
        print("downloading", name)
        try:
            urllib.request.urlretrieve(url, path)
        except OSError as err:
            sys.exit(f"could not download {name} ({err}); save it to {path} by hand from {url}")


def font(name, size, weight):
    fnt = ImageFont.truetype(str(FONT_DIR / name), size)
    try:
        fnt.set_variation_by_axes([weight])
    except (OSError, AttributeError):  # a static font, or a Pillow without variation support
        pass
    return fnt


def tracked_width(fnt, text, track):
    return sum(fnt.getlength(ch) for ch in text) + track * (len(text) - 1)


def draw_tracked(draw, xy, text, fnt, fill, track):
    """Draw text letter by letter with extra tracking; xy is the left end of the baseline."""
    x, y = xy
    for ch in text:
        draw.text((x, y), ch, font=fnt, fill=fill, anchor="ls")
        x += fnt.getlength(ch) + track


def wordmark(draw, x, baseline, size, fill=WHITE):
    fnt = font(DISPLAY, size, 500)
    draw_tracked(draw, (x, baseline), "WUREC", fnt, fill, WORDMARK_TRACK * size)


def w_tile(size, glyph_size, border):
    """A black square with a centred white W."""
    im = Image.new("RGB", (size, size), BLACK)
    draw = ImageDraw.Draw(im)
    if border:
        draw.rectangle([0, 0, size - 1, size - 1], outline=HAIRLINE, width=max(1, size // 64))
    fnt = font(DISPLAY, glyph_size, 500)
    x0, y0, x1, y1 = fnt.getbbox("W", anchor="ls")
    draw.text(((size - (x1 - x0)) / 2 - x0, (size - (y1 - y0)) / 2 - y0), "W", font=fnt, fill=WHITE, anchor="ls")
    return im


def favicon_svg():
    """The same W as a vector path, so the SVG favicon needs no web font."""
    try:
        from fontTools.pens.boundsPen import BoundsPen
        from fontTools.pens.svgPathPen import SVGPathPen
        from fontTools.pens.transformPen import TransformPen
        from fontTools.ttLib import TTFont
        from fontTools.varLib.instancer import instantiateVariableFont
    except ImportError:
        print("fontTools is not installed, so favicon.svg was left as it is")
        return
    tt = TTFont(FONT_DIR / DISPLAY)
    if "fvar" in tt:
        tt = instantiateVariableFont(tt, {"wght": 500})
    glyphs = tt.getGlyphSet()
    glyph = glyphs[tt.getBestCmap()[ord("W")]]
    bounds = BoundsPen(glyphs)
    glyph.draw(bounds)
    xmin, ymin, xmax, ymax = bounds.bounds
    box, glyph_height = 64, 34
    scale = glyph_height / (ymax - ymin)
    tx = (box - (xmax - xmin) * scale) / 2 - xmin * scale
    ty = box / 2 + (ymin + ymax) / 2 * scale
    pen = SVGPathPen(glyphs, ntos=lambda v: f"{v:.2f}".rstrip("0").rstrip("."))
    glyph.draw(TransformPen(pen, (scale, 0, 0, -scale, tx, ty)))
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {box} {box}">'
           f'<rect width="{box}" height="{box}" rx="12" fill="#000000"/>'
           f'<rect x="0.5" y="0.5" width="{box - 1}" height="{box - 1}" rx="11.5" fill="none" stroke="#474747"/>'
           f'<path d="{pen.getCommands()}" fill="#ffffff"/></svg>\n')
    (IMG / "favicon.svg").write_text(svg, encoding="utf-8")
    print("wrote assets/img/favicon.svg")


def logo():
    size, margin = 512, 60
    im = Image.new("RGB", (size, size), BLACK)
    draw = ImageDraw.Draw(im)
    probe = font(DISPLAY, 100, 500)
    fs = int(100 * (size - 2 * margin) / tracked_width(probe, "WUREC", WORDMARK_TRACK * 100))
    fnt = font(DISPLAY, fs, 500)
    track = WORDMARK_TRACK * fs
    x0, y0, x1, y1 = fnt.getbbox("WUREC", anchor="ls")
    x = (size - tracked_width(fnt, "WUREC", track)) / 2 - x0
    draw_tracked(draw, (x, (size - (y1 - y0)) / 2 - y0), "WUREC", fnt, WHITE, track)
    im.save(IMG / "logo.png", optimize=True)
    print("wrote assets/img/logo.png")


def og_image(hero, out):
    width, height = 1200, 630
    im = ImageOps.exif_transpose(Image.open(hero)).convert("RGB")
    im = ImageOps.fit(im, (width, height), Image.LANCZOS, centering=(0.5, 0.4))
    black = Image.new("RGB", (width, height), BLACK)
    im = Image.blend(im, black, 0.15)
    mask = Image.new("L", (1, height))
    for y in range(height):
        t = max(0.0, (y - 120) / (height - 120))
        mask.putpixel((0, y), int(240 * t ** 1.1))
    im = Image.composite(black, im, mask.resize((width, height)))
    draw = ImageDraw.Draw(im)
    x = 84
    draw.rectangle([x, 402, x + 72, 402], fill=WHITE)
    wordmark(draw, x, 500, 88)
    sub = font(BODY, 20, 400)
    draw_tracked(draw, (x, 548), "WHARTON UNDERGRADUATE REAL ESTATE CLUB", sub, CAPTION, 0.3 * 20)
    draw_tracked(draw, (x, 582), "THE WHARTON SCHOOL · UNIVERSITY OF PENNSYLVANIA", sub, GREY, 0.3 * 20)
    im.save(out, "JPEG", quality=85, optimize=True, progressive=True)


def pages():
    """(og name, hero path) for every page with a hero photo."""
    for path in sorted(PAGES.glob("*.html")):
        match = FRONT_RE.match(path.read_text(encoding="utf-8"))
        meta = {}
        for line in match.group(1).splitlines():
            key, _, value = line.partition(":")
            meta[key.strip()] = value.strip()
        if meta.get("hero") and not meta.get("out"):
            yield meta.get("slug", "").strip("/").replace("/", "-") or "home", ROOT / meta["hero"]


def main():
    fetch_fonts()
    favicon_svg()
    w_tile(32, 22, border=True).save(IMG / "favicon-32.png", optimize=True)
    w_tile(180, 118, border=False).save(IMG / "apple-touch-icon.png", optimize=True)
    print("wrote assets/img/favicon-32.png and apple-touch-icon.png")
    logo()
    OG_DIR.mkdir(parents=True, exist_ok=True)
    for name, hero in pages():
        og_image(hero, OG_DIR / f"{name}.jpg")
        print(f"wrote assets/img/og/{name}.jpg  <- {hero.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
