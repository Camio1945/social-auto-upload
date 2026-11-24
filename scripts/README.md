# Autostart helpers

Starts the Flask backend (`sau_backend.py`, port 5409) and the Vite frontend
(`sau_frontend`, port 5173) automatically when you sign in to Windows — with no
console windows and no admin rights required.

## Install

Double-click `install-autostart.bat`, or from a terminal:

```bat
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\install-autostart.ps1
```

It does three things:

1. Records `python.exe` / `pythonw.exe` / `node.exe` absolute paths in
   `scripts\paths.json` (git-ignored), so the launcher works even if `node` is
   not on the PATH at logon time.
2. Creates `Social Auto Upload.lnk` in
   `%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup`.
3. Starts both servers right away (skip with `-NoStart`).

## Everyday use

```bat
.venv\Scripts\pythonw.exe scripts\launcher.pyw          :: start both
.venv\Scripts\pythonw.exe scripts\launcher.pyw status   :: what is running
.venv\Scripts\pythonw.exe scripts\launcher.pyw stop     :: stop both
```

Starting is idempotent: any port already serving is skipped, so running the
command twice (or at logon while a dev server is open) never creates duplicates.

| Service  | URL                      | Log                   |
| -------- | ------------------------ | --------------------- |
| backend  | http://localhost:5409    | `logs\backend.log`    |
| frontend | http://localhost:5173    | `logs\frontend.log`   |
| launcher | —                        | `logs\launcher.log`   |

Logs rotate to `.1` once they pass 5 MB.

## Uninstall

Double-click `uninstall-autostart.bat`. This removes the Startup shortcut and
`paths.json`; it does not touch running servers or logs.

## Notes

- Startup happens at **sign-in**, not at boot, which is what a desktop GUI app
  needs (a browser session must exist anyway).
- The browser is not opened automatically at logon (`BROWSER=none`). Open
  http://localhost:5173 yourself, or drop that line in `launcher.pyw` to change it.
- If you move the project to another drive or reinstall Node.js, rerun the
  installer so `paths.json` matches the new locations.
- Alternative to the Startup folder: Task Scheduler with trigger "At log on"
  pointing at `.venv\Scripts\pythonw.exe scripts\launcher.pyw` — useful if you
  want a delay or to run before Explorer is ready.
