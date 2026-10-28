# Protocol reference — SMS/NHS/generic UPSes with the MEC0003 chip (0001:0000)

> Extracted by code analysis of the dmslabsbr/smsUps and petersenna/nobreakSMS
> projects, the NUT subdrivers (blazer_usb.c, nutdrv_qx.c,
> nutdrv_qx_megatec.c, nutdrv_qx_hunnox.c) and NUT issues #1326, #2208 and #307.

## 0. Overview: there are TWO hardware/protocol stacks

| Stack | USB chip | USB IDs | Protocol | Implemented by |
|---|---|---|---|---|
| A | Cypress CY7C63xxx "HID→COM RS232" (SMS Manager III Senoidal cable) | `04b4:5500` | SMS **binary**: 7-byte packets at 2400 baud 8N1 tunneled over HID | kernel driver `cypress_m8` → `/dev/ttyUSB0`; smsUps + nobreakSMS |
| B | Generic "Fry's Electronics" MEC0003 chip (SMS, NHS, Powercool, CPC, DEXP, Hunnox, Eurocase…) | `0001:0000`, product "MEC0003", iManufacturer=0, iSerial=0 | **Megatec ASCII** (`Q1\r`, `F\r`, `I\r`, `S\r`…) in HID SET_REPORT reports **or** inside string GET_DESCRIPTOR requests (UPSmart "MEGA(USB)" mode) | NUT `nutdrv_qx` subdriver `hunnox`/`krauler`; `driver.py` in this directory |

## 1. Stack A — SMS binary serial protocol (smsUps/nobreakSMS)

### 1.1 Transport

Serial 2400 baud, 8N1, raw. Host command = **7 bytes**; UPS answer =
**18 bytes**, first byte a marker (`=`/`:`/`;` depending on the command), last
byte `0x0D`.

### 1.2 Framing and checksum

Host packet = `[ASCII letter][4 arg bytes][checksum][0x0D]`, where
`checksum = (0x100 - (sum(bytes[0..4]) & 0xFF)) & 0xFF`. Unused args:
`0xFF` (commands without parameters) or `0x00`. Bytes may be written one at a
time with 100 ms between them (more conservative).

### 1.3 Commands

| Query | Bytes | Meaning | Observed answer |
|---|---|---|---|
| Q | `51 ff ff ff ff b3 0d` | status | 18 bytes (§1.4) |
| I | `49 ff ff ff ff bb 0d` | name + firmware | `:SENOIDAL    7.0b\r` / `:M3 SENOIDAL 2.0\r` |
| F | `46 ff ff ff ff be 0d` | characteristics | `;EBiS115000 2460o` |
| D | `44 ff ff ff ff c0 0d` | abort battery test | — |
| G | `47 01 ff ff ff bb 0d` | initialization (optional) | — |
| M | `4d ff ff ff ff b7 0d` | toggle buzzer | — |
| T | `54 hh ll 00 00 ck 0d` | battery test for n s (n = BE arg) | — |
| C | `43 ff ff ff ff c1 0d` | cancel shutdown/restore | — |
| L | `4c ff ff ff ff …` | test until battery low | — |
| R | `52 00 C8 27 0F B0 0D` | shutdown + restore | — |

### 1.4 `Q` answer (18 bytes)

| Offset | Size | Field | Encoding | Example → value |
|---|---|---|---|---|
| 0 | 1 | marker | `=` 0x3D | — |
| 1–2 | 2 | last input voltage | u16 BE ÷10 → V | `08 34` → 210.0 V |
| 3–4 | 2 | input voltage | u16 BE ÷10 → V | — |
| 5–6 | 2 | output voltage | u16 BE ÷10 → V | `04 38` → 108.0 V |
| 7–8 | 2 | output power | u16 BE ÷10 → % | `01 22` → 29.0 % |
| 9–10 | 2 | output frequency | u16 BE ÷10 → Hz | `02 58` → 60.0 Hz |
| 11–12 | 2 | battery level | u16 BE ÷10 → % | `03 e8` → 100 % |
| 13–14 | 2 | temperature | u16 BE ÷10 → °C | `01 7c` → 38.0 °C |
| 15 | 1 | status bits | §1.5 | — |
| 16 | 1 | unknown (0x01) | — | — |
| 17 | 1 | terminator | 0x0D | — |

Sanity ranges: V ∈ [0,270], % ∈ [0,100], Hz ∈ [40,70], °C ∈ [−20,70].

### 1.5 Status bits (offset 15)

| Bit | Meaning |
|---|---|
| 0 | Beeper on |
| 1 | Shutdown active |
| 2 | Test active |
| 3 | UPS OK (output energized) |
| 4 | Boost |
| 5 | Bypass |
| 6 | Battery low |
| 7 | On battery |

Real observed values: `0x09` normal; `0x89` unplugged from mains;
`0x8d`/`0x8c` battery test with/without beeper.

## 2. Stack B — MEC0003 USB HID transport (the chip of this UPS)

### 2.1 Real descriptors

`0001:0000`, bcdDevice 1.00, 1 interface class 3 (HID), 2 interrupt
endpoints of 8 bytes: `EP 0x81 IN` and `EP 0x02 OUT`, bInterval 10.
bcdHID 1.11, 624-byte report descriptor (often unreadable — and
irrelevant: no software uses its structured usages).

### 2.2 Method A — HID SET_REPORT tunnel

