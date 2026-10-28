# REVERSE-ENGINEERING EVIDENCE — USB protocol of the MEC0003 chip (NUT `nutdrv_qx`, subdriver `hunnox`)

**Date:** 2026-10-28
**Tools:** REA (`rea-agents` npm) 6.8.0 + Ghidra 12.1.4 (installed in a user directory, no root) + binutils (`objdump`, `readelf`, `nm`, `strings`) + Arch Linux debug symbols via `debuginfod` (`DEBUGINFOD_URLS=https://debuginfod.archlinux.org`).

**Analyzed target:**

| Field | Value |
|---|---|
| Path | `/usr/lib/nut/nutdrv_qx` |
| SHA-256 | `812462090980c8275858a58910a6a5c90af4bcb3c04090239ea3d35cb5ddbfad` |
| Build-ID | `b2b5422ee0bcf6110637c82c580489a3d1abe62a` |
| Format | ELF 64-bit LSB PIE, x86-64, **stripped** (no `.symtab`; `.dynsym` + `.gnu_debuglink` → `nutdrv_qx.debug` remain) |
| Driver version | string `"2.8.5"` in `.rodata` (0x3eac0), confirmed by the package |
| Offset↔address mapping | identity in every section (`.text` 0x7040, `.rodata` 0x3b000, `.data` 0x54000) — file offset = virtual address |

> Note on addresses: in this section, addresses such as `0xe7a0` are ELF **file/virtual** addresses (used by `objdump`). Ghidra/REA rebased the image at `0x100000`, so `hunnox_command` = `0xe7a0` in objdump = `0x10e7a0` in REA.

---

## (a) What REA managed to do — commands and generated bundles

### Environment

- REA 6.8.0 via `PATH="$HOME/.local/share/mise/installs/node/24.22.1/bin:$PATH" npx -y rea-agents@latest <cmd>`.
- Initial state of REA's native providers: **ghidra** (`not_configured`, requires `GHIDRA_INSTALL_DIR` with Ghidra 12.1.x), **hopper** (`executable_missing`), **ida** (`not_configured`), **kuna** (`not_configured`). The **rizin provider does not exist** in REA 6.8.0 (there are `execute-rizin-command`/`debug-with-rizin` commands, but no registered rizin analysis provider; `capabilities` only lists `native-macos`, `rea-artifact-graph`, `rea-dotnet-static`, `sqlite` as available). Java 21.0.2 (mise) was present.
- Corrective action (no root): downloaded **Ghidra 12.1.4** (`ghidra_12.1.4_PUBLIC_20260921.zip`, GitHub releases) into `~/.local/opt/ghidra_12.1.4_PUBLIC` + `export GHIDRA_INSTALL_DIR=...`. No privileged installation was attempted or needed.

### Commands run and results

| REA command | Result | Bundle saved in `rea-evidence/` |
|---|---|---|
| `analyze /usr/lib/nut/nutdrv_qx` (no engine) | **FAILED** — `provider_unavailable` (candidates ghidra/hopper/ida/kuna rejected) | error recorded in the history below |
| `analyze /usr/lib/nut/nutdrv_qx` (with Ghidra) | **OK** — inventory: 679 procedures, 2137 strings, 29 sections; `evidence_id=ev_4cd63432aa0cf1971…` | `rea-analyze-nutdrv.json` |
| `decompile /usr/lib/nut/nutdrv_qx 0x10e7a0` | **OK** — Ghidra C pseudocode of `hunnox_command`; `evidence_id=ev_c7eb9d0aeb8fd579…` (op. `procedure_pseudo_code`, provider `ghidra`, confidence `observed`) | `rea-decompile-hunnox_command.json` |
| `function /usr/lib/nut/nutdrv_qx 0x10e7a0 --detail summary --evidence_output …` | **OK** — full dossier (`analyze_function`, `evidence_id=ev_a87dd6b2938c7092…`) with calls, incoming references (`fabula_hunnox_subdriver` at 0x10ab44 → hunnox_command) and native value flow | `rea-function-hunnox_command.json.gz` (unpack: `gunzip -c`) + `rea-function-hunnox_command.summary.json` |
| `inspect-elf-notes` | **OK** (needs no engine) — PT_NOTE/ABI-tag/build-id; `ev_a4d22490876abcb6…` | `rea-inspect-elf-notes.json` |
| `inspect-native-exports` | **OK** — ELF export table; `ev_f36efb9a8bb11431…` | `rea-inspect-native-exports.json` |
| `inspect-byte-entropy` | **OK** — per-block entropy; `ev_85ed44662a25b3a2…` | `rea-inspect-byte-entropy.json` |
| `decompile-all --address-start 0x10e7a0 --address-end 0x10f240 --limit 4` | **OK** (2nd attempt) — wrote `functions/0x10e7a0.c` (hunnox_command) and `functions/0x10f240.c` (ablerex_command) with a per-file SHA-256 in the index; `evidence_id=ev_2d18634bff66620e…`, provider `ghidra 12.1.4` | `rea-decompile-all.json`, `ghidra-pseudocode/` |
| `inspect-binary-layout` | **NOT run successfully** — requires caller-provided pwntools; `import pwn` unavailable on the host's Python 3.14 (no root to install it) | — |

