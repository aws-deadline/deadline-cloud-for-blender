# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
"""Set of shortcut functions to query Blender scene data."""

from __future__ import annotations

import logging
import os
from pathlib import Path

import bpy
from deadline.client.exceptions import DeadlineOperationError

_logger = logging.getLogger(__name__)


def get_renderable_view_layers(saved_scene_name) -> list[str]:
    """Get the view layers associated with a scene that are selected to use
    during rendering.

    Args:
        saved_scene_name: The name of the scene (a key in ``bpy.data.scenes``).
    """
    scene = bpy.data.scenes[saved_scene_name]
    return [layer.name for layer in scene.view_layers if layer.use]


def get_renderable_cameras(saved_scene_name) -> list[str]:
    """Returns a list of all camera objects in the scene that are marked as renderable.

    Args:
        saved_scene_name: The name of the scene (a key in ``bpy.data.scenes``).
    """
    scene = bpy.data.scenes[saved_scene_name]
    camera_names = [obj.name for obj in scene.objects if obj.type == "CAMERA"]
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
    """Construct and return a name for the current scene based on the currently opened `.blend` file.

    The dialog submitter uses this as the default *job* name
    (``open_deadline_cloud_dialog.py``), so it must stay derived from the
    ``.blend`` file name. Callers that need the active scene's name as a
    ``bpy.data.scenes`` key (e.g. the unified ``BlenderSubmitter`` path) must
    use ``get_active_scene_name()`` instead.
    """
    scene_name = bpy.path.basename(bpy.context.blend_data.filepath).replace(".blend", "")
    return scene_name


def get_active_scene_name() -> str:
    """Return the name of the active Blender scene.

    This is an actual key in ``bpy.data.scenes`` (unlike ``get_scene_name()``,
    which derives a label from the ``.blend`` file name). Callers that index
    ``bpy.data.scenes`` — e.g. ``get_renderable_view_layers`` /
    ``get_renderable_cameras`` — must use this, since the active scene is not
    necessarily named identically to the file (the default scene is ``"Scene"``),
    which would otherwise raise a KeyError during job-template construction.
    """
    return bpy.context.scene.name


def get_frames() -> str:
    """Returns the frame range of the active scene, formatted as a string e.g. `"1-10"`."""
    start = bpy.context.scene.frame_start
    end = bpy.context.scene.frame_end
    return str(start) + "-" + str(end)


# Maps Blender's internal engine id (e.g. "BLENDER_EEVEE", "CYCLES") to the
# render-engine names the job template's RenderEngine parameter allows
# ("eevee"/"cycles"/"workbench"). Emitting the raw "blender_eevee" id fails
# CreateJob with a ValidationException.
_RENDER_ENGINE_MAP = {
    "BLENDER_EEVEE": "eevee",
    "BLENDER_EEVEE_NEXT": "eevee",
    "CYCLES": "cycles",
    "BLENDER_WORKBENCH": "workbench",
}


def get_render_engine() -> str:
    """Return the active scene's render engine as a template RenderEngine value.

    Shared by the GUI submitter and the unified API path so both map Blender's
    internal engine id to the template's allowed values identically.

    Raises:
        DeadlineOperationError: If the active engine is not one of the built-in
            engines the job template supports (Cycles / EEVEE / Workbench).
            Third-party engines (V-Ray, Octane, Redshift, …) would otherwise be
            forwarded as an out-of-range ``RenderEngine`` value that CreateJob
            rejects with an opaque ValidationException, so fail early with an
            actionable message instead.
    """
    engine = bpy.context.scene.render.engine
    if engine not in _RENDER_ENGINE_MAP:
        raise DeadlineOperationError(
            f"Render engine '{engine}' is not supported. Switch the scene's render "
            "engine to Cycles, EEVEE, or Workbench before submitting."
        )
    return _RENDER_ENGINE_MAP[engine]


def resolve_output_path() -> str:
    """Return the render output *directory* for the active scene.

    The OutputDir job parameter is type PATH / objectType DIRECTORY, so this
    must be a directory (``scene.render.filepath`` is a directory + filename
    prefix, e.g. ``//render/frame_``). Falls back, in order, to:

    1. the directory of ``scene.render.filepath`` (if it has a directory part),
    2. the Preferences "render output directory", then
    3. the directory containing the ``.blend`` file.

    Shared by the GUI submitter and the unified API path so both resolve the
    output directory (and its fallbacks) identically.
    """
    render_filepath = bpy.context.scene.render.filepath
    if os.path.dirname(render_filepath):
        return os.path.dirname(bpy.path.abspath(render_filepath))
    if bpy.context.preferences.filepaths.render_output_directory:
        return bpy.context.preferences.filepaths.render_output_directory
    return os.path.dirname(bpy.context.blend_data.filepath)


