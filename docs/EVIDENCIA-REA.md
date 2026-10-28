# EVIDÊNCIA DE ENGENHARIA REVERSA — Protocolo USB do chip MEC0003 (NUT `nutdrv_qx`, subdriver `hunnox`)

**Data:** 2026-10-28
**Ferramentas:** REA (`rea-agents` npm) 6.8.0 + Ghidra 12.1.4 (instalado em diretório de usuário, sem root) + binutils (`objdump`, `readelf`, `nm`, `strings`) + símbolos de depuração do Arch Linux via `debuginfod` (`DEBUGINFOD_URLS=https://debuginfod.archlinux.org`).

**Alvo analisado:**

| Campo | Valor |
|---|---|
| Caminho | `/usr/lib/nut/nutdrv_qx` |
| SHA-256 | `812462090980c8275858a58910a6a5c90af4bcb3c04090239ea3d35cb5ddbfad` |
| Build-ID | `b2b5422ee0bcf6110637c82c580489a3d1abe62a` |
| Formato | ELF 64-bit LSB PIE, x86-64, **stripped** (sem `.symtab`; restam `.dynsym` + `.gnu_debuglink` → `nutdrv_qx.debug`) |
| Versão do driver | string `"2.8.5"` em `.rodata` (0x3eac0), confirmada pelo pacote |
| Mapeamento offset↔endereço | identidade em todas as seções (`.text` 0x7040, `.rodata` 0x3b000, `.data` 0x54000) — offset de arquivo = endereço virtual |

> Nota sobre endereços: nesta seção, endereços como `0xe7a0` são endereços de **arquivo/virtuais** do ELF (usados pelo `objdump`). O Ghidra/REA rebaseou a imagem em `0x100000`, portanto `hunnox_command` = `0xe7a0` no objdump = `0x10e7a0` no REA.

---

## (a) O que o REA conseguiu fazer — comandos e bundles gerados

### Ambiente

- REA 6.8.0 via `PATH="$HOME/.local/share/mise/installs/node/24.22.1/bin:$PATH" npx -y rea-agents@latest <cmd>`.
- Estado inicial dos provedores nativos do REA: **ghidra** (`not_configured`, exige `GHIDRA_INSTALL_DIR` com Ghidra 12.1.x), **hopper** (`executable_missing`), **ida** (`not_configured`), **kuna** (`not_configured`). O provedor **rizin não existe** no REA 6.8.0 (há comandos `execute-rizin-command`/`debug-with-rizin`, mas nenhum provedor de análise rizin registrado; `capabilities` lista apenas `native-macos`, `rea-artifact-graph`, `rea-dotnet-static`, `sqlite` como disponíveis). Java 21.0.2 (mise) estava presente.
- Ação corretiva (sem root): download do **Ghidra 12.1.4** (`ghidra_12.1.4_PUBLIC_20260921.zip`, releases do GitHub) para `~/.local/opt/ghidra_12.1.4_PUBLIC` + `export GHIDRA_INSTALL_DIR=...`. Nenhuma instalação com privilégio foi tentada nem necessária.

### Comandos executados e resultados

