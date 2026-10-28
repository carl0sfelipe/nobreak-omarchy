# Launch notes — nobreak-omarchy

Where and how to announce the project. Repository (not created yet):
`https://github.com/carl0sfelipe/nobreak-omarchy`.

## Honest framing (applies everywhere)

- Do not invent benchmarks, user counts or "thousands of compatible UPSes".
  The brand list for MEC0003 is "chip found in", not "tested and approved on".
- One driver is tested today (MEC0003, live on 2026-10-28: on mains, on
  battery, autoheal recovering a wedged chip). Everything else is an
  invitation to contribute.
- The method (AI agents + REA + pre-existing open source) is real and can be
  said with pride; "AI solved it alone" is not true — AI accelerated a human
  diagnosis.
- One-liner, where it fits:
  > **"My UPS pretended to be a Fry's Electronics keyboard; now it speaks
  > Megatec through USB string descriptors — and my Hyprland desktop tells me
  > when the power goes out."**

## Upstream first (most useful, least noisy)

1. **NUT HCL submission** — submit the MEC0003 entry to the NUT Hardware
   Compatibility List (`nutdrv_qx`, `subdriver=hunnox`, `protocol=q1`,
   `langid_fix=0x0409`, `noscanlangid`, per-cell battery packs, `ignorelb`),
   linking `drivers/mec0003/nut/ups.conf` and the captures.
2. **Comment on NUT issues [#1539](https://github.com/networkupstools/nut/issues/1539)
   and [#2208](https://github.com/networkupstools/nut/issues/2208)** — short,
   factual: the working config, the zeros-until-warm-up behavior, the
   wedge-on-concurrent-access finding, the voltage-based charge drop on
   battery, and a link to the evidence. No marketing.

## Communities

| Where | Angle |
|---|---|
| **r/omarchy** | "UPS notifications + autoheal for Omarchy" — screenshots of the mako notification, `install.sh --check` output |
| **r/archlinux** | the NUT config and the reverse-engineering story; AUR packaging is a future step |
| **r/homelab** | MQTT/Home Assistant bridge, autoheal, `upsmon` clean shutdown for cheap UPSes |
| **Home Assistant forum** (Community → Share your Projects) | MQTT auto-discovery sensors, no YAML |
| **Clube do Hardware** (Brazil, Portuguese) | SMS/NHS owners: "seu nobreak aparece como Fry's Electronics no lsusb? funciona no Linux" — link `README.pt-BR.md` |

## Post template (adapt per platform)

**Title:** nobreak-omarchy — community UPS kit for Omarchy/Arch: desktop
notifications on power loss, USB autoheal, proven NUT configs (first
driver: the MEC0003 "Fry's Electronics" chip)

**Body:**

My UPS (generic MEC0003 chip, `0001:0000`, shows up as "Fry's Electronics"
in `lsusb`) made NUT's `nutdrv_qx` crash-loop and wedged its own USB
firmware. After a day of forensics — NUT issues #1539/#2208, two old
Brazilian SMS projects, AI agents and REA reverse-engineering the
`nutdrv_qx` binary — it turned out the chip tunnels Megatec commands inside
USB string-descriptor requests (the string index is the opcode).

That fix grew into a small kit:

- a power guardian that sends desktop notifications on outage / restore /
  low battery and logs events as JSON lines;
- a USB autoheal timer that replugs the device by software when NUT loses
  it (usbreset → sysfs authorized → xHCI rebind);
- proven NUT configs per driver, an installer with `--check`, `--dry-run`
  and `--unwedge`;
- an MQTT bridge with Home Assistant auto-discovery.

MEC0003 is the first driver. If your UPS needs special NUT options, a driver
is just a directory with a `driver.toml` and an `ups.conf` — PRs welcome.

REPO_URL

## After publishing

- [ ] Replace `REPO_URL` everywhere.
- [ ] Pin an issue "Add your UPS" pointing at CONTRIBUTING.md.
- [ ] Label `new-driver` and `model-report` issues.
- [ ] Answer every model report within a few days — that is how the driver
      table grows.
