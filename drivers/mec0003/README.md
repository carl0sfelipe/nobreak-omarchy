# Driver: MEC0003 (`0001:0000`, "Fry's Electronics")

The first nobreak-omarchy driver. The generic MEC0003 USB chip ships in
UPSes ("nobreaks") from dozens of brands worldwide — SMS, NHS, Powercool,
DEXP, Hunnox, Eurocase, CPC… It has no first-class Linux support and makes
a default NUT `nutdrv_qx` setup crash-loop. This directory provides a proven
NUT config, a standalone Python driver, an MQTT/Home Assistant bridge, a udev
rule and the full protocol reference.

**Status:** tested live 2026-10-28 — on-battery telemetry verified, autoheal
verified (it recovered a wedged chip at level 2, the sysfs authorized cycle).
Maintainer: [@carl0sfelipe](https://github.com/carl0sfelipe).

## Is my UPS compatible?

```console
$ lsusb | grep 0001:0000
Bus 001 Device 005: ID 0001:0000 Fry's Electronics MEC0003
```

If you see `0001:0000`, your UPS uses the MEC0003 chip. "Fry's Electronics"
is just how usb.ids labels that generic vendor ID — your UPS did not come
from Fry's.

## Install

```console
$ bash install.sh --check                 # diagnostics, no root
$ sudo bash install.sh --driver mec0003   # NUT config + udev + autoheal + guardian
$ upsc nobreak@localhost
```

Real output after install (full capture:
[`captures/2026-10-28-upsc-working.txt`](captures/2026-10-28-upsc-working.txt)):

```console
$ upsc nobreak@localhost
battery.voltage: 2.22
input.voltage: 230.9
output.voltage: 219.8
ups.load: 8
ups.status: OL
ups.temperature: 27.0
```

The NUT section lives in [`nut/ups.conf`](nut/ups.conf): `nutdrv_qx` with
`subdriver = hunnox`, `protocol = q1`, `langid_fix = 0x0409`,
`noscanlangid`, `pollinterval = 2`, per-cell battery handling, `ignorelb` and
a voltage-based charge model.

### Without NUT: standalone driver

**Stop NUT first** (`systemctl stop nut-driver@nobreak`) — never query the
chip while NUT is polling it.

```console
$ sudo python3 drivers/mec0003/driver.py --watch 1   # one read per second, reopens after a wedge
$ sudo python3 drivers/mec0003/driver.py --json      # for scripts
$ sudo python3 drivers/mec0003/driver.py --info      # manufacturer / model / firmware
$ python3 drivers/mec0003/driver.py --selftest       # parsers only, no hardware
```

Three transports: `--method string` (default, UPSmart mode), `--method
setreport` (classic HID tunnel) and `--method serial` (the SMS binary
protocol, 2400 baud 8N1, for serial-cable models such as Cypress `04b4:5500`).

### Home Assistant / MQTT

```console
$ sudo bash install.sh --driver mec0003 --mode mqtt
$ systemctl status nobreak-mec0003-mqtt
```

The bridge publishes over MQTT with Home Assistant **auto-discovery**:
voltage, load, battery, temperature and status sensors appear on their own.
(MQTT mode uses the standalone driver, so NUT, the guardian and autoheal are
not used in that mode.)

## Known quirks

| Quirk | What you see | How the kit handles it |
|---|---|---|
| **Per-cell battery voltage** | `battery.voltage: 2.22` | 2.22 V is lead-acid float per cell. `override.battery.packs = 6` (12 V) or `12` (24 V) + `battery_voltage_reports_one_pack` |
| **Fixed 50 Hz** | `input.frequency: 50.0` even in a 60 Hz country | The firmware lies; ignore it |
| **LB flag unreliable** | `LB` can assert while the battery is fine | `ignorelb` + `override.battery.charge.low = 30` (low battery is derived from the charge) |
| **BL/I/F answer zeros without warm-up** | standalone `--battery`/`--info`/`--ratings` return zeros | The warm-up lock-step (string 0/1 + interleaved F/Q1/I) must run first; NUT hunnox does it |
| **Standalone query while NUT runs wedges the chip** | device stops answering, re-enumerates | Never run `driver.py` while `nut-driver@...` is active; the standalone units `Conflicts=` with NUT; autoheal recovers it |
| **Estimated % is voltage-based** | `battery.charge` drops ~25 points the moment it goes on battery | Voltage sags under load; the estimate comes from `default.battery.voltage.{nominal,high,low}` = 12 / 13.2 / 10.4. The UPS LCD shows its own % — trust the trend, not the number |
| **Zeros after a replug** | all values 0 for ~1 min | `pollinterval = 2` brings it back (mimics UPSmart's ~1 Hz) |
| **Fragile firmware** | device vanishes from `lsusb` | `sudo bash install.sh --unwedge`, or let `nobreak-autoheal` do it |
| **Dangerous indices** | — | string indices `0x68`/`0x69` **shut the UPS down**; nothing in the kit uses them |

## The story (why this exists)

One day — **2026-10-28** — one stubborn UPS:

1. The UPS showed up in `lsusb` as `0001:0000 Fry's Electronics MEC0003`,
   and NUT's `nutdrv_qx` went into a **crash-loop**, hammering the device
   every 2 s with the wrong protocol over the wrong transport.
2. The fragile USB firmware **wedged**: the device vanished and reappeared
   constantly (3 re-enumerations in 30 s in `dmesg` —
   [`captures/2026-10-28-crash-loop-dmesg.txt`](captures/2026-10-28-crash-loop-dmesg.txt)).
3. udev/journal forensics → NUT issues [#1539][n1539] and [#2208][n2208],
   the NUT HCL, and the Brazilian projects [smsUps][smsups] and
   [nobreakSMS][nobreaksms].
4. **AI agents** extracted the full protocol from existing open-source code;
   [REA][rea] ("reverse engineer anything") inspected the `nutdrv_qx` binary
   and confirmed the hunnox string-index table (evidence in
   [`EVIDENCE-REA.md`](EVIDENCE-REA.md)).
5. The finding: the chip carries **Megatec ASCII commands inside USB
   string-descriptor requests** — the string index IS the opcode
   (`Q1`=0x03, `F`=0x0d, `I`=0x0c, battery=0xf3), with a fixed langid
   `0x0409`, `wLength ≤ 102`, and interleaved reads — the same "MEGA(USB)"
   mode used by the vendor's Windows software, UPSmart.
6. Fix applied live (`subdriver=hunnox` + `protocol=q1` + `langid_fix` +
   `noscanlangid`), the wedged chip revived via a sysfs USB "authorized"
   cycle (software replug) — and the values woke up from all-zeros:
   **231.2 V input, 219.8 V output, 8% load, status OL**.
7. Later the same day the kit was verified on battery (on-battery telemetry
   checked live), and `nobreak-autoheal` recovered a wedged chip by itself
   at level 2 (sysfs authorized cycle).

## How it works

```
+------------------+  GET_DESCRIPTOR(STRING), index = opcode      +-----------+
| driver.py   or   |  Q1 -> 0x03 | F -> 0x0d | I -> 0x0c          |  MEC0003  |
| NUT nutdrv_qx    | -------------------------------------------->|   (USB)   |
| (subdrv hunnox)  |<---------------------------------------------|           |
+------------------+   reply UTF-16LE -> ASCII (Megatec)          +-----+-----+
      |                                                             |
      v                                                             v
upsc / upsmon / guardian / MQTT / Home Assistant          Megatec firmware (Q1/F/I)
```

Full reference (bytes, checksums, both protocols, the hazards):
[`PROTOCOL.md`](PROTOCOL.md). The chip's 624-byte HID report descriptor is
a decoy: no software uses its usages.

## Files

| Path | What |
|---|---|
| `driver.toml` | metadata read by `install.sh --driver mec0003` |
| `nut/ups.conf` | the proven NUT section |
| `udev/99-nobreak-mec0003.rules` | raw USB access for the `nut` group |
| `driver.py` | standalone driver + MQTT bridge (`--selftest` for CI) |
| `systemd/` | `nobreak-mec0003.service` (standalone), `nobreak-mec0003-mqtt.service` |
| `tests/` | parser tests from real frames |
| `PROTOCOL.md`, `EVIDENCE-REA.md`, `rea-evidence/` | protocol reference and reverse-engineering evidence |
| `captures/` | real captures from 2026-10-28 |

## Credits

- [NUT — Network UPS Tools](https://networkupstools.org/) and the
  `nutdrv_qx` `hunnox`/`krauler` subdrivers; issues [#1539][n1539],
  [#2208][n2208] and [#1326][n1326] documented the chip's behavior.
- [dmslabsbr/smsUps][smsups] and [petersenna/nobreakSMS][nobreaksms] —
  Brazilian projects that decoded the SMS binary serial protocol.
- **UPSmart** (the vendor's Windows software) — its "MEGA(USB)" mode is the
  transport this driver replicates.
- [REA — Reverse Engineer Anything][rea].

[n1539]: https://github.com/networkupstools/nut/issues/1539
[n2208]: https://github.com/networkupstools/nut/issues/2208
[n1326]: https://github.com/networkupstools/nut/issues/1326
[smsups]: https://github.com/dmslabsbr/smsUps
[nobreaksms]: https://github.com/petersenna/nobreakSMS
[rea]: https://github.com/morluto/rea