| Comando REA | Resultado | Bundle salvo em `docs/rea-evidence/` |
|---|---|---|
| `analyze /usr/lib/nut/nutdrv_qx` (sem engine) | **FALHOU** — `provider_unavailable` (candidatos ghidra/hopper/ida/kuna rejeitados) | erro registrado no histórico abaixo |
| `analyze /usr/lib/nut/nutdrv_qx` (com Ghidra) | **OK** — inventário: 679 procedimentos, 2137 strings, 29 seções; `evidence_id=ev_4cd63432aa0cf1971…` | `rea-analyze-nutdrv.json` |
| `decompile /usr/lib/nut/nutdrv_qx 0x10e7a0` | **OK** — pseudocódigo C Ghidra de `hunnox_command`; `evidence_id=ev_c7eb9d0aeb8fd579…` (op. `procedure_pseudo_code`, provedor `ghidra`, confiança `observed`) | `rea-decompile-hunnox_command.json` |
| `function /usr/lib/nut/nutdrv_qx 0x10e7a0 --detail summary --evidence_output …` | **OK** — dossiê completo (`analyze_function`, `evidence_id=ev_a87dd6b2938c7092…`) com chamadas, referências entrantes (`fabula_hunnox_subdriver` em 0x10ab44 → hunnox_command) e fluxo de valores nativo | `rea-function-hunnox_command.json.gz` (descompactar: `gunzip -c`) + `rea-function-hunnox_command.summary.json` |
| `inspect-elf-notes` | **OK** (não precisa de engine) — PT_NOTE/ABI-tag/build-id; `ev_a4d22490876abcb6…` | `rea-inspect-elf-notes.json` |
| `inspect-native-exports` | **OK** — tabela de exportações ELF; `ev_f36efb9a8bb11431…` | `rea-inspect-native-exports.json` |
| `inspect-byte-entropy` | **OK** — entropia por bloco; `ev_85ed44662a25b3a2…` | `rea-inspect-byte-entropy.json` |
| `decompile-all --address-start 0x10e7a0 --address-end 0x10f240 --limit 4` | **OK** (2ª tentativa) — escreveu `functions/0x10e7a0.c` (hunnox_command) e `functions/0x10f240.c` (ablerex_command) com SHA-256 por arquivo no índice; `evidence_id=ev_2d18634bff66620e…`, provedor `ghidra 12.1.4` | `rea-decompile-all.json`, `ghidra-pseudocode/` |
| `inspect-binary-layout` | **NÃO EXECUTADO com sucesso** — requer pwntools fornecido pelo chamador; `import pwn` indisponível no Python 3.14 do host (sem root para instalar) | — |

### Trecho do pseudocódigo REA/Ghidra (`rea-decompile-hunnox_command.json`, `normalized_result`)

Confirma, em alto nível, os mesmos fatos do disassembly (linhas relevantes):

```c
local_460 = 0xf3;                                   // índice BL na tabela da pilha
...
uVar4 = 0x409;                                      // langid 0x0409
// passo 0 (aquecimento):
libusb_control_transfer(DAT_00277ca0,0x80,6,0x300,uVar4 & 0xffff,...);  // string 0
libusb_control_transfer(DAT_00277ca0,0x80,6,0x300,uVar4 & 0xffff,...);  // string 0 (2a vez)
libusb_control_transfer(DAT_00277ca0,0x80,6,0x301,uVar4 & 0xffff,...);  // string 1
//   (com puStack_4e0 = 0x3e8 timeout e pcStack_4e8 = 0x402 wLength)
pcVar8 = (char *)0x30d;   // aquecimento passo 1: string 0x0D (F)
pcVar8 = (char *)0x30c;   // aquecimento passo 3: string 0x0C (I)
pcVar8 = (char *)0x303;   // aquecimento passo 2: string 0x03 (Q1)
pcVar14 = (char *)0x66;   // teto wLength = 102 (várias ocorrências)
uVar4 = libusb_get_string_descriptor_ascii(...);    // caminho alternativo (langid_fix == -1)
libusb_control_transfer(DAT_00277ca0,0x80,6,(ushort)uVar10 | 0x300,uVar15 & 0xffff,param_3);
                                                    // comando real: wValue = 0x0300 | índice
```

Cabeçalho da função descompilada: `FUN_0010e7a0(char *param_1, size_t param_2, undefined1 (*param_3)[16], char *param_4)` — coerente com ABI de 4 argumentos observada no disassembly: `(cmd, cmdlen, answer, answer_len)`.

