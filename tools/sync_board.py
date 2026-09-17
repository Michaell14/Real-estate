#!/usr/bin/env python3
"""Refresh the Executive Board from the club's Google Sheet and Drive folder.

Usage:
    GOOGLE_API_KEY=... BOARD_SHEET_ID=... BOARD_DRIVE_FOLDER_ID=... \\
        python3 tools/sync_board.py [--check] [--no-photos]

    --check         fetch and validate everything but write nothing
    --no-photos     update the roster only, leave exec-board/pictures/ alone
    --allow-shrink  accept a roster less than half the size of the current one
                    (otherwise a mostly-emptied sheet is refused)

What it does:

1. Reads the ``Board`` tab of the sheet (one member per row, header row first;
   see README "Updating the Executive Board" for the columns) and the optional
   ``Settings`` tab (``Season`` -> the year shown on the page), validates them
   and writes ``src/data/board.json``.
2. Lists the images in the Drive folder, matches each to a member by file name
   (``Josh Kwon.jpg`` -> Josh Kwon, or whatever the member's Photo column says),
   downloads the ones that are new or changed, and writes them as 512x512 WebP
   headshots into ``exec-board/pictures/``. ``src/data/headshots.json`` records
   which Drive file each headshot came from so unchanged photos are skipped.
   Headshots for people no longer on the board are deleted.

Then run ``python3 tools/build.py`` to render the page. The GitHub Action in
.github/workflows/sync-board.yml does both on a schedule and commits the result.

Problems with the sheet (a missing column, a bad email, a row with no name)
stop the script before anything is written and are listed all at once. A
member with no photo is only a warning: the page shows a placeholder.

Setup (once): a Google Cloud API key with the Google Sheets API and Google
Drive API enabled; the sheet and the folder shared as "Anyone with the link"
(viewer). Nothing is written to Google.
"""
import argparse
import io
import json
import os
import pathlib
import sys
import urllib.error
import urllib.parse
import urllib.request

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import board  # noqa: E402

ROOT = board.ROOT
MANIFEST = ROOT / "src" / "data" / "headshots.json"
SHEETS_API = "https://sheets.googleapis.com/v4/spreadsheets/"
DRIVE_API = "https://www.googleapis.com/drive/v3/files"
IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp", "image/heic", "image/heif", "image/tiff", "image/bmp"}
ROSTER_TAB = "Board"
SETTINGS_TAB = "Settings"
SIZE, QUALITY = 512, 85

warnings = []


def warn(message):
    warnings.append(message)
    print("warning:", message)


def fail(message):
    print("error:", message, file=sys.stderr)
    summary(failed=True)
    sys.exit(1)