### Excerpt of the REA/Ghidra pseudocode (`rea-decompile-hunnox_command.json`, `normalized_result`)

Confirms, at a high level, the same facts as the disassembly (relevant lines):

```c
local_460 = 0xf3;                                   // BL index in the stack table
...
uVar4 = 0x409;                                      // langid 0x0409
// step 0 (warm-up):
libusb_control_transfer(DAT_00277ca0,0x80,6,0x300,uVar4 & 0xffff,...);  // string 0
libusb_control_transfer(DAT_00277ca0,0x80,6,0x300,uVar4 & 0xffff,...);  // string 0 (2nd time)
libusb_control_transfer(DAT_00277ca0,0x80,6,0x301,uVar4 & 0xffff,...);  // string 1
//   (with puStack_4e0 = 0x3e8 timeout and pcStack_4e8 = 0x402 wLength)
pcVar8 = (char *)0x30d;   // warm-up step 1: string 0x0D (F)
pcVar8 = (char *)0x30c;   // warm-up step 3: string 0x0C (I)
pcVar8 = (char *)0x303;   // warm-up step 2: string 0x03 (Q1)
pcVar14 = (char *)0x66;   // wLength cap = 102 (several occurrences)
uVar4 = libusb_get_string_descriptor_ascii(...);    // alternate path (langid_fix == -1)
libusb_control_transfer(DAT_00277ca0,0x80,6,(ushort)uVar10 | 0x300,uVar15 & 0xffff,param_3);
                                                    // real command: wValue = 0x0300 | index
```

Header of the decompiled function: `FUN_0010e7a0(char *param_1, size_t param_2, undefined1 (*param_3)[16], char *param_4)` — consistent with the 4-argument ABI seen in the disassembly: `(cmd, cmdlen, answer, answer_len)`.

**Important attribution fix:** Ghidra merged `hunnox_command` (0x10e7a0–0x10f23f) with the following function `ablerex_command` (0x10f240+) into a single `FUN_0010e7a0`. The block with `libusb_control_transfer(0x21,9,0x305,…)` (SET_REPORT) / `(0xa1,1,0x305,…)` (GET_REPORT) and the strings `"R11 read"`/`"R2 read"`/`"R3 read"` (referenced at 0xf346–0xf5ef) belongs to **ablerex_command**, NOT to hunnox. The correct boundaries were obtained from the debuginfod symbol labels in objdump (see (b)).

---

## (b) Independent verification via objdump/strings (ground truth)

### b.1 Relevant strings (`strings -t x`)

```
  3b238 UPS No Ack
  3b24b S%lfR%d\r          (S command with R)
  3b254 S%lf\r             (plain S command)
  3b25a command index: 0x%02x
  3b274 asking for: %02X
  3b285 novendor          (NUT variable consulted in step 3)
  3d084 Hunnox 0.03
  3d1f5 hunnox
  3d243 MEC0003
  4bdb8 hunnox_command    (__func__)
```

### b.2 Subdriver dispatch table (`.data.rel.ro` 0x53740+, `{name → function}` pairs)

```
0x053770: fabula  -> 0xe140   (fabula_command)
0x053780: hunnox  -> 0xe7a0   (hunnox_command)   <====
0x0537c0: ablerex -> 0xf240   (ablerex_command)
```

