# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

"""
submitter_operations.py

This file contains the logic behind the Blender Submitter's UI elements (ie. Button functions,
handling importing/exporting data, etc.).
"""

import json
import os
import os.path as path
from pathlib import Path

try:
    import bpy
except ImportError:  # pragma: no cover
    raise OSError("Could not find the Blender module. Are you running this inside of Blender?")

from .submission_functions import SubmitBackgroundThread, build_config, build_submission
from .utility_functions import (
    deadline_login,
    deadline_logout,
    get_assets,
    set_farm_queue_and_storage_profile_lookups,
)


# Operations are contained outside of the Operator subclass so that they can be properly unit tested
class DeadlineLogin:
    """
    Class to contain logic for DEADLINE_OT_Login operation
    """

    def execute(self):
        deadline_login()
        return {"FINISHED"}


class DEADLINE_OT_Login(bpy.types.Operator):  # pragma: no cover
    """
    Login with Deadline
    """

    bl_idname = "deadline.login"
    bl_label = "Login"
    bl_options = {"REGISTER"}

    bea_login = DeadlineLogin()

    def execute(self, context):
        self.report({"INFO"}, "Attempting to login with Amazon Deadline Cloud")
        return self.bea_login.execute()


# Operations are contained outside of the Operator subclass so that they can be properly unit tested
class DeadlineLogout:
    """
    Class to contain logic for DEADLINE_OT_Logout operation
    """

    def execute(self):
        deadline_logout()
        return {"FINISHED"}


class DEADLINE_OT_Logout(bpy.types.Operator):  # pragma: no cover
    """
    Logout of Deadline
    """

    bl_idname = "deadline.logout"
    bl_label = "Logout"
    bl_options = {"REGISTER"}

    bea_logout = DeadlineLogout()

    def execute(self, context):
        response = self.bea_logout.execute()
        self.report({"INFO"}, "Successfully logged out.")
        return response


# Operations are contained outside of the Operator subclass so that they can be properly unit tested
class DeadlineSetProjectPath:
    """
    Class to contain logic for DEADLINE_OT_Set_Project_Path operation
    """

    def execute(self, context):
        filepath = context.blend_data.filepath
        context.window_manager.deadline_project_path = path.dirname(filepath)
        return {"FINISHED"}


class DEADLINE_OT_Set_Project_Path(bpy.types.Operator):  # pragma: no cover
    """
    Set the project path based on the active project.
    """

    bl_idname = "deadline.set_project_path"
    bl_label = "Set Project Path"
    bl_options = {"REGISTER"}

    bea_set_path = DeadlineSetProjectPath()

    def execute(self, context):
        return self.bea_set_path.execute(context)


# Operations are contained outside of the Operator subclass so that they can be properly unit tested
class DeadlineSubmit:
    """
    Class to contain logic for DEADLINE_OT_Submit operation
    """

    def poll(self, context):
        wm = context.window_manager
        # Check for submission name and that we are logged in.
        if not wm.deadline_job_name or not wm.deadline_logged_in:
            return False

        return True

    def execute(self, context):
        wm = context.window_manager

        # fill project path if it's not currently set
        if wm.deadline_project_path == "":
            bpy.ops.deadline.set_project_path()

        # Build a temp config file for setting the selected farm, queue, and storage profile
        config = build_config()

        # Generate the job bundle files required for submitting with DeadlineClientLib
        build_submission(wm.deadline_project_path, config)

        submit_thread = SubmitBackgroundThread(wm.deadline_project_path, config)
        submit_thread.start()

        return {"FINISHED"}

    def uses_eevee(self, context):
        wm = context.window_manager
        scene = bpy.data.scenes[wm.deadline_scene]

        if scene.render.engine == "BLENDER_EEVEE":
            return True

        return False


