#!/usr/bin/env bash
# =============================================================================
# uninstall.sh — desinstalação do kit nobreak-mec0003
#
# Remove: regra udev, units systemd (standalone e MQTT), seção do
# /etc/nut/ups.conf (com backup) e — com --purge — os arquivos em
# /usr/local/lib/nobreak-mec0003 e o /etc/nobreak-mec0003.env.
# Logs (journalctl) e backups NÃO são removidos.
#
# Uso:
#   sudo bash uninstall.sh [--name nobreak] [--yes] [--dry-run] [--purge]
# =============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=scripts/lib.sh
. "$SCRIPT_DIR/scripts/lib.sh"

usage() {
    sed -n '2,12p' "${BASH_SOURCE[0]}" | sed 's/^#\{1\} \{0,1\}//'
}

UPS_NAME="nobreak"
PURGE=0

while (( $# )); do
    case $1 in
        --name)
            [[ $# -ge 2 ]] || die "--name exige valor (nome da seção do ups.conf)"
            UPS_NAME=$2; shift ;;
        --name=*) UPS_NAME="${1#*=}" ;;
        --purge)  PURGE=1 ;;
        --yes|-y) ASSUME_YES=1 ;;
        --dry-run) DRY_RUN=1 ;;
        -h|--help) usage; exit 0 ;;
        *) err "opção desconhecida: $1"; usage >&2; exit 2 ;;
    esac
    shift
done

require_root_or_dry
[[ $UPS_NAME =~ ^[A-Za-z0-9_-]+$ ]] || die "nome de seção inválido: $UPS_NAME"

step "Desinstalação do kit nobreak-mec0003 (seção [$UPS_NAME])$([[ $DRY_RUN == 1 ]] && echo ' [DRY-RUN]')"
if (( ! ASSUME_YES && ! DRY_RUN )); then
    if [[ -t 0 ]]; then
        ask "Confirma a desinstalação? (s/N)" "n"
        [[ $REPLY == s || $REPLY == S || $REPLY == sim ]] || die "abortado pelo usuário."
    fi
fi

# 1) Units systemd (para mesmo se não existirem)
step "Parando e desabilitando units"
run systemctl disable --now "$UNIT_MQTT" 2>/dev/null || true
run systemctl disable --now "$UNIT_STANDALONE" 2>/dev/null || true
run rm -f "/etc/systemd/system/$UNIT_MQTT"
run rm -f "/etc/systemd/system/$UNIT_STANDALONE"
run systemctl daemon-reload

# 2) Regra udev
step "Removendo regra udev"
run rm -f "$UDEV_RULE_DST"
run udevadm control --reload-rules

# 3) Seção do ups.conf (com backup)
step "Removendo seção [$UPS_NAME] de $NUT_CONF"
if [[ -r $NUT_CONF ]] && upsconf_show_section "$NUT_CONF" "$UPS_NAME" | grep -q .; then
    backup_file "$NUT_CONF"
    if (( DRY_RUN )); then
        printf '%s[dry ]%s reescreveria %s sem a seção [%s]\n' "$C_C" "$C_0" "$NUT_CONF" "$UPS_NAME"
    else
        local_tmp="$(mktemp)"
        upsconf_without_section "$NUT_CONF" "$UPS_NAME" > "$local_tmp"
        cat "$local_tmp" > "$NUT_CONF"   # preserva dono/modo do arquivo original
        rm -f "$local_tmp"
        ok "seção [$UPS_NAME] removida (backup com sufixo .bak.<timestamp> ao lado)."
    fi
    run systemctl stop "nut-driver@${UPS_NAME}.service" 2>/dev/null || true
else
    info "nenhuma seção [$UPS_NAME] em $NUT_CONF — nada a fazer."
fi

# 4) Purge opcional
if (( PURGE )); then
    step "Purge: removendo $INSTALL_DIR e $ENV_FILE"
    run rm -rf "$INSTALL_DIR"
    run rm -f "$ENV_FILE"
else
    info "mantidos: $INSTALL_DIR e $ENV_FILE (use --purge para removê-los)."
fi

ok "Desinstalação concluída."
info "Logs antigos continuam no journal (ex.: journalctl -u $UNIT_STANDALONE -e)."
info "Se fez backup do ups.conf, restaure com o arquivo .bak.<timestamp> ao lado de $NUT_CONF."
