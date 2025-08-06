# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

import os
from pathlib import Path
from typing import Any, Optional

import bpy
from qtpy.QtCore import Qt  # type: ignore

from deadline.client import api
from deadline.client.job_bundle._yaml import deadline_yaml_dump
from deadline.client.job_bundle.submission import AssetReferences
from deadline.client.ui.dialogs.submit_job_to_deadline_dialog import SubmitJobToDeadlineDialog

from . import blender_utils as bu
from . import sanity_checks as sc
from . import scene_settings_widget as ssw
from . import template_filling as tf
from . import ocio_utils as ocio
from ._version import version
from ._version import version_tuple as adaptor_version_tuple


def create_deadline_dialog(parent=None) -> SubmitJobToDeadlineDialog:
    """Main function that shows the UI.

    Initialize job settings with default values or values from the scene. Build and return a dialogue widget with these settings.

    This function is called every time the `Render > Submit to AWS Deadline Cloud` window is clicked; there is no persistence except for the sticky settings.
    """

    # The scene must be saved before opening the submit dialog.
    if not bpy.data.is_saved:
        raise RuntimeError(
            "The Blender scene is not saved to disk. Please save it before opening the submitter dialog."
        )

    # Initialize telemetry client, opt-out is respected
    api.get_deadline_cloud_library_telemetry_client().update_common_details(
        {
            "deadline-cloud-for-blender-submitter-version": version,
            "blender-version": bpy.app.version_string,
        }
    )

    # Initialize render settings with default values.
    settings = tf.BlenderSubmitterUISettings()

    # Set settings dependent on scene.
    settings.name = bu.get_scene_name()
    settings.project_path = bpy.context.blend_data.filepath
    settings.frame_list = bu.get_frames()

    # For the output path, first check for a value in the Scene settings
    if os.path.dirname(bpy.context.scene.render.filepath):
        settings.output_path = os.path.dirname(bpy.path.abspath(bpy.context.scene.render.filepath))
    # If none, use the one in Preferences
    elif bpy.context.preferences.filepaths.render_output_directory:
        settings.output_path = bpy.context.preferences.filepaths.render_output_directory
    # If neither of these are set, use the job bundle directory by default
    else:
        settings.output_path = os.path.dirname(bpy.context.blend_data.filepath)

    if bpy.path.basename(bpy.context.scene.render.filepath):
        settings.output_file_prefix = bpy.path.basename(bpy.context.scene.render.filepath)

    # Read the user's preferences to set GPU settings.
    settings.enable_gpu = bpy.context.scene.cycles.device == "GPU"

    if bpy.context.preferences.addons["cycles"].preferences.compute_device_type != "NONE":
        settings.gpu_device = bpy.context.preferences.addons[
            "cycles"
        ].preferences.compute_device_type

    # Load and set sticky settings, if any.
    settings.load_sticky_settings(settings.project_path)

    settings.current_layer_selectable_cameras = [settings.camera_selection]
    settings.all_layer_selectable_cameras = [settings.camera_selection]

    # Set auto-detected attachments.
    auto_detected_attachments = _get_auto_detected_assets(settings.project_path)

    # If the user has an OCIO config file set, we will have to upload any directories referenced by that file as job attachments.
    if ocio.get_ocio_path():
        ocio_config = ocio.get_ocio_config(ocio.get_ocio_path())
        for path in ocio.get_ocio_referenced_dirs(ocio_config):
            auto_detected_attachments.input_directories.add(str(path))

    # Set regular attachments.
    attachments = AssetReferences(
        input_filenames=set(settings.input_filenames),
        input_directories=set(settings.input_directories),
        output_directories=set(settings.output_directories),
    )

    # https://docs.blender.org/api/current/bpy.app.html#bpy.app.version
    blender_version = ".".join(str(v) for v in bpy.app.version[:2])
    adaptor_version = ".".join(str(v) for v in adaptor_version_tuple[:2])
    # Need Blender and the Blender OpenJD application interface adaptor
    rez_packages = f"blender-{blender_version} deadline_cloud_for_blender"
    conda_packages = f"blender={blender_version}.* blender-openjd={adaptor_version}.*"

    # Create and return the dialog widget.
    # dialog = SubmitJobToDeadlineDialog(
    dialog = SubmitJobToDeadlineDialog(
        job_setup_widget_type=ssw.SceneSettingsWidget,
        initial_job_settings=settings,
        initial_shared_parameter_values={
            "RezPackages": rez_packages,
            "CondaPackages": conda_packages,
        },
        auto_detected_attachments=auto_detected_attachments,
        attachments=attachments,
        on_create_job_bundle_callback=_create_bundle,
        parent=parent,
        f=Qt.Tool,
        show_host_requirements_tab=True,
    )
    dialog.setWindowFlags(Qt.WindowStaysOnTopHint)
    return dialog