### b.3 USB match table (`.data` 0x174e40+) and subdriver installation

The `qx_usb` table associates VID:PID and product strings with "claim" functions; the pointers to `"MEC"`/`"MEC0003"`/`"ATCL FOR UPS"` appear at 0x174e68–0x174ef0 next to the pairs `0483:0035` and `0925:1234`. The matching claim function (debuginfod symbol `fabula_hunnox_subdriver`, 0xab40) installs the hunnox handler in the global pointer:

```
000000000000ab40 <fabula_hunnox_subdriver>:
    ab44: lea 0x3c55(%rip),%rax        # e7a0 <hunnox_command>
    ab4b: mov %rax,0x16d13e(%rip)      # 177c90 <subdriver_command>
    ab52: xor %eax,%eax
    ab54: ret
```

That is: a device with USB product `"MEC0003"` (the table also accepts `"MEC"` and `"ATCL FOR UPS"`) ⇒ `subdriver_command = hunnox_command` ⇒ **every Megatec command goes through the string-descriptor tunnel**.

### b.4 `hunnox_command` (0xe7a0–0xf23f; boundaries from the debuginfod symbols)

Labels obtained from objdump (symbols downloaded via debuginfod by Build-ID, since the binary is stripped):
`000000000000e7a0 <hunnox_command>:` … `000000000000f240 <ablerex_command>:`. Also confirmed: `fabula_hunnox_subdriver` (0xab40), `hunnox_initups.lto_priv.0` (0x269e0, tail-call to `blazer_initups` with the `hunnox_qx2nut` table at 0x9d7c0) and `hunnox_battery_charge.lto_priv.0` (0x26a10, parses the `BL` answer, tests `'B'`/`'L'`).

#### b.4.1 Index↔command table built on the stack (0xe814–0xe869) + matching loop

```asm
e81b: movl $0x3,-0x4a8(%rbp)     ; Q1  -> 0x03   (string literal "Q1\r" at 0x3b20c, iteration 0 unrolled)
e825: movl $0xd,-0x498(%rbp)     ; F   -> 0x0d   (str 0x3c5f6 = "F\r")
e82f: movl $0xc,-0x488(%rbp)     ; I   -> 0x0c   (str 0x3c7fc = "I\r")
e839: movl $0x7,-0x478(%rbp)     ; Q   -> 0x07   (str 0x3cc12 = "Q\r")
e843: movl $0xa,-0x468(%rbp)     ; C   -> 0x0a   (str 0x3c9a0 = "C\r")
e854: movl $0xf3,-0x458(%rbp)    ; BL  -> 0xf3   (str 0x3b270 = "BL\r")
e85e: movq $0x0,-0x450(%rbp)     ; terminator {NULL, 0}
e869: movl $0x0,-0x448(%rbp)

e89e: lea 0x2c967(%rip),%rsi     # 3b20c ("Q1\r")
e8af: call strncmp@GLIBC         ; strncmp(cmd, table_entry, cmdlen)
e8b7: jne eb90                   ; no match -> advance 0x10 bytes and try the next one
eb90: addq $0x10,-0x4d0(%rbp)
eba3: mov (%rax),%rsi            ; load the string of the current entry
e8bd: shl $0x4,%r13              ; r13 = iteration number * 16
e8c1: mov -0x4a8(%rbp,%r13,1),%r13d ; USB index of the matched entry
```

The 16-byte structure is `{const char *cmd; int usb_index;}`. **Mapping verified byte by byte:** `Q1→0x03, F→0x0d, I→0x0c, Q→0x07, C→0x0a, BL→0xf3`.

`S` commands (outlet delay, format `"S%lfR%d\r"`/`"S%lf\r"`) do not use the table: the index is **computed** (0xebe2–0xec5c): value ≤ 0.5 → index `0x10`; value > 10 → `0xf0`; otherwise `index = (v−1)*16 + 96` for v ∈ [1,10] and `index = round((v−0.5)*10)*16 + 96` for v ∈ (0.5,1); the `R` suffix adds **+8** to the index.

#### b.4.2 langid 0x0409 and override

