#!/usr/bin/env python3
"""
mec0003.py (v2) — driver standalone para nobreaks com chip USB genérico
MEC0003 (VID:PID 0001:0000, "Fry's Electronics" no lsusb — marcas SMS, NHS,
Powercool, Hunnox, DEXP, Eurocase etc.)

Protocolo documentado a partir de:
  * engenharia reversa do cliente Windows UPSmart (modo "MEGA(USB)") refletida
    nos subdrivers hunnox/krauler/fabula do NUT (nutdrv_qx.c)
  * issues networkupstools/nut#1539 e #2208 (comportamento do firmware)
  * smsUps/nobreakSMS (protocolo binário serial SMS para o modo serial)
  * capturas ao vivo em hardware real (2026-10-28) — ver tests/frames/

Idiossincrasias de firmware (aprendidas com hardware real — RESPEITAR):
  * battery_voltage do Q1 vem POR CÉLULA (~2,22 V em flutuação): multiplicar
    pelo número de elementos da bateria — 6 para bateria de 12 V,
    12 para bateria de 24 V.
  * alguns firmwares reportam frequência de entrada FIXA em 50.0 Hz
    (ignorar o valor para lógica de decisão, é cosmético).
  * após replug / ciclo USB o dispositivo responde ZEROS até o lock-step de
    aquecimento completar: pollar a ~1 Hz por alguns segundos até os
    valores ficarem vivos (o aquecimento já roda no StringChannel, mas as
    primeiras leituras seguintes ainda podem vir zeradas).

Métodos de acesso (o auto tenta nesta ordem):
  1. string    — comandos embarcados em GET_DESCRIPTOR(String): o índice da
                 string É o opcode (Q1=0x03, F=0x0d, I=0x0c, BL=0xf3...),
                 langid fixo 0x0409, wLength no máx 102 (maior trava o chip).
  2. setreport — túnel HID: comando ASCII em report de saída de 8 bytes via
                 SET_REPORT (0x21/0x09/0x0200), resposta no endpoint 0x81.
  3. serial    — protocolo binário SMS 2400 8N1 (7 bytes cmd / 18 bytes
                 resposta) em /dev/ttyUSB*, se o cabo criar porta serial.

Dependências (extras opcionais não são obrigatórias para o uso básico):
  pip install pyusb pyserial hidapi     # núcleo (ver requirements.txt)
  pip install paho-mqtt                 # só para --mqtt / --daemon com MQTT

Saídas: 0 ok, 1 erro de dispositivo/protocolo, 2 dependência opcional ausente.
"""

import argparse
import glob
import json
import os
import signal
import sys
import time

__version__ = "2.0.0"

VID = 0x0001
PID = 0x0000
LANGID = 0x0409          # langid fixo: a negociação padrão trava o firmware
MAX_STRING_LEN = 102     # wLength > 102 trava o chip (medido do cliente Windows)


class UpsError(Exception):
    """Erro de dispositivo/protocolo (código de saída 1)."""


class MissingDependency(Exception):
    """Dependência opcional ausente, ex.: paho-mqtt (código de saída 2)."""


# ---------------------------------------------------------------------------
# Camada 1 — canais de comando (detalhes de protocolo são SAGRADOS,
# reverse-engineered e verificados contra hardware real — não mexer nos bytes)
# ---------------------------------------------------------------------------

# ---------- Método "string" (modo MEGA(USB) do UPSmart / hunnox-krauler) ----

# Índice de string = opcode do comando Megatec
STRING_INDEX = {
    "Q1": 0x03,   # status completo (ASCII "(226.0 195.0 ...")
    "F":  0x0d,   # nominal
    "I":  0x0c,   # fabricante/modelo/firmware
    "Q":  0x07,   # alterna o bip
    "C":  0x0a,   # cancela desligamento
    "T":  0x04,   # teste de bateria (10 s)
    "TL": 0x05,   # teste até bater baixa
    "BL": 0xf3,   # carga da bateria em % (dialeto hunnox)
}
# 0x68/0x69 existem na tabela krauler mas causam desligamento — nunca usar.
FORBIDDEN_INDEXES = {0x68, 0x69}


