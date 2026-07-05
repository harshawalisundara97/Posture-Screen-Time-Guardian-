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
