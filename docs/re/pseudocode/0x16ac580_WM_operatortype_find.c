// REA procedure_pseudo_code (Ghidra 12.1.4) on blender 5.2.2 LTS, sha256 bafec183e960819c76fe213c000cdb2284c53a87ef6791812f8728b51f07145b
// evidence: docs/re/evidence/rea-session/36-c-otfind.json (ev_fc0a4fe87e8474601213cf682d95d749e7289ee6f62defa39f4d571c292c2479)
// Source identification (by anchor strings, matched against tag v5.2.2): WM_operatortype_find

long FUN_016ac580(char *param_1,char param_2)

{
  ulong uVar1;
  long lVar2;
  char *__s;
  long lVar3;
  int iVar4;
  long lVar5;
  size_t __n;
  byte *pbVar6;
  byte *pbVar7;
  size_t sVar8;
  ulong uVar9;
  ulong uVar10;
  byte local_78 [72];
  
  if (*param_1 == '\0') {
    if (param_2 == '\0') {
      lVar5 = *(long *)(PTR_DAT_0a939560 + 8);
      if (lVar5 == 0) {
        FUN_0160b160(PTR_DAT_0a939560);
        lVar5 = *(long *)(PTR_DAT_0a939560 + 8);
      }
      if (2 < *(int *)(lVar5 + 0x50)) {
        FUN_0160a890(lVar5,3,"source/blender/windowmanager/intern/wm_operator_type.cc:95",
                     "WM_operatortype_find","Search for empty operator");
      }
    }
    return 0;
  }
  uVar9 = 0x1505;
  FUN_016b0e00(local_78,param_1);
  lVar5 = FUN_016ac450();
  __n = strlen((char *)local_78);
  pbVar6 = local_78;
  if (__n != 0) {
    do {
      pbVar7 = pbVar6 + 1;
      uVar9 = (ulong)*pbVar6 + uVar9 * 0x21;
      pbVar6 = pbVar7;
    } while (local_78 + __n != pbVar7);
  }
  uVar1 = *(ulong *)(lVar5 + 0x18);
  lVar2 = *(long *)(lVar5 + 0x20);
  lVar5 = *(long *)(lVar5 + 0x90);
  uVar10 = uVar9;
  do {
    lVar3 = *(long *)(lVar2 + (uVar1 & uVar10) * 8);
    if (lVar3 < 0) {
      if (lVar3 == -1) {
        if (param_2 != '\0') {
          return 0;
        }
        lVar5 = *(long *)(PTR_DAT_0a939560 + 8);
        if (lVar5 == 0) {
          FUN_0160b160(PTR_DAT_0a939560);
          lVar5 = *(long *)(PTR_DAT_0a939560 + 8);
        }
        if (*(int *)(lVar5 + 0x50) < 3) {
          return 0;
        }
        FUN_0160a890(lVar5,3,"source/blender/windowmanager/intern/wm_operator_type.cc:90",
                     "WM_operatortype_find","Search for unknown operator \'%s\', \'%s\'",local_78,
                     param_1);
        return 0;
      }
    }
    else {
      lVar3 = *(long *)(lVar5 + lVar3 * 8);
      __s = *(char **)(lVar3 + 8);
      if (__s == (char *)0x0) {
        if (__n == 0) {
          return lVar3;
        }
      }
      else {
        sVar8 = strlen(__s);
        if (__n == sVar8) {
          if (__n == 0) {
            return lVar3;
          }
          iVar4 = memcmp(local_78,__s,__n);
          if (iVar4 == 0) {
            return lVar3;
          }
        }
      }
    }
    uVar9 = uVar9 >> 5;
    uVar10 = uVar10 * 5 + 1 + uVar9;
  } while( true );
}

