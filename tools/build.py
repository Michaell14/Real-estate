#!/usr/bin/env python3
"""Static site builder for the WUREC website remake.

Usage:
    python3 tools/build.py

Reads ``src/layout.html`` (shared header/footer) and every page in
``src/pages/``, then writes ``index.html`` files into the repository root, e.g.

    src/pages/membership.html        -> membership/index.html
    src/pages/treks-highlights.html  -> treks/highlights/index.html   (slug: treks/highlights)

It also writes ``sitemap.xml``, ``robots.txt``, ``404.html`` and a small
redirect page for every old address listed in ``REDIRECTS``.

Each page starts with a front-matter block::

    ---
    title: Membership               # page name; <title> becomes "Membership | WUREC — Wharton ..."
    slug: membership                # output folder; empty for the home page
    description: One or two sentences for search results and link previews.
    hero: assets/img/photos/x.jpg   # (optional) hero photo: preloaded, and the link-preview image
    nav: membership                 # (optional) which nav item is highlighted
    body_class: home                # (optional) extra class on <body>
    seo_title: ...                  # (optional) exact <title> text
    image: assets/img/og/x.jpg      # (optional) link-preview image, if not the generated one
    out: 404.html                   # (optional) write here instead of <slug>/index.html
    noindex: true                   # (optional) keep the page out of search engines and the sitemap
    ---

Inside page bodies use ``{{root}}`` for links/assets so pages work at any depth
(e.g. ``{{root}}assets/img/x.svg`` or ``{{root}}membership/``).

SITE_URL must be the address the site is served from: it is used for canonical
links, link previews, structured data, the sitemap and robots.txt.
"""
import datetime
import html
import json
import pathlib
import re
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
PAGES_DIR = SRC / "pages"

SITE_NAME = "WUREC"
SITE_LONG_NAME = "Wharton Undergraduate Real Estate Club"
SITE_URL = "https://wurec.info"            # no trailing slash
DEFAULT_IMAGE = "assets/img/og/home.jpg"   # link-preview image for pages without a hero
TWITTER_HANDLE = "@WUREC"
SOCIAL = [
    "https://www.instagram.com/wurec_/",
    "https://www.linkedin.com/company/wharton-undergraduate-real-estate-group",
    "https://www.facebook.com/wurec",
    "https://x.com/WUREC",
    "https://pennclubs.com/club/wharton-undergraduate-real-estate-club/",
]

# Main navigation. A tuple of (label, slug) is a link; (label, None, children)
# is a Squarespace-style "folder" with a dropdown.
NAV = [
    ("Membership", "membership"),
    ("Events", None, [
        ("Treks", "treks"),
        ("Speakers", "speakers"),
        ("Case Comps", "case-competitions"),
    ]),
    ("Executive Board", "exec-board"),
]

# Old address -> current page slug ("" is the home page). Each old address gets
# a small index.html that sends visitors and search engines to the new one, so
# links to the former wurec.info pages keep working.
REDIRECTS = {
    "new-page": "treks/highlights",
    "new-page-1": "speakers",
    "new-page-2": "case-competitions",
    "featured-events": "",
    "nyc102017": "treks",
    "nyc112021": "treks",
    "calendar": "",
    "resources": "membership",
    "media": "",
    "blog": "",
    "blog/blockchain-real-estate": "",
    "blog/global-debt-series": "",
    "blog/golf-real-estate": "",
    "blog/middle-housing": "",
    "blog/rediscovering-retail": "",
    "blog/b83fe5ea-706b-4643-a4f3-f117a9ba99b2": "",
}

FRONT_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*\n", re.S)
CHEVRON = ('<svg class="chevron" viewBox="0 0 12 12" aria-hidden="true">'
           '<path d="M2 4l4 4 4-4" fill="none" stroke="currentColor" '
           'stroke-width="1.6" stroke-linecap="round"/></svg>')
