// rea decompile_all
// name: FUN_0010f240
// address: 0x10f240
// body: available
// range: 0x10f240-0x10f2dd inclusive
// range: 0x10f2e0-0x10f3b5 inclusive
// range: 0x10f3c0-0x10f485 inclusive
// range: 0x10f490-0x10f4d3 inclusive
// range: 0x10f4d8-0x10f50a inclusive
// range: 0x10f510-0x10f585 inclusive
// range: 0x10f590-0x10f5d8 inclusive
// range: 0x10f5e0-0x10f618 inclusive
// range: 0x10f620-0x10f649 inclusive
// range: 0x10f650-0x10f735 inclusive
// non_contiguous: true
// provider: Ghidra 12.1.4 (ghidra)
// analysis_profile: ae80ece8c83379eddabbdf379bbffca5da84c7df7fa7c159f45fa810468f85d9
// limitations: The session serves operations only after Ghidra reports default auto-analysis complete; incomplete analysis does not expose partial results.; The imported Program and temporary project are ephemeral and deleted on close. Annotation operations edit session database metadata; original executable bytes are never written.; Cancelling an active Ghidra request terminates its ephemeral database and discards session annotations. The selected target remains open; the next provider query imports the original artifact again.; Default-space addresses use lowercase 0x-prefixed hexadecimal; other address spaces use <percent-encoded-space>:0x<hex>.; Pseudocode is Ghidra decompiler output, not original source and not text-equivalent to Hopper output.; External functions and functions without an analyzable body return null; other decompiler failures remain explicit.
// pseudocode: provider-specific; not original source


ulong FUN_0010f240(char *param_1,ulong param_2,char *param_3,ulong param_4)