class DEADLINE_OT_Submit(bpy.types.Operator):  # pragma: no cover
    """
    Submit the job to Amazon Deadline Cloud.
    """

    bl_idname = "deadline.submit"
    bl_label = "Submit"
    bl_options = {"REGISTER"}

    bea_submit = DeadlineSubmit()

    @classmethod
    def poll(self, context):
        return self.bea_submit.poll(context)

    def execute(self, context):
        if self.bea_submit.uses_eevee(context):
            self.report(
                {"WARNING"},
                "Selected scene uses Eevee, which is not supported by Amazon Deadline Cloud. Please select a different render engine.",
            )
            return {"FINISHED"}

        if bpy.data.is_dirty:
            self.report(
                {"WARNING"}, "Please save your changes before submitting to Amazon Deadline Cloud"
            )
            return {"FINISHED"}

        self.report({"INFO"}, "Submitting job...")
        return self.bea_submit.execute(context)


class DEADLINE_OT_Refresh_Deadline(bpy.types.Operator):  # pragma: no cover
    """
    Refresh info from Deadline.
    """

    bl_idname = "deadline.refresh_deadline"
    bl_label = "Refresh"
    bl_option = {"REGISTER"}

    def execute(self, context):
        set_farm_queue_and_storage_profile_lookups()
        return {"FINISHED"}


# Operations are contained outside of the Operator subclass so that they can be properly unit tested
class DeadlineExport:
    """
    Class to contain logic for DEADLINE_OT_Submit operation
    """

    def build_data(self, context):
        """
        Builds json data to be saved to a file
        """
        wm = context.window_manager
        data = {}

        data["deadline_job_name"] = wm.deadline_job_name
        data["deadline_job_description"] = wm.deadline_job_description
        data["deadline_farm"] = wm.deadline_farm
        data["deadline_queue"] = wm.deadline_queue
        data["deadline_storage_profile"] = wm.deadline_storage_profile
        data["deadline_submission_status"] = wm.deadline_submission_status
        data["deadline_max_retries_per_task"] = wm.deadline_max_retries_per_task
        data["deadline_priority"] = wm.deadline_priority
        data["deadline_max_failed_tasks_count"] = wm.deadline_max_failed_tasks_count
        data[
            "deadline_override_installation_requirements"
        ] = wm.deadline_override_installation_requirements
        data["deadline_installation_requirements"] = wm.deadline_installation_requirements
        data["deadline_scene"] = wm.deadline_scene
        data["deadline_layer"] = wm.deadline_layer
        data["deadline_project_path"] = wm.deadline_project_path
        data["deadline_override_output_path"] = wm.deadline_override_output_path
        data["deadline_output_path"] = wm.deadline_output_path
        data["deadline_render_animation"] = wm.deadline_render_animation
        data["deadline_override_frame_range"] = wm.deadline_override_frame_range
        data["deadline_frame_range"] = wm.deadline_frame_range
        data["deadline_job_attachments_index"] = wm.deadline_job_attachments_index
        attachments = []
        for item in wm.deadline_job_attachments:
            attachments.append({"name": item.name, "path": item.path})
        data["deadline_job_attachments"] = attachments
        data["deadline_user_job_attachments_index"] = wm.deadline_user_job_attachments_index
        attachments = []
        for item in wm.deadline_user_job_attachments:
            attachments.append({"name": item.name, "path": item.path})
        data["deadline_user_job_attachments"] = attachments
        data["deadline_job_output_attachments_index"] = wm.deadline_job_output_attachments_index
        attachments = []
        for item in wm.deadline_job_output_attachments:
            attachments.append({"name": item.name})
        data["deadline_job_output_attachments"] = attachments

        return data


class DEADLINE_OT_Export(bpy.types.Operator):  # pragma: no cover
    """
    Export the Amazon Deadline Cloud Submission Settings to a JSON.
    """

    bl_idname = "deadline.export_settings"
    bl_label = "Export Settings"
    bl_options = {"REGISTER"}

    filepath: bpy.props.StringProperty(subtype="FILE_PATH")  # type: ignore  # noqa: F821

    bea_export = DeadlineExport()

    def execute(self, context):
        data = self.bea_export.build_data(context)
        json_object = json.dumps(data, indent=4)

        # Writing to json
        with open(self.filepath + ".json", "w", encoding="utf8") as outfile:
            outfile.write(json_object)

        return {"FINISHED"}

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {"RUNNING_MODAL"}