class StringChannel:
    """Comandos Megatec tunelados em descritores de string USB."""

    name = "string"
    needs_usb = True

    def __init__(self, dev):
        self.dev = dev
        self.warmed = False
        self.step = 1          # lock-step do UPSmart: intercala F/Q1/I
        # aquecimento: sem isso o firmware responde zeros (NUT#2208)
        for _ in range(2):
            self._raw_string(0x00, 1026, required=False)
        self._raw_string(0x01, 1026, required=False)
        time.sleep(0.01)
        self.warmed = True

    def _raw_string(self, index, wlength, required=True):
        r = self.dev.ctrl_transfer(0x80, 0x06, (0x03 << 8) | index,
                                   LANGID, wlength, 5000)
        if r is None or len(r) == 0:
            if required:
                raise UpsError(f"string 0x{index:02x}: sem resposta")
            return b""
        return bytes(r)

    def _get_string(self, index):
        if index in FORBIDDEN_INDEXES:
            raise UpsError(f"índice 0x{index:02x} é perigoso (desliga o nobreak)")
        raw = self._raw_string(index, MAX_STRING_LEN)
        if len(raw) < 2 or raw[1] != 0x03:
            raise UpsError(f"string 0x{index:02x}: descritor inválido "
                           f"{raw[:4].hex()}")
        if raw[0] != len(raw):
            raise UpsError(f"string 0x{index:02x}: tamanho divergente "
                           f"({raw[0]} != {len(raw)})")
        # UTF-16LE -> ASCII (1 byte a cada 2, a partir do offset 2)
        return raw[2:raw[0]:2].decode("ascii", "replace").rstrip("\r\n\x00")

    def _dummy(self, asking_index):
        # o UPSmart intercala leituras F/Q1/I entre comandos reais para
        # manter os valores vivos; pulamos a que estamos pedindo de verdade
        for idx in (0x0d, 0x03, 0x0c):
            if idx != asking_index:
                try:
                    self._get_string(idx)
                except Exception:
                    pass
                return

    def query(self, cmd):
        idx = STRING_INDEX[cmd]
        if self.warmed:
            self._dummy(idx)
        return self._get_string(idx)


# ---------- Método "setreport" (túnel HID clássico Megatec/cypress) --------

class SetReportChannel:
    """Comando ASCII em report de 8 bytes via SET_REPORT; resposta no EP 0x81."""

    name = "setreport"
    needs_usb = True

    def __init__(self, dev):
        self.dev = dev

    def query(self, cmd):
        payload = (cmd + "\r").encode("ascii")[:8]
        payload = payload + b"\x00" * (8 - len(payload))
        self.dev.ctrl_transfer(0x21, 0x09, 0x0200, 0, payload, 5000)
        out = b""
        deadline = time.time() + 3.0
        while time.time() < deadline and len(out) < 128:
            try:
                chunk = self.dev.read(0x81, 8, 1000)
            except Exception:
                break
            if not chunk:
                continue
            out += bytes(chunk)
            if b"\r" in out:
                break
        s = out.decode("ascii", "replace").strip("\r\n\x00")
        if s.upper() == "UPS NO ACK":
            return ""
        return s


# ---------- Método "serial" (protocolo binário SMS) -------------------------

def sms_checksum(body):
    """Checksum aditivo do protocolo SMS: (0x100 - soma(bytes)) & 0xFF.

    `body` são os 5 primeiros bytes do pacote (letra + 4 args); o pacote
    completo tem 7 bytes: body + checksum + 0x0D (ver docs/PROTOCOLO.md §1.2).
    """
    return (0x100 - (sum(body) & 0xFF)) & 0xFF


def build_sms_frame(cmd, args_bytes=b"\xff\xff\xff\xff"):
    """Monta pacote de 7 bytes: [cmd][4 args][checksum][0x0D]."""
    body = bytes([cmd]) + bytes(args_bytes)
    return body + bytes([sms_checksum(body), 0x0D])


# Bytes literais mantidos da v1 (verificados em hardware; o --selftest
# confere que continuam idênticos ao recalculados por build_sms_frame).
SMS_CMDS = {
    "Q":  bytes.fromhex("51 ff ff ff ff b3 0d"),
    "I":  bytes.fromhex("49 ff ff ff ff bb 0d"),
    "F":  bytes.fromhex("46 ff ff ff ff be 0d"),
}


