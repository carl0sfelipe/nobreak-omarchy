# Contributing to nobreak-omarchy

Contributions are very welcome — issues and PRs in **English or
Portuguese**. This project exists because lots of people own a UPS
("nobreak") with poor Linux support; every confirmed model and every
protocol finding helps someone else.

## Ways to help

1. **Add a driver** for a UPS that is not supported yet (below).
2. **Confirm a model** for an existing driver — open an issue titled
   `Model: <brand> <model> (<driver>)` with `lsusb` and `upsc` output.
3. **Captured frames** — raw answers from your device become test fixtures
   (`drivers/<name>/tests/frames/`).
4. **Core improvements** — guardian, autoheal, installer.

## Adding a driver

A "driver" in nobreak-omarchy is a directory under `drivers/` that tells the
kit how to talk to one family of UPS. Most of the time that is just a NUT
config — no code needed.

1. **Copy the template**

   ```console
   $ cp -r drivers/_template drivers/<name>     # lowercase, [a-z0-9_-]
   ```

2. **Fill `driver.toml`**: `name`, `vid_pid` (from `lsusb`), `nut_driver`,
   `ups_name`, `autoheal` (`true` only if you verified that a software
   replug recovers it), `modes`, `status`, `maintainer` (your GitHub handle).

3. **Provide the NUT config** in `drivers/<name>/nut/ups.conf` — the section
   that works for you, every non-obvious option explained in a comment.
   `install.sh --driver <name>` copies it to `/etc/nut/ups.conf`. If NUT
   cannot drive it, ship a standalone `driver.py` + units in `systemd/`
   (see `drivers/mec0003/` for an example) and set `nut_driver = ""`.

4. **Capture evidence** into `drivers/<name>/captures/` (strip serial numbers):

   ```console
   $ lsusb -v -d <vid>:<pid>       > captures/lsusb-v.txt
   $ upsc nobreak@localhost        > captures/upsc-mains.txt     # on mains
   # unplug the UPS from the wall for ~30 s:
   $ upsc nobreak@localhost        > captures/upsc-battery.txt   # on battery
   ```

   Both mains **and** battery captures are required: many quirks (LB flag,
   charge estimate, status bits) only show up on battery.

5. **Add tests from real frames** if you ship any parser
   (`drivers/<name>/tests/`, pytest, no hardware). Never synthesize a frame
   you have not seen on a real device.

6. **Write `drivers/<name>/README.md`**: compatibility (`lsusb` ID), status,
   known quirks, install line.

7. **Add a row** to the supported-drivers table in `README.md` and
   `README.pt-BR.md`.

Test your install path without touching the system:

```console
$ bash install.sh --driver <name> --dry-run --yes
$ bash install.sh --driver <name> --check
```

## Safety rules for protocol work

- Never send commands you have not seen documented or captured. On the
  MEC0003, string indices `0x68`/`0x69` **shut the UPS down**; other chips
  have similar traps. A "curious" scan can kill your equipment and that of
  whoever copies your code.
- Do not query the device directly while NUT is polling it (concurrent
  access wedges fragile firmware).
- Document every new command with its source (capture, test, reference code).

Tip: if you have the vendor's Windows software (UPSmart, "Manager III",
PowerView), [REA](https://github.com/morluto/rea) can extract the protocol
from the binary — see `drivers/mec0003/EVIDENCE-REA.md`.

## Code style

- Python 3.10+, standard library first; driver dependencies go in
  `requirements.txt` and must be optional for the tests (keep parsers
  importable without `pyusb`).
- Shell: bash, `set -euo pipefail` in entry points, must pass `bash -n` and
  ideally `shellcheck -x`. Reuse `scripts/lib.sh` helpers (`run`, `ok`,
  `warn`, `die`, dry-run aware).
- Everything user-facing (logs, notifications, CLI help) in English.
- Commit messages descriptive, no emoji.

## PR checklist

- [ ] `.venv-test/bin/python -m pytest -q` (or `pytest -q`) passes
- [ ] `bash -n install.sh uninstall.sh scripts/lib.sh core/autoheal/nobreak-autoheal`
- [ ] `bash install.sh --driver <name> --dry-run --yes` looks right
- [ ] new driver: `driver.toml`, `nut/ups.conf`, `README.md`, captures on mains **and** battery
- [ ] tested on real hardware — say which brand/model in the PR
- [ ] READMEs (EN + pt-BR) updated if behavior changed
- [ ] **no secrets**: no MQTT passwords, tokens, hostnames you care about,
      serial numbers or `.env` files in the commit

## License

By contributing you agree that your contribution is licensed under MIT
(see `LICENSE`).
