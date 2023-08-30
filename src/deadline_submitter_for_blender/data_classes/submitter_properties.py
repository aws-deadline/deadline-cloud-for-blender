# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

"""
submitter_properties.py

This file defines all properties the Blender Submitter needs to keep track of to handle populating
the Submitter UI and processing a job submissions.
"""

try:
    import bpy
except ImportError:  # pragma: no cover
    raise OSError("Could not find the Blender module. Are you running this inside of Blender?")

from ..utilities.utility_functions import get_profiles_list
import deadline.client


# Enum Callbacks
def profiles_callback(self, conext):
    wm_type = bpy.types.WindowManager
    if not hasattr(wm_type, "deadline_profiles_lookup"):
        wm_type.deadline_profiles_lookup = get_profiles_list()
    return wm_type.deadline_profiles_lookup


def farm_callback(self, context):
    wm_type = bpy.types.WindowManager
    if hasattr(wm_type, "deadline_farm_lookup"):
        return wm_type.deadline_farm_lookup
    else:
        return ()


def queue_callback(self, context):
    wm_type = bpy.types.WindowManager
    wm_instance = context.window_manager
    if hasattr(wm_type, "deadline_queue_lookup"):
        return wm_type.deadline_queue_lookup[wm_instance.deadline_farm]
    else:
        return ()


def storage_profile_callback(self, context):
    wm_type = bpy.types.WindowManager
    wm_instance = context.window_manager
    if hasattr(wm_type, "deadline_storage_profile_lookup"):
        return wm_type.deadline_storage_profile_lookup[
            (wm_instance.deadline_farm, wm_instance.deadline_queue)
        ]
    else:
        return ()


def submission_status_callback(self, context):
    return (
        ("READY", "Ready", "Ready"),
        ("PAUSED", "Paused", "Paused"),
    )


def scene_callback(self, context):
    return [(scene.name, scene.name, scene.name_full) for scene in bpy.data.scenes]


def layer_callback(self, context):
    wm = context.window_manager
    return [
        (layer.name, layer.name, layer.name)
        for layer in bpy.data.scenes[wm.deadline_scene].view_layers
    ]


# Property Groups
class CUSTOM_JobAttachments(bpy.types.PropertyGroup):
    """
    Group of properties representing job attachments
    """

    name: bpy.props.StringProperty(name="Name", description="File Name", default="")  # type: ignore  # noqa
    path: bpy.props.StringProperty(name="Path", description="File Path", default="")  # type: ignore  # noqa


class CUSTOM_JobOutputAttachments(bpy.types.PropertyGroup):
    """
    Group of properties representing job output attachments
    """

    name: bpy.props.StringProperty(name="Name", description="Job output attachment name", default="")  # type: ignore  # noqa