def parse_sms_status(raw):
    """Parser da resposta de 18 bytes do comando Q (protocolo binário SMS).

    Layout documentado em docs/PROTOCOLO.md §1.4 (capturas reais):
    offset 1-14 são 7 u16 big-endian ÷ 10; offset 15 = bits de estado;
    offset 17 = terminador 0x0D. Bits de estado: bit0 beep, bit6 bateria
    baixa, bit7 em bateria (0x09 = normal, 0x89 = fora da tomada).
    """
    raw = bytes(raw)
    if len(raw) < 18:
        raise UpsError(f"resposta SMS curta ({len(raw)} bytes): {raw.hex()}")
    if raw[0] != 0x3D:
        raise UpsError(f"marcador SMS inválido: 0x{raw[0]:02x}")
    if raw[17] != 0x0D:
        raise UpsError(f"terminador SMS inválido: 0x{raw[17]:02x}")
    u16 = lambda i: (raw[i] << 8) | raw[i + 1]
    st = raw[15]
    return {
        "input_voltage_last": u16(1) / 10,
        "input_voltage": u16(3) / 10,
        "output_voltage": u16(5) / 10,
        "load_percent": u16(7) / 10,
        "output_frequency_hz": u16(9) / 10,
        "battery_charge_percent": u16(11) / 10,
        "temperature_c": u16(13) / 10,
        "bits": {
            "beeper_on": bool(st & 0x01), "shutdown_active": bool(st & 0x02),
            "test_active": bool(st & 0x04), "ups_ok": bool(st & 0x08),
            "boost": bool(st & 0x10), "bypass": bool(st & 0x20),
            "battery_low": bool(st & 0x40), "on_battery": bool(st & 0x80),
        },
    }


class SmsSerialChannel:
    """Protocolo binário SMS: 2400 8N1, cmd 7 bytes, resposta 18 bytes."""

    name = "serial"
    needs_usb = False

    def __init__(self, port):
        import serial  # pyserial
        self.ser = serial.Serial(port, 2400, bytesize=8, parity="N",
                                 stopbits=1, timeout=3)

    def _send(self, frame):
        # firmware prefere bytes espaçados (dmslabsbr/smsUps usa 100 ms)
        for b in frame:
            self.ser.write(bytes([b]))
            self.ser.sleep(0.1) if hasattr(self.ser, "sleep") else time.sleep(0.1)

    def query(self, cmd):
        self.ser.reset_input_buffer()
        frame = SMS_CMDS.get(cmd)
        if frame is None:
            raise UpsError(f"comando {cmd} não mapeado no modo serial")
        self._send(frame)
        raw = self.ser.read(18)
        if len(raw) < 18 or raw[0] != 0x3D or raw[17] != 0x0D:
            raise UpsError(f"resposta serial inválida: {raw.hex()}")
        return raw  # binário; parser específico acima

    def status(self):
        d = parse_sms_status(self.query("Q"))
        # deriva ups_status no mesmo dialeto do Q1 (OB/OL + LB) para o
        # formato de saída e para o sensor MQTT ficarem uniformes
        d["ups_status"] = montar_ups_status(
            d["bits"]["on_battery"], d["bits"]["battery_low"],
            boost=d["bits"]["boost"])
        return d


# ---------------------------------------------------------------------------
# Camada 2 — parsers do dialeto Megatec ASCII (chaves do dict SÃO ESTÁVEIS:
# são consumidas por JSON/MQTT/NUT — não renomear, não reordenar valores)
# ---------------------------------------------------------------------------

def montar_ups_status(em_bateria, bateria_baixa, boost=False, falha=False,
                      teste=False):
    """Mapeia flags para o dialeto NUT: OB/OL + LB (+BOOST/ALARM/TEST).

    utility_fail → "OB" (on battery), senão "OL" (on line); acrescenta
    "LB" se battery_low. Ordem idêntica à v1 — JSON é consumido externamente.
    """
    st = []
    st.append("OB" if em_bateria else "OL")
    if bateria_baixa:
        st.append("LB")
    if boost:
        st.append("BOOST")
    if falha:
        st.append("ALARM")
    if teste:
        st.append("TEST")
    return " ".join(st)


def parse_q1(s):
    """(226.0 195.0 226.0 014 49.0 27.5 30.0 00001000

    QUIRK: battery_voltage vem POR CÉLULA (~2,22 V em flutuação) — multiplique
    pelo número de elementos (6 p/ bateria 12 V, 12 p/ 24 V).
    QUIRK: alguns firmwares reportam input_frequency_hz fixa em 50.0.
    """
    if len(s) < 46 or not s.startswith("("):
        raise UpsError(f"Q1 malformado: {s!r}")
    flags = s[38:46]
    out = {
        "input_voltage": float(s[1:6]),
        "input_voltage_fault": float(s[7:12]),
        "output_voltage": float(s[13:18]),
        "load_percent": float(s[19:22]),
        "input_frequency_hz": float(s[23:27]),
        "battery_voltage": float(s[28:32]),
        "temperature_c": float(s[33:37]),
        "flags": {
            "utility_fail": flags[0] == "1",
            "battery_low": flags[1] == "1",
            "bypass_or_boost": flags[2] == "1",
            "ups_failed": flags[3] == "1",
            "test_in_progress": flags[5] == "1",
            "shutdown_active": flags[6] == "1",
            "beeper_on": flags[7] == "1",
        },
    }
    out["ups_status"] = montar_ups_status(
        out["flags"]["utility_fail"], out["flags"]["battery_low"],
        boost=out["flags"]["bypass_or_boost"],
        falha=out["flags"]["ups_failed"],
        teste=out["flags"]["test_in_progress"])
    return out