**Correção de atribuição importante:** o Ghidra fundiu `hunnox_command` (0x10e7a0–0x10f23f) com a função seguinte `ablerex_command` (0x10f240+) num único `FUN_0010e7a0`. O bloco com `libusb_control_transfer(0x21,9,0x305,…)` (SET_REPORT) / `(0xa1,1,0x305,…)` (GET_REPORT) e as strings `"R11 read"`/`"R2 read"`/`"R3 read"` (referenciadas em 0xf346–0xf5ef) pertence a **ablerex_command**, NÃO ao hunnox. Os limites corretos foram obtidos pelos rótulos de símbolo do debuginfod no objdump (ver (b)).

---

## (b) Verificação independente via objdump/strings (ground truth)

### b.1 Strings relevantes (`strings -t x`)

```
  3b238 UPS No Ack
  3b24b S%lfR%d\r          (comando S com R)
  3b254 S%lf\r             (comando S simples)
  3b25a command index: 0x%02x
  3b274 asking for: %02X
  3b285 novendor          (variável NUT consultada no passo 3)
  3d084 Hunnox 0.03
  3d1f5 hunnox
  3d243 MEC0003
  4bdb8 hunnox_command    (__func__)
```

### b.2 Tabela de dispatch dos subdrivers (`.data.rel.ro` 0x53740+, pares `{nome → função}`)

```
0x053770: fabula  -> 0xe140   (fabula_command)
0x053780: hunnox  -> 0xe7a0   (hunnox_command)   <====
0x0537c0: ablerex -> 0xf240   (ablerex_command)
```

### b.3 Tabela de correspondência USB (`.data` 0x174e40+) e instalação do subdriver

A tabela do `qx_usb` associa VID:PID e strings de produto a funções “claim”; os ponteiros para `"MEC"`/`"MEC0003"`/`"ATCL FOR UPS"` aparecem em 0x174e68–0x174ef0 junto aos pares `0483:0035` e `0925:1234`. A função claim correspondente (símbolo do debuginfod `fabula_hunnox_subdriver`, 0xab40) instala o handler do hunnox no ponteiro global:

```
000000000000ab40 <fabula_hunnox_subdriver>:
    ab44: lea 0x3c55(%rip),%rax        # e7a0 <hunnox_command>
    ab4b: mov %rax,0x16d13e(%rip)      # 177c90 <subdriver_command>
    ab52: xor %eax,%eax
    ab54: ret
```

Ou seja: dispositivo com produto USB `"MEC0003"` (a tabela também aceita `"MEC"` e `"ATCL FOR UPS"`) ⇒ `subdriver_command = hunnox_command` ⇒ **todos os comandos Megatec passam pelo túnel de string descriptors**.

### b.4 `hunnox_command` (0xe7a0–0xf23f; limites pelos símbolos debuginfod)

Rótulos obtidos do objdump (símbolos baixados via debuginfod pelo Build-ID, pois o binário está stripped):
`000000000000e7a0 <hunnox_command>:` … `000000000000f240 <ablerex_command>:`. Também confirmados: `fabula_hunnox_subdriver` (0xab40), `hunnox_initups.lto_priv.0` (0x269e0, tail-call para `blazer_initups` com a tabela `hunnox_qx2nut` em 0x9d7c0) e `hunnox_battery_charge.lto_priv.0` (0x26a10, faz parse da resposta `BL`, testes `'B'`/`'L'`).

#### b.4.1 Tabela índice↔comando montada na pilha (0xe814–0xe869) + loop de correspondência