def summary(failed=False):
    """Write the outcome to the GitHub Actions job summary, if there is one."""
    path = os.environ.get("GITHUB_STEP_SUMMARY")
    if not path:
        return
    lines = ["## Executive Board sync", ""]
    if failed:
        lines.append("**Failed** – nothing was changed. See the log for the problem.")
    if warnings:
        lines += ["", "Warnings:", ""] + [f"- {w}" for w in warnings]
    with open(path, "a", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")


def get(url, params, key, binary=False):
    params = dict(params, key=key)
    full = url + "?" + urllib.parse.urlencode(params, doseq=True)
    try:
        with urllib.request.urlopen(full, timeout=60) as resp:
            body = resp.read()
    except urllib.error.HTTPError as err:
        detail = err.read().decode("utf-8", "replace")
        try:
            detail = json.loads(detail)["error"]["message"]
        except (ValueError, KeyError, TypeError):
            pass
        hint = {
            403: "  (is the Sheets/Drive API enabled for this key, and is the sheet/folder shared as 'Anyone with the link'?)",
            404: "  (check BOARD_SHEET_ID / BOARD_DRIVE_FOLDER_ID and the sharing settings)",
        }.get(err.code, "")
        fail(f"Google returned HTTP {err.code} for {url}: {detail}{hint}")
    except (urllib.error.URLError, TimeoutError) as err:
        fail(f"could not reach {url}: {err}")
    return body if binary else json.loads(body.decode("utf-8"))


# --- Sheet ------------------------------------------------------------------

def fetch_roster(sheet_id, key):
    meta = get(SHEETS_API + sheet_id, {"fields": "sheets.properties.title"}, key)
    tabs = [s["properties"]["title"] for s in meta.get("sheets", [])]
    roster_tab = ROSTER_TAB if ROSTER_TAB in tabs else (tabs[0] if tabs else None)
    if not roster_tab:
        fail("the spreadsheet has no tabs")
    if roster_tab != ROSTER_TAB:
        warn(f"no tab called {ROSTER_TAB!r}; using the first tab, {roster_tab!r}")
    values = get(SHEETS_API + sheet_id + "/values/" + urllib.parse.quote(f"'{roster_tab}'"),
                 {"majorDimension": "ROWS"}, key).get("values", [])
    if not values:
        fail(f"the {roster_tab!r} tab is empty")
    try:
        members = board.rows_to_members(values[0], values[1:])
    except board.RosterError as err:
        fail(f"problems in the {roster_tab!r} tab:\n{err}")
    season = ""
    if SETTINGS_TAB in tabs:
        rows = get(SHEETS_API + sheet_id + "/values/" + urllib.parse.quote(f"'{SETTINGS_TAB}'"),
                   {"majorDimension": "ROWS"}, key).get("values", [])
        settings = {board.norm_key(r[0]): (r[1].strip() if len(r) > 1 else "") for r in rows if r and r[0]}
        season = settings.get("season", "")
    if not season:
        season = board.load()["season"] if board.DATA_FILE.exists() else ""
        if season:
            print(f"no Season in a {SETTINGS_TAB!r} tab; keeping {season!r}")
        else:
            warn(f"no Season in a {SETTINGS_TAB!r} tab and none on record; the page will show no year")
    return {"season": season, "members": members}


# --- Drive ------------------------------------------------------------------

def list_folder(folder_id, key):
    files, token = [], None
    while True:
        params = {
            "q": f"'{folder_id}' in parents and trashed = false",
            "fields": "nextPageToken, files(id, name, mimeType, md5Checksum, modifiedTime)",
            "pageSize": 200,
            "supportsAllDrives": "true",
            "includeItemsFromAllDrives": "true",
        }
        if token:
            params["pageToken"] = token
        page = get(DRIVE_API, params, key)
        files += page.get("files", [])
        token = page.get("nextPageToken")
        if not token:
            return files


def download(file_id, key):
    return get(f"{DRIVE_API}/{file_id}", {"alt": "media", "supportsAllDrives": "true"}, key, binary=True)


def sync_photos(members, folder_id, key, dry_run):
    try:
        from make_headshots import headshot, save_webp
    except SystemExit as err:   # make_headshots exits if Pillow is missing
        fail(str(err))
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8")) if MANIFEST.exists() else {}
    images = {}
    for f in list_folder(folder_id, key):
        if f.get("mimeType") not in IMAGE_TYPES:
            continue
        stem = pathlib.Path(f["name"]).stem
        images.setdefault(board.norm_key(stem), []).append(f)

    wanted, new_manifest, changed = {}, {}, 0
    for member in members:
        pic = board.picture_name(member)
        out = board.PICTURES / (pic + ".webp")
        wanted[out.name] = member
        candidates = images.get(board.norm_key(pic), [])
        if not candidates:
            if not out.exists():
                warn(f"no photo for {member['name']} (add '{pic}.jpg' or '{pic}.png' to the Drive folder); "
                     "showing a placeholder")
            elif out.name in manifest:
                new_manifest[out.name] = manifest[out.name]
            continue
        if len(candidates) > 1:
            candidates.sort(key=lambda f: f["modifiedTime"], reverse=True)
            warn(f"{len(candidates)} files in the Drive folder match {member['name']}; using the newest, "
                 f"{candidates[0]['name']}")
        source = candidates[0]
        stamp = source.get("md5Checksum") or source["modifiedTime"]
        record = {"drive_id": source["id"], "drive_name": source["name"], "md5": stamp}
        new_manifest[out.name] = record
        if out.exists() and manifest.get(out.name, {}).get("md5") == stamp:
            continue
        print(f"{'would fetch' if dry_run else 'fetching'} {source['name']} -> {out.relative_to(ROOT)}")
        if dry_run:
            changed += 1
            continue
        data = download(source["id"], key)
        try:
            img, note = headshot(io.BytesIO(data), SIZE)
        except Exception as err:   # noqa: BLE001 - one bad file must not stop the rest
            warn(f"could not read {source['name']} for {member['name']}: {err}")
            new_manifest.pop(out.name, None)
            continue
        save_webp(img, out, QUALITY)
        print(f"  wrote {out.relative_to(ROOT)} ({note})")
        changed += 1

    known_stems = {board.norm_key(pathlib.Path(n).stem) for n in wanted}
    for k, files in images.items():
        if k not in known_stems:
            warn(f"{files[0]['name']} in the Drive folder does not match anyone on the board; ignored")

    board.PICTURES.mkdir(parents=True, exist_ok=True)
    for old in sorted(board.PICTURES.glob("*.webp")):
        if old.name not in wanted:
            print(f"{'would remove' if dry_run else 'removing'} {old.relative_to(ROOT)} (no longer on the board)")
            if not dry_run:
                old.unlink()
            changed += 1
    if not dry_run:
        MANIFEST.write_text(json.dumps(new_manifest, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
                            encoding="utf-8")
    return changed


# --- Main -------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--check", action="store_true", help="validate everything but write nothing")
    parser.add_argument("--no-photos", action="store_true", help="skip the Drive folder")
    parser.add_argument("--allow-shrink", action="store_true",
                        help="accept a roster less than half the size of the current one")
    args = parser.parse_args()

    key = os.environ.get("GOOGLE_API_KEY", "").strip()
    sheet_id = os.environ.get("BOARD_SHEET_ID", "").strip()
    folder_id = os.environ.get("BOARD_DRIVE_FOLDER_ID", "").strip()
    if not key or not sheet_id:
        fail("set GOOGLE_API_KEY and BOARD_SHEET_ID (see README, 'Updating the Executive Board')")

    data = fetch_roster(sheet_id, key)
    print(f"sheet: {len(data['members'])} members in {len(board.groups(data['members']))} groups, "
          f"season {data['season']!r}")
    if board.DATA_FILE.exists() and not args.allow_shrink:
        # A half-deleted sheet should not quietly wipe most of the board (and its photos).
        current = len(board.load()["members"])
        if len(data["members"]) * 2 < current:
            fail(f"the sheet has {len(data['members'])} members but the site has {current}; "
                 "if that is right, run again with --allow-shrink")
    if not args.check:
        board.save(data)
        print("wrote", board.DATA_FILE.relative_to(ROOT))

    if args.no_photos:
        print("photos skipped (--no-photos)")
    elif not folder_id:
        warn("BOARD_DRIVE_FOLDER_ID is not set; headshots were not synced")
    else:
        changed = sync_photos(data["members"], folder_id, key, args.check)
        print(f"photos: {changed} file(s) {'would be ' if args.check else ''}changed")
    print(f"done{' (check only, nothing written)' if args.check else ''}, {len(warnings)} warning(s)")
    summary()


if __name__ == "__main__":
    main()
