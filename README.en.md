# nobreak-mec0003

**A complete Linux driver kit for UPSes with the MEC0003 USB chip (`0001:0000`) — the "Fry's Electronics" devices in your `lsusb`.**

[![CI](https://github.com/carl0sfelipe/nobreak-mec0003/actions/workflows/ci.yml/badge.svg)](https://github.com/carl0sfelipe/nobreak-mec0003/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-yellow.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)

This generic chip ships in UPSes from dozens of brands worldwide (SMS, NHS,
Powercool, DEXP, Hunnox, Eurocase…). It has no first-class Linux support and
makes NUT's `nutdrv_qx` crash-loop. The kit provides: a working NUT
configuration, a standalone Python driver, an MQTT/Home Assistant bridge, an
installer with an unwedge mode, and a full protocol reference.

---

## The story (why this exists)

One day — **2026-10-28** — one stubborn UPS:

1. The UPS showed up in `lsusb` as `0001:0000 Fry's Electronics MEC0003`,
   and NUT's `nutdrv_qx` went into a **crash-loop**, hammering the device
   every 2 s with the wrong protocol over the wrong transport.
2. The fragile USB firmware **wedged**: the device vanished and reappeared
   constantly (3 re-enumerations in 30 s in `dmesg`).
3. udev/journal forensics → NUT issues [#1539][n1539] and [#2208][n2208],
   the NUT HCL, and the Brazilian projects [smsUps][smsups] and
   [nobreakSMS][nobreaksms].
4. **AI agents** extracted the full protocol from existing open-source code;
   [REA][rea] ("reverse engineer anything") inspected the `nutdrv_qx` binary
   and confirmed the hunnox string-index table (evidence in
   [`docs/EVIDENCIA-REA.md`](docs/EVIDENCIA-REA.md)).
5. The finding: the chip carries **Megatec ASCII commands inside USB
   string-descriptor requests** — the string index IS the opcode
   (`Q1`=0x03, `F`=0x0d, `I`=0x0c, battery=0xf3), with a fixed langid
   `0x0409`, `wLength ≤ 102`, and interleaved reads — the same "MEGA(USB)"
   mode used by the vendor's Windows software, UPSmart.
6. Fix applied live (`subdriver=hunnox` + `protocol=q1` + `langid_fix` +
   `noscanlangid`), the wedged chip revived via a sysfs USB "authorized"
   cycle (software replug) — and the values woke up from all-zeros:
   **231.2 V input, 219.8 V output, 8% load, status OL**.

---

## Is my UPS compatible?

```console
$ lsusb | grep 0001:0000
Bus 001 Device 005: ID 0001:0000 Fry's Electronics MEC0003
```

That's it: if you see `0001:0000`, your UPS uses the MEC0003 chip. The
"Fry's Electronics" name is just how usb.ids labels that generic vendor ID —
your UPS did not come from Fry's.

## Quickstart (30 seconds)

```console
$ git clone https://github.com/carl0sfelipe/nobreak-mec0003.git
$ cd nobreak-mec0003
$ bash install.sh --check      # diagnostics: finds the UPS, checks NUT and dependencies
$ sudo bash install.sh         # installs the NUT kit (config + udev + services)
$ upsc nobreak@localhost
```

If a previous `nutdrv_qx` setup is already crash-looping your device, the
installer detects it and unwedges with a sysfs "authorized" cycle (a
software replug). Real output after install:

```console
$ upsc nobreak@localhost
battery.voltage: 2.22
input.voltage: 230.9
output.voltage: 219.8
ups.load: 8
ups.status: OL
ups.temperature: 27.0
```

(Full capture: [`docs/capturas/2026-10-28-upsc-funcionando.txt`](docs/capturas/2026-10-28-upsc-funcionando.txt))

### Without NUT: standalone driver

```console
$ python3 mec0003.py --watch    # one read per second, reopens after a wedge
$ python3 mec0003.py --json     # for scripts
$ python3 mec0003.py --info     # manufacturer / model / firmware
$ python3 mec0003.py --battery  # battery charge %
$ python3 mec0003.py --ratings  # nominal values (F)
```

Three transports, in case one doesn't work on your unit:
`--method string` (default, UPSmart mode), `--method setreport` (classic
HID tunnel), and `--method serial` (the SMS binary protocol, 2400 baud 8N1,
for serial-cable models).

### Home Assistant / MQTT

```console
$ sudo bash install.sh --mqtt   # installs and enables the bridge service
$ systemctl status nobreak-mec0003-mqtt
```

The bridge publishes values over MQTT with Home Assistant
**auto-discovery**: voltage, load, battery, temperature and status sensors
appear on their own — no YAML.

## What you get

| Data | NUT variable | Real sample |
|---|---|---|
| Input voltage | `input.voltage` | 230.9 V |
| Output voltage | `output.voltage` | 219.8 V |
| Load | `ups.load` | 8% |
| Battery voltage | `battery.voltage` | 2.22 V/cell (see below) |
| Battery charge | `battery.charge` | 100% |
| Temperature | `ups.temperature` | 27.0 °C |
| Status | `ups.status` | `OL` (on line) / `OB` (on battery) / `LB` (low battery) |
| Estimated runtime | `battery.runtime` | via `runtimecal` in `ups.conf` |

With `upsmon` configured, you get a clean server shutdown when the power
goes out — which is the point of owning a UPS.

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| All values zeroed | Missing warm-up sequence (firmware returns zeros until someone replicates the UPSmart handshake) | Run the driver/installer in full (it does the warm-up); if it persists, physically replug |
| Device vanishes from `lsusb` | Wedged firmware (old driver crash-loop) | `bash install.sh --unwedge` (sysfs "authorized" cycle) or physical replug; then use the kit config |
| `Input/Output Error` in NUT | langid scanning or wrong transport | Kit `ups.conf`: `subdriver=hunnox`, `protocol=q1`, `langid_fix=0x0409`, `noscanlangid` |
| Frequency always 50.0 Hz (in a 60 Hz country) | The firmware **lies** — it reports a fixed 50.0 | Ignore the value; known firmware defect, not a driver bug |
| `battery.voltage: 2.22` looks wrong | Firmware reports **per-cell** voltage (2.22 V = lead-acid float per cell) | 12 V battery = 6 cells: set `battery.packs = 6` in `ups.conf` (the driver multiplies) |
| NUT wedges it again later | Old config without `subdriver=hunnox` — the wrong transport crashes the firmware | Use the kit config: with hunnox, `pollinterval = 2` is safe and keeps values alive (~1 Hz, like UPSmart) |

**Important:** never send string indices `0x68`/`0x69` to the chip — they
**shut the UPS down**. The driver and the kit config never use them.

## How it works

1. The software (Python driver or NUT `nutdrv_qx`/hunnox) opens the
   `0001:0000` device via libusb (a udev rule grants access without root).
2. Instead of regular HID, it sends the Megatec command **as a string
   `GET_DESCRIPTOR`**: the string index is the opcode.
3. The MEC0003 chip answers the descriptor in UTF-16LE; we convert to ASCII.
4. A warm-up sequence plus interleaved F/Q1/I reads keep the firmware
   "awake" (this is what UPSmart does).
5. Megatec parsing feeds NUT variables / JSON / MQTT — and `upsmon`, Home
   Assistant, etc. can finally see the UPS.

```
+------------------+  GET_DESCRIPTOR(STRING), index = opcode      +-----------+
| mec0003.py  or   |  Q1 -> 0x03 | F -> 0x0d | I -> 0x0c          |  MEC0003  |
| NUT nutdrv_qx    | -------------------------------------------->|   (USB)   |
| (subdrv hunnox)  |<---------------------------------------------|           |
+------------------+   reply UTF-16LE -> ASCII (Megatec)          +-----+-----+
      |                                                             |
      v                                                             v
upsc / upsmon / MQTT / Home Assistant                     Megatec firmware (Q1/F/I)
```

The complete reference (bytes, checksums, both protocols, the hazards) is
in [`docs/PROTOCOLO.md`](docs/PROTOCOLO.md) (in Portuguese). The chip's
624-byte HID report descriptor is a decoy: no software uses its usages.

## Compatibility

Chip `0001:0000`, product "MEC0003". Brands where the chip has been found:

SMS · NHS · Powercool · DEXP · Hunnox · Eurocase · CPC

**Did it work with your model?** Open an issue (or a PR editing this list)
adding brand/model — that is how the list grows. SMS serial-cable models
(Cypress chip `04b4:5500`) are also supported via `--method serial`.

## Credits

This project is a convenience layer on top of people who broke this
protocol before us:

- [NUT — Network UPS Tools](https://networkupstools.org/) and the
  `nutdrv_qx` `hunnox`/`krauler` subdrivers; issues [#1539][n1539],
  [#2208][n2208] and [#1326][n1326] documented the chip's behavior.
- [dmslabsbr/smsUps][smsups] and [petersenna/nobreakSMS][nobreaksms] —
  Brazilian projects that decoded the SMS binary serial protocol.
- **UPSmart** (the vendor's Windows software) — reverse-engineering
  reference: its "MEGA(USB)" mode is the transport this driver replicates.
- [REA — Reverse Engineer Anything][rea] — used to inspect the `nutdrv_qx`
  binary and confirm the index table (see
  [`docs/EVIDENCIA-REA.md`](docs/EVIDENCIA-REA.md)).

[n1539]: https://github.com/networkupstools/nut/issues/1539
[n2208]: https://github.com/networkupstools/nut/issues/2208
[n1326]: https://github.com/networkupstools/nut/issues/1326
[smsups]: https://github.com/dmslabsbr/smsUps
[nobreaksms]: https://github.com/petersenna/nobreakSMS
[rea]: https://github.com/morluto/rea

## License

[MIT](LICENSE) — built with AI agents (ZCode + [REA][rea]) in one day of
diagnostics. The full story, in post form (Portuguese), is in
[`docs/POST-LANCAMENTO.md`](docs/POST-LANCAMENTO.md).
