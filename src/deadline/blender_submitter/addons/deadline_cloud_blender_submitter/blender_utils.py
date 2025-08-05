# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
"""Set of shortcut functions to query Blender scene data."""


from __future__ import annotations

import logging
import os
from pathlib import Path

import bpy

_logger = logging.getLogger(__name__)


def get_renderable_view_layers(saved_scene_name) -> list[str]:
    """Get the view layers associated with a scene that are selected to use
    during rendering.

    Args:
        saved_scene_name: The name of the scene.
    """
    scene_name = bpy.data.scenes[saved_scene_name].name
    layers = [layer.name for layer in bpy.data.scenes[scene_name].view_layers if layer.use]
    return layers


def get_renderable_cameras(saved_scene_name) -> list[str]:
    """Returns a list of all camera objects in the scene that are marked as renderable.

    Args:
        saved_scene_name: The name of the scene.
    """
    scene_name = bpy.data.scenes[saved_scene_name].name
    camera_names = [cam.name for cam in bpy.data.scenes[scene_name].objects if cam.type == "CAMERA"]
    return [cam for cam in camera_names if not bpy.data.objects[cam].hide_render]


def get_all_scenes() -> list[str]:
    """Returns a list of all scenes."""
    scene_names = [x.name for x in bpy.data.scenes]
    return scene_names


def get_scene_resolution(saved_scene_name):
    """Returns the resolution of the scene.

    Args:
        saved_scene_name: The name of the scene.
    """
    res_x = bpy.data.scenes[saved_scene_name].render.resolution_x
    res_y = bpy.data.scenes[saved_scene_name].render.resolution_y
    return res_x, res_y


def get_scene_name() -> str:
    """Construct and return a name for the current scene based on the currently opened `.blend` file."""
    scene_name = bpy.path.basename(bpy.context.blend_data.filepath).replace(".blend", "")
    return scene_name


def get_frames() -> str:
    """Returns the frame range of the active scene, formatted as a string e.g. `"1-10"`."""
    start = bpy.context.scene.frame_start
    end = bpy.context.scene.frame_end
    return str(start) + "-" + str(end)


def find_files(project_path, skip_temp=True, skip_nonexistent=True) -> list[Path]:
    """Returns a normalized list of paths to external files referenced by the loaded `.blend` file, augmented with `project_path`.

    Args:
        project_path: The path to the project directory.
        skip_temp: if True, skip all files from any of Blender's potential temp directories.
        skip_nonexistent: if True, skip all files that do not exist. When files are shared across machines, Blender may retain memory of original paths; this ensures that all retrieved paths exist on the local filesystem.
    """
    files = bpy.utils.blend_paths(absolute=True)
    files.append(project_path)
    files = set(Path(f) for f in files)

    temp_dirs = []
    if skip_temp:
        temp_dirs = _get_blender_temp_dirs()
        _logger.debug(f"Resolved Blender temp directories: {temp_dirs}")

    # Path where Blender stores its built-in brush asset .blend files
    blender_resource_path = Path(bpy.utils.resource_path("LOCAL"))

    def _is_in_temp(f: Path) -> bool:
        """Returns True if the given file is in any of Blender's temp directories."""
        return any(f.is_relative_to(temp_dir) for temp_dir in temp_dirs)

    def _is_essential_brush(path: Path) -> bool:
        """
        Returns True if the given file is a built-in brush asset.
        Any paths to files within the local Blender resource folder prefixed with
        'essentials_brushes-' are filtered out since these are bundled with Blender and appear
        to be unneccesary for just rendering. These files were previously included in the main
        .blend file but with 4.3+ they are now separate assets in the Blender install
        https://code.blender.org/2024/07/brush-assets-is-out/#new-brush-workflow
        """
        return path.is_relative_to(blender_resource_path) and path.name.startswith(
            "essentials_brushes-"
        )

    filtered_files = []
    for file in files:
        if (
            (skip_temp and _is_in_temp(file))
            or (skip_nonexistent and not file.exists())
            or _is_essential_brush(file)
        ):
            continue
        filtered_files.append(Path(os.path.abspath(file)))

    return filtered_files


def _get_blender_temp_dirs() -> list[Path]:
    """Returns a list of directories that Blender can try to use to store temporary files.

    Note that Blender only uses one of these at a time.

    Recreate the logic Blender uses to compute temp folders, as described here:
    https://docs.blender.org/manual/en/latest/advanced/blender_directory_layout.html#temporary-directory
    """
    dirs = []

    # `bpy.app.tempdir` seems to resolve to a project-specific directory, e.g. `'C:\\Users\\user\\AppData\\Local\\Temp\\blender_a07504\\'`. We want the parent directory, e.g. `'Temp\\'`.
    dirs.append(Path(os.path.abspath(bpy.app.tempdir)).parent)

    # The user's preferences may specify a temp directory.
    user_pref_dir = bpy.context.preferences.filepaths.temporary_directory
    if user_pref_dir:
        dirs.append(Path(os.path.abspath(user_pref_dir)))

    # System environment variables may specify a temp directory. Which one exists (if any) depends on the OS.
    for var in ["TEMP", "TMP", "TMP_DIR"]:
        if os.environ.get(var):
            dirs.append(Path(os.path.abspath(os.environ[var])))

    # The root temp directory is always a candidate.
    dirs.append(Path("/tmp"))

    return list(set(dirs))
