# Posture Guardian — Double-Clickable App Bundle

## Goals
- Let the user launch Posture Guardian by double-clicking an icon in Finder (or `/Applications`), instead of opening Terminal, activating the venv, and running `python -m posture_guardian.main`.
- Preserve today's behavior exactly: menu-bar tray icon only, no Dock icon, no visible Terminal window.
- Fail loudly enough to be debuggable, even though there's no Terminal attached — a double-clicked app that silently dies is worse than the current friction.

## Non-goals
- Not building a fully self-contained/relocatable `.app` (no py2app / PyInstaller). opencv and mediapipe are large native-extension dependencies that are known to be fragile to bundle this way, and the payoff (moving the app to another folder or Mac) isn't a stated need.
- Not changing the existing "Launch at Login" tray menu feature (`posture_guardian/launch_agent.py`), which already works by invoking the venv's Python directly via a `LaunchAgent` plist. It's left untouched.
- Not adding a Dock icon, window, or any visible chrome — this app is and remains tray-only.

## Design

### Bundle layout
A hand-built bundle at the project root, `Posture Guardian.app/`:
```
Posture Guardian.app/
  Contents/
    Info.plist
    MacOS/
      launch                 (executable bash script — the bundle's entry point)
    Resources/
      icon.icns
```

`Info.plist` declares:
- `CFBundleExecutable` = `launch`
- `CFBundleIdentifier` = `com.nuvirahub.postureguardian` (same identifier already used by the LaunchAgent in `launch_agent.py`, for consistency)
- `CFBundleIconFile` = `icon.icns`
- `LSUIElement` = `1` — this is what suppresses the Dock icon; it's the standard mechanism macOS gives background/menu-bar-only apps.

### Launcher script (`Contents/MacOS/launch`)
A bash script, resolved relative to its own location (via `dirname`) so the bundle isn't hardcoded to today's absolute path — it walks up from `Contents/MacOS/` to the project root, then execs:
```
"$PROJECT_ROOT/.venv/bin/python" -m posture_guardian.main
```
stderr is redirected to `~/.posture_guardian/launch_error.log` (truncated on each launch). If the python process exits non-zero, the script fires a native notification via `osascript` pointing the user at that log file, using the same `_applescript_quote` escaping pattern already established in `posture_guardian/notifications.py` (reimplemented in shell since this script runs before any Python module is importable).

### Icon generation
A one-time-per-build step inside `build_app.sh`: a small inline Python snippet uses PIL (already a dependency) to draw a simple flat glyph (e.g. a circle with a simple seated-figure silhouette) at 1024×1024, saves as PNG, then shells out to `sips` (resize into the iconset's required sizes) and `iconutil --convert icns` (both are standard macOS command-line tools, no new dependency) to produce `icon.icns`.

### Build script (`build_app.sh`)
Idempotent — deletes and recreates `Posture Guardian.app/` each run. Responsibilities:
1. Create the directory structure.
2. Write `Info.plist`.
3. Write and `chmod +x` the launcher script.
4. Generate the icon (skipped if `Resources/icon.icns` already exists and `--force` isn't passed, so re-running after unrelated changes is fast).

Re-running this script is how the user rebuilds the bundle after moving the project folder or making launcher changes.

## Data flow
1. User double-clicks `Posture Guardian.app` in Finder.
2. macOS LaunchServices runs `Contents/MacOS/launch`.
3. The script execs the venv's Python running `posture_guardian.main`, exactly as if the user had typed the command in Terminal themselves.
4. `PostureGuardianApp` starts as today: camera warm-up (triggers the camera permission prompt on first-ever run, same as before), tray icon appears, detection loop starts.
5. If the process exits non-zero before the tray icon can appear (e.g. missing venv, missing dependency), the launcher script's error trap fires a notification and writes the log.

## Error handling
- Missing `.venv/bin/python`: the launcher's `exec` fails immediately; trapped, logged, notified.
- Any Python-level startup exception (e.g. a dependency import error): non-zero exit, same trap.
- Camera permission not yet granted: unchanged from today — first run prompts via the existing main-thread warm-up in `tray_app.py:start()`.

## Testing
This is packaging/OS-integration work with no pure business logic to unit-test, so there's no addition to `tests/`. Verification is manual/scripted:
- `build_app.sh` runs cleanly and produces a well-formed bundle (valid `Info.plist` via `plutil -lint`, executable launcher, non-empty `icon.icns`).
- `open "Posture Guardian.app"` actually launches the process (verified via `pgrep -f posture_guardian.main`), and it stays running (no immediate crash) with no `launch_error.log` written.
- Deliberately breaking the launcher (e.g. renaming `.venv`) to confirm the failure path: process exits non-zero, log file appears, notification fires.
- Full camera-based tray-icon-appears verification is left to the user, same limitation as all prior camera-dependent work in this project.

## Tech / tooling
- No new pip dependencies. Uses: bash, `sips`, `iconutil`, `osascript`, `plutil` — all stock on macOS.
- `PIL` (already in `requirements.txt`) is used to generate the source PNG for the icon.
