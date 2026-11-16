import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "stack_watchdog", Path(__file__).parents[1] / "scripts" / "stack_watchdog.py"
)
wd = importlib.util.module_from_spec(spec)
spec.loader.exec_module(wd)

OK = {"a": True, "b": True}
BAD = {"a": False, "b": True}


def test_everything_fine_says_nothing():
    state, messages = wd.step({}, OK, now=0)
    assert messages == [] and state["alerted_at"] is None


def test_one_failed_minute_stays_quiet_two_in_a_row_alerts():
    state, messages = wd.step({}, BAD, now=0)
    assert messages == []
    state, messages = wd.step(state, BAD, now=60)
    assert len(messages) == 1
    assert messages[0]["priority"] == 5 and "a" in messages[0]["text"] and "b" not in messages[0]["text"]


def test_a_blip_in_between_resets_the_count():
    state, _ = wd.step({}, BAD, now=0)
    state, _ = wd.step(state, OK, now=60)
    state, messages = wd.step(state, BAD, now=120)
    assert messages == []


def test_it_does_not_repeat_every_minute_but_reminds_after_two_hours():
    state, _ = wd.step({}, BAD, now=0)
    state, first = wd.step(state, BAD, now=60)
    assert len(first) == 1
    state, again = wd.step(state, BAD, now=120)
    assert again == []
    state, later = wd.step(state, BAD, now=60 + wd.REMIND_AFTER_SECONDS)
    assert len(later) == 1


def test_recovery_sends_one_fixed_message():
    state, _ = wd.step({}, BAD, now=0)
    state, _ = wd.step(state, BAD, now=60)
    state, messages = wd.step(state, OK, now=120)
    assert len(messages) == 1 and messages[0]["title"].startswith("Fixed")
    state, messages = wd.step(state, OK, now=180)
    assert messages == []


def test_a_check_that_raises_counts_as_failing_not_as_a_crash():
    def boom():
        raise OSError("connection refused")

    assert wd.run_checks({"x": boom, "y": lambda: True}) == {"x": False, "y": True}


def test_state_survives_a_missing_or_broken_file(tmp_path):
    assert wd.load_state(tmp_path / "nope.json") == {}
    broken = tmp_path / "broken.json"
    broken.write_text("{not json")
    assert wd.load_state(broken) == {}
    wd.save_state(tmp_path / "ok.json", {"fails": {"a": 1}})
    assert wd.load_state(tmp_path / "ok.json") == {"fails": {"a": 1}}


def test_a_failed_send_never_prints_the_secret_topic(capsys, monkeypatch):
    def refuse(*args, **kwargs):
        raise OSError("https://ntfy.sh/SECRET-TOPIC refused")

    monkeypatch.setattr(wd.urllib.request, "urlopen", refuse)
    assert wd.send({"title": "t", "text": "x", "priority": 3, "tags": "t"}, "SECRET-TOPIC") is False
    assert "SECRET-TOPIC" not in capsys.readouterr().err
