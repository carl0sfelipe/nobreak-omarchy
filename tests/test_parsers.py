"""Testes dos parsers/checksums do driver MEC0003 — sem hardware e sem root.

Os frames usados abaixo vieram de capturas reais (ver tests/frames/README.md);
o frame Q1 foi capturado ao vivo em 2026-10-28 (entrada 231,2 V, saida
219,8 V, carga 8%, 50,0 Hz, bateria 2,22 V por celula, 27,0 C).
"""

import pytest

import mec0003


# ---------------------------------------------------------------------------
# parse_q1 — dialeto Megatec ASCII (canais string/setreport)
# ---------------------------------------------------------------------------

def test_parse_q1_frame_real():
    d = mec0003.parse_q1("(231.2 000.0 219.8 008 50.0 2.22 27.0 00001000")
    assert d["input_voltage"] == 231.2
    assert d["input_voltage_fault"] == 0.0
    assert d["output_voltage"] == 219.8
    assert d["load_percent"] == 8
    assert d["input_frequency_hz"] == 50.0
    # QUIRK: tensao POR CELULA (~2,22 V em flutuacao) — multiplicar por
    # 6 (bateria 12 V) ou 12 (24 V) para obter a tensao total
    assert d["battery_voltage"] == 2.22
    assert d["temperature_c"] == 27.0
    assert d["ups_status"] == "OL"
    # flags 00001000: nenhum bit relevante ativo (bit 4 e reservado)
    assert d["flags"]["utility_fail"] is False
    assert d["flags"]["battery_low"] is False
    assert d["flags"]["bypass_or_boost"] is False
    assert d["flags"]["ups_failed"] is False
    assert d["flags"]["test_in_progress"] is False
    assert d["flags"]["shutdown_active"] is False
    assert d["flags"]["beeper_on"] is False


def test_parse_q1_utility_fail_vira_ob():
    base = "(231.2 000.0 219.8 008 50.0 2.22 27.0 "
    # utility_fail=1 -> "OB" (on battery)
    assert mec0003.parse_q1(base + "10000000")["ups_status"] == "OB"
    # utility_fail=1 + battery_low=1 -> "OB LB"
    assert mec0003.parse_q1(base + "11000000")["ups_status"] == "OB LB"
    # bateria baixa com rede ok -> "OL LB"
    assert mec0003.parse_q1(base + "01000000")["ups_status"] == "OL LB"
    # beep ligado nao altera o status NUT
    d = mec0003.parse_q1(base + "00000001")
    assert d["ups_status"] == "OL"
    assert d["flags"]["beeper_on"] is True


def test_parse_q1_chaves_do_dict_estaveis():
    # as chaves do JSON publicado (stdout/MQTT) nao podem mudar
    d = mec0003.parse_q1("(231.2 000.0 219.8 008 50.0 2.22 27.0 00001000")
    assert list(d.keys()) == [
        "input_voltage", "input_voltage_fault", "output_voltage",
        "load_percent", "input_frequency_hz", "battery_voltage",
        "temperature_c", "flags", "ups_status",
    ]
    assert list(d["flags"].keys()) == [
        "utility_fail", "battery_low", "bypass_or_boost", "ups_failed",
        "test_in_progress", "shutdown_active", "beeper_on",
    ]


# ---------------------------------------------------------------------------
# parse_f / parse_i / parse_bl
# ---------------------------------------------------------------------------

def test_parse_f():
    d = mec0003.parse_f("#220.0 000 024.0 50.0")
    assert d == {
        "nominal_input_voltage": 220.0,
        "nominal_current_a": 0.0,
        "nominal_battery_voltage": 24.0,
        "nominal_frequency_hz": 50.0,
    }


def test_parse_i():
    d = mec0003.parse_i("#SUNTEK  MODEL-X  FW123")
    assert d == {"manufacturer": "SUNTEK", "model": "MODEL-X",
                 "firmware": "FW123"}


def test_parse_bl():
    assert mec0003.parse_bl("BL85") == 85
    assert mec0003.parse_bl("bl0") == 0


# ---------------------------------------------------------------------------
# Protocolo binario SMS (canal serial)
# ---------------------------------------------------------------------------

