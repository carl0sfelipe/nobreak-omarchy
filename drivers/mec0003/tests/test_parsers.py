"""Tests for the MEC0003 driver parsers/checksums — no hardware, no root.

The frames below come from real captures (see tests/frames/README.md);
the Q1 frame was captured live on 2026-10-28 (input 231.2 V, output
219.8 V, load 8%, 50.0 Hz, battery 2.22 V per cell, 27.0 C).
"""

import pytest

import mec0003


# ---------------------------------------------------------------------------
# parse_q1 — Megatec ASCII dialect (string/setreport channels)
# ---------------------------------------------------------------------------

def test_parse_q1_real_frame():
    d = mec0003.parse_q1("(231.2 000.0 219.8 008 50.0 2.22 27.0 00001000")
    assert d["input_voltage"] == 231.2
    assert d["input_voltage_fault"] == 0.0
    assert d["output_voltage"] == 219.8
    assert d["load_percent"] == 8
    assert d["input_frequency_hz"] == 50.0
    # QUIRK: voltage PER CELL (~2.22 V on float) — multiply by
    # 6 (12 V battery) or 12 (24 V) to get the total voltage
    assert d["battery_voltage"] == 2.22
    assert d["temperature_c"] == 27.0
    assert d["ups_status"] == "OL"
    # flags 00001000: no relevant bit set (bit 4 is reserved)
    assert d["flags"]["utility_fail"] is False
    assert d["flags"]["battery_low"] is False
    assert d["flags"]["bypass_or_boost"] is False
    assert d["flags"]["ups_failed"] is False
    assert d["flags"]["test_in_progress"] is False
    assert d["flags"]["shutdown_active"] is False
    assert d["flags"]["beeper_on"] is False


def test_parse_q1_utility_fail_becomes_ob():
    base = "(231.2 000.0 219.8 008 50.0 2.22 27.0 "
    # utility_fail=1 -> "OB" (on battery)
    assert mec0003.parse_q1(base + "10000000")["ups_status"] == "OB"
    # utility_fail=1 + battery_low=1 -> "OB LB"
    assert mec0003.parse_q1(base + "11000000")["ups_status"] == "OB LB"
    # battery low with mains ok -> "OL LB"
    assert mec0003.parse_q1(base + "01000000")["ups_status"] == "OL LB"
    # beeper on does not change the NUT status
    d = mec0003.parse_q1(base + "00000001")
    assert d["ups_status"] == "OL"
    assert d["flags"]["beeper_on"] is True


def test_parse_q1_dict_keys_are_stable():
    # the keys of the published JSON (stdout/MQTT) must not change
    d = mec0003.parse_q1("(231.2 000.0 219.8 008 50.0 2.22 27.0 00001000")
    assert list(d.keys()) == [
        "input_voltage", "input_voltage_fault", "output_voltage",
        "load_percent", "input_frequency_hz", "battery_voltage",
        "temperature_c", "flags", "ups_status",
    ]
    assert list(d["flags"].keys()) == [
        "utility_fail", "battery_low", "bypass_or_boost", "ups_failed",
        "test_in_progress", "shutdown_active", "beeper_on",
    ]


# ---------------------------------------------------------------------------
# parse_f / parse_i / parse_bl
# ---------------------------------------------------------------------------

def test_parse_f():
    d = mec0003.parse_f("#220.0 000 024.0 50.0")
    assert d == {
        "nominal_input_voltage": 220.0,
        "nominal_current_a": 0.0,
        "nominal_battery_voltage": 24.0,
        "nominal_frequency_hz": 50.0,
    }


def test_parse_i():
    d = mec0003.parse_i("#SUNTEK  MODEL-X  FW123")
    assert d == {"manufacturer": "SUNTEK", "model": "MODEL-X",
                 "firmware": "FW123"}


def test_parse_bl():
    assert mec0003.parse_bl("BL85") == 85
    assert mec0003.parse_bl("bl0") == 0


# ---------------------------------------------------------------------------
# SMS binary protocol (serial channel)
# ---------------------------------------------------------------------------

