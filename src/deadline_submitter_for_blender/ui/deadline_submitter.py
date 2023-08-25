# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

"""
deadline_submitter.py

This file contains the Blender UI code for building and drawing the main Submitter UI and submit button.
"""

import os
from typing import Any, Dict

try:
    import bpy
    import bpy.utils.previews
except ImportError:  # pragma: no cover
    raise OSError("Could not find the Blender module. Are you running this inside of Blender?")

from .components.asset_settings import (
    DEADLINE_PT_Asset_Settings,
    DEADLINE_UL_Job_Attachments,
    DEADLINE_UL_Job_Output_Attachments,
)
from .components.deadline_settings import DEADLINE_PT_Deadline_Settings
from .components.common import DEADLINE_PT_PANEL_NAME, SERVICE_NAME
from .components.import_export import DEADLINE_PT_Import_Export
from .components.scene_settings import DEADLINE_PT_Scene_Settings

preview_collections: Dict[str, Any] = {}


class DEADLINE_PT_Panel(bpy.types.Panel):
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "output"
    bl_category = f"{SERVICE_NAME}"
    bl_idname = DEADLINE_PT_PANEL_NAME
    bl_label = f"{SERVICE_NAME} Render Submitter"

    @classmethod
    def poll(self, context):
        return True

    def draw(self, context):
        layout = self.layout
        wm = context.window_manager

        layout.use_property_split = True

        obj_prev = preview_collections["logo"]

        box = layout.box()
        col = box.column()
        row = col.row()
        logo = obj_prev["logo"]
        row.label(text="", icon_value=logo.icon_id)
        row.label(text=f"{SERVICE_NAME}")

        col.separator()

        sub_col = col.column(align=True)
        row = sub_col.row(align=True)
        row.prop(wm, "deadline_profiles")
        row = sub_col.row(align=True)
        row.enabled = False
        row.prop(wm, "deadline_creds")
        row = sub_col.row(align=True)
        row.enabled = False
        row.prop(wm, "deadline_status")
        row = sub_col.row(align=True)
        row.enabled = False
        row.prop(wm, "deadline_api_status")

        col.separator()

        row = col.row(align=True)
        row.alignment = "CENTER"
        row.operator("deadline.login", text="Login")
        row.separator()
        row.operator("deadline.logout", text="Logout")

    def execute(self, context):
        return {"FINISHED"}


class DEADLINE_PT_Submit(bpy.types.Panel):
    bl_idname = "PROPERTIES_PT_Submit"
    bl_label = "Submit"
    bl_options = {"HIDE_HEADER"}
    bl_parent_id = DEADLINE_PT_PANEL_NAME
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"

    def draw(self, context):
        layout = self.layout
        pcoll = preview_collections["logo"]

        col = layout.column()
        logo = pcoll["logo"]
        col.operator("deadline.submit", icon_value=logo.icon_id)
        col.scale_y = 2

    def execute(self, context):
        return {"FINISHED"}


classes = (
    DEADLINE_PT_Panel,
    DEADLINE_PT_Deadline_Settings,
    DEADLINE_PT_Scene_Settings,
    DEADLINE_PT_Asset_Settings,
    DEADLINE_UL_Job_Attachments,
    DEADLINE_UL_Job_Output_Attachments,
    DEADLINE_PT_Import_Export,
    DEADLINE_PT_Submit,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)

    # get the icon
    obj_prev = bpy.utils.previews.new()
    my_icons_dir = os.path.join(os.path.dirname(__file__), "../icons")

    # load the preview thumbnail of a file and store in the preview collections
    obj_prev.load("logo", os.path.join(my_icons_dir, "logo.png"), "IMAGE")
    preview_collections["logo"] = obj_prev


def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)

    for obj_prev in preview_collections.values():
        bpy.utils.previews.remove(obj_prev)
    preview_collections.clear()