def parse_f(s):
    """#220.0 000 024.0 50.0  -> nominal de entrada, corrente, bateria, frequência"""
    p = s.strip("#").split()
    return {
        "nominal_input_voltage": float(p[0]),
        "nominal_current_a": float(p[1]),
        "nominal_battery_voltage": float(p[2]),
        "nominal_frequency_hz": float(p[3]),
    }


def parse_i(s):
    """#-------------   ------     VT12046Q  -> fabricante, modelo, firmware"""
    p = s.strip("#").split()
    return {
        "manufacturer": p[0] if len(p) > 0 else "?",
        "model": p[1] if len(p) > 1 else "?",
        "firmware": p[2] if len(p) > 2 else "?",
    }


def parse_bl(s):
    """BL85 -> carga da bateria em %"""
    if not s.upper().startswith("BL"):
        raise UpsError(f"BL malformado: {s!r}")
    return int(s[2:])


# ---------------------------------------------------------------------------
# Camada 3 — abertura do dispositivo e recuperação de travamento USB
# ---------------------------------------------------------------------------

def open_usb():
    try:
        import usb.core
        import usb.util
    except ImportError as e:
        raise UpsError(f"pyusb não instalado (pip install pyusb): {e}") from e
    try:
        dev = usb.core.find(idVendor=VID, idProduct=PID)
    except usb.core.NoBackendError as e:
        raise UpsError("libusb não encontrada (instale o pacote libusb do "
                       "sistema)") from e
    if dev is None:
        raise UpsError("nobreak não encontrado no USB (0001:0000). "
                       "Ele está ligado e o cabo conectado?")
    try:
        try:
            if dev.is_kernel_driver_active(0):
                dev.detach_kernel_driver(0)   # tira o usbhid da frente
        except NotImplementedError:
            pass
        try:
            dev.get_active_configuration()
        except Exception:
            dev.set_configuration()
        usb.util.claim_interface(dev, 0)
    except usb.core.USBError as e:
        # típico sem root: o dispositivo existe mas o udev não deu permissão
        raise UpsError(f"sem acesso ao USB ({e}) — rode como root ou instale "
                       "a regra udev do repositório (diretório udev/)") from e
    return dev


def make_channel(method, port):
    if method == "serial":
        return SmsSerialChannel(port)
    dev = open_usb()
    if method == "string":
        return StringChannel(dev)
    if method == "setreport":
        return SetReportChannel(dev)
    # auto: string é o que o UPSmart usa nesses chips
    return StringChannel(dev)


def sysfs_reauthorize(log):
    """Recuperação de chip travado: ciclo 'authorized' 0->1 via sysfs.

    Só funciona como root (sysfs de USB é write-protected para usuário).
    Gravação envolvida em try/except — só escreve se o arquivo estiver
    gravável. Após o ciclo o dispositivo reenumera: o canal reaberto passa
    pelo aquecimento e o firmware ainda pode responder zeros nos primeiros
    segundos (~1 Hz até estabilizar — quirk documentado no cabeçalho).
    """
    if os.geteuid() != 0:
        log("dica: sem root não é possível ciclar "
            "/sys/bus/usb/devices/*/authorized — reconecte o cabo USB ou "
            "rode o serviço como root")
        return False
    ciclado = False
    for auth in glob.glob("/sys/bus/usb/devices/*/authorized"):
        base = os.path.dirname(auth)
        try:
            with open(os.path.join(base, "idVendor")) as f:
                vid = f.read().strip()
            with open(os.path.join(base, "idProduct")) as f:
                pid = f.read().strip()
        except OSError:
            continue
        if vid != "0001" or pid != "0000":
            continue  # só mexe no dispositivo do nobreak
        try:
            with open(auth, "w") as f:
                f.write("0")
            time.sleep(1.0)
            with open(auth, "w") as f:
                f.write("1")
            ciclado = True
            log(f"USB ciclado em {base}, aguardando reenumeracao")
        except OSError as e:
            log(f"sysfs nao gravavel ({auth}): {e}")
    return ciclado


