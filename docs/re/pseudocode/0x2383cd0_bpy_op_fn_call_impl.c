// REA procedure_pseudo_code (Ghidra 12.1.4) on blender 5.2.2 LTS, sha256 bafec183e960819c76fe213c000cdb2284c53a87ef6791812f8728b51f07145b
// evidence: docs/re/evidence/rea-session/31-c-call.json (ev_d7c5b79d2ff1f3ca44282b405ca6dfe05519ef6f47dcc5d5523c89693d4f62cb)
// Source identification (by anchor strings, matched against tag v5.2.2): bpy_op_fn_call_impl

undefined8 FUN_02383cd0(long param_1,undefined8 param_2,long param_3)

{
  uint uVar1;
  char cVar2;
  short sVar3;
  uint uVar4;
  int iVar5;
  long lVar6;
  long lVar7;
  long lVar8;
  long lVar9;
  long lVar10;
  undefined1 (*pauVar11) [16];
  undefined8 uVar12;
  undefined1 uVar13;
  undefined1 local_95;
  uint local_94;
  long local_90;
  undefined1 local_88 [24];
  undefined1 *local_70;
  undefined1 local_58 [40];
  
  lVar6 = FUN_02358f40();
  if (lVar6 == 0) {
    PyErr_SetString(PyExc_RuntimeError,"Context is None, cannot call an operator");
    return 0;
  }
  if ((param_3 != 0) && (cVar2 = FUN_03482830(param_3), cVar2 == '\0')) {
    PyErr_SetString(PyExc_TypeError,"keywords must be strings");
    return 0;
  }
  lVar7 = FUN_007aa6b0(lVar6);
  cVar2 = FUN_023837a0(param_2,&local_90,&local_95);
  if (cVar2 == '\0') {
    return 0;
  }
  FUN_02383bb0(lVar6);
  lVar8 = FUN_02358f40();
  if (lVar8 == 0) {
    PyErr_SetString(PyExc_RuntimeError,"Context is None, cannot poll any operators");
    return 0;
  }
  param_1 = param_1 + 0x10;
  lVar9 = FUN_016ac580(param_1,1);
  if (lVar9 == 0) {
    FUN_016b0d60(local_88,param_1);
    PyErr_Format(PyExc_AttributeError,"Calling operator \"bpy.ops.%s\" error, could not be found",
                 local_88);
    return 0;
  }
  cVar2 = FUN_0236ba90();
  if (cVar2 == '\0') {
    FUN_016b0d60(local_88,param_1);
    PyErr_Format(PyExc_RuntimeError,
                 "Calling operator \"bpy.ops.%s\" error, cannot modify blend data in this state (drawing/rendering)"
                 ,local_88);
    return 0;
  }
  if (local_90 == 0) {
    uVar13 = 6;
  }
  else {
    local_94 = 6;
    cVar2 = FUN_01d0ea90(&DAT_0a5f6e40,local_90,&local_94);
    uVar13 = (char)local_94;
    if (cVar2 == '\0') {
      lVar6 = FUN_0347e990(&DAT_0a5f6e40);
      FUN_016b0d60(local_88,param_1);
      PyErr_Format(PyExc_TypeError,
                   "Calling operator \"bpy.ops.%s\" error, expected a string enum in (%s)",local_88,
                   lVar6);
      if (lVar6 == 0) {
        return 0;
      }
      goto LAB_02383e31;
    }
  }
  cVar2 = FUN_0168b750(lVar8,lVar9,uVar13);
  if (cVar2 != '\0') {
    FUN_016b0f30(local_88,lVar9);
                    /* try { // try from 02383f24 to 02384020 has its CatchHandler @ 023841a1 */
    FUN_016b1100(local_88,0);
    if (((param_3 == 0) || (lVar10 = PyDict_Size(param_3), lVar10 == 0)) ||
       (iVar5 = FUN_023778a0(local_88,param_3,0,"Converting py args to operator properties:"),
       iVar5 == 0)) {
      pauVar11 = (undefined1 (*) [16])(*(code *)PTR_FUN_0a938758)(0x30,8,"wmOperatorReportList",0);
      *pauVar11 = (undefined1  [16])0x0;
      pauVar11[1] = (undefined1  [16])0x0;
      pauVar11[2] = (undefined1  [16])0x0;
      FUN_00a08590(pauVar11,0x1a);
      uVar12 = PyEval_SaveThread();
      uVar4 = FUN_0168caa0(lVar8,lVar9,uVar13,local_88,pauVar11,local_95);
      PyEval_RestoreThread(uVar12);
      sVar3 = FUN_0237f960(pauVar11,PyExc_RuntimeError,0);
      iVar5 = (int)sVar3;
      if (*(long *)*pauVar11 != 0) {
        uVar1 = *(uint *)pauVar11[1];
        cVar2 = FUN_0160af30();
        FUN_00a08880(pauVar11,(-(uint)(cVar2 == '\0') & 0xfffffff1) + 0x10);
        FUN_0237f9e0(pauVar11,0);
        FUN_00a08880(pauVar11,uVar1 & 0xffff);
      }
      FUN_00a08600(pauVar11);
      if ((*(uint *)(pauVar11[1] + 8) & 4) == 0) {
                    /* try { // try from 023840a3 to 023840d5 has its CatchHandler @ 023841a1 */
        FUN_00a086c0(pauVar11);
        (*(code *)PTR_FUN_0a938798)(pauVar11,1);
      }
      else {
        *(uint *)(pauVar11[1] + 8) = *(uint *)(pauVar11[1] + 8) & 0xfffffff7;
      }
    }
    else {
      uVar4 = 2;
    }
    FUN_016b1510(local_88);
    if (local_70 != local_58) {
      FUN_0160b9f0();
    }
    if (iVar5 == -1) {
      return 0;
    }
    thunk_FUN_0236c1c0();
    if (((uVar4 & 4) != 0) && (lVar8 = FUN_007aa6b0(lVar6), lVar7 == lVar8)) {
      FUN_02383bb0(lVar6);
    }
    uVar12 = FUN_0347eda0(&DAT_0a600fc0,uVar4);
    return uVar12;
  }
  local_94 = local_94 & 0xffffff00;
  lVar6 = FUN_007aaa90(lVar8,&local_94);
  if (lVar6 == 0) {
    FUN_016b0d60(local_88,param_1);
    PyErr_Format(PyExc_RuntimeError,"Operator bpy.ops.%.200s.poll() %.200s",local_88,
                 "failed, context is incorrect");
    FUN_007aa9e0(lVar8);
    return 0;
  }
  FUN_016b0d60(local_88,param_1);
  PyErr_Format(PyExc_RuntimeError,"Operator bpy.ops.%.200s.poll() %.200s",local_88,lVar6);
  FUN_007aa9e0(lVar8);
  if ((char)local_94 == '\0') {
    return 0;
  }
LAB_02383e31:
  (*(code *)PTR_FUN_0a938798)(lVar6,1);
  return 0;
}

