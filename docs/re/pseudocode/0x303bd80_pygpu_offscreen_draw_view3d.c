// REA procedure_pseudo_code (Ghidra 12.1.4) on blender 5.2.2 LTS, sha256 bafec183e960819c76fe213c000cdb2284c53a87ef6791812f8728b51f07145b
// evidence: docs/re/evidence/rea-session/34-c-drawview3d.json (ev_cd468c5d09cba4d40464ef3da204ba0b75f27031e72b4170b8809bd42524679c)
// Source identification (by anchor strings, matched against tag v5.2.2): pygpu_offscreen_draw_view3d

undefined4 * FUN_0303bd80(long param_1,undefined8 param_2,undefined8 param_3)

{
  undefined8 uVar1;
  undefined8 uVar2;
  undefined8 uVar3;
  undefined1 uVar4;
  undefined1 uVar5;
  char cVar6;
  int iVar7;
  undefined4 uVar8;
  undefined4 uVar9;
  long lVar10;
  long lVar11;
  long lVar12;
  long lVar13;
  undefined8 uVar14;
  undefined8 uVar15;
  undefined1 local_6a;
  undefined1 local_69;
  long local_68;
  long local_60;
  undefined8 local_58;
  undefined8 local_50;
  undefined8 local_48;
  undefined8 local_40 [2];
  
  local_6a = 0;
  local_69 = 1;
  if (*(long *)(param_1 + 0x10) == 0) {
    PyErr_SetString(PyExc_ReferenceError,"GPU offscreen was freed, no further access is valid");
  }
  else {
    iVar7 = _PyArg_ParseTupleAndKeywordsFast
                      (param_2,param_3,&PTR_s_OOOOO_O___O_O__draw_view3d_0a97a500,&local_58,
                       &local_50,local_40,&local_48,FUN_030d53c0,&local_68,FUN_030d53c0,&local_60,
                       FUN_0347f680,&local_6a,FUN_0347f680,&local_69);
    if (iVar7 != 0) {
      lVar10 = FUN_03481420(local_58,"Scene");
      if (lVar10 != 0) {
        lVar11 = FUN_03481420(local_50,"ViewLayer");
        if (lVar11 != 0) {
          lVar12 = FUN_03481420(local_40[0],"SpaceView3D");
          if (lVar12 != 0) {
            lVar13 = FUN_03481420(local_48,"Region");
            if (lVar13 != 0) {
              cVar6 = thunk_FUN_017f2da0();
              if (cVar6 == '\0') {
                uVar14 = FUN_00a151d0(DAT_0aa2ada0,lVar10,lVar11);
                FUN_012dc040(*(undefined8 *)(param_1 + 0x10),1);
                if (*(long *)(param_1 + 0x18) == 0) {
                  uVar15 = FUN_03683830();
                  *(undefined8 *)(param_1 + 0x18) = uVar15;
                }
                else {
                  FUN_03683810();
                  uVar15 = *(undefined8 *)(param_1 + 0x18);
                }
                uVar5 = local_69;
                uVar4 = local_6a;
                uVar1 = *(undefined8 *)(param_1 + 0x10);
                uVar2 = *(undefined8 *)(local_60 + 0x10);
                uVar3 = *(undefined8 *)(local_68 + 0x10);
                uVar8 = FUN_012dc1b0(uVar1);
                uVar9 = FUN_012dc1a0(*(undefined8 *)(param_1 + 0x10));
                FUN_03339d20(uVar14,lVar10,*(undefined1 *)(lVar12 + 0x118),lVar12,lVar13,0,uVar9,
                             uVar8,uVar3,uVar2,1,uVar5,0x7f1c405,uVar4,1,uVar1,uVar15);
                FUN_012dc070(*(undefined8 *)(param_1 + 0x10),1);
                return &_Py_NoneStruct;
              }
              PyErr_SetString(PyExc_RuntimeError,"Nested off-screen drawing not supported");
            }
          }
        }
      }
    }
  }
  return (undefined4 *)0x0;
}

