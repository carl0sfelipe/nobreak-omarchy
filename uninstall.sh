#!/usr/bin/env bash
# =============================================================================
# uninstall.sh — uninstaller of nobreak-omarchy
#
# Removes: the driver's udev rule and systemd units (standalone and MQTT),
# the core autoheal timer and guardian user unit, the /etc/nut/ups.conf
# section (with a backup) and — with --purge — the files under
# /usr/local/lib/nobreak-omarchy, /etc/nobreak-omarchy and /etc/nobreak-<driver>.env.
# Logs (journalctl), backups and ~/.local/state/nobreak-omarchy are NOT removed.
#
# Usage:
#   sudo bash uninstall.sh [--driver mec0003] [--name nobreak] [--yes] [--dry-run] [--purge]
# =============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=scripts/lib.sh
. "$SCRIPT_DIR/scripts/lib.sh"

usage() {
    sed -n '2,13p' "${BASH_SOURCE[0]}" | sed 's/^#\{1\} \{0,1\}//'
}

UPS_NAME=""
DRIVER_ARG="mec0003"
PURGE=0

while (( $# )); do
    case $1 in
        --driver)
            [[ $# -ge 2 ]] || die "--driver needs a value"
            DRIVER_ARG=$2; shift ;;
        --driver=*) DRIVER_ARG="${1#*=}" ;;
        --name)
            [[ $# -ge 2 ]] || die "--name needs a value (ups.conf section name)"
            UPS_NAME=$2; shift ;;
        --name=*) UPS_NAME="${1#*=}" ;;
        --purge)  PURGE=1 ;;
        --yes|-y) ASSUME_YES=1 ;;
        --dry-run) DRY_RUN=1 ;;
        -h|--help) usage; exit 0 ;;
        *) err "unknown option: $1"; usage >&2; exit 2 ;;
    esac
    shift
done

load_driver "$SCRIPT_DIR" "$DRIVER_ARG"
UPS_NAME=${UPS_NAME:-$DRV_UPS_NAME}
require_root_or_dry
[[ $UPS_NAME =~ ^[A-Za-z0-9_-]+$ ]] || die "invalid section name: $UPS_NAME"

step "Uninstalling $KIT_NAME (driver $DRIVER, section [$UPS_NAME])$([[ $DRY_RUN == 1 ]] && echo ' [DRY-RUN]')"
if (( ! ASSUME_YES && ! DRY_RUN )); then
    if [[ -t 0 ]]; then
        ask "Confirm uninstall? (y/N)" "n"
        [[ $REPLY == y || $REPLY == Y || $REPLY == yes ]] || die "aborted by the user."
    fi
fi

# 1) Driver systemd units (stop even if they do not exist)
step "Stopping and disabling driver units"
run systemctl disable --now "$UNIT_MQTT" 2>/dev/null || true
run systemctl disable --now "$UNIT_STANDALONE" 2>/dev/null || true
run rm -f "/etc/systemd/system/$UNIT_MQTT"
run rm -f "/etc/systemd/system/$UNIT_STANDALONE"

# 2) Core: autoheal + guardian
step "Removing core autoheal timer and guardian unit"
run systemctl disable --now "$AUTOHEAL_TIMER" 2>/dev/null || true
run rm -f "/etc/systemd/system/$AUTOHEAL_TIMER" "/etc/systemd/system/$AUTOHEAL_SERVICE" "$AUTOHEAL_BIN"
as_desktop_user systemctl --user disable --now "$GUARDIAN_UNIT" 2>/dev/null \
    || info "if the guardian runs for your user: systemctl --user disable --now $GUARDIAN_UNIT"
run rm -f "$GUARDIAN_UNIT_DST"
run systemctl daemon-reload

# 3) udev rule
step "Removing udev rule"
if [[ -n $DRV_UDEV_DST ]]; then
    run rm -f "$DRV_UDEV_DST"
    run udevadm control --reload-rules
fi

# 4) ups.conf section (with backup)
step "Removing section [$UPS_NAME] from $NUT_CONF"
if [[ -r $NUT_CONF ]] && upsconf_show_section "$NUT_CONF" "$UPS_NAME" | grep -q .; then
    backup_file "$NUT_CONF"
    if (( DRY_RUN )); then
        printf '%s[dry ]%s would rewrite %s without section [%s]\n' "$C_C" "$C_0" "$NUT_CONF" "$UPS_NAME"
    else
        local_tmp="$(mktemp)"
        upsconf_without_section "$NUT_CONF" "$UPS_NAME" > "$local_tmp"
        cat "$local_tmp" > "$NUT_CONF"   # keeps owner/mode of the original file
        rm -f "$local_tmp"
        ok "section [$UPS_NAME] removed (backup with suffix .bak.<timestamp> next to it)."
    fi
    run systemctl stop "nut-driver@${UPS_NAME}.service" 2>/dev/null || true
else
    info "no [$UPS_NAME] section in $NUT_CONF — nothing to do."
fi

# 5) Optional purge
if (( PURGE )); then
    step "Purge: removing $KIT_LIB, $KIT_ETC and $ENV_FILE"
    run rm -rf "$KIT_LIB" "$KIT_ETC"
    run rm -f "$ENV_FILE"
else
    info "kept: $KIT_LIB, $KIT_ETC and $ENV_FILE (use --purge to remove them)."
fi

ok "Uninstall complete."
info "Old logs stay in the journal (e.g. journalctl -t nobreak-autoheal, journalctl -u $UNIT_STANDALONE -e)."
info "If ups.conf was backed up, restore it from the .bak.<timestamp> file next to $NUT_CONF."