```asm
e8dc: mov 0x50b1d(%rip),%r15d    # 5f400 <langid_fix>   (initially -1 in .data)
e8e9: mov $0x409,%r14d           ; default langid 0x0409
e8f3: cmovne %r15d,%r14d         ; if langid_fix != -1, use langid_fix
```

When `langid_fix == -1` (default), reading the real command uses `libusb_get_string_descriptor_ascii` (which handles langid internally; libusb also falls back to 0x0409):

```asm
ed20: cmp $0xff,%r13d ; ja f202        ; validate index < 256
ed2d: movzbl %r13b,%esi                ; desc_index
ed34: mov %rbx,%rdx                    ; buffer
ed37: call libusb_get_string_descriptor_ascii
```

#### b.4.3 Real command transfer — wValue = 0x0300|index, wLength = min(len, 0x66), timeout 1000 ms

```asm
e98c: mov $0x66,%r14d                  ; 102
e99c: cmp %r14,%r12                    ; r12 = answer_len (4th argument)
e99f: cmovbe %r12,%r14                 ; wLength = min(answer_len, 102)
e9c5: movzwl %r14w,%eax                ; wLength (uint16)
e9c9: push $0x3e8                      ; timeout 1000 ms
e9ce: mov %rbx,%r9                     ; data = answer
e9d1: movzwl %r15w,%r8d                ; wIndex = langid (langid_fix)
e9d5: or $0x300,%r13w                  ; wValue = 0x0300 | index
e9db: push %rax                        ; wLength
e9dc: mov $0x6,%edx                    ; bRequest = 0x06 (GET_DESCRIPTOR)
e9e1: mov $0x80,%esi                   ; bmRequestType = 0x80 (IN, device)
e9e6: movzwl %r13w,%ecx                ; wValue
e9ea: call libusb_control_transfer
```

#### b.4.4 bLength validation and UTF-16LE→ASCII decoding (2-byte step)

```asm
e9f2: mov %eax,%r12d                   ; ret = bytes transferred
e9f5: test %r12d,%r12d ; jle ece0      ; error/libusb <0 -> log and return ret
ea0b: movsbl (%rbx),%ecx               ; answer[0] = descriptor bLength
ea0e: cmp %r12d,%ecx ; je ea98         ; bLength == ret -> decode
      (otherwise: log "size mismatch: %d / %d" at debug>=1 and return 0 without decoding)
ea98: cmp $0x2,%r12d ; jbe f1ac        ; <=2 bytes -> empty answer, return 0
eaa2: lea -0x1(%r14),%rdi              ; limit = 102-1 iterations
eaa6: lea 0x2(%rbx),%rax               ; skip header (bLength+bDescriptorType)
eab3: mov $0x3f,%ecx                   ; '?' (0x3F) default
eab8: cmpb $0x0,0x1(%rax)              ; HIGH byte of the UTF-16LE pair != 0 ?
eabc: jne eac1                         ;   yes -> keep '?'
eabe: movzbl (%rax),%ecx               ;   no -> take the low byte (ASCII)
eac1: add $0x2,%rax                    ; ADVANCE 2 BYTES AT A TIME
eac5: mov %cl,(%rsi)                   ; write "in place" (compaction)
eadf: (end) mov %edx,%r12d
eae2: movb $0x0,(%rsi)                 ; NUL terminator
```

#### b.4.5 "UPS No Ack" detection (0xeafd–0xeb2e)

```asm
eafd: lea 0x2d5a5(%rip),%rsi   # 3c0a9 ("\r")
eb07: call strcspn
eb0d: cmp $0xa,%rax ; jne ea28 ; strcspn(answer,"\r") == 10 ?
eb17: mov $0xa,%edx
eb1c: lea 0x2c715(%rip),%rsi   # 3b238 ("UPS No Ack")
eb26: call strncasecmp         ; compare 10 bytes, case-insensitive
eb2e: jne ea28                  ; different -> continue
eb34..eb83: zero the answer buffer (memset by size 0x40/0x20/0x10/8/4/2) and return 0
```

#### b.4.6 Warm-up state machine (`hunnox_step`, global in `.bss` 0x177c98; starts at 0)