def test_sms_checksum_known_vectors():
    # known-good commands captured from the SMS protocol
    assert mec0003.sms_checksum(bytes.fromhex("51 ff ff ff ff")) == 0xB3
    assert mec0003.sms_checksum(bytes.fromhex("49 ff ff ff ff")) == 0xBB
    assert mec0003.sms_checksum(bytes.fromhex("46 ff ff ff ff")) == 0xBE
    assert mec0003.sms_checksum(bytes.fromhex("54 00 10 00 00")) == 0x9C


def test_sms_cmds_from_v1_match_checksum():
    # the literal frames inherited from v1 (verified on hardware) must
    # match the recomputed checksum
    assert mec0003.SMS_CMDS["Q"] == mec0003.build_sms_frame(0x51)
    assert mec0003.SMS_CMDS["I"] == mec0003.build_sms_frame(0x49)
    assert mec0003.SMS_CMDS["F"] == mec0003.build_sms_frame(0x46)


def test_parse_sms_status_q_answer():
    frame = bytes.fromhex(
        "3d 08 34 08 34 04 38 01 22 02 58 03 e8 01 7c 09 01 0d")
    d = mec0003.parse_sms_status(frame)
    assert d["input_voltage_last"] == 210.0
    assert d["input_voltage"] == 210.0
    assert d["output_voltage"] == 108.0
    assert d["load_percent"] == 29.0
    assert d["output_frequency_hz"] == 60.0
    assert d["battery_charge_percent"] == 100.0
    assert d["temperature_c"] == 38.0
    # status byte 0x09 = normal: beeper on (bit 0) and NOT on battery
    # (bit 7 — "unplugged from mains" is 0x89, see PROTOCOL.md 1.5)
    assert d["bits"]["beeper_on"] is True
    assert d["bits"]["on_battery"] is False
    assert d["bits"]["ups_ok"] is True


def test_parse_sms_status_on_battery():
    # same capture with status byte 0x89 (bit 7 = on battery)
    frame = bytes.fromhex(
        "3d 08 34 08 34 04 38 01 22 02 58 03 e8 01 7c 89 01 0d")
    d = mec0003.parse_sms_status(frame)
    assert d["bits"]["on_battery"] is True
    assert d["bits"]["beeper_on"] is True


def test_parse_sms_status_derives_ups_status():
    frame = bytes.fromhex(
        "3d 08 34 08 34 04 38 01 22 02 58 03 e8 01 7c 89 01 0d")
    # SmsSerialChannel.status() adds ups_status in the same dialect as Q1;
    # here we only validate the mapping (the serial channel is mocked)
    d = mec0003.parse_sms_status(frame)
    status = mec0003.build_ups_status(d["bits"]["on_battery"],
                                      d["bits"]["battery_low"])
    assert status == "OB"


# ---------------------------------------------------------------------------
# Invalid frames must raise UpsError
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("bad", ["", "XYZ", "(000", "(1.0 2.0 3.0 004 5.0 6.0 7.0 0"])
def test_parse_q1_invalid(bad):
    with pytest.raises(mec0003.UpsError):
        mec0003.parse_q1(bad)


@pytest.mark.parametrize("bad", ["", "85", "XX85"])
def test_parse_bl_invalid(bad):
    with pytest.raises(mec0003.UpsError):
        mec0003.parse_bl(bad)


@pytest.mark.parametrize("bad", [
    b"",                                   # short
    b"\x3d\x00",                          # short
    b"\x3e" + b"\x00" * 17,               # wrong marker
    b"\x3d" + b"\x00" * 16 + b"\x0a",     # wrong terminator
])
def test_parse_sms_status_invalid(bad):
    with pytest.raises(mec0003.UpsError):
        mec0003.parse_sms_status(bad)


def test_builtin_selftest_passes():
    # the CLI --selftest runs the same checks — it must pass here
    import contextlib
    import io
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        rc = mec0003.run_selftest()
    assert rc == 0
    assert "SELFTEST OK" in out.getvalue()
