// REA procedure_pseudo_code (Ghidra 12.1.4) on blender 5.2.2 LTS, sha256 bafec183e960819c76fe213c000cdb2284c53a87ef6791812f8728b51f07145b
// evidence: docs/re/evidence/rea-session/32-c-poll.json (ev_d45a576e4526dd6d432623902178e2d4aa15609c4c26e013e1008e02503e8f63)
// Source identification (by anchor strings, matched against tag v5.2.2): bpy_op_fn_poll_impl

int * FUN_02383900(long param_1,undefined8 param_2)

{
  char cVar1;
  long lVar2;
  long lVar3;
  int *piVar4;
  undefined1 uVar5;
  undefined4 local_74;
  long local_70;
  undefined1 local_68 [72];
  
  cVar1 = FUN_023837a0(param_2,&local_70,0);
  if (cVar1 == '\0') {
    return (int *)0x0;
  }
  param_1 = param_1 + 0x10;
  lVar2 = FUN_02358f40();
  if (lVar2 == 0) {
    PyErr_SetString(PyExc_RuntimeError,"Context is None, cannot poll any operators");
LAB_023839e6:
    piVar4 = (int *)0x0;
  }
  else {
    lVar3 = FUN_016ac580(param_1,1);
    if (lVar3 == 0) {
      FUN_016b0d60(local_68,param_1);
      PyErr_Format(PyExc_AttributeError,"Polling operator \"bpy.ops.%s\" error, could not be found",
                   local_68);
      return (int *)0x0;
    }
    if (local_70 == 0) {
      uVar5 = 6;
    }
    else {
      local_74 = 6;
      cVar1 = FUN_01d0ea90(&DAT_0a5f6e40,local_70,&local_74);
      uVar5 = (undefined1)local_74;
      if (cVar1 == '\0') {
        lVar2 = FUN_0347e990(&DAT_0a5f6e40);
        FUN_016b0d60(local_68,param_1);
        PyErr_Format(PyExc_TypeError,
                     "Calling operator \"bpy.ops.%s.poll\" error, expected a string enum in (%s)",
                     local_68,lVar2);
        if (lVar2 != 0) {
          (*(code *)PTR_FUN_0a938798)(lVar2,1);
          return (int *)0x0;
        }
        goto LAB_023839e6;
      }
    }
    cVar1 = FUN_0168b750(lVar2,lVar3,uVar5);
    if (cVar1 == '\0') {
      piVar4 = &_Py_FalseStruct;
    }
    else {
      piVar4 = &_Py_TrueStruct;
    }
    if (*piVar4 + 1 != 0) {
      *piVar4 = *piVar4 + 1;
    }
  }
  return piVar4;
}