# Operations are contained outside of the Operator subclass so that they can be properly unit tested
class DeadlineImport:
    """
    Class to contain logic for DEADLINE_OT_Submit operation
    """

    def create_settings(self, context, data):
        """
        Apply the settings loaded from json
        """
        wm = context.window_manager

        # now update them.
        for i in data:
            if i not in [
                "deadline_job_attachments",
                "deadline_user_job_attachments",
                "deadline_job_output_attachments",
                "deadline_farm",
                "deadline_queue",
                "deadline_storage_profile",
                "deadline_scene",
                "deadline_layer",
            ]:
                setattr(wm, i, data[i])

        # handle enum values
        if bpy.data.scenes.get(data["deadline_scene"], None):
            setattr(wm, "deadline_scene", data["deadline_scene"])

            if bpy.data.scenes[data["deadline_scene"]].view_layers.get(
                data["deadline_layer"], None
            ):
                setattr(wm, "deadline_layer", data["deadline_layer"])

        if wm.get("deadline_farm_lookup", None) and wm.deadline_farm_lookup.get(
            data["deadline_farm"], None
        ):
            setattr(wm, "deadline_farm", data["deadline_farm"])

            if (
                wm.get("deadline_queue_lookup", None)
                and wm.deadline_queue_lookup.get(data["deadline_farm"], None)
                and wm.deadline_queue.lookup.get(data["deadline_farm"]).get(
                    data["deadline_queue"], None
                )
            ):
                setattr(wm, "deadline_queue", data["deadline_queue"])

                if (
                    wm.get("deadline_storage_profile_lookup", None)
                    and wm.deadline_storage_profile_lookup(
                        (data["deadline_farm"], data["deadline_queue"]), None
                    )
                    and wm.deadline_storage_profile_lookup(
                        (data["deadline_farm"], data["deadline_queue"])
                    ).get(data["deadline_storage_profile"], None)
                ):
                    setattr(wm, "deadline_storage_profile", data["deadline_storage_profile"])

        # handle file attachments
        bpy.ops.deadline.clear_assets()
        for item in data["deadline_job_attachments"]:
            bpy.ops.deadline.add_assets(name=item["name"], path=item["path"])

        bpy.ops.deadline.clear_user_assets()
        for item in data["deadline_user_job_attachments"]:
            bpy.ops.deadline.add_user_assets(name=item["name"], path=item["path"])

        bpy.ops.deadline.clear_job_output_attachments()
        for item in data["deadline_job_output_attachments"]:
            bpy.ops.deadline.add_job_output_attachments(name=item["name"])


class DEADLINE_OT_Import(bpy.types.Operator):  # pragma: no cover
    """
    Import the Amazon Deadline Cloud Submitter Settings.
    """

    bl_idname = "deadline.do_import"
    bl_label = "Import Submitter Settings"
    bl_options = {"REGISTER"}

    filepath: bpy.props.StringProperty(  # type: ignore
        name="Filepath", description="Path of the library json file.", default=""  # noqa
    )

    bea_import = DeadlineImport()

    def read(self, context):
        """Reads the JSON file"""
        with open(self.filepath, "r", encoding="utf8") as f:
            self.data = json.load(f)

    def execute(self, context):
        if not os.path.exists(self.filepath):
            return {"FINISHED"}

        self.read(context)
        self.bea_import.create_settings(context, self.data)

        return {"FINISHED"}


# Operations are contained outside of the Operator subclass so that they can be properly unit tested
class DeadlineImportPrompt:
    """
    Class to contain logic for DEADLINE_OT_ImportPrompt operation
    """

    def execute(self, filepath):
        if filepath:
            bpy.ops.deadline.do_import(filepath=filepath)

        return {"FINISHED"}


