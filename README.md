# downloads-toolkit

Three small Python scripts that clean up a messy Downloads folder and show where the space went, with a way back built in.

My Downloads folder had 463 files in it. Version 1 of the sorter had no undo and moved project files I didn't want touched. Nothing was lost, but fixing it by hand was painful. So all three scripts here log every move and can undo the last run.

Built with AI's help. No installs needed, just Python 3.8+.

## What's in here

| Script | What it does |
|---|---|
| `organize_downloads.py` | Sorts loose files into folders by type (Images, PDFs, Documents, Spreadsheets, Videos, Audio, Archives, Installers, Code, Other) |
| `find_duplicates.py` | Finds files with identical content (by hash, not by name) and moves the extra copies into a `Duplicates` folder |
| `downloads_report.py` | Shows where the space went (size per folder, biggest files) and moves installers older than 30 days into a `Review` folder |

None of the scripts delete anything.

## Safety

- **Preview first.** Without `--run`, all three scripts only show what they would do.
- **Undo.** Every `--run` is written to a log next to the script (`moves.log`, `duplicates.log`, `review.log`). `--undo` reverses the last run. Run it again to go back one more.
- **Never overwrites.** If a name is taken, the file gets `(1)`, `(2)`, ... added.
- **Project-aware.** Files like `package.json`, `Dockerfile`, `requirements.txt`, `docker-compose.yml`, README/LICENSE files and `.env*` are left alone. So are `.ini`, `.lnk`, `.log`, hidden files, and unfinished downloads (`.crdownload`, `.part`, `.tmp`). Folders are never moved. The skip list is at the top of each script, so you can edit it.
- **Recent files are skipped.** `organize_downloads.py` ignores files newer than 30 minutes (`--min-age`), so a download in progress isn't touched.

## organize_downloads.py

```
python organize_downloads.py                  # preview
python organize_downloads.py --run            # move files
python organize_downloads.py --undo           # undo the last run
python organize_downloads.py --run --skip Code,Documents   # leave these categories alone
python organize_downloads.py --folder "D:\Some\Folder" --min-age 0
```

## find_duplicates.py

```
python find_duplicates.py                     # preview
python find_duplicates.py --run               # move duplicates to Downloads\Duplicates
python find_duplicates.py --undo              # put the last run back
```

How it works: files are grouped by size first, then only files with the same size are hashed (SHA-256). Files with the same hash are exact copies. In each group it keeps the file whose name looks like the original (no `(1)` or `Copy`), then the shortest name, then the oldest.

It scans the top of the folder plus the category folders made by `organize_downloads.py`. Project folders are not scanned.

Files named `Resume (1)`, `Resume (2)`, ... are not necessarily copies. In my own folder, a whole series like that turned out to be all different files. That's why it compares contents.

Read the preview before using `--run`. If a "KEEP" file isn't the one you want, don't run it for that group.

## downloads_report.py

```
python downloads_report.py                    # report only
python downloads_report.py --run              # move old installers to Downloads\Review
python downloads_report.py --undo             # put the last run back
python downloads_report.py --days 60          # what counts as "old" (default 30)
```

The report shows total size, size per folder, the 10 biggest files, and installers older than `--days` (`.exe`, `.msi`, `.dmg`, `.pkg`, `.deb`, `.apk`). `--run` moves only those installers into a `Review` folder. Files already in `Duplicates` or `Review` are never picked up.

Age is counted from when the file was created (downloaded) on Windows, and from last modified elsewhere. Some old installers can't be downloaded again (old versions, dead links), so read the list before using `--run`. Delete the `Review` folder yourself once you're sure.

## Run it every day (Windows)

Find your pythonw path:

```
where pythonw
```

Then create the task (replace `PYTHONW_PATH` and the script path with yours, and add `--skip` if you want):

```
schtasks /Create /TN "OrganizeDownloads" /SC DAILY /ST 21:00 /F /TR "\"PYTHONW_PATH\" \"%USERPROFILE%\Desktop\organize_downloads.py\" --run --quiet"
```

Notes:
- `pythonw` has no window, so errors are invisible. After the first run, check that `moves.log` appeared next to the script. "Last Result: 0" in Task Scheduler only means the task started, not that the script worked.
- By default Task Scheduler won't run on battery. To allow it and to catch up on missed runs:
  ```
  powershell -Command "$s = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable; Set-ScheduledTask -TaskName 'OrganizeDownloads' -Settings $s"
  ```
- Don't schedule `find_duplicates.py` or `downloads_report.py --run`. Deciding what counts as a duplicate or an old installer is better done by looking at the list once.

## Tested on

Windows 10 with Python 3.12, on a real Downloads folder. `organize_downloads.py`: a scheduled run, and undo on a few test files. `find_duplicates.py`: undo of 96 files. `downloads_report.py`: undo of 13 installers. The logic was also tested on Linux. macOS should work but I haven't tried it.

## Known limits

- Sorting is by file extension only, so it can't tell that `config.py` belongs to a project. That's what the skip list is for.
- Undo reverses the most recent run only, and only if the files are still where the script put them.
- If a file is open in another program, the move is skipped and reported.
- `downloads_report.py` only looks at the top of the folder and the category folders, not project folders.

## License

MIT. See `LICENSE`.
