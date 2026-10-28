# nobreak-omarchy

**Kit comunitário de suporte a nobreaks (UPS) para o [Omarchy](https://omarchy.org) — Arch Linux + Hyprland — e outros desktops com systemd. Drivers plugáveis: o MEC0003 é o primeiro driver; o seu pode ser o próximo.**

[![CI](https://github.com/carl0sfelipe/nobreak-omarchy/actions/workflows/ci.yml/badge.svg)](https://github.com/carl0sfelipe/nobreak-omarchy/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-yellow.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)

[English](README.md)

Nobreak barato está em todo lugar, e muitos mal funcionam no Linux: chips
USB estranhos, firmware que trava, configuração de NUT que ninguém
documentou. O nobreak-omarchy empacota o que é preciso para um nobreak ser
*útil de verdade* num desktop Linux — e facilita a comunidade adicionar o
próximo modelo.

## O que o núcleo oferece

| Peça | O que faz |
|---|---|
| **Guardião de energia** (`core/guardian`) | Serviço de usuário que vigia o nobreak pelo NUT e manda **notificações no desktop** (mako/Hyprland, GNOME, KDE) quando falta luz, quando a energia volta e com bateria baixa. Registra cada evento em JSON (uma linha por evento) em `~/.local/state/nobreak-omarchy/events.jsonl`. Ganchos opcionais: `--on-cmd 'systemctl suspend'`. |
| **Autocura USB** (`core/autoheal`) | Timer de sistema (a cada 2 min). Se o NUT perder o nobreak em 2 checagens seguidas, "tira e bota" o USB *por software*, em escada: `usbreset` → ciclo authorized no sysfs → rebind da controladora xHCI. No máximo 4 curas por hora. |
| **Configuração do NUT** | Cada driver traz uma seção `ups.conf` comprovada; o instalador a grava de forma idempotente (com backup) e valida com `upsc`. Funciona com o `upsmon` para desligamento limpo. |
| **Ponte MQTT / Home Assistant** | Drivers com daemon próprio podem publicar no MQTT com auto-discovery do Home Assistant. |
| **Instalador** | `install.sh --check` (diagnóstico, sem root), `--driver <nome>`, `--unwedge`, `--dry-run`; `uninstall.sh` para desfazer. |

## Drivers suportados

| Driver | ID USB | Marcas | Driver NUT | Autocura | Status |
|---|---|---|---|---|---|
| [`mec0003`](drivers/mec0003/) | `0001:0000` ("Fry's Electronics MEC0003") | SMS, NHS, Powercool, DEXP, Hunnox, Eurocase, CPC | `nutdrv_qx` (hunnox) | sim | testado ao vivo em 2026-10-28: telemetria em bateria verificada, autocura verificada |
| *o seu?* | | | | | veja [Adicione seu nobreak](#adicione-seu-nobreak) |

Confira o seu: rode `lsusb` e procure o ID USB.

## Início rápido

```console
$ git clone https://github.com/carl0sfelipe/nobreak-omarchy.git
$ cd nobreak-omarchy
$ bash install.sh --check                    # diagnóstico: acha o nobreak, checa NUT e dependências
$ sudo bash install.sh --driver mec0003      # config NUT + udev + autocura + guardião
$ upsc nobreak@localhost
$ python3 core/guardian/guardian.py --dry-run   # veja as notificações
```

Requisitos: `nut`, `python3`, `libnotify` (`notify-send`), systemd.
No Omarchy/Arch: `sudo pacman -S nut libnotify`.

Opções úteis: `--battery 12|24`, `--name <ups>`, `--mode nut|standalone|mqtt`,
`--no-guardian`, `--no-autoheal`, `--list-drivers`, `--dry-run`.

### O guardião

```console
$ systemctl --user status nobreak-guardian
$ tail -f ~/.local/state/nobreak-omarchy/events.jsonl
{"ts": "...", "event": "power_outage", "ups_status": "OB", "input_v": 0.0, ...}
```

Eventos: `monitoring_started`, `power_outage`, `power_restored`,
`battery_low`, `status_change`, `ups_not_responding`. As notificações agora
são em inglês.

CLI: `guardian.py [--ups nobreak@localhost] [--interval 5] [--once] [--dry-run] [--on-cmd CMD] [--restore-cmd CMD]`.

> **Migrando do nobreak-mec0003:** o guardião gravava em
> `~/.local/state/nobreak-mec0003/eventos.jsonl` com nomes de evento em
> português (`falta_de_luz`, `energia_volvou`, `bateria_baixa`,
> `inicio_monitoramento`…). Agora grava em
> `~/.local/state/nobreak-omarchy/events.jsonl`, com nomes em inglês e a
> chave `event` no lugar de `evento`. O arquivo antigo não é mexido — guarde
> como histórico ou mova. A unit agora é `nobreak-guardian.service` (era
> `nobreak-guardiao.service`) e a autocura é `nobreak-autoheal` (era
> `nobreak-autocura`); as opções antigas `--intervalo`, `--forcar` e
> `--nivel` continuam aceitas.

### Autocura

```console
$ systemctl list-timers nobreak-autoheal.timer
$ journalctl -t nobreak-autoheal
$ sudo nobreak-autoheal --force          # cura agora
```

Configurada por `/etc/nobreak-omarchy/autoheal.env` (gravado pelo
instalador): `NOBREAK_VIDPID` (padrão `0001:0000`), `NOBREAK_UPS` (padrão
`nobreak@localhost`), `NOBREAK_NUT_UNIT` (padrão `nut-driver@<ups>.service`).
"Saudável" = o `upsc` responde e a tensão de entrada ou de saída é maior que 0.

## Estrutura do repositório

```
core/guardian/     guardião de energia (serviço de usuário, notificações)
core/autoheal/     script de autocura USB + timer systemd
drivers/<nome>/    um diretório por nobreak: driver.toml, nut/ups.conf, udev/, README, testes
drivers/_template/ esqueleto para um driver novo
install.sh         instalador (--driver, --check, --unwedge, --dry-run)
uninstall.sh       desinstalador
tests/             testes do núcleo
```

## Adicione seu nobreak

Tem um nobreak que não está na tabela? Você pode adicioná-lo — não precisa
de Python se o NUT já conversa com ele usando as opções certas:

1. `cp -r drivers/_template drivers/<nome>` e preencha o `driver.toml`.
2. Coloque a seção do NUT que funciona em `drivers/<nome>/nut/ups.conf`.
3. Capture as evidências: `lsusb -v` e `upsc` **na tomada e na bateria**.
4. Abra um PR.

Guia completo (em inglês): [CONTRIBUTING.md](CONTRIBUTING.md). Issues e PRs
em português são bem-vindos.

## A história do MEC0003

O projeto começou com um nobreak teimoso: um chip genérico MEC0003 que
deixava o NUT em crash-loop e travava o próprio firmware USB. Um dia de
perícia, issues do NUT, projetos brasileiros antigos da SMS, agentes de IA e
o [REA](https://github.com/morluto/rea) (engenharia reversa do binário
`nutdrv_qx`) acharam o truque: comandos Megatec tunelados em descritores de
string USB. A história completa, as peculiaridades e o protocolo estão em
[`drivers/mec0003/`](drivers/mec0003/README.md) (em inglês).

## Licença

[MIT](LICENSE). Notas de lançamento: [`docs/LAUNCH.md`](docs/LAUNCH.md).
