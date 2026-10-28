# =============================================================================
# scripts/lib.sh — biblioteca compartilhada do kit nobreak-mec0003
#
# Propósito: funções usadas por install.sh e uninstall.sh — saída colorida,
# modo dry-run, detecção do chip MEC0003 no sysfs, ciclo "authorized"
# (destravamento do firmware USB), manipulação idempotente do /etc/nut/ups.conf
# e utilidades de sistema (grupo udev, busca de binários em sbin).
#
# Este arquivo é SOURCED pelos scripts chamadores (que definem
# `set -euo pipefail`); não executa nada sozinho.
#
# Globals configuráveis pelo chamador (com defaults seguros aqui):
#   DRY_RUN     1 = apenas imprimir o que seria feito (não exige root)
#   ASSUME_YES  1 = não fazer perguntas (usa defaults)
# =============================================================================

# --- Constantes do hardware e caminhos do kit --------------------------------
MEC_VID="0001"
MEC_PID="0000"
MEC_PRODUCT="MEC0003"

NUT_CONF="/etc/nut/ups.conf"
INSTALL_DIR="/usr/local/lib/nobreak-mec0003"
ENV_FILE="/etc/nobreak-mec0003.env"
UDEV_RULE_SRC_NAME="99-nobreak-mec0003.rules"
UDEV_RULE_DST="/etc/udev/rules.d/99-nobreak-mec0003.rules"
UNIT_STANDALONE="nobreak-mec0003.service"
UNIT_MQTT="nobreak-mec0003-mqtt.service"

# --- Globals com defaults ------------------------------------------------------
DRY_RUN=${DRY_RUN:-0}
ASSUME_YES=${ASSUME_YES:-0}

# --- Saída colorida (desliga se não for tty ou NO_COLOR estiver definido) ------
if [[ -t 1 && -z ${NO_COLOR:-} ]]; then
    C_G=$'\e[32m' C_Y=$'\e[33m' C_R=$'\e[31m' C_B=$'\e[1m' C_C=$'\e[36m' C_0=$'\e[0m'
else
    C_G='' C_Y='' C_R='' C_B='' C_C='' C_0=''
fi

ok()   { printf '%s[ OK ]%s %s\n'  "$C_G" "$C_0" "$*"; }
warn() { printf '%s[AVISO]%s %s\n' "$C_Y" "$C_0" "$*"; }
err()  { printf '%s[ERRO]%s %s\n'  "$C_R" "$C_0" "$*" >&2; }
info() { printf '       %s\n' "$*"; }
step() { printf '\n%s==>%s %s\n' "$C_B" "$C_0" "$*"; }
die()  { err "$*"; exit 1; }

# --- Root / dry-run ------------------------------------------------------------

have_root() { [[ ${EUID:-$(id -u)} -eq 0 ]]; }

# Exige root, exceto em dry-run (modo de planejamento sem efeitos colaterais).
require_root_or_dry() {
    if (( DRY_RUN )); then
        have_root || info "(dry-run: seguindo SEM root; nada será alterado)"
        return 0
    fi
    have_root || die "esta operação precisa de root — rode com sudo (ou em --dry-run para simular)."
}

# run CMD... — executa o comando; em dry-run apenas imprime.
run() {
    if (( DRY_RUN )); then
        printf '%s[dry ]%s %s\n' "$C_C" "$C_0" "$*"
    else
        "$@"
    fi
}

# write_file DEST [MODO] — escreve stdin em DEST; em dry-run mostra o conteúdo.
write_file() {
    local dest=$1 mode=${2:-0644}
    if (( DRY_RUN )); then
        printf '%s[dry ]%s escreveria %s (modo %s) com o conteúdo:\n' "$C_C" "$C_0" "$dest" "$mode"
        sed 's/^/      | /'
    else
        cat > "$dest"
        chmod "$mode" "$dest"
        ok "escrito: $dest"
    fi
}

# ask PROMPT DEFAULT — lê REPLY do teclado; com --yes ou sem tty usa o default.
ask() {
    local prompt=$1 default=$2
    if (( ASSUME_YES )) || ! [[ -t 0 ]]; then
        REPLY=$default
        return 0
    fi
    read -r -p "$prompt [$default]: " REPLY || REPLY=$default
    REPLY=${REPLY:-$default}
}

# --- Sistema --------------------------------------------------------------------

# find_bin CMD — acha CMD no PATH ou nos diretórios de sbin comuns (em
# Debian/Ubuntu o PATH de usuário nem sempre inclui /usr/sbin, onde vivem
# upsc/nutdrv_qx). Imprime o caminho absoluto; retorna 1 se não achar.
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