Initial dispatch (0xe8e3–0xe911): `step 0 -> 0xee00`, `step 2 -> 0xedb8`, `step 1 -> 0xe913`, `step 3 -> 0xea50`.

**Step 0** (0xee0d–0xeebc) — initial warm-up, reads string 0 **twice** and string 1, with `wLength = 0x402` (1026) and timeout 1000 ms, then `usleep(10000)` (10 ms):

```asm
ee1a: push $0x3e8          ; timeout
ee31: push $0x402          ; wLength 1026
ee36: mov $0x300,%ecx      ; GET_DESCRIPTOR(STRING, index 0)  [langid]
ee45: call libusb_control_transfer
ee53: mov $0x300,%ecx      ; string 0 again
ee69: push $0x402
ee6e..eeaf: call libusb_control_transfer   ; wValue 0x301 (string 1 = iProduct)
eeb6: mov $0x2710,%edi     ; 10000 us
eebc: call usleep
```

**Step 1** (0xe913–0xe95f): if the current command is `F` (index 0x0d) it goes straight to the real transfer and sets `hunnox_step=2` (0xf038–0xf051); otherwise it does an extra warm-up:

```asm
e947: mov $0x30d,%ecx      ; GET string index 0x0D (F)
e94c: push $0x66           ; wLength 102
e937: push $0x3e8          ; timeout 1000 ms
e95f: call libusb_control_transfer
e967..e977: hunnox_step++ (from 1 to 2)
```

**Step 2** (0xedb8–0xedf3 + 0xf000): if the command is `Q1` (index 3): `hunnox_step=3` and transfer directly (0xf012); otherwise warm-up `wValue=0x303` (string Q1), `wLength=0x66`, then `step 2→3`:

```asm
edec: mov $0x303,%ecx ; edf1: push $0x66 ; (falls into the same call at e95f)
```

**Step 3** (0xea50–0xea5d, 0xef68–0xefef, 0xea63–0xea75): if the command is `I` (index 0x0c): `hunnox_step=1` and transfer directly; otherwise it looks up the **`novendor`** variable in `vartab_h` (strcasecmp at 0xef94) — if set, the warm-up is skipped; otherwise warm-up `wValue=0x30c` (string I), `wLength=0x66`, `step 3→4`, which is reset to 1 (`cmp $0x3; jle; movl $1,hunnox_step` at 0xe97d–0xe982).

```asm
efea: mov $0x30c,%ecx
efef: push $0x66
```

Practical effect: during normal operation (F/Q1/I polling by the Qx driver), each `hunnox_command` call in steps 1/2/3 issues **one extra string GET (F, Q1 or I) before the real command**, and when the request matches the step's "expected" one the warm-up is skipped — hence the F/Q1/I interleaving seen on the bus. The NUT variable `novendor` disables the step-3 warm-up.

### b.5 Interrupt endpoints in the generic qx_usb layer (outside hunnox)

```asm
bc91: mov $0x81,%esi        ; endpoint IN 0x81
bc96: call libusb_interrupt_transfer   ; with ecx=8 (8 bytes), r9=0x3e8 (1000 ms)
f946: mov $0x2,%esi         ; endpoint OUT 0x02 (example in fuji_command)
```

Several places (0xbc91, 0xc064, 0xc3d0, 0xc5e1, 0xc926, 0xcf8b, 0xd24e, 0xd8d9…) use endpoint `0x81` with length 8 and timeout 1000 ms — consistent with the 8-byte 0x81 IN / 0x02 OUT endpoints reported by USB observation (the real device's VID:PID 0001:0000 does **not** appear in the binary's match table, which lists 0483:0035 and 0925:1234 by product — hunnox selection happens through the iProduct "MEC0003"; the 0001:0000 identity belongs to the physical device, not to the driver).

---

## (c) Final VERIFIED protocol table

Every row below was confirmed by **two independent sources** (objdump disassembly + REA/Ghidra pseudocode), except where marked.

### c.1 Megatec command ↔ USB string index mapping

