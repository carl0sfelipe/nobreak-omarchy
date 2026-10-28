# Tests — MEC0003 driver

No hardware and no root: the tests only exercise parsers/checksums against
frames captured from real devices (see `frames/README.md`).

How to run (from the repository root):

```sh
python3 -m venv .venv-test
.venv-test/bin/pip install pytest pyusb pyserial
.venv-test/bin/python -m pytest -q
```

`paho-mqtt` is **not** installed on purpose (light CI): the tests do not
import paho — the driver only imports it when `--mqtt` is used.

Self-check built into the driver itself (same checks, no pytest):

```sh
python3 drivers/mec0003/driver.py --selftest
```