class DEADLINE_OT_Import_Prompt(bpy.types.Operator):  # pragma: no cover
    """
    Prompt User for Import File.
    """

    bl_idname = "deadline.do_import_prompt"
    bl_label = "Import"
    bl_options = {"REGISTER"}

    filepath: bpy.props.StringProperty(subtype="FILE_PATH")  # type: ignore  # noqa: F821

    bea_import_prompt = DeadlineImportPrompt()

    def execute(self, context):
        return self.bea_import_prompt.execute(self.filepath)

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {"RUNNING_MODAL"}


# Operations are contained outside of the Operator subclass so that they can be properly unit tested
class DeadlineAddAssets:
    """
    Class to contain logic for DEADLINE_OT_Add_Assets operation
    """

    def execute(self, context, name, path):
        if not name == "":
            wm = context.window_manager
            attachment = wm.deadline_job_attachments.add()
            attachment.name = name
            attachment.path = path

            wm.deadline_job_attachments_index = len(wm.deadline_job_attachments) - 1
        return {"FINISHED"}


class DEADLINE_OT_Add_Assets(bpy.types.Operator):  # pragma: no cover
    """
    Add assets.
    """

    bl_idname = "deadline.add_assets"
    bl_label = "Add Asset"
    bl_options = {"REGISTER"}

    name: bpy.props.StringProperty(name="Name", default="")  # type: ignore  # noqa
    path: bpy.props.StringProperty(name="Path", default="")  # type: ignore  # noqa

    bea_add_assets = DeadlineAddAssets()

    def execute(self, context):
        return self.bea_add_assets.execute(context, self.name, self.path)

    def invoke(self, context, event):
        wm = context.window_manager
        return wm.invoke_props_dialog(self)


# Operations are contained outside of the Operator subclass so that they can be properly unit tested
class DeadlineParseAssets:
    """
    Class to contain logic for DEADLINE_OT_Parse_Assets operation
    """

    def execute(self):
        # clear all assets
        bpy.ops.deadline.clear_assets()

        files = get_assets()
        for item in files:
            bpy.ops.deadline.add_assets(name=bpy.path.basename(item), path=str(item))
        return {"FINISHED"}


class DEADLINE_OT_Parse_Assets(bpy.types.Operator):  # pragma: no cover
    """
    Parse all assets.
    """

    bl_idname = "deadline.parse_assets"
    bl_label = "Parse Assets"
    bl_options = {"REGISTER"}

    bea_parse_assets = DeadlineParseAssets()

    def execute(self, context):
        return self.bea_parse_assets.execute()


# Operations are contained outside of the Operator subclass so that they can be properly unit tested
class DeadlineClearAssets:
    """
    Class to contain logic for DEADLINE_OT_Clear_Assets operation
    """

    def execute(self, context):
        wm = context.window_manager
        wm.deadline_job_attachments.clear()
        wm.deadline_job_attachments_index = 0
        return {"FINISHED"}


class DEADLINE_OT_Clear_Assets(bpy.types.Operator):  # pragma: no cover
    """
    Clear list of assets.
    """

    bl_idname = "deadline.clear_assets"
    bl_label = "Clear Assets"
    bl_options = {"REGISTER"}

    bea_clear_assets = DeadlineClearAssets()

    def execute(self, context):
        return self.bea_clear_assets.execute(context)


class DeadlineClearUserAssets:
    """
    Class to contain logic for DEADLINE_OT_Clear_User_Assets operation
    """

    def execute(self, context):
        wm = context.window_manager
        wm.deadline_user_job_attachments.clear()
        wm.deadline_user_job_attachments_index = 0
        return {"FINISHED"}


class DEADLINE_OT_Clear_User_Assets(bpy.types.Operator):  # pragma: no cover
    """
    Clear list of user assets.
    """

    bl_idname = "deadline.clear_user_assets"
    bl_label = "Clear Assets"
    bl_options = {"REGISTER"}

    bea_clear_assets = DeadlineClearUserAssets()

    def execute(self, context):
        return self.bea_clear_assets.execute(context)


