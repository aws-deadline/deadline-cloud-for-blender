# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

"""
deadline_settings.py

This file contains the Blender UI code for building and drawing the Deadline Settings sub-panel.
"""

try:
    import bpy
except ImportError:  # pragma: no cover
    raise OSError("Could not find the Blender module. Are you running this inside of Blender?")

from .common import DEADLINE_PT_PANEL_NAME, SERVICE_NAME, section_label


class DEADLINE_PT_Deadline_Settings(bpy.types.Panel):
    bl_idname = "PROPERTIES_PT_DeadlineSettings"
    bl_options = {"DEFAULT_CLOSED"}
    bl_label = "Deadline Settings"
    bl_parent_id = DEADLINE_PT_PANEL_NAME
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"

    def draw(self, context):
        layout = self.layout
        wm = context.window_manager

        layout.use_property_split = True
        layout.use_property_decorate = False

        col = layout.column()

        # Submission Settings
        sub_col = col.column(align=True)
        section_label(sub_col, "Submission Settings")
        row = sub_col.row(align=True)
        row.prop(wm, "deadline_job_name", text="Name")

        sub_col.prop(wm, "deadline_job_description", text="Description")

        sub_col.separator()

        # Amazon Deadline Cloud Settings
        sub_col = col.column(align=False)
        section_label(sub_col, f"{SERVICE_NAME} Settings")

        sub_col.prop(wm, "deadline_farm")
        sub_col.prop(wm, "deadline_queue")
        sub_col.prop(wm, "deadline_storage_profile")

        enabled_section = sub_col.row(align=True)
        enabled_section.alignment = "RIGHT"
        enabled_section.operator("deadline.refresh_deadline")
        enabled_section.enabled = wm.deadline_logged_in

        sub_col.separator()

        sub_col = col.column(align=False)
        sub_col.prop(wm, "deadline_submission_status")
        sub_col.prop(wm, "deadline_max_retries_per_task")
        sub_col.prop(wm, "deadline_priority")
        sub_col.prop(wm, "deadline_max_failed_tasks_count")

        sub_col.separator()

        # Installation Requirements
        row = sub_col.row(align=True, heading="Override Installation Requirements")
        row.prop(wm, "deadline_override_installation_requirements", text="")

        enabled_section = row.row(align=True)
        enabled_section.prop(wm, "deadline_installation_requirements", text="")
        enabled_section.enabled = wm.deadline_override_installation_requirements

    def execute(self, context):
        return {"FINISHED"}