| ASCII command (Megatec) | String descriptor index (wValue = 0x0300\|idx) | Protocol function | Status |
|---|---|---|---|
| `Q1\r` | **0x03** | general status | **verified** (stack table + literal 0x3b20c) |
| `F\r` | **0x0d** | UPS ratings | **verified** (0x3c5f6) |
| `I\r` | **0x0c** | manufacturer info | **verified** (0x3c7fc) |
| `Q\r` | **0x07** | beeper on/off | **verified** (0x3cc12) |
| `C\r` | **0x0a** | cancel outlet shutdown/restart | **verified** (0x3c9a0) |
| `BL\r` | **0xf3** | battery level | **verified** (0x3b270) |
| `S<val>[R<n>]\r` | **0x10…0xf0 (computed)** | outlet delay; `+8` if `R` | **verified** (0xebe2–0xec5c) |

### c.2 Read transfer parameters

| Parameter | Value | Status |
|---|---|---|
| bmRequestType / bRequest | `0x80` / `0x06` (GET_DESCRIPTOR) | **verified** |
| Descriptor type | `0x03` (STRING), `wValue = 0x0300\|index` | **verified** |
| langid (wIndex) | `0x0409` default; overridden by the global `langid_fix` (init −1) | **verified** |
| wLength (real command) | `min(answer_len, 102)` — constant `0x66` | **verified** |
| Timeout | `1000 ms` (0x3e8) | **verified** |
| Alternate path | `langid_fix == −1` ⇒ `libusb_get_string_descriptor_ascii()` (ready-made ASCII, skips manual decoding) | **verified** |
| Validation | `answer[0]` (bLength) must equal bytes transferred; mismatch ⇒ "size mismatch" log and return 0 | **verified** |
| Decoding | UTF-16LE→ASCII "in place", step 2, header skipped (2 bytes), non-ASCII becomes `'?'` (0x3F), final NUL | **verified** |
| Invalid answer | `"UPS No Ack"` (10 bytes, strncasecmp) ⇒ buffer zeroed, return 0 | **verified** |

### c.3 Lock-step warm-up — `hunnox_step` (0..3, starts at 0, wraps 4→1)

| Step | Action before the real command | Status |
|---|---|---|
| 0 | GET string 0 (wLength **0x402**), GET string 0 again, GET string 1 (0x301), `usleep` 10 ms; step→1 | **verified** |
| 1 | If request ≠ F: GET string 0x0D (F) with wLength 0x66; step→2. If request = F: step→2 without warm-up | **verified** |
| 2 | If request ≠ Q1: GET string 0x03 (Q1) wLength 0x66; step→3. If request = Q1: step→3 without warm-up | **verified** |
| 3 | If request ≠ I: GET string 0x0C (I) wLength 0x66; step→4→1 (unless the NUT var `novendor` is set ⇒ skip warm-up). If request = I: step→1 without warm-up | **verified** |
| Resulting interleaving | while polling: extra F/Q1/I reads interleaved with the commands | **verified (static)** — dynamic bus behavior: **not verified** here (no USB capture in this analysis) |

### c.4 Subdriver selection

USB `iProduct` `"MEC0003"` (the table also accepts `"MEC"` and `"ATCL FOR UPS"`; VID:PIDs listed in the binary: `0483:0035`, `0925:1234`) ⇒ claim function `fabula_hunnox_subdriver()` (0xab40) ⇒ `subdriver_command = hunnox_command` (0xe7a0). **Verified.** Note: `hunnox_initups` reuses `blazer_initups` with the `hunnox_qx2nut` table — inherited from the Megatec/blazer mapping.

### c.5 Claims from the original context and their status in this analysis

| The context claimed | Status |
|---|---|
| Real chip VID:PID 0001:0000, low-speed, HID, 8-byte EP 0x81 IN / 0x02 OUT | endpoints/size **verified** in the generic qx layer (0x81/0x02, 8 bytes, 1000 ms); physical device VID:PID 0001:0000 **not verified in the binary** (the binary matches by iProduct; it does not contain 0001:0000) |
| Indices 0x03/0x0d/0x0c/0x07/0x0a/0xf3 | **verified** (identical table) |
| langid 0x0409 | **verified** (nuance: `langid_fix` override; without override, path via `libusb_get_string_descriptor_ascii`) |
| wLength cap 102 | **verified** (`min(answer_len, 0x66)`); step-0 warm-up uses 0x402, steps 1–3 use 0x66 |
| Warm-up reading strings 0/1 and interleaving F/Q1/I | **verified in detail** (full state machine) |

