# Referência do protocolo — Nobreaks SMS/NHS/genéricos com chip MEC0003 (0001:0000)

> Documento extraído por análise de código dos projetos dmslabsbr/smsUps e
> petersenna/nobreakSMS, dos subdrivers do NUT (blazer_usb.c, nutdrv_qx.c,
> nutdrv_qx_megatec.c, nutdrv_qx_hunnox.c) e das issues NUT #1326, #2208 e #307.

## 0. Visão geral: existem DUAS pilhas de hardware/protocolo

| Pilha | Chip USB | USB IDs | Protocolo | Implementado por |
|---|---|---|---|---|
| A | Cypress CY7C63xxx "HID→COM RS232" (cabo do SMS Manager III Senoidal) | `04b4:5500` | SMS **binário**: pacotes de 7 bytes a 2400 baud 8N1 tunelados em HID | driver de kernel `cypress_m8` → `/dev/ttyUSB0`; smsUps + nobreakSMS |
| B | Chip genérico "Fry's Electronics" MEC0003 (SMS, NHS, Powercool, CPC, DEXP, Hunnox, Eurocase…) | `0001:0000`, produto "MEC0003", iManufacturer=0, iSerial=0 | **Megatec ASCII** (`Q1\r`, `F\r`, `I\r`, `S\r`…) em reports HID SET_REPORT **ou** dentro de GET_DESCRIPTOR de string (modo "MEGA(USB)" do UPSmart) | NUT `nutdrv_qx` subdriver `hunnox`/`krauler`; `mec0003.py` deste diretório |

## 1. Pilha A — protocolo binário serial SMS (smsUps/nobreakSMS)

### 1.1 Transporte

Serial 2400 baud, 8N1, raw. Comando do host = **7 bytes**; resposta do nobreak
= **18 bytes**, primeiro byte marcador (`=`/`:`/`;` conforme o comando), último
byte `0x0D`.

### 1.2 Enquadramento e checksum

Pacote do host = `[letra ASCII][4 bytes de args][checksum][0x0D]`, onde
`checksum = (0x100 - (soma(bytes[0..4]) & 0xFF)) & 0xFF`. Args não usados:
`0xFF` (comandos sem parâmetro) ou `0x00`. Os bytes podem ser escritos um a um
com 100 ms entre eles (mais conservador).

### 1.3 Comandos

| Query | Bytes | Significado | Resposta observada |
|---|---|---|---|
| Q | `51 ff ff ff ff b3 0d` | status | 18 bytes (§1.4) |
| I | `49 ff ff ff ff bb 0d` | nome + firmware | `:SENOIDAL    7.0b\r` / `:M3 SENOIDAL 2.0\r` |
| F | `46 ff ff ff ff be 0d` | características | `;EBiS115000 2460o` |
| D | `44 ff ff ff ff c0 0d` | aborta teste de bateria | — |
| G | `47 01 ff ff ff bb 0d` | inicialização (opcional) | — |
| M | `4d ff ff ff ff b7 0d` | alterna o buzzer | — |
| T | `54 hh ll 00 00 ck 0d` | teste de bateria n s (n = arg BE) | — |
| C | `43 ff ff ff ff c1 0d` | cancela desligamento/restauração | — |
| L | `4c ff ff ff ff …` | teste até bateria baixa | — |
| R | `52 00 C8 27 0F B0 0D` | desliga + restaura | — |

### 1.4 Resposta do `Q` (18 bytes)

| Offset | Tam | Campo | Codificação | Exemplo → valor |
|---|---|---|---|---|
| 0 | 1 | marcador | `=` 0x3D | — |
| 1–2 | 2 | última tensão de entrada | u16 BE ÷10 → V | `08 34` → 210,0 V |
| 3–4 | 2 | tensão de entrada | u16 BE ÷10 → V | — |
| 5–6 | 2 | tensão de saída | u16 BE ÷10 → V | `04 38` → 108,0 V |
| 7–8 | 2 | potência de saída | u16 BE ÷10 → % | `01 22` → 29,0 % |
| 9–10 | 2 | frequência de saída | u16 BE ÷10 → Hz | `02 58` → 60,0 Hz |
| 11–12 | 2 | nível da bateria | u16 BE ÷10 → % | `03 e8` → 100 % |
| 13–14 | 2 | temperatura | u16 BE ÷10 → °C | `01 7c` → 38,0 °C |
| 15 | 1 | bits de estado | §1.5 | — |
| 16 | 1 | desconhecido (0x01) | — | — |
| 17 | 1 | terminador | 0x0D | — |

Faixas de sanidade: V ∈ [0,270], % ∈ [0,100], Hz ∈ [40,70], °C ∈ [−20,70].

### 1.5 Bits de estado (offset 15)

| Bit | Significado |
|---|---|
| 0 | Beep ligado |
| 1 | Shutdown ativo |
| 2 | Teste ativo |
| 3 | UPS OK (saída energizada) |
| 4 | Boost |
| 5 | ByPass |
| 6 | Bateria baixa |
| 7 | Em bateria |

Valores reais observados: `0x09` normal; `0x89` fora da tomada;
`0x8d`/`0x8c` teste de bateria com/sem beep.

## 2. Pilha B — transporte USB HID do MEC0003 (o chip deste nobreak)

### 2.1 Descritores reais

`0001:0000`, bcdDevice 1.00, 1 interface classe 3 (HID), 2 endpoints
interrupção de 8 bytes: `EP 0x81 IN` e `EP 0x02 OUT`, bInterval 10.
bcdHID 1.11, report descriptor de 624 bytes (frequentemente ilegível —
e irrelevante: os usages estruturados não são usados por software nenhum).

