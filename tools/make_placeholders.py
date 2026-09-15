#!/usr/bin/env python3
"""Generate the original placeholder artwork (SVG) used until real photos are
dropped into assets/img/. Re-run with:  python3 tools/make_placeholders.py
"""
import pathlib
import random

OUT = pathlib.Path(__file__).resolve().parent.parent / "assets" / "img"
OUT.mkdir(parents=True, exist_ok=True)


def skyline(width, height, seed, layers, windows=True):
    rnd = random.Random(seed)
    groups = []
    for index, (color, opacity, min_h, max_h, min_w, max_w) in enumerate(layers):
        x = -30
        rects, lights = [], []
        while x < width + 30:
            bw = rnd.randint(min_w, max_w)
            bh = rnd.randint(min_h, max_h)
            y = height - bh
            rects.append(f'<rect x="{x}" y="{y}" width="{bw}" height="{bh + 40}"/>')
            if rnd.random() < 0.35:  # rooftop spire / mechanical box
                sw = max(6, bw // 6)
                rects.append(f'<rect x="{x + bw // 2 - sw // 2}" y="{y - rnd.randint(14, 60)}" width="{sw}" height="70"/>')
            if windows and index == len(layers) - 1:
                cols = max(1, bw // 16)
                rows = max(1, bh // 22)
                for c in range(cols):
                    for r in range(rows):
                        if rnd.random() < 0.28:
                            lights.append(f'<rect x="{x + 6 + c * 16}" y="{y + 10 + r * 22}" width="6" height="9"/>')
            x += bw + rnd.randint(3, 16)
        groups.append(f'<g fill="{color}" opacity="{opacity}">{"".join(rects)}</g>')
        if lights:
            groups.append(f'<g fill="#ffd98a" opacity="0.45">{"".join(lights)}</g>')
    return "".join(groups)


def write(name, svg):
    (OUT / name).write_text(svg, encoding="utf-8")
    print("wrote", (OUT / name).relative_to(OUT.parent.parent))


# Hero / banner background --------------------------------------------------
W, H = 1600, 900
hero = (
    f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" preserveAspectRatio="xMidYMid slice">'
    '<defs><linearGradient id="sky" x1="0" y1="0" x2="0" y2="1">'
    '<stop offset="0" stop-color="#123c8f"/><stop offset="0.6" stop-color="#062a72"/><stop offset="1" stop-color="#011f5b"/>'
    '</linearGradient><radialGradient id="glow" cx="0.5" cy="1" r="0.8">'
    '<stop offset="0" stop-color="#3f6fd0" stop-opacity="0.55"/><stop offset="1" stop-color="#011f5b" stop-opacity="0"/>'
    '</radialGradient></defs>'
    f'<rect width="{W}" height="{H}" fill="url(#sky)"/>'
    f'<rect width="{W}" height="{H}" fill="url(#glow)"/>'
    + skyline(W, H, 7, [
        ("#0b2f78", 0.85, 140, 360, 40, 110),
        ("#062458", 1.0, 180, 480, 50, 140),
        ("#02163f", 1.0, 220, 620, 60, 170),
    ])
    + "</svg>"
)
write("hero-skyline.svg", hero)


# 3:2 tile placeholders ------------------------------------------------------
def tile(name, seed, top, bottom, label_icon):
    w, h = 900, 600
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" preserveAspectRatio="xMidYMid slice">'
        f'<defs><linearGradient id="g" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{top}"/>'
        f'<stop offset="1" stop-color="{bottom}"/></linearGradient></defs>'
        f'<rect width="{w}" height="{h}" fill="url(#g)"/>'
        + skyline(w, h, seed, [
            ("#ffffff", 0.08, 90, 220, 30, 80),
            ("#ffffff", 0.14, 120, 320, 40, 110),
            ("#ffffff", 0.22, 150, 400, 50, 130),
        ], windows=False)
        + label_icon
        + "</svg>"
    )
    write(name, svg)


ICON_TREK = ('<g transform="translate(450 250)" fill="none" stroke="#ffffff" stroke-width="10" stroke-linecap="round" stroke-linejoin="round" opacity="0.9">'
             '<path d="M-90 60 L-30 -50 L20 30 L60 -20 L110 60 Z"/><circle cx="60" cy="-70" r="18"/></g>')
ICON_SPEAKER = ('<g transform="translate(450 250)" fill="none" stroke="#ffffff" stroke-width="10" stroke-linecap="round" opacity="0.9">'
                '<rect x="-30" y="-90" width="60" height="120" rx="30"/><path d="M-65 0a65 65 0 0 0 130 0M0 65v40M-40 105h80"/></g>')
ICON_TROPHY = ('<g transform="translate(450 250)" fill="none" stroke="#ffffff" stroke-width="10" stroke-linecap="round" stroke-linejoin="round" opacity="0.9">'
               '<path d="M-60 -90h120v50a60 60 0 0 1 -120 0zM-60 -70h-35v25a35 35 0 0 0 35 35M60 -70h35v25a35 35 0 0 1 -35 35M0 20v40M-45 100h90M-30 60h60v40h-60z"/></g>')
ICON_CAMERA = ('<g transform="translate(450 250)" fill="none" stroke="#ffffff" stroke-width="10" stroke-linecap="round" stroke-linejoin="round" opacity="0.9">'
               '<path d="M-110 -40h50l20 -30h80l20 30h50v130h-220z"/><circle cx="0" cy="25" r="38"/></g>')

tile("placeholder-treks.svg", 11, "#1a3f8f", "#011f5b", ICON_TREK)
tile("placeholder-speakers.svg", 23, "#8a1414", "#4a0a0a", ICON_SPEAKER)
tile("placeholder-casecomps.svg", 37, "#2b4a7a", "#0e1f3f", ICON_TROPHY)
tile("placeholder-photo.svg", 51, "#5b6b85", "#2b3446", ICON_CAMERA)
tile("placeholder-nyc.svg", 63, "#274a93", "#0b1d4c", "")
tile("placeholder-philly.svg", 77, "#6b2222", "#2e0d0d", "")
tile("placeholder-chicago.svg", 89, "#3a5a8a", "#122544", "")

# Headshot placeholder ---------------------------------------------------------
write("headshot.svg",
      '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 200">'
      '<rect width="200" height="200" fill="#e9ecf1"/>'
      '<circle cx="100" cy="78" r="36" fill="#b8c0ce"/>'
      '<path d="M30 200c0-45 31-72 70-72s70 27 70 72z" fill="#b8c0ce"/></svg>')

# Favicon ---------------------------------------------------------------------
write("favicon.svg",
      '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">'
      '<rect width="64" height="64" rx="10" fill="#011f5b"/>'
      '<text x="32" y="43" text-anchor="middle" font-family="Helvetica, Arial, sans-serif" '
      'font-weight="700" font-size="34" fill="#ffffff">W</text></svg>')
