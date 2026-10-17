# Operator cross-check: binary vs runtime (Blender 5.2.2 LTS, build d13f752e3b9c)

| set | count |
|---|---:|
| `XXX_OT_*` idname strings found in the binary | 2247 |
| operators registered at runtime (`bpy.ops`, factory startup, `-b`) | 2498 |
| in both | 2237 |
| runtime only, defined in bundled Python scripts | 260 |
| runtime only, not found in bundled scripts | 1 |
| binary only (compiled in, not registered in this session) | 10 |

## Runtime-only operators not explained by bundled scripts

- `curve.draw`


## Binary-only operators by module

| module | count |
|---|---:|
| `view3d` | 3 |
| `paint` | 2 |
| `anim` | 1 |
| `outliner` | 1 |
| `rigidbody` | 1 |
| `sequencer` | 1 |
| `wm` | 1 |

## Binary-only operators

- `anim.channels` (`ANIM_OT_channels`)
- `outliner.lib_reload` (`OUTLINER_OT_lib_reload`)
- `paint.brush_select` (`PAINT_OT_brush_select`)
- `paint.face_select` (`PAINT_OT_face_select`)
- `rigidbody.world_export` (`RIGIDBODY_OT_world_export`)
- `sequencer.select_inverse` (`SEQUENCER_OT_select_inverse`)
- `view3d.vr_location_scouting_add_camera_from_capture` (`VIEW3D_OT_vr_location_scouting_add_camera_from_capture`)
- `view3d.vr_location_scouting_add_marker_from_capture` (`VIEW3D_OT_vr_location_scouting_add_marker_from_capture`)
- `view3d.vr_location_scouting_browse_captures` (`VIEW3D_OT_vr_location_scouting_browse_captures`)
- `wm.context_` (`WM_OT_context_`)
