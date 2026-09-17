"""The Executive Board roster: reading src/data/board.json and rendering it.

Shared by tools/build.py (which turns the roster into the exec-board page) and
tools/sync_board.py (which refreshes the roster from Google Sheets). Pure
standard library so the site still builds without Pillow.

board.json looks like::

    {
      "season": "2026–2027",
      "members": [
        {"committee": "Co-Presidents", "name": "Josh Kwon", "school": "Wharton",
         "class": "2028", "email": "joshkwon@wharton.upenn.edu",
         "bio": "", "photo": ""},
        ...
      ]
    }

Members appear on the page in list order, grouped by committee in the order
each committee first appears. ``bio`` and ``photo`` are optional: ``photo``
names the headshot in exec-board/pictures/ (without the .webp) when it is not
simply the member's name.
"""
import html
import json
import pathlib
import re
import unicodedata
import urllib.parse

ROOT = pathlib.Path(__file__).resolve().parent.parent
DATA_FILE = ROOT / "src" / "data" / "board.json"
PICTURES = ROOT / "exec-board" / "pictures"
PLACEHOLDER = "assets/img/headshot-placeholder.svg"

# Sheet column header -> member field. Matching ignores case, spaces and
# punctuation, so "Class of", "class_of" and "Class" all work.
COLUMNS = {
    "committee": "committee",
    "name": "name",
    "school": "school",
    "class": "class",
    "classof": "class",
    "year": "class",
    "classyear": "class",
    "email": "email",
    "bio": "bio",
    "description": "bio",
    "photo": "photo",
    "headshot": "photo",
    "picture": "photo",
    "image": "photo",
}
REQUIRED = ("committee", "name", "school", "class", "email")
EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


class RosterError(Exception):
    """A problem with the roster that should stop the sync/build."""


def norm_key(text):
    """Case-, space- and punctuation-insensitive key for headers and file names."""
    text = unicodedata.normalize("NFKD", str(text))
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return re.sub(r"[^a-z0-9]+", "", text.casefold())


def picture_name(member):
    """File name (without extension) of the member's headshot."""
    name = (member.get("photo") or member["name"]).strip()
    name = re.sub(r"\.(png|jpe?g|webp|heic)$", "", name, flags=re.I)
    return re.sub(r'[\\/:*?"<>|]+', "", name).strip()


def class_year(value):
    """'2028', '28', "'28" or "’28" -> '2028'."""
    digits = re.sub(r"\D", "", str(value))
    if len(digits) == 2:
        return "20" + digits
    if len(digits) == 4:
        return digits
    raise RosterError(f"class year {value!r} is not a year like 2028 or '28")


def rows_to_members(header, rows):
    """Turn a sheet (header row + data rows) into member dicts.

    Blank rows are skipped. Raises RosterError with every problem found, so a
    single sheet edit fixes them all at once.
    """
    fields = [COLUMNS.get(norm_key(h)) for h in header]
    known = [f for f in fields if f]
    missing = [f for f in REQUIRED if f not in known]
    if missing:
        raise RosterError("the sheet is missing the column(s): " + ", ".join(missing)
                          + f"  (headers found: {', '.join(h for h in header if h)})")
    members, problems = [], []
    for n, row in enumerate(rows, start=2):   # row 1 is the header
        cells = [str(c).strip() for c in row] + [""] * (len(fields) - len(row))
        member = {f: c for f, c in zip(fields, cells) if f}
        if not any(member.values()):
            continue
        for f in REQUIRED:
            if not member.get(f):
                problems.append(f"row {n}: missing {f}")
        if member.get("email") and not EMAIL_RE.match(member["email"]):
            problems.append(f"row {n}: {member['email']!r} is not an email address")
        if member.get("class"):
            try:
                member["class"] = class_year(member["class"])
            except RosterError as err:
                problems.append(f"row {n}: {err}")
        member.setdefault("bio", "")
        member.setdefault("photo", "")
        members.append(member)
    if not members:
        problems.append("the sheet has no members")
    if problems:
        raise RosterError("\n".join(problems))
    return members


def load():
    if not DATA_FILE.exists():
        raise RosterError(f"{DATA_FILE.relative_to(ROOT)} is missing; run tools/sync_board.py")
    data = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    if not isinstance(data.get("members"), list) or not data["members"]:
        raise RosterError(f"{DATA_FILE.relative_to(ROOT)} has no members")
    data.setdefault("season", "")
    return data


def save(data):
    DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    DATA_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def groups(members):
    """[(committee, [member, ...]), ...] in first-appearance order."""
    out = {}
    for member in members:
        out.setdefault(member["committee"], []).append(member)
    return list(out.items())


def esc(text):
    return html.escape(str(text), quote=True)


def render_member(member, root):
    name, email = member["name"], member["email"]
    local, _, domain = email.partition("@")
    picture = PICTURES / (picture_name(member) + ".webp")
    if picture.exists():
        src = "pictures/" + urllib.parse.quote(picture.name)
    else:
        src = f"{root}{PLACEHOLDER}"
    year = member["class"][-2:]
    lines = [
        '        <div class="member">',
        f'          <a class="member__photo-link" href="mailto:{esc(email)}" aria-label="Email {esc(name)}">',
        f'            <img class="member__photo" src="{src}" alt="{esc(name)}">',
        f'            <span class="member__email" aria-hidden="true">{esc(local)}@<br>{esc(domain)}</span>',
        '          </a>',
        f'          <h3>{esc(name)}</h3>',
        f'          <p class="meta">{esc(member["school"])} &rsquo;{esc(year)}</p>',
    ]
    if member.get("bio"):
        lines.append(f'          <p class="member__bio">{esc(member["bio"])}</p>')
    lines.append('        </div>')
    return "\n".join(lines)


def render(data, root=""):
    """The .board-group sections for the exec-board page body."""
    sections = []
    for committee, members in groups(data["members"]):
        cards = "\n\n".join(render_member(m, root) for m in members)
        sections.append(
            '    <section class="board-group" data-reveal>\n'
            f'      <h2 class="board-group__title">{esc(committee)}</h2>\n'
            '      <div class="board-group__members">\n'
            f'{cards}\n'
            '      </div>\n'
            '    </section>'
        )
    return "\n\n".join(sections)
