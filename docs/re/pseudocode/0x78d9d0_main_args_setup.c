// REA procedure_pseudo_code (Ghidra 12.1.4) on blender 5.2.2 LTS, sha256 bafec183e960819c76fe213c000cdb2284c53a87ef6791812f8728b51f07145b
// evidence: docs/re/evidence/rea-session/51-c-bg2.json (ev_438f6e482bc8c8ac2f23893e03fa1422ca3fec0ceafa520c3da541a455dbaadf)
// Source identification (by anchor strings, matched against tag v5.2.2): main_args_setup

void FUN_0078d9d0(undefined8 param_1,undefined8 param_2,char param_3)

{
  char *pcVar1;
  undefined8 extraout_RDX;
  code *pcVar2;
  
  FUN_010ee080(param_2,0xffffffff);
  FUN_010ee1d0(param_2,&DAT_07f1efe9,0,
               "\n\tEnd option processing, following arguments passed unchanged. Access via Python\'s \'sys.argv\'."
               ,FUN_00789aa0,0);
  FUN_010ee080(param_2,1);
  FUN_010ee1d0(param_2,0,"--python-use-system-env",
               "\n\tAllow Python to use system environment variables such as \'PYTHONPATH\'.\n\tThis also enables user environment, see: \'--python-use-user-env\'."
               ,FUN_0078ac70,0);
  FUN_010ee1d0(param_2,0,"--python-use-user-env",
               "\n\tAllow Python to use user\'s site-packages directory.\n\tThis disables full isolation for the Python environment."
               ,FUN_0078ac60,0);
  FUN_010ee1d0(param_2,0,"--env-system-datafiles",
               "\n\tSet the BLENDER_SYSTEM_DATAFILES environment variable.",FUN_0078aba0,0);
  FUN_010ee1d0(param_2,0,"--env-system-scripts",
               "\n\tSet the BLENDER_SYSTEM_SCRIPTS environment variable.",FUN_0078aba0,0);
  FUN_010ee1d0(param_2,0,"--env-system-python",
               "\n\tSet the BLENDER_SYSTEM_PYTHON environment variable.",FUN_0078aba0,0);
  FUN_010ee1d0(param_2,0,"--env-system-extensions",
               "\n\tSet the BLENDER_SYSTEM_EXTENSIONS environment variable.",FUN_0078aba0,0);
  FUN_010ee1d0(param_2,&DAT_07ef1558,"--threads",
               "<threads>\n\tUse amount of <threads> for rendering and other operations\n\t[1-1024], 0 to use the system\'s processor count."
               ,FUN_0078b7f0,0);
  FUN_010ee1d0(param_2,0,"--log",
               "<match>\n\tEnable logging categories, taking a single comma separated argument.\n\n\t--log \"*\": log everything\n\t--log \"event\": logs every category starting with \'event\'.\n\t--log \"render,cycles\": log both render and cycles messages.\n\t--log \"*mesh*\": log every category containing \'mesh\' sub-string.\n\t--log \"*,^operator\": log everything except operators, with \'^prefix\' to exclude."
               ,FUN_0078b040,param_2);
  FUN_010ee1d0(param_2,0,"--log-level",
               "<level>\n\tSet the logging verbosity level.\n\n\tfatal: Fatal errors only\n\terror: Errors only\n\twarning: Warnings\n\tinfo: Information about devices, files, configuration, operations\n\tdebug: Verbose messages for developers\n\ttrace: Very verbose code execution tracing"
               ,FUN_0078c0a0,param_2);
  FUN_010ee1d0(param_2,0,"--log-show-source","\n\tShow source file and function name in output.",
               FUN_0078ab80,param_2);
  FUN_010ee1d0(param_2,0,"--log-show-backtrace",
               "\n\tShow a back trace for each log message (debug builds only).",FUN_0078ab60,
               param_2);
  FUN_010ee1d0(param_2,0,"--log-show-memory","\n\tShow memory usage for each log message.",
               FUN_0078ab40,param_2);
  FUN_010ee1d0(param_2,0,"--log-file","<filepath>\n\tSet a file to output the log to.",FUN_0078af60,
               param_2);
  pcVar1 = "\n\tForce to use a specific GPU backend. Valid options: \'opengl\' or \'vulkan\'.";
  if (param_3 != '\0') {
    pcVar1 = 
    "\n\tForce to use a specific GPU backend. Valid options: \'vulkan\',  \'metal\',  \'opengl\'.";
  }
  FUN_010ee1d0(param_2,0,"--gpu-backend",pcVar1,FUN_0078aa50,0);
  FUN_010ee1d0(param_2,0,"--gpu-device",
               "<device>\n\tSelect a specific GPU device, overriding the GPU device from user preferences for this\n\trun only. Accepted forms:\n\n\t* \'<vendor-hex>/<device-hex>/<index-hex>\' (matches the identifier used in user\n\t  preferences, with vendor PCI ID, device PCI ID and enumeration index all hex-encoded).\n\t* \'<index>\' (no slashes) picks the Nth supported device by enumeration order, decimal.\n\t* \'help\' prints supported Vulkan devices and exits.\n\n\tOnly used with the Vulkan backend. Other backends print a warning and ignore this option.\n\tIf the requested Vulkan device is unavailable, Blender falls back to the saved GPU\n\tpreference unless \'--gpu-device-no-fallback\' is also set."
               ,FUN_0078b8b0,0);
  FUN_010ee1d0(param_2,0,"--gpu-device-no-fallback",
               "\n\tFail instead of falling back when \'--gpu-device\' does not match a usable Vulkan device."
               ,FUN_00789b90,0x40000000);
  FUN_010ee1d0(param_2,0,"--gpu-vsync",
               "\n\tSet the VSync.\n\tValid options are: \'on\', \'off\' & \'auto\' for adaptive sync.\n\n\t* The default settings depend on the GPU driver.\n\t* Disabling VSync can be useful for testing performance.\n\t* \'auto\' is only supported by the OpenGL backend."
               ,FUN_0078a980,0);
  FUN_010ee1d0(param_2,0,"--gpu-compilation-subprocesses",
               "\n\tOverride the Max Compilation Subprocesses setting (OpenGL only).",FUN_0078bb50,0
              );
  FUN_010ee1d0(param_2,0,"--profile-gpu",
               "\n\tEnable CPU & GPU performance profiling for GPU debug groups\n\t(Outputs a profile.json file in the Trace Event Format to the current directory)"
               ,FUN_00789cc0,0);
  FUN_010ee080(param_2,2);
  FUN_010ee1d0(param_2,&DAT_07e25b24,&DAT_07e25a59,"\n\tPrint this help text and exit.",FUN_0078d630
               ,param_2);
  FUN_010ee1d0(param_2,&DAT_07e25a60,0,"\n\tPrint this help text and exit (Windows only).",
               FUN_0078d630,param_2);
  FUN_010ee1d0(param_2,&DAT_07e25b27,"--version","\n\tPrint Blender version and exit.",FUN_0078a850,
               0);
  FUN_010ee1d0(param_2,0,"--log-list-categories",
               "\n\tList all available logging categories for \'--log\', and exit.\n",FUN_0078a830,0
              );
  FUN_010ee1d0(param_2,"-y","--enable-autoexec","\n\tEnable automatic Python script execution.",
               FUN_00789ab0,1);
  FUN_010ee1d0(param_2,&DAT_07e82983,"--disable-autoexec",
               "\n\tDisable automatic Python script execution (Python-drivers & startup scripts), (default)."
               ,FUN_00789ab0,0);
  FUN_010ee1d0(param_2,0,"--offline-mode","\n\tDisallow internet access, overriding the preference."
               ,FUN_00789ae0,0);
  FUN_010ee1d0(param_2,0,"--online-mode","\n\tAllow internet access, overriding the preference.",
               FUN_00789ae0,1);
  FUN_010ee1d0(param_2,0,"--console-crash-handler","\n\tUse the console to report crashes.",
               FUN_00789b20,0);
  FUN_010ee1d0(param_2,0,"--disable-crash-handler","\n\tDisable the crash handler.",FUN_00789b30,0);
  FUN_010ee1d0(param_2,0,"--disable-abort-handler","\n\tDisable the abort handler.",FUN_00789b40,0);
  FUN_010ee1d0(param_2,"-q","--quiet",
               "\n\tSuppress status printing (warnings & errors are still printed).",FUN_0078a4d0,0)
  ;
  FUN_010ee1d0(param_2,"-b","--background",
               "\n\tRun in background (often used for UI-less rendering).\n\n\tThe audio device is disabled in background-mode by default\n\tand can be re-enabled by passing in \'-setaudio Default\' afterwards."
               ,FUN_0078a7d0,0);
  FUN_010ee1d0(param_2,"-c","--command",
               "<command>\n\tRun a command which consumes all remaining arguments.\n\tUse \'-c help\' to list all other commands.\n\tPass \'--help\' after the command to see its help text.\n\n\tThis implies \'--background\' mode."
               ,FUN_0078a6b0,param_1);
  FUN_010ee1d0(param_2,0,"--qos",
               "<level>\n\tSet the Quality of Service (QoS) mode for hybrid CPU architectures (Windows only).\n\n\tdefault: Uses the default behavior of the OS.\n\thigh: Always makes use of performance cores.\n\teco: Schedules Blender threads exclusively to efficiency cores."
               ,FUN_0078ac80,0);
  FUN_010ee1d0(param_2,0,"--disable-depsgraph-on-file-load",
               "\n\tBackground mode: Do not systematically build and evaluate ViewLayers\' dependency graphs\n\twhen loading a blend-file in background mode (\'-b\' or \'-c\' options).\n\n\tScripts requiring evaluated data then need to explicitly ensure that\n\tan evaluated depsgraph is available\n\t(e.g. by calling \'depsgraph = context.evaluated_depsgraph_get()\').\n\n\tNOTE: this is a temporary option, in the future depsgraph will never be\n\tautomatically generated on file load in background mode."
               ,FUN_00789b50,0);
  FUN_010ee1d0(param_2,0,"--disable-liboverride-auto-resync",
               "\n\tDo not perform library override automatic resync when loading a new blend-file.\n\n\tNOTE: this is an alternative way to get the same effect as when setting the\n\t\'No Override Auto Resync\' User Preferences Debug option."
               ,FUN_00789b70,0);
  FUN_010ee1d0(param_2,&DAT_07e254aa,0,
               "<options> <file(s)>\n\tInstead of showing Blender\'s user interface, this runs Blender as an animation player,\n\tto view movies and image sequences rendered in Blender (ignored if \'-b\' is set).\n\n\tPlayback Arguments:\n\n\t-p <sx> <sy>\n\t\tOpen with lower left corner at <sx>, <sy>.\n\t-m\n\t\tRead from disk (Do not buffer).\n\t-f <fps> <fps_base>\n\t\tSpecify FPS to start with.\n\t-j <frame>\n\t\tSet frame step to <frame>.\n\t-s <frame>\n\t\tPlay from <frame>.\n\t-e <frame>\n\t\tPlay until <frame>.\n\t-c <cache_memory>\n\t\tAmount of memory in megabytes to allow for caching images during playback.\n\t\tZero disables (clamping to a fixed number of frames instead)."
               ,FUN_0078af30,0);
  FUN_010ee1d0(param_2,&DAT_07e25b2a,"--debug",
               "\n\tTurn debugging on.\n\n\t* Enables memory error detection\n\t* Disables mouse grab (to interact with a debugger in some cases)\n\t* Keeps Python\'s \'sys.stdin\' rather than setting it to None"
               ,FUN_0078a640,param_2);
  FUN_010ee1d0(param_2,0,"--debug-ffmpeg",
               "\n\tEnable debug messages from FFmpeg video input and output.",FUN_0078a470,0);
  FUN_010ee1d0(param_2,0,"--debug-freestyle","\n\tEnable debug messages for Freestyle.",FUN_00789b90
               ,0x80);
  FUN_010ee1d0(param_2,0,"--debug-python","\n\tEnable debug messages for Python.",FUN_00789b90,4);
  FUN_010ee1d0(param_2,0,"--debug-events","\n\tEnable debug messages for the event system.",
               FUN_00789b90,8);
  FUN_010ee1d0(param_2,0,"--debug-handlers","\n\tEnable debug messages for event handling.",
               FUN_00789b90,0x10);
  FUN_010ee1d0(param_2,0,"--debug-wm",
               "\n\tEnable debug messages for the window manager, shows all operators in search, shows keymap errors."
               ,FUN_00789b90,0x20);
  FUN_010ee1d0(param_2,0,"--debug-xr",
               "\n\tEnable debug messages for virtual reality contexts.\n\tEnables the OpenXR API validation layer, (OpenXR) debug messages and general information prints."
               ,FUN_00789b90,0x1000000);
  FUN_010ee1d0(param_2,0,"--debug-xr-time",
               "\n\tEnable debug messages for virtual reality frame rendering times.",FUN_00789b90,
               0x2000000);
  FUN_010ee1d0(param_2,0,"--debug-ghost","\n\tEnable debug messages for Ghost (Linux only).",
               FUN_00789b90,0x4000000);
  FUN_010ee1d0(param_2,0,"--debug-wintab","\n\tEnable debug messages for Wintab.",FUN_00789b90,
               0x8000000);
  FUN_010ee1d0(param_2,0,"--debug-all","\n\tEnable all debug messages.",FUN_0078a600,0);
  FUN_010ee1d0(param_2,0,"--debug-io","\n\tEnable debug messages for I/O.",FUN_00789ba0,0);
  FUN_010ee1d0(param_2,0,"--debug-fpe","\n\tEnable floating-point exceptions.",FUN_0078a630,0);
  FUN_010ee1d0(param_2,0,"--debug-libmv","\n\tEnable debug messages from libmv library.",
               FUN_0078a5f0,0);
  FUN_010ee1d0(param_2,0,"--debug-cycles","\n\tEnable debug messages from Cycles.",FUN_0078a450,0);
  FUN_010ee1d0(param_2,0,"--debug-memory",
               "\n\tEnable fully guarded memory allocation and debugging.",FUN_00789bc0,0);
  FUN_010ee1d0(param_2,0,"--debug-value","<value>\n\tSet debug value of <value> on startup.",
               FUN_0078bda0,0);
  FUN_010ee1d0(param_2,0,"--debug-jobs","\n\tEnable time profiling for background jobs.",
               FUN_00789b90,0x40);
  FUN_010ee1d0(param_2,0,"--debug-gpu",
               "\n\tEnable GPU debug context and information for OpenGL 4.3+.",FUN_0078a420,0);
  FUN_010ee1d0(param_2,0,"--debug-gpu-compile-shaders",
               "\n\tCompile all statically defined shaders to test platform compatibility.",
               FUN_00789be0,0);
  FUN_010ee1d0(param_2,0,"--debug-gpu-no-texture-pool",
               "\n\tDisable memory aliasing optimizations in the GPU texture pool.",FUN_00789c40,0);
  FUN_010ee1d0(param_2,0,"--debug-gpu-scope-capture",
               "\n\tCapture the GPU commands issued inside the given scope name.",FUN_0078b340,0);
  FUN_010ee1d0(param_2,0,"--debug-gpu-shader-source",
               "\n\tSave the compiled GPU shader source code for the given shader name.\n\tThe given name can contain leading or trailing wildcard \"*\" to match multiple shaders.\n\tFiles are saved in the current working directory inside a directory named \"Shaders\"."
               ,FUN_0078b2e0,0);
  FUN_010ee1d0(param_2,0,"--debug-gpu-shader-no-preprocessor",
               "\n\tSkip preprocessor pass and rely on driver or shader compiler preprocessor instead.\n\tAlso disable dead code elimination."
               ,FUN_00789c00,0);
  FUN_010ee1d0(param_2,0,"--debug-gpu-shader-no-dce","\n\tSkip dead code elimination pass.",
               FUN_00789c20,0);
  if (param_3 != '\0') {
    FUN_010ee1d0(param_2,0,"--debug-gpu-renderdoc",
                 "\n\tEnable RenderDoc integration for GPU frame grabbing and debugging.",
                 FUN_0078a5c0,0);
  }
  FUN_010ee1d0(param_2,0,"--debug-gpu-shader-debug-info",
               "\n\tEnable shader debug info generation (Vulkan only).",FUN_00789c60,0);
  FUN_010ee1d0(param_2,0,"--debug-depsgraph","\n\tEnable all debug messages from dependency graph.",
               FUN_00789b90,0x4f00);
  FUN_010ee1d0(param_2,0,"--debug-depsgraph-build",
               "\n\tEnable debug messages from dependency graph related on graph construction.",
               FUN_00789b90,0x100);
  FUN_010ee1d0(param_2,0,"--debug-depsgraph-eval",
               "\n\tEnable debug messages from dependency graph related on evaluation.",FUN_00789b90
               ,0x200);
  FUN_010ee1d0(param_2,0,"--debug-depsgraph-tag",
               "\n\tEnable debug messages from dependency graph related on tagging.",FUN_00789b90,
               0x400);
  FUN_010ee1d0(param_2,0,"--debug-depsgraph-time",
               "\n\tEnable debug messages from dependency graph related on timing.",FUN_00789b90,
               0x800);
  FUN_010ee1d0(param_2,0,"--debug-depsgraph-no-threads",
               "\n\tSwitch dependency graph to a single threaded evaluation.",FUN_00789b90,0x1000);
  FUN_010ee1d0(param_2,0,"--debug-depsgraph-pretty",
               "\n\tEnable colors for dependency graph debug messages.",FUN_00789b90,0x2000);
  FUN_010ee1d0(param_2,0,"--debug-depsgraph-uid",
               "\n\tVerify validity of session-wide identifiers assigned to ID data-blocks.",
               FUN_00789b90,0x4000);
  FUN_010ee1d0(param_2,0,"--debug-gpu-force-workarounds",
               "\n\tEnable workarounds for typical GPU issues and disable all GPU extensions.",
               FUN_00789b90,0x40000);
  FUN_010ee1d0(param_2,0,"--debug-gpu-vulkan-local-read",
               "\n\tForce Vulkan dynamic rendering local read when supported by device.",
               FUN_00789b90,0x80000);
  FUN_010ee1d0(param_2,0,"--debug-exit-on-error",
               "\n\tImmediately exit when internal errors are detected.",FUN_0078a580,0);
  FUN_010ee1d0(param_2,0,"--verbose",
               "<verbose>\n\tSet the logging verbosity level for debug messages that support it.",
               FUN_0078bc10,0);
  FUN_010ee1d0(param_2,0,"--app-template",
               "<template>\n\tSet the application template (matching the directory name), use \'default\' for none."
               ,FUN_0078aed0,0);
  FUN_010ee1d0(param_2,&DAT_07e8297a,"--factory-startup",
               "\n\tSkip reading the \'startup.blend\' in the user\'s home directory.",FUN_00789c80,
               0);
  FUN_010ee1d0(param_2,0,"--enable-event-simulate",
               "\n\tEnable event simulation testing feature \'bpy.types.Window.event_simulate\'.",
               FUN_00789ca0,0);
  FUN_010ee080(param_2,3);
  FUN_010ee1d0(param_2,&DAT_07e25b4b,"--window-geometry",
               "<sx> <sy> <w> <h>\n\tOpen with lower left corner at <sx>, <sy> and width and height as <w>, <h>."
               ,FUN_0078bcc0,0);
  FUN_010ee1d0(param_2,"-w","--window-border",
               "\n\tForce opening with borders, in a normal (non maximized) state.",FUN_0078a570,0);
  FUN_010ee1d0(param_2,&DAT_07e25b4e,"--window-fullscreen","\n\tForce opening full-screen.",
               FUN_0078a560,0);
  FUN_010ee1d0(param_2,&DAT_07e25b51,"--window-maximized","\n\tForce opening maximized.",
               FUN_0078a550,0);
  FUN_010ee1d0(param_2,0,"--no-window-frame","\n\tDisable all window decorations (Linux only).",
               FUN_0078a530,0);
  FUN_010ee1d0(param_2,0,"--no-window-focus",
               "\n\tOpen behind other windows and without taking focus.",FUN_0078a510,0);
  FUN_010ee1d0(param_2,&DAT_07e25b54,"--start-console",
               "\n\tStart with the console window open (ignored if \'-b\' is set), (Windows only).",
               FUN_0078a4f0,0);
  FUN_010ee1d0(param_2,"-r","--register",
               "\n\tRegister blend-file extension for current user, then exit (Windows & Linux only)."
               ,FUN_0078d870,0);
  FUN_010ee1d0(param_2,0,"--register-allusers",
               "\n\tRegister blend-file extension for all users, then exit (Windows & Linux only).",
               FUN_0078d7b0,0);
  FUN_010ee1d0(param_2,0,"--unregister",
               "\n\tUnregister blend-file extension for current user, then exit (Windows & Linux only)."
               ,FUN_0078d700,0);
  FUN_010ee1d0(param_2,0,"--unregister-allusers",
               "\n\tUnregister blend-file extension for all users, then exit (Windows & Linux only)."
               ,FUN_0078d650,0);
  FUN_010ee1d0(param_2,0,"--no-native-pixels",
               "\n\tDo not use native pixel size, for high resolution displays (MacBook \'Retina\')."
               ,FUN_0078a4b0,param_2);
  FUN_010ee080(param_2,4);
  FUN_010ee0f0(param_2,"-noaudio",1,0,0,"\n\tForce sound system to None.",FUN_0078a490,0);
  pcVar2 = FUN_0078ae70;
  FUN_010ee0f0(param_2,"-setaudio",1,0,0,
               "\n\tForce sound system to a specific device.\n\t\'None\' \'Default\' \'SDL\' \'OpenAL\' \'CoreAudio\' \'JACK\' \'PulseAudio\' \'WASAPI\'."
               ,FUN_0078ae70,0);
  FUN_010ee080(param_2,5,extraout_RDX,pcVar2);
  FUN_010ee1d0(param_2,&DAT_07e25b59,"--render-frame",
               "<frame>\n\tRender frame <frame> and save it.\n\n\t* +<frame> start frame relative, -<frame> end frame relative.\n\t* A comma separated list of frames can also be used (no spaces).\n\t* A range of frames can be expressed using \'..\' separator between the first and last frames (inclusive).\n"
               ,FUN_0078c2a0,param_1);
  FUN_010ee1d0(param_2,&DAT_07e254aa,"--render-anim",
               "\n\tRender frames from start to end (inclusive).",FUN_0078a330,param_1);
  FUN_010ee1d0(param_2,&DAT_07e25b5c,"--scene",
               "<name>\n\tSet the active scene <name> for rendering.",FUN_0078adc0,param_1);
  FUN_010ee1d0(param_2,"-s","--frame-start",
               "<frame>\n\tSet start to frame <frame>, supports +/- for relative frames too.",
               FUN_0078c760,param_1);
  FUN_010ee1d0(param_2,&DAT_07e25b5f,"--frame-end",
               "<frame>\n\tSet end to frame <frame>, supports +/- for relative frames too.",
               FUN_0078bf10,param_1);
  FUN_010ee1d0(param_2,&DAT_07e25b62,"--frame-jump",
               "<frames>\n\tSet number of frames to step forward after each rendered frame.",
               FUN_0078c890,param_1);
  FUN_010ee1d0(param_2,&DAT_07e25b65,"--python","<filepath>\n\tRun the given Python script file.",
               FUN_0078b500,param_1);
  FUN_010ee1d0(param_2,0,"--python-text","<name>\n\tRun the given Python script text block.",
               FUN_0078b630,param_1);
  FUN_010ee1d0(param_2,0,"--python-expr",
               "<expression>\n\tRun the given expression as a Python script.\n\n\tThe expression may be a complete multi-line script;\n\tyou are limited only by the platform\'s maximum argument length."
               ,FUN_0078b220,param_1);
  FUN_010ee1d0(param_2,0,"--python-console","\n\tRun Blender with an interactive console.",
               FUN_0078a2d0,param_1);
  FUN_010ee1d0(param_2,0,"--python-exit-code",
               "<code>\n\tSet the exit-code in [0..255] to exit if a Python exception is raised\n\t(only for scripts executed from the command line), zero disables."
               ,FUN_0078be50,0);
  FUN_010ee1d0(param_2,0,"--addons",
               "<addon(s)>\n\tComma separated list (no spaces) of add-ons to enable in addition to any default add-ons."
               ,FUN_0078b120,param_1);
  FUN_010ee1d0(param_2,&DAT_07e25b68,"--render-output",
               "<path>\n\tSet the render path and file name.\n\tUse \'//\' at the start of the path to render relative to the blend-file.\n\n\tYou can use path templating features such as \'{blend_name}\' in the path.\n\tSee Blender\'s documentation on path templates for more details.\n\n\tThe \'#\' characters are replaced by the frame number, and used to define zero padding.\n\n\t* \'animation_##_test.png\' becomes \'animation_01_test.png\'\n\t* \'test-######.png\' becomes \'test-000001.png\'\n\n\tWhen the filename does not contain \'#\', the suffix \'####\' is added to the filename.\n\n\tThe frame number will be added at the end of the filename, eg:\n\t# blender -b animation.blend -o //render_ -F PNG -x 1 -a\n\t\'//render_\' becomes \'//render_####\', writing frames as \'//render_0001.png\'"
               ,FUN_0078b3a0,param_1);
  FUN_010ee1d0(param_2,&DAT_07f4e71c,"--engine",
               "<engine>\n\tSpecify the render engine.\n\tUse \'-E help\' to list available engines."
               ,FUN_00789ec0,param_1);
  FUN_010ee1d0(param_2,"-F","--render-format",
               "<format>\n\tSet the render format.\n\tValid options are:\n\t\'TGA\' \'RAWTGA\' \'JPEG\' \'IRIS\' \'PNG\' \'BMP\' \'HDR\' \'TIFF\'.\n\n\tFormats that can be compiled into Blender, not available on all systems:\n\t\'OPEN_EXR\' \'OPEN_EXR_MULTILAYER\' \'FFMPEG\' \'CINEON\' \'DPX\' \'JP2\' \'WEBP\'."
               ,FUN_0078ace0,param_1);
  FUN_010ee1d0(param_2,&DAT_07e2f934,"--use-extension",
               "<bool>\n\tSet option to add the file extension to the end of the file.",FUN_0078b550
               ,param_1);
  FUN_010ee1d0(param_2,0,"--open-last",
               "\n\tOpen the most recently opened blend file, instead of the default startup file.",
               FUN_00789e50,param_1);
  DAT_0b54eb60 = FUN_0078ea30;
  return;
}

