#!/usr/bin/env python3
"""
driver.py (v2) — nobreak-omarchy driver for UPSes with the generic MEC0003
USB chip (VID:PID 0001:0000, "Fry's Electronics" in lsusb — brands SMS, NHS,
Powercool, Hunnox, DEXP, Eurocase etc.). Standalone: works without NUT.

Protocol documented from:
  * reverse engineering of the UPSmart Windows client ("MEGA(USB)" mode) as
    reflected in NUT's hunnox/krauler/fabula subdrivers (nutdrv_qx.c)
  * issues networkupstools/nut#1539 and #2208 (firmware behavior)
  * smsUps/nobreakSMS (SMS binary serial protocol, for the serial mode)
  * live captures on real hardware (2026-10-28) — see tests/frames/

Firmware quirks (learned on real hardware — RESPECT THEM):
  * Q1 battery_voltage is PER CELL (~2.22 V on float): multiply by the
    number of cells — 6 for a 12 V battery, 12 for a 24 V battery.
  * some firmwares report a FIXED 50.0 Hz input frequency
    (ignore it for decisions, it is cosmetic).
  * after a replug / USB cycle the device answers ZEROS until the warm-up
    lock-step completes: poll at ~1 Hz for a few seconds until values come
    alive (StringChannel already does the warm-up, but the next few reads
    may still be zeros).
  * never run this driver while NUT is talking to the chip: concurrent
    access (or a standalone BL/I/F query) wedges the firmware.

Access methods (auto tries in this order):
  1. string    — commands embedded in GET_DESCRIPTOR(String): the string
                 index IS the opcode (Q1=0x03, F=0x0d, I=0x0c, BL=0xf3...),
                 fixed langid 0x0409, wLength at most 102 (larger wedges it).
  2. setreport — HID tunnel: ASCII command in an 8-byte output report via
                 SET_REPORT (0x21/0x09/0x0200), answer on endpoint 0x81.
  3. serial    — SMS binary protocol 2400 8N1 (7-byte cmd / 18-byte
                 answer) on /dev/ttyUSB*, if the cable creates a serial port.

Dependencies (optional extras are not needed for basic use):
  pip install pyusb pyserial hidapi     # core (see requirements.txt)
  pip install paho-mqtt                 # only for --mqtt / --daemon with MQTT

Exit codes: 0 ok, 1 device/protocol error, 2 optional dependency missing.
"""

import argparse
import glob
import json
import os
import signal
import sys
import time

__version__ = "2.0.0"

VID = 0x0001
PID = 0x0000
LANGID = 0x0409          # fixed langid: default negotiation wedges the firmware
MAX_STRING_LEN = 102     # wLength > 102 wedges the chip (measured from the Windows client)


class UpsError(Exception):
    """Device/protocol error (exit code 1)."""


class MissingDependency(Exception):
    """Optional dependency missing, e.g. paho-mqtt (exit code 2)."""


# ---------------------------------------------------------------------------
# Layer 1 — command channels (protocol details are SACRED: reverse-engineered
# and verified against real hardware — do not touch the bytes)
# ---------------------------------------------------------------------------

# ---------- "string" method (UPSmart MEGA(USB) mode / hunnox-krauler) -------

# String index = Megatec command opcode
STRING_INDEX = {
    "Q1": 0x03,   # full status (ASCII "(226.0 195.0 ...")
    "F":  0x0d,   # ratings
    "I":  0x0c,   # manufacturer/model/firmware
    "Q":  0x07,   # toggles the beeper
    "C":  0x0a,   # cancels shutdown
    "T":  0x04,   # battery test (10 s)
    "TL": 0x05,   # test until battery low
    "BL": 0xf3,   # battery charge in % (hunnox dialect)
}
# 0x68/0x69 exist in the krauler table but shut the UPS down — never use.
FORBIDDEN_INDEXES = {0x68, 0x69}


