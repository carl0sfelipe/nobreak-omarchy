# shellcheck shell=bash disable=SC2034  # sourced by install.sh/uninstall.sh; vars are used there
# =============================================================================
# scripts/lib.sh — shared library of the nobreak-omarchy kit
#
# Functions used by install.sh and uninstall.sh: colored output, dry-run
# mode, driver metadata loading (drivers/<name>/driver.toml), device lookup
# in sysfs, the "authorized" cycle (USB firmware unwedge), idempotent
# editing of /etc/nut/ups.conf and system helpers (udev group, sbin lookup).
#
# This file is SOURCED by the calling scripts (which set
# `set -euo pipefail`); it does not run anything by itself.
#
# Globals the caller may set (safe defaults here):
#   DRY_RUN     1 = only print what would be done (no root needed)
#   ASSUME_YES  1 = ask no questions (use defaults)
# =============================================================================

# --- Kit paths -------------------------------------------------------------------
KIT_NAME="nobreak-omarchy"
KIT_LIB="/usr/local/lib/nobreak-omarchy"
KIT_ETC="/etc/nobreak-omarchy"
NUT_CONF="/etc/nut/ups.conf"
GUARDIAN_UNIT="nobreak-guardian.service"
GUARDIAN_UNIT_DST="/etc/systemd/user/$GUARDIAN_UNIT"
AUTOHEAL_BIN="/usr/local/sbin/nobreak-autoheal"
AUTOHEAL_ENV="$KIT_ETC/autoheal.env"
AUTOHEAL_SERVICE="nobreak-autoheal.service"
AUTOHEAL_TIMER="nobreak-autoheal.timer"

# --- Globals with defaults -------------------------------------------------------
DRY_RUN=${DRY_RUN:-0}
ASSUME_YES=${ASSUME_YES:-0}

# --- Colored output (off when not a tty or NO_COLOR is set) ----------------------
if [[ -t 1 && -z ${NO_COLOR:-} ]]; then
    C_G=$'\e[32m' C_Y=$'\e[33m' C_R=$'\e[31m' C_B=$'\e[1m' C_C=$'\e[36m' C_0=$'\e[0m'
else
    C_G='' C_Y='' C_R='' C_B='' C_C='' C_0=''
fi

ok()   { printf '%s[ OK ]%s %s\n'  "$C_G" "$C_0" "$*"; }
warn() { printf '%s[WARN]%s %s\n'  "$C_Y" "$C_0" "$*"; }
err()  { printf '%s[FAIL]%s %s\n'  "$C_R" "$C_0" "$*" >&2; }
info() { printf '       %s\n' "$*"; }
step() { printf '\n%s==>%s %s\n' "$C_B" "$C_0" "$*"; }
die()  { err "$*"; exit 1; }

# --- Root / dry-run ----------------------------------------------------------------

have_root() { [[ ${EUID:-$(id -u)} -eq 0 ]]; }

# Requires root, except in dry-run (planning mode with no side effects).
require_root_or_dry() {
    if (( DRY_RUN )); then
        have_root || info "(dry-run: continuing WITHOUT root; nothing will be changed)"
        return 0
    fi
    have_root || die "this operation needs root — run it with sudo (or use --dry-run to simulate)."
}

# run CMD... — runs the command; in dry-run only prints it.
run() {
    if (( DRY_RUN )); then
        printf '%s[dry ]%s %s\n' "$C_C" "$C_0" "$*"
    else
        "$@"
    fi
}

# write_file DEST [MODE] — writes stdin to DEST; in dry-run shows the content.
write_file() {
    local dest=$1 mode=${2:-0644}
    if (( DRY_RUN )); then
        printf '%s[dry ]%s would write %s (mode %s) with:\n' "$C_C" "$C_0" "$dest" "$mode"
        sed 's/^/      | /'
    else
        install -d -m 0755 "$(dirname -- "$dest")"
        cat > "$dest"
        chmod "$mode" "$dest"
        ok "written: $dest"
    fi
}

# ask PROMPT DEFAULT — reads REPLY from the keyboard; with --yes or no tty uses the default.
ask() {
    local prompt=$1 default=$2
    if (( ASSUME_YES )) || ! [[ -t 0 ]]; then
        REPLY=$default
        return 0
    fi
    read -r -p "$prompt [$default]: " REPLY || REPLY=$default
    REPLY=${REPLY:-$default}
}

# --- Drivers -------------------------------------------------------------------------

