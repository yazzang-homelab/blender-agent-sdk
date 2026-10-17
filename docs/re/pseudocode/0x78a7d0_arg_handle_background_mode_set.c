// REA procedure_pseudo_code (Ghidra 12.1.4) on blender 5.2.2 LTS, sha256 bafec183e960819c76fe213c000cdb2284c53a87ef6791812f8728b51f07145b
// evidence: docs/re/evidence/rea-session/53-c-bgset.json (ev_7063fa836b502c0bf3d0cd41856c87a5718aedece362ec033813f68f19f05cb2)
// Source identification (by anchor strings, matched against tag v5.2.2): arg_handle_background_mode_set

undefined8 FUN_0078a7d0(void)

{
  char cVar1;
  undefined8 uVar2;
  
  cVar1 = FUN_0160af30();
  if (cVar1 == '\0') {
    uVar2 = FUN_00791ff0();
    printf("Blender %s (hash %s built %s %s)\n",uVar2,s_d13f752e3b9c_0a9020f0,s_2026_09_15_0a902110,
           s_01_34_58_0a902100);
  }
  DAT_0aa2b9c1 = 1;
  FUN_00a243e0("None");
  return 0;
}