```asm
e81b: movl $0x3,-0x4a8(%rbp)     ; Q1  -> 0x03   (string literal "Q1\r" em 0x3b20c, iteração 0 desenrolada)
e825: movl $0xd,-0x498(%rbp)     ; F   -> 0x0d   (str 0x3c5f6 = "F\r")
e82f: movl $0xc,-0x488(%rbp)     ; I   -> 0x0c   (str 0x3c7fc = "I\r")
e839: movl $0x7,-0x478(%rbp)     ; Q   -> 0x07   (str 0x3cc12 = "Q\r")
e843: movl $0xa,-0x468(%rbp)     ; C   -> 0x0a   (str 0x3c9a0 = "C\r")
e854: movl $0xf3,-0x458(%rbp)    ; BL  -> 0xf3   (str 0x3b270 = "BL\r")
e85e: movq $0x0,-0x450(%rbp)     ; terminador {NULL, 0}
e869: movl $0x0,-0x448(%rbp)

e89e: lea 0x2c967(%rip),%rsi     # 3b20c ("Q1\r")
e8af: call strncmp@GLIBC         ; strncmp(cmd, entrada_da_tabela, cmdlen)
e8b7: jne eb90                   ; não casou -> avança 0x10 bytes e tenta a próxima
eb90: addq $0x10,-0x4d0(%rbp)
eba3: mov (%rax),%rsi            ; carrega string da entrada corrente
e8bd: shl $0x4,%r13              ; r13 = nº da iteração * 16
e8c1: mov -0x4a8(%rbp,%r13,1),%r13d ; índice USB da entrada casada
```

A estrutura de 16 bytes é `{const char *cmd; int indice_usb;}`. **Mapeamento verificado byte a byte:** `Q1→0x03, F→0x0d, I→0x0c, Q→0x07, C→0x0a, BL→0xf3`.

Comandos `S` (delay de tomada, formato `"S%lfR%d\r"`/`"S%lf\r"`) não usam a tabela: o índice é **calculado** (0xebe2–0xec5c): valor ≤ 0,5 → índice `0x10`; valor > 10 → `0xf0`; caso contrário `índice = (v−1)*16 + 96` para v ∈ [1,10] e `índice = round((v−0,5)*10)*16 + 96` para v ∈ (0,5,1); o sufixo `R` soma **+8** ao índice.

#### b.4.2 langid 0x0409 e override

```asm
e8dc: mov 0x50b1d(%rip),%r15d    # 5f400 <langid_fix>   (inicial = -1 em .data)
e8e9: mov $0x409,%r14d           ; langid padrão 0x0409
e8f3: cmovne %r15d,%r14d         ; se langid_fix != -1, usa langid_fix
```

Quando `langid_fix == -1` (padrão), a leitura do comando real usa `libusb_get_string_descriptor_ascii` (que gerencia langid internamente; libusb também recorre a 0x0409):

```asm
ed20: cmp $0xff,%r13d ; ja f202        ; valida índice < 256
ed2d: movzbl %r13b,%esi                ; desc_index
ed34: mov %rbx,%rdx                    ; buffer
ed37: call libusb_get_string_descriptor_ascii
```

#### b.4.3 Transferência do comando real — wValue = 0x0300|índice, wLength = min(len, 0x66), timeout 1000 ms

```asm
e98c: mov $0x66,%r14d                  ; 102
e99c: cmp %r14,%r12                    ; r12 = answer_len (4º argumento)
e99f: cmovbe %r12,%r14                 ; wLength = min(answer_len, 102)
e9c5: movzwl %r14w,%eax                ; wLength (uint16)
e9c9: push $0x3e8                      ; timeout 1000 ms
e9ce: mov %rbx,%r9                     ; data = answer
e9d1: movzwl %r15w,%r8d                ; wIndex = langid (langid_fix)
e9d5: or $0x300,%r13w                  ; wValue = 0x0300 | índice
e9db: push %rax                        ; wLength
e9dc: mov $0x6,%edx                    ; bRequest = 0x06 (GET_DESCRIPTOR)
e9e1: mov $0x80,%esi                   ; bmRequestType = 0x80 (IN, device)
e9e6: movzwl %r13w,%ecx                ; wValue
e9ea: call libusb_control_transfer
```

#### b.4.4 Validação bLength e decodificação UTF-16LE→ASCII (passo de 2 bytes)

