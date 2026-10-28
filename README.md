# nobreak-omarchy

**Community UPS ("nobreak") support kit for [Omarchy](https://omarchy.org) — Arch Linux + Hyprland — and other systemd desktops. Driver-pluggable: MEC0003 is the first driver; yours can be next.**

[![CI](https://github.com/carl0sfelipe/nobreak-omarchy/actions/workflows/ci.yml/badge.svg)](https://github.com/carl0sfelipe/nobreak-omarchy/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-yellow.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)

[Português](README.pt-BR.md)

Cheap UPSes are everywhere, and many of them barely work on Linux: odd USB
chips, firmware that wedges, NUT configs nobody wrote down. nobreak-omarchy
packages what it takes to make one *actually useful* on a Linux desktop —
and makes it easy for the community to add the next UPS.

## What the core gives you

| Piece | What it does |
|---|---|
| **Power guardian** (`core/guardian`) | User service that watches the UPS via NUT and sends **desktop notifications** (mako/Hyprland, GNOME, KDE) on power outage, power restored and low battery. Logs every event as JSON lines to `~/.local/state/nobreak-omarchy/events.jsonl`. Optional hooks: `--on-cmd 'systemctl suspend'`. |
| **USB autoheal** (`core/autoheal`) | System timer (every 2 min). If NUT loses the UPS for 2 checks in a row, it replugs the USB *by software*, escalating: `usbreset` → sysfs authorized cycle → xHCI controller rebind. Max 4 heals/hour. |
| **NUT config** | Each driver ships a proven `ups.conf` section; the installer writes it idempotently (with backup) and validates with `upsc`. Works with `upsmon` for clean shutdowns. |
| **MQTT / Home Assistant bridge** | Drivers with a standalone daemon can publish to MQTT with Home Assistant auto-discovery. |
| **Installer** | `install.sh --check` (diagnostics, no root), `--driver <name>`, `--unwedge`, `--dry-run`; `uninstall.sh` to undo. |

## Supported drivers

| Driver | USB ID | Brands | NUT driver | Autoheal | Status |
|---|---|---|---|---|---|
| [`mec0003`](drivers/mec0003/) | `0001:0000` ("Fry's Electronics MEC0003") | SMS, NHS, Powercool, DEXP, Hunnox, Eurocase, CPC | `nutdrv_qx` (hunnox) | yes | tested live 2026-10-28: on-battery telemetry verified, autoheal verified |
| *yours?* | | | | | see [Add your UPS](#add-your-ups) |

Check yours: `lsusb` and look for the USB ID.

## Quickstart

```console
$ git clone https://github.com/carl0sfelipe/nobreak-omarchy.git
$ cd nobreak-omarchy
$ bash install.sh --check                    # diagnostics: finds the UPS, checks NUT and deps
$ sudo bash install.sh --driver mec0003      # NUT config + udev + autoheal + guardian
$ upsc nobreak@localhost
$ python3 core/guardian/guardian.py --dry-run   # see the notifications
```

Requirements: `nut`, `python3`, `libnotify` (`notify-send`), systemd.
On Omarchy/Arch: `sudo pacman -S nut libnotify`.

Useful flags: `--battery 12|24`, `--name <ups>`, `--mode nut|standalone|mqtt`,
`--no-guardian`, `--no-autoheal`, `--list-drivers`, `--dry-run`.

### The guardian

```console
$ systemctl --user status nobreak-guardian
$ tail -f ~/.local/state/nobreak-omarchy/events.jsonl
{"ts": "...", "event": "power_outage", "ups_status": "OB", "input_v": 0.0, ...}
```

Events: `monitoring_started`, `power_outage`, `power_restored`,
`battery_low`, `status_change`, `ups_not_responding`.

CLI: `guardian.py [--ups nobreak@localhost] [--interval 5] [--once] [--dry-run] [--on-cmd CMD] [--restore-cmd CMD]`.

> **Migrating from nobreak-mec0003:** the guardian used to log to
> `~/.local/state/nobreak-mec0003/eventos.jsonl` with Portuguese event names
> (`falta_de_luz`, `energia_volvou`, `bateria_baixa`, `inicio_monitoramento`…).
> It now writes `~/.local/state/nobreak-omarchy/events.jsonl` with English
> names and the key `event` instead of `evento`. The old file is left alone —
> keep it as history or move it. The unit is now `nobreak-guardian.service`
> (was `nobreak-guardiao.service`) and autoheal is `nobreak-autoheal`
> (was `nobreak-autocura`); the old `--intervalo`, `--forcar` and `--nivel`
> flags are still accepted.

### Autoheal

```console
$ systemctl list-timers nobreak-autoheal.timer
$ journalctl -t nobreak-autoheal
$ sudo nobreak-autoheal --force          # heal now
```

Configured by `/etc/nobreak-omarchy/autoheal.env` (written by the installer):
`NOBREAK_VIDPID` (default `0001:0000`), `NOBREAK_UPS` (default
`nobreak@localhost`), `NOBREAK_NUT_UNIT` (default `nut-driver@<ups>.service`).
"Healthy" means `upsc` answers and input or output voltage is above 0.

## Repository layout

```
core/guardian/     power guardian (user service, notifications)
core/autoheal/     USB autoheal script + systemd timer
drivers/<name>/    one directory per UPS: driver.toml, nut/ups.conf, udev/, README, tests
drivers/_template/ skeleton for a new driver
install.sh         installer (--driver, --check, --unwedge, --dry-run)
uninstall.sh       uninstaller
tests/             core tests
```

## Add your UPS

Got a UPS that is not in the table? You can add it — no Python required if
NUT already speaks to it with the right options:

1. `cp -r drivers/_template drivers/<name>` and fill `driver.toml`.
2. Put the working NUT section in `drivers/<name>/nut/ups.conf`.
3. Capture evidence: `lsusb -v`, and `upsc` **on mains and on battery**.
4. Open a PR.

Full guide: [CONTRIBUTING.md](CONTRIBUTING.md).

## The MEC0003 story

The project started with one stubborn UPS: a generic MEC0003 chip that made
NUT crash-loop and wedged its own USB firmware. A day of forensics, NUT
issues, old Brazilian SMS projects, AI agents and [REA](https://github.com/morluto/rea)
(reverse engineering of the `nutdrv_qx` binary) found the trick: Megatec
commands tunneled in USB string descriptors. The full story, the quirks and
the protocol are in [`drivers/mec0003/`](drivers/mec0003/README.md).

## License

[MIT](LICENSE). Launch notes: [`docs/LAUNCH.md`](docs/LAUNCH.md).
