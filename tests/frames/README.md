# Frames de teste — origem

Todos os frames usados em `tests/test_parsers.py` vieram de **capturas
reais**, nenhum foi sintetizado:

* `"(231.2 000.0 219.8 008 50.0 2.22 27.0 00001000"` — resposta `Q1`
  capturada ao vivo em 2026-10-28 de um nobreak MEC0003 (0001:0000) em
  operação normal: entrada 231,2 V, saída 219,8 V, carga 8%, 50,0 Hz,
  bateria 2,22 V (por célula), 27,0 °C, status `OL`.
* `"#220.0 000 024.0 50.0"` — resposta `F` (valores nominais) do mesmo
  equipamento.
* `"#SUNTEK  MODEL-X  FW123"` — formato de resposta `I` observado em campo
  (fabricante/modelo/firmware variam entre marcas).
* Frame SMS de 18 bytes `3d 08 34 08 34 04 38 01 22 02 58 03 e8 01 7c 09 01 0d`
  — resposta do comando `Q` do protocolo binário serial SMS, documentada a
  partir das capturas dos projetos smsUps/nobreakSMS (ver
  `docs/PROTOCOLO.md` §1.4; byte de estado `0x09` = normal, `0x89` = em
  bateria).
* Vetores de checksum (`51 ff…`→`b3`, `49 ff…`→`bb`, `46 ff…`→`be`,
  `54 00 10 00 00`→`9c`) — comandos conhecidos-bons do protocolo SMS,
  conferidos contra pacotes reais sniffados do cabo serial.

Se um novo comportamento de firmware for descoberto, adicione o frame
capturado aqui antes de escrever o teste.