```asm
e9f2: mov %eax,%r12d                   ; ret = bytes transferidos
e9f5: test %r12d,%r12d ; jle ece0      ; erro/libusb <0 -> log e retorna ret
ea0b: movsbl (%rbx),%ecx               ; answer[0] = bLength do descriptor
ea0e: cmp %r12d,%ecx ; je ea98         ; bLength == ret -> decodifica
      (senão: log "size mismatch: %d / %d" em debug>=1 e retorna 0 sem decodificar)
ea98: cmp $0x2,%r12d ; jbe f1ac        ; <=2 bytes -> resposta vazia, retorna 0
eaa2: lea -0x1(%r14),%rdi              ; limite = 102-1 iterações
eaa6: lea 0x2(%rbx),%rax               ; pula cabeçalho (bLength+bDescriptorType)
eab3: mov $0x3f,%ecx                   ; '?' (0x3F) padrão
eab8: cmpb $0x0,0x1(%rax)              ; byte ALTO do par UTF-16LE != 0 ?
eabc: jne eac1                         ;   sim -> mantém '?'
eabe: movzbl (%rax),%ecx               ;   não -> pega byte baixo (ASCII)
eac1: add $0x2,%rax                    ; AVANÇA DE 2 EM 2 BYTES
eac5: mov %cl,(%rsi)                   ; grava "in place" (compactação)
eadf: (fim) mov %edx,%r12d
eae2: movb $0x0,(%rsi)                 ; terminador NUL
```

#### b.4.5 Detecção de "UPS No Ack" (0xeafd–0xeb2e)

```asm
eafd: lea 0x2d5a5(%rip),%rsi   # 3c0a9 ("\r")
eb07: call strcspn
eb0d: cmp $0xa,%rax ; jne ea28 ; strcspn(answer,"\r") == 10 ?
eb17: mov $0xa,%edx
eb1c: lea 0x2c715(%rip),%rsi   # 3b238 ("UPS No Ack")
eb26: call strncasecmp         ; compara 10 bytes, sem caixa
eb2e: jne ea28                  ; diferente -> segue
eb34..eb83: zera o buffer de resposta (memset por tamanho 0x40/0x20/0x10/8/4/2) e retorna 0
```

#### b.4.6 Máquina de estados do aquecimento (`hunnox_step`, global em `.bss` 0x177c98; inicia 0)

Despacho inicial (0xe8e3–0xe911): `step 0 -> 0xee00`, `step 2 -> 0xedb8`, `step 1 -> 0xe913`, `step 3 -> 0xea50`.

**Passo 0** (0xee0d–0xeebc) — aquecimento inicial, lê string 0 **duas vezes** e string 1, com `wLength = 0x402` (1026) e timeout 1000 ms, depois `usleep(10000)` (10 ms):

```asm
ee1a: push $0x3e8          ; timeout
ee31: push $0x402          ; wLength 1026
ee36: mov $0x300,%ecx      ; GET_DESCRIPTOR(STRING, índice 0)  [langid]
ee45: call libusb_control_transfer
ee53: mov $0x300,%ecx      ; repete string 0
ee69: push $0x402
ee6e..eeaf: call libusb_control_transfer   ; wValue 0x301 (string 1 = iProduct)
eeb6: mov $0x2710,%edi     ; 10000 us
eebc: call usleep
```

**Passo 1** (0xe913–0xe95f): se o comando atual for `F` (índice 0x0d) vai direto para a transferência real e põe `hunnox_step=2` (0xf038–0xf051); senão faz um aquecimento extra:

```asm
e947: mov $0x30d,%ecx      ; GET string índice 0x0D (F)
e94c: push $0x66           ; wLength 102
e937: push $0x3e8          ; timeout 1000 ms
e95f: call libusb_control_transfer
e967..e977: hunnox_step++ (de 1 para 2)
```

**Passo 2** (0xedb8–0xedf3 + 0xf000): se o comando for `Q1` (índice 3): `hunnox_step=3` e transfere direto (0xf012); senão aquecimento `wValue=0x303` (string Q1), `wLength=0x66`, depois `step 2→3`:

```asm
edec: mov $0x303,%ecx ; edf1: push $0x66 ; (cai no mesmo call em e95f)
```