# toml_get FILE KEY — prints the value of a top-level `key = value` line of a
# simple TOML file (strings unquoted; arrays/booleans printed as written).
toml_get() {
    awk -v k="$2" '
        /^[[:space:]]*\[/ { exit }
        {
            line = $0
            sub(/#.*$/, "", line)
            if (match(line, "^[[:space:]]*" k "[[:space:]]*=")) {
                v = substr(line, RLENGTH + 1)
                gsub(/^[[:space:]]+|[[:space:]]+$/, "", v)
                gsub(/^"|"$/, "", v)
                print v
                exit
            }
        }
    ' "$1"
}

# list_drivers REPO_DIR — prints the available driver names (skips _template).
list_drivers() {
    local d
    for d in "$1"/drivers/*/; do
        d=${d%/}; d=${d##*/}
        [[ $d == _* ]] && continue
        [[ -r $1/drivers/$d/driver.toml ]] && printf '%s\n' "$d"
    done
    return 0
}

# load_driver REPO_DIR NAME — loads drivers/NAME/driver.toml into DRV_* globals
# and derives the per-driver paths/units.
load_driver() {
    local repo=$1 name=$2 toml
    [[ $name =~ ^[a-z0-9][a-z0-9_-]*$ ]] || die "invalid driver name: $name"
    DRIVER_DIR="$repo/drivers/$name"
    toml="$DRIVER_DIR/driver.toml"
    [[ -r $toml ]] || die "unknown driver '$name' (no $toml). Available: $(list_drivers "$repo" | tr '\n' ' ')"
    DRIVER=$name
    DRV_VIDPID="$(toml_get "$toml" vid_pid)"
    [[ $DRV_VIDPID =~ ^[0-9a-fA-F]{4}:[0-9a-fA-F]{4}$ ]] || die "$toml: vid_pid must look like 0001:0000"
    DRV_VID=${DRV_VIDPID%%:*}
    DRV_PID=${DRV_VIDPID##*:}
    DRV_NUT_DRIVER="$(toml_get "$toml" nut_driver)"
    DRV_AUTOHEAL="$(toml_get "$toml" autoheal)"
    DRV_UPS_NAME="$(toml_get "$toml" ups_name)"
    DRV_UPS_NAME=${DRV_UPS_NAME:-nobreak}
    DRV_STATUS="$(toml_get "$toml" status)"
    DRV_NUT_CONF="$DRIVER_DIR/nut/ups.conf"
    DRV_UDEV_SRC="$(find "$DRIVER_DIR/udev" -maxdepth 1 -name '*.rules' 2>/dev/null | head -n1 || true)"
    DRV_UDEV_DST=""
    if [[ -n $DRV_UDEV_SRC ]]; then DRV_UDEV_DST="/etc/udev/rules.d/${DRV_UDEV_SRC##*/}"; fi
    DRV_SCRIPT="$DRIVER_DIR/driver.py"
    INSTALL_DIR="$KIT_LIB/drivers/$name"
    ENV_FILE="/etc/nobreak-$name.env"
    UNIT_STANDALONE="nobreak-$name.service"
    UNIT_MQTT="nobreak-$name-mqtt.service"
}

# --- System ---------------------------------------------------------------------------

# find_bin CMD — finds CMD in PATH or in the common sbin dirs (on Debian/Ubuntu
# the user PATH does not always include /usr/sbin, where upsc/nutdrv_qx live).
# Prints the absolute path; returns 1 if not found.
find_bin() {
    local cmd=$1 p
    if command -v "$cmd" >/dev/null 2>&1; then
        command -v "$cmd"
        return 0
    fi
    for p in /usr/sbin /sbin /usr/bin /bin /usr/local/sbin /usr/local/bin; do
        if [[ -x $p/$cmd ]]; then
            printf '%s\n' "$p/$cmd"
            return 0
        fi
    done
    return 1
}

# find_dev_sysfs — prints the names (e.g. "3-12") of USB devices matching the
# driver's VID/PID in /sys/bus/usb/devices. Empty output = absent.
# (Entries with ":" are interfaces; bus roots have no idVendor.)
find_dev_sysfs() {
    local d
    for d in /sys/bus/usb/devices/*; do
        [[ -r $d/idVendor ]] || continue
        if [[ $(<"$d/idVendor") == "${DRV_VID,,}" && $(<"$d/idProduct") == "${DRV_PID,,}" ]]; then
            printf '%s\n' "${d##*/}"
        fi
    done
    return 0
}

# detect_udev_group — group that gets the device in the udev rule.
# Arch and Debian/Ubuntu create "nut" with the NUT package; some old Debian
# only have "plugdev". Empty if neither exists (the installer creates nut).
detect_udev_group() {
    if getent group nut >/dev/null 2>&1; then
        printf 'nut\n'
    elif getent group plugdev >/dev/null 2>&1; then
        printf 'plugdev\n'
    fi
    return 0
}

# usb_cycle_authorized — UNWEDGE the device's USB firmware.
# Some UPS firmwares (MEC0003 notably) wedge (stop answering control
# transfers) when hammered with the wrong protocol; the recovery without a
# physical replug is de-authorizing and re-authorizing the device in sysfs.
# After the cycle, the MEC0003 answers ZEROS until it is polled at ~1 Hz for a
# few seconds (NUT with pollinterval=2 recovers in ~1 min).
usb_cycle_authorized() {
    local devs dev sys i
    devs="$(find_dev_sysfs)"
    if [[ -z $devs ]]; then
        err "no ${DRV_VIDPID} device found in sysfs — is the UPS plugged in?"
        return 1
    fi
    for dev in $devs; do
        sys="/sys/bus/usb/devices/$dev"
        step "Authorized cycle on $sys"
        if (( DRY_RUN )); then
            info "echo 0 > $sys/authorized ; sleep 1 ; echo 1 > $sys/authorized"
            continue
        fi
        if ! printf '0\n' > "$sys/authorized" 2>/dev/null; then
            err "no write permission on $sys/authorized (needs root)."
            return 1
        fi
        sleep 1
        if ! printf '1\n' > "$sys/authorized" 2>/dev/null; then
            err "FAILED to re-authorize $sys — the device is left DISABLED; run again or replug it physically."
            return 1
        fi
        # Wait for the interfaces to come back (logical re-enumeration).
        for _ in $(seq 1 15); do
            if ls -d "${sys}:"* >/dev/null 2>&1; then
                ok "interfaces re-enumerated at ${sys}:*"
                break
            fi
            sleep 1
        done
        if ! ls -d "${sys}:"* >/dev/null 2>&1; then
            warn "interfaces did not come back within 15s — try a physical replug."
        fi
    done
    warn "after the cycle the chip may answer ZEROS until it is polled at ~1 Hz for a few seconds (with pollinterval=2 NUT settles in ~1 min)."
    return 0
}

# --- /etc/nut/ups.conf -----------------------------------------------------------------

# upsconf_section_text NAME PACKS — prints the driver's PROVEN section from
# drivers/<driver>/nut/ups.conf: comments before the first [section] header
# are dropped, the header becomes [NAME] and `override.battery.packs` (if
# present) is set to PACKS.
upsconf_section_text() {
    local name=$1 packs=$2
    [[ -r $DRV_NUT_CONF ]] || die "driver '$DRIVER' has no NUT config ($DRV_NUT_CONF)."
    printf '# --- section generated by %s install.sh, driver %s (%s) ---\n' "$KIT_NAME" "$DRIVER" "$(date +%Y-%m-%d)"
    awk -v name="$name" -v packs="$packs" '
        !started && /^[[:space:]]*\[/ { started = 1; print "[" name "]"; next }
        !started { next }
        /^[[:space:]]*\[/ { exit }
        packs != "" && /^[[:space:]]*override\.battery\.packs[[:space:]]*=/ {
            print "    override.battery.packs = " packs; next
        }
        { print }
    ' "$DRV_NUT_CONF"
}

# upsconf_without_section FILE SECTION — reprints the file without the
# [SECTION] (header + body up to the next header). Global directives at the
# top are kept.
upsconf_without_section() {
    awk -v sec="$2" '
        BEGIN { keep = 1 }
        /^[[:space:]]*\[/ {
            line = $0
            sub(/^[[:space:]]*\[/, "", line)
            sub(/\].*$/, "", line)
            keep = (line != sec)
        }
        keep { print }
    ' "$1"
}

# upsconf_show_section FILE SECTION — prints the existing section (or nothing).
upsconf_show_section() {
    awk -v sec="$2" '
        /^[[:space:]]*\[/ {
            line = $0
            sub(/^[[:space:]]*\[/, "", line)
            sub(/\].*$/, "", line)
            insec = (line == sec)
            if (insec) print $0
            next
        }
        insec { print }
    ' "$1" 2>/dev/null || true
}

# backup_file FILE — timestamped copy (only if it exists and not in dry-run).
backup_file() {
    local f=$1
    if (( DRY_RUN )); then
        printf '%s[dry ]%s cp -a %s %s.bak.<timestamp>\n' "$C_C" "$C_0" "$f" "$f"
        return 0
    fi
    if [[ -e $f ]]; then
        local ts
        ts=$(date +%Y%m%d-%H%M%S)
        cp -a "$f" "$f.bak.$ts"
        ok "backup: $f.bak.$ts"
    fi
    return 0
}

# battery_packs 12|24 -> 6|12 (1 cell = 2 V nominal; MEC0003 reports per cell).
battery_packs() {
    case $1 in
        12) echo 6 ;;
        24) echo 12 ;;
        *)  return 1 ;;
    esac
}

# --- User services (guardian) ------------------------------------------------------------

# as_desktop_user CMD... — runs CMD as the user who invoked sudo, with their
# systemd --user bus. Returns 1 if there is no such user.
as_desktop_user() {
    local u=${SUDO_USER:-} uid
    [[ -n $u && $u != root ]] || return 1
    uid=$(id -u "$u") || return 1
    run runuser -u "$u" -- env XDG_RUNTIME_DIR="/run/user/$uid" \
        DBUS_SESSION_BUS_ADDRESS="unix:path=/run/user/$uid/bus" "$@"
}
