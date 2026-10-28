# nobreak-mec0003

**Driver Linux completo para nobreaks com chip USB MEC0003 (`0001:0000`) — os "Fry's Electronics" do `lsusb`.**

[![CI](https://github.com/carl0sfelipe/nobreak-mec0003/actions/workflows/ci.yml/badge.svg)](https://github.com/carl0sfelipe/nobreak-mec0003/actions/workflows/ci.yml)
[![Licença: MIT](https://img.shields.io/badge/licen%C3%A7a-MIT-yellow.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)

Esse chip genérico está em nobreaks de dezenas de marcas no mundo inteiro
(SMS, NHS, Powercool, DEXP, Hunnox, Eurocase…), não tem suporte pronto no
Linux e faz o `nutdrv_qx` do NUT entrar em crash-loop. Este kit entrega:
driver NUT configurado, driver Python standalone, bridge MQTT para
Home Assistant, instalador com modo de destravamento e a referência
completa do protocolo.

---

## A história (como isso existe)

Em um dia — **2026-10-28** — um nobreak teimando em não funcionar:

1. O nobreak aparecia no `lsusb` como `0001:0000 Fry's Electronics MEC0003`
   e o `nutdrv_qx` do NUT entrava em **crash-loop**, martelando o
   dispositivo a cada 2 s com o protocolo e o transporte errados.
2. O firmware USB, frágil, **travava**: o dispositivo sumia e reaparecia
   o tempo todo (3 reenumerações em 30 s no `dmesg`).
3. Perícia em `udev`/`journalctl` → issues do NUT ([#1539][n1539],
   [#2208][n2208]), a HCL e os projetos brasileiros [smsUps][smsups] e
   [nobreakSMS][nobreaksms].
4. **Agentes de IA** extrairam o protocolo completo do código-fonte aberto
   existente; o [REA][rea] ("reverse engineer anything") inspecionou o
   binário `nutdrv_qx` e confirmou a tabela de índices de string do
   subdriver `hunnox` (evidência em [`docs/EVIDENCIA-REA.md`](docs/EVIDENCIA-REA.md)).
5. A descoberta: o chip carrega comandos **Megatec ASCII dentro de
   requisições de descritor de string USB** — o índice da string É o opcode
   (`Q1`=0x03, `F`=0x0d, `I`=0x0c, bateria=0xf3), com langid fixo `0x0409`,
   `wLength ≤ 102` e leituras intercaladas — o mesmo modo "MEGA(USB)" do
   software Windows UPSmart.
6. Correção aplicada ao vivo (`subdriver=hunnox` + `protocol=q1` +
   `langid_fix` + `noscanlangid`), chip travado revivido por "replug"
   via sysfs — e os valores acordaram dos zeros: **231,2 V na entrada,
   219,8 V na saída, carga 8 %, status OL**.

---

## Como saber se meu nobreak é compatível

```console
$ lsusb | grep 0001:0000
Bus 001 Device 005: ID 0001:0000 Fry's Electronics MEC0003
```

É isso: se aparecer `0001:0000` (o `lsusb` mostra "Fry's Electronics" porque
esse vendor ID genérico está registrado assim no usb.ids), seu nobreak usa o
chip MEC0003 e este projeto é para você. A nota acima sobre "Fry's
Electronics" é só uma curiosidade do banco de IDs — seu nobreak não veio de
nenhuma loja Fry's.

## Quickstart (30 segundos)

```console
$ git clone https://github.com/carl0sfelipe/nobreak-mec0003.git
$ cd nobreak-mec0003
$ bash install.sh --check      # diagnóstico: acha o nobreak, checa NUT e dependências
$ sudo bash install.sh         # instala o kit NUT (config + udev + serviços)
$ upsc nobreak@localhost
```

Se o seu `nutdrv_qx` já estava travando o dispositivo, o instalador detecta e
desbloqueia com um ciclo "authorized" no sysfs (replug por software). Saída
real após a instalação:

```console
$ upsc nobreak@localhost
battery.voltage: 2.22
input.voltage: 230.9
output.voltage: 219.8
ups.load: 8
ups.status: OL
ups.temperature: 27.0
```

(Captura completa: [`docs/capturas/2026-10-28-upsc-funcionando.txt`](docs/capturas/2026-10-28-upsc-funcionando.txt))

### Sem NUT: driver standalone

```console
$ python3 mec0003.py --watch    # uma leitura por segundo, reabre sozinho após travamento
$ python3 mec0003.py --json     # para scripts
$ python3 mec0003.py --info     # fabricante / modelo / firmware
$ python3 mec0003.py --battery  # carga da bateria em %
$ python3 mec0003.py --ratings  # valores nominais (F)
```

Três transportes, se um não pegar no seu modelo:
`--method string` (padrão, modo UPSmart), `--method setreport`
(túnel HID clássico) e `--method serial` (protocolo binário SMS,
2400 baud 8N1, para os modelos de cabo serial).

### Home Assistant / MQTT

```console
$ sudo bash install.sh --mqtt   # instala e habilita o serviço da bridge
$ systemctl status nobreak-mec0003-mqtt
```

A bridge publica os valores em MQTT com **auto-discovery** do Home
Assistant: sensores de tensão, carga, bateria, temperatura e status aparecem
sozinhos, sem YAML.

## O que você ganha

| Dado | Variável NUT | Exemplo real |
|---|---|---|
| Tensão de entrada | `input.voltage` | 230,9 V |
| Tensão de saída | `output.voltage` | 219,8 V |
| Carga (consumo) | `ups.load` | 8 % |
| Tensão da bateria | `battery.voltage` | 2,22 V/célula (ver abaixo) |
| Carga da bateria | `battery.charge` | 100 % |
| Temperatura | `ups.temperature` | 27,0 °C |
| Status | `ups.status` | `OL` (rede OK) / `OB` (na bateria) / `LB` (bateria baixa) |
| Autonomia estimada | `battery.runtime` | via `runtimecal` no `ups.conf` |

Com `upsmon` configurado, você ganha desligamento limpo do servidor quando
faltar energia — que é o motivo de existir de um nobreak.

## Solução de problemas

| Sintoma | Causa | Soluções |
|---|---|---|
| Todos os valores zerados | Falta a sequência de "aquecimento" (o firmware devolve zeros até alguém replicar o handshake do UPSmart) | Rode o driver/instalador por completo (ele faz o warm-up); se persistir, faça replug físico |
| Dispositivo some e reaparece no `lsusb` | Firmware travado (crash-loop de driver antigo) | `bash install.sh --unwedge` (ciclo "authorized" via sysfs) ou replug físico; depois use a config do kit |
| `Input/Output Error` no NUT | Varredura de langid ou transporte errado | `ups.conf` do kit: `subdriver=hunnox`, `protocol=q1`, `langid_fix=0x0409`, `noscanlangid` |
| Frequência sempre 50,0 Hz (num país 60 Hz) | O firmware **mente** — reporta 50,0 fixo | Ignore o valor; é um defeito conhecido do firmware, não do driver |
| `battery.voltage: 2.22` parece errado | O firmware reporta tensão **por célula** (2,22 V = float de chumbo-ácido por célula) | Bateria de 12 V = 6 células: `battery.packs = 6` no `ups.conf` (o driver multiplica) |
| NUT volta a travar depois de um tempo | Config antiga sem `subdriver=hunnox` — o transporte errado derruba o firmware | Use a config do kit: com hunnox, `pollinterval = 2` é seguro e mantém os valores acordados (~1 Hz, como o UPSmart) |

**Importante:** nunca envie os índices de string `0x68`/`0x69` para o chip —
eles **desligam o nobreak**. O driver e a config do kit nunca os usam.

## Como funciona

1. O software (driver Python ou NUT `nutdrv_qx`/hunnox) abre o dispositivo
   `0001:0000` via libusb (regra udev dá acesso sem root).
2. Em vez de HID normal, manda o comando Megatec **como um
   `GET_DESCRIPTOR` de string**: o índice da string é o opcode.
3. O chip MEC0003 responde o descritor em UTF-16LE; convertemos para ASCII.
4. Uma sequência de aquecimento + leituras intercaladas F/Q1/I mantém o
   firmware "acordado" (é o que o UPSmart faz).
5. O parsing Megatec vira variáveis NUT / JSON / MQTT — e o `upsmon`,
   Home Assistant etc. passam a enxergar o nobreak.

```
+------------------+   GET_DESCRIPTOR(STRING), índice = opcode   +-----------+
| mec0003.py  ou   |   Q1 -> 0x03 | F -> 0x0d | I -> 0x0c        |  MEC0003  |
| NUT nutdrv_qx    | ------------------------------------------->|  (USB)    |
| (subdrv hunnox)  |<--------------------------------------------|           |
+------------------+    resposta UTF-16LE -> ASCII (Megatec)     +-----+-----+
      |                                                            |
      v                                                            v
upsc / upsmon / MQTT / Home Assistant                    firmware Megatec (Q1/F/I)
```

A referência completa (bytes, checksums, os dois protocolos, os perigos)
está em [`docs/PROTOCOLO.md`](docs/PROTOCOLO.md). O report descriptor HID de
624 bytes do chip é uma isca: nenhum software usa os usages dele.

## Compatibilidade

Chip `0001:0000` / produto "MEC0003". Marcas onde o chip já foi encontrado:

SMS · NHS · Powercool · DEXP · Hunnox · Eurocase · CPC

**Funcionou com o seu modelo?** Abra uma issue (ou PR editando esta lista)
adicionando marca/modelo — é assim que a lista cresce. Os modelos de cabo
serial da SMS (chip Cypress `04b4:5500`) também são suportados via
`--method serial`.

## Créditos

Este projeto é uma camada de conveniência em cima de muita gente que
quebrou esse protocolo antes:

- [NUT — Network UPS Tools](https://networkupstools.org/) e os subdrivers
  `hunnox`/`krauler` do `nutdrv_qx`; issues [#1539][n1539], [#2208][n2208] e
  [#1326][n1326] documentaram o comportamento do chip.
- [dmslabsbr/smsUps][smsups] e [petersenna/nobreakSMS][nobreaksms] —
  projetos brasileiros que decifraram o protocolo binário serial da SMS.
- **UPSmart** (software Windows do fabricante) — referência de engenharia
  reversa: o modo "MEGA(USB)" dele é o transporte que este driver replica.
- [REA — Reverse Engineer Anything][rea] — usado para inspecionar o binário
  `nutdrv_qx` e confirmar a tabela de índices (ver
  [`docs/EVIDENCIA-REA.md`](docs/EVIDENCIA-REA.md)).

[n1539]: https://github.com/networkupstools/nut/issues/1539
[n2208]: https://github.com/networkupstools/nut/issues/2208
[n1326]: https://github.com/networkupstools/nut/issues/1326
[smsups]: https://github.com/dmslabsbr/smsUps
[nobreaksms]: https://github.com/petersenna/nobreakSMS
[rea]: https://github.com/morluto/rea

## Licença

[MIT](LICENSE) — feito com agentes de IA (ZCode + [REA][rea]) em um dia de
diagnóstico. A história completa, em formato de post, está em
[`docs/POST-LANCAMENTO.md`](docs/POST-LANCAMENTO.md).
