import datetime
import json
import tkinter as tk
from pathlib import Path

from PIL import Image, ImageTk

from posture_guardian import config
from posture_guardian.scoring import compute_score
from posture_guardian.storage import get_daily_stats, get_recent_stats

_STATUS_DISPLAY = {
    "good": ("Good posture", "#2e7d32"),
    "slouching": ("Slouching — sit up straight", "#c62828"),
    "too_close": ("Too close to screen", "#c62828"),
    "neck_bent": ("Neck bent — straighten up", "#c62828"),
    "not_calibrated": ("Not calibrated yet — use Calibrate", "#757575"),
    "no_person": ("No one detected in frame", "#757575"),
    "no_camera": ("Camera not available", "#757575"),
    "paused": ("Monitoring paused", "#757575"),
    "calibrating": ("Calibrating...", "#757575"),
}

_METRIC_LABELS = (
    ("neck_angle", "Neck angle"),
    ("shoulder_tilt", "Shoulder tilt"),
    ("forward_lean", "Forward lean"),
)


def _read_live_data() -> dict:
    try:
        with open(config.STATUS_PATH) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _touch_preview_request() -> None:
    Path(config.PREVIEW_REQUEST_PATH).touch()


def show_dashboard(conn) -> None:
    today = datetime.date.today().isoformat()
    today_stats = get_daily_stats(conn, today)
    today_score = compute_score(today_stats["good_seconds"], today_stats["monitored_seconds"])
    recent = list(reversed(get_recent_stats(conn, days=7)))

    root = tk.Tk()
    root.title("Posture Guardian — Dashboard")
    root.geometry("360x600")

    live_label = tk.Label(root, text="", font=("Helvetica", 13, "bold"), wraplength=320)
    live_label.pack(pady=(16, 8))

    metrics_frame = tk.Frame(root)
    metrics_frame.pack(pady=(0, 12))
    metric_value_labels = {}
    for key, caption in _METRIC_LABELS:
        row = tk.Frame(metrics_frame)
        row.pack(fill="x")
        tk.Label(row, text=f"{caption}:", width=14, anchor="w", font=("Helvetica", 10)).pack(side="left")
        value_label = tk.Label(row, text="—", width=22, anchor="w", font=("Helvetica", 10, "bold"))
        value_label.pack(side="left")
        metric_value_labels[key] = value_label

    preview_var = tk.BooleanVar(value=False)
    preview_label = tk.Label(root, text="", bg="black")

    def toggle_preview():
        if preview_var.get():
            preview_label.pack(pady=(0, 12))
        else:
            preview_label.pack_forget()
            preview_label.config(image="")

    tk.Checkbutton(
        root,
        text="Show live camera preview (uses more CPU)",
        variable=preview_var,
        command=toggle_preview,
    ).pack(pady=(0, 4))

    def refresh_live():
        data = _read_live_data()
        text, color = _STATUS_DISPLAY.get(data.get("state"), ("Waiting for detection to start...", "#757575"))
        live_label.config(text=text, fg=color)

        metrics = data.get("metrics")
        baseline = data.get("baseline")
        for key, _ in _METRIC_LABELS:
            if metrics and baseline:
                delta = metrics[key] - baseline[key]
                metric_value_labels[key].config(text=f"{metrics[key]:.3f}  (baseline {baseline[key]:.3f}, Δ{delta:+.3f})")
            else:
                metric_value_labels[key].config(text="—")

        if preview_var.get():
            _touch_preview_request()
            try:
                img = Image.open(config.PREVIEW_JPEG_PATH)
                img = img.resize((320, 240))
                photo = ImageTk.PhotoImage(img)
                preview_label.config(image=photo, text="")
                preview_label.image = photo
            except (FileNotFoundError, OSError):
                preview_label.config(image="", text="Waiting for camera frame...")

        root.after(500, refresh_live)

    refresh_live()

    tk.Label(root, text="Today's Posture Score", font=("Helvetica", 14, "bold")).pack(pady=(8, 4))
    tk.Label(root, text=f"{today_score:.0f}%", font=("Helvetica", 32, "bold")).pack(pady=(0, 12))

    tk.Label(root, text="Last 7 days", font=("Helvetica", 12, "bold")).pack(pady=(4, 4))

    chart = tk.Canvas(root, width=320, height=140, highlightthickness=0)
    chart.pack(pady=(0, 8))

    bar_width = 320 / max(len(recent), 1)
    for i, row in enumerate(recent):
        score = compute_score(row["good_seconds"], row["monitored_seconds"])
        bar_height = max(2, score / 100 * 110)
        x0 = i * bar_width + 4
        x1 = (i + 1) * bar_width - 4
        y1 = 120
        y0 = y1 - bar_height
        color = "#2e7d32" if score >= 70 else ("#f9a825" if score >= 40 else "#c62828")
        chart.create_rectangle(x0, y0, x1, y1, fill=color, outline="")
        chart.create_text((x0 + x1) / 2, y1 + 10, text=row["date"][5:], font=("Helvetica", 7))
        chart.create_text((x0 + x1) / 2, y0 - 8, text=f"{score:.0f}", font=("Helvetica", 7))

    root.mainloop()
