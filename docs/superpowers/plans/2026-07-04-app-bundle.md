# Double-Clickable App Bundle Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let the user launch Posture Guardian by double-clicking `Posture Guardian.app` instead of running `python -m posture_guardian.main` from Terminal, with the exact same tray-only behavior (no Dock icon, no visible window) and a debuggable failure path if it can't start.

**Architecture:** A hand-built (not py2app/PyInstaller) `.app` bundle whose `Contents/MacOS/launch` is a bash script that resolves the project root relative to its own location and execs the existing venv's `python -m posture_guardian.main`. Pure builder functions (Info.plist XML, launcher script text, icon image) live in `posture_guardian/app_bundle.py` and are unit-tested; the impure orchestration (writing files, shelling out to `iconutil`/`plutil`) lives in `posture_guardian/build_app_cli.py`, invoked via a thin `build_app.sh` wrapper at the project root.

**Tech Stack:** Python 3.11 (existing venv), Pillow (already a dependency, used to draw the icon), stock macOS command-line tools (`iconutil`, `plutil`, `osascript`) — no new pip dependencies.

## Global Constraints

- Bundle identifier is `com.nuvirahub.postureguardian` — must match the existing `LAUNCH_AGENT_LABEL` in `posture_guardian/config.py:39`, for consistency (not functionally linked).
- `Info.plist` must set `LSUIElement` to `true` — this is what suppresses the Dock icon and is required, not optional.
- Do not modify `posture_guardian/launch_agent.py` or the "Launch at Login" tray feature — it already works by invoking the venv's Python directly and is out of scope.
- No new pip dependencies. Only Pillow (existing) plus stock macOS tools (`iconutil`, `plutil`, `osascript`, bash).
- Generated build artifacts (`Posture Guardian.app/`) must not be committed to git — add to `.gitignore`.
- Follow the existing project pattern: pure logic in importable/testable modules under `posture_guardian/`, impure OS-integration glue kept separate and thin (see `posture_guardian/launch_agent.py` and `posture_guardian/notifications.py` for the established style).

---

### Task 1: Pure builder functions — `app_bundle.py`

**Files:**
- Create: `posture_guardian/app_bundle.py`
- Test: `tests/test_app_bundle.py`

**Interfaces:**
- Consumes: nothing from other tasks.
- Produces (used by Task 2):
  - `build_info_plist_xml(bundle_id: str, executable_name: str, icon_file: str) -> str`
  - `build_launcher_script(log_path: str) -> str`
  - `build_icon_image(size: int) -> PIL.Image.Image` (mode `"RGBA"`, dimensions `(size, size)`)

- [ ] **Step 1: Write the failing tests for `build_info_plist_xml`**

Create `tests/test_app_bundle.py` with:

```python
from PIL import Image

from posture_guardian.app_bundle import build_icon_image, build_info_plist_xml, build_launcher_script


def test_build_info_plist_xml_contains_required_keys():
    xml = build_info_plist_xml("com.example.app", "launch", "icon.icns")
    assert "<key>CFBundleExecutable</key>" in xml
    assert "<string>launch</string>" in xml
    assert "<key>CFBundleIdentifier</key>" in xml
    assert "<string>com.example.app</string>" in xml
    assert "<key>CFBundleIconFile</key>" in xml
    assert "<string>icon.icns</string>" in xml
    assert "<key>LSUIElement</key>" in xml
    assert "<true/>" in xml
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_app_bundle.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'posture_guardian.app_bundle'`

- [ ] **Step 3: Implement `build_info_plist_xml`**

Create `posture_guardian/app_bundle.py` with:

```python
from PIL import Image, ImageDraw


def build_info_plist_xml(bundle_id: str, executable_name: str, icon_file: str) -> str:
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleExecutable</key>
    <string>{executable_name}</string>
    <key>CFBundleIdentifier</key>
    <string>{bundle_id}</string>
    <key>CFBundleIconFile</key>
    <string>{icon_file}</string>
    <key>CFBundleName</key>
    <string>Posture Guardian</string>
    <key>CFBundlePackageType</key>
    <string>APPL</string>
    <key>LSUIElement</key>
    <true/>
</dict>
</plist>
"""
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_app_bundle.py -v`
Expected: PASS (1 passed) — the other two functions aren't imported by name yet at call sites, but the test file already imports `build_icon_image` and `build_launcher_script`, so this step will actually fail on import. Add stub-free real implementations in the same step instead — see Step 3 continues below before running.

Note for implementer: since the test file's import line pulls in all three functions at once, write all three functions in Step 3 before running pytest in Step 4 (Steps 5-8 below just add more *assertions*, not new imports). Proceed to Step 5 immediately, then run the full file once.

- [ ] **Step 5: Write the failing tests for `build_launcher_script`**

Append to `tests/test_app_bundle.py`:

