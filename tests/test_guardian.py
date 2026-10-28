"""Core guardian tests — pure logic, no NUT, no notifications."""

import guardian


def test_classify():
    assert guardian.classify("OL") == "on_line"
    assert guardian.classify("OL CHRG") == "on_line"
    assert guardian.classify("OB DISCHRG") == "on_battery"
    assert guardian.classify("OB LB") == "battery_low"
    assert guardian.classify("") == "unknown"


def test_summary_parses_numbers():
    s = guardian.summary({"input.voltage": "231.2", "output.voltage": "219.8",
                          "ups.load": "8", "battery.voltage": "2.22",
                          "battery.charge": "100", "ups.temperature": "27.0"})
    assert s == {"input_v": 231.2, "output_v": 219.8, "load_pct": 8.0,
                 "battery_v": 2.22, "battery_pct": 100.0, "temp_c": 27.0}


def test_cli_english_flags():
    a = guardian.build_parser().parse_args(["--ups", "x@localhost",
                                            "--interval", "10"])
    assert a.ups == "x@localhost" and a.interval == 10.0


def test_cli_legacy_portuguese_alias():
    # units installed before the pivot use --intervalo; must keep working
    a = guardian.build_parser().parse_args(["--intervalo", "7"])
    assert a.interval == 7.0
    assert "--intervalo" not in guardian.build_parser().format_help()


def test_record_writes_english_event(tmp_path, monkeypatch):
    import json
    monkeypatch.setattr(guardian, "STATE_DIR", tmp_path)
    monkeypatch.setattr(guardian, "EVENTS_FILE", tmp_path / "events.jsonl")
    guardian.record("power_outage", "OB", {"input.voltage": "0"})
    line = json.loads((tmp_path / "events.jsonl").read_text())
    assert line["event"] == "power_outage" and line["ups_status"] == "OB"
