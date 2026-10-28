#!/usr/bin/env bash
# =============================================================================
# install.sh — installer of nobreak-omarchy, the community UPS kit for
# Omarchy (Arch + Hyprland) and other systemd Linux desktops.
#
# Installs, for the chosen driver (drivers/<name>/):
#   * the driver's udev rule and NUT config (/etc/nut/ups.conf section)
#   * core/autoheal  — system timer that replugs the USB by software if NUT
#                      loses the UPS (only for drivers with autoheal = true)
#   * core/guardian  — user service with desktop notifications on power events
#
# Usage:
#   bash install.sh --check            diagnostics WITHOUT root
#   bash install.sh --unwedge          sysfs "authorized" cycle to unwedge the USB (root)
#   bash install.sh --list-drivers     list the available drivers
#   sudo bash install.sh [--driver NAME] [--mode MODE] [--battery 12|24]
#                        [--name UPS] [--no-guardian] [--no-autoheal]
#                        [--yes] [--dry-run]
#
# --driver   driver directory under drivers/ (default: mec0003)
# Modes (the driver's driver.toml says which it supports):
#   nut        NUT integration (recommended; enables guardian + autoheal)
#   standalone the driver's own Python daemon + systemd, without NUT
#   mqtt       standalone + paho-mqtt, config in /etc/nobreak-<driver>.env
#
# --dry-run  prints everything it would do, changes nothing (no root needed).
# --yes      non-interactive (uses defaults).
# Arch Linux / Omarchy first; Debian/Ubuntu compatible. bash >= 4, NUT >= 2.7.
# =============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=scripts/lib.sh
. "$SCRIPT_DIR/scripts/lib.sh"

UPSC_TIMEOUT=90   # s — chip warm-up after a restart can take ~1 min

usage() {
    sed -n '2,29p' "${BASH_SOURCE[0]}" | sed 's/^#\{1\} \{0,1\}//'
}