# Operations are contained outside of the Operator subclass so that they can be properly unit tested
class DeadlineAddUserAssets:
    """
    Class to contain logic for DEADLINE_OT_Add_User_Assets operation
    """

    def execute(self, context, name, path):
        if not name == "":
            wm = context.window_manager
            attachment = wm.deadline_user_job_attachments.add()
            attachment.name = name
            attachment.path = path

            wm.deadline_user_job_attachments_index = len(wm.deadline_user_job_attachments) - 1
        return {"FINISHED"}


class DEADLINE_OT_Add_User_Assets(bpy.types.Operator):  # pragma: no cover
    """Add assets."""

    bl_idname = "deadline.add_user_assets"
    bl_label = "Add Assets"
    bl_options = {"REGISTER"}

    name: bpy.props.StringProperty(name="Name", default="")  # type: ignore  # noqa
    path: bpy.props.StringProperty(name="Path", default="")  # type: ignore  # noqa

    bea_add_assets = DeadlineAddUserAssets()

    def execute(self, context):
        return self.bea_add_assets.execute(context, self.name, self.path)

    def invoke(self, context, event):
        wm = context.window_manager
        return wm.invoke_props_dialog(self)


# Operations are contained outside of the Operator subclass so that they can be properly unit tested
class DeadlineUserFileSelector:
    """
    Class to contain logic for DEADLINE_OT_User_File_Selector operation
    """

    def execute(self, files, directory):
        directory_path = Path(directory)
        for file in files:
            file_path = directory_path / file.name
            bpy.ops.deadline.add_user_assets(name=file.name, path=str(file_path))
        return {"FINISHED"}


class DEADLINE_OT_User_File_Selector(bpy.types.Operator):  # pragma: no cover
    bl_idname = "deadline.user_asset_selector"
    bl_label = "Add Assets"

    files: bpy.props.CollectionProperty(  # type: ignore
        name="Filepaths",
        description="Path(s) of the asset file(s).",
        type=bpy.types.OperatorFileListElement,  # noqa
    )
    directory: bpy.props.StringProperty(subtype="DIR_PATH")  # type: ignore  # noqa

    bea_user_file_selector = DeadlineUserFileSelector()

    def execute(self, context):
        return self.bea_user_file_selector.execute(self.files, self.directory)

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {"RUNNING_MODAL"}


# Operations are contained outside of the Operator subclass so that they can be properly unit tested
class DeadlineRemoveAssets:
    """
    Class to contain logic for DEADLINE_OT_Remove_Assets operation
    """

    def execute(self, context):
        wm = context.window_manager

        index = wm.deadline_job_attachments_index
        wm.deadline_job_attachments.remove(index)
        orig_len = len(wm.deadline_job_attachments)

        if index == orig_len:
            wm.deadline_job_attachments_index = len(wm.deadline_job_attachments) - 1

        return {"FINISHED"}


class DEADLINE_OT_Remove_Assets(bpy.types.Operator):  # pragma: no cover
    """Remove assets."""

    bl_idname = "deadline.remove_assets"
    bl_label = "Remove Asset"
    bl_options = {"REGISTER"}

    bea_remove_assets = DeadlineRemoveAssets()

    def execute(self, context):
        return self.bea_remove_assets.execute(context)


# Operations are contained outside of the Operator subclass so that they can be properly unit tested
class DeadlineRemoveUserAssets:
    """
    Class to contain logic for DEADLINE_OT_Remove_User_Assets operation
    """

    def execute(self, context):
        wm = context.window_manager

        index = wm.deadline_user_job_attachments_index
        wm.deadline_user_job_attachments.remove(index)
        orig_len = len(wm.deadline_user_job_attachments)

        if index == orig_len:
            wm.deadline_user_job_attachments_index = len(wm.deadline_user_job_attachments) - 1

        return {"FINISHED"}


class DEADLINE_OT_Remove_User_Assets(bpy.types.Operator):  # pragma: no cover
    """Remove assets."""

    bl_idname = "deadline.remove_user_assets"
    bl_label = "Remove Asset"
    bl_options = {"REGISTER"}

    bea_remove_assets = DeadlineRemoveUserAssets()

    def execute(self, context):
        return self.bea_remove_assets.execute(context)


