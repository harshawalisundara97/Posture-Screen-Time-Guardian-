import subprocess


def build_summary_message(date: str, score: float, previous_score: float | None) -> str:
    line = f"{date}: {score:.0f}% good posture"
    if previous_score is None:
        return line
    delta = score - previous_score
    if abs(delta) < 0.5:
        return f"{line} (same as previous day)"
    arrow = "up" if delta > 0 else "down"
    return f"{line} ({arrow} {abs(delta):.0f} pts vs previous day)"


def _applescript_quote(text: str) -> str:
    escaped = text.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def send_native_notification(title: str, message: str) -> None:
    script = f"display notification {_applescript_quote(message)} with title {_applescript_quote(title)}"
    subprocess.run(["osascript", "-e", script], check=False)
