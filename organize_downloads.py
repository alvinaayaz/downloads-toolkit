#!/usr/bin/env python3
"""Downloads folder organizer v2 (Windows / Mac / Linux, Python 3.8+, no installs).

    python organize_downloads.py                 # preview only
    python organize_downloads.py --run           # move files
    python organize_downloads.py --undo          # undo the last --run
    python organize_downloads.py --run --quiet   # for scheduled runs

Options:
    --folder PATH       folder to organize (default: your Downloads)
    --skip Code,PDFs    leave these categories alone
    --min-age 30        only touch files older than N minutes (default 30)

Every --run is saved in moves.log (next to this script) so --undo can reverse it.
"""
import argparse
import json
import shutil
import sys
import time
from datetime import datetime
from pathlib import Path

try:  # emoji / non-latin filenames must never crash the script
    sys.stdout.reconfigure(errors="replace")
except Exception:
    pass

CATEGORIES = {
    "Images": {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".svg", ".heic"},
    "PDFs": {".pdf"},
    "Documents": {".doc", ".docx", ".txt", ".rtf", ".odt", ".ppt", ".pptx", ".md"},
    "Spreadsheets": {".xls", ".xlsx", ".csv", ".ods"},
    "Videos": {".mp4", ".mkv", ".mov", ".avi", ".webm"},
    "Audio": {".mp3", ".wav", ".m4a", ".flac", ".ogg"},
    "Archives": {".zip", ".rar", ".7z", ".tar", ".gz"},
    "Installers": {".exe", ".msi", ".dmg", ".pkg", ".deb", ".apk"},
    "Code": {".py", ".js", ".html", ".css", ".json", ".ipynb", ".sql"},
}

# Never touched: unfinished downloads, system files, shortcuts, our own log
SKIP_SUFFIXES = {".crdownload", ".part", ".tmp", ".download", ".ini", ".lnk", ".log"}

# Project files: moving these breaks a project folder
SKIP_NAMES = {
    "package.json", "package-lock.json", "yarn.lock", "pnpm-lock.yaml",
    "requirements.txt", "pyproject.toml", "pipfile", "pipfile.lock", "setup.py",
    "dockerfile", "docker-compose.yml", "docker-compose.yaml", ".dockerignore",
    "makefile", "tsconfig.json", "jest.config.js", "webpack.config.js",
    "vite.config.js", "babel.config.js", "env.example", "test.yml",
    "index.html", "server.js", "config.py", "db.js",
}
SKIP_PREFIXES = (".env", "readme", "license", "changelog")

LOG = Path(__file__).resolve().parent / "moves.log"


def category_for(path):
    ext = path.suffix.lower()
    for name, exts in CATEGORIES.items():
        if ext in exts:
            return name
    return "Other"


def is_protected(path):
    name = path.name.lower()
    return (name in SKIP_NAMES or name.startswith(SKIP_PREFIXES) or name.startswith(".")
            or path.suffix.lower() in SKIP_SUFFIXES)


def unique_target(target):
    """Never overwrite: add (1), (2), ... if the name is taken."""
    if not target.exists():
        return target
    n = 1
    while True:
        candidate = target.with_name(f"{target.stem} ({n}){target.suffix}")
        if not candidate.exists():
            return candidate
        n += 1


def organize(folder, run, skip, min_age, quiet):
    moves, kept, too_new = [], 0, 0
    for item in sorted(folder.iterdir()):
        if not item.is_file():
            continue
        cat = category_for(item)
        if is_protected(item) or cat in skip:
            kept += 1
            continue
        if (time.time() - item.stat().st_mtime) / 60 < min_age:
            too_new += 1
            continue
        dest_dir = folder / cat
        target = unique_target(dest_dir / item.name)
        if not quiet:
            print(f"{'MOVE' if run else 'WOULD MOVE'}: {item.name}  ->  {cat}/")
        if run:
            try:
                dest_dir.mkdir(exist_ok=True)
                shutil.move(str(item), str(target))
                moves.append([str(item), str(target)])
            except OSError as e:  # file in use, permissions, ...
                print(f"SKIPPED (in use?): {item.name} ({e})")
        else:
            moves.append([str(item), str(target)])

    if run and moves:
        entry = {"time": datetime.now().isoformat(timespec="seconds"),
                 "folder": str(folder), "moves": moves}
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    verb = "Moved" if run else "Would move"
    print(f"{verb} {len(moves)} file(s). Left alone: {kept} protected, {too_new} too new.")
    if not run and moves:
        print("Happy with this? Run again with --run. You can undo with --undo.")


def undo():
    if not LOG.exists():
        raise SystemExit("Nothing to undo (no moves.log yet).")
    lines = [l for l in LOG.read_text(encoding="utf-8").splitlines() if l.strip()]
    if not lines:
        raise SystemExit("Nothing to undo.")
    entry = json.loads(lines[-1])
    restored = missing = 0
    for src, dst in reversed(entry["moves"]):
        s, d = Path(src), Path(dst)
        if not d.exists():
            missing += 1
            continue
        s.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(d), str(unique_target(s)))
        restored += 1
    for d in {Path(dst).parent for _, dst in entry["moves"]}:
        try:
            d.rmdir()  # only removes folders that are now empty
        except OSError:
            pass
    LOG.write_text("".join(l + "\n" for l in lines[:-1]), encoding="utf-8")
    print(f"Undid the run from {entry['time']}: restored {restored} file(s), "
          f"{missing} no longer found.")


def main():
    p = argparse.ArgumentParser(description="Organize your Downloads folder.")
    p.add_argument("--folder", default=str(Path.home() / "Downloads"))
    p.add_argument("--run", action="store_true", help="actually move files")
    p.add_argument("--undo", action="store_true", help="undo the last run")
    p.add_argument("--skip", default="", help="comma list of categories to leave alone")
    p.add_argument("--min-age", type=int, default=30, help="minutes (default 30)")
    p.add_argument("--quiet", action="store_true", help="print only the summary")
    a = p.parse_args()

    if a.undo:
        return undo()
    folder = Path(a.folder).expanduser()
    if not folder.is_dir():
        raise SystemExit(f"Folder not found: {folder}")
    skip = {s.strip() for s in a.skip.split(",") if s.strip()}
    organize(folder, a.run, skip, a.min_age, a.quiet)


if __name__ == "__main__":
    main()
