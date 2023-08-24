# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

"""
asset_settings.py

This file contains the Blender UI code for building and drawing Asset Settings sub-panel.
"""

import os

try:
    import bpy
except ImportError:  # pragma: no cover
    raise OSError("Could not find the Blender module. Are you running this inside of Blender?")

from .common import DEADLINE_PT_PANEL_NAME


class DEADLINE_UL_Job_Attachments(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname):
        self.use_filter_show = True

        layout.use_property_split = True

        if self.layout_type in {"DEFAULT", "COMPACT"}:
            icon = self.get_icon(item.path)
            name = layout.row()
            name.label(text=item.name, icon=icon)

            path = layout.row()
            path.label(text=item.path)

    def get_icon(self, filepath):
        """
        Return a Blender icon enum based on the extension of the provided filepath.
        """
        name, ext = os.path.splitext(filepath)

        ext = ext.lower()
        if ext in bpy.path.extensions_audio:
            return "PLAY_SOUND"
        elif ext in bpy.path.extensions_image:
            return "IMAGE_DATA"
        elif ext in bpy.path.extensions_movie:
            return "FILE_MOVIE"
        elif ext == ".blend":
            return "BLENDER"
        elif ext == ".vdb":
            return "FILE_VOLUME"
        elif ext == ".abc":
            return "MESH_CUBE"
        elif ext in [".txt", ".py", ".json"]:
            return "FILE_TEXT"
        else:
            return "FILE_BLANK"


class DEADLINE_UL_Job_Output_Attachments(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname):
        self.use_filter_show = True

        layout.use_property_split = True

        if self.layout_type in {"DEFAULT", "COMPACT"}:
            name = layout.row()
            name.label(text=item.name)


class DEADLINE_PT_Asset_Settings(bpy.types.Panel):
    bl_idname = "PROPERTIES_PT_AssetAttachments"
    bl_options = {"DEFAULT_CLOSED"}
    bl_label = "Assets"
    bl_parent_id = DEADLINE_PT_PANEL_NAME
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"

    def draw(self, context):
        layout = self.layout
        wm = context.window_manager

        layout.use_property_split = False

        col = layout.column()

        top = col.column()
        top.label(text="Project Job Attachments")
        split = top.row()
        left = split.box()
        left.template_list(
            "DEADLINE_UL_Job_Attachments",  # listtype_name
            "project_assets",  # list_id
            wm,  # dataptr: Data from which to take the property,
            "deadline_job_attachments",  # propname: propertyname,
            wm,  # active_dataptr: data from which to take the integer property of active data
            "deadline_job_attachments_index",  # active_propname: Identifier of the integer property in active data
            item_dyntip_propname="File",  # item_dyntip_propname='',
            rows=5,  # rows=5,
        )

        right = split.column()
        right.ui_units_x = 6

        right.alignment = "RIGHT"

        right.operator("deadline.remove_assets")
        right.operator("deadline.parse_assets")
        right.operator("deadline.clear_assets")

        top = col.column()
        top.label(text="User Job Attachments")
        split = top.row()
        left = split.box()
        left.template_list(
            "DEADLINE_UL_Job_Attachments",  # listtype_name
            "user_assets",  # list_id
            wm,  # dataptr: Data from which to take the property,
            "deadline_user_job_attachments",  # propname: propertyname,
            wm,  # active_dataptr: data from which to take the integer property of active data
            "deadline_user_job_attachments_index",  # active_propname: Identifier of the integer property in active data
            item_dyntip_propname="File",  # item_dyntip_propname='',
            rows=5,  # rows=5,
        )

        right = split.column()
        right.ui_units_x = 6

        right.alignment = "RIGHT"

        right.operator("deadline.user_asset_selector")
        right.operator("deadline.remove_user_assets")
        right.operator("deadline.clear_user_assets")

        bot = col.column()
        bot.label(text="Job Output Attachments")
        split = bot.row()
        left = split.box()
        left.template_list(
            "DEADLINE_UL_Job_Output_Attachments",  # listtype_name
            "job_outputs",  # list_id
            wm,  # dataptr: Data from which to take the property,
            "deadline_job_output_attachments",  # propname: propertyname,
            wm,  # active_dataptr: data from which to take the integer property of active data
            "deadline_job_output_attachments_index",  # active_propname: Identifier of the integer property in active data
            item_dyntip_propname="Outputs",  # item_dyntip_propname='',
            rows=5,  # rows=5,
        )
        right = split.column()
        right.ui_units_x = 6
        right.alignment = "RIGHT"
        right.operator("deadline.add_job_output_attachments")
        right.operator("deadline.remove_job_output_attachments")
        right.operator("deadline.clear_job_output_attachments")

    def execute(self, context):
        return {"FINISHED"}