{
  char cVar1;
  int iVar2;
  uint uVar3;
  size_t sVar4;
  undefined2 *puVar5;
  char *pcVar6;
  ulong uVar7;
  ulong __n;
  ulong uVar8;
  long in_FS_OFFSET;
  bool bVar9;
  undefined8 uVar10;
  undefined8 uVar11;
  long local_d0;
  char local_c8 [64];
  undefined2 local_88;
  byte local_86;
  char local_85 [69];
  long local_40;
  
  local_40 = *(long *)(in_FS_OFFSET + 0x28);
  if (2 < DAT_00276b68) {
    sVar4 = strcspn(param_1,"\r");
    FUN_00132c30(3,"send: %.*s",sVar4 & 0xffffffff,param_1);
  }
  __n = param_4;
  if (0x7fffffff < param_4) {
    if (DAT_00276b68 < 3) {
      __n = 0x7ffffffe;
    }
    else {
      __n = 0x7ffffffe;
      FUN_00132c30(3,"%s: requested to read too much (%lu), reducing buflen to (INT_MAX-1)",
                   "ablerex_command",param_4);
    }
  }
  local_d0 = 3;
  do {
    memset(param_3,0,__n);
    local_88 = 5;
    sVar4 = strcspn(param_1,"\r");
    local_86 = (char)sVar4 + 1;
    if (local_86 != 0) {
      uVar7 = 0;
      puVar5 = &local_88;
      do {
        if ((param_2 == uVar7) || (uVar7 == 0x3d)) break;
        pcVar6 = param_1 + uVar7;
        uVar7 = uVar7 + 1;
        *(char *)((long)puVar5 + 3) = *pcVar6;
        puVar5 = (undefined2 *)((long)puVar5 + 1);
      } while (uVar7 != local_86);
    }
    uVar11 = 1000;
    uVar10 = 0x2f;
    iVar2 = libusb_control_transfer(DAT_00277ca0,0x21,9,0x305,0,&local_88);
    if (2 < DAT_00276b68) {
      pcVar6 = "timeout";
      if (iVar2 != 0) {
        pcVar6 = (char *)libusb_strerror(iVar2,uVar11,"timeout",uVar10);
      }
      FUN_00132c30(3,"R11 read: %s",pcVar6);
    }
    usleep(500000);
    local_c8[0] = '\x05';
    uVar3 = libusb_control_transfer(DAT_00277ca0,0xa1,1,0x305,0,local_c8,0x2f,1000);
    if (2 < DAT_00276b68) {
      FUN_00132c30(3,"R2 read%d: %.*s",uVar3,uVar3);
    }
    uVar7 = (ulong)uVar3;
    pcVar6 = local_c8;
    uVar8 = 0;
    do {
      cVar1 = *pcVar6;
      param_3[uVar8] = cVar1;
      if (cVar1 == '\r') {
        if (2 < DAT_00276b68) {
          FUN_00132c30(3,"R3 read%lu: %.*s",uVar8,uVar8 & 0xffffffff);
        }
        uVar8 = (uVar8 + 1) - (ulong)(uVar8 == 0);
        goto LAB_0010f3f4;
      }
      uVar8 = uVar8 + 1;
      pcVar6 = pcVar6 + 1;
    } while (uVar8 != 0x2f);
    uVar8 = 0;
    if (2 < DAT_00276b68) {
      FUN_00132c30(3,"R3 read%lu: %.*s",0,0);
    }
LAB_0010f3f4:
    if ((int)uVar3 < 1) {
      if (2 < DAT_00276b68) {
        pcVar6 = "timeout";
        if (uVar3 != 0) {
          pcVar6 = (char *)libusb_strerror(uVar7);
        }
        FUN_00132c30(3,"read: %s",pcVar6);
      }
      goto LAB_0010f461;
    }
    if (0 < DAT_00276b68) {
      FUN_00132c30(1,"received %d (%d)",uVar7,(int)*param_3);
    }
    iVar2 = strcasecmp(param_1,"Q1\r");
    if (iVar2 == 0) {
      if (uVar8 == 0x2f) {
        iVar2 = strcasecmp(param_1,"I\r");
        if (iVar2 != 0) {
LAB_0010f51a:
          iVar2 = strcasecmp(param_1,"F\r");
          if (iVar2 != 0) {
            bVar9 = true;
            goto LAB_0010f537;
          }
        }
      }
    }
    else {
      iVar2 = strcasecmp(param_1,"I\r");
      if (iVar2 != 0) {
        iVar2 = strcasecmp(param_1,"F\r");
        if (iVar2 == 0) {
          if (uVar8 != 0x16) goto LAB_0010f450;
        }
        else {
          bVar9 = uVar8 != 0x16;
LAB_0010f537:
          iVar2 = strcasecmp(param_1,"Q5\r");
          if ((iVar2 == 0) && (bVar9)) {
            *param_3 = '(';
            iVar2 = DAT_00276b68;
            *(undefined1 (*) [16])(param_3 + 0x11) = (undefined1  [16])0x0;
            *(undefined1 (*) [16])(param_3 + 1) = (undefined1  [16])0x0;
            *(undefined1 (*) [16])(param_3 + 0x1f) = (undefined1  [16])0x0;
            if (2 < iVar2) {
              FUN_00132c30(3,"read Q5 Fail...");
            }
            uVar7 = 0x16;
            goto LAB_0010f461;
          }
        }
        if (2 < DAT_00276b68) {
          sVar4 = strcspn(param_3,"\r");
          FUN_00132c30(3,"read: %.*s",sVar4 & 0xffffffff,param_3);
        }
        uVar7 = uVar8 & 0xffffffff;
        goto LAB_0010f461;
      }
      if (uVar8 == 0x27) goto LAB_0010f51a;
    }
LAB_0010f450:
    local_d0 = local_d0 + -1;
  } while (local_d0 != 0);
  uVar7 = 0;
LAB_0010f461:
  if (local_40 == *(long *)(in_FS_OFFSET + 0x28)) {
    return uVar7;
  }
                    /* WARNING: Subroutine does not return */
  __stack_chk_fail();
}

