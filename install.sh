#!/usr/bin/env bash
# =============================================================================
# install.sh — instalador do kit nobreak-mec0003
#
# Nobreaks SMS/NHS/genéricos com chip USB MEC0003 (VID:PID 0001:0000, produto
# "MEC0003"). O chip fala Megatec Q1 tunelado em descritores de string USB;
# o firmware é frágil: trava se receber protocolo errado (recuperação:
# --unwedge ou replug) e responde ZEROS até haver polling ~1Hz pós-plug.
#
# Uso:
#   bash install.sh --check            diagnóstico SEM root (pode rodar como usuário)
#   bash install.sh --unwedge          ciclo "authorized" no sysfs p/ destravar o USB (root)
#   bash install.sh [--mode MODO] [--battery 12|24] [--name NOME] [--yes] [--dry-run]
#
# Modos:
#   nut        integração com NUT (nutdrv_qx subdriver=hunnox, protocol=q1) — recomendado
#   standalone driver Python (mec0003.py) + systemd, sem NUT
#   mqtt       standalone + paho-mqtt, config em /etc/nobreak-mec0003.env
#
# --dry-run  imprime tudo o que faria, sem alterar nada (não exige root).
# --yes      não-interativo (usa os defaults; exige --mode se não houver tty).
# Arch Linux primeiro; Debian/Ubuntu compatível. bash >= 4, NUT >= 2.7.
# =============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=scripts/lib.sh
. "$SCRIPT_DIR/scripts/lib.sh"

UPSC_TIMEOUT=90   # s — aquecimento do chip após restart pode demorar ~1 min

usage() {
    sed -n '2,23p' "${BASH_SOURCE[0]}" | sed 's/^#\{1\} \{0,1\}//'
}

