// rea decompile_all
// name: FUN_0010e7a0
// address: 0x10e7a0
// body: available
// range: 0x10e7a0-0x10ea4c inclusive
// range: 0x10ea50-0x10ea94 inclusive
// range: 0x10ea98-0x10eaad inclusive
// range: 0x10eab0-0x10eb8e inclusive
// range: 0x10eb90-0x10ec84 inclusive
// range: 0x10ec88-0x10ecd5 inclusive
// range: 0x10ece0-0x10ed17 inclusive
// range: 0x10ed20-0x10ed44 inclusive
// range: 0x10ed48-0x10ed93 inclusive
// range: 0x10ed98-0x10edb2 inclusive
// range: 0x10edb8-0x10edf7 inclusive
// range: 0x10ee00-0x10eec6 inclusive
// range: 0x10eed0-0x10eefe inclusive
// range: 0x10ef00-0x10ef52 inclusive
// range: 0x10ef58-0x10ef61 inclusive
// range: 0x10ef68-0x10ef75 inclusive
// range: 0x10ef80-0x10eff5 inclusive
// range: 0x10f000-0x10f031 inclusive
// range: 0x10f038-0x10f069 inclusive
// range: 0x10f070-0x10f089 inclusive
// range: 0x10f090-0x10f0b7 inclusive
// range: 0x10f0c0-0x10f0dc inclusive
// range: 0x10f0e0-0x10f0fc inclusive
// range: 0x10f100-0x10f110 inclusive
// range: 0x10f118-0x10f23f inclusive
// non_contiguous: true
// provider: Ghidra 12.1.4 (ghidra)
// analysis_profile: ae80ece8c83379eddabbdf379bbffca5da84c7df7fa7c159f45fa810468f85d9
// limitations: The session serves operations only after Ghidra reports default auto-analysis complete; incomplete analysis does not expose partial results.; The imported Program and temporary project are ephemeral and deleted on close. Annotation operations edit session database metadata; original executable bytes are never written.; Cancelling an active Ghidra request terminates its ephemeral database and discards session annotations. The selected target remains open; the next provider query imports the original artifact again.; Default-space addresses use lowercase 0x-prefixed hexadecimal; other address spaces use <percent-encoded-space>:0x<hex>.; Ghidra Listing reports a terminal call at 0x10f21f to 0x138e80 FUN_00138e80 (external=false, thunk=false, hasNoReturn=true); fallthrough is excluded by Ghidra's flow model. This records Ghidra's FunctionManager flag, not an independent verification that the callee cannot return.; Pseudocode is Ghidra decompiler output, not original source and not text-equivalent to Hopper output.; External functions and functions without an analyzable body return null; other decompiler failures remain explicit.
// pseudocode: provider-specific; not original source


ulong FUN_0010e7a0(char *param_1,size_t param_2,undefined1 (*param_3) [16],char *param_4)