**Passo 3** (0xea50–0xea5d, 0xef68–0xefef, 0xea63–0xea75): se o comando for `I` (índice 0x0c): `hunnox_step=1` e transfere direto; senão consulta a `vartab_h` pela variável **`novendor`** (strcasecmp em 0xef94) — se ativa, pula o aquecimento; caso contrário aquecimento `wValue=0x30c` (string I), `wLength=0x66`, `step 3→4` que é re-ajustado para 1 (`cmp $0x3; jle; movl $1,hunnox_step` em 0xe97d–0xe982).

```asm
efea: mov $0x30c,%ecx
efef: push $0x66
```

Efeito prático: durante a operação normal (polling F/Q1/I do driver Qx), cada chamada de `hunnox_command` nos passos 1/2/3 emite **um GET de string extra (F, Q1 ou I) antes do comando real**, e quando o pedido coincide com o “esperado” do passo o warm-up é pulado — daí o intercalar F/Q1/I observado no barramento. A variável NUT `novendor` desativa o aquecimento do passo 3.

### b.5 Endpoints de interrupção na camada genérica qx_usb (fora do hunnox)

```asm
bc91: mov $0x81,%esi        ; endpoint IN 0x81
bc96: call libusb_interrupt_transfer   ; com ecx=8 (8 bytes), r9=0x3e8 (1000 ms)
f946: mov $0x2,%esi         ; endpoint OUT 0x02 (exemplo em fuji_command)
```

Vários pontos (0xbc91, 0xc064, 0xc3d0, 0xc5e1, 0xc926, 0xcf8b, 0xd24e, 0xd8d9…) usam endpoint `0x81` com comprimento 8 e timeout 1000 ms — consistente com os endpoints 0x81 IN / 0x02 OUT de 8 bytes relatados pela observação USB (VID:PID 0001:0000 do dispositivo real **não** aparece na tabela de match do binário, que lista 0483:0035 e 0925:1234 por produto — a seleção hunnox acontece pelo iProduct "MEC0003"; a identidade 0001:0000 é do dispositivo físico e não do driver).

---

## (c) Tabela final VERIFICADA do protocolo

Todas as linhas abaixo foram confirmadas por **duas fontes independentes** (disassembly objdump + pseudocódigo REA/Ghidra), exceto onde marcado.

### c.1 Mapeamento comando Megatec ↔ índice de string USB

| Comando ASCII (Megatec) | Índice do string descriptor (wValue = 0x0300\|idx) | Função no protocolo | Status |
|---|---|---|---|
| `Q1\r` | **0x03** | status geral | **verificado** (tabela em pilha + literal 0x3b20c) |
| `F\r` | **0x0d** | ratings da UPS | **verificado** (0x3c5f6) |
| `I\r` | **0x0c** | informações do fabricante | **verificado** (0x3c7fc) |
| `Q\r` | **0x07** | beep ligar/desligar | **verificado** (0x3cc12) |
| `C\r` | **0x0a** | desligar/reiniciar tomada | **verificado** (0x3c9a0) |
| `BL\r` | **0xf3** | tensão da bateria | **verificado** (0x3b270) |
| `S<val>[R<n>]\r` | **0x10…0xf0 (calculado)** | delay da tomada; `+8` se `R` | **verificado** (0xebe2–0xec5c) |

### c.2 Parâmetros da transferência de leitura

| Parâmetro | Valor | Status |
|---|---|---|
| bmRequestType / bRequest | `0x80` / `0x06` (GET_DESCRIPTOR) | **verificado** |
| Tipo de descriptor | `0x03` (STRING), `wValue = 0x0300\|índice` | **verificado** |
| langid (wIndex) | `0x0409` padrão; override pela variável global `langid_fix` (init −1) | **verificado** |
| wLength (comando real) | `min(answer_len, 102)` — constante `0x66` | **verificado** |
| Timeout | `1000 ms` (0x3e8) | **verificado** |
| Caminho alternativo | `langid_fix == −1` ⇒ `libusb_get_string_descriptor_ascii()` (ASCII pronto, pula decodificação manual) | **verificado** |
| Validação | `answer[0]` (bLength) deve igualar bytes transferidos; divergência ⇒ log “size mismatch” e retorno 0 | **verificado** |
| Decodificação | UTF-16LE→ASCII “in place”, passo 2, header pulado (2 bytes), não-ASCII vira `'?'` (0x3F), NUL final | **verificado** |
| Resposta inválida | `"UPS No Ack"` (10 bytes, strncasecmp) ⇒ buffer zerado, retorno 0 | **verificado** |