---

## (d) Limitations

1. **Stripped binary** — no `.symtab`; the function names in the objdump labels came from separate Arch **debuginfod** symbols (`.gnu_debuglink` → `nutdrv_qx.debug`, absent locally; downloaded by build-id at run time). Without debuginfod the addresses are still valid, but the names would not show.
2. **No rizin/radare2 on the host** and REA 6.8.0 **has no rizin provider**; no Ghidra installed at first. Mitigated by installing Ghidra 12.1.4 under `~/.local/opt` (user, no root). `inspect-binary-layout` stayed unavailable because it requires pwntools (Python 3.14 without the module; package install not attempted to avoid depending on root).
3. **Every REA command re-imports the binary into an ephemeral Ghidra project** (limitation stated by REA itself) — no persistent session between CLI calls.
4. **Imprecise function boundary in Ghidra**: `FUN_0010e7a0` merged `hunnox_command` + `ablerex_command`; the SET_REPORT/GET_REPORT blocks (0x21/9 and 0xa1/1, wValue 0x305) and the "R1x read" strings belong to `ablerex_command`. Fixed using the debuginfod symbols.
5. **`decompile-all`**: the first attempt (wide window 0x10ab40–0x10f240) ended with a **SIGKILL** of the Ghidra process (REA only reports the signal; likely memory, but not proven); the **second attempt**, with a narrow window (`--address-start 0x10e7a0 --address-end 0x10f240 --limit 4`), succeeded and wrote 2 `.c` files with an index and hashes (`ghidra-pseudocode/`).
6. **Static analysis only**: no USB capture and no driver execution were done here; dynamic effects (real MEC0003 answers, lock-step timing on the bus) remain **unverified** in this document.
7. `hunnox_battery_charge`/`hunnox_qx2nut` (`BL` parsing and variable mapping) were only located, not documented in depth (out of scope of the tunnel protocol).

## (e) Conclusion on the fidelity of the documented protocol

The prior protocol documentation (Megatec ASCII command tunnel inside string-descriptor GETs; indices 0x03=Q1, 0x0d=F, 0x0c=I, 0x07=Q, 0x0a=C, 0xf3=BL; langid 0x0409; wLength cap 102; warm-up reading strings 0/1 with F/Q1/I interleaving) is **faithful to the binary**, with three refinements found during verification:

1. langid 0x0409 applies directly to the **warm-ups**; for the real command, the default path is `libusb_get_string_descriptor_ascii` (0x0409 is only passed explicitly when `langid_fix` is configured);
2. the step-0 warm-up uses `wLength = 0x402` (1026), not 102;
3. there are also `S<value>[R<n>]` commands with a **dynamically computed index** (0x10…0xf8) and the NUT variable `novendor`, which suppresses the step-3 warm-up.

High confidence: every item marked "verified" has a double source (objdump bytes/instructions + Ghidra/REA pseudocode) and cited addresses.

---

## Artifacts

Directory `rea-evidence/`:

- `rea-analyze-nutdrv.json` — REA+Ghidra inventory (ev_4cd63432…)
- `rea-decompile-hunnox_command.json` — hunnox_command pseudocode (ev_c7eb9d0a…)
- `rea-function-hunnox_command.json.gz` / `.summary.json` — analyze_function dossier (ev_a87dd6b2…)
- `rea-decompile-all.json`, `ghidra-pseudocode/` — bulk export (ev_2d18634b…): `functions/0x10e7a0.c` (hunnox_command), `functions/0x10f240.c` (ablerex_command), `decompile-index.json`, `decompile-journal.jsonl`
- `rea-inspect-elf-notes.json`, `rea-inspect-native-exports.json`, `rea-inspect-byte-entropy.json` — target-free inspectors
- `objdump-hunnox_command-0xe7a0-0xf23f.txt` — full disassembly of the function
- `objdump-full-disasm.txt.gz` — full disassembly of the binary (with debuginfod labels)
- `strings-and-matchtable.txt` — relevant strings + USB match table (0483:0035 / 0925:1234 / "MEC0003"…)
- `subdriver-table.txt` — `{name → *_command}` dispatch table (`.data.rel.ro` 0x53740+)