The Megatec ASCII stream is sliced into 8-byte output reports (report ID
0x00) sent as a SET_REPORT **control transfer**
(`0x21/0x09/wValue=0x0200`), answer on **EP 0x81** in 8-byte chunks until
`\r` shows up. No header/CRC — the payload is the serial stream itself
(command + `\r`, zero-padded).

### 2.3 Method B — UPSmart "MEGA(USB)" mode (what NUT hunnox uses)

Commands travel as **GET_DESCRIPTOR(STRING)**; the **string index is the
opcode**:

| Command | Index | Answer |
|---|---|---|
| `Q1\r` (status) | `0x03` | `(MMM.M NNN.N OOO.O PPP QQ.Q RR.R SS.S bbbbbbbb` (47 bytes) |
| `F\r` (ratings) | `0x0d` | `#220.0 000 024.0 50.0` |
| `I\r` (info) | `0x0c` | `#manuf  model  firmware` |
| `Q\r` (beeper) | `0x07` | — |
| `C\r` (cancel) | `0x0a` | — |
| `T\r` (test) | `0x04` | — |
| `TL\r` (test until low) | `0x05` | — |
| `BL\r` (charge %) | `0xf3` | `BLnn` |
| ⚠ dangerous | `0x68`/`0x69` | **shut the UPS down** — never use |

Critical details:
- **fixed** langid `0x0409` (default negotiation wedges the firmware);
- `wLength ≤ 102` (0x66) — value measured from the Windows client; larger wedges the USB;
- answer = UNICODE_STRING descriptor (len + 0x03 + UTF-16LE) → convert to
  ASCII by taking 1 byte out of every 2 from offset 2;
- validate: returned length == first byte of the descriptor;
- `"UPS No Ack"` (10 chars) = command accepted with no answer.

### 2.4 Mandatory initialization sequence

Until the vendor client has run once after the plug, the device answers
**all zeros** (NUT #2208). hunnox replicates the UPSmart pattern: at start,
read string 0 (langid list, wLength 1026) twice + string 1, 10 ms pause; and
**interleave dummy F/Q1/I reads** between real polls (UPSmart does ~1 poll/s
and the companion reads keep the values alive).

Field note (2026-10-28): standalone `BL`/`I`/`F` queries without that
warm-up answer zeros, and a standalone query sent while NUT is polling the
chip **wedges it** (concurrent access). Never query the chip directly while
`nut-driver@...` is running.

### 2.5 Shutdown via string index (hunnox/fabula)

```
delay ∈ [0.5 .. 10] min:
  < 1 min : index = 16 + round((delay − 0.5) × 10) × 16
  ≥ 1 min : index = 96 + (delay − 1) × 16
  + 8 to power back on afterwards (fixed 10 s restart)
e.g.: 0x10 = stay off 30 s · 0x18 = off and back on after 30 s · 0xF8 = 10 min, restarting
```

### 2.6 Megatec ASCII payloads

```
> Q1\r
< (226.0 195.0 226.0 014 49.0 27.5 30.0 00001000\r
  │1-5 input V · 7-11 fault V · 13-17 output V · 19-21 load % ·
  23-26 Hz · 28-31 battery V · 33-36 temp °C · 38-45 flags (each char 0/1:
  utility_fail, battery_low, bypass/boost, ups_failed, type, test,
  shutdown, beeper)
```

## 3. Quirks checklist

1. Without the warm-up sequence (§2.4) → zeroed values; a replug resets it.
2. A large `wLength` wedges the chip; always use ≤ 102 on the command channel.
3. Do not use `usb_get_string_simple` (langid scan) — fixed langid.
4. The kernel `usbhid` driver gets in the way; detach it before using libusb.
5. Fragile firmware: after a wedge it re-enumerates (the driver must reopen).
   With `subdriver=hunnox`, `pollinterval = 2` is safe (it mimics UPSmart's ~1 Hz).
6. The 624-byte report descriptor (report IDs 1–5, Power Device Page) is a
   "decoy": no software uses the structured usages.
7. For serial use of the MEC0003: `modprobe usbserial vendor=0x0001 product=0x0000`
   (after detaching usbhid); low-speed limits it to ~4800 baud.
8. `battery.voltage` is per cell; input frequency is a fixed 50.0 Hz; the LB
   flag is unreliable (use `ignorelb` + `override.battery.charge.low`).

## Sources

- [dmslabsbr/smsUps](https://github.com/dmslabsbr/smsUps) — smsUPS.py, tst.txt, DOCS.md
- [petersenna/nobreakSMS](https://github.com/petersenna/nobreakSMS) — userland/nobreakSMS.c
- [NUT nutdrv_qx.c](https://github.com/networkupstools/nut/blob/master/drivers/nutdrv_qx.c) · [blazer_usb.c](https://github.com/networkupstools/nut/blob/master/drivers/blazer_usb.c) · [nutdrv_qx_megatec.c](https://github.com/networkupstools/nut/blob/master/drivers/nutdrv_qx_megatec.c)
- NUT issues: [#1326](https://github.com/networkupstools/nut/issues/1326) · [#2208](https://github.com/networkupstools/nut/issues/2208) · [#307](https://github.com/networkupstools/nut/issues/307) · [#1539](https://github.com/networkupstools/nut/issues/1539)
- [NUT HCL](https://networkupstools.org/stable-hcl.html)
- [cypress_m8 (Linux kernel)](https://github.com/torvalds/linux/blob/master/drivers/usb/serial/cypress_m8.c)
- [nut-upsdev 2014 thread (lsusb of the Manager III cable)](https://alioth-lists.debian.net/pipermail/nut-upsdev/2014-February/006657.html)