### c.3 Aquecimento (warm-up) em lock-step — `hunnox_step` (0..3, inicia 0, wrap 4→1)

| Passo | Ação antes do comando real | Status |
|---|---|---|
| 0 | GET string 0 (wLength **0x402**), GET string 0 de novo, GET string 1 (0x301), `usleep` 10 ms; step→1 | **verificado** |
| 1 | Se pedido ≠ F: GET string 0x0D (F) com wLength 0x66; step→2. Se pedido = F: step→2 sem warm-up | **verificado** |
| 2 | Se pedido ≠ Q1: GET string 0x03 (Q1) wLength 0x66; step→3. Se pedido = Q1: step→3 sem warm-up | **verificado** |
| 3 | Se pedido ≠ I: GET string 0x0C (I) wLength 0x66; step→4→1 (a menos que var NUT `novendor` ativa ⇒ pula warm-up). Se pedido = I: step→1 sem warm-up | **verificado** |
| Interleaving resultante | durante polling: leituras extras de F/Q1/I intercaladas com os comandos | **verificado (estático)** — comportamento dinâmico no barramento: **não verificado** aqui (não houve captura USB nesta análise) |

### c.4 Seleção do subdriver

`iProduct` USB `"MEC0003"` (tabela também aceita `"MEC"` e `"ATCL FOR UPS"`; VID:PID listados no binário: `0483:0035`, `0925:1234`) ⇒ função claim `fabula_hunnox_subdriver()` (0xab40) ⇒ `subdriver_command = hunnox_command` (0xe7a0). **Verificado.** Nota: `hunnox_initups` reaproveita `blazer_initups` com a tabela `hunnox_qx2nut` — herança do mapeamento Megatec/blazer.

### c.5 Itens do contexto original e seu status nesta análise

| Afirmava o contexto | Status |
|---|---|
| VID:PID real do chip 0001:0000, low-speed, HID, EP 0x81 IN / 0x02 OUT de 8 bytes | endpoints/tamanho **verificados** na camada genérica qx (0x81/0x02, 8 bytes, 1000 ms); VID:PID 0001:0000 do dispositivo físico **não verificado no binário** (o binário casa por iProduct; não contém 0001:0000) |
| Índices 0x03/0x0d/0x0c/0x07/0x0a/0xf3 | **verificados** (tabela idêntica) |
| langid 0x0409 | **verificado** (com nuance: override `langid_fix`; sem override, caminho via `libusb_get_string_descriptor_ascii`) |
| wLength cap 102 | **verificado** (`min(answer_len, 0x66)`); warm-up passo 0 usa 0x402, passos 1–3 usam 0x66 |
| Warm-up lendo strings 0/1 e intercalando F/Q1/I | **verificado em detalhe** (máquina de estados completa) |

---

## (d) Limitações

