// REA procedure_pseudo_code (Ghidra 12.1.4) on blender 5.2.2 LTS, sha256 bafec183e960819c76fe213c000cdb2284c53a87ef6791812f8728b51f07145b
// evidence: docs/re/evidence/rea-session/33-c-exitcode.json (ev_b6071389d3a4d08c31584e25f97e0d7656f75d87965ae40dc1f6f00f8baeb6e6)
// Source identification (by anchor strings, matched against tag v5.2.2): arg_handle_python_exit_code_set

/* WARNING: Globals starting with '_' overlap smaller symbols at the same address */

undefined1  [16] FUN_0078be50(int param_1,long param_2)

{
  undefined1 auVar1 [16];
  char cVar2;
  ulong extraout_RDX;
  undefined1 auVar3 [16];
  ulong uStack_20;
  uint local_14;
  undefined8 local_10;
  
  if (1 < param_1) {
    local_10 = 0;
    uStack_20 = 0x78be80;
    cVar2 = FUN_0078b740(*(undefined8 *)(param_2 + 8),0,0xff,&local_14,&local_10);
    if (cVar2 == '\0') {
      fprintf(_stderr,"\nError: %s \'%s %s\', expected number in [%d..%d].\n",local_10,
              "--python-exit-code",*(undefined8 *)(param_2 + 8),0,0xff);
    }
    else {
      uStack_20 = (ulong)local_14;
      DAT_0a901bd3 = (undefined1)local_14;
    }
    auVar3._8_8_ = uStack_20;
    auVar3._0_8_ = 1;
    return auVar3;
  }
  fprintf(_stderr,"\nError: you must specify an exit code number \'%s\'.\n","--python-exit-code");
  auVar1._8_8_ = 0;
  auVar1._0_8_ = extraout_RDX;
  return auVar1 << 0x40;
}

