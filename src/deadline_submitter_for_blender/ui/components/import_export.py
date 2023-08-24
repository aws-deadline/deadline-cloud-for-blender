# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

"""
import_export.py

This file contains the Blender UI code for building and drawing the Import/Export sub-panel.
"""

try:
    import bpy
except ImportError:  # pragma: no cover
    raise OSError("Could not find the Blender module. Are you running this inside of Blender?")

from .common import DEADLINE_PT_PANEL_NAME


class DEADLINE_PT_Import_Export(bpy.types.Panel):
    bl_idname = "PROPERTIES_PT_ImportExport"
    bl_options = {"DEFAULT_CLOSED"}
    bl_label = "Import/Export"
    bl_parent_id = DEADLINE_PT_PANEL_NAME
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"

    def draw(self, context):
        layout = self.layout

        layout.use_property_split = False

        col = layout.column()

        col.operator("deadline.client.export_settings", text="Export")
        col.operator("deadline.client.do_import_prompt", text="Import")

    def execute(self, context):
        return {"FINISHED"}
