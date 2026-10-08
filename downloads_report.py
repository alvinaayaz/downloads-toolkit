#!/usr/bin/env python3
"""Downloads space report + old-installer cleanup (Windows / Mac / Linux, Python 3.8+).

    python downloads_report.py              # report only, nothing is moved
    python downloads_report.py --run        # move old installers into Downloads\\Review
    python downloads_report.py --undo       # put the last run back
    python downloads_report.py --days 60    # what counts as "old" (default 30)

The report shows total size, size per folder, the 10 biggest files, and installers
older than --days. --run moves ONLY those old installers (.exe .msi .dmg .pkg .deb .apk)
into a Review folder. Nothing is ever deleted. Every --run is saved in review.log
(next to this script) so --undo works.
"""
import argparse
import json
import shutil
import sys
import time
from datetime import datetime
from pathlib import Path

try:
    sys.stdout.reconfigure(errors="replace")
except Exception:
    pass

FOLDERS = ["Images", "PDFs", "Documents", "Spreadsheets", "Videos", "Audio",
           "Archives", "Installers", "Code", "Other", "Duplicates", "Review"]
REVIEW = "Review"
INSTALLER_EXT = {".exe", ".msi", ".dmg", ".pkg", ".deb", ".apk"}
SKIP_SUFFIXES = {".crdownload", ".part", ".tmp", ".download", ".ini", ".lnk", ".log"}
LOG = Path(__file__).resolve().parent / "review.log"


def size_str(n):
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024


def age_days(f):
    st = f.stat()
    t = st.st_ctime if sys.platform == "win32" else st.st_mtime  # win32 ctime = created
    return (time.time() - t) / 86400


def scan(folder):
    """Top of the folder + the category folders. Project folders are not scanned."""
    found = []
    places = [(folder, "(top level)")] + [(folder / d, d) for d in FOLDERS if (folder / d).is_dir()]
    for place, label in places:
        for f in place.iterdir():
            try:
                if f.is_file() and not f.name.startswith(".") and f.suffix.lower() not in SKIP_SUFFIXES:
                    found.append((f, f.stat().st_size, label))
            except OSError:
                pass
    return found


def unique_target(target):
    if not target.exists():
        return target
    n = 1
    while True:
        c = target.with_name(f"{target.stem} ({n}){target.suffix}")
        if not c.exists():
            return c
        n += 1


def report(folder, days, run):
    files = scan(folder)
    total = sum(s for _, s, _ in files)
    print(f"Downloads: {len(files)} files, {size_str(total)}\n")

    by = {}
    for _, s, label in files:
        c, t = by.get(label, (0, 0))
        by[label] = (c + 1, t + s)
    print("Size by folder:")
    for label, (c, t) in sorted(by.items(), key=lambda x: -x[1][1]):
        print(f"  {label:<14}{c:>5} files  {size_str(t):>10}")

    print("\n10 biggest files:")
    for f, s, label in sorted(files, key=lambda x: -x[1])[:10]:
        print(f"  {size_str(s):>10}  {label}/{f.name}")

    old = [(f, s, label) for f, s, label in files
           if f.suffix.lower() in INSTALLER_EXT and label not in (REVIEW, "Duplicates")
           and age_days(f) >= days]
    old_total = sum(s for _, s, _ in old)
    print(f"\nInstallers older than {days} days: {len(old)} files, {size_str(old_total)}")
    moves = []
    review = folder / REVIEW
    for f, s, label in sorted(old, key=lambda x: -x[1]):
        print(f"  {size_str(s):>10}  {int(age_days(f)):>4} days  {label}/{f.name}")
        if run:
            try:
                review.mkdir(exist_ok=True)
                target = unique_target(review / f.name)
                shutil.move(str(f), str(target))
                moves.append([str(f), str(target)])
            except OSError as e:
                print(f"  SKIPPED (in use?): {f.name} ({e})")

    dup = by.get("Duplicates")
    if dup:
        print(f"\nDuplicates folder: {size_str(dup[1])} (exact copies; safe to delete once you're sure)")

    if run:
        if moves:
            entry = {"time": datetime.now().isoformat(timespec="seconds"),
                     "folder": str(folder), "moves": moves}
            with open(LOG, "a", encoding="utf-8") as fh:
                fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
        print(f"\nMoved {len(moves)} installer(s) into {REVIEW}/. Nothing was deleted. "
              f"Undo anytime with --undo.")
    elif old:
        print("\nHappy with this list? Run again with --run. Undo anytime with --undo.")


def undo():
    if not LOG.exists():
        raise SystemExit("Nothing to undo (no review.log yet).")
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
        (Path(entry["folder"]) / REVIEW).rmdir()  # only if empty
    except OSError:
        pass
    LOG.write_text("".join(l + "\n" for l in lines[:-1]), encoding="utf-8")
    print(f"Undid the run from {entry['time']}: restored {restored} file(s), "
          f"{missing} no longer found.")


def main():
    p = argparse.ArgumentParser(description="Downloads space report + old installer cleanup.")
    p.add_argument("--folder", default=str(Path.home() / "Downloads"))
    p.add_argument("--run", action="store_true", help="move old installers to Review")
    p.add_argument("--undo", action="store_true", help="undo the last run")
    p.add_argument("--days", type=int, default=30, help="installer age in days (default 30)")
    a = p.parse_args()
    if a.undo:
        return undo()
    folder = Path(a.folder).expanduser()
    if not folder.is_dir():
        raise SystemExit(f"Folder not found: {folder}")
    report(folder, a.days, a.run)


if __name__ == "__main__":
    main()
