import subprocess
from pathlib import Path


def build_plist_xml(label: str, python_executable: str, module: str) -> str:
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>{label}</string>
    <key>ProgramArguments</key>
    <array>
        <string>{python_executable}</string>
        <string>-m</string>
        <string>{module}</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <false/>
</dict>
</plist>
"""


def is_enabled(plist_path: str) -> bool:
    return Path(plist_path).exists()


def enable(plist_path: str, label: str, python_executable: str, module: str) -> None:
    Path(plist_path).parent.mkdir(parents=True, exist_ok=True)
    Path(plist_path).write_text(build_plist_xml(label, python_executable, module))
    subprocess.run(["launchctl", "load", plist_path], check=False)


def disable(plist_path: str, label: str) -> None:
    subprocess.run(["launchctl", "unload", plist_path], check=False)
    Path(plist_path).unlink(missing_ok=True)