```python
def test_build_launcher_script_execs_module_with_log_redirect():
    script = build_launcher_script("/tmp/example/launch_error.log")
    assert script.startswith("#!/usr/bin/env bash")
    assert "posture_guardian.main" in script
    assert "/tmp/example/launch_error.log" in script
    assert "osascript" in script


def test_build_launcher_script_resolves_path_relative_to_itself():
    script = build_launcher_script("/tmp/example/launch_error.log")
    assert "BASH_SOURCE" in script
    assert ".venv/bin/python" in script
```

- [ ] **Step 6: Implement `build_launcher_script`**

Append to `posture_guardian/app_bundle.py`:

```python
def build_launcher_script(log_path: str) -> str:
    return f"""#!/usr/bin/env bash
set -u
SCRIPT_DIR="$(cd "$(dirname "${{BASH_SOURCE[0]}}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
LOG_PATH="{log_path}"
mkdir -p "$(dirname "$LOG_PATH")"
: > "$LOG_PATH"
"$PROJECT_ROOT/.venv/bin/python" -m posture_guardian.main 2>> "$LOG_PATH"
STATUS=$?
if [ "$STATUS" -ne 0 ]; then
    osascript -e 'display notification "Check ~/.posture_guardian/launch_error.log for details" with title "Posture Guardian failed to start"'
fi
exit $STATUS
"""
```

- [ ] **Step 7: Write the failing tests for `build_icon_image`**

Append to `tests/test_app_bundle.py`:

```python
def test_build_icon_image_returns_requested_size_rgba():
    image = build_icon_image(256)
    assert image.size == (256, 256)
    assert image.mode == "RGBA"


def test_build_icon_image_corners_are_transparent():
    image = build_icon_image(256)
    r, g, b, a = image.getpixel((0, 0))
    assert a == 0


def test_build_icon_image_center_is_opaque():
    image = build_icon_image(256)
    r, g, b, a = image.getpixel((128, 128))
    assert a > 0
```

- [ ] **Step 8: Implement `build_icon_image`**

Append to `posture_guardian/app_bundle.py`:

```python
def build_icon_image(size: int) -> Image.Image:
    image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)

    margin = size * 0.08
    draw.ellipse((margin, margin, size - margin, size - margin), fill=(108, 99, 255, 255))

    cx = size / 2
    head_r = size * 0.14
    head_cy = size * 0.34
    draw.ellipse(
        (cx - head_r, head_cy - head_r, cx + head_r, head_cy + head_r),
        fill=(240, 240, 248, 255),
    )

    body_w = size * 0.34
    body_top = head_cy + head_r * 0.6
    body_bottom = size * 0.78
    draw.rounded_rectangle(
        (cx - body_w / 2, body_top, cx + body_w / 2, body_bottom),
        radius=size * 0.08,
        fill=(240, 240, 248, 255),
    )
    return image
```

- [ ] **Step 9: Run the full test file to verify everything passes**

Run: `.venv/bin/python -m pytest tests/test_app_bundle.py -v`
Expected: `8 passed`

- [ ] **Step 10: Run the full project test suite to check for regressions**

Run: `.venv/bin/python -m pytest -q`
Expected: `49 passed` (41 existing + 8 new)

- [ ] **Step 11: Commit**

```bash
git add posture_guardian/app_bundle.py tests/test_app_bundle.py
git commit -m "Add pure builder functions for the app bundle (plist, launcher script, icon)"
```

---

### Task 2: Orchestration CLI + shell wrapper — build and verify the bundle

**Files:**
- Create: `posture_guardian/build_app_cli.py`
- Create: `build_app.sh` (project root)
- Modify: `.gitignore` — add `Posture Guardian.app/`

**Interfaces:**
- Consumes: `build_info_plist_xml`, `build_launcher_script`, `build_icon_image` from `posture_guardian/app_bundle.py` (Task 1).
- Produces: a runnable `build_app.sh` at the project root; no other task depends on this one's internals.

- [ ] **Step 1: Add the generated bundle to `.gitignore`**

Read the current `.gitignore`, then add a line `Posture Guardian.app/` to it (it currently contains `__pycache__/`, `*.pyc`, `.venv/`, `*.db`, `.DS_Store`, `.superpowers/`).

- [ ] **Step 2: Write `posture_guardian/build_app_cli.py`**

