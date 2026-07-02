from posture_guardian.alerts import AlertDebouncer


class FakeClock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += seconds


def test_no_alert_before_consecutive_threshold_reached():
    clock = FakeClock()
    debouncer = AlertDebouncer(consecutive_required=3, cooldown_seconds=60.0, clock=clock)
    assert debouncer.update("slouching") is False
    assert debouncer.update("slouching") is False


def test_alert_fires_once_threshold_reached():
    clock = FakeClock()
    debouncer = AlertDebouncer(consecutive_required=3, cooldown_seconds=60.0, clock=clock)
    debouncer.update("slouching")
    debouncer.update("slouching")
    assert debouncer.update("slouching") is True


def test_alert_does_not_refire_during_cooldown():
    clock = FakeClock()
    debouncer = AlertDebouncer(consecutive_required=1, cooldown_seconds=60.0, clock=clock)
    assert debouncer.update("slouching") is True
    assert debouncer.update("slouching") is False


def test_alert_refires_after_cooldown_elapses():
    clock = FakeClock()
    debouncer = AlertDebouncer(consecutive_required=1, cooldown_seconds=60.0, clock=clock)
    assert debouncer.update("slouching") is True
    clock.advance(61.0)
    assert debouncer.update("slouching") is True


def test_good_state_resets_consecutive_counter():
    clock = FakeClock()
    debouncer = AlertDebouncer(consecutive_required=3, cooldown_seconds=60.0, clock=clock)
    debouncer.update("slouching")
    debouncer.update("slouching")
    debouncer.update("good")
    assert debouncer.update("slouching") is False
    assert debouncer.update("slouching") is False
    assert debouncer.update("slouching") is True


def test_different_states_tracked_independently():
    clock = FakeClock()
    debouncer = AlertDebouncer(consecutive_required=1, cooldown_seconds=60.0, clock=clock)
    assert debouncer.update("slouching") is True
    assert debouncer.update("neck_bent") is True