def test_sms_checksum_vetores_conhecidos():
    # comandos conhecidos-bons capturados do protocolo SMS
    assert mec0003.sms_checksum(bytes.fromhex("51 ff ff ff ff")) == 0xB3
    assert mec0003.sms_checksum(bytes.fromhex("49 ff ff ff ff")) == 0xBB
    assert mec0003.sms_checksum(bytes.fromhex("46 ff ff ff ff")) == 0xBE
    assert mec0003.sms_checksum(bytes.fromhex("54 00 10 00 00")) == 0x9C


def test_sms_cmds_da_v1_consistentes_com_checksum():
    # os frames literais herdados da v1 (verificados em hardware) têm que
    # bater com o checksum recalculado
    assert mec0003.SMS_CMDS["Q"] == mec0003.build_sms_frame(0x51)
    assert mec0003.SMS_CMDS["I"] == mec0003.build_sms_frame(0x49)
    assert mec0003.SMS_CMDS["F"] == mec0003.build_sms_frame(0x46)


def test_parse_sms_status_resposta_q():
    frame = bytes.fromhex(
        "3d 08 34 08 34 04 38 01 22 02 58 03 e8 01 7c 09 01 0d")
    d = mec0003.parse_sms_status(frame)
    assert d["input_voltage_last"] == 210.0
    assert d["input_voltage"] == 210.0
    assert d["output_voltage"] == 108.0
    assert d["load_percent"] == 29.0
    assert d["output_frequency_hz"] == 60.0
    assert d["battery_charge_percent"] == 100.0
    assert d["temperature_c"] == 38.0
    # byte de estado 0x09 = normal: beep ligado (bit 0) e NAO esta em
    # bateria (bit 7 — "fora da tomada" e 0x89, ver docs/PROTOCOLO.md 1.5)
    assert d["bits"]["beeper_on"] is True
    assert d["bits"]["on_battery"] is False
    assert d["bits"]["ups_ok"] is True


def test_parse_sms_status_em_bateria():
    # mesma captura com o byte de estado 0x89 (bit 7 = em bateria)
    frame = bytes.fromhex(
        "3d 08 34 08 34 04 38 01 22 02 58 03 e8 01 7c 89 01 0d")
    d = mec0003.parse_sms_status(frame)
    assert d["bits"]["on_battery"] is True
    assert d["bits"]["beeper_on"] is True


def test_parse_sms_status_deriva_ups_status():
    frame = bytes.fromhex(
        "3d 08 34 08 34 04 38 01 22 02 58 03 e8 01 7c 89 01 0d")
    # SmsSerialChannel.status() adiciona ups_status no mesmo dialeto do Q1;
    # aqui validamos so o mapeamento (canal serial e mockado)
    d = mec0003.parse_sms_status(frame)
    status = mec0003.montar_ups_status(d["bits"]["on_battery"],
                                       d["bits"]["battery_low"])
    assert status == "OB"


# ---------------------------------------------------------------------------
# Frames invalidos precisam levantar UpsError
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("ruim", ["", "XYZ", "(000", "(1.0 2.0 3.0 004 5.0 6.0 7.0 0"])
def test_parse_q1_invalidos(ruim):
    with pytest.raises(mec0003.UpsError):
        mec0003.parse_q1(ruim)


@pytest.mark.parametrize("ruim", ["", "85", "XX85"])
def test_parse_bl_invalidos(ruim):
    with pytest.raises(mec0003.UpsError):
        mec0003.parse_bl(ruim)


@pytest.mark.parametrize("ruim", [
    b"",                                   # curto
    b"\x3d\x00",                          # curto
    b"\x3e" + b"\x00" * 17,               # marcador errado
    b"\x3d" + b"\x00" * 16 + b"\x0a",     # terminador errado
])
def test_parse_sms_status_invalidos(ruim):
    with pytest.raises(mec0003.UpsError):
        mec0003.parse_sms_status(ruim)


def test_selftest_embutido_passa():
    # o --selftest do CLI roda as mesmas checagens — tem que passar aqui
    import contextlib
    import io
    saida = io.StringIO()
    with contextlib.redirect_stdout(saida):
        rc = mec0003.run_selftest()
    assert rc == 0
    assert "SELFTEST OK" in saida.getvalue()
