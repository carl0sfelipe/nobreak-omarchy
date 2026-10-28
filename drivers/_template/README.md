# Driver: <brand / chip>

> Copy this directory to `drivers/<name>/` and replace every `<...>`.

## Compatibility

`lsusb` shows: `ID <vid>:<pid> <vendor string>`

Brands/models confirmed: <list — only what someone actually tested>

## Status

<untested | tested live YYYY-MM-DD: what was verified (on mains, on battery,
autoheal)>

## Install

```console
$ sudo bash install.sh --driver <name>
$ upsc nobreak@localhost
```

## Known quirks

- <per-cell battery voltage? fixed frequency? unreliable LB flag? ...>

## Contributor checklist

- [ ] `driver.toml` filled (name, vid_pid, nut_driver, autoheal, status, maintainer)
- [ ] `nut/ups.conf` with only verified options, each explained in a comment
- [ ] `captures/lsusb-v.txt` — `lsusb -v -d <vid>:<pid>` (remove serial numbers)
- [ ] `captures/upsc-mains.txt` — `upsc nobreak@localhost` on mains power
- [ ] `captures/upsc-battery.txt` — `upsc nobreak@localhost` with the UPS unplugged from the wall
- [ ] if `autoheal = true`: journal lines showing `nobreak-autoheal` recovering it
- [ ] tests from real frames under `tests/` (if you ship a standalone `driver.py` or parsers)
- [ ] udev rule under `udev/` (only if raw USB access needs it)
- [ ] this README: compatibility, status, quirks
- [ ] a row in the supported-drivers table of the main `README.md` and `README.pt-BR.md`