class StringChannel:
    """Megatec commands tunneled in USB string descriptors."""

    name = "string"
    needs_usb = True

    def __init__(self, dev):
        self.dev = dev
        self.warmed = False
        self.step = 1          # UPSmart lock-step: interleaves F/Q1/I
        # warm-up: without it the firmware answers zeros (NUT#2208)
        for _ in range(2):
            self._raw_string(0x00, 1026, required=False)
        self._raw_string(0x01, 1026, required=False)
        time.sleep(0.01)
        self.warmed = True

    def _raw_string(self, index, wlength, required=True):
        r = self.dev.ctrl_transfer(0x80, 0x06, (0x03 << 8) | index,
                                   LANGID, wlength, 5000)
        if r is None or len(r) == 0:
            if required:
                raise UpsError(f"string 0x{index:02x}: no answer")
            return b""
        return bytes(r)

    def _get_string(self, index):
        if index in FORBIDDEN_INDEXES:
            raise UpsError(f"index 0x{index:02x} is dangerous (shuts the UPS down)")
        raw = self._raw_string(index, MAX_STRING_LEN)
        if len(raw) < 2 or raw[1] != 0x03:
            raise UpsError(f"string 0x{index:02x}: invalid descriptor "
                           f"{raw[:4].hex()}")
        if raw[0] != len(raw):
            raise UpsError(f"string 0x{index:02x}: length mismatch "
                           f"({raw[0]} != {len(raw)})")
        # UTF-16LE -> ASCII (1 byte out of every 2, from offset 2)
        return raw[2:raw[0]:2].decode("ascii", "replace").rstrip("\r\n\x00")

    def _dummy(self, asking_index):
        # UPSmart interleaves F/Q1/I reads between real commands to keep
        # the values alive; we skip the one we are actually asking for
        for idx in (0x0d, 0x03, 0x0c):
            if idx != asking_index:
                try:
                    self._get_string(idx)
                except Exception:
                    pass
                return

    def query(self, cmd):
        idx = STRING_INDEX[cmd]
        if self.warmed:
            self._dummy(idx)
        return self._get_string(idx)


# ---------- "setreport" method (classic Megatec/cypress HID tunnel) --------

class SetReportChannel:
    """ASCII command in an 8-byte report via SET_REPORT; answer on EP 0x81."""

    name = "setreport"
    needs_usb = True

    def __init__(self, dev):
        self.dev = dev

    def query(self, cmd):
        payload = (cmd + "\r").encode("ascii")[:8]
        payload = payload + b"\x00" * (8 - len(payload))
        self.dev.ctrl_transfer(0x21, 0x09, 0x0200, 0, payload, 5000)
        out = b""
        deadline = time.time() + 3.0
        while time.time() < deadline and len(out) < 128:
            try:
                chunk = self.dev.read(0x81, 8, 1000)
            except Exception:
                break
            if not chunk:
                continue
            out += bytes(chunk)
            if b"\r" in out:
                break
        s = out.decode("ascii", "replace").strip("\r\n\x00")
        if s.upper() == "UPS NO ACK":
            return ""
        return s


# ---------- "serial" method (SMS binary protocol) ---------------------------

def sms_checksum(body):
    """Additive checksum of the SMS protocol: (0x100 - sum(bytes)) & 0xFF.

    `body` is the first 5 bytes of the packet (letter + 4 args); the full
    packet has 7 bytes: body + checksum + 0x0D (see PROTOCOL.md §1.2).
    """
    return (0x100 - (sum(body) & 0xFF)) & 0xFF


def build_sms_frame(cmd, args_bytes=b"\xff\xff\xff\xff"):
    """Builds a 7-byte packet: [cmd][4 args][checksum][0x0D]."""
    body = bytes([cmd]) + bytes(args_bytes)
    return body + bytes([sms_checksum(body), 0x0D])


# Literal bytes kept from v1 (verified on hardware; --selftest checks they
# are still identical to the ones recomputed by build_sms_frame).
SMS_CMDS = {
    "Q":  bytes.fromhex("51 ff ff ff ff b3 0d"),
    "I":  bytes.fromhex("49 ff ff ff ff bb 0d"),
    "F":  bytes.fromhex("46 ff ff ff ff be 0d"),
}