1. **Binário stripped** — sem `.symtab`; os nomes de função nos rótulos do objdump vieram de símbolos separados do Arch **debuginfod** (`.gnu_debuglink` → `nutdrv_qx.debug`, ausente localmente; baixado via build-id em tempo de execução). Sem debuginfod, os endereços continuam válidos, mas os nomes não apareceriam.
2. **Sem rizin/radare2 no host** e o REA 6.8.0 **não possui provedor rizin**; sem Ghidra instalado inicialmente. Mitigado instalando Ghidra 12.1.4 em `~/.local/opt` (usuário, sem root). `inspect-binary-layout` ficou indisponível por exigir pwntools (Python 3.14 sem o módulo; instalação de pacote não tentada para não depender de root).
3. **Cada comando REA reimporta o binário num projeto Ghidra efêmero** (limitação declarada pelo próprio REA) — sem sessão persistente entre chamadas CLI.
4. **Fronteira de função imprecisa no Ghidra**: `FUN_0010e7a0` fundiu `hunnox_command` + `ablerex_command`; os blocos SET_REPORT/GET_REPORT (0x21/9 e 0xa1/1, wValue 0x305) e strings “R1x read” pertencem a `ablerex_command`. Corrigido pelos símbolos debuginfod.
5. **`decompile-all`**: a primeira tentativa (janela ampla 0x10ab40–0x10f240) terminou com **SIGKILL** do processo Ghidra (o REA apenas reporta o sinal; causa provável é memória, mas não comprovada); a **segunda tentativa**, com janela estreita (`--address-start 0x10e7a0 --address-end 0x10f240 --limit 4`), teve sucesso e gravou 2 arquivos `.c` com índice e hash (`ghidra-pseudocode/`).
6. **Análise exclusivamente estática**: nenhuma captura USB nem execução do driver foram feitas aqui; os efeitos dinâmicos (respostas reais do MEC0003, timing do lock-step no barramento) permanecem **não verificados** neste documento.
7. `hunnox_battery_charge`/`hunnox_qx2nut` (parse de `BL` e mapeamento de variáveis) foram apenas localizados, não documentados em profundidade (fora do escopo do protocolo de túnel).

## (e) Conclusão sobre a fidelidade do protocolo documentado

A documentação prévia do protocolo (túnel de comandos Megatec ASCII dentro de GETs de string descriptor; índices 0x03=Q1, 0x0d=F, 0x0c=I, 0x07=Q, 0x0a=C, 0xf3=BL; langid 0x0409; teto wLength 102; aquecimento lendo strings 0/1 com intercalação F/Q1/I) é **fiel ao binário**, com três refinamentos descobertos na verificação:

1. o langid 0x0409 aplica-se diretamente aos **warm-ups**; para o comando real, o caminho padrão é `libusb_get_string_descriptor_ascii` (0x0409 só é passado explicitamente quando `langid_fix` está configurado);
2. o warm-up do passo 0 usa `wLength = 0x402` (1026), e não 102;
3. existem também comandos `S<valor>[R<n>]` com **índice calculado dinamicamente** (0x10…0xf8) e a variável NUT `novendor` que suprime o aquecimento do passo 3.

Confiança alta: todos os itens marcados “verificados” têm fonte dupla (bytes/instruções objdump + pseudocódigo Ghidra/REA) e endereços citados.

---

## Artifacts

Diretório `docs/rea-evidence/`:

- `rea-analyze-nutdrv.json` — inventário REA+Ghidra (ev_4cd63432…)
- `rea-decompile-hunnox_command.json` — pseudocódigo de hunnox_command (ev_c7eb9d0a…)
- `rea-function-hunnox_command.json.gz` / `.summary.json` — dossiê analyze_function (ev_a87dd6b2…)
- `rea-decompile-all.json`, `ghidra-pseudocode/` — exportação em massa (ev_2d18634b…): `functions/0x10e7a0.c` (hunnox_command), `functions/0x10f240.c` (ablerex_command), `decompile-index.json`, `decompile-journal.jsonl`
- `rea-inspect-elf-notes.json`, `rea-inspect-native-exports.json`, `rea-inspect-byte-entropy.json` — inspetores target-free
- `objdump-hunnox_command-0xe7a0-0xf23f.txt` — disassembly completo da função
- `objdump-full-disasm.txt.gz` — disassembly completo do binário (com rótulos debuginfod)
- `strings-and-matchtable.txt` — strings relevantes + tabela de match USB (0483:0035 / 0925:1234 / “MEC0003”…)
- `subdriver-table.txt` — tabela de dispatch `{nome → *_command}` (`.data.rel.ro` 0x53740+)
