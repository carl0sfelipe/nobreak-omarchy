# Pós-lançamento — posts prontos para colar

Postagens prontas para o lançamento do `nobreak-mec0003`, cada uma no formato
da plataforma. Antes de publicar:

1. Troque `REPO_URL` pela URL final do repositório (ex.:
   `https://github.com/usuario/nobreak-mec0003`).
2. **Moldura honesta** (vale para todas as plataformas):
   - Não inventar benchmark, número de usuários ou "miles de nobreaks
     compatíveis" — a lista de marcas é "chip já encontrado em", não
     "testado e aprovado em".
   - Não prometer suporte a todos os modelos: o que existe é um chip
     (`0001:0000`), três transportes e muita coisa documentada.
   - O método (agentes de IA + REA + código aberto pré-existente) é real e
     pode ser dito com orgulho; "IA resolveu sozinha" não é verdade e não
     deve ser dito — a IA acelerou um diagnóstico humano.
3. A frase-resumo, use onde couber:
   > **"Meu nobreak fingia ser um teclado da Fry's Electronics e agora fala
   > Megatec por descritor de string."**

---

## 1) LinkedIn

Fui resolver um nobreak que não funcionava no Linux e terminei o dia com um
driver open-source completo.

O nobreak aparecia no `lsusb` como "Fry's Electronics MEC0003" (chip
genérico 0001:0000, usado por SMS, NHS, Powercool, Hunnox, DEXP, Eurocase…).
O driver padrão do NUT entrava em crash-loop, martelando o equipamento a
cada 2 segundos com o protocolo errado — o firmware USB, frágil, travava e o
dispositivo sumia e reaparecia na porta (3 reenumerações em 30 segundos no
dmesg).

A investigação passou por perícia em udev/journal, issues antigas do projeto
NUT, dois projetos brasileiros que decifraram o protocolo da SMS nos anos
2010 — e por agentes de IA, que extraíram o protocolo completo do
código-fonte aberto e confirmaram a tabela de índices dentro do binário do
driver do NUT usando o REA, uma ferramenta de engenharia reversa com agentes.
A descoberta central: esse chip transporta comandos Megatec ASCII dentro de
requisições de descritor de string USB — o índice da string é o opcode.

O resultado está no GitHub, licença MIT:

- Driver standalone em Python com 3 transportes (string UPSmart, túnel HID,
  serial binário SMS)
- Kit de configuração para o NUT (upsc/upsmon funcionando de verdade)
- Bridge MQTT com auto-discovery do Home Assistant
- Instalador com modo de diagnóstico e modo "destravar" o chip
- Referência completa do protocolo + evidências da engenharia reversa
- Testes e CI

Sem mentir nos números: foram horas de um dia, uma pessoa, muita leitura de
código de outras pessoas e IA como acelerador — não como mágica. Se o seu
nobreak é um "Fry's Electronics" do lsusb, teste e conte se funcionou.

REPO_URL

---

## 2) Reddit (r/linux, r/linuxhardware, r/homeassistant)

**Título sugerido (igual nos três):**

> Meu nobreak fingia ser um teclado da Fry's Electronics e agora fala
> Megatec por descritor de string — driver Linux open-source para o chip
> MEC0003 (0001:0000)

**Corpo:**

Meu nobreak (marca brasileira, chip USB genérico MEC0003, `0001:0000` —
aparece no `lsusb` como "Fry's Electronics", porque é assim que o usb.ids
registra esse vendor ID) não tinha suporte decente no Linux: o `nutdrv_qx`
do NUT entrava em crash-loop, mandando `Q1` pelo transporte errado a cada
2 s. O firmware é frágil: travava, e o dispositivo sumia e reaparecia na
porta USB — 3 reenumerações em 30 segundos no dmesg.

