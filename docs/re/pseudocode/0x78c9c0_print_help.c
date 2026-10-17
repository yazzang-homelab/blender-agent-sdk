// REA procedure_pseudo_code (Ghidra 12.1.4) on blender 5.2.2 LTS, sha256 bafec183e960819c76fe213c000cdb2284c53a87ef6791812f8728b51f07145b
// evidence: docs/re/evidence/rea-session/50-c-bg1.json (ev_ccc902c5f24f0aacabc247ed11f06c7d90bb5cc01073367b16ad866292b559bd)
// Source identification (by anchor strings, matched against tag v5.2.2): print_help

void FUN_0078c9c0(undefined8 param_1,char param_2)

{
  char cVar1;
  undefined8 uVar2;
  char cVar3;
  
  cVar3 = param_2;
  if (param_2 == '\0') {
    cVar3 = '\0';
  }
  uVar2 = FUN_00791ff0();
  FUN_010edeb0(param_1,"Blender %s\n",uVar2);
  FUN_010edeb0(param_1,"Usage: blender [args ...] [file] [args ...]\n");
  FUN_010edeb0(param_1,"\n");
  FUN_010edeb0(param_1,"Render Options:\n");
  FUN_010ee1f0(param_1,"--background");
  FUN_010ee1f0(param_1,"--render-anim");
  FUN_010ee1f0(param_1,"--scene");
  FUN_010ee1f0(param_1,"--render-frame");
  FUN_010ee1f0(param_1,"--frame-start");
  FUN_010ee1f0(param_1,"--frame-end");
  FUN_010ee1f0(param_1,"--frame-jump");
  FUN_010ee1f0(param_1,"--render-output");
  FUN_010ee1f0(param_1,"--engine");
  FUN_010ee1f0(param_1,"--threads");
  FUN_010edeb0(param_1,"Cycles Render Options:\n");
  FUN_010edeb0(param_1,"\tCycles add-on options must be specified following a double dash.\n");
  FUN_010edeb0(param_1,"\n");
  FUN_010edeb0(param_1,"--cycles-device <device>\n");
  FUN_010edeb0(param_1,"\tSet the device used for rendering.\n");
  FUN_010edeb0(param_1,
               "\tValid options are: \'CPU\' \'CUDA\' \'OPTIX\' \'HIP\' \'ONEAPI\' \'METAL\'.\n");
  FUN_010edeb0(param_1,"\n");
  FUN_010edeb0(param_1,"\tAppend +CPU to a GPU device to render on both CPU and GPU.\n");
  FUN_010edeb0(param_1,"\n");
  FUN_010edeb0(param_1,"\tExample:\n");
  FUN_010edeb0(param_1,"\t# blender -b file.blend -f 20 -- --cycles-device OPTIX\n");
  FUN_010edeb0(param_1,"--cycles-print-stats\n");
  FUN_010edeb0(param_1,"\tLog statistics about render memory and time usage.\n");
  FUN_010edeb0(param_1,"\n");
  FUN_010edeb0(param_1,"Format Options:\n");
  FUN_010ee1f0(param_1,"--render-format");
  FUN_010ee1f0(param_1,"--use-extension");
  FUN_010edeb0(param_1,"\n");
  FUN_010edeb0(param_1,"Animation Playback Options:\n");
  FUN_010ee1f0(param_1,&DAT_07e254aa);
  FUN_010edeb0(param_1,"\n");
  FUN_010edeb0(param_1,"Window Options:\n");
  FUN_010ee1f0(param_1,"--window-border");
  FUN_010ee1f0(param_1,"--window-maximized");
  FUN_010ee1f0(param_1,"--window-fullscreen");
  FUN_010ee1f0(param_1,"--window-geometry");
  FUN_010ee1f0(param_1,"--start-console");
  FUN_010ee1f0(param_1,"--no-native-pixels");
  FUN_010ee1f0(param_1,"--no-window-frame");
  FUN_010ee1f0(param_1,"--no-window-focus");
  FUN_010edeb0(param_1,"\n");
  FUN_010edeb0(param_1,"Python Options:\n");
  FUN_010ee1f0(param_1,"--enable-autoexec");
  FUN_010ee1f0(param_1,"--disable-autoexec");
  FUN_010edeb0(param_1,"\n");
  FUN_010ee1f0(param_1,"--python");
  FUN_010ee1f0(param_1,"--python-text");
  FUN_010ee1f0(param_1,"--python-expr");
  FUN_010ee1f0(param_1,"--python-console");
  FUN_010ee1f0(param_1,"--python-exit-code");
  FUN_010ee1f0(param_1,"--python-use-system-env");
  FUN_010ee1f0(param_1,"--python-use-user-env");
  FUN_010ee1f0(param_1,"--addons");
  FUN_010edeb0(param_1,"\n");
  FUN_010edeb0(param_1,"Network Options:\n");
  FUN_010ee1f0(param_1,"--online-mode");
  FUN_010ee1f0(param_1,"--offline-mode");
  FUN_010edeb0(param_1,"\n");
  FUN_010edeb0(param_1,"Logging Options:\n");
  FUN_010ee1f0(param_1,"--log");
  FUN_010ee1f0(param_1,"--log-level");
  FUN_010ee1f0(param_1,"--log-show-memory");
  FUN_010ee1f0(param_1,"--log-show-source");
  FUN_010ee1f0(param_1,"--log-show-backtrace");
  FUN_010ee1f0(param_1,"--log-file");
  FUN_010ee1f0(param_1,"--log-list-categories");
  FUN_010edeb0(param_1,"\n");
  FUN_010edeb0(param_1,"Debug Options:\n");
  FUN_010ee1f0(param_1,"--debug");
  FUN_010ee1f0(param_1,"--debug-value");
  FUN_010edeb0(param_1,"\n");
  FUN_010ee1f0(param_1,"--debug-events");
  FUN_010ee1f0(param_1,"--debug-handlers");
  FUN_010ee1f0(param_1,"--debug-libmv");
  FUN_010ee1f0(param_1,"--debug-memory");
  FUN_010ee1f0(param_1,"--debug-jobs");
  FUN_010ee1f0(param_1,"--debug-python");
  FUN_010ee1f0(param_1,"--debug-depsgraph");
  FUN_010ee1f0(param_1,"--debug-depsgraph-eval");
  FUN_010ee1f0(param_1,"--debug-depsgraph-build");
  FUN_010ee1f0(param_1,"--debug-depsgraph-tag");
  FUN_010ee1f0(param_1,"--debug-depsgraph-no-threads");
  FUN_010ee1f0(param_1,"--debug-depsgraph-time");
  FUN_010ee1f0(param_1,"--debug-depsgraph-pretty");
  FUN_010ee1f0(param_1,"--debug-depsgraph-uid");
  FUN_010ee1f0(param_1,"--debug-ghost");
  FUN_010ee1f0(param_1,"--debug-wintab");
  FUN_010ee1f0(param_1,"--debug-gpu");
  FUN_010ee1f0(param_1,"--debug-gpu-force-workarounds");
  FUN_010ee1f0(param_1,"--debug-gpu-compile-shaders");
  FUN_010ee1f0(param_1,"--debug-gpu-shader-debug-info");
  FUN_010ee1f0(param_1,"--debug-gpu-scope-capture");
  FUN_010ee1f0(param_1,"--debug-gpu-shader-source");
  FUN_010ee1f0(param_1,"--debug-gpu-shader-no-preprocessor");
  FUN_010ee1f0(param_1,"--debug-gpu-shader-no-dce");
  FUN_010ee1f0(param_1,"--debug-gpu-no-texture-pool");
  if (cVar3 != '\0') {
    FUN_010ee1f0(param_1,"--debug-gpu-renderdoc");
  }
  FUN_010ee1f0(param_1,"--debug-gpu-vulkan-local-read");
  FUN_010ee1f0(param_1,"--debug-wm");
  FUN_010ee1f0(param_1,"--debug-xr");
  FUN_010ee1f0(param_1,"--debug-xr-time");
  FUN_010ee1f0(param_1,"--debug-all");
  FUN_010ee1f0(param_1,"--debug-io");
  FUN_010edeb0(param_1,"\n");
  FUN_010ee1f0(param_1,"--debug-fpe");
  FUN_010ee1f0(param_1,"--debug-exit-on-error");
  FUN_010ee1f0(param_1,"--debug-freestyle");
  FUN_010ee1f0(param_1,"--console-crash-handler");
  FUN_010ee1f0(param_1,"--disable-crash-handler");
  FUN_010ee1f0(param_1,"--disable-abort-handler");
  FUN_010ee1f0(param_1,"--verbose");
  FUN_010ee1f0(param_1,"--quiet");
  FUN_010edeb0(param_1,"\n");
  FUN_010edeb0(param_1,"GPU Options:\n");
  FUN_010ee1f0(param_1,"--gpu-backend");
  FUN_010ee1f0(param_1,"--gpu-device");
  FUN_010ee1f0(param_1,"--gpu-device-no-fallback");
  FUN_010ee1f0(param_1,"--gpu-vsync");
  FUN_010ee1f0(param_1,"--gpu-compilation-subprocesses");
  FUN_010ee1f0(param_1,"--profile-gpu");
  FUN_010edeb0(param_1,"\n");
  FUN_010edeb0(param_1,"Misc Options:\n");
  FUN_010ee1f0(param_1,"--open-last");
  FUN_010ee1f0(param_1,"--app-template");
  FUN_010ee1f0(param_1,"--factory-startup");
  FUN_010ee1f0(param_1,"--enable-event-simulate");
  FUN_010edeb0(param_1,"\n");
  FUN_010ee1f0(param_1,"--env-system-datafiles");
  FUN_010ee1f0(param_1,"--env-system-scripts");
  FUN_010ee1f0(param_1,"--env-system-extensions");
  FUN_010ee1f0(param_1,"--env-system-python");
  FUN_010edeb0(param_1,"\n");
  FUN_010ee1f0(param_1,"-noaudio");
  FUN_010ee1f0(param_1,"-setaudio");
  FUN_010edeb0(param_1,"\n");
  FUN_010ee1f0(param_1,"--command");
  FUN_010edeb0(param_1,"\n");
  FUN_010ee1f0(param_1,&DAT_07e25a59);
  FUN_010ee1f0(param_1,&DAT_07e25a60);
  FUN_010ee1f0(param_1,"--register");
  FUN_010ee1f0(param_1,"--register-allusers");
  FUN_010ee1f0(param_1,"--unregister");
  FUN_010ee1f0(param_1,"--unregister-allusers");
  FUN_010ee1f0(param_1,"--qos");
  FUN_010ee1f0(param_1,"--version");
  FUN_010ee1f0(param_1,&DAT_07f1efe9);
  cVar1 = FUN_010ee2d0(param_1);
  if (cVar1 != '\0') {
    FUN_010edeb0(param_1,"\n");
    FUN_010edeb0(param_1,"Other Options:\n");
    FUN_010ee280(param_1);
  }
  FUN_010edeb0(param_1,"\n");
  FUN_010edeb0(param_1,"Argument Parsing:\n");
  FUN_010edeb0(param_1,"\tArguments must be separated by white space, eg:\n");
  FUN_010edeb0(param_1,"\t# blender -ba test.blend\n");
  FUN_010edeb0(param_1,"\t...will exit since \'-ba\' is an unknown argument.\n");
  FUN_010edeb0(param_1,"\n");
  FUN_010edeb0(param_1,"Argument Order:\n");
  FUN_010edeb0(param_1,"\tArguments are executed in the order they are given. eg:\n");
  FUN_010edeb0(param_1,
               "\t# blender --background test.blend --render-frame 1 --render-output \"/tmp\"\n");
  FUN_010edeb0(param_1,
               "\t...will not render to \'/tmp\' because \'--render-frame 1\' renders before the output path is set.\n"
              );
  FUN_010edeb0(param_1,"\t# blender --background --render-output /tmp test.blend --render-frame 1\n"
              );
  FUN_010edeb0(param_1,
               "\t...will not render to \'/tmp\' because loading the blend-file overwrites the render output that was set.\n"
              );
  FUN_010edeb0(param_1,"\t# blender --background test.blend --render-output /tmp --render-frame 1\n"
              );
  FUN_010edeb0(param_1,"\t...works as expected.\n");
  FUN_010edeb0(param_1,"\n");
  FUN_010edeb0(param_1,"Environment Variables:\n");
  FUN_010edeb0(param_1,"  $BLENDER_USER_RESOURCES  Replace default directory of all user files.\n");
  FUN_010edeb0(param_1,
               "                           Other \'BLENDER_USER_*\' variables override when set.\n")
  ;
  FUN_010edeb0(param_1,"  $BLENDER_USER_CONFIG     Directory for user configuration files.\n");
  FUN_010edeb0(param_1,"  $BLENDER_USER_SCRIPTS    Directory for user scripts.\n");
  FUN_010edeb0(param_1,"  $BLENDER_USER_EXTENSIONS Directory for user extensions.\n");
  FUN_010edeb0(param_1,
               "  $BLENDER_USER_DATAFILES  Directory for user data files (icons, translations, ..).\n"
              );
  FUN_010edeb0(param_1,"\n");
  FUN_010edeb0(param_1,
               "  $BLENDER_SYSTEM_RESOURCES  Replace default directory of all bundled resource files.\n"
              );
  FUN_010edeb0(param_1,"  $BLENDER_SYSTEM_SCRIPTS    Directories to add extra scripts.\n");
  FUN_010edeb0(param_1,"  $BLENDER_SYSTEM_EXTENSIONS Directory for system extensions repository.\n")
  ;
  FUN_010edeb0(param_1,"  $BLENDER_SYSTEM_DATAFILES  Directory to replace bundled datafiles.\n");
  FUN_010edeb0(param_1,
               "  $BLENDER_SYSTEM_PYTHON     Directory to replace bundled Python libraries.\n");
  FUN_010edeb0(param_1,
               "  $BLENDER_CUSTOM_SPLASH     Full path to an image that replaces the splash screen.\n"
              );
  FUN_010edeb0(param_1,
               "  $BLENDER_CUSTOM_SPLASH_BANNER Full path to an image to overlay on the splash screen.\n"
              );
  FUN_010edeb0(param_1,
               "  $BLENDER_OCIO              Path to override the OpenColorIO configuration file.\n                             If not set, the \'OCIO\' environment variable is used.\n"
              );
  if (cVar3 == '\0') {
    if (param_2 == '\0') {
      FUN_010edeb0(param_1,
                   "  $SPNAV_SOCKET              The socket path to connect to the 3D-mouse daemon (Unix only).\n"
                  );
    }
    else if (param_2 != '\0') {
      FUN_010edeb0(param_1,
                   "  $SPNAV_SOCKET              The socket path to connect to the 3D-mouse daemon (Unix only).\n"
                  );
      FUN_010edeb0(param_1,"  $TEMP                      Store temporary files here (MS-Windows).\n"
                  );
    }
  }
  else {
    if (param_2 == '\0') {
      FUN_010edeb0(param_1,"  $TEMP                      Store temporary files here (MS-Windows).\n"
                  );
      goto LAB_0078d591;
    }
    FUN_010edeb0(param_1,
                 "  $SPNAV_SOCKET              The socket path to connect to the 3D-mouse daemon (Unix only).\n"
                );
    FUN_010edeb0(param_1,"  $TEMP                      Store temporary files here (MS-Windows).\n");
  }
  FUN_010edeb0(param_1,"  $TMPDIR                    Store temporary files here (UNIX Systems).\n");
LAB_0078d591:
  FUN_010edeb0(param_1,
               "                             The path must reference an existing directory or it will be ignored.\n"
              );
  return;
}