```python
import argparse
import subprocess
from pathlib import Path

from PIL import Image

from posture_guardian.app_bundle import build_icon_image, build_info_plist_xml, build_launcher_script

BUNDLE_NAME = "Posture Guardian.app"
BUNDLE_ID = "com.nuvirahub.postureguardian"
LOG_PATH = str(Path.home() / ".posture_guardian" / "launch_error.log")

_ICONSET_SIZES = (16, 32, 128, 256, 512)


def find_project_root() -> Path:
    return Path(__file__).resolve().parent.parent


def generate_icns(resources_dir: Path) -> None:
    resources_dir.mkdir(parents=True, exist_ok=True)
    iconset_dir = resources_dir / "icon.iconset"
    iconset_dir.mkdir(exist_ok=True)

    source = build_icon_image(1024)
    for size in _ICONSET_SIZES:
        source.resize((size, size), Image.LANCZOS).save(iconset_dir / f"icon_{size}x{size}.png")
        source.resize((size * 2, size * 2), Image.LANCZOS).save(iconset_dir / f"icon_{size}x{size}@2x.png")

    subprocess.run(
        ["iconutil", "--convert", "icns", "--output", str(resources_dir / "icon.icns"), str(iconset_dir)],
        check=True,
    )
    for f in iconset_dir.iterdir():
        f.unlink()
    iconset_dir.rmdir()


def build_bundle(project_root: Path, force_icon: bool) -> Path:
    bundle_dir = project_root / BUNDLE_NAME
    contents_dir = bundle_dir / "Contents"
    macos_dir = contents_dir / "MacOS"
    resources_dir = contents_dir / "Resources"
    macos_dir.mkdir(parents=True, exist_ok=True)
    resources_dir.mkdir(parents=True, exist_ok=True)

    (contents_dir / "Info.plist").write_text(build_info_plist_xml(BUNDLE_ID, "launch", "icon.icns"))

    launcher_path = macos_dir / "launch"
    launcher_path.write_text(build_launcher_script(LOG_PATH))
    launcher_path.chmod(0o755)

    icns_path = resources_dir / "icon.icns"
    if force_icon or not icns_path.exists():
        generate_icns(resources_dir)

    subprocess.run(["plutil", "-lint", str(contents_dir / "Info.plist")], check=True)
    return bundle_dir


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true", help="Regenerate the icon even if it already exists")
    args = parser.parse_args()

    project_root = find_project_root()
    bundle_dir = build_bundle(project_root, force_icon=args.force)
    print(f"Built {bundle_dir}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 3: Write `build_app.sh`**

```bash
#!/usr/bin/env bash
set -euo pipefail
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec "$DIR/.venv/bin/python" -m posture_guardian.build_app_cli "$@"
```

Make it executable: `chmod +x build_app.sh`

- [ ] **Step 4: Run the build and verify bundle structure**

Run: `./build_app.sh`
Expected: prints `Built /Users/ranjana/Harsha/Projects/Posture-Screen-Time-Guardian-/Posture Guardian.app` with no errors (the `plutil -lint` call inside `build_bundle` would raise `CalledProcessError` and abort if the plist were malformed).

- [ ] **Step 5: Verify `Info.plist` independently**

Run: `plutil -lint "Posture Guardian.app/Contents/Info.plist"`
Expected: `Posture Guardian.app/Contents/Info.plist: OK`

- [ ] **Step 6: Verify the launcher script is executable and correct**

Run: `test -x "Posture Guardian.app/Contents/MacOS/launch" && echo LAUNCHER_EXECUTABLE`
Expected: `LAUNCHER_EXECUTABLE`

Run: `cat "Posture Guardian.app/Contents/MacOS/launch"`
Expected: output matches the template from `build_launcher_script`, with `LOG_PATH="/Users/ranjana/.posture_guardian/launch_error.log"` substituted in.

- [ ] **Step 7: Verify the icon was generated**

Run: `test -s "Posture Guardian.app/Contents/Resources/icon.icns" && echo ICON_OK`
Expected: `ICON_OK`

- [ ] **Step 8: Verify the bundle actually launches the app**

Run: `open "Posture Guardian.app"`

Wait 3 seconds, then run: `pgrep -f posture_guardian.main`
Expected: a single PID is printed (the process is running).

Clean up: `pkill -f posture_guardian.main`

- [ ] **Step 9: Verify the failure path (missing venv) logs and notifies**

Run:
```bash
mv .venv .venv-temp-hidden
"Posture Guardian.app/Contents/MacOS/launch"; echo "exit code: $?"
```
Expected: non-zero exit code printed (the `exec` of a nonexistent `.venv/bin/python` fails). A macOS notification titled "Posture Guardian failed to start" should appear.

Run: `cat ~/.posture_guardian/launch_error.log`
Expected: file exists (may be empty, since the failure happens before the redirected python process starts producing stderr — the exit-code check and notification still fire either way, which is what step matters for: no silent failure).

Restore: `mv .venv-temp-hidden .venv`

- [ ] **Step 10: Run the full project test suite to check for regressions**

Run: `.venv/bin/python -m pytest -q`
Expected: `49 passed`

- [ ] **Step 11: Commit**

```bash
git add posture_guardian/build_app_cli.py build_app.sh .gitignore
git commit -m "Add build_app.sh to package Posture Guardian as a double-clickable .app"
```

---

## Post-plan note for the user

After Task 2 lands, tell the user:
- Run `./build_app.sh` once from the project root.
- Drag `Posture Guardian.app` to `/Applications` if they want it there, or just double-click it in place — either works since the launcher resolves its own project root at runtime via `dirname`, not a baked-in path (as long as the `.app` and the project folder stay together).
- Re-run `./build_app.sh` any time `posture_guardian/app_bundle.py` changes; pass `--force` to also regenerate the icon.