# find_mec_sysfs — imprime os nomes (ex.: "3-12") dos dispositivos USB com
# VID/PID do MEC0003 presentes em /sys/bus/usb/devices. Saída vazia = ausente.
# (Entradas com ":" são interfaces; raízes de barramento não têm idVendor.)
find_mec_sysfs() {
    local d
    for d in /sys/bus/usb/devices/*; do
        [[ -r $d/idVendor ]] || continue
        if [[ $(<"$d/idVendor") == "$MEC_VID" && $(<"$d/idProduct") == "$MEC_PID" ]]; then
            printf '%s\n' "${d##*/}"
        fi
    done
    return 0
}

# detect_udev_group — grupo que vai receber o dispositivo na regra udev.
# Arch e Debian/Ubuntu criam o grupo "nut" junto com o pacote NUT; alguns
# Debian antigos só têm "plugdev". Vazio se nenhum existir (o instalador cria).
detect_udev_group() {
    if getent group nut >/dev/null 2>&1; then
        printf 'nut\n'
    elif getent group plugdev >/dev/null 2>&1; then
        printf 'plugdev\n'
    fi
    return 0
}

# usb_cycle_authorized — DESTRAVAMENTO do firmware USB do chip MEC0003.
# O firmware trava (para de responder control transfers) se for bombardeado
# com o protocolo errado; a recuperação sem replug físico é desautorizar e
# reautorizar o dispositivo via sysfs. Depois do ciclo o chip responde ZEROS
# até rodar polling ~1Hz por alguns segundos (o NUT com pollinterval=2
# recupera em ~1 min).
usb_cycle_authorized() {
    local devs dev sys i
    devs="$(find_mec_sysfs)"
    if [[ -z $devs ]]; then
        err "nenhum dispositivo ${MEC_VID}:${MEC_PID} encontrado no sysfs — o nobreak está plugado?"
        return 1
    fi
    for dev in $devs; do
        sys="/sys/bus/usb/devices/$dev"
        step "Ciclo authorized em $sys"
        if (( DRY_RUN )); then
            info "echo 0 > $sys/authorized ; sleep 1 ; echo 1 > $sys/authorized"
            continue
        fi
        if ! printf '0\n' > "$sys/authorized" 2>/dev/null; then
            err "sem permissão de escrita em $sys/authorized (precisa de root)."
            return 1
        fi
        sleep 1
        if ! printf '1\n' > "$sys/authorized" 2>/dev/null; then
            err "FALHOU ao reautorizar $sys — o dispositivo ficou DESATIVADO; rode novamente ou faça replug físico."
            return 1
        fi
        # Aguarda as interfaces HID reaparecerem (reenumeração lógica).
        for i in $(seq 1 15); do
            if ls -d "${sys}:"* >/dev/null 2>&1; then
                ok "interfaces reenumeradas em ${sys}:*"
                break
            fi
            sleep 1
        done
        if ! ls -d "${sys}:"* >/dev/null 2>&1; then
            warn "interfaces não reapareceram em 15s — tente replug físico."
        fi
    done
    warn "após o ciclo, o chip responde ZEROS até haver polling ~1Hz por alguns segundos (com pollinterval=2 o NUT normaliza em ~1 min)."
    return 0
}

# --- /etc/nut/ups.conf -----------------------------------------------------------

# upsconf_section_text NOME PACKS — imprime a seção PROVADA (nutdrv_qx +
# subdriver hunnox + protocolo q1, vide docs/capturas/2026-10-28). O
# battery.voltage do chip vem POR CÉLULA (~2.22V float) → battery.packs
# converte: 12V → 6, 24V → 12.
upsconf_section_text() {
    local name=$1 packs=$2
    printf '# --- seção gerada pelo install.sh do nobreak-mec0003 (%s) ---\n' "$(date +%Y-%m-%d)"
    printf '[%s]\n' "$name"
    printf '    driver = nutdrv_qx\n'
    printf '    port = auto\n'
    printf '    vendorid = %s\n' "$MEC_VID"
    printf '    productid = %s\n' "$MEC_PID"
    printf '    product = %s\n' "$MEC_PRODUCT"
    printf '    subdriver = hunnox\n'
    printf '    protocol = q1\n'
    printf '    langid_fix = 0x0409\n'
    printf '    noscanlangid\n'
    printf '    pollinterval = 2\n'
    printf '    battery.packs = %s\n' "$packs"
}

# upsconf_without_section ARQUIVO SECAO — reimprime o arquivo sem a seção
# [SECAO] (cabeçalho + corpo até o próximo cabeçalho). Diretivas globais no
# topo são preservadas.
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

# upsconf_show_section ARQUIVO SECAO — imprime a seção existente (ou nada).
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

# backup_file ARQUIVO — cópia timestampada (só se existir e não estiver em dry-run).
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

# battery_packs 12|24 → 6|12 (1 célula = 2V nominal; tensão vem por célula).
battery_packs() {
    case $1 in
        12) echo 6 ;;
        24) echo 12 ;;
        *)  return 1 ;;
    esac
}