# Properties
def create():  # pragma: no cover
    wm = bpy.types.WindowManager

    creds_status = deadline.client.api.check_credentials_status()
    wm.deadline_logged_in = bpy.props.BoolProperty(
        name="Logged in",
        default=(creds_status == deadline.client.api.AwsCredentialsStatus.AUTHENTICATED),
    )

    wm.deadline_profiles = bpy.props.EnumProperty(
        name="Profile Name",
        items=profiles_callback,
        description="AWS profile to use for cloud companion.",
        default=None,
        options=set(),
        update=None,
        get=None,
        set=None,
    )

    wm.deadline_creds = bpy.props.StringProperty(
        name="Credential Type", default="CLOUD_COMPANION_LOGIN", description="Deadline Credentials"
    )

    wm.deadline_status = bpy.props.StringProperty(
        name="Credential Status",
        default=creds_status.name,
        description="Deadline Credential Status",
    )

    wm.deadline_api_status = bpy.props.StringProperty(
        name="API Status", default="UNAVAILABLE", description="Amazon Deadline Cloud API Status"
    )

    wm.deadline_job_name = bpy.props.StringProperty(
        default="", description="The name of the job to submit to Amazon Deadline Cloud."
    )

    wm.deadline_job_description = bpy.props.StringProperty(
        default="", description="The description of the job to submit to Amazon Deadline Cloud."
    )

    wm.deadline_farm = bpy.props.EnumProperty(
        items=farm_callback,
        name="Farm",
        description="Deadline farm to submit the job to.",
        default=None,
        options=set(),
        update=None,
        get=None,
        set=None,
    )

    wm.deadline_queue = bpy.props.EnumProperty(
        items=queue_callback,
        name="Queue",
        description="Deadline queue to submit the job to.",
        default=None,
        options=set(),
        update=None,
        get=None,
        set=None,
    )

    wm.deadline_storage_profile = bpy.props.EnumProperty(
        items=storage_profile_callback,
        name="Storage Profile",
        description="Deadline storage profile to submit the job with.",
        default=None,
        options=set(),
        update=None,
        get=None,
        set=None,
    )

    wm.deadline_scene = bpy.props.EnumProperty(
        items=scene_callback,
        name="Scene",
        description="The scene to Render.",
        default=None,
        options=set(),
        update=None,
        get=None,
        set=None,
    )

    wm.deadline_layer = bpy.props.EnumProperty(
        items=layer_callback,
        name="Layer",
        description="The layer to Render.",
        default=None,
        options=set(),
        update=None,
        get=None,
        set=None,
    )

    wm.deadline_submission_status = bpy.props.EnumProperty(
        items=submission_status_callback,
        name="Submit State",
        description="What state the job will be set to when it is placed in the queue.",
        default=None,
        options=set(),
        update=None,
        get=None,
        set=None,
    )

    wm.deadline_max_retries_per_task = bpy.props.IntProperty(
        name="Task Retry Limit",
        default=5,
        description="Maximum number of times that a Task will retry before it's marked as failed.",
        min=0,
        soft_max=100,
    )

    wm.deadline_priority = bpy.props.IntProperty(
        name="Priority",
        default=50,
        description="Value from 0 (lowest) to 100 (highest) indicating the priority in which this job should be picked up.",
        min=0,
        soft_max=100,
    )

    wm.deadline_max_failed_tasks_count = bpy.props.IntProperty(
        name="Max Failed Tasks",
        default=100,
        description="Maximum number of Tasks that can fail before the Job will be marked as failed.",
        min=0,
        soft_max=1000,
    )

    wm.deadline_override_installation_requirements = bpy.props.BoolProperty(
        name="Override Installation Requirements",
        default=False,
        description="Override installation requirements",
    )
    wm.deadline_installation_requirements = bpy.props.StringProperty(
        name="Installation Requirements", default="", description="Installation requirements"
    )

    wm.deadline_project_path = bpy.props.StringProperty(
        name="Project Path", description="The project path", default=""
    )

    wm.deadline_override_output_path = bpy.props.BoolProperty(
        name="Override Output Path", default=False, description="Override output path."
    )

    wm.deadline_output_path = bpy.props.StringProperty(
        name="Output Path", description="The output path", default=""
    )

    wm.deadline_render_animation = bpy.props.BoolProperty(
        name="Animation", default=False, description="Whether or not to render an animation."
    )

    wm.deadline_override_frame_range = bpy.props.BoolProperty(
        name="Override Frame Range", default=False, description="Override frame range."
    )

    wm.deadline_frame_range = bpy.props.StringProperty(
        name="Frame Range",
        default="1",
        description="Frame range to use if 'Override Frame Range' is enabled.",
    )

    wm.deadline_job_attachments_index = bpy.props.IntProperty()
    wm.deadline_job_attachments = bpy.props.CollectionProperty(type=CUSTOM_JobAttachments)

    wm.deadline_user_job_attachments_index = bpy.props.IntProperty()
    wm.deadline_user_job_attachments = bpy.props.CollectionProperty(type=CUSTOM_JobAttachments)

    wm.deadline_job_output_attachments_index = bpy.props.IntProperty()
    wm.deadline_job_output_attachments = bpy.props.CollectionProperty(
        type=CUSTOM_JobOutputAttachments
    )


def delete():  # pragma: no cover
    wm = bpy.types.WindowManager

    del wm.deadline_job_name
    del wm.deadline_job_description
    del wm.deadline_farm
    del wm.deadline_queue
    del wm.deadline_storage_profile
    del wm.deadline_submission_status
    del wm.deadline_max_retries_per_task
    del wm.deadline_priority
    del wm.max_failed_tasks_count
    del wm.deadline_override_installation_requirements
    del wm.deadline_installation_requirements
    del wm.deadline_scene
    del wm.deadline_layer
    del wm.deadline_project_path
    del wm.deadline_override_output_path
    del wm.deadline_output_path
    del wm.deadline_override_frame_range
    del wm.deadline_frame_range
    del wm.deadline_render_animation
    del wm.deadline_job_attachments_index
    del wm.deadline_job_attachments
    del wm.deadline_user_job_attachments_index
    del wm.deadline_user_job_attachments
    del wm.deadline_job_output_attachments_index
    del wm.deadline_job_output_attachments


classes = (CUSTOM_JobAttachments, CUSTOM_JobOutputAttachments)  # pragma: no cover


def register():  # pragma: no cover
    for cls in classes:
        bpy.utils.register_class(cls)
    create()


def unregister():  # pragma: no cover
    for cls in classes:
        bpy.utils.unregister_class(cls)
    delete()


if __name__ == "__main__":  # pragma: no cover
    register()