# ---------------------------------------------------------------------------
# Camada 4 — ponte MQTT / Home Assistant (paho-mqtt é OPCIONAL)
# ---------------------------------------------------------------------------

# Entidades publicadas via MQTT Discovery. `chave` é a chave do JSON de
# estado publicado em --mqtt-topic (as chaves são estáveis — ver parse_q1).
DISCOVERY_SENSORS = (
    {"id": "input_voltage", "nome": "Nobreak tensao de entrada",
     "chave": "input_voltage", "unit": "V", "device_class": "voltage"},
    {"id": "output_voltage", "nome": "Nobreak tensao de saida",
     "chave": "output_voltage", "unit": "V", "device_class": "voltage"},
    {"id": "load", "nome": "Nobreak carga",
     "chave": "load_percent", "unit": "%", "icon": "mdi:gauge"},
    {"id": "battery_charge", "nome": "Nobreak bateria",
     "chave": "battery_charge_percent", "unit": "%", "device_class": "battery"},
    # ups_status já vem no dialeto NUT: "OL" na rede, "OB" em bateria,
    # "LB" bateria baixa (mapeamento feito em montar_ups_status)
    {"id": "ups_status", "nome": "Nobreak status",
     "chave": "ups_status", "icon": "mdi:power-plug"},
    {"id": "temperature", "nome": "Nobreak temperatura",
     "chave": "temperature_c", "unit": "°C", "device_class": "temperature"},
)

DEVICE_INFO = {
    "identifiers": ["nobreak_mec0003"],
    "name": "Nobreak (MEC0003)",
    "manufacturer": "SMS/NHS/generico",
    "model": "MEC0003 (0001:0000)",
}


def split_broker(broker):
    """'host' ou 'host:porta' -> (host, porta); porta padrão 1883."""
    if ":" in broker:
        host, porta = broker.rsplit(":", 1)
        return host, int(porta)
    return broker, 1883


class MqttBridge:
    """Publica o estado JSON + configs de discovery do Home Assistant.

    paho-mqtt é importado AQUI dentro (opcional): os modos sem --mqtt
    nunca exigem a biblioteca.
    """

    def __init__(self, broker, state_topic):
        try:
            import paho.mqtt.client as mqtt
        except ImportError as e:
            raise MissingDependency(
                "paho-mqtt nao esta instalado (necessario apenas para --mqtt): "
                f"{e}") from e
        host, port = split_broker(broker)
        # compativel com paho 1.x e 2.x
        try:
            self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2,
                                      client_id="mec0003")
        except AttributeError:
            self.client = mqtt.Client(client_id="mec0003")
        self.state_topic = state_topic
        self.client.on_connect = self._on_connect
        self.client.connect(host, port, keepalive=30)
        self.client.loop_start()

    def _on_connect(self, client, userdata, *args):
        # (re)publica o discovery a cada reconexão ao broker
        self.publish_discovery()

    def publish_discovery(self):
        for cfg in DISCOVERY_SENSORS:
            payload = {
                "name": cfg["nome"],
                "state_topic": self.state_topic,
                "value_template": "{{ value_json." + cfg["chave"] + " }}",
                "unique_id": "mec0003_" + cfg["id"],
                "device": DEVICE_INFO,
            }
            if "unit" in cfg:
                payload["unit_of_measurement"] = cfg["unit"]
            if "device_class" in cfg:
                payload["device_class"] = cfg["device_class"]
            if "icon" in cfg:
                payload["icon"] = cfg["icon"]
            if cfg["chave"] != "ups_status":
                payload["state_class"] = "measurement"
            topic = "homeassistant/sensor/nobreak_mec0003/" + cfg["id"] + "/config"
            self.client.publish(topic, json.dumps(payload, ensure_ascii=False),
                                qos=1, retain=True)

    def publish_state(self, status):
        self.client.publish(self.state_topic,
                            json.dumps(status, ensure_ascii=False),
                            qos=1, retain=True)


# ---------------------------------------------------------------------------
# Camada 5 — formatação, selftest e CLI
# ---------------------------------------------------------------------------

