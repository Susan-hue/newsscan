"""Tells your phone when the monitoring stack itself is down.

Prometheus can't report its own death, and neither can anything running inside the same Docker network.
So this runs on the computer, outside Docker, every minute (a systemd timer). It checks three things:
  - Prometheus answers
  - Alertmanager answers
  - Prometheus can still reach Alertmanager (otherwise no alert could reach your phone)
A check must fail twice in a row (2 minutes) before the phone is told, so a quick restart stays quiet.

    python3 scripts/stack_watchdog.py              one run (what the timer does)
    python3 scripts/stack_watchdog.py --dry-run    checks, prints what it would send, sends and saves nothing
    python3 scripts/stack_watchdog.py --send-test  sends one normal-priority test message to the phone

It can't help if the whole computer is off or asleep. The secret topic is read from
platform/secrets/ntfy_topic and is never printed.
"""

import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

PLATFORM = Path(__file__).resolve().parents[1]
TOPIC_FILE = PLATFORM / "secrets" / "ntfy_topic"
STATE_FILE = Path.home() / ".local" / "state" / "newsscan" / "watchdog.json"
NTFY = "https://ntfy.sh"

FAILS_BEFORE_ALERT = 2  # in a row, one minute apart
REMIND_AFTER_SECONDS = 2 * 3600  # while it stays broken


def _get(url: str) -> bytes:
    with urllib.request.urlopen(url, timeout=5) as response:
        if response.status != 200:
            raise OSError(f"status {response.status}")
        return response.read()


def check_prometheus_runs() -> bool:
    _get("http://127.0.0.1:9090/-/healthy")
    return True


def check_alertmanager_runs() -> bool:
    _get("http://127.0.0.1:9093/-/healthy")
    return True


def check_prometheus_sees_alertmanager() -> bool:
    data = json.loads(_get("http://127.0.0.1:9090/api/v1/alertmanagers"))
    return len(data["data"]["activeAlertmanagers"]) >= 1


CHECKS = {
    "Prometheus is not answering": check_prometheus_runs,
    "Alertmanager is not answering": check_alertmanager_runs,
    "Prometheus can't reach Alertmanager": check_prometheus_sees_alertmanager,
}


def run_checks(checks: dict) -> dict[str, bool]:
    results = {}
    for name, check in checks.items():
        try:
            results[name] = bool(check())
        except (OSError, ValueError, KeyError, urllib.error.URLError):
            results[name] = False
    return results


def step(state: dict, results: dict[str, bool], now: float) -> tuple[dict, list[dict]]:
    """Pure decision: from the old state and this minute's results, the new state and the messages to send."""
    fails = {name: (state.get("fails", {}).get(name, 0) + 1 if not ok else 0) for name, ok in results.items()}
    broken = sorted(name for name, count in fails.items() if count >= FAILS_BEFORE_ALERT)
    alerted_at = state.get("alerted_at")
    messages: list[dict] = []
    if broken and (alerted_at is None or now - alerted_at >= REMIND_AFTER_SECONDS):
        messages.append(
            {
                "title": "PROBLEM: the monitoring stack",
                "text": "; ".join(broken) + ". Nothing is watching your app until this is fixed.",
                "priority": 5,
                "tags": "rotating_light",
            }
        )
        alerted_at = now
    elif not broken and alerted_at is not None:
        messages.append(
            {
                "title": "Fixed: the monitoring stack",
                "text": "Prometheus and Alertmanager are working again.",
                "priority": 3,
                "tags": "white_check_mark",
            }
        )
        alerted_at = None
    return {"fails": fails, "alerted_at": alerted_at}, messages


def read_topic() -> str:
    return TOPIC_FILE.read_text().strip()


def send(message: dict, topic: str) -> bool:
    request = urllib.request.Request(
        f"{NTFY}/{topic}",
        data=message["text"].encode(),
        headers={
            "Title": message["title"],
            "Priority": str(message["priority"]),
            "Tags": message["tags"],
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=10):
            return True
    except (OSError, urllib.error.URLError) as exc:
        # Say what went wrong without printing the address, which contains the secret topic.
        print(f"could not send the message: {type(exc).__name__}", file=sys.stderr)
        return False


def load_state(path: Path) -> dict:
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError):
        return {}


def save_state(path: Path, state: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(".tmp")
    temp.write_text(json.dumps(state))
    temp.replace(path)


def main(argv: list[str]) -> int:
    if "--send-test" in argv:
        ok = send(
            {"title": "Watchdog test", "text": "This is only a test.", "priority": 3, "tags": "test_tube"},
            read_topic(),
        )
        print("sent" if ok else "not sent")
        return 0 if ok else 1
    results = run_checks(CHECKS)
    new_state, messages = step(load_state(STATE_FILE), results, time.time())
    if "--dry-run" in argv:
        print({name: ("ok" if ok else "FAILING") for name, ok in results.items()})
        print("would send:", messages or "nothing")
        return 0
    if messages:
        topic = read_topic()
        if not all(send(message, topic) for message in messages):
            return 1  # keep the old state, so the next minute tries again
    save_state(STATE_FILE, new_state)
    failing = [name for name, ok in results.items() if not ok]
    print("ok" if not failing else "failing: " + ", ".join(failing))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
