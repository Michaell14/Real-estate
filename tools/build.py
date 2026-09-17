#!/usr/bin/env python3
"""Static site builder for the WUREC website remake.

Usage:
    python3 tools/build.py

Reads ``src/layout.html`` (shared header/footer) and every page in
``src/pages/``, then writes ``index.html`` files into the repository root using
the original wurec.info URL slugs, e.g.

    src/pages/membership.html        -> membership/index.html
    src/pages/events/nyc.html        -> events/nyc/index.html   (nested folders work too)

Each page starts with a small front-matter block::

    ---
    title: Membership
    slug: membership
    description: One-line description for <meta name="description">.
    nav: membership          # (optional) which nav item is highlighted
    body_class: home         # (optional) extra class on <body>
    ---

Inside page bodies use ``{{root}}`` for links/assets so pages work at any depth
(e.g. ``{{root}}assets/img/x.svg`` or ``{{root}}membership/``).
"""
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
PAGES_DIR = SRC / "pages"
SITE_NAME = "WUREC"

# Main navigation. A tuple of (label, slug) is a link; (label, None, children)
# is a Squarespace-style "folder" with a dropdown.
NAV = [
    ("Home", ""),
    ("Membership", "membership"),
    ("Events", None, [
        ("Events", "featured-events"),
        ("Treks", "treks"),
        ("Speakers", "new-page-1"),
        ("Case Comps", "new-page-2"),
    ]),
    ("Executive Board", "exec-board"),
]

FRONT_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*\n", re.S)
CHEVRON = ('<svg class="chevron" viewBox="0 0 12 12" aria-hidden="true">'
           '<path d="M2 4l4 4 4-4" fill="none" stroke="currentColor" '
           'stroke-width="1.6" stroke-linecap="round"/></svg>')


def parse_page(path):
    text = path.read_text(encoding="utf-8")
    match = FRONT_RE.match(text)
    if not match:
        sys.exit(f"{path}: missing front matter block")
    meta = {}
    for line in match.group(1).splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        key, _, value = line.partition(":")
        meta[key.strip()] = value.strip()
    return meta, text[match.end():]


def link(root, slug):
    if slug:
        return f"{root}{slug}/"
    return root or "./"


def render_nav(root, active):
    items = []
    for entry in NAV:
        label, slug = entry[0], entry[1]
        children = entry[2] if len(entry) > 2 else None
        if children is None:
            current = ' aria-current="page"' if slug == active else ""
            items.append(f'<li><a href="{link(root, slug)}"{current}>{label}</a></li>')
            continue
        is_active = any(child[1] == active for child in children)
        cls = "folder is-active" if is_active else "folder"
        subs = []
        for child_label, child_slug in children:
            current = ' aria-current="page"' if child_slug == active else ""
            subs.append(f'<li><a href="{link(root, child_slug)}"{current}>{child_label}</a></li>')
        items.append(
            f'<li class="{cls}">'
            f'<button class="folder-toggle" type="button" aria-expanded="false" aria-haspopup="true">'
            f'{label}{CHEVRON}</button>'
            f'<ul class="sub">{"".join(subs)}</ul></li>'
        )
    return "<ul>" + "".join(items) + "</ul>"


def build():
    layout = (SRC / "layout.html").read_text(encoding="utf-8")
    pages = sorted(PAGES_DIR.rglob("*.html"))
    if not pages:
        sys.exit("no pages found in src/pages")
    written = []
    for path in pages:
        meta, body = parse_page(path)
        slug = meta.get("slug", path.relative_to(PAGES_DIR).with_suffix("").as_posix()).strip("/")
        depth = len(slug.split("/")) if slug else 0
        root = "../" * depth
        title = meta.get("title", SITE_NAME)
        full_title = SITE_NAME if slug == "" else f"{title} — {SITE_NAME}"
        active = meta.get("nav", slug.split("/")[0] if slug else "")
        values = {
            "title": full_title,
            "description": meta.get("description", ""),
            "root": root,
            "home": root or "./",
            "nav": render_nav(root, active),
            "body_class": meta.get("body_class", "page"),
            "content": body.replace("{{root}}", root),
        }
        out = layout
        for key, value in values.items():
            out = out.replace("{{" + key + "}}", value)
        out_path = (ROOT / slug / "index.html") if slug else (ROOT / "index.html")
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(out, encoding="utf-8")
        written.append(out_path.relative_to(ROOT).as_posix())
    for item in written:
        print("wrote", item)
    print(f"{len(written)} pages built")


if __name__ == "__main__":
    build()