def fmt_status(d):
    freq = d.get("input_frequency_hz", d.get("output_frequency_hz", 0.0))
    if "battery_voltage" in d:
        # QUIRK: tensao POR CELULA (~2,22 V) — multiplicar pelo n. de
        # elementos (6 p/ 12 V, 12 p/ 24 V) para ter a tensao total
        linha_bat = f"bateria           : {d['battery_voltage']:6.2f} V (por celula)"
    else:
        linha_bat = (f"bateria           : "
                     f"{d.get('battery_charge_percent', 0):3.0f} %")
    lines = [
        f"rede (entrada)    : {d['input_voltage']:6.1f} V  {freq:5.1f} Hz",
        f"saída             : {d['output_voltage']:6.1f} V  carga {d['load_percent']:3.0f}%",
        linha_bat,
        f"temperatura       : {d['temperature_c']:6.1f} °C",
        f"status            : {d.get('ups_status', '?')}",
    ]
    return "\n".join(lines)


# Amostras de hardware real (2026-10-28) — usadas pelo --selftest;
# os testes de CI (tests/test_parsers.py) usam os mesmos frames.
Q1_AMOSTRA_REAL = "(231.2 000.0 219.8 008 50.0 2.22 27.0 00001000"
SMS_Q_AMOSTRA = bytes.fromhex(
    "3d 08 34 08 34 04 38 01 22 02 58 03 e8 01 7c 09 01 0d")


def run_selftest():
    """Checagens sem hardware: parsers, checksums e frames reais."""
    print(f"mec0003 {__version__} --selftest (sem hardware, sem root)")
    falhas = 0

    def check(nome, fn):
        nonlocal falhas
        try:
            fn()
        except Exception as e:
            falhas += 1
            print(f"FALHA  {nome}: {type(e).__name__}: {e}")
            return
        print(f"ok     {nome}")

    def t_q1_real():
        d = parse_q1(Q1_AMOSTRA_REAL)
        assert d["input_voltage"] == 231.2
        assert d["input_voltage_fault"] == 0.0
        assert d["output_voltage"] == 219.8
        assert d["load_percent"] == 8
        assert d["input_frequency_hz"] == 50.0
        assert d["battery_voltage"] == 2.22
        assert d["temperature_c"] == 27.0
        assert d["ups_status"] == "OL"
        assert not any(d["flags"].values())

    def t_q1_flags():
        base = "(231.2 000.0 219.8 008 50.0 2.22 27.0 "
        assert parse_q1(base + "10000000")["ups_status"] == "OB"
        assert parse_q1(base + "11000000")["ups_status"] == "OB LB"
        assert parse_q1(base + "01000000")["ups_status"] == "OL LB"

    def t_f():
        d = parse_f("#220.0 000 024.0 50.0")
        assert d == {"nominal_input_voltage": 220.0, "nominal_current_a": 0.0,
                     "nominal_battery_voltage": 24.0, "nominal_frequency_hz": 50.0}

    def t_i():
        d = parse_i("#SUNTEK  MODEL-X  FW123")
        assert d == {"manufacturer": "SUNTEK", "model": "MODEL-X",
                     "firmware": "FW123"}

    def t_bl():
        assert parse_bl("BL85") == 85
        assert parse_bl("bl100") == 100

    def t_checksum():
        # vetores conhecidos-bons dos comandos reais do protocolo SMS
        assert sms_checksum(bytes.fromhex("51 ff ff ff ff")) == 0xB3
        assert sms_checksum(bytes.fromhex("49 ff ff ff ff")) == 0xBB
        assert sms_checksum(bytes.fromhex("46 ff ff ff ff")) == 0xBE
        assert sms_checksum(bytes.fromhex("54 00 10 00 00")) == 0x9C
        # e os frames da v1 continuam consistentes com o checksum
        assert SMS_CMDS["Q"] == build_sms_frame(0x51)
        assert SMS_CMDS["I"] == build_sms_frame(0x49)
        assert SMS_CMDS["F"] == build_sms_frame(0x46)

    def t_sms_status():
        d = parse_sms_status(SMS_Q_AMOSTRA)
        assert d["input_voltage_last"] == 210.0
        assert d["input_voltage"] == 210.0
        assert d["output_voltage"] == 108.0
        assert d["load_percent"] == 29.0
        assert d["output_frequency_hz"] == 60.0
        assert d["battery_charge_percent"] == 100.0
        assert d["temperature_c"] == 38.0
        assert d["bits"]["beeper_on"] is True
        assert d["bits"]["on_battery"] is False   # 0x09 = normal (0x89 = em bateria)
        # variante em bateria (bit 7)
        ob = parse_sms_status(SMS_Q_AMOSTRA[:15] + b"\x89" + SMS_Q_AMOSTRA[16:])
        assert ob["bits"]["on_battery"] is True

    def t_invalidos():
        for ruim in ("", "XYZ", "(000", "(1.0 2.0 3.0 004 5.0 6.0 7.0 0"):
            try:
                parse_q1(ruim)
            except UpsError:
                pass
            else:
                raise AssertionError(f"parse_q1 aceitou {ruim!r}")
        for ruim in ("", "85", "XX85"):
            try:
                parse_bl(ruim)
            except UpsError:
                pass
            else:
                raise AssertionError(f"parse_bl aceitou {ruim!r}")
        for ruim in (b"", b"\x3d\x00", b"\x3e" + b"\x00" * 17,
                     SMS_Q_AMOSTRA[:17] + b"\x0a"):
            try:
                parse_sms_status(ruim)
            except UpsError:
                pass
            else:
                raise AssertionError(f"parse_sms_status aceitou {ruim!r}")

    check("parse_q1 frame real 2026-10-28", t_q1_real)
    check("parse_q1 mapeamento OB/OL/LB", t_q1_flags)
    check("parse_f nominais", t_f)
    check("parse_i identificacao", t_i)
    check("parse_bl carga", t_bl)
    check("sms_checksum + frames SMS", t_checksum)
    check("parse_sms_status resposta Q", t_sms_status)
    check("frames invalidos rejeitados", t_invalidos)

    if falhas:
        print(f"SELFTEST FALHOU ({falhas} teste(s))")
        return 1
    print("SELFTEST OK")
    return 0