{
  char cVar1;
  size_t sVar2;
  int iVar3;
  uint uVar4;
  undefined1 *puVar5;
  size_t sVar6;
  undefined1 uVar7;
  char *pcVar8;
  undefined2 *puVar9;
  uint uVar10;
  char *pcVar11;
  char *__s;
  char *__s2;
  undefined1 (*pauVar12) [16];
  ulong uVar13;
  char *pcVar14;
  ulong uVar15;
  long in_FS_OFFSET;
  bool bVar16;
  double dVar17;
  undefined8 uVar18;
  undefined8 uVar19;
  long lStack_5a8;
  char acStack_5a0 [64];
  undefined2 uStack_560;
  byte bStack_55e;
  char acStack_55d [69];
  long lStack_518;
  undefined1 (*pauStack_508) [16];
  char *pcStack_500;
  ulong uStack_4f8;
  char *pcStack_4f0;
  char *pcStack_4e8;
  undefined1 *puStack_4e0;
  long *local_4d8;
  size_t local_4d0;
  uint local_4c4;
  double local_4c0;
  long local_4b8;
  uint local_4b0 [2];
  undefined *local_4a8;
  undefined4 local_4a0;
  undefined *local_498;
  undefined4 local_490;
  undefined *local_488;
  undefined4 local_480;
  undefined *local_478;
  undefined4 local_470;
  undefined *local_468;
  undefined4 local_460;
  undefined8 local_458;
  undefined4 local_450;
  undefined1 local_448 [1032];
  long local_40;
  
  local_40 = *(long *)(in_FS_OFFSET + 0x28);
  local_4a8 = &DAT_0013c5f6;
  local_498 = &DAT_0013c7fc;
  local_488 = &DAT_0013cc12;
  local_478 = &DAT_0013c9a0;
  local_4b0[0] = 3;
  local_4a0 = 0xd;
  local_490 = 0xc;
  local_480 = 7;
  local_470 = 10;
  local_468 = &DAT_0013b270;
  local_460 = 0xf3;
  local_458 = 0;
  local_450 = 0;
  pcVar11 = param_4;
  local_4d0 = param_2;
  if ((int)DAT_00276b68 < 3) {
    pcVar8 = param_4;
    if ((char *)0x7fffffff < param_4) {
      pcVar11 = (char *)0x7ffffffe;
    }
  }
  else {
    puStack_4e0 = (undefined1 *)0x10ec95;
    sVar6 = strcspn(param_1,"\r");
    puStack_4e0 = (undefined1 *)0x10ecad;
    pcVar8 = param_1;
    FUN_00132c30(3,"send: %.*s",sVar6 & 0xffffffff);
    if ((char *)0x7fffffff < param_4) {
      if ((int)DAT_00276b68 < 3) {
        pcVar11 = (char *)0x7ffffffe;
      }
      else {
        pcVar11 = (char *)0x7ffffffe;
        puStack_4e0 = (undefined1 *)0x10eef3;
        FUN_00132c30(3,"%s: requested to read too much (%lu), reducing buflen to (INT_MAX-1)",
                     "hunnox_command");
        pcVar8 = param_4;
      }
    }
  }
  uVar4 = DAT_00276b68;
  local_4d8 = &local_4b8;
  uVar13 = 0;
  __s2 = "Q1\r";
  do {
    puStack_4e0 = (undefined1 *)0x10e8b5;
    iVar3 = strncmp(param_1,__s2,local_4d0);
    if (iVar3 == 0) {
      uVar10 = local_4b0[uVar13 * 4];
      if (local_4b0[uVar13 * 4] != 0) goto joined_r0x0010e8d6;
      break;
    }
    local_4d8 = local_4d8 + 2;
    uVar13 = (ulong)((int)uVar13 + 1);
    __s2 = (char *)*local_4d8;
  } while (__s2 != (char *)0x0);
  local_4c4 = 0xffffffff;
  __s2 = "S%lfR%d\r";
  local_4c0 = -1.0;
  puStack_4e0 = (undefined1 *)0x10ebe8;
  iVar3 = __isoc23_sscanf(param_1,"S%lfR%d\r",&local_4c0,&local_4c4);
  if (iVar3 == 2) {
LAB_0010ebf1:
    uVar10 = 0x10;
    if ((0.5 <= local_4c0) && (uVar10 = 0xf0, local_4c0 <= 10.0)) {
      if (local_4c0 < 1.0) {
        puStack_4e0 = (undefined1 *)0x10f09e;
        dVar17 = round((local_4c0 - 0.5) * 10.0);
        uVar10 = (uint)(dVar17 * 16.0 + 16.0);
      }
      else {
        uVar10 = (uint)((local_4c0 - 1.0) * 16.0 + 96.0);
      }
    }
    pcVar8 = (char *)(ulong)local_4c4;
    if (local_4c4 != 0) {
      uVar10 = uVar10 + 8;
    }
joined_r0x0010e8d6:
    uVar13 = (ulong)uVar10;
    if (3 < (int)uVar4) {
      __s2 = "command index: 0x%02x";
      puStack_4e0 = (undefined1 *)0x10ec80;
      FUN_00132c30(4,"command index: 0x%02x",uVar13);
    }
    uVar15 = (ulong)DAT_0015f400;
    uVar4 = 0x409;
    if (DAT_0015f400 != 0xffffffff) {
      uVar4 = DAT_0015f400;
    }
    if (DAT_00277c98 != 2) {
      if (DAT_00277c98 < 3) {
        if (DAT_00277c98 == 0) {
          if (2 < (int)DAT_00276b68) {
            puStack_4e0 = (undefined1 *)0x10f085;
            FUN_00132c30(3,"asking for: %02X",0);
          }
          if (uVar4 < 0x10000) {
            puStack_4e0 = (undefined1 *)0x3e8;
            pcStack_4e8 = (char *)0x402;
            pcStack_4f0 = (char *)0x10ee4b;
            libusb_control_transfer(DAT_00277ca0,0x80,6,0x300,uVar4 & 0xffff,local_448);
            puStack_4e0 = (undefined1 *)0x3e8;
            pcStack_4e8 = (char *)0x402;
            pcStack_4f0 = (char *)0x10ee80;
            libusb_control_transfer(DAT_00277ca0,0x80,6,0x300,uVar4 & 0xffff,local_448);
            puStack_4e0 = (undefined1 *)0x3e8;
            pcVar8 = (char *)0x301;
            pcStack_4e8 = (char *)0x402;
            __s2 = (char *)0x80;
            pcStack_4f0 = (char *)0x10eeb5;
            libusb_control_transfer(DAT_00277ca0,0x80,6,0x301,uVar4 & 0xffff,local_448);
            puStack_4e0 = (undefined1 *)0x10eec2;
            usleep(10000);
            goto LAB_0010e967;
          }
        }
        else {
          if (DAT_00277c98 != 1) goto LAB_0010e982;
          if (uVar10 == 0xd) {
            uVar4 = 0xd;
            DAT_00277c98 = 2;
            pcVar14 = (char *)0x66;
            if (pcVar11 < (char *)0x67) {
              pcVar14 = pcVar11;
            }
            goto joined_r0x0010ea8a;
          }
          if (2 < (int)DAT_00276b68) {
            puStack_4e0 = (undefined1 *)0x10f0d8;
            FUN_00132c30(3,"asking for: %02X",0xd);
          }
          if (uVar4 < 0x10000) {
            pcVar8 = (char *)0x30d;
            goto LAB_0010e94e;
          }
        }
      }
      else {
        if (DAT_00277c98 != 3) {
LAB_0010e982:
          DAT_00277c98 = 1;
          goto LAB_0010e98c;
        }
        sVar2 = DAT_00276b58;
        sVar6 = local_4d0;
        if (uVar10 == 0xc) {
          uVar4 = 0xc;
          DAT_00277c98 = 1;
          pcVar14 = (char *)0x66;
          if (pcVar11 < (char *)0x67) {
            pcVar14 = pcVar11;
          }
          goto joined_r0x0010ea8a;
        }
        while (local_4d0 = sVar2, local_4d0 != 0) {
          __s2 = "novendor";
          puStack_4e0 = (undefined1 *)0x10efa1;
          iVar3 = strcasecmp(*(char **)(local_4d0 + 8),"novendor");
          sVar6 = local_4d0;
          if (iVar3 == 0) {
            if (*(int *)(local_4d0 + 0x20) != 0) goto LAB_0010e982;
            break;
          }
          sVar2 = *(size_t *)(local_4d0 + 0x28);
        }
        local_4d0 = sVar6;
        if (2 < (int)DAT_00276b68) {
          puStack_4e0 = (undefined1 *)0x10f1a7;
          FUN_00132c30(3,"asking for: %02X",0xc);
        }
        if (uVar4 < 0x10000) {
          pcVar8 = (char *)0x30c;
          goto LAB_0010e94e;
        }
      }
LAB_0010f202:
      if (local_40 == *(long *)(in_FS_OFFSET + 0x28)) {
                    /* WARNING: Subroutine does not return */
        puStack_4e0 = (undefined1 *)0x10f224;
        FUN_00138e80(1,
                     "usb_get_string() args out of range for libusb_get_string_descriptor() implementation"
                    );
      }
      goto LAB_0010f224;
    }
    if (uVar10 == 3) {
      uVar4 = 3;
      DAT_00277c98 = 3;
      pcVar14 = (char *)0x66;
      if (pcVar11 < (char *)0x67) {
        pcVar14 = pcVar11;
      }
joined_r0x0010ea8a:
      if (DAT_0015f400 != 0xffffffff) goto LAB_0010e9ad;
LAB_0010ed2d:
      puStack_4e0 = (undefined1 *)0x10ed3d;
      uVar4 = libusb_get_string_descriptor_ascii
                        (DAT_00277ca0,uVar13 & 0xff,param_3,(ulong)pcVar14 & 0xffffffff);
    }
    else {
      if (2 < (int)DAT_00276b68) {
        puStack_4e0 = (undefined1 *)0x10f0f8;
        FUN_00132c30(3,"asking for: %02X",3);
      }
      if (0xffff < uVar4) goto LAB_0010f202;
      pcVar8 = (char *)0x303;
LAB_0010e94e:
      puStack_4e0 = (undefined1 *)0x3e8;
      pcStack_4e8 = (char *)0x66;
      pcStack_4f0 = (char *)0x10e965;
      libusb_control_transfer(DAT_00277ca0,0x80,6,pcVar8,uVar4 & 0xffff,local_448);
      __s2 = pcStack_4e8;
LAB_0010e967:
      uVar15 = (ulong)DAT_0015f400;
      DAT_00277c98 = DAT_00277c98 + 1;
      if (3 < DAT_00277c98) goto LAB_0010e982;
LAB_0010e98c:
      pcVar14 = (char *)0x66;
      if (pcVar11 < (char *)0x67) {
        pcVar14 = pcVar11;
      }
      uVar4 = uVar10;
      if ((int)uVar15 == -1) {
        if (0xff < uVar10) {
          if (local_40 == *(long *)(in_FS_OFFSET + 0x28)) {
            puStack_4e0 = (undefined1 *)0x10f23e;
            pauVar12 = DAT_00277ca0;
            FUN_0010dab0();
            lStack_518 = *(long *)(in_FS_OFFSET + 0x28);
            pauStack_508 = param_3;
            pcStack_500 = pcVar11;
            uStack_4f8 = uVar13;
            pcStack_4f0 = pcVar14;
            pcStack_4e8 = (char *)uVar15;
            puStack_4e0 = &stack0xfffffffffffffff8;
            if (2 < (int)DAT_00276b68) {
              puStack_4e0 = &stack0xfffffffffffffff8;
              sVar6 = strcspn((char *)pauVar12,"\r");
              FUN_00132c30(3,"send: %.*s",sVar6 & 0xffffffff,pauVar12);
            }
            pcVar11 = pcVar8;
            if ((char *)0x7fffffff < pcVar8) {
              if ((int)DAT_00276b68 < 3) {
                pcVar11 = (char *)0x7ffffffe;
              }
              else {
                pcVar11 = (char *)0x7ffffffe;
                FUN_00132c30(3,
                             "%s: requested to read too much (%lu), reducing buflen to (INT_MAX-1)",
                             "ablerex_command",pcVar8);
              }
            }
            lStack_5a8 = 3;
            do {
              memset(__s,0,(size_t)pcVar11);
              uStack_560 = 5;
              sVar6 = strcspn((char *)pauVar12,"\r");
              bStack_55e = (char)sVar6 + 1;
              if (bStack_55e != 0) {
                pcVar8 = (char *)0x0;
                puVar9 = &uStack_560;
                do {
                  if ((__s2 == pcVar8) || (pcVar8 == (char *)0x3d)) break;
                  pcVar14 = pcVar8 + (long)*pauVar12;
                  pcVar8 = pcVar8 + 1;
                  *(char *)((long)puVar9 + 3) = *pcVar14;
                  puVar9 = (undefined2 *)((long)puVar9 + 1);
                } while (pcVar8 != (char *)(ulong)bStack_55e);
              }
              uVar19 = 1000;
              uVar18 = 0x2f;
              iVar3 = libusb_control_transfer(DAT_00277ca0,0x21,9,0x305,0,&uStack_560);
              if (2 < (int)DAT_00276b68) {
                pcVar8 = "timeout";
                if (iVar3 != 0) {
                  pcVar8 = (char *)libusb_strerror(iVar3,uVar19,"timeout",uVar18);
                }
                FUN_00132c30(3,"R11 read: %s",pcVar8);
              }
              usleep(500000);
              acStack_5a0[0] = '\x05';
              uVar4 = libusb_control_transfer(DAT_00277ca0,0xa1,1,0x305,0,acStack_5a0,0x2f,1000);
              if (2 < (int)DAT_00276b68) {
                FUN_00132c30(3,"R2 read%d: %.*s",uVar4,uVar4);
              }
              uVar13 = (ulong)uVar4;
              pcVar8 = acStack_5a0;
              uVar15 = 0;
              do {
                cVar1 = *pcVar8;
                __s[uVar15] = cVar1;
                if (cVar1 == '\r') {
                  if (2 < (int)DAT_00276b68) {
                    FUN_00132c30(3,"R3 read%lu: %.*s",uVar15,uVar15 & 0xffffffff);
                  }
                  uVar15 = (uVar15 + 1) - (ulong)(uVar15 == 0);
                  goto LAB_0010f3f4;
                }
                uVar15 = uVar15 + 1;
                pcVar8 = pcVar8 + 1;
              } while (uVar15 != 0x2f);
              uVar15 = 0;
              if (2 < (int)DAT_00276b68) {
                FUN_00132c30(3,"R3 read%lu: %.*s",0,0);
              }
LAB_0010f3f4:
              if ((int)uVar4 < 1) {
                if (2 < (int)DAT_00276b68) {
                  pcVar11 = "timeout";
                  if (uVar4 != 0) {
                    pcVar11 = (char *)libusb_strerror(uVar13);
                  }
                  FUN_00132c30(3,"read: %s",pcVar11);
                }
                goto LAB_0010f461;
              }
              if (0 < (int)DAT_00276b68) {
                FUN_00132c30(1,"received %d (%d)",uVar13,(int)*__s);
              }
              iVar3 = strcasecmp((char *)pauVar12,"Q1\r");
              if (iVar3 == 0) {
                if ((uVar15 == 0x2f) && (iVar3 = strcasecmp((char *)pauVar12,"I\r"), iVar3 != 0)) {
LAB_0010f51a:
                  iVar3 = strcasecmp((char *)pauVar12,"F\r");
                  if (iVar3 != 0) {
                    bVar16 = true;
LAB_0010f537:
                    iVar3 = strcasecmp((char *)pauVar12,"Q5\r");
                    if ((iVar3 != 0) || (!bVar16)) goto LAB_0010f4c2;
                    *__s = '(';
                    uVar4 = DAT_00276b68;
                    *(undefined1 (*) [16])(__s + 0x11) = (undefined1  [16])0x0;
                    *(undefined1 (*) [16])(__s + 1) = (undefined1  [16])0x0;
                    *(undefined1 (*) [16])(__s + 0x1f) = (undefined1  [16])0x0;
                    if (2 < (int)uVar4) {
                      FUN_00132c30(3,"read Q5 Fail...");
                    }
                    uVar13 = 0x16;
                    goto LAB_0010f461;
                  }
                }
              }
              else {
                iVar3 = strcasecmp((char *)pauVar12,"I\r");
                if (iVar3 != 0) {
                  iVar3 = strcasecmp((char *)pauVar12,"F\r");
                  if (iVar3 != 0) {
                    bVar16 = uVar15 != 0x16;
                    goto LAB_0010f537;
                  }
                  if (uVar15 != 0x16) goto LAB_0010f450;
LAB_0010f4c2:
                  if (2 < (int)DAT_00276b68) {
                    sVar6 = strcspn(__s,"\r");
                    FUN_00132c30(3,"read: %.*s",sVar6 & 0xffffffff,__s);
                  }
                  uVar13 = uVar15 & 0xffffffff;
                  goto LAB_0010f461;
                }
                if (uVar15 == 0x27) goto LAB_0010f51a;
              }
LAB_0010f450:
              lStack_5a8 = lStack_5a8 + -1;
            } while (lStack_5a8 != 0);
            uVar13 = 0;
LAB_0010f461:
            if (lStack_518 != *(long *)(in_FS_OFFSET + 0x28)) {
                    /* WARNING: Subroutine does not return */
              __stack_chk_fail();
            }
            return uVar13;
          }
          goto LAB_0010f224;
        }
        goto LAB_0010ed2d;
      }
LAB_0010e9ad:
      if ((0xff < uVar4) || (0xffff < (uint)uVar15)) goto LAB_0010f202;
      pcStack_4e8 = (char *)((ulong)pcVar14 & 0xffff);
      puStack_4e0 = (undefined1 *)0x3e8;
      pcStack_4f0 = (char *)0x10e9f0;
      uVar4 = libusb_control_transfer
                        (DAT_00277ca0,0x80,6,(ushort)uVar10 | 0x300,uVar15 & 0xffff,param_3);
    }
    uVar13 = (ulong)uVar4;
    if ((int)uVar4 < 1) {
      if (2 < (int)DAT_00276b68) {
        pcVar11 = "timeout";
        if (uVar4 != 0) {
          puStack_4e0 = (undefined1 *)0x10f109;
          pcVar11 = (char *)libusb_strerror(uVar13);
        }
        puStack_4e0 = (undefined1 *)0x10ed13;
        FUN_00132c30(3,"read: %s (%d)",pcVar11,uVar13);
      }
    }
    else if (DAT_0015f400 == 0xffffffff) {
LAB_0010eae5:
      if (4 < (int)DAT_00276b68) {
        puStack_4e0 = (undefined1 *)0x10ef17;
        FUN_00137710(5,&DAT_0013b1b8,param_3,(long)(int)uVar13);
      }
      if (2 < (int)DAT_00276b68) {
        puStack_4e0 = (undefined1 *)0x10ef36;
        sVar6 = strcspn((char *)param_3,"\r");
        puStack_4e0 = (undefined1 *)0x10ef4e;
        FUN_00132c30(3,"read: %.*s",sVar6 & 0xffffffff,param_3);
      }
      puStack_4e0 = (undefined1 *)0x10eb0d;
      sVar6 = strcspn((char *)param_3,"\r");
      if (sVar6 == 10) {
        puStack_4e0 = (undefined1 *)0x10eb2c;
        iVar3 = strncasecmp((char *)param_3,"UPS No Ack",10);
        if (iVar3 == 0) {
          uVar4 = (uint)pcVar14;
          uVar13 = (ulong)pcVar14 & 0xffffffff;
          if (uVar4 < 0x40) {
            if (((ulong)pcVar14 & 0x20) == 0) {
              if (((ulong)pcVar14 & 0x10) == 0) {
                if (((ulong)pcVar14 & 8) == 0) {
                  if (((ulong)pcVar14 & 4) == 0) {
                    if ((uVar4 != 0) && ((*param_3)[0] = 0, ((ulong)pcVar14 & 2) != 0)) {
                      *(undefined2 *)(param_3[-1] + uVar13 + 0xe) = 0;
                    }
                  }
                  else {
                    *(undefined4 *)*param_3 = 0;
                    *(undefined4 *)(param_3[-1] + uVar13 + 0xc) = 0;
                  }
                }
                else {
                  *(undefined8 *)*param_3 = 0;
                  *(undefined8 *)(param_3[-1] + uVar13 + 8) = 0;
                }
              }
              else {
                *param_3 = (undefined1  [16])0x0;
                *(undefined1 (*) [16])(param_3[-1] + uVar13) = (undefined1  [16])0x0;
              }
            }
            else {
              *param_3 = (undefined1  [16])0x0;
              param_3[1] = (undefined1  [16])0x0;
              *(undefined1 (*) [16])(param_3[-2] + uVar13) = (undefined1  [16])0x0;
              *(undefined1 (*) [16])(param_3[-1] + uVar13) = (undefined1  [16])0x0;
            }
          }
          else {
            uVar13 = (ulong)pcVar14 & 0xffffffff;
            *(undefined1 (*) [16])(param_3[-4] + uVar13) = (undefined1  [16])0x0;
            *(undefined1 (*) [16])(param_3[-3] + uVar13) = (undefined1  [16])0x0;
            *(undefined1 (*) [16])(param_3[-2] + uVar13) = (undefined1  [16])0x0;
            *(undefined1 (*) [16])(param_3[-1] + uVar13) = (undefined1  [16])0x0;
            if (0x3f < uVar4 - 1) {
              uVar13 = 0;
              do {
                uVar10 = (int)uVar13 + 0x40;
                *(undefined1 (*) [16])(*param_3 + uVar13) = (undefined1  [16])0x0;
                *(undefined1 (*) [16])(param_3[1] + uVar13) = (undefined1  [16])0x0;
                *(undefined1 (*) [16])(param_3[2] + uVar13) = (undefined1  [16])0x0;
                *(undefined1 (*) [16])(param_3[3] + uVar13) = (undefined1  [16])0x0;
                uVar13 = (ulong)uVar10;
              } while (uVar10 < (uVar4 - 1 & 0xffffffc0));
            }
          }
          goto LAB_0010ea25;
        }
      }
    }
    else {
      if ((int)(char)(*param_3)[0] == uVar4) {
        if (uVar4 < 3) {
          uVar13 = 0;
          pauVar12 = param_3;
        }
        else {
          puVar5 = *param_3 + 2;
          uVar10 = 0;
          do {
            pauVar12 = (undefined1 (*) [16])((char *)(ulong)uVar10 + (long)*param_3);
            if (pcVar14 + -1 <= (char *)(ulong)uVar10) goto LAB_0010eadf;
            uVar10 = uVar10 + 1;
            uVar7 = 0x3f;
            if (puVar5[1] == '\0') {
              uVar7 = *puVar5;
            }
            puVar5 = puVar5 + 2;
            (*pauVar12)[0] = uVar7;
          } while ((uint)((int)puVar5 - (int)param_3) < uVar4);
          pauVar12 = (undefined1 (*) [16])(*param_3 + uVar10);
LAB_0010eadf:
          uVar13 = (ulong)uVar10;
        }
        (*pauVar12)[0] = 0;
        goto LAB_0010eae5;
      }
      if (0 < (int)DAT_00276b68) {
        puStack_4e0 = (undefined1 *)0x10edae;
        FUN_00132c30(1,"size mismatch: %d / %d",uVar13);
      }
LAB_0010ea25:
      uVar13 = 0;
    }
  }
  else {
    __s2 = "S%lf\r";
    puStack_4e0 = (undefined1 *)0x10ed61;
    iVar3 = __isoc23_sscanf(param_1,"S%lf\r",&local_4c0);
    if (iVar3 == 1) goto LAB_0010ebf1;
    if (2 < (int)uVar4) {
      puStack_4e0 = (undefined1 *)0x10f128;
      sVar6 = strcspn(param_1,"\r");
      puStack_4e0 = (undefined1 *)0x10f140;
      FUN_00132c30(3,"read: %.*s",sVar6 & 0xffffffff,param_1);
    }
    puStack_4e0 = (undefined1 *)0x10ed8c;
    uVar4 = snprintf((char *)param_3,(size_t)pcVar11,"%s",param_1);
    uVar13 = (ulong)uVar4;
  }
  if (local_40 == *(long *)(in_FS_OFFSET + 0x28)) {
    return uVar13;
  }
LAB_0010f224:
                    /* WARNING: Subroutine does not return */
  puStack_4e0 = (undefined1 *)0x10f22a;
  __stack_chk_fail();
}