# =============================================================================
# --check: diagnostics without root
# =============================================================================
do_check() {
    local reasons=() nut_ok=0 sa_ok=0

    step "Environment check — $KIT_NAME, driver $DRIVER (${DRV_VIDPID})"
    info "driver status: ${DRV_STATUS:-unknown}"

    # 1) Device present (lsusb + sysfs)
    local lsusb_line sysfs_devs
    lsusb_line="$(lsusb 2>/dev/null | grep -i "${DRV_VIDPID}" || true)"
    if [[ -n $lsusb_line ]]; then
        ok "device present (lsusb): $lsusb_line"
    else
        warn "device ${DRV_VIDPID} NOT seen in lsusb — plug in the UPS (installing without the hardware is allowed)."
    fi
    sysfs_devs="$(find_dev_sysfs)"
    if [[ -n $sysfs_devs ]]; then
        local d
        for d in $sysfs_devs; do ok "sysfs: /sys/bus/usb/devices/$d (used by --unwedge and autoheal)"; done
    else
        info "sysfs: no ${DRV_VIDPID} node (same remark as above)."
    fi

    # 2) NUT (nut mode)
    step "NUT (needed for --mode nut)"
    local nutdrv="" upsc_bin nut_pkg p drvbin=${DRV_NUT_DRIVER:-}
    if [[ -n $drvbin ]]; then
        for p in "/usr/lib/nut/$drvbin" "/usr/libexec/nut/$drvbin" "/lib/nut/$drvbin"; do
            if [[ -x $p ]]; then nutdrv=$p; break; fi
        done
        if [[ -z $nutdrv ]]; then nutdrv="$(find_bin "$drvbin" || true)"; fi
        if [[ -n $nutdrv ]]; then
            ok "$drvbin: $nutdrv"
        else
            warn "$drvbin NOT found (expected /usr/lib/nut/$drvbin)."
            reasons+=("nut mode: $drvbin missing — install NUT (pacman -S nut / apt install nut)")
        fi
    else
        warn "driver $DRIVER declares no nut_driver — nut mode not available for it."
        reasons+=("nut mode: not supported by driver $DRIVER")
    fi
    upsc_bin="$(find_bin upsc || true)"
    if [[ -n $upsc_bin ]]; then
        ok "upsc: $upsc_bin"
    else
        warn "upsc NOT found — without it the installer cannot validate (and the guardian cannot run)."
        reasons+=("nut mode: upsc missing — install NUT")
    fi
    if [[ ! -d /etc/nut ]]; then
        warn "/etc/nut does not exist (NUT package not installed?)."
        reasons+=("nut mode: /etc/nut missing")
    fi
    nut_pkg="$(pacman -Q nut 2>/dev/null || dpkg-query -W -f='${Version}\n' nut 2>/dev/null || true)"
    if [[ -n $nut_pkg ]]; then info "NUT package: $nut_pkg"; fi
    if [[ -n $nutdrv && -n $upsc_bin && -d /etc/nut ]]; then nut_ok=1; fi

    # 3) Current ups.conf section
    step "Current section in $NUT_CONF"
    if [[ -r $NUT_CONF ]]; then
        local cur
        cur="$(upsconf_show_section "$NUT_CONF" "$UPS_NAME")"
        if [[ -n $cur ]]; then
            info "section [$UPS_NAME] already exists (the installer replaces it, with a backup):"
            printf '%s\n' "$cur" | sed 's/^/      | /'
        else
            info "no [$UPS_NAME] section yet — it will be created."
        fi
    else
        info "$NUT_CONF not readable/missing."
    fi

    # 4) Python
    step "Python (guardian; driver --mode standalone|mqtt)"
    local pyver py_mm py_ok=0
    pyver="$(python3 -V 2>&1 || true)"
    py_mm=0
    if [[ $pyver =~ Python\ ([0-9]+)\.([0-9]+) ]]; then
        py_mm=$((10#${BASH_REMATCH[1]} * 100 + 10#${BASH_REMATCH[2]}))
    fi
    if (( py_mm >= 308 )); then
        ok "python3: $pyver"
    else
        warn "python3 too old: $pyver (minimum 3.8)."
        reasons+=("python3 >= 3.8 required")
    fi
    if python3 -c 'import venv, ensurepip' >/dev/null 2>&1; then
        ok "venv/ensurepip available"
    else
        warn "venv/ensurepip unavailable (on Debian: apt install python3-venv)."
        reasons+=("standalone/mqtt mode: python3-venv required")
    fi
    if (( py_mm >= 308 )) && python3 -c 'import venv, ensurepip' >/dev/null 2>&1 \
        && [[ -f $DRV_SCRIPT ]]; then py_ok=1; fi

    # 5) Desktop notifications (guardian)
    step "Desktop notifications (guardian)"
    if find_bin notify-send >/dev/null; then
        ok "notify-send available"
    else
        warn "notify-send missing (pacman -S libnotify) — the guardian will only log."
    fi

    # 6) systemd
    step "systemd"
    local systemctl_bin
    systemctl_bin="$(find_bin systemctl || true)"
    if [[ -n $systemctl_bin && -d /run/systemd/system ]]; then
        ok "systemd is the init ($systemctl_bin)"
    elif [[ -n $systemctl_bin ]]; then
        warn "systemctl exists ($systemctl_bin) but systemd is NOT the init of this session."
        reasons+=("systemd is not running (container?) — units cannot be enabled")
    else
        warn "systemctl not found."
        reasons+=("systemctl missing")
    fi

    # Verdict: installable if any mode is viable.
    step "Verdict"
    if (( nut_ok )); then ok "nut mode: AVAILABLE"; else warn "nut mode: UNAVAILABLE"; fi
    if (( py_ok )) && [[ -n $systemctl_bin ]]; then
        sa_ok=1
        ok "standalone/mqtt mode: AVAILABLE"
    else
        warn "standalone/mqtt mode: UNAVAILABLE"
    fi
    if (( nut_ok || sa_ok )); then
        ok "ENVIRONMENT INSTALLABLE — run: sudo bash install.sh --driver $DRIVER --mode <mode>"
        return 0
    fi
    err "ENVIRONMENT NOT INSTALLABLE — reasons:"
    local r
    for r in "${reasons[@]}"; do info " - $r"; done
    return 1
}

# =============================================================================
# --unwedge: unwedge the USB firmware via sysfs authorized
# =============================================================================
do_unwedge() {
    require_root_or_dry
    step "Unwedging the $DRIVER chip (sysfs authorized cycle)"
    usb_cycle_authorized || die "the authorized cycle failed (is the chip plugged in?)."
    ok "done. Give it up to ~1 min of polling (pollinterval=2 in NUT) to leave the ZEROS state."
}

# =============================================================================
# Common step: udev rule (all modes)
# =============================================================================
install_udev_rule() {
    step "udev rule (device access permission)"
    if [[ -z $DRV_UDEV_SRC ]]; then
        info "driver $DRIVER ships no udev rule — skipping."
        return 0
    fi
    local group tmp
    group="$(detect_udev_group)"
    if [[ -z $group ]]; then
        if (( DRY_RUN )); then
            group="nut"
            info "no nut/plugdev group exists — for real: groupadd -f nut and use group nut"
        else
            run groupadd -f nut
            group=nut
        fi
    fi
    # The template uses GROUP="nut"; rewrite if the chosen group differs.
    tmp="$(sed "s/GROUP=\"nut\"/GROUP=\"$group\"/" "$DRV_UDEV_SRC")"
    printf '%s\n' "$tmp" | write_file "$DRV_UDEV_DST" 0644
    run udevadm control --reload-rules
    # --subsystem-match: accepted by old (Debian) and current systemd.
    run udevadm trigger --subsystem-match=usb
    ok "device ${DRV_VIDPID} accessible to group '$group' after retrigger."
}

# =============================================================================
# NUT mode
# =============================================================================
write_upsconf_section() {
    local name=$1 packs=$2 tmp
    step "Writing section [$name] to $NUT_CONF (idempotent)"
    tmp="$(mktemp)"
    if [[ -r $NUT_CONF ]]; then
        backup_file "$NUT_CONF"
        upsconf_without_section "$NUT_CONF" "$name" > "$tmp"
        printf '\n' >> "$tmp"
    fi
    upsconf_section_text "$name" "$packs" >> "$tmp"
    if (( DRY_RUN )); then
        printf '%s[dry ]%s would write %s with:\n' "$C_C" "$C_0" "$NUT_CONF"
        sed 's/^/      | /' "$tmp"
    else
        # cat > keeps the inode (owner/mode from the NUT package).
        cat "$tmp" > "$NUT_CONF"
        ok "section [$name] written."
    fi
    rm -f "$tmp"
}

wait_for_upsc() {
    # Wait for upsc to answer with useful data. A freshly (re)plugged MEC0003
    # answers ZEROS until it is polled at ~1 Hz for a few seconds —
    # pollinterval=2 fixes it in ~1 min; hence the generous timeout and the
    # unwedge halfway through.
    local name=$1 timeout=${2:-$UPSC_TIMEOUT} cycled=0 out deadline start
    start=$SECONDS
    deadline=$(( start + timeout ))
    info "validating with upsc ${name}@localhost (up to ${timeout}s — the chip may need to warm up)..."
    while (( SECONDS < deadline )); do
        out="$(upsc "${name}@localhost" 2>/dev/null || true)"
        if [[ -n $out ]] \
           && grep -q '^ups\.status: .\+' <<<"$out" \
           && ! grep -q '^battery\.voltage: 0' <<<"$out"; then
            return 0
        fi
        if (( ! cycled && SECONDS - start >= 30 )); then
            warn "no useful data after 30s — running an authorized cycle (USB firmware unwedge)..."
            usb_cycle_authorized || true
            cycled=1
        fi
        sleep 3
    done
    return 1
}

install_nut() {
    local packs
    packs="$(battery_packs "$BATTERY")" || die "invalid --battery: $BATTERY (use 12 or 24)."
    [[ -n $DRV_NUT_DRIVER ]] || die "driver $DRIVER does not support nut mode (no nut_driver in driver.toml)."
    step "NUT mode — driver $DRIVER ($DRV_NUT_DRIVER)"
    [[ -d /etc/nut ]] || (( DRY_RUN )) || die "/etc/nut does not exist — install NUT first (pacman -S nut / apt install nut)."
    local upsc_bin
    upsc_bin="$(find_bin upsc || true)"
    [[ -n $upsc_bin ]] || (( DRY_RUN )) || die "upsc not found — install the full NUT package."

    install_udev_rule
    write_upsconf_section "$UPS_NAME" "$packs"

    step "(Re)starting nut-driver@${UPS_NAME}"
    if (( DRY_RUN )); then
        run systemctl restart "nut-driver@${UPS_NAME}.service"
        run systemctl enable --now nut-server.service
        info "(dry-run: would skip the upsc validation of up to ${UPSC_TIMEOUT}s)"
        return 0
    fi
    systemctl restart "nut-driver@${UPS_NAME}.service" \
        || warn "restart of nut-driver@${UPS_NAME} failed (does it exist? pacman -S nut / apt install nut)."
    systemctl enable --now nut-server.service 2>/dev/null \
        || warn "could not enable nut-server.service — if upsd is already running, ignore."

    step "Validation (upsc ${UPS_NAME}@localhost)"
    if wait_for_upsc "$UPS_NAME"; then
        ok "UPS answering:"
        upsc "${UPS_NAME}@localhost" | sed 's/^/      /'
        ok "NUT INSTALL COMPLETE. Test: upsc ${UPS_NAME}@localhost"
    else
        err "the UPS did not answer within ${UPSC_TIMEOUT}s. Checklist:"
        info " - journalctl -u nut-driver@${UPS_NAME}.service -e   (see the driver error)"
        info " - sudo bash $0 --driver $DRIVER --unwedge         (unwedges the USB firmware)"
        info " - physical replug + wait ~1 min of warm-up and run again"
        exit 1
    fi
}

# =============================================================================
# Core: autoheal (system timer) and guardian (user service)
# =============================================================================
install_autoheal() {
    step "Core: autoheal (software USB replug when NUT loses the UPS)"
    if [[ $DRV_AUTOHEAL != true ]]; then
        info "driver $DRIVER has autoheal = false — skipping."
        return 0
    fi
    run install -m 0755 "$SCRIPT_DIR/core/autoheal/nobreak-autoheal" "$AUTOHEAL_BIN"
    {
        printf '# nobreak-omarchy autoheal config — generated by install.sh (driver %s)\n' "$DRIVER"
        printf 'NOBREAK_VIDPID=%s\n' "$DRV_VIDPID"
        printf 'NOBREAK_UPS=%s@localhost\n' "$UPS_NAME"
        printf 'NOBREAK_NUT_UNIT=nut-driver@%s.service\n' "$UPS_NAME"
    } | write_file "$AUTOHEAL_ENV" 0644
    run install -m 0644 "$SCRIPT_DIR/core/autoheal/$AUTOHEAL_SERVICE" "/etc/systemd/system/$AUTOHEAL_SERVICE"
    run install -m 0644 "$SCRIPT_DIR/core/autoheal/$AUTOHEAL_TIMER" "/etc/systemd/system/$AUTOHEAL_TIMER"
    run systemctl daemon-reload
    run systemctl enable --now "$AUTOHEAL_TIMER"
    ok "autoheal timer enabled (logs: journalctl -t nobreak-autoheal)."
}

install_guardian() {
    step "Core: guardian (desktop notifications on power events)"
    run install -d -m 0755 "$KIT_LIB"
    run install -m 0755 "$SCRIPT_DIR/core/guardian/guardian.py" "$KIT_LIB/guardian.py"
    sed "s/--ups nobreak@localhost/--ups ${UPS_NAME}@localhost/" \
        "$SCRIPT_DIR/core/guardian/$GUARDIAN_UNIT" | write_file "$GUARDIAN_UNIT_DST" 0644
    if as_desktop_user systemctl --user daemon-reload \
        && as_desktop_user systemctl --user enable --now "$GUARDIAN_UNIT"; then
        ok "guardian enabled for user ${SUDO_USER}."
    else
        info "enable it as your desktop user: systemctl --user daemon-reload && systemctl --user enable --now $GUARDIAN_UNIT"
    fi
    info "events are logged to ~/.local/state/nobreak-omarchy/events.jsonl"
}

# =============================================================================
# standalone / mqtt modes
# =============================================================================
install_standalone() { # $1 = pip extra (paho-mqtt for mqtt), $2 = unit, $3 = with-mqtt (0/1)
    local extra_pip=$1 unit=$2 with_mqtt=$3
    local -a pips=(pyusb pyserial hidapi)
    if [[ -n $extra_pip ]]; then pips+=("$extra_pip"); fi
    step "Mode $MODE — installing the $DRIVER Python driver into $INSTALL_DIR"
    [[ -f $DRV_SCRIPT ]] || die "driver $DRIVER has no standalone driver.py ($DRV_SCRIPT) — use --mode nut."

    run install -d -m 0755 "$INSTALL_DIR"
    run install -m 0755 "$DRV_SCRIPT" "$INSTALL_DIR/driver.py"
    run python3 -m venv "$INSTALL_DIR/venv"
    run "$INSTALL_DIR/venv/bin/pip" install --upgrade pip
    run "$INSTALL_DIR/venv/bin/pip" install "${pips[@]}"

    # MQTT config (env read by the unit via EnvironmentFile=)
    if [[ $with_mqtt == 1 ]]; then
        step "MQTT config ($ENV_FILE)"
        local broker port prefix
        ask "MQTT broker (host)" localhost; broker=$REPLY
        ask "Broker port" 1883; port=$REPLY
        ask "Topic prefix" "nobreak/$DRIVER"; prefix=$REPLY
        {
            printf '# MQTT publisher config — nobreak-omarchy driver %s\n' "$DRIVER"
            printf '# Generated by install.sh; read by %s (EnvironmentFile=).\n' "$UNIT_MQTT"
            printf '# The driver also accepts: NUT_ON_BATTERY_CMD=command (runs when going on battery).\n'
            printf 'MQTT_BROKER=%s\n' "$broker"
            printf 'MQTT_PORT=%s\n' "$port"
            printf 'MQTT_TOPIC_PREFIX=%s\n' "$prefix"
            printf 'POLL_SECONDS=2\n'
        } | write_file "$ENV_FILE" 0640
    fi

    step "systemd unit ($unit)"
    local unit_src="$DRIVER_DIR/systemd/$unit"
    [[ -r $unit_src ]] || die "unit missing in the driver: $unit_src"
    run install -m 0644 "$unit_src" "/etc/systemd/system/$unit"
    run systemctl daemon-reload
    # NUT and the other unit must not talk to the chip at the same time.
    run systemctl disable --now "nut-driver@${UPS_NAME}.service" 2>/dev/null || true
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
        ok "service active. Logs: journalctl -u $unit -f"
    else
        warn "service is not up yet — see: journalctl -u $unit -e"
    fi
}

# =============================================================================
# Install (default)
# =============================================================================
do_install() {
    require_root_or_dry

    # Resolve the mode (interactive when possible)
    if [[ -z $MODE ]]; then
        if [[ -t 0 ]] && (( ! ASSUME_YES )); then
            echo "Install modes:"
            echo "  1) nut        — NUT (recommended: guardian notifications + autoheal + upsmon)"
            echo "  2) standalone — the driver's Python daemon + systemd, without NUT"
            echo "  3) mqtt       — standalone + MQTT publishing (Home Assistant)"
            ask "Pick a mode" 1
            case $REPLY in
                1|nut) MODE=nut ;;
                2|standalone) MODE=standalone ;;
                3|mqtt) MODE=mqtt ;;
                *) die "invalid mode: $REPLY (use nut, standalone or mqtt)" ;;
            esac
        else
            MODE=nut
            info "non-interactive and no --mode: assuming default mode 'nut'."
        fi
    fi
    case $MODE in nut|standalone|mqtt) ;; *) die "invalid mode: $MODE" ;; esac
    [[ $UPS_NAME =~ ^[A-Za-z0-9_-]+$ ]] || die "invalid section name: $UPS_NAME (use [A-Za-z0-9_-])"
    [[ $BATTERY == 12 || $BATTERY == 24 ]] || die "invalid --battery: $BATTERY (use 12 or 24)"

    # Ask for the battery where it is used (nut: battery.packs in ups.conf).
    if [[ $MODE == nut ]] && (( ! ASSUME_YES )) && [[ -t 0 ]]; then
        ask "UPS battery voltage (12V -> packs=6, 24V -> packs=12)" "$BATTERY"
        BATTERY=$REPLY
        [[ $BATTERY == 12 || $BATTERY == 24 ]] || die "invalid voltage: $BATTERY (12 or 24)."
    fi

    step "Installing $KIT_NAME — driver=$DRIVER mode=$MODE battery=${BATTERY}V section=$UPS_NAME$([[ $DRY_RUN == 1 ]] && echo ' [DRY-RUN]')"
    case $MODE in
        nut)
            install_nut
            if (( WITH_AUTOHEAL )); then install_autoheal; fi
            if (( WITH_GUARDIAN )); then install_guardian; fi
            ;;
        standalone) install_udev_rule; install_standalone "" "$UNIT_STANDALONE" 0 ;;
        mqtt)       install_udev_rule; install_standalone "paho-mqtt" "$UNIT_MQTT" 1 ;;
    esac
    if [[ $MODE != nut ]]; then
        info "guardian and autoheal need NUT (upsc) — they are only installed in --mode nut."
    fi
    ok "Done ($DRIVER, $MODE)."
}