def one_shot(ch, args):
    if args.raw:
        idx = int(args.raw, 16)
        return {"raw": ch._get_string(idx)}
    if args.beeper:
        return {"beeper": ch.query("Q") or "(sem resposta — normal)"}
    if args.test is not None:
        return {"test": ch.query("T") or "(iniciado)"}
    result = {}
    if args.info:
        result.update(parse_i(ch.query("I")))
    if args.ratings:
        result.update(parse_f(ch.query("F")))
    if args.battery:
        result["battery_charge_percent"] = parse_bl(ch.query("BL"))
    if not result or args.watch or args.daemon:
        if ch.name == "serial":
            result.update(ch.status())
        else:
            result.update(parse_q1(ch.query("Q1")))
    return result


def run_loop(args, ch, mqtt):
    """Modo watch/daemon: tolera travamentos e reenumerações do firmware."""
    intervalo = args.watch if args.watch > 0 else args.interval
    erros_seguidos = 0
    was_ob = False

    def log_stderr(msg):
        print(f"[{time.strftime('%H:%M:%S')}] {msg}", file=sys.stderr, flush=True)

    while True:
        try:
            r = one_shot(ch, args)
            erros_seguidos = 0
            # para o sensor de bateria do HA: canal USB consegue BL a cada poll
            if (mqtt is not None and "battery_charge_percent" not in r
                    and ch.name in ("string", "setreport")):
                try:
                    r["battery_charge_percent"] = parse_bl(ch.query("BL"))
                except UpsError:
                    pass
            # daemon é silencioso no stdout (systemd/journal) salvo --verbose
            if not args.daemon or args.verbose:
                saida = (json.dumps(r, ensure_ascii=False) if args.json
                         else fmt_status(r))
                print(saida, flush=True)
            if mqtt is not None:
                mqtt.publish_state(r)
            ob = "OB" in r.get("ups_status", "")
            if ob and not was_ob and "NUT_ON_BATTERY_CMD" in os.environ:
                os.system(os.environ["NUT_ON_BATTERY_CMD"])
            was_ob = ob
        except (KeyboardInterrupt, SystemExit):
            raise
        except Exception as e:
            erros_seguidos += 1
            log_stderr(f"{e}")
            if erros_seguidos >= 3:
                # chip travado de vez: tenta ciclo 'authorized' (só root)
                if sysfs_reauthorize(log_stderr):
                    time.sleep(2.0)
                erros_seguidos = 0
            try:
                ch = make_channel(args.method, args.port)
                # QUIRK: apos reabrir, o firmware responde zeros ate
                # completar o lock-step — algumas leituras a ~1 Hz
                # sao descartadas ate os valores estabilizarem
                for _ in range(3):
                    time.sleep(1.0)
                    try:
                        one_shot(ch, args)
                    except Exception:
                        pass
            except UpsError:
                pass
        time.sleep(intervalo)