### 2.2 Método A — túnel HID SET_REPORT

O stream ASCII Megatec é fatiado em reports de saída de 8 bytes (report ID
0x00) enviados como **transferência de controle** SET_REPORT
(`0x21/0x09/wValue=0x0200`), resposta no **EP 0x81** em blocos de 8 bytes até
aparecer `\r`. Sem header/CRC — o payload é o próprio stream serial
(comando + `\r`, completado com zeros).

### 2.3 Método B — modo "MEGA(USB)" do UPSmart (o que o NUT hunnox usa)

Comandos viajam como **GET_DESCRIPTOR(STRING)**; o **índice da string é o
opcode**:

| Comando | Índice | Resposta |
|---|---|---|
| `Q1\r` (status) | `0x03` | `(MMM.M NNN.N OOO.O PPP QQ.Q RR.R SS.S bbbbbbbb` (47 bytes) |
| `F\r` (nominal) | `0x0d` | `#220.0 000 024.0 50.0` |
| `I\r` (infos) | `0x0c` | `#fabr  modelo  firmware` |
| `Q\r` (bip) | `0x07` | — |
| `C\r` (cancela) | `0x0a` | — |
| `T\r` (teste) | `0x04` | — |
| `TL\r` (teste até baixa) | `0x05` | — |
| `BL\r` (carga %) | `0xf3` | `BLnn` |
| ⚠ perigosos | `0x68`/`0x69` | **causam desligamento** — nunca usar |

Detalhes críticos:
- langid **fixo** `0x0409` (a negociação padrão trava o firmware);
- `wLength ≤ 102` (0x66) — valor medido do cliente Windows; maior trava o USB;
- resposta = descritor UNICODE_STRING (len + 0x03 + UTF-16LE) → converter
  para ASCII pegando 1 byte a cada 2 a partir do offset 2;
- validar: tamanho retornado == primeiro byte do descritor;
- `"UPS No Ack"` (10 chars) = comando aceito sem retorno.

### 2.4 Sequência de inicialização obrigatória

Até o cliente do fabricante rodar uma vez após o plug, o dispositivo responde
**tudo zeros** (NUT #2208). O hunnox replica o padrão do UPSmart: no início,
ler string 0 (lista de langids, wLength 1026) duas vezes + string 1, pausa de
10 ms; e **intercalar leituras dummy de F/Q1/I** entre polls reais (o UPSmart
faz ~1 poll/s e as leituras acompanhantes mantêm os valores vivos).

### 2.5 Desligamento via índice de string (hunnox/fabula)

```
delay ∈ [0.5 .. 10] min:
  < 1 min : índice = 16 + round((delay − 0.5) × 10) × 16
  ≥ 1 min : índice = 96 + (delay − 1) × 16
  + 8 se quiser religar depois (restart fixo em 10 s)
ex.: 0x10 = stayoff 30 s · 0x18 = desliga e religa em 30 s · 0xF8 = 10 min religando
```

### 2.6 Payloads ASCII Megatec

```
> Q1\r
< (226.0 195.0 226.0 014 49.0 27.5 30.0 00001000\r
  │1-5 entrada V · 7-11 falta V · 13-17 saída V · 19-21 carga % ·
  23-26 Hz · 28-31 V bateria · 33-36 temp °C · 38-45 flags (cada char 0/1:
  falha_rede, bateria_baixa, bypass/boost, ups_defeituoso, tipo, teste,
  shutdown, bip)
```

## 3. Checklist de peculiaridades

1. Sem a sequência de aquecimento (§2.4) → valores zerados; replug reseta.
2. `wLength` grande trava o chip; usar sempre ≤ 102 no canal de comandos.
3. Não usar `usb_get_string_simple` (varredura de langid) — langid fixo.
4. `usbhid` do kernel estrapola o dispositivo; dar detach antes de usar libusb.
5. Firmware frágil: manter poll ≥ 15 s no NUT; após travamento, ele reenumera
   (o driver precisa reabrir).
6. O report descriptor de 624 bytes (report IDs 1–5, Power Device Page) é
   "isca": nenhum software usa os usages estruturados.
7. Para uso serial do MEC0003: `modprobe usbserial vendor=0x0001 product=0x0000`
   (após desanexar usbhid); low-speed limita a ~4800 baud.

## Fontes

- [dmslabsbr/smsUps](https://github.com/dmslabsbr/smsUps) — smsUPS.py, tst.txt, DOCS.md
- [petersenna/nobreakSMS](https://github.com/petersenna/nobreakSMS) — userland/nobreakSMS.c
- [NUT nutdrv_qx.c](https://github.com/networkupstools/nut/blob/master/drivers/nutdrv_qx.c) · [blazer_usb.c](https://github.com/networkupstools/nut/blob/master/drivers/blazer_usb.c) · [nutdrv_qx_megatec.c](https://github.com/networkupstools/nut/blob/master/drivers/nutdrv_qx_megatec.c)
- Issues NUT: [#1326](https://github.com/networkupstools/nut/issues/1326) · [#2208](https://github.com/networkupstools/nut/issues/2208) · [#307](https://github.com/networkupstools/nut/issues/307) · [#1539](https://github.com/networkupstools/nut/issues/1539)
- [NUT HCL](https://networkupstools.org/stable-hcl.html)
- [cypress_m8 (kernel Linux)](https://github.com/torvalds/linux/blob/master/drivers/usb/serial/cypress_m8.c)
- [Thread nut-upsdev 2014 (lsusb do cabo Manager III)](https://alioth-lists.debian.net/pipermail/nut-upsdev/2014-February/006657.html)