# =============================================================================
# CLI
# =============================================================================
CMD="install"
MODE=""
BATTERY=12
UPS_NAME=""
DRIVER_ARG="mec0003"
WITH_GUARDIAN=1
WITH_AUTOHEAL=1

while (( $# )); do
    case $1 in
        --check)   CMD="check" ;;
        --unwedge) CMD="unwedge" ;;
        --list-drivers) CMD="list" ;;
        --driver)
            [[ $# -ge 2 ]] || die "--driver needs a value (see --list-drivers)"
            DRIVER_ARG=$2; shift ;;
        --driver=*) DRIVER_ARG="${1#*=}" ;;
        --mode)
            [[ $# -ge 2 ]] || die "--mode needs a value: nut|standalone|mqtt"
            MODE=$2; shift ;;
        --mode=*)   MODE="${1#*=}" ;;
        --mqtt)     MODE=mqtt ;;
        --battery)
            [[ $# -ge 2 ]] || die "--battery needs a value: 12 or 24"
            BATTERY=$2; shift ;;
        --battery=*) BATTERY="${1#*=}" ;;
        --name)
            [[ $# -ge 2 ]] || die "--name needs a value (ups.conf section name)"
            UPS_NAME=$2; shift ;;
        --name=*)   UPS_NAME="${1#*=}" ;;
        --no-guardian) WITH_GUARDIAN=0 ;;
        --no-autoheal) WITH_AUTOHEAL=0 ;;
        --yes|-y)   ASSUME_YES=1 ;;
        --dry-run)  DRY_RUN=1 ;;
        -h|--help)  usage; exit 0 ;;
        *) err "unknown option: $1"; usage >&2; exit 2 ;;
    esac
    shift
done

if [[ $CMD == list ]]; then
    list_drivers "$SCRIPT_DIR"
    exit 0
fi
load_driver "$SCRIPT_DIR" "$DRIVER_ARG"
UPS_NAME=${UPS_NAME:-$DRV_UPS_NAME}

case $CMD in
    check)   do_check ;;
    unwedge) do_unwedge ;;
    install) do_install ;;
    *)       err "unknown command: $CMD"; exit 2 ;;
esac