def parse_sms_status(raw):
    """Parser for the 18-byte answer of the Q command (SMS binary protocol).

    Layout documented in PROTOCOL.md §1.4 (real captures):
    offsets 1-14 are 7 big-endian u16 / 10; offset 15 = status bits;
    offset 17 = terminator 0x0D. Status bits: bit0 beeper, bit6 battery
    low, bit7 on battery (0x09 = normal, 0x89 = unplugged from mains).
    """
    raw = bytes(raw)
    if len(raw) < 18:
        raise UpsError(f"short SMS answer ({len(raw)} bytes): {raw.hex()}")
    if raw[0] != 0x3D:
        raise UpsError(f"invalid SMS marker: 0x{raw[0]:02x}")
    if raw[17] != 0x0D:
        raise UpsError(f"invalid SMS terminator: 0x{raw[17]:02x}")
    u16 = lambda i: (raw[i] << 8) | raw[i + 1]
    st = raw[15]
    return {
        "input_voltage_last": u16(1) / 10,
        "input_voltage": u16(3) / 10,
        "output_voltage": u16(5) / 10,
        "load_percent": u16(7) / 10,
        "output_frequency_hz": u16(9) / 10,
        "battery_charge_percent": u16(11) / 10,
        "temperature_c": u16(13) / 10,
        "bits": {
            "beeper_on": bool(st & 0x01), "shutdown_active": bool(st & 0x02),
            "test_active": bool(st & 0x04), "ups_ok": bool(st & 0x08),
            "boost": bool(st & 0x10), "bypass": bool(st & 0x20),
            "battery_low": bool(st & 0x40), "on_battery": bool(st & 0x80),
        },
    }


class SmsSerialChannel:
    """SMS binary protocol: 2400 8N1, 7-byte cmd, 18-byte answer."""

    name = "serial"
    needs_usb = False

    def __init__(self, port):
        import serial  # pyserial
        self.ser = serial.Serial(port, 2400, bytesize=8, parity="N",
                                 stopbits=1, timeout=3)

    def _send(self, frame):
        # firmware prefers spaced-out bytes (dmslabsbr/smsUps uses 100 ms)
        for b in frame:
            self.ser.write(bytes([b]))
            self.ser.sleep(0.1) if hasattr(self.ser, "sleep") else time.sleep(0.1)

    def query(self, cmd):
        self.ser.reset_input_buffer()
        frame = SMS_CMDS.get(cmd)
        if frame is None:
            raise UpsError(f"command {cmd} not mapped in serial mode")
        self._send(frame)
        raw = self.ser.read(18)
        if len(raw) < 18 or raw[0] != 0x3D or raw[17] != 0x0D:
            raise UpsError(f"invalid serial answer: {raw.hex()}")
        return raw  # binary; dedicated parser above

    def status(self):
        d = parse_sms_status(self.query("Q"))
        # derive ups_status in the same dialect as Q1 (OB/OL + LB) so the
        # output format and the MQTT sensor stay uniform
        d["ups_status"] = build_ups_status(
            d["bits"]["on_battery"], d["bits"]["battery_low"],
            boost=d["bits"]["boost"])
        return d


# ---------------------------------------------------------------------------
# Layer 2 — Megatec ASCII parsers (dict keys ARE STABLE: they are consumed
# by JSON/MQTT/NUT — do not rename, do not reorder)
# ---------------------------------------------------------------------------

def build_ups_status(on_battery, battery_low, boost=False, failed=False,
                     test=False):
    """Maps flags to the NUT dialect: OB/OL + LB (+BOOST/ALARM/TEST).

    utility_fail -> "OB" (on battery), else "OL" (on line); appends "LB"
    if battery_low. Same order as v1 — the JSON is consumed externally.
    """
    st = []
    st.append("OB" if on_battery else "OL")
    if battery_low:
        st.append("LB")
    if boost:
        st.append("BOOST")
    if failed:
        st.append("ALARM")
    if test:
        st.append("TEST")
    return " ".join(st)


def parse_q1(s):
    """(226.0 195.0 226.0 014 49.0 27.5 30.0 00001000

    QUIRK: battery_voltage is PER CELL (~2.22 V on float) — multiply by the
    number of cells (6 for a 12 V battery, 12 for 24 V).
    QUIRK: some firmwares report a fixed input_frequency_hz of 50.0.
    """
    if len(s) < 46 or not s.startswith("("):
        raise UpsError(f"malformed Q1: {s!r}")
    flags = s[38:46]
    out = {
        "input_voltage": float(s[1:6]),
        "input_voltage_fault": float(s[7:12]),
        "output_voltage": float(s[13:18]),
        "load_percent": float(s[19:22]),
        "input_frequency_hz": float(s[23:27]),
        "battery_voltage": float(s[28:32]),
        "temperature_c": float(s[33:37]),
        "flags": {
            "utility_fail": flags[0] == "1",
            "battery_low": flags[1] == "1",
            "bypass_or_boost": flags[2] == "1",
            "ups_failed": flags[3] == "1",
            "test_in_progress": flags[5] == "1",
            "shutdown_active": flags[6] == "1",
            "beeper_on": flags[7] == "1",
        },
    }
    out["ups_status"] = build_ups_status(
        out["flags"]["utility_fail"], out["flags"]["battery_low"],
        boost=out["flags"]["bypass_or_boost"],
        failed=out["flags"]["ups_failed"],
        test=out["flags"]["test_in_progress"])
    return out


