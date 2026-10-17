// REA procedure_pseudo_code (Ghidra 12.1.4) on blender 5.2.2 LTS, sha256 bafec183e960819c76fe213c000cdb2284c53a87ef6791812f8728b51f07145b
// evidence: docs/re/evidence/rea-session/35-c-otappend.json (ev_7be0a2048bf0b35eb67e01fec93c5f785c51dd5f2009d6e6f2f7766dede350e2)
// Source identification (by anchor strings, matched against tag v5.2.2): wm_operatortype_append__end

void FUN_016acda0(long *param_1)

{
  long *plVar1;
  ulong uVar2;
  long lVar3;
  undefined8 uVar4;
  long *plVar5;
  size_t sVar6;
  byte *pbVar7;
  char *pcVar8;
  byte *__s;
  ulong uVar9;
  long lVar10;
  
  if (*param_1 == 0) {
    lVar10 = *(long *)(PTR_DAT_0a939560 + 8);
    if (lVar10 == 0) {
      FUN_0160b160(PTR_DAT_0a939560);
      lVar10 = *(long *)(PTR_DAT_0a939560 + 8);
    }
    if (0 < *(int *)(lVar10 + 0x50)) {
      FUN_0160a890(lVar10,1,"source/blender/windowmanager/intern/wm_operator_type.cc:126",
                   "wm_operatortype_append__end","Operator \'%s\' has no name property",param_1[1]);
    }
  }
  FUN_016acc20(param_1);
  pcVar8 = (char *)param_1[3];
  if (pcVar8 == (char *)0x0) {
    pcVar8 = "(undocumented operator)";
  }
  FUN_01d235b0(param_1[0x11],*param_1,pcVar8);
  lVar10 = param_1[1];
  lVar3 = param_1[0x11];
  uVar4 = FUN_01d48520();
  uVar9 = 0x1505;
  FUN_01d26900(uVar4,lVar3,lVar10);
  plVar5 = (long *)FUN_016ac450();
  __s = (byte *)param_1[1];
  if (__s != (byte *)0x0) {
    sVar6 = strlen((char *)__s);
    pbVar7 = __s + sVar6;
    for (; pbVar7 != __s; __s = __s + 1) {
      uVar9 = (ulong)*__s + uVar9 * 0x21;
    }
  }
  lVar10 = plVar5[1];
  if (plVar5[2] <= lVar10) {
    FUN_016abec0(plVar5,(lVar10 - *plVar5) + 1);
    lVar10 = plVar5[1];
  }
  plVar1 = (long *)(plVar5[4] + (uVar9 & plVar5[3]) * 8);
  lVar3 = *plVar1;
  uVar2 = uVar9;
  while (lVar3 != -1) {
    uVar9 = uVar9 >> 5;
    uVar2 = uVar9 + 1 + uVar2 * 5;
    plVar1 = (long *)(plVar5[4] + (uVar2 & plVar5[3]) * 8);
    lVar3 = *plVar1;
  }
  lVar3 = *plVar5;
  *(long **)(plVar5[0x12] + (lVar10 - lVar3) * 8) = param_1;
  *plVar1 = lVar10 - lVar3;
  plVar5[1] = plVar5[1] + 1;
  FUN_016a5350();
  return;
}

