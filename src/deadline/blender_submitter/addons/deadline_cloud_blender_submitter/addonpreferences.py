# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

"""
This file contains the AddonPreferences for the deadline submitter ui.
"""

from bpy.props import BoolProperty, EnumProperty, StringProperty
from bpy.types import AddonPreferences


# Addon preferences / layout
class DEADLINE_CLOUD_AddonPreferences(AddonPreferences):
    """NOTE: not currently used."""

    # this must match the add-on name, use '__package__'
    # when defining this in a submodule of a python package.
    bl_idname = __package__

    # TODO: Will need to be a dynamic selection

    job_history: StringProperty(  # type: ignore
        name="Job History Dir",
        default="",
    )
    user_identities: EnumProperty(  # type: ignore
        name="User Identities",
        description="User Identities",
        items=[("op1", "False", ""), ("op2", "True", "")],
    )
    auto_accept_confirm_prompt: BoolProperty(name="Auto Accept Confirmation Prompts")  # type: ignore
    current_logging_level: EnumProperty(  # type: ignore
        name="Current Logging Level",
        description="Current Logging Level",
        items=[("op1", "Debug", ""), ("op2", "None", "")],
    )

    def draw(self, context):
        """
        This draw builds the AddonPreferences ui in
        settings > preferences > addons > Deadline Cloud Submitter Addon
        """
        layout = self.layout
        layout.label(text="This is a preferences view for our add-on")
        box = layout.box()
        box.label(text="Global Settings:")
        row = box.row()
        split = row.split(factor=0.9)
        split.prop(context.scene, "aws_profile")
        split.operator("ops.dlcloud_add_to_aws_profile", icon="FILE_REFRESH")

        box = layout.box()
        box.label(text="Profile Settings:")
        row = box.row()
        split = row.split(factor=0.9)
        split.prop(self, "job_history")
        split.operator("ops.dlcloud_get_job_history_dir", text="", icon="FOLDER_REDIRECT")
        row = box.row()
        split = row.split(factor=0.9)
        split.prop(context.scene, "default_farm")
        split.operator("ops.dlcloud_add_to_default_farm", icon="FILE_REFRESH")
        row = box.row()
        row.prop(self, "user_identities")

        box = layout.box()
        box.label(text="Farm Settings:")
        row = box.row()
        split = row.split(factor=0.9)
        split.prop(context.scene, "default_queue")
        split.operator("ops.dlcloud_add_to_default_queue", icon="FILE_REFRESH")

        box = layout.box()
        box.label(text="General Settings:")
        row = box.row()
        row.prop(self, "auto_accept_confirm_prompt")
        row = box.row()
        row.prop(self, "current_logging_level")
