# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
from __future__ import annotations

import logging
from typing import Any, Optional, cast

from deadline.client.api import BaseSubmitter, BaseSubmitterSettings
from deadline.client.exceptions import DeadlineOperationError

import bpy  # type: ignore[import]

from deadline.client.job_bundle.parameters import JobParameter
from deadline.client.job_bundle.submission import AssetReferences

from . import ocio_utils as ocio
from .blender_utils import (
    classify_auto_detected_paths,
    get_active_scene_name,
    get_frames,
    get_render_engine,
    get_renderable_cameras,
    get_renderable_view_layers,
    resolve_gpu_settings,
    resolve_output_file_prefix,
    resolve_output_path,
)
from .template_filling import (
    BlenderSubmitterSettings,
    CommonLayerSettings,
    fill_job_template,
    get_parameter_values as _fill_parameter_values,
)

_logger = logging.getLogger(__name__)

# Re-exported for callers that import it from this module (e.g. the GUI dialog
# and tests). The definition lives in ``template_filling`` so the module
# dependency flows one way and avoids an import cycle.
__all__ = ["BlenderSubmitter", "BlenderSubmitterSettings"]

# Sentinel for "render every renderable view layer". Duplicated from
# scene_settings_widget.COMBO_DEFAULT_ALL_RENDERABLE_LAYERS to avoid importing
# the Qt-heavy widget module into this headless engine (the same pattern
# template_filling uses for the camera sentinels).
_ALL_RENDERABLE_LAYERS = "All Renderable Layers"