REDIRECT_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Redirecting to {name} — {site}</title>
<meta name="robots" content="noindex">
<link rel="canonical" href="{abs_url}">
<meta http-equiv="refresh" content="0; url={rel_url}">
<script>location.replace("{rel_url}");</script>
</head>
<body>
<p>This page has moved to <a href="{rel_url}">{abs_url}</a>.</p>
</body>
</html>
"""
ROBOTS_TXT = f"""User-agent: *
Allow: /
Disallow: /src/
Disallow: /tools/
Disallow: /carousel/

Sitemap: {SITE_URL}/sitemap.xml
"""


def esc(text):
    return html.escape(str(text), quote=True)


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


def page_url(slug):
    return f"{SITE_URL}/" + (f"{slug}/" if slug else "")


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


def last_modified(path):
    """Date of the page's last commit, or today if it has uncommitted changes."""
    rel = path.relative_to(ROOT).as_posix()

    def git(*args):
        try:
            return subprocess.run(["git", *args, "--", rel], cwd=ROOT, capture_output=True,
                                  text=True, check=False).stdout.strip()
        except OSError:
            return ""

    if not git("status", "--porcelain"):
        date = git("log", "-1", "--format=%cs")
        if date:
            return date
    return datetime.date.today().isoformat()


def seo_block(root, canonical, title, description, image_abs, hero, noindex):
    """Canonical link, robots, Open Graph / Twitter tags and the hero preload."""
    lines = []
    if noindex:
        lines.append('<meta name="robots" content="noindex">')
    else:
        lines += [
            f'<link rel="canonical" href="{canonical}">',
            '<meta name="robots" content="index, follow, max-image-preview:large">',
            f'<meta property="og:url" content="{canonical}">',
        ]
    lines += [
        f'<meta property="og:site_name" content="{esc(SITE_LONG_NAME)}">',
        '<meta property="og:type" content="website">',
        '<meta property="og:locale" content="en_US">',
        f'<meta property="og:title" content="{esc(title)}">',
        f'<meta property="og:description" content="{esc(description)}">',
        f'<meta property="og:image" content="{esc(image_abs)}">',
        f'<meta property="og:image:alt" content="{esc(title)}">',
        '<meta name="twitter:card" content="summary_large_image">',
        f'<meta name="twitter:site" content="{TWITTER_HANDLE}">',
    ]
    if hero:
        lines.append(f'<link rel="preload" as="image" href="{root}{hero}" fetchpriority="high">')
    return "\n".join(lines)


def structured_data(slug, canonical, title, description, image_abs, titles):
    """JSON-LD: the club, the site, this page and its breadcrumb trail."""
    org_id, site_id = f"{SITE_URL}/#organization", f"{SITE_URL}/#website"
    graph = [
        {
            "@type": "Organization", "@id": org_id,
            "name": SITE_LONG_NAME, "alternateName": SITE_NAME, "url": f"{SITE_URL}/",
            "logo": {"@type": "ImageObject", "url": f"{SITE_URL}/assets/img/logo.png", "width": 512, "height": 512},
            "sameAs": SOCIAL,
            "parentOrganization": {"@type": "CollegeOrUniversity", "name": "The Wharton School, University of Pennsylvania",
                                   "url": "https://www.wharton.upenn.edu/"},
        },
        {"@type": "WebSite", "@id": site_id, "url": f"{SITE_URL}/", "name": SITE_NAME,
         "alternateName": SITE_LONG_NAME, "publisher": {"@id": org_id}},
        {"@type": "WebPage", "@id": canonical, "url": canonical, "name": title, "description": description,
         "isPartOf": {"@id": site_id}, "about": {"@id": org_id},
         "primaryImageOfPage": {"@type": "ImageObject", "url": image_abs}},
    ]
    if slug:
        crumbs = [{"@type": "ListItem", "position": 1, "name": "Home", "item": f"{SITE_URL}/"}]
        parts = slug.split("/")
        for n in range(1, len(parts) + 1):
            part = "/".join(parts[:n])
            name = titles.get(part, parts[n - 1].replace("-", " ").title())
            crumbs.append({"@type": "ListItem", "position": n + 1, "name": name, "item": page_url(part)})
        graph.append({"@type": "BreadcrumbList", "itemListElement": crumbs})
    data = json.dumps({"@context": "https://schema.org", "@graph": graph}, ensure_ascii=False, separators=(",", ":"))
    return f'<script type="application/ld+json">{data}</script>'


