import datetime
import tkinter as tk

from posture_guardian.scoring import compute_score
from posture_guardian.storage import get_daily_stats, get_recent_stats


def show_dashboard(conn) -> None:
    today = datetime.date.today().isoformat()
    today_stats = get_daily_stats(conn, today)
    today_score = compute_score(today_stats["good_seconds"], today_stats["monitored_seconds"])
    recent = get_recent_stats(conn, days=7)

    root = tk.Tk()
    root.title("Posture Guardian — Dashboard")
    root.geometry("320x360")

    tk.Label(root, text="Today's Posture Score", font=("Helvetica", 14, "bold")).pack(pady=(16, 4))
    tk.Label(root, text=f"{today_score:.0f}%", font=("Helvetica", 32, "bold")).pack(pady=(0, 16))

    tk.Label(root, text="Last 7 days", font=("Helvetica", 12, "bold")).pack(pady=(8, 4))

    history_frame = tk.Frame(root)
    history_frame.pack(fill="both", expand=True, padx=16)

    for row in recent:
        score = compute_score(row["good_seconds"], row["monitored_seconds"])
        tk.Label(history_frame, text=f"{row['date']}: {score:.0f}%", anchor="w").pack(fill="x")

    root.mainloop()
