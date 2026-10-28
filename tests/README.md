# Testes — driver MEC0003

Sem hardware e sem root: os testes exercitam apenas parsers/checksums
contra frames capturados de equipamentos reais (ver `frames/README.md`).

Como rodar (a partir da raiz do repositório):

```sh
python3 -m venv .venv-test
.venv-test/bin/pip install pytest pyusb pyserial
.venv-test/bin/python -m pytest tests/ -q
```

O `paho-mqtt` **não** é instalado de propósito (CI leve): os testes não
importam paho — o driver só o importa quando `--mqtt` é usado.

Autochecagem embutida no próprio driver (mesmas checagens, sem pytest):

```sh
python3 mec0003.py --selftest
```