def write_redirects(titles):
    written = []
    for old, new in REDIRECTS.items():
        depth = len(old.split("/"))
        rel_url = "../" * depth + (f"{new}/" if new else "")
        page = REDIRECT_HTML.format(name=esc(titles.get(new, new)), site=SITE_NAME, abs_url=page_url(new), rel_url=rel_url)
        out_path = ROOT / old / "index.html"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(page, encoding="utf-8")
        written.append(out_path.relative_to(ROOT).as_posix())
    return written


def write_sitemap(entries):
    lines = ['<?xml version="1.0" encoding="UTF-8"?>',
             '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" '
             'xmlns:image="http://www.google.com/schemas/sitemap-image/1.1">']
    for loc, lastmod, image in entries:
        lines.append(f"  <url>\n    <loc>{esc(loc)}</loc>\n    <lastmod>{lastmod}</lastmod>\n"
                     f"    <image:image>\n      <image:loc>{esc(image)}</image:loc>\n    </image:image>\n  </url>")
    lines.append("</urlset>\n")
    (ROOT / "sitemap.xml").write_text("\n".join(lines), encoding="utf-8")


def build():
    layout = (SRC / "layout.html").read_text(encoding="utf-8")
    pages = []
    for path in sorted(PAGES_DIR.rglob("*.html")):
        meta, body = parse_page(path)
        slug = meta.get("slug", path.relative_to(PAGES_DIR).with_suffix("").as_posix()).strip("/")
        pages.append((path, meta, body, slug))
    if not pages:
        sys.exit("no pages found in src/pages")
    titles = {slug: meta.get("title", SITE_NAME) for _, meta, _, slug in pages if not meta.get("out")}
    written, sitemap = [], []
    for path, meta, body, slug in pages:
        out_name = meta.get("out")
        noindex = meta.get("noindex", "").lower() in ("true", "yes", "1")
        if out_name:
            root = f"{SITE_URL}/"   # a 404 page is served at any depth, so its links must be absolute
            out_path = ROOT / out_name
        else:
            root = "../" * (len(slug.split("/")) if slug else 0)
            out_path = (ROOT / slug / "index.html") if slug else (ROOT / "index.html")
        title = meta.get("title", SITE_NAME)
        full_title = meta.get("seo_title") or f"{title} | {SITE_NAME} — {SITE_LONG_NAME}"
        description = meta.get("description", "")
        canonical = "" if out_name else page_url(slug)
        hero = meta.get("hero", "")
        generated = f"assets/img/og/{slug.replace('/', '-') or 'home'}.jpg"
        image = meta.get("image") or (generated if (ROOT / generated).exists() else "") or hero or DEFAULT_IMAGE
        image_abs = f"{SITE_URL}/{image}"
        active = meta.get("nav", slug.split("/")[0] if slug else "")
        values = {
            "title": esc(full_title),
            "description": esc(description),
            "root": root,
            "home": root or "./",
            "nav": render_nav(root, active),
            "body_class": meta.get("body_class", "page"),
            "seo": seo_block(root, canonical, full_title, description, image_abs, hero, noindex),
            "jsonld": "" if noindex else structured_data(slug, canonical, full_title, description, image_abs, titles),
            "content": body.replace("{{root}}", root),
        }
        out = layout
        for key, value in values.items():
            out = out.replace("{{" + key + "}}", value)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(out, encoding="utf-8")
        written.append(out_path.relative_to(ROOT).as_posix())
        if not (noindex or out_name):
            sitemap.append((canonical, last_modified(path), image_abs))
    redirects = write_redirects(titles)
    write_sitemap(sitemap)
    (ROOT / "robots.txt").write_text(ROBOTS_TXT, encoding="utf-8")
    for item in written:
        print("wrote", item)
    print(f"{len(written)} pages built, {len(redirects)} redirects, sitemap.xml and robots.txt written")


if __name__ == "__main__":
    build()