def parse_f(s):
    """#220.0 000 024.0 50.0  -> nominal input voltage, current, battery, frequency"""
    p = s.strip("#").split()
    return {
        "nominal_input_voltage": float(p[0]),
        "nominal_current_a": float(p[1]),
        "nominal_battery_voltage": float(p[2]),
        "nominal_frequency_hz": float(p[3]),
    }


def parse_i(s):
    """#-------------   ------     VT12046Q  -> manufacturer, model, firmware"""
    p = s.strip("#").split()
    return {
        "manufacturer": p[0] if len(p) > 0 else "?",
        "model": p[1] if len(p) > 1 else "?",
        "firmware": p[2] if len(p) > 2 else "?",
    }


def parse_bl(s):
    """BL85 -> battery charge in %"""
    if not s.upper().startswith("BL"):
        raise UpsError(f"malformed BL: {s!r}")
    return int(s[2:])


# ---------------------------------------------------------------------------
# Layer 3 — opening the device and recovering from a USB wedge
# ---------------------------------------------------------------------------

def open_usb():
    try:
        import usb.core
        import usb.util
    except ImportError as e:
        raise UpsError(f"pyusb not installed (pip install pyusb): {e}") from e
    try:
        dev = usb.core.find(idVendor=VID, idProduct=PID)
    except usb.core.NoBackendError as e:
        raise UpsError("libusb not found (install the system libusb "
                       "package)") from e
    if dev is None:
        raise UpsError("UPS not found on USB (0001:0000). "
                       "Is it powered on and the cable connected?")
    try:
        try:
            if dev.is_kernel_driver_active(0):
                dev.detach_kernel_driver(0)   # get usbhid out of the way
        except NotImplementedError:
            pass
        try:
            dev.get_active_configuration()
        except Exception:
            dev.set_configuration()
        usb.util.claim_interface(dev, 0)
    except usb.core.USBError as e:
        # typical without root: the device exists but udev did not grant access
        raise UpsError(f"no USB access ({e}) — run as root or install "
                       "the udev rule (drivers/mec0003/udev/)") from e
    return dev


def make_channel(method, port):
    if method == "serial":
        return SmsSerialChannel(port)
    dev = open_usb()
    if method == "string":
        return StringChannel(dev)
    if method == "setreport":
        return SetReportChannel(dev)
    # auto: string is what UPSmart uses on these chips
    return StringChannel(dev)


def sysfs_reauthorize(log):
    """Wedged-chip recovery: 'authorized' 0->1 cycle via sysfs.

    Only works as root (USB sysfs is write-protected for users). Writes are
    wrapped in try/except — only written if the file is writable. After the
    cycle the device re-enumerates: the reopened channel goes through the
    warm-up and the firmware may still answer zeros for the first seconds
    (~1 Hz until it settles — quirk documented in the header).
    """
    if os.geteuid() != 0:
        log("hint: without root /sys/bus/usb/devices/*/authorized cannot be "
            "cycled — replug the USB cable or run the service as root")
        return False
    cycled = False
    for auth in glob.glob("/sys/bus/usb/devices/*/authorized"):
        base = os.path.dirname(auth)
        try:
            with open(os.path.join(base, "idVendor")) as f:
                vid = f.read().strip()
            with open(os.path.join(base, "idProduct")) as f:
                pid = f.read().strip()
        except OSError:
            continue
        if vid != "0001" or pid != "0000":
            continue  # only touch the UPS device
        try:
            with open(auth, "w") as f:
                f.write("0")
            time.sleep(1.0)
            with open(auth, "w") as f:
                f.write("1")
            cycled = True
            log(f"USB cycled at {base}, waiting for re-enumeration")
        except OSError as e:
            log(f"sysfs not writable ({auth}): {e}")
    return cycled


