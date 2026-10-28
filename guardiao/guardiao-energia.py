#!/usr/bin/env python3
"""
guardiao-energia.py — vigia o nobreak via NUT (upsc) e reage a eventos de energia.

O que faz:
  * polla `upsc <ups>@localhost` a cada N segundos (padrão 5)
  * detecta transições: falta de luz (OL→OB), retorno (OB→OL), bateria baixa (LB)
  * registra cada evento como 1 linha JSON em ~/.local/state/nobreak-mec0003/eventos.jsonl
    (mesma filosofia da telemetria: 1 linha por evento, post-mortem friendly)
  * notifica no desktop (notify-send — Hyprland/GNOME/KDE)
  * opcional: executa um comando em eventos (--on-cmd / --restore-cmd)

Não precisa de root: upsc é cliente TCP do upsd (localhost:3493).
Rode como serviço de usuário (systemd --user), veja nobreak-guardiao.service.

Uso:
  python3 guardiao-energia.py                    # vigia 'nobreak@localhost' a cada 5s
  python3 guardiao-energia.py --ups outro@localhost --intervalo 10
  python3 guardiao-energia.py --once             # uma leitura só (teste)
  python3 guardiao-energia.py --dry-run          # simula eventos p/ testar notificações
  python3 guardiao-energia.py --on-cmd 'systemctl suspend'   # ação na falta de luz

Integração com o workflow hq (opcional): aponte --on-cmd para um script que
abra um registro de incidente com a skill `incident` e/ou anexe em
telemetria — este script só produz o evento, não escreve em diretórios que
não sejam dele.
"""

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

STATE_DIR = Path(os.environ.get("MEC0003_STATE_DIR",
                                Path.home() / ".local/state/nobreak-mec0003"))
EVENTS_FILE = STATE_DIR / "eventos.jsonl"

# eventos que disparam notificação crítica
CRITICOS = {"falta_de_luz", "bateria_baixa"}


def agora():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def notificar(titulo, mensagem, critico=False):
    cmd = ["notify-send", "-u", "critical" if critico else "normal",
           "-t", "15000", "-a", "nobreak", titulo, mensagem]
    try:
        subprocess.run(cmd, check=False, timeout=5,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        pass  # sem notify-send / sem DBUS: só loga


def ler_ups(nome):
    """Roda upsc e devolve dict chave->valor (string)."""
    try:
        out = subprocess.run(["upsc", nome], capture_output=True, text=True,
                             timeout=10, check=True)
    except Exception as e:
        return None, f"upsc falhou: {e}"
    dados = {}
    for linha in out.stdout.splitlines():
        if ": " in linha:
            k, v = linha.split(": ", 1)
            dados[k.strip()] = v.strip()
    return dados, None


def resumo(dados):
    """Subconjunto estável de leituras para o evento (número SEMPRE medido)."""
    def pega(chave):
        try:
            return float(dados.get(chave, "nan"))
        except ValueError:
            return None
    return {
        "input_v": pega("input.voltage"),
        "output_v": pega("output.voltage"),
        "load_pct": pega("ups.load"),
        "battery_v": pega("battery.voltage"),
        "temp_c": pega("ups.temperature"),
    }


def registrar(evento, status, dados, extra=None):
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    linha = {
        "ts": agora(),
        "evento": evento,
        "ups_status": status,
        **resumo(dados),
    }
    if extra:
        linha.update(extra)
    with EVENTS_FILE.open("a", encoding="utf-8") as f:
        f.write(json.dumps(linha, ensure_ascii=False) + "\n")
    return linha


def classificar(status):
    """'OL' -> on_line; 'OB' -> no_break; 'LB' presente -> bateria_baixa."""
    flags = status.split()
    if "LB" in flags:
        return "bateria_baixa"
    if "OB" in flags:
        return "no_break"
    if "OL" in flags:
        return "on_line"
    return "desconhecido"


EVENTOS_HUMANOS = {
    "falta_de_luz": ("⚠️  Sem energia elétrica",
                     "O nobreak assumiu (bateria). Salve seu trabalho."),
    "energia_volvou": ("⚡ Energia restabelecida",
                       "Rede elétrica de volta. Nobreak recarregando."),
    "bateria_baixa": ("🔋 Bateria baixa!",
                      "Autonomia no fim — desligue a máquina em segurança."),
}


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--ups", default="nobreak@localhost")
    ap.add_argument("--intervalo", type=float, default=5.0)
    ap.add_argument("--once", action="store_true", help="uma leitura e sai")
    ap.add_argument("--dry-run", action="store_true",
                    help="não vigia: apenas testa notificações e registra evento de teste")
    ap.add_argument("--on-cmd", help="comando ao faltar luz (ex.: 'systemctl suspend')")
    ap.add_argument("--restore-cmd", help="comando quando a energia voltar")
    args = ap.parse_args()

    if args.dry_run:
        fake = {"input.voltage": "0.0", "ups.status": "OB LB", "ups.load": "8",
                "battery.voltage": "2.22", "ups.temperature": "30.0",
                "output.voltage": "220.0"}
        for evento in ("falta_de_luz", "energia_volvou", "bateria_baixa"):
            titulo, msg = EVENTOS_HUMANOS[evento]
            notificar(titulo, msg, critico=(evento in CRITICOS))
            registrar(evento, "OB LB (dry-run)", fake, {"dry_run": True})
        print(f"dry-run ok — eventos gravados em {EVENTS_FILE}")
        return 0

    print(f"guardião vigiando {args.ups} a cada {args.intervalo}s "
          f"(log: {EVENTS_FILE})")
    estado = None          # último estado classificado
    falhas = 0

    while True:
        dados, erro = ler_ups(args.ups)
        if erro:
            falhas += 1
            if falhas == 6:   # ~30s sem resposta: avisa uma vez
                notificar("Nobreak sem resposta",
                          f"{args.ups} não responde ({falhas} tentativas). "
                          "Verifique: systemctl status nut-driver@" +
                          args.ups.split("@")[0])
                registrar("ups_sem_resposta", "n/a", {},
                          {"erro": erro[:200], "falhas": falhas})
            if args.once:
                print(erro, file=sys.stderr)
                return 1
            time.sleep(args.intervalo)
            continue
        falhas = 0

        status = dados.get("ups.status", "?")
        novo = classificar(status)

        if estado is None:
            registrar("inicio_monitoramento", status, dados)
        elif novo != estado:
            if estado == "on_line" and novo in ("no_break", "bateria_baixa"):
                evento = ("bateria_baixa" if novo == "bateria_baixa"
                          else "falta_de_luz")
                titulo, msg = EVENTOS_HUMANOS[evento]
                notificar(titulo, msg, critico=True)
                registrar(evento, status, dados)
                if args.on_cmd:
                    subprocess.run(args.on_cmd, shell=True, check=False)
            elif estado in ("no_break", "bateria_baixa") and novo == "on_line":
                titulo, msg = EVENTOS_HUMANOS["energia_volvou"]
                notificar(titulo, msg)
                registrar("energia_volvou", status, dados)
                if args.restore_cmd:
                    subprocess.run(args.restore_cmd, shell=True, check=False)
            else:
                registrar("mudanca_status", status, dados,
                          {"anterior": estado, "atual": novo})
        estado = novo

        if args.once:
            print(json.dumps({**resumo(dados), "status": status,
                              "estado": novo}, ensure_ascii=False))
            return 0
        time.sleep(args.intervalo)


if __name__ == "__main__":
    sys.exit(main())