def resolve_output_file_prefix() -> str:
    """Return the output filename prefix from ``scene.render.filepath``.

    Empty when the scene's render filepath has no filename part (the caller
    keeps its own default in that case). Shared by both submission flows.
    """
    return bpy.path.basename(bpy.context.scene.render.filepath)


def resolve_gpu_settings() -> tuple[bool, str]:
    """Return ``(enable_gpu, gpu_device)`` read from the scene/preferences.

    ``gpu_device`` defaults to the ``"NONE"`` sentinel (uppercase) — matching
    ``default_blender_template.yaml`` and the adaptor's ``CyclesHandler`` check
    — and is set to the Cycles ``compute_device_type`` only when the scene is
    actually rendering on GPU (``scene.cycles.device == "GPU"``).

    The ``compute_device_type`` preference persists independently of the scene's
    render device, so gating on ``enable_gpu`` here keeps ``gpu_device`` at
    ``"NONE"`` for a CPU scene even when a GPU device type is selected in
    Preferences — mirroring ``scene_settings_widget.update_settings`` so the GUI
    and unified API paths enable GPU rendering identically.
    """
    enable_gpu = bpy.context.scene.cycles.device == "GPU"
    gpu_device = "NONE"
    if enable_gpu:
        compute_device_type = bpy.context.preferences.addons[
            "cycles"
        ].preferences.compute_device_type
        if compute_device_type != "NONE":
            gpu_device = compute_device_type
    return enable_gpu, gpu_device


def classify_auto_detected_paths(project_path) -> tuple[set[str], set[str]]:
    """Auto-detect external dependencies and split them into files/directories.

    Runs :func:`find_files` for ``project_path`` and classifies each result as
    an input filename or input directory. Shared by the GUI submitter and the
    unified API path so both attach the same auto-detected assets.

    Returns:
        A ``(input_filenames, input_directories)`` tuple of string sets.
    """
    input_filenames: set[str] = set()
    input_directories: set[str] = set()
    for f in find_files(project_path):
        if f.is_dir():
            input_directories.add(str(f))
        else:
            input_filenames.add(str(f))
    return input_filenames, input_directories


def find_files(project_path, skip_temp=True, skip_nonexistent=True) -> list[Path]:
    """Returns a normalized list of paths to external files referenced by the loaded `.blend` file, augmented with `project_path`.

    Args:
        project_path: The path to the project directory.
        skip_temp: if True, skip all files from any of Blender's potential temp directories.
        skip_nonexistent: if True, skip all files that do not exist. When files are shared across machines, Blender may retain memory of original paths; this ensures that all retrieved paths exist on the local filesystem.
    """
    import os

    # Get allowlist from environment variable (semicolon-separated on Windows, colon-separated on Unix)
    allowlist_env = os.environ.get("BLENDER_TEMP_ALLOWLIST", "")
    temp_allowlist = [Path(p.strip()) for p in allowlist_env.split(os.pathsep) if p.strip()]

    files = bpy.utils.blend_paths(absolute=True)
    files.append(project_path)

    # blend_paths() returns paths with <UDIM>/<UVTILE> tokens that don't exist
    # on disk, so they get filtered out later. We use Blender's tile data to
    # construct the real file paths for each tile instead.
    for image in bpy.data.images:
        if image.source == "TILED":
            filepath = bpy.path.abspath(image.filepath, library=image.library)
            if filepath:
                parent_dir = os.path.normpath(str(Path(filepath).parent))
                filename = Path(filepath).name
                for tile in image.tiles:
                    u = (tile.number - 1001) % 10
                    v = (tile.number - 1001) // 10
                    tile_name = filename.replace("<UDIM>", str(tile.number))
                    tile_name = tile_name.replace("<UVTILE>", f"u{u + 1}_v{v + 1}")
                    files.append(os.path.join(parent_dir, tile_name))

    # Remove unresolved tile token paths — blend_paths() includes these but
    # they aren't real files. The resolved tile paths were added above.
    files = [f for f in files if "<UDIM>" not in str(f) and "<UVTILE>" not in str(f)]

    files = {Path(f) for f in files}

    temp_dirs = []
    if skip_temp:
        temp_dirs = _get_blender_temp_dirs()
        _logger.debug(f"Resolved Blender temp directories: {temp_dirs}")

    # Path where Blender stores its built-in brush asset .blend files
    blender_resource_path = Path(bpy.utils.resource_path("LOCAL"))

    def _is_in_temp(f: Path) -> bool:
        """Returns True if the given file is in any of Blender's temp directories, unless it's in the allowlist."""
        if any(f.is_relative_to(allowed) for allowed in temp_allowlist):
            return False
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