# Operations are contained outside of the Operator subclass so that they can be properly unit tested
class DeadlineJobOutputAddAttachments:
    """
    Class to contain logic for DEADLINE_OT_Add_Job_Output_Attachments operation
    """

    def execute(self, context, name):
        if not name == "":
            wm = context.window_manager
            attachment = wm.deadline_job_output_attachments.add()
            attachment.name = name

            wm.deadline_job_output_attachments_index = len(wm.deadline_job_output_attachments) - 1
        return {"FINISHED"}


class DEADLINE_OT_Add_Job_Output_Attachments(bpy.types.Operator):  # pragma: no cover
    """Add Job Output Attachments."""

    bl_idname = "deadline.add_job_output_attachments"
    bl_label = "Add Job Output"
    bl_options = {"REGISTER"}

    name: bpy.props.StringProperty(name="Name", default="")  # type: ignore  # noqa

    bea_add_job_output = DeadlineJobOutputAddAttachments()

    def execute(self, context):
        return self.bea_add_job_output.execute(context, self.name)

    def invoke(self, context, event):
        wm = context.window_manager
        return wm.invoke_props_dialog(self)


# Operations are contained outside of the Operator subclass so that they can be properly unit tested
class DeadlineJobOutputRemoveAttachments:
    """
    Class to contain logic for DEADLINE_OT_Remove_Job_Output_Attachments operation
    """

    def execute(self, context):
        wm = context.window_manager

        index = wm.deadline_job_output_attachments_index
        wm.deadline_job_output_attachments.remove(index)
        orig_len = len(wm.deadline_job_output_attachments)

        if index == orig_len:
            wm.deadline_job_output_attachments_index = len(wm.deadline_job_output_attachments) - 1

        return {"FINISHED"}


class DEADLINE_OT_Remove_Job_Output_Attachments(bpy.types.Operator):  # pragma: no cover
    """Add Job Output Attachments."""

    bl_idname = "deadline.remove_job_output_attachments"
    bl_label = "Remove Job Output"
    bl_options = {"REGISTER"}

    bea_remove_job_outputs = DeadlineJobOutputRemoveAttachments()

    def execute(self, context):
        return self.bea_remove_job_outputs.execute(context)


# Operations are contained outside of the Operator subclass so that they can be properly unit tested
class DeadlineClearJobOutputs:
    """
    Class to contain logic for DEADLINE_OT_Clear_Job_Outputs operation
    """

    def execute(self, context):
        wm = context.window_manager
        wm.deadline_job_output_attachments.clear()
        wm.deadline_job_output_attachments_index = 0
        return {"FINISHED"}


class DEADLINE_OT_Clear_Job_Outputs(bpy.types.Operator):  # pragma: no cover
    """Clear list of Job Output Attachments."""

    bl_idname = "deadline.clear_job_output_attachments"
    bl_label = "Clear Job Outputs"
    bl_options = {"REGISTER"}

    bea_clear_job_outputs = DeadlineClearJobOutputs()

    def execute(self, context):
        return self.bea_clear_job_outputs.execute(context)


classes = (
    DEADLINE_OT_Login,
    DEADLINE_OT_Logout,
    DEADLINE_OT_Submit,
    DEADLINE_OT_Set_Project_Path,
    DEADLINE_OT_Add_Assets,
    DEADLINE_OT_Parse_Assets,
    DEADLINE_OT_Remove_Assets,
    DEADLINE_OT_Clear_Assets,
    DEADLINE_OT_Add_User_Assets,
    DEADLINE_OT_User_File_Selector,
    DEADLINE_OT_Clear_User_Assets,
    DEADLINE_OT_Remove_User_Assets,
    DEADLINE_OT_Add_Job_Output_Attachments,
    DEADLINE_OT_Remove_Job_Output_Attachments,
    DEADLINE_OT_Clear_Job_Outputs,
    DEADLINE_OT_Export,
    DEADLINE_OT_Import,
    DEADLINE_OT_Import_Prompt,
    DEADLINE_OT_Refresh_Deadline,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)


if __name__ == "__main__":
    register()