def _create_bundle(
    widget: SubmitJobToDeadlineDialog,
    job_bundle_dir: str,
    settings: tf.BlenderSubmitterUISettings,
    queue_parameters: list[dict[str, Any]],
    asset_references: AssetReferences,
    requirements: Optional[dict[str, Any]] = None,
    purpose: Optional[str] = None,
) -> dict[str, Any]:
    """Create and write Deadline job bundle files to the given directory. Also save sticky settings.

    NOTE: The parameters to this function are fixed by the Deadline API. Do not change them, even if they are unused. See the source of the `SubmitJobToDeadlineDialog` class.

    This function is called when the user clicks the "Submit" button in the submitter dialog.

    Args:
        widget: The submitter dialog widget.
        job_bundle_dir: The directory to write the job bundle files to.
        settings: The job settings.
        queue_parameters: The queue parameters.
        asset_references: The asset references.
        requirements: The host requirements. There are only passed if the user has specified custom host requirements in the UI. If "all available worker hosts" are selected, this is None.
        purpose: The purpose of the job bundle.
    """
    return _create_bundle_internal(
        widget, job_bundle_dir, settings, queue_parameters, asset_references, requirements, purpose
    )


def _create_bundle_internal(
    widget: SubmitJobToDeadlineDialog,
    job_bundle_dir: str,
    settings: tf.BlenderSubmitterUISettings,
    queue_parameters: list[dict[str, Any]],
    asset_references: AssetReferences,
    requirements: Optional[dict[str, Any]] = None,
    purpose: Optional[str] = None,
    prompt_for_saving=True,
) -> dict[str, Any]:
    """Create and write Deadline job bundle files to the given directory. Also save sticky settings.
    The internal variation exists so that the functionality can be accessed without a UI.

    Args:
        widget: The submitter dialog widget.
        job_bundle_dir: The directory to write the job bundle files to.
        settings: The job settings.
        queue_parameters: The queue parameters.
        asset_references: The asset references.
        requirements: The host requirements. There are only passed if the user has specified custom host requirements in the UI. If "all available worker hosts" are selected, this is None.
        purpose: The purpose of the job bundle.
    """
    # Make sure the output path used for submission is absolute
    settings.output_path = bpy.path.abspath(settings.output_path)

    # Run sanity checks on submission
    sc.run_sanity_checks(settings, prompt_for_saving)

    renderable_cameras = bu.get_renderable_cameras(settings.scene_name)

    common_layer_settings = tf.CommonLayerSettings(
        renderer_name=settings.renderer_name,
        frame_range=bu.get_frames(),
        renderable_camera_names=renderable_cameras,
        output_directories=settings.output_path,
        output_file_prefix=settings.output_file_prefix,
        image_resolution=(
            bpy.context.scene.render.resolution_x,
            bpy.context.scene.render.resolution_y,
        ),
        ui_group_label=settings.ui_group_label,
        frames_parameter_name=settings.frames_parameter_name,
        output_file_prefix_parameter_name=settings.output_file_prefix_parameter_name,
        image_width_parameter_name=settings.image_width_parameter_name,
        image_height_parameter_name=settings.image_height_parameter_name,
        scene_name=settings.scene_name,
    )

    # Add selected layers to the list of layers to render.
    layer_names: list[str] = []
    if settings.view_layer_selection == ssw.COMBO_DEFAULT_ALL_RENDERABLE_LAYERS:
        for layer in bu.get_renderable_view_layers(settings.scene_name):
            layer_names.append(layer)
    else:
        layer_names.append(settings.view_layer_selection)

    if settings.override_frame_range:
        common_layer_settings.frame_range = settings.frame_list

    job_template = tf.fill_job_template(settings, layer_names, common_layer_settings, requirements)
    parameter_values = tf.get_parameter_values(settings, common_layer_settings, queue_parameters)

    # Write the job bundle files.
    job_bundle_path = Path(job_bundle_dir)
    for file_name, to_dump in [
        ("template.yaml", job_template),
        ("parameter_values.yaml", {"parameterValues": parameter_values}),
        ("asset_references.yaml", asset_references.to_dict()),
    ]:
        with open(job_bundle_path / file_name, "w", encoding="utf8") as f:
            deadline_yaml_dump(to_dump, f, indent=1)

    # save sticky settings
    attachments: AssetReferences = widget.job_attachments.attachments
    settings.input_filenames = sorted(attachments.input_filenames)
    settings.input_directories = sorted(attachments.input_directories)
    settings.input_filenames = sorted(attachments.input_filenames)
    scene_filename = settings.project_path
    settings.save_sticky_settings(scene_filename)

    return {
        "job_parameters": parameter_values,
    }


def _get_auto_detected_assets(project_path: str) -> AssetReferences:
    files = bu.find_files(project_path)

    # Sort auto-detected attachments to classify files and directories correctly.
    input_filenames = set()
    input_directories = set()
    for f in files:
        if f.is_dir():
            input_directories.add(str(f))
        else:
            input_filenames.add(str(f))

    return AssetReferences(input_filenames=input_filenames, input_directories=input_directories)


if __name__ == "__main__":
    create_deadline_dialog()