# =============================================================================
# --check: diagnóstico sem root
# =============================================================================
do_check() {
    local reasons=() nut_ok=0 sa_ok=0

    step "Verificação de ambiente — kit nobreak MEC0003 (${MEC_VID}:${MEC_PID})"

    # 1) Dispositivo presente (lsusb + sysfs)
    local lsusb_line sysfs_devs
    lsusb_line="$(lsusb 2>/dev/null | grep -i "${MEC_VID}:${MEC_PID}" || true)"
    if [[ -n $lsusb_line ]]; then
        ok "dispositivo presente (lsusb): $lsusb_line"
    else
        warn "dispositivo ${MEC_VID}:${MEC_PID} NÃO visto no lsusb — plugue o nobreak (a instalação sem o hardware é permitida)."
    fi
    sysfs_devs="$(find_mec_sysfs)"
    if [[ -n $sysfs_devs ]]; then
        local d
        for d in $sysfs_devs; do ok "sysfs: /sys/bus/usb/devices/$d (usado pelo --unwedge)"; done
    else
        info "sysfs: nenhum nó ${MEC_VID}:${MEC_PID} (mesma observação acima)."
    fi

    # 2) NUT (modo nut)
    step "NUT (necessário para --mode nut)"
    local nutdrv upsc_bin nut_pkg
    nutdrv=""
    local p
    for p in /usr/lib/nut/nutdrv_qx /usr/libexec/nut/nutdrv_qx /lib/nut/nutdrv_qx; do
        if [[ -x $p ]]; then nutdrv=$p; break; fi
    done
    if [[ -z $nutdrv ]]; then nutdrv="$(find_bin nutdrv_qx || true)"; fi
    if [[ -n $nutdrv ]]; then
        ok "nutdrv_qx: $nutdrv"
    else
        warn "nutdrv_qx NÃO encontrado (espere /usr/lib/nut/nutdrv_qx)."
        reasons+=("modo nut: nutdrv_qx ausente — instale o pacote NUT (pacman -S nut / apt install nut)")
    fi
    upsc_bin="$(find_bin upsc || true)"
    if [[ -n $upsc_bin ]]; then
        ok "upsc: $upsc_bin"
    else
        warn "upsc NÃO encontrado — sem ele o instalador não consegue validar."
        reasons+=("modo nut: upsc ausente — instale o pacote NUT")
    fi
    if [[ ! -d /etc/nut ]]; then
        warn "/etc/nut não existe (pacote NUT não instalado?)."
        reasons+=("modo nut: /etc/nut ausente")
    fi
    nut_pkg="$(pacman -Q nut 2>/dev/null || dpkg-query -W -f='${Version}\n' nut 2>/dev/null || true)"
    if [[ -n $nut_pkg ]]; then info "pacote NUT: $nut_pkg"; fi
    if [[ -n $nutdrv && -n $upsc_bin && -d /etc/nut ]]; then nut_ok=1; fi

    # 3) Seção atual do ups.conf
    step "Seção atual em $NUT_CONF"
    if [[ -r $NUT_CONF ]]; then
        local cur
        cur="$(upsconf_show_section "$NUT_CONF" "$UPS_NAME")"
        if [[ -n $cur ]]; then
            info "seção [$UPS_NAME] já existe (o instalador a substitui, com backup):"
            printf '%s\n' "$cur" | sed 's/^/      | /'
        else
            info "nenhuma seção [$UPS_NAME] ainda — será criada."
        fi
    else
        info "$NUT_CONF não legível/ausente."
    fi

    # 4) Python (modos standalone/mqtt)
    step "Python (necessário para --mode standalone|mqtt)"
    local pyver py_mm py_ok=0
    pyver="$(python3 -V 2>&1 || true)"
    py_mm=0
    if [[ $pyver =~ Python\ ([0-9]+)\.([0-9]+) ]]; then
        py_mm=$((10#${BASH_REMATCH[1]} * 100 + 10#${BASH_REMATCH[2]}))
    fi
    if (( py_mm >= 308 )); then
        ok "python3: $pyver"
    else
        warn "python3 muito antigo: $pyver (mínimo 3.8)."
        reasons+=("modo standalone/mqtt: python3 >= 3.8 necessário")
    fi
    if python3 -c 'import venv, ensurepip' >/dev/null 2>&1; then
        ok "venv/ensurepip disponíveis"
    else
        warn "venv/ensurepip indisponíveis (no Debian: apt install python3-venv)."
        reasons+=("modo standalone/mqtt: python3-venv necessário")
    fi
    if (( py_mm >= 308 )) && python3 -c 'import venv, ensurepip' >/dev/null 2>&1; then py_ok=1; fi

    # 5) systemd
    step "systemd"
    local systemctl_bin
    systemctl_bin="$(find_bin systemctl || true)"
    if [[ -n $systemctl_bin && -d /run/systemd/system ]]; then
        ok "systemd ativo como init ($systemctl_bin)"
    elif [[ -n $systemctl_bin ]]; then
        warn "systemctl existe ($systemctl_bin) mas systemd NÃO é o init desta sessão."
        reasons+=("systemd não está rodando (contêiner?) — units não podem ser habilitadas")
    else
        warn "systemctl não encontrado."
        reasons+=("systemctl ausente")
    fi

    # Veredito: instalável se qualquer modo for viável.
    step "Veredito"
    if (( nut_ok )); then ok "modo nut: DISPONÍVEL"; else warn "modo nut: INDISPONÍVEL"; fi
    if (( py_ok )) && [[ -n $systemctl_bin ]]; then
        sa_ok=1
        ok "modo standalone/mqtt: DISPONÍVEL"
    else
        warn "modo standalone/mqtt: INDISPONÍVEL"
    fi
    if (( nut_ok || sa_ok )); then
        ok "AMBIENTE INSTALÁVEL — rode: sudo bash install.sh --mode <modo>"
        return 0
    fi
    err "AMBIENTE NÃO INSTALÁVEL — motivos:"
    local r
    for r in "${reasons[@]}"; do info " - $r"; done
    return 1
}

# =============================================================================
# --unwedge: destravar o firmware USB via sysfs authorized
# =============================================================================
do_unwedge() {
    require_root_or_dry
    step "Destravamento do chip MEC0003 (ciclo authorized no sysfs)"
    usb_cycle_authorized || die "o ciclo authorized falhou (o chip está plugado?)."
    ok "concluído. Dê até ~1 min de polling (pollinterval=2 no NUT) para o chip sair dos ZEROS."
}

# =============================================================================
# Passo comum: regra udev (todos os modos)
# =============================================================================
install_udev_rule() {
    step "Regra udev (permissão de acesso ao dispositivo)"
    local group src tmp
    group="$(detect_udev_group)"
    if [[ -z $group ]]; then
        if (( DRY_RUN )); then
            group="nut"
            info "nenhum grupo nut/plugdev existe — no modo real: groupadd -f nut e usaria grupo nut"
        else
            run groupadd -f nut
            group=nut
        fi
    fi
    src="$SCRIPT_DIR/udev/$UDEV_RULE_SRC_NAME"
    [[ -r $src ]] || die "modelo de regra udev ausente: $src"
    # O modelo usa GROUP="nut"; reescreve se o grupo escolhido for outro.
    tmp="$(sed "s/GROUP=\"nut\"/GROUP=\"$group\"/" "$src")"
    printf '%s\n' "$tmp" | write_file "$UDEV_RULE_DST" 0644
    run udevadm control --reload-rules
    # --subsystem-match: aceito em systemd antigos (Debian) e atuais (alias).
    run udevadm trigger --subsystem-match=usb
    ok "dispositivo ${MEC_VID}:${MEC_PID} acessível ao grupo '$group' após retrigger."
}

# =============================================================================
# Modo NUT
# =============================================================================
write_upsconf_section() {
    local name=$1 packs=$2 tmp
    step "Gravando seção [$name] em $NUT_CONF (idempotente)"
    tmp="$(mktemp)"
    if [[ -r $NUT_CONF ]]; then
        backup_file "$NUT_CONF"
        upsconf_without_section "$NUT_CONF" "$name" > "$tmp"
        printf '\n' >> "$tmp"
    fi
    upsconf_section_text "$name" "$packs" >> "$tmp"
    if (( DRY_RUN )); then
        printf '%s[dry ]%s escreveria %s com:\n' "$C_C" "$C_0" "$NUT_CONF"
        sed 's/^/      | /' "$tmp"
    else
        # cat > preserva inode (dono/modo originais do pacote NUT).
        cat "$tmp" > "$NUT_CONF"
        ok "seção [$name] gravada."
    fi
    rm -f "$tmp"
}

wait_for_upsc() {
    # Aguarda upsc responder com dados úteis. O chip recém-(re)plugado responde
    # ZEROS até ~1Hz de polling rodar por alguns segundos — pollinterval=2
    # resolve em ~1 min; por isso o timeout generoso e o unwedge no meio do caminho.
    local name=$1 timeout=${2:-$UPSC_TIMEOUT} cycled=0 out deadline start
    start=$SECONDS
    deadline=$(( start + timeout ))
    info "validando com upsc ${name}@localhost (até ${timeout}s — o chip pode precisar de aquecimento)..."
    while (( SECONDS < deadline )); do
        out="$(upsc "${name}@localhost" 2>/dev/null || true)"
        if [[ -n $out ]] \
           && grep -q '^ups\.status: .\+' <<<"$out" \
           && ! grep -q '^battery\.voltage: 0' <<<"$out"; then
            return 0
        fi
        if (( ! cycled && SECONDS - start >= 30 )); then
            warn "sem dados úteis após 30s — rodando ciclo authorized (destavamento do firmware USB)..."
            usb_cycle_authorized || true
            cycled=1
        fi
        sleep 3
    done
    return 1
}

install_nut() {
    local packs
    packs="$(battery_packs "$BATTERY")" || die "--battery inválida: $BATTERY (use 12 ou 24)."
    step "Modo NUT — nutdrv_qx (subdriver hunnox, protocolo q1)"
    [[ -d /etc/nut ]] || die "/etc/nut não existe — instale o NUT primeiro (pacman -S nut / apt install nut)."
    local upsc_bin
    upsc_bin="$(find_bin upsc || true)"
    [[ -n $upsc_bin ]] || die "upsc não encontrado — instale o pacote NUT completo."

    install_udev_rule
    write_upsconf_section "$UPS_NAME" "$packs"

    step "(Re)iniciando nut-driver@${UPS_NAME}"
    if (( DRY_RUN )); then
        run systemctl restart "nut-driver@${UPS_NAME}.service"
        run systemctl enable --now nut-server.service
        info "(dry-run: pularia a validação upsc de até ${UPSC_TIMEOUT}s)"
        return 0
    fi
    systemctl restart "nut-driver@${UPS_NAME}.service" \
        || warn "restart do nut-driver@${UPS_NAME} falhou (ele existe? pacman -S nut / apt install nut)."
    systemctl enable --now nut-server.service 2>/dev/null \
        || warn "não consegui habilitar nut-server.service — se o upsd já roda, ignore."

    step "Validação (upsc ${UPS_NAME}@localhost)"
    if wait_for_upsc "$UPS_NAME"; then
        ok "nobreak respondendo:"
        upsc "${UPS_NAME}@localhost" | sed 's/^/      /'
        local bv
        bv="$(upsc "${UPS_NAME}@localhost" 2>/dev/null | awk -F': ' '/^battery\.voltage:/{print $2}' || true)"
        if [[ -n $bv ]]; then
            info "battery.voltage=$bv é POR CÉLULA — total ≈ $(awk -v v="$bv" -v p="$packs" 'BEGIN{printf "%.1f", v*p}')V (packs=$packs)."
        fi
        ok "INSTALAÇÃO NUT CONCLUÍDA. Teste: upsc ${UPS_NAME}@localhost"
    else
        err "o nobreak não respondeu em ${UPSC_TIMEOUT}s. Checklist:"
        info " - journalctl -u nut-driver@${UPS_NAME}.service -e   (veja o erro do driver)"
        info " - sudo bash $0 --unwedge                        (destrava o firmware USB)"
        info " - replug físico + aguarde ~1 min de aquecimento e rode novamente"
        exit 1
    fi
}

# =============================================================================
# Modos standalone / mqtt
# =============================================================================
install_standalone() { # $1 = pip extra (paho-mqtt p/ mqtt), $2 = unit, $3 = com-mqtt(0/1)
    local extra_pip=$1 unit=$2 with_mqtt=$3
    local -a pips=(pyusb hidapi)
    if [[ -n $extra_pip ]]; then pips+=("$extra_pip"); fi
    step "Modo $MODE — instalando driver Python em $INSTALL_DIR"
    local src_py="$SCRIPT_DIR/mec0003.py"
    if [[ ! -f $src_py ]]; then
        if (( DRY_RUN )); then
            warn "mec0003.py ainda não existe na raiz do repo — no modo real a instalação ABORTARIA aqui."
        else
            die "mec0003.py não encontrado em $src_py (ele está na raiz do repo?)."
        fi
    fi

    run install -d -m 0755 "$INSTALL_DIR"
    if [[ -f $src_py ]]; then
        run install -m 0755 "$src_py" "$INSTALL_DIR/mec0003.py"
    fi
    run python3 -m venv "$INSTALL_DIR/venv"
    run "$INSTALL_DIR/venv/bin/pip" install --upgrade pip
    run "$INSTALL_DIR/venv/bin/pip" install "${pips[@]}"

    # Configuração MQTT (env lido pelo unit via EnvironmentFile=)
    if [[ $with_mqtt == 1 ]]; then
        step "Configuração MQTT ($ENV_FILE)"
        local broker port prefix
        ask "Broker MQTT (host)" localhost; broker=$REPLY
        ask "Porta do broker" 1883; port=$REPLY
        ask "Prefixo de tópico" nobreak/mec0003; prefix=$REPLY
        {
            printf '# Configuracao do publicador MQTT — nobreak MEC0003\n'
            printf '# Gerado por install.sh; lido por %s (EnvironmentFile=).\n' "$UNIT_MQTT"
            printf '# O driver tambem aceita: NUT_ON_BATTERY_CMD=comando (roda ao entrar em bateria).\n'
            printf 'MQTT_BROKER=%s\n' "$broker"
            printf 'MQTT_PORT=%s\n' "$port"
            printf 'MQTT_TOPIC_PREFIX=%s\n' "$prefix"
            printf 'POLL_SECONDS=2\n'
        } | write_file "$ENV_FILE" 0640
    fi

    step "Unit systemd ($unit)"
    local unit_src="$SCRIPT_DIR/systemd/$unit"
    [[ -r $unit_src ]] || die "unit ausente no repo: $unit_src"
    run install -m 0644 "$unit_src" "/etc/systemd/system/$unit"
    run systemctl daemon-reload
    # O outro unit que fala com o chip precisa parar (Conflicts= cuida disso,
    # mas desabilitamos explicitamente para não voltar no boot).
    if [[ $unit == "$UNIT_MQTT" ]]; then
        run systemctl disable --now "$UNIT_STANDALONE" 2>/dev/null || true
    else
        run systemctl disable --now "$UNIT_MQTT" 2>/dev/null || true
    fi
    run systemctl enable --now "$unit"
    if (( DRY_RUN )); then
        return 0
    fi
    sleep 2
    if systemctl is-active --quiet "$unit"; then
        ok "serviço ativo. Logs: journalctl -u $unit -f"
    else
        warn "serviço não subiu ainda — veja: journalctl -u $unit -e"
    fi
}

# =============================================================================
# Instalação (padrão)
# =============================================================================
do_install() {
    require_root_or_dry

    # Resolve o modo (interativo quando possível)
    if [[ -z $MODE ]]; then
        if [[ -t 0 ]] && (( ! ASSUME_YES )); then
            echo "Modos de instalação:"
            echo "  1) nut        — NUT/nutdrv_qx (recomendado: integra com upsmon/monitoração)"
            echo "  2) standalone — driver Python + systemd, sem NUT"
            echo "  3) mqtt       — standalone + publicação MQTT"
            ask "Escolha o modo" 1
            case $REPLY in
                1|nut) MODE=nut ;;
                2|standalone) MODE=standalone ;;
                3|mqtt) MODE=mqtt ;;
                *) die "modo inválido: $REPLY (use nut, standalone ou mqtt)" ;;
            esac
        else
            MODE=nut
            info "sem interatividade e sem --mode: assumindo modo padrão 'nut'."
        fi
    fi
    case $MODE in nut|standalone|mqtt) ;; *) die "modo inválido: $MODE" ;; esac
    [[ $UPS_NAME =~ ^[A-Za-z0-9_-]+$ ]] || die "nome de seção inválido: $UPS_NAME (use [A-Za-z0-9_-])"
    [[ $BATTERY == 12 || $BATTERY == 24 ]] || die "--battery inválida: $BATTERY (use 12 ou 24)"

    # Pergunta a bateria onde o valor é usado (nut: battery.packs no ups.conf).
    # Default 12V → 6 packs (battery.voltage do chip vem POR CÉLULA).
    if [[ $MODE == nut ]] && (( ! ASSUME_YES )) && [[ -t 0 ]]; then
        ask "Tensão da bateria do nobreak (12V → packs=6, 24V → packs=12)" "$BATTERY"
        BATTERY=$REPLY
        [[ $BATTERY == 12 || $BATTERY == 24 ]] || die "tensão inválida: $BATTERY (12 ou 24)."
    fi

    step "Instalação nobreak-mec0003 — modo=$MODE bateria=${BATTERY}V seção=$UPS_NAME$([[ $DRY_RUN == 1 ]] && echo ' [DRY-RUN]')"
    case $MODE in
        nut)        install_nut ;;
        standalone) install_udev_rule; install_standalone "" "$UNIT_STANDALONE" 0 ;;
        mqtt)       install_udev_rule; install_standalone "paho-mqtt" "$UNIT_MQTT" 1 ;;
    esac
    ok "Concluído ($MODE)."
}