Passando por issues do NUT (#1539, #2208), a HCL e dois projetos
brasileiros antigos que decifraram o protocolo serial da SMS, e com agentes
de IA lendo o código-fonte do driver do NUT (e uma ferramenta de engenharia
reversa com agentes, o REA, confirmando a tabela dentro do binário), a
descoberta foi: esses chips falam Megatec ASCII **dentro de descritores de
string USB**. O índice da string é o opcode: `Q1`=0x03, `F`=0x0d, `I`=0x0c,
bateria=0xf3. Langid fixo 0x0409, wLength no máximo 102 (maior trava o
chip), uma sequência de "aquecimento" e leituras intercaladas ~1 Hz — é o
que o software Windows do fabricante (UPSmart, modo "MEGA(USB)") faz.

Com `subdriver=hunnox` + `protocol=q1` + `langid_fix` + `noscanlangid` no
`ups.conf` — e um ciclo "authorized" no sysfs para destravar o chip sem
replug físico — os valores acordaram dos zeros: 231 V na entrada, 219 V na
saída, carga 8 %, status OL.

Publiquei tudo (MIT): driver standalone Python com 3 transportes, kit NUT,
bridge MQTT com auto-discovery do Home Assistant (sem YAML!), instalador
com `--check` e `--unwedge`, referência completa do protocolo, evidências
da engenharia reversa, testes e CI:

REPO_URL

Curiosidades do firmware: reporta tensão da bateria **por célula** (2,22 V
× 6 = bateria de 12 V), mente a frequência (50,0 Hz fixo num país de 60 Hz),
carrega um report descriptor HID de 624 bytes que ninguém usa (isca), e tem
dois índices de string (0x68/0x69) que **desligam o nobreak** se você
enviar.

Se o seu `lsusb` mostra `0001:0000`, testa aí e me conta o modelo — a lista
de compatíveis cresce por issue/PR.

*(Para r/homeassistant: o gancho é o parágrafo do MQTT — sensor de tensão,
carga, bateria e temperatura aparecem sozinhos no HA via auto-discovery,
sem YAML.)*

---

## 3) Hacker News

**Título (77 chars):**

> Show HN: Linux driver for MEC0003 UPSes (Megatec over USB string descriptors)

**Primeiro comentário (postar logo em seguida, como autor):**

Details for the curious:

The MEC0003 (USB `0001:0000`, shows up in lsusb as "Fry's Electronics"
because of how usb.ids labels that vendor ID) is a generic UPS interface
chip found in units from SMS, NHS, Powercool, Hunnox, DEXP, Eurocase and
others. NUT's `nutdrv_qx` crash-looped on it: it kept sending Q1 over the
wrong transport every 2 s, and the fragile firmware would wedge — the
device re-enumerated 3 times in 30 seconds.

The transport it actually speaks: Megatec ASCII commands carried inside USB
string-descriptor requests. The string index IS the opcode — `Q1`=0x03,
`F`=0x0d, `I`=0x0c, battery=0xf3 — with a fixed langid `0x0409`, `wLength`
capped at 102 (larger wedges the chip), a mandatory warm-up sequence, and
interleaved F/Q1/I reads at ~1 Hz. This mirrors what the vendor's Windows
software (UPSmart, "MEGA(USB)" mode) does; NUT's `hunnox` subdriver
implements the same thing.

How it was figured out: udev/journal forensics, NUT issues #1539/#2208, the
NUT HCL, two Brazilian projects (smsUps, nobreakSMS) that had decoded the
older SMS binary serial protocol, then AI agents extracting the protocol
from open-source code, and REA (https://github.com/morluto/rea) inspecting
the `nutdrv_qx` binary to confirm the string-index table.

Fun firmware quirks: battery voltage is reported per-cell (2.22 V × 6 for a
12 V battery), input frequency is a hard-coded lie (fixed 50.0 Hz in a 60 Hz
country), the 624-byte HID report descriptor is a decoy nothing uses, and
string indices 0x68/0x69 will shut the UPS down.

Repo has a standalone Python driver (3 transports: UPSmart strings, HID
SET_REPORT tunnel, SMS binary serial), an NUT config kit, an MQTT/Home
Assistant bridge with auto-discovery, an installer with check/unwedge
modes, pytest and CI. MIT. Protocol reference included (in Portuguese):
docs/PROTOCOLO.md.

If lsusb shows `0001:0000` on your UPS, please test and report your model —
the compatibility list grows via issues/PRs.

---

## 4) X/Twitter (thread de 5 tweets)

**1/5**
Meu nobreak fingia ser um teclado da Fry's Electronics e agora fala Megatec
por descritor de string. História de um dia de diagnóstico que virou
driver open-source. 🧵

**2/5**
O nobreak aparecia no lsusb como `0001:0000 Fry's Electronics MEC0003`
(chip genérico de SMS, NHS, Hunnox, DEXP…). O driver do NUT crashava em
loop e travava o firmware: o dispositivo sumia/reaparecia 3× em 30 s.

**3/5**
A descoberta: comandos Megatec ASCII viajam DENTRO de descritores de string
USB — o índice da string é o opcode (Q1=0x03, F=0x0d, bateria=0xf3), langid
fixo, wLength ≤ 102 e warm-up. Igual ao UPSmart no Windows. Agentes de IA +
REA confirmaram a tabela no binário do driver.

**4/5**
Com a config certa (+ um "replug" por sysfs para destravar o chip), os
valores acordaram: 231 V entrada, carga 8%, status OL. O firmware ainda
mente a frequência (50 Hz fixo) e reporta bateria por célula (2,22 V ×6).

**5/5**
Tudo no GitHub, MIT: driver Python (3 transportes), kit NUT, bridge MQTT
com auto-discovery do Home Assistant, instalador com modo destravar,
referência do protocolo, testes e CI. Seu lsusb mostra 0001:0000? Testa e
conta o modelo!

REPO_URL

---

## Checklist pós-publicação

- [ ] Responder os primeiros comentários/issues rapidamente (o primeiro dia
      define o tom do projeto).
- [ ] Adicionar cada modelo confirmado à lista de compatibilidade do
      `README.md`/`README.en.md` (PR de 1 linha, sempre).
- [ ] Se aparecer relato de modelo com transporte diferente, pedir captura
      (`lsusb -v`, frame do Q1) e documentar em `docs/PROTOCOLO.md`.
- [ ] Não editar a história depois de publicada: se novos fatos surgirem,
      acrescente, não reescreva.
