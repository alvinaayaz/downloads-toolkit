#!/usr/bin/env python3
"""Duplicate finder (Windows / Mac / Linux, Python 3.8+, no installs).

Finds files with IDENTICAL CONTENT (not just similar names), keeps one copy,
and moves the rest into a "Duplicates" folder. Nothing is ever deleted.

    python find_duplicates.py            # preview only
    python find_duplicates.py --run      # move duplicates into Downloads\\Duplicates
    python find_duplicates.py --undo     # put the last run back

Scans the top of your Downloads folder plus the category folders made by
organize_downloads.py (Images, PDFs, Documents, ...). Project folders are not touched.
Every --run is saved in duplicates.log (next to this script) so --undo works.
"""
import argparse
import hashlib
import json
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path

try:
    sys.stdout.reconfigure(errors="replace")
except Exception:
    pass

CATEGORY_DIRS = ["Images", "PDFs", "Documents", "Spreadsheets", "Videos",
                 "Audio", "Archives", "Installers", "Code", "Other"]
DUP_DIR = "Duplicates"

SKIP_SUFFIXES = {".crdownload", ".part", ".tmp", ".download", ".ini", ".lnk", ".log"}
SKIP_NAMES = {
    "package.json", "package-lock.json", "yarn.lock", "pnpm-lock.yaml",
    "requirements.txt", "pyproject.toml", "pipfile", "pipfile.lock", "setup.py",
    "dockerfile", "docker-compose.yml", "docker-compose.yaml", ".dockerignore",
    "makefile", "tsconfig.json", "env.example", "index.html", "server.js",
    "config.py", "db.js",
}
SKIP_PREFIXES = (".env", "readme", "license", "changelog")

COPY_SUFFIX = re.compile(r"(\s\(\d+\)|\s-\sCopy|\scopy(\s\d+)?)$", re.I)
LOG = Path(__file__).resolve().parent / "duplicates.log"


def protected(path):
    n = path.name.lower()
    return (n in SKIP_NAMES or n.startswith(SKIP_PREFIXES) or n.startswith(".")
            or path.suffix.lower() in SKIP_SUFFIXES)


def collect(folder):
    dirs = [folder] + [folder / d for d in CATEGORY_DIRS if (folder / d).is_dir()]
    files = []
    for d in dirs:
        for f in d.iterdir():
            try:
                if f.is_file() and not protected(f) and f.stat().st_size > 0:
                    files.append(f)
            except OSError:
                pass
    return files


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def find_groups(files):
    by_size = {}
    for f in files:
        by_size.setdefault(f.stat().st_size, []).append(f)
    groups = {}
    for same in by_size.values():
        if len(same) < 2:
            continue  # unique size, cannot be a duplicate, no need to hash
        for f in same:
            try:
                groups.setdefault(sha256(f), []).append(f)
            except OSError as e:
                print(f"SKIPPED (cannot read): {f.name} ({e})")
    return [g for g in groups.values() if len(g) > 1]


def keeper_first(group):
    """Keep the file whose name looks most 'original': no (1)/Copy, then shortest, then oldest."""
    def rank(f):
        is_copy = bool(COPY_SUFFIX.search(f.stem))
        return (is_copy, len(f.name), f.stat().st_mtime)
    return sorted(group, key=rank)


def unique_target(target):
    if not target.exists():
        return target
    n = 1
    while True:
        c = target.with_name(f"{target.stem} ({n}){target.suffix}")
        if not c.exists():
            return c
        n += 1


def mb(n):
    return f"{n / 1024 / 1024:.1f} MB"


def scan(folder, run):
    groups = find_groups(collect(folder))
    moves, saved = [], 0
    dup_root = folder / DUP_DIR
    for g in sorted(groups, key=lambda g: keeper_first(g)[0].name.lower()):
        keep, *dups = keeper_first(g)
        print(f"KEEP: {keep.parent.name}/{keep.name}")
        for d in dups:
            print(f"   dup: {d.parent.name}/{d.name}")
            size = d.stat().st_size
            if run:
                try:
                    dup_root.mkdir(exist_ok=True)
                    target = unique_target(dup_root / d.name)
                    shutil.move(str(d), str(target))
                    moves.append([str(d), str(target)])
                    saved += size
                except OSError as e:
                    print(f"   SKIPPED (in use?): {d.name} ({e})")
            else:
                moves.append([str(d), ""])
                saved += size
    if run and moves:
        entry = {"time": datetime.now().isoformat(timespec="seconds"),
                 "folder": str(folder), "moves": moves}
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    verb = "Moved" if run else "Would move"
    print(f"\n{len(groups)} group(s) of duplicates. {verb} {len(moves)} file(s) "
          f"({mb(saved)}) into {DUP_DIR}/.")
    if not run and moves:
        print("Happy with this? Run again with --run. Undo anytime with --undo.")


def undo():
    if not LOG.exists():
        raise SystemExit("Nothing to undo (no duplicates.log yet).")
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
    try:
        (Path(entry["folder"]) / DUP_DIR).rmdir()  # only if empty
    except OSError:
        pass
    LOG.write_text("".join(l + "\n" for l in lines[:-1]), encoding="utf-8")
    print(f"Undid the run from {entry['time']}: restored {restored} file(s), "
          f"{missing} no longer found.")


def main():
    p = argparse.ArgumentParser(description="Find duplicate files by content.")
    p.add_argument("--folder", default=str(Path.home() / "Downloads"))
    p.add_argument("--run", action="store_true", help="actually move duplicates")
    p.add_argument("--undo", action="store_true", help="undo the last run")
    a = p.parse_args()
    if a.undo:
        return undo()
    folder = Path(a.folder).expanduser()
    if not folder.is_dir():
        raise SystemExit(f"Folder not found: {folder}")
    scan(folder, a.run)


if __name__ == "__main__":
    main()
