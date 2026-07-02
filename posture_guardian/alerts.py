import time


class AlertDebouncer:
    def __init__(self, consecutive_required: int, cooldown_seconds: float, clock=time.monotonic):
        self.consecutive_required = consecutive_required
        self.cooldown_seconds = cooldown_seconds
        self._clock = clock
        self._consecutive = {}
        self._last_fired = {}

    def update(self, state: str) -> bool:
        if state == "good":
            self._consecutive.clear()
            return False

        self._consecutive[state] = self._consecutive.get(state, 0) + 1
        if self._consecutive[state] < self.consecutive_required:
            return False

        now = self._clock()
        last = self._last_fired.get(state)
        if last is not None and (now - last) < self.cooldown_seconds:
            return False

        self._last_fired[state] = now
        self._consecutive[state] = 0
        return True


ALERT_MESSAGES = {
    "slouching": "Sit up straight",
    "too_close": "You're too close to the screen",
    "neck_bent": "Straighten your neck",
}


def show_overlay(message: str, duration_seconds: float = 4.0) -> None:
    import tkinter as tk

    root = tk.Tk()
    root.overrideredirect(True)
    root.attributes("-topmost", True)

    width, height = 340, 90
    screen_width = root.winfo_screenwidth()
    x = (screen_width - width) // 2
    y = 40
    root.geometry(f"{width}x{height}+{x}+{y}")

    frame = tk.Frame(root, bg="#1e1e1e", bd=2, relief="ridge")
    frame.pack(fill="both", expand=True)

    label = tk.Label(
        frame,
        text=message,
        fg="white",
        bg="#1e1e1e",
        font=("Helvetica", 16, "bold"),
        wraplength=300,
    )
    label.pack(expand=True)

    root.after(int(duration_seconds * 1000), root.destroy)
    root.mainloop()
