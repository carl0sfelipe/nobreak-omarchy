# Contribuindo

Contribuições são muito bem-vindas — em **português ou inglês**, como preferir.
Este projeto existe porque muita gente tem um nobreak "MEC0003" sem suporte;
cada modelo confirmado e cada descoberta de protocolo ajuda outra pessoa.

## O que mais falta (e você pode dar)

1. **Modelos confirmados** — rodou em um nobreak que não está na lista de
   compatibilidade do `README.md`? Conte-nos (issue ou PR).
2. **Frames capturados** — respostas cruas do seu dispositivo (Q1/F/I/BL)
   viram fixtures de teste em `tests/frames/` e ajudam a cobrir variações de
   firmware.
3. **Descobertas de protocolo** — comandos extras do seu modelo específico
   (calibração, teste de bateria, beep) documentados em `docs/PROTOCOLO.md`.

## Reportando um modelo compatível

Abra uma issue com o título `Modelo: <marca> <modelo>` e inclua:

```console
$ lsusb | grep 0001:0000
$ upsc nobreak@localhost        # se funcionou via NUT
$ python3 mec0003.py --info --json   # se funcionou via driver standalone
```

Mais o que ajudou (ou atrapalhou): método usado (`string`, `setreport`,
`serial`), linha do `ups.conf`, e se precisou de `--unwedge`.

Para adicionar direto à tabela de compatibilidade, edite a seção
"Compatibilidade" do `README.md` **e** do `README.en.md` no mesmo PR.

## Política de testes

- Toda mudança de **parsing** (Q1, F, I, BL, frames SMS binários) deve vir
  acompanhada de teste com frame real colocado em `tests/frames/`.
- Testes de parsing são puros (sem hardware): `python3 -m pytest` roda no CI
  (`ci.yml`) em Python 3.10+.
- Mudanças que tocam o transporte USB devem ser testadas **contra o hardware
  real** por quem escreveu — o CI não tem nobreak plugado. Diga qual
  marca/modelo você testou no PR.
- `install.sh`/`uninstall.sh` devem passar em `bash -n` (sintaxe) e, sempre
  que possível, em shellcheck.

## Descobrindo coisas novas do protocolo

Leia `docs/PROTOCOLO.md` antes — muita coisa já está mapeada, incluindo as
armadilhas. Regras de segurança **obrigatórias**:

- **Nunca** envie índices de string `0x68`/`0x69` (desligam o nobreak) nem
  índices não documentados sem evidência prévia (uma varredura "curiosa" pode
  derrubar o seu equipamento e o da pessoa que copiar seu código).
- Mantenha `wLength <= 102` e langid fixo `0x0409` no canal de comandos.
- Documente qualquer comando novo em `docs/PROTOCOLO.md` com a fonte
  (captura, teste, código de referência).

Dica: se você tem o CD/instalador Windows que veio com o nobreak (UPSmart,
"Manager III", PowerView), o [REA](https://github.com/morluto/rea) consegue
extrair o protocolo exatamente do binário do fabricante — foi assim que
validamos a tabela de índices do subdriver `hunnox` (ver
`docs/EVIDENCIA-REA.md`).

## Estilo

- Python 3.10+, sem dependências obrigatórias além de `requirements.txt`
  (mantenha o core importável sem `pyusb` para os testes rodarem no CI).
- Commits e PRs em PT ou EN, mensagem descritiva (sem emoji, por favor).
- Ao mudar comportamento visível, atualize `README.md` e `README.en.md`
  juntos — os dois devem dizer a mesma coisa.

## Licença

Ao contribuir, você concorda que sua contribuição é licenciada sob a MIT
(ver `LICENSE`).
