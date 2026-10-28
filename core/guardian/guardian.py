#!/usr/bin/env python3
"""
guardian.py — nobreak-omarchy power guardian: watches a UPS through NUT
(upsc) and reacts to power events. Driver-agnostic: works with any UPS that
NUT can read.

What it does:
  * polls `upsc <ups>` every N seconds (default 5)
  * detects transitions: power outage (OL->OB), power restored (OB->OL),
    low battery (LB)
  * records each event as one JSON line in
    ~/.local/state/nobreak-omarchy/events.jsonl (post-mortem friendly)
  * sends a desktop notification (notify-send — Hyprland/GNOME/KDE)
  * optional: runs a command on events (--on-cmd / --restore-cmd)

No root needed: upsc is a TCP client of upsd (localhost:3493).
Run it as a user service (systemd --user), see nobreak-guardian.service.

Usage:
  guardian.py                                   # watch 'nobreak@localhost' every 5s
  guardian.py --ups other@localhost --interval 10
  guardian.py --once                            # single reading (test)
  guardian.py --dry-run                         # simulate events to test notifications
  guardian.py --on-cmd 'systemctl suspend'      # action on power outage

Environment:
  NOBREAK_STATE_DIR   override the state dir (default ~/.local/state/nobreak-omarchy)
"""

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

STATE_DIR = Path(os.environ.get("NOBREAK_STATE_DIR",
                                Path.home() / ".local/state/nobreak-omarchy"))
EVENTS_FILE = STATE_DIR / "events.jsonl"

# events that trigger a critical notification
CRITICAL = {"power_outage", "battery_low"}


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def notify(title, message, critical=False):
    cmd = ["notify-send", "-u", "critical" if critical else "normal",
           "-t", "15000", "-a", "nobreak", title, message]
    try:
        subprocess.run(cmd, check=False, timeout=5,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        pass  # no notify-send / no D-Bus: just log


def read_ups(name):
    """Run upsc and return (dict key->value string, error)."""
    try:
        out = subprocess.run(["upsc", name], capture_output=True, text=True,
                             timeout=10, check=True)
    except Exception as e:
        return None, f"upsc failed: {e}"
    data = {}
    for line in out.stdout.splitlines():
        if ": " in line:
            k, v = line.split(": ", 1)
            data[k.strip()] = v.strip()
    return data, None


def summary(data):
    """Stable subset of readings for the event (numbers are always measured)."""
    def get(key):
        try:
            return float(data.get(key, "nan"))
        except ValueError:
            return None
    return {
        "input_v": get("input.voltage"),
        "output_v": get("output.voltage"),
        "load_pct": get("ups.load"),
        "battery_v": get("battery.voltage"),
        "battery_pct": get("battery.charge"),
        "temp_c": get("ups.temperature"),
    }


def record(event, status, data, extra=None):
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    line = {
        "ts": now(),
        "event": event,
        "ups_status": status,
        **summary(data),
    }
    if extra:
        line.update(extra)
    with EVENTS_FILE.open("a", encoding="utf-8") as f:
        f.write(json.dumps(line, ensure_ascii=False) + "\n")
    return line


def classify(status):
    """'OL' -> on_line; 'OB' -> on_battery; 'LB' present -> battery_low."""
    flags = status.split()
    if "LB" in flags:
        return "battery_low"
    if "OB" in flags:
        return "on_battery"
    if "OL" in flags:
        return "on_line"
    return "unknown"


HUMAN_EVENTS = {
    "power_outage": ("⚠️  Power outage",
                     "The UPS took over (on battery). Save your work."),
    "power_restored": ("⚡ Power restored",
                       "Mains power is back. UPS is recharging."),
    "battery_low": ("🔋 Battery low!",
                    "Runtime is almost over — shut the machine down safely."),
}


def build_parser():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--ups", default="nobreak@localhost",
                    help="NUT UPS name (default nobreak@localhost)")
    ap.add_argument("--interval", type=float, default=5.0,
                    help="poll interval in seconds (default 5)")
    # legacy Portuguese alias (pre-nobreak-omarchy units); hidden from --help
    ap.add_argument("--intervalo", dest="interval", type=float,
                    help=argparse.SUPPRESS)
    ap.add_argument("--once", action="store_true", help="one reading and exit")
    ap.add_argument("--dry-run", action="store_true",
                    help="do not watch: only test notifications and record test events")
    ap.add_argument("--on-cmd", help="command to run on power outage "
                                     "(e.g. 'systemctl suspend')")
    ap.add_argument("--restore-cmd", help="command to run when power is restored")
    return ap


def main(argv=None):
    args = build_parser().parse_args(argv)

    if args.dry_run:
        fake = {"input.voltage": "0.0", "ups.status": "OB LB", "ups.load": "8",
                "battery.voltage": "2.22", "ups.temperature": "30.0",
                "output.voltage": "220.0"}
        for event in ("power_outage", "power_restored", "battery_low"):
            title, msg = HUMAN_EVENTS[event]
            notify(title, msg, critical=(event in CRITICAL))
            record(event, "OB LB (dry-run)", fake, {"dry_run": True})
        print(f"dry-run ok — events written to {EVENTS_FILE}")
        return 0

    print(f"guardian watching {args.ups} every {args.interval}s "
          f"(log: {EVENTS_FILE})", flush=True)
    state = None          # last classified state
    failures = 0

    while True:
        data, error = read_ups(args.ups)
        if error:
            failures += 1
            if failures == 6:   # ~30s without an answer: warn once
                notify("UPS not responding",
                       f"{args.ups} is not responding ({failures} attempts). "
                       "Check: systemctl status nut-driver@" +
                       args.ups.split("@")[0])
                record("ups_not_responding", "n/a", {},
                       {"error": error[:200], "failures": failures})
            if args.once:
                print(error, file=sys.stderr)
                return 1
            time.sleep(args.interval)
            continue
        failures = 0

        status = data.get("ups.status", "?")
        new = classify(status)

        if state is None:
            record("monitoring_started", status, data)
        elif new != state:
            if state == "on_line" and new in ("on_battery", "battery_low"):
                event = "battery_low" if new == "battery_low" else "power_outage"
                title, msg = HUMAN_EVENTS[event]
                notify(title, msg, critical=True)
                record(event, status, data)
                if args.on_cmd:
                    subprocess.run(args.on_cmd, shell=True, check=False)
            elif state in ("on_battery", "battery_low") and new == "on_line":
                title, msg = HUMAN_EVENTS["power_restored"]
                notify(title, msg)
                record("power_restored", status, data)
                if args.restore_cmd:
                    subprocess.run(args.restore_cmd, shell=True, check=False)
            elif state == "on_battery" and new == "battery_low":
                title, msg = HUMAN_EVENTS["battery_low"]
                notify(title, msg, critical=True)
                record("battery_low", status, data)
            else:
                record("status_change", status, data,
                       {"previous": state, "current": new})
        state = new

        if args.once:
            print(json.dumps({**summary(data), "status": status,
                              "state": new}, ensure_ascii=False))
            return 0
        time.sleep(args.interval)


if __name__ == "__main__":
    sys.exit(main())