# ---------------------------------------------------------------------------
# Layer 4 — MQTT / Home Assistant bridge (paho-mqtt is OPTIONAL)
# ---------------------------------------------------------------------------

# Entities published via MQTT Discovery. `key` is the key in the state JSON
# published on --mqtt-topic (keys are stable — see parse_q1).
DISCOVERY_SENSORS = (
    {"id": "input_voltage", "name": "UPS input voltage",
     "key": "input_voltage", "unit": "V", "device_class": "voltage"},
    {"id": "output_voltage", "name": "UPS output voltage",
     "key": "output_voltage", "unit": "V", "device_class": "voltage"},
    {"id": "load", "name": "UPS load",
     "key": "load_percent", "unit": "%", "icon": "mdi:gauge"},
    {"id": "battery_charge", "name": "UPS battery",
     "key": "battery_charge_percent", "unit": "%", "device_class": "battery"},
    # ups_status is already in the NUT dialect: "OL" on mains, "OB" on
    # battery, "LB" battery low (mapping done in build_ups_status)
    {"id": "ups_status", "name": "UPS status",
     "key": "ups_status", "icon": "mdi:power-plug"},
    {"id": "temperature", "name": "UPS temperature",
     "key": "temperature_c", "unit": "°C", "device_class": "temperature"},
)

DEVICE_INFO = {
    "identifiers": ["nobreak_mec0003"],
    "name": "UPS (MEC0003)",
    "manufacturer": "SMS/NHS/generic",
    "model": "MEC0003 (0001:0000)",
}


def split_broker(broker):
    """'host' or 'host:port' -> (host, port); default port 1883."""
    if ":" in broker:
        host, port = broker.rsplit(":", 1)
        return host, int(port)
    return broker, 1883


class MqttBridge:
    """Publishes the JSON state + Home Assistant discovery configs.

    paho-mqtt is imported HERE (optional): modes without --mqtt never
    require the library.
    """

    def __init__(self, broker, state_topic):
        try:
            import paho.mqtt.client as mqtt
        except ImportError as e:
            raise MissingDependency(
                "paho-mqtt is not installed (only needed for --mqtt): "
                f"{e}") from e
        host, port = split_broker(broker)
        # compatible with paho 1.x and 2.x
        try:
            self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2,
                                      client_id="mec0003")
        except AttributeError:
            self.client = mqtt.Client(client_id="mec0003")
        self.state_topic = state_topic
        self.client.on_connect = self._on_connect
        self.client.connect(host, port, keepalive=30)
        self.client.loop_start()

    def _on_connect(self, client, userdata, *args):
        # (re)publish discovery on every broker reconnect
        self.publish_discovery()

    def publish_discovery(self):
        for cfg in DISCOVERY_SENSORS:
            payload = {
                "name": cfg["name"],
                "state_topic": self.state_topic,
                "value_template": "{{ value_json." + cfg["key"] + " }}",
                "unique_id": "mec0003_" + cfg["id"],
                "device": DEVICE_INFO,
            }
            if "unit" in cfg:
                payload["unit_of_measurement"] = cfg["unit"]
            if "device_class" in cfg:
                payload["device_class"] = cfg["device_class"]
            if "icon" in cfg:
                payload["icon"] = cfg["icon"]
            if cfg["key"] != "ups_status":
                payload["state_class"] = "measurement"
            topic = "homeassistant/sensor/nobreak_mec0003/" + cfg["id"] + "/config"
            self.client.publish(topic, json.dumps(payload, ensure_ascii=False),
                                qos=1, retain=True)

    def publish_state(self, status):
        self.client.publish(self.state_topic,
                            json.dumps(status, ensure_ascii=False),
                            qos=1, retain=True)


# ---------------------------------------------------------------------------
# Layer 5 — formatting, selftest and CLI
# ---------------------------------------------------------------------------