class BlenderSubmitter(BaseSubmitter):
    """BaseSubmitter implementation for Blender submissions."""

    def get_settings(self) -> BlenderSubmitterSettings:
        settings = BlenderSubmitterSettings()
        scene = bpy.context.scene

        settings.job_name = bpy.path.basename(bpy.data.filepath) or "Untitled"
        settings.project_path = bpy.data.filepath or ""
        # scene_name must be a key in bpy.data.scenes (indexed downstream by
        # get_renderable_view_layers/cameras), so use the active scene name
        # rather than the .blend-derived label.
        settings.scene_name = get_active_scene_name()
        settings.frame_list = get_frames()
        # Shared with the GUI flow: maps Blender's internal engine id to the
        # template's allowed RenderEngine values (eevee/cycles/workbench).
        settings.renderer_name = get_render_engine()

        settings.image_width = scene.render.resolution_x
        settings.image_height = scene.render.resolution_y
        # Shared with the GUI flow: resolve the output *directory* (with the
        # scene/prefs/blend-dir fallbacks) and the filename prefix identically.
        settings.output_path = resolve_output_path()
        settings.output_file_prefix = resolve_output_file_prefix() or settings.output_file_prefix

        settings.input_filenames = [bpy.data.filepath] if bpy.data.filepath else []
        settings.output_directories = [settings.output_path] if settings.output_path else []

        # Default to rendering all renderable view layers (empty selection),
        # matching the dialog's default. _resolve_view_layer_names expands this.
        settings.view_layer_selection = ""

        # An empty camera_selection flows into _fill_step_template's else branch
        # and produces a bogus [""] camera dimension. Fall back to the scene's
        # default camera (mirrors the dialog) when none is resolved.
        if scene.camera:
            settings.camera_selection = scene.camera.name
        else:
            settings.camera_selection = "Use Default Camera"

        # Read GPU settings from the scene/preferences (shared helper), so API
        # submissions honor the user's GPU choice and default to the "NONE"
        # sentinel (not "None") that the template/adaptor expect.
        settings.enable_gpu, settings.gpu_device = resolve_gpu_settings()

        # Mirror the dialog flow: pick up a custom OCIO config from the
        # environment so jobs render with the correct color management. The
        # OCIO-referenced directories are attached in get_asset_references().
        settings.ocio_config_path = ocio.get_ocio_path()

        return settings

    def get_job_template(
        self,
        settings: BaseSubmitterSettings,
        host_requirements: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        # The builders read BlenderSubmitterSettings directly (no UISettings
        # translation); at runtime this is always that concrete type.
        blender_settings = cast("BlenderSubmitterSettings", settings)
        view_layers = self._resolve_view_layer_names(settings)
        common_layer_settings = self._build_common_layer_settings(settings)

        return fill_job_template(
            blender_settings, view_layers, common_layer_settings, host_requirements
        )

    def get_parameter_values(
        self,
        settings: BaseSubmitterSettings,
        queue_parameters: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        blender_settings = cast("BlenderSubmitterSettings", settings)
        common_layer_settings = self._build_common_layer_settings(settings)

        # The unified ABC types queue_parameters as list[dict]; the native
        # filler expects list[JobParameter] (a TypedDict). They are the same
        # shape at runtime, so cast to bridge the static types.
        return _fill_parameter_values(
            blender_settings,
            common_layer_settings,
            cast(list[JobParameter], queue_parameters),
        )

    def _build_common_layer_settings(self, settings: BaseSubmitterSettings):
        """Construct CommonLayerSettings from the unified settings."""
        renderer_name = "cycles"
        scene_name = "Scene"
        output_file_prefix = "output_####"
        image_resolution = (1920, 1080)
        if isinstance(settings, BlenderSubmitterSettings):
            renderer_name = settings.renderer_name
            scene_name = settings.scene_name
            output_file_prefix = settings.output_file_prefix
            image_resolution = (settings.image_width, settings.image_height)

        # Populate the renderable cameras so the "All Renderable Cameras"
        # selection produces a real Camera task dimension (mirrors the dialog).
        # A scene with no renderable cameras returns []; an invalid scene_name
        # raises KeyError here (same as _resolve_view_layer_names), which should
        # surface as a submission error rather than be silently swallowed.
        renderable_camera_names = get_renderable_cameras(scene_name)

        return CommonLayerSettings(
            renderer_name=renderer_name,
            frame_range=settings.frame_list,
            frames_parameter_name="Frames",
            renderable_camera_names=renderable_camera_names,
            output_directories=settings.output_path,
            output_file_prefix=output_file_prefix,
            output_file_prefix_parameter_name="OutputFileName",
            ui_group_label="Blender Settings",
            image_width_parameter_name="ResolutionX",
            image_height_parameter_name="ResolutionY",
            image_resolution=image_resolution,
            scene_name=scene_name,
        )

    def _resolve_view_layer_names(self, settings: BaseSubmitterSettings) -> list[str]:
        """Return the view layers to render, honoring view_layer_selection.

        An empty selection (or the "All Renderable Layers" sentinel) renders
        every renderable view layer; any other value renders that single layer.
        Mirrors the dialog flow so the GUI and unified API paths agree.
        """
        # scene_name must be a key in bpy.data.scenes. Fail fast on an empty
        # scene_name with an actionable message rather than falling back to
        # job_name (the .blend file name, which is NOT a scenes key and would
        # only produce a more confusing KeyError deep in get_renderable_view_layers).
        scene_name = getattr(settings, "scene_name", "")
        if not scene_name:
            raise DeadlineOperationError(
                "settings.scene_name is empty; set it to a valid scene name "
                "(a key in bpy.data.scenes) before submitting."
            )
        selection = getattr(settings, "view_layer_selection", "")

        if not selection or selection == _ALL_RENDERABLE_LAYERS:
            return get_renderable_view_layers(scene_name)
        return [selection]

    def get_asset_references(self, settings: BaseSubmitterSettings) -> AssetReferences:
        # Seed from any caller-supplied inputs so they are honored (not dropped).
        input_filenames: set[str] = set(settings.input_filenames)
        input_directories: set[str] = set(settings.input_directories)

        # The .blend file itself.
        if bpy.data.filepath:
            input_filenames.add(bpy.data.filepath)

        # Auto-detect external dependencies (textures, linked libraries, UDIM
        # tiles, OCIO configs, …) via the shared helper, so jobs submitted
        # through this API attach the same assets the dialog flow does.
        # Best-effort: never let a scan failure block the submission (the .blend
        # + explicit directories are still attached), but log rather than
        # swallow so a scan bug is diagnosable.
        try:
            files, dirs = classify_auto_detected_paths(bpy.data.filepath)
        except Exception:
            _logger.warning(
                "Auto-detection of external dependencies failed; only the .blend "
                "file and explicitly-provided paths will be attached.",
                exc_info=True,
            )
        else:
            input_filenames |= files
            input_directories |= dirs

        # Attach the directories referenced by the OCIO config (shared with the
        # dialog flow) so custom color management resolves on the farm. Honor an
        # explicitly-set ocio_config_path (defaults to "" -> the active $OCIO
        # config). get_current_ocio_referenced_dirs returns [] when no config is
        # set; a malformed/unreadable config raises inside PyOpenColorIO — log
        # and continue rather than block submission, but don't swallow silently.
        blender_settings = cast(BlenderSubmitterSettings, settings)
        try:
            referenced_dirs = ocio.get_current_ocio_referenced_dirs(
                blender_settings.ocio_config_path
            )
        except Exception:
            _logger.warning(
                "Failed to read OCIO config %r; its referenced directories will "
                "not be attached as job inputs.",
                blender_settings.ocio_config_path,
                exc_info=True,
            )
        else:
            input_directories.update(referenced_dirs)

        # Return the typed AssetReferences per the unified BaseSubmitter
        # contract (deadline-cloud #1245); callers call .to_dict() at the
        # job-bundle serialization boundary.
        return AssetReferences(
            input_filenames=input_filenames,
            input_directories=input_directories,
            output_directories=set(settings.output_directories),
        )
