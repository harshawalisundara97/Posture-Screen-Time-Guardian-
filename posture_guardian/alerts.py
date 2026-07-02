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