def fmt_status(d):
    freq = d.get("input_frequency_hz", d.get("output_frequency_hz", 0.0))
    if "battery_voltage" in d:
        # QUIRK: voltage PER CELL (~2.22 V) — multiply by the number of
        # cells (6 for 12 V, 12 for 24 V) to get the total voltage
        batt_line = f"battery           : {d['battery_voltage']:6.2f} V (per cell)"
    else:
        batt_line = (f"battery           : "
                     f"{d.get('battery_charge_percent', 0):3.0f} %")
    lines = [
        f"mains (input)     : {d['input_voltage']:6.1f} V  {freq:5.1f} Hz",
        f"output            : {d['output_voltage']:6.1f} V  load {d['load_percent']:3.0f}%",
        batt_line,
        f"temperature       : {d['temperature_c']:6.1f} °C",
        f"status            : {d.get('ups_status', '?')}",
    ]
    return "\n".join(lines)


# Real hardware samples (2026-10-28) — used by --selftest;
# the CI tests (tests/test_parsers.py) use the same frames.
Q1_REAL_SAMPLE = "(231.2 000.0 219.8 008 50.0 2.22 27.0 00001000"
SMS_Q_SAMPLE = bytes.fromhex(
    "3d 08 34 08 34 04 38 01 22 02 58 03 e8 01 7c 09 01 0d")


def run_selftest():
    """Hardware-free checks: parsers, checksums and real frames."""
    print(f"nobreak-omarchy driver mec0003 {__version__} --selftest (no hardware, no root)")
    failures = 0

    def check(name, fn):
        nonlocal failures
        try:
            fn()
        except Exception as e:
            failures += 1
            print(f"FAIL   {name}: {type(e).__name__}: {e}")
            return
        print(f"ok     {name}")

    def t_q1_real():
        d = parse_q1(Q1_REAL_SAMPLE)
        assert d["input_voltage"] == 231.2
        assert d["input_voltage_fault"] == 0.0
        assert d["output_voltage"] == 219.8
        assert d["load_percent"] == 8
        assert d["input_frequency_hz"] == 50.0
        assert d["battery_voltage"] == 2.22
        assert d["temperature_c"] == 27.0
        assert d["ups_status"] == "OL"
        assert not any(d["flags"].values())

    def t_q1_flags():
        base = "(231.2 000.0 219.8 008 50.0 2.22 27.0 "
        assert parse_q1(base + "10000000")["ups_status"] == "OB"
        assert parse_q1(base + "11000000")["ups_status"] == "OB LB"
        assert parse_q1(base + "01000000")["ups_status"] == "OL LB"

    def t_f():
        d = parse_f("#220.0 000 024.0 50.0")
        assert d == {"nominal_input_voltage": 220.0, "nominal_current_a": 0.0,
                     "nominal_battery_voltage": 24.0, "nominal_frequency_hz": 50.0}

    def t_i():
        d = parse_i("#SUNTEK  MODEL-X  FW123")
        assert d == {"manufacturer": "SUNTEK", "model": "MODEL-X",
                     "firmware": "FW123"}

    def t_bl():
        assert parse_bl("BL85") == 85
        assert parse_bl("bl100") == 100

    def t_checksum():
        # known-good vectors from real SMS protocol commands
        assert sms_checksum(bytes.fromhex("51 ff ff ff ff")) == 0xB3
        assert sms_checksum(bytes.fromhex("49 ff ff ff ff")) == 0xBB
        assert sms_checksum(bytes.fromhex("46 ff ff ff ff")) == 0xBE
        assert sms_checksum(bytes.fromhex("54 00 10 00 00")) == 0x9C
        # and the v1 frames are still consistent with the checksum
        assert SMS_CMDS["Q"] == build_sms_frame(0x51)
        assert SMS_CMDS["I"] == build_sms_frame(0x49)
        assert SMS_CMDS["F"] == build_sms_frame(0x46)

    def t_sms_status():
        d = parse_sms_status(SMS_Q_SAMPLE)
        assert d["input_voltage_last"] == 210.0
        assert d["input_voltage"] == 210.0
        assert d["output_voltage"] == 108.0
        assert d["load_percent"] == 29.0
        assert d["output_frequency_hz"] == 60.0
        assert d["battery_charge_percent"] == 100.0
        assert d["temperature_c"] == 38.0
        assert d["bits"]["beeper_on"] is True
        assert d["bits"]["on_battery"] is False   # 0x09 = normal (0x89 = on battery)
        # on-battery variant (bit 7)
        ob = parse_sms_status(SMS_Q_SAMPLE[:15] + b"\x89" + SMS_Q_SAMPLE[16:])
        assert ob["bits"]["on_battery"] is True

    def t_invalid():
        for bad in ("", "XYZ", "(000", "(1.0 2.0 3.0 004 5.0 6.0 7.0 0"):
            try:
                parse_q1(bad)
            except UpsError:
                pass
            else:
                raise AssertionError(f"parse_q1 accepted {bad!r}")
        for bad in ("", "85", "XX85"):
            try:
                parse_bl(bad)
            except UpsError:
                pass
            else:
                raise AssertionError(f"parse_bl accepted {bad!r}")
        for bad in (b"", b"\x3d\x00", b"\x3e" + b"\x00" * 17,
                     SMS_Q_SAMPLE[:17] + b"\x0a"):
            try:
                parse_sms_status(bad)
            except UpsError:
                pass
            else:
                raise AssertionError(f"parse_sms_status accepted {bad!r}")

    check("parse_q1 real frame 2026-10-28", t_q1_real)
    check("parse_q1 OB/OL/LB mapping", t_q1_flags)
    check("parse_f ratings", t_f)
    check("parse_i identification", t_i)
    check("parse_bl charge", t_bl)
    check("sms_checksum + frames SMS", t_checksum)
    check("parse_sms_status Q answer", t_sms_status)
    check("invalid frames rejected", t_invalid)

    if failures:
        print(f"SELFTEST FAILED ({failures} test(s))")
        return 1
    print("SELFTEST OK")
    return 0


