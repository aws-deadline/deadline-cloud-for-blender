# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

"""
Sanity checks done on submit or export bundle
"""
from typing import Union
from pathlib import Path

import bpy
from qtpy import QtWidgets

from . import blender_utils
from . import scene_settings_widget as ssw


def run_sanity_checks(settings):
    # Prompt user for decision if there are unsaved changes
    _prompt_unsaved_changes()

    # Ensure there is a job name.
    if not settings.name:
        raise RuntimeError("No name was given for this submission")

    # Ensure that project path matches active file.
    if settings.project_path != bpy.context.blend_data.filepath:
        raise RuntimeError("Project Path does not match open file.")

    # Check if frame range is valid
    if settings.override_frame_range:
        _validate_frame_range(settings.frame_list)

    # Ensure the selected scene still exists
    if settings.scene_name not in blender_utils.get_all_scenes():
        raise RuntimeError(
            "The selected scene ({}) no longer exists! \n"
            "Please select a different scene.".format(settings.scene_name)
        )

    renderable_cameras = blender_utils.get_renderable_cameras(settings.scene_name)
    renderable_layers = blender_utils.get_renderable_view_layers(settings.scene_name)

    # Ensure there is at least one renderable camera.
    if len(renderable_cameras) == 0:
        raise RuntimeError(
            "There are no renderable cameras in the scene. Please enable at least one before submitting."
        )

    # Ensure the selected camera is still in the scene
    if (
        settings.camera_selection != ssw.COMBO_DEFAULT_ALL_RENDERABLE_CAMERAS
        and settings.camera_selection not in renderable_cameras
    ):
        raise RuntimeError(
            "The selected Camera ({}) is no longer in your scene! \n"
            "Please select a different Camera.".format(settings.camera_selection)
        )

    # Ensure the selected layer is still in the scene
    if (
        settings.view_layer_selection != ssw.COMBO_DEFAULT_ALL_RENDERABLE_LAYERS
        and settings.view_layer_selection not in renderable_layers
    ):
        raise RuntimeError(
            "The selected ViewLayer ({}) is no longer in your scene! \n"
            "Please select a different ViewLayer.".format(settings.view_layer_selection)
        )

    # Ensure the specified output directory exists.
    # If not, create it
    output_dir_as_path = Path(settings.output_path)
    if not (output_dir_as_path.exists()):
        try:
            output_dir_as_path.mkdir(parents=True)
        except Exception as e:
            raise RuntimeError(f"Could not create {output_dir_as_path}.\n\nError message:\n{e}")


def _prompt_unsaved_changes():
    """
    Prompts the user if the current file has unsaved changes.

    User can either:

    * Save (and continue) or;
    * Don't save (and continue) or;
    * Cancel

    Cancelling raises a RuntimeError.
    """
    # Check if file is saved before submit, if not add prompt to save
    if not bpy.data.is_dirty:
        return
    # Show message to user for decision
    msg = QtWidgets.QMessageBox()
    msg.setText("Scene has unsaved changes.")
    msg.setWindowTitle("Blender")
    msg.addButton("Save", QtWidgets.QMessageBox.YesRole)
    msg.addButton("Don't Save", QtWidgets.QMessageBox.NoRole)
    msg.addButton(QtWidgets.QMessageBox.Cancel)
    return_value = msg.exec()
    if return_value == 0:
        bpy.ops.wm.save_mainfile()
    elif return_value == QtWidgets.QMessageBox.Cancel:
        raise RuntimeError("Submission cancelled.")


def _validate_frame_range(frames: str):
    """
    Validates the given frame range string.

    Raises a RuntimeError if it is invalid.

    Example inputs:

        "1"
        "1,3,5-7"
        "1,3,3,3,5" will result in a RuntimeError.
    """
    if not frames:
        raise RuntimeError("Override Frame Range checked but no frame range was given")
    if not is_correct_frame_range(frames):
        raise RuntimeError(
            "You entered an invalid frame range. Please make sure that the first number in the range "
            "is smaller than the second number. \n"
            "E.g.: 10-5 is invalid, 5-10 is valid."
        )
    if not has_no_duplicate_frames(frames)[0]:
        raise RuntimeError(
            "You entered an invalid frame range. Please make sure there are no duplicate frames in "
            "your range. \n"
            f"Duplicate frames: {has_no_duplicate_frames(frames)[1]}"
        )


def is_correct_frame_range(frames: str) -> bool:
    """
    Check if first number in range is smaller than the second.
    Input from text field can only have numbers, commas or dashes due to
    regex validator on field.

    :param frames: frame range you want to check
    :type frames: str
    :returns: boolean that indicates whether the frame range was valid
    :return_type: bool
    """
    frames_input = frames.strip()
    override_frames = frames_input.split(",")
    # only need to check for ranges, not single frames
    frame_ranges = [pair for pair in override_frames if "-" in pair]
    for range_ in frame_ranges:
        numbers = range_.split("-")
        if int(numbers[1]) <= int(numbers[0]):
            return False
    return True


def has_no_duplicate_frames(frames: str) -> list[Union[bool, str]]:
    """
    Check if there are any repeating numbers in the given frame range.
    Input from text field can only have numbers, commas or dashes due to
    regex validator on field.

    :param frames: frame range you want to check
    :type frames: str
    :returns: a list containing a boolean that indicates whether there were no duplicates and a string with the
    duplicate numbers
    :return_type: list[Union[bool, str]]
    """
    # remove any spaces and split into groups
    frames_input = frames.strip()
    override_frames = frames_input.split(",")
    frames_to_render: list[int] = []
    has_no_duplicates = True
    duplicates = []
    for frames in override_frames:
        try:
            if frames_to_render:
                if int(frames) in frames_to_render:
                    has_no_duplicates = False
                    duplicates.append(frames)
            frames_to_render.append(int(frames))
        # when there is a dash in the frame string it can't be converted to an int
        # this way we can easily split single frames from ranges
        except ValueError:
            numbers = frames.split("-")
            for i in range(int(numbers[0]), int(numbers[1]) + 1):
                if frames_to_render:
                    if i in frames_to_render:
                        has_no_duplicates = False
                        duplicates.append(str(i))
                frames_to_render.append(i)
    return [has_no_duplicates, ", ".join(duplicates)]
