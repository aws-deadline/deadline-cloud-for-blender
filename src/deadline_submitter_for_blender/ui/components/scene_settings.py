# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

"""
scene_settings.py

This file contains the Blender UI code for building and drawing the Scene Settings sub-panel.
"""

try:
    import bpy
except ImportError:  # pragma: no cover
    raise OSError("Could not find the Blender module. Are you running this inside of Blender?")

from .common import DEADLINE_PT_PANEL_NAME


class DEADLINE_PT_Scene_Settings(bpy.types.Panel):
    bl_idname = "PROPERTIES_PT_SceneSettings"
    bl_options = {"DEFAULT_CLOSED"}
    bl_label = "Scene Settings"
    bl_parent_id = DEADLINE_PT_PANEL_NAME
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"

    def draw(self, context):
        layout = self.layout
        wm = context.window_manager
        scene = context.scene

        layout.use_property_split = True
        layout.use_property_decorate = False

        col = layout.column()

        col.prop(wm, "deadline_scene")
        col.prop(wm, "deadline_layer")

        row = col.row(align=True, heading="Render Animation")
        row.prop(wm, "deadline_render_animation", text="")

        col.separator()

        row = col.row(align=True, heading="Override Output Path")
        row.prop(wm, "deadline_override_output_path", text="")
        if wm.deadline_override_output_path:
            row.prop(wm, "deadline_output_path", text="")
        else:
            row.label(text=f"{scene.render.filepath}")

        row = col.row(align=True, heading="Override Frame Range")
        row.prop(wm, "deadline_override_frame_range", text="")

        if wm.deadline_override_frame_range:
            row.prop(wm, "deadline_frame_range", text="")
        else:
            row.label(text=f"{scene.frame_start}-{scene.frame_end}")

    def execute(self, context):
        return {"FINISHED"}