def one_shot(ch, args):
    if args.raw:
        idx = int(args.raw, 16)
        return {"raw": ch._get_string(idx)}
    if args.beeper:
        return {"beeper": ch.query("Q") or "(no answer — normal)"}
    if args.test is not None:
        return {"test": ch.query("T") or "(started)"}
    result = {}
    if args.info:
        result.update(parse_i(ch.query("I")))
    if args.ratings:
        result.update(parse_f(ch.query("F")))
    if args.battery:
        result["battery_charge_percent"] = parse_bl(ch.query("BL"))
    if not result or args.watch or args.daemon:
        if ch.name == "serial":
            result.update(ch.status())
        else:
            result.update(parse_q1(ch.query("Q1")))
    return result


def run_loop(args, ch, mqtt):
    """watch/daemon mode: tolerates firmware wedges and re-enumerations."""
    interval_s = args.watch if args.watch > 0 else args.interval
    consecutive_errors = 0
    was_ob = False

    def log_stderr(msg):
        print(f"[{time.strftime('%H:%M:%S')}] {msg}", file=sys.stderr, flush=True)

    while True:
        try:
            r = one_shot(ch, args)
            consecutive_errors = 0
            # for the HA battery sensor: the USB channel can read BL on every poll
            if (mqtt is not None and "battery_charge_percent" not in r
                    and ch.name in ("string", "setreport")):
                try:
                    r["battery_charge_percent"] = parse_bl(ch.query("BL"))
                except UpsError:
                    pass
            # daemon is silent on stdout (systemd/journal) unless --verbose
            if not args.daemon or args.verbose:
                output = (json.dumps(r, ensure_ascii=False) if args.json
                         else fmt_status(r))
                print(output, flush=True)
            if mqtt is not None:
                mqtt.publish_state(r)
            ob = "OB" in r.get("ups_status", "")
            if ob and not was_ob and "NUT_ON_BATTERY_CMD" in os.environ:
                os.system(os.environ["NUT_ON_BATTERY_CMD"])
            was_ob = ob
        except (KeyboardInterrupt, SystemExit):
            raise
        except Exception as e:
            consecutive_errors += 1
            log_stderr(f"{e}")
            if consecutive_errors >= 3:
                # chip wedged for good: try an 'authorized' cycle (root only)
                if sysfs_reauthorize(log_stderr):
                    time.sleep(2.0)
                consecutive_errors = 0
            try:
                ch = make_channel(args.method, args.port)
                # QUIRK: after reopening, the firmware answers zeros until
                # the lock-step completes — a few ~1 Hz reads are
                # discarded until the values settle
                for _ in range(3):
                    time.sleep(1.0)
                    try:
                        one_shot(ch, args)
                    except Exception:
                        pass
            except UpsError:
                pass
        time.sleep(interval_s)