# =============================================================================
# CLI
# =============================================================================
CMD="install"
MODE=""
BATTERY=12
UPS_NAME="nobreak"

while (( $# )); do
    case $1 in
        --check)   CMD="check" ;;
        --unwedge) CMD="unwedge" ;;
        --mode)
            [[ $# -ge 2 ]] || die "--mode exige valor: nut|standalone|mqtt"
            MODE=$2; shift ;;
        --mode=*)   MODE="${1#*=}" ;;
        --battery)
            [[ $# -ge 2 ]] || die "--battery exige valor: 12 ou 24"
            BATTERY=$2; shift ;;
        --battery=*) BATTERY="${1#*=}" ;;
        --name)
            [[ $# -ge 2 ]] || die "--name exige valor (nome da seção do ups.conf)"
            UPS_NAME=$2; shift ;;
        --name=*)   UPS_NAME="${1#*=}" ;;
        --yes|-y)   ASSUME_YES=1 ;;
        --dry-run)  DRY_RUN=1 ;;
        -h|--help)  usage; exit 0 ;;
        *) err "opção desconhecida: $1"; usage >&2; exit 2 ;;
    esac
    shift
done

case $CMD in
    check)   do_check ;;
    unwedge) do_unwedge ;;
    install) do_install ;;
    *)       err "comando desconhecido: $CMD"; exit 2 ;;
esac
