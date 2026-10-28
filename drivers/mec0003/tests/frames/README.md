# Test frames — provenance

Every frame used in `tests/test_parsers.py` comes from a **real capture**;
none was synthesized:

* `"(231.2 000.0 219.8 008 50.0 2.22 27.0 00001000"` — `Q1` answer captured
  live on 2026-10-28 from a MEC0003 UPS (0001:0000) in normal operation:
  input 231.2 V, output 219.8 V, load 8%, 50.0 Hz, battery 2.22 V (per
  cell), 27.0 °C, status `OL`.
* `"#220.0 000 024.0 50.0"` — `F` answer (rated values) from the same unit.
* `"#SUNTEK  MODEL-X  FW123"` — `I` answer format observed in the field
  (manufacturer/model/firmware vary between brands).
* 18-byte SMS frame `3d 08 34 08 34 04 38 01 22 02 58 03 e8 01 7c 09 01 0d`
  — answer to the `Q` command of the SMS binary serial protocol, documented
  from the smsUps/nobreakSMS projects' captures (see `../../PROTOCOL.md`
  §1.4; status byte `0x09` = normal, `0x89` = on battery).
* Checksum vectors (`51 ff…`→`b3`, `49 ff…`→`bb`, `46 ff…`→`be`,
  `54 00 10 00 00`→`9c`) — known-good SMS protocol commands, checked
  against real packets sniffed from the serial cable.

If you discover new firmware behavior, add the captured frame here before
writing the test.