EPILOG = """\
examples:
  sudo python3 driver.py                       # single status read (Q1)
  sudo python3 driver.py --watch 1             # monitor every 1 s
  sudo python3 driver.py --json --info         # model/firmware as JSON
  sudo python3 driver.py --beeper              # toggles the beeper
  sudo python3 driver.py --method serial --port /dev/ttyUSB0
  sudo python3 driver.py --daemon --interval 5 --mqtt localhost:1883
                                               # service (systemd) + Home Assistant
  python3 driver.py --selftest                 # hardware-free check (CI)

WARNING: do not query the chip while NUT (nut-driver@...) is running —
concurrent access wedges the firmware. Stop NUT first, or use upsc.

exit codes: 0 ok | 1 device/protocol error |
2 optional dependency missing (paho-mqtt)
"""


def build_parser():
    ap = argparse.ArgumentParser(
        description=__doc__,
        epilog=EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--method", choices=["auto", "string", "setreport", "serial"],
                    default="auto",
                    help="UPS access method (default: auto)")
    ap.add_argument("--port", default="/dev/ttyUSB0",
                    help="serial port for --method serial (default /dev/ttyUSB0)")
    ap.add_argument("--watch", type=int, metavar="N", default=0,
                    help="continuous monitor, one reading every N seconds")
    ap.add_argument("--daemon", action="store_true",
                    help="service mode (systemd): silent on stdout unless "
                         "--verbose; default interval 5 s (--interval)")
    ap.add_argument("--interval", type=float, metavar="S", default=5.0,
                    help="--daemon interval in seconds (default 5)")
    ap.add_argument("--mqtt", metavar="broker[:port]", default=None,
                    help="publish the JSON state to the MQTT broker and create "
                         "the Home Assistant entities (Discovery); also via "
                         "env MEC0003_MQTT")
    ap.add_argument("--mqtt-topic", default="home/nobreak/state",
                    help="MQTT state topic (default home/nobreak/state)")
    ap.add_argument("--json", action="store_true", help="JSON output")
    ap.add_argument("--verbose", action="store_true",
                    help="with --daemon, print every reading to stdout")
    ap.add_argument("--info", action="store_true",
                    help="manufacturer/model/firmware (I)")
    ap.add_argument("--ratings", action="store_true", help="rated values (F)")
    ap.add_argument("--battery", action="store_true", help="battery charge %% (BL)")
    ap.add_argument("--beeper", action="store_true", help="toggle the beeper (Q)")
    ap.add_argument("--test", type=int, metavar="SEC", help="battery test (T)")
    ap.add_argument("--raw", metavar="IDX",
                    help="read raw string IDX (hex) — advanced use")
    ap.add_argument("--selftest", action="store_true",
                    help="self-check of parsers/checksums with no hardware and "
                         "no root (used by CI)")
    return ap


def _sigterm_handler(signum, frame):
    # systemd stops us with SIGTERM — exit cleanly with code 0
    raise SystemExit(0)


def main():
    args = build_parser().parse_args()

    if args.selftest:
        return run_selftest()

    try:
        signal.signal(signal.SIGTERM, _sigterm_handler)
    except (ValueError, OSError):
        pass  # not on the main thread (e.g. embedded in a test)

    # --mqtt (or env MEC0003_MQTT): paho-mqtt is OPTIONAL — exit 2 if missing
    broker = args.mqtt or os.environ.get("MEC0003_MQTT")
    mqtt = None
    if broker:
        try:
            mqtt = MqttBridge(broker, args.mqtt_topic)
        except MissingDependency as e:
            print(f"ERROR: {e}", file=sys.stderr)
            print("Install with: pip install paho-mqtt", file=sys.stderr)
            return 2
        except Exception as e:
            print(f"ERROR: MQTT: {e}", file=sys.stderr)
            return 1

    try:
        ch = make_channel(args.method, args.port)
    except UpsError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1

    if not (args.watch or args.daemon):
        try:
            r = one_shot(ch, args)
            if mqtt is not None:
                mqtt.publish_state(r)
            print(json.dumps(r, ensure_ascii=False, indent=2) if args.json
                  else (fmt_status(r) if "ups_status" in r else "\n".join(
                      f"{k:28s}: {v}" for k, v in r.items())))
            return 0
        except UpsError as e:
            print(f"ERROR: {e}", file=sys.stderr)
            return 1

    try:
        run_loop(args, ch, mqtt)
    except (KeyboardInterrupt, SystemExit):
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