EPILOGO = """\
exemplos:
  sudo python3 mec0003.py                      # status unico (Q1)
  sudo python3 mec0003.py --watch 1            # monitor a cada 1 s
  sudo python3 mec0003.py --json --info        # modelo/firmware em JSON
  sudo python3 mec0003.py --beeper             # alterna o bip
  sudo python3 mec0003.py --method serial --port /dev/ttyUSB0
  sudo python3 mec0003.py --daemon --interval 5 --mqtt localhost:1883
                                               # servico (systemd) + Home Assistant
  python3 mec0003.py --selftest                # checagem sem hardware (CI)

codigos de saida: 0 ok | 1 erro de dispositivo/protocolo |
2 dependencia opcional ausente (paho-mqtt)
"""


def montar_parser():
    ap = argparse.ArgumentParser(
        description=__doc__,
        epilog=EPILOGO,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--method", choices=["auto", "string", "setreport", "serial"],
                    default="auto",
                    help="metodo de acesso ao nobreak (padrao: auto)")
    ap.add_argument("--port", default="/dev/ttyUSB0",
                    help="porta serial para --method serial (padrao /dev/ttyUSB0)")
    ap.add_argument("--watch", type=int, metavar="N", default=0,
                    help="monitor continuo, uma leitura a cada N segundos")
    ap.add_argument("--daemon", action="store_true",
                    help="modo servico (systemd): silencioso no stdout a nao "
                         "ser com --verbose; intervalo padrao 5 s (--interval)")
    ap.add_argument("--interval", type=float, metavar="S", default=5.0,
                    help="intervalo do --daemon em segundos (padrao 5)")
    ap.add_argument("--mqtt", metavar="broker[:porta]", default=None,
                    help="publica estado JSON no broker MQTT e cria as "
                         "entidades no Home Assistant (Discovery); tambem via "
                         "env MEC0003_MQTT")
    ap.add_argument("--mqtt-topic", default="home/nobreak/state",
                    help="topico de estado MQTT (padrao home/nobreak/state)")
    ap.add_argument("--json", action="store_true", help="saida em JSON")
    ap.add_argument("--verbose", action="store_true",
                    help="no --daemon, imprime cada leitura no stdout")
    ap.add_argument("--info", action="store_true",
                    help="fabricante/modelo/firmware (I)")
    ap.add_argument("--ratings", action="store_true", help="valores nominais (F)")
    ap.add_argument("--battery", action="store_true", help="carga da bateria %% (BL)")
    ap.add_argument("--beeper", action="store_true", help="alterna o bip (Q)")
    ap.add_argument("--test", type=int, metavar="SEG", help="teste de bateria (T)")
    ap.add_argument("--raw", metavar="IDX",
                    help="le string bruta IDX (hex) — uso avancado")
    ap.add_argument("--selftest", action="store_true",
                    help="autochecagem dos parsers/checksums sem hardware e "
                         "sem root (usado pelo CI)")
    return ap


def _sigterm_handler(signum, frame):
    # systemd encerra com SIGTERM — sai limpo com codigo 0
    raise SystemExit(0)


def main():
    args = montar_parser().parse_args()

    if args.selftest:
        return run_selftest()

    try:
        signal.signal(signal.SIGTERM, _sigterm_handler)
    except (ValueError, OSError):
        pass  # nao estamos na thread principal (ex.: embutido em teste)

    # --mqtt (ou env MEC0003_MQTT): paho-mqtt e OPCIONAL — sai com 2 se faltar
    broker = args.mqtt or os.environ.get("MEC0003_MQTT")
    mqtt = None
    if broker:
        try:
            mqtt = MqttBridge(broker, args.mqtt_topic)
        except MissingDependency as e:
            print(f"ERRO: {e}", file=sys.stderr)
            print("Instale com: pip install paho-mqtt", file=sys.stderr)
            return 2
        except Exception as e:
            print(f"ERRO: MQTT: {e}", file=sys.stderr)
            return 1

    try:
        ch = make_channel(args.method, args.port)
    except UpsError as e:
        print(f"ERRO: {e}", file=sys.stderr)
        return 1

    if not (args.watch or args.daemon):
        try:
            r = one_shot(ch, args)
            if mqtt is not None:
                mqtt.publish_state(r)
            print(json.dumps(r, ensure_ascii=False, indent=2) if args.json
                  else (fmt_status(r) if "ups_status" in r else "\n".join(
                      f"{k:28s}: {v}" for k, v in r.items())))
            return 0
        except UpsError as e:
            print(f"ERRO: {e}", file=sys.stderr)
            return 1

    try:
        run_loop(args, ch, mqtt)
    except (KeyboardInterrupt, SystemExit):
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
