// REA procedure_pseudo_code (Ghidra 12.1.4) on blender 5.2.2 LTS, sha256 bafec183e960819c76fe213c000cdb2284c53a87ef6791812f8728b51f07145b
// evidence: docs/re/evidence/rea-session/54-c-pythonrun.json (ev_ce1998bb3f77ed7d5f82109a51c495789f655961eda64ea35faf830cb3c0911d)
// Source identification (by anchor strings, matched against tag v5.2.2): arg_handle_python_file_run

/* WARNING: Globals starting with '_' overlap smaller symbols at the same address */

undefined8 FUN_0078b500(int param_1,undefined8 *param_2,undefined8 param_3)

{
  if (1 < param_1) {
    FUN_0078b450(param_2,param_3);
    return 1;
  }
  fprintf(_stderr,"\nError: you must specify a filepath after \'%s\'.\n",*param_2);
  return 0;
}

