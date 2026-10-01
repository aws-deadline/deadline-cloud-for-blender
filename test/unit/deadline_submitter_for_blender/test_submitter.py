# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

"""Tests for the unified BlenderSubmitter (…deadline_cloud_blender_submitter.submitter).

`bpy` and the UI dialog are mocked in this package's __init__.py.

The unified BaseSubmitter base class lives in deadline-cloud (PR #1245). This
module imports it at load, so — matching the Maya submitter's convention — it is
NOT guarded with a skip: it fails until a `deadline` release carrying
BaseSubmitter is installed, and passes once it is.
"""

from __future__ import annotations

from unittest import mock

import pytest

_API = "deadline.blender_submitter.addons.deadline_cloud_blender_submitter.submitter"


def _import_api():
    import importlib

    return importlib.import_module(_API)


def _inputs(refs) -> tuple[set[str], set[str]]:
    """Return (input_filenames, input_directories) from an AssetReferences."""
    return set(refs.input_filenames), set(refs.input_directories)


def _outputs(refs) -> set[str]:
    return set(refs.output_directories)


def test_get_asset_references_includes_auto_detected(tmp_path):
    api_mod = _import_api()

    tex = tmp_path / "tex.png"
    sub = tmp_path / "cache"

    settings = api_mod.BlenderSubmitterSettings()
    settings.input_directories = []
    settings.output_directories = ["/out"]

    with (
        mock.patch.object(api_mod.bpy, "data") as bpy_data,
        # classify_auto_detected_paths is the shared helper (blender_utils);
        # it returns (files, dirs) already split.
        mock.patch.object(
            api_mod,
            "classify_auto_detected_paths",
            return_value=({str(tex)}, {str(sub)}),
        ),
        mock.patch.object(api_mod.ocio, "get_current_ocio_referenced_dirs", return_value=[]),
    ):
        bpy_data.filepath = "/proj/scene.blend"
        api = api_mod.BlenderSubmitter()
        refs = api.get_asset_references(settings)

    input_filenames, input_directories = _inputs(refs)
    # the .blend itself plus the auto-detected texture are attached as inputs,
    # and the auto-detected directory is attached as an input directory.
    assert "/proj/scene.blend" in input_filenames
    assert str(tex) in input_filenames
    assert str(sub) in input_directories
    assert _outputs(refs) == {"/out"}


def test_get_asset_references_survives_scan_failure():
    api_mod = _import_api()
    settings = api_mod.BlenderSubmitterSettings()
    settings.input_directories = []
    settings.output_directories = []

    with (
        mock.patch.object(api_mod.bpy, "data") as bpy_data,
        mock.patch.object(
            api_mod,
            "classify_auto_detected_paths",
            side_effect=RuntimeError("scan boom"),
        ),
        mock.patch.object(api_mod.ocio, "get_current_ocio_referenced_dirs", return_value=[]),
    ):
        bpy_data.filepath = "/proj/scene.blend"
        api = api_mod.BlenderSubmitter()
        # a scan failure must not blow up the submission; the .blend is still there
        refs = api.get_asset_references(settings)

    input_filenames, _ = _inputs(refs)
    assert "/proj/scene.blend" in input_filenames


def test_get_asset_references_honors_caller_input_filenames(tmp_path):
    """Caller-supplied input_filenames must be preserved, not dropped."""
    api_mod = _import_api()

    settings = api_mod.BlenderSubmitterSettings()
    settings.input_filenames = ["/extra/asset.abc"]
    settings.input_directories = ["/extra/dir"]
    settings.output_directories = []

    with (
        mock.patch.object(api_mod.bpy, "data") as bpy_data,
        mock.patch.object(api_mod, "classify_auto_detected_paths", return_value=(set(), set())),
        mock.patch.object(api_mod.ocio, "get_current_ocio_referenced_dirs", return_value=[]),
    ):
        bpy_data.filepath = "/proj/scene.blend"
        api = api_mod.BlenderSubmitter()
        refs = api.get_asset_references(settings)

    input_filenames, input_directories = _inputs(refs)
    assert "/extra/asset.abc" in input_filenames
    assert "/extra/dir" in input_directories
    assert "/proj/scene.blend" in input_filenames


def test_get_asset_references_attaches_ocio_dirs(tmp_path):
    """Directories referenced by a custom OCIO config are attached as inputs."""
    api_mod = _import_api()

    settings = api_mod.BlenderSubmitterSettings()
    settings.input_directories = []
    settings.output_directories = []
    settings.ocio_config_path = "/color/config.ocio"

    with (
        mock.patch.object(api_mod.bpy, "data") as bpy_data,
        mock.patch.object(api_mod, "classify_auto_detected_paths", return_value=(set(), set())),
        mock.patch.object(
            api_mod.ocio, "get_current_ocio_referenced_dirs", return_value=["/color/luts"]
        ) as get_ocio_dirs,
    ):
        bpy_data.filepath = "/proj/scene.blend"
        api = api_mod.BlenderSubmitter()
        refs = api.get_asset_references(settings)

    _, input_directories = _inputs(refs)
    assert "/color/luts" in input_directories
    # the explicitly-set ocio_config_path is honored (passed to the helper)
    get_ocio_dirs.assert_called_once_with("/color/config.ocio")


def test_get_asset_references_survives_bad_ocio_config():
    """A broken OCIO config must not block submission."""
    api_mod = _import_api()

    settings = api_mod.BlenderSubmitterSettings()
    settings.input_directories = []
    settings.output_directories = []
    settings.ocio_config_path = "/color/config.ocio"

    with (
        mock.patch.object(api_mod.bpy, "data") as bpy_data,
        mock.patch.object(api_mod, "classify_auto_detected_paths", return_value=(set(), set())),
        mock.patch.object(
            api_mod.ocio,
            "get_current_ocio_referenced_dirs",
            side_effect=RuntimeError("bad config"),
        ),
    ):
        bpy_data.filepath = "/proj/scene.blend"
        api = api_mod.BlenderSubmitter()
        refs = api.get_asset_references(settings)

    input_filenames, _ = _inputs(refs)
    assert "/proj/scene.blend" in input_filenames


def test_get_settings_defaults_camera_when_none():
    """When the active scene has no camera, fall back to 'Use Default Camera'."""
    api_mod = _import_api()

    scene = mock.MagicMock()
    scene.camera = None
    scene.render.engine = "CYCLES"
    scene.render.filepath = ""
    scene.view_layers = []

    with (
        mock.patch.object(api_mod.bpy, "context") as ctx,
        mock.patch.object(api_mod.bpy, "data") as bpy_data,
        mock.patch.object(api_mod, "get_active_scene_name", return_value="Scene"),
        mock.patch.object(api_mod, "get_frames", return_value="1-1"),
        mock.patch.object(api_mod.ocio, "get_ocio_path", return_value=""),
    ):
        ctx.scene = scene
        bpy_data.filepath = "/proj/scene.blend"
        api_mod.bpy.path.basename.return_value = "scene.blend"
        api = api_mod.BlenderSubmitter()
        settings = api.get_settings()

    assert settings.camera_selection == "Use Default Camera"


def test_get_settings_populates_gpu_from_helper():
    """get_settings reads GPU settings via resolve_gpu_settings."""
    api_mod = _import_api()

    scene = mock.MagicMock()
    scene.camera = None
    scene.render.engine = "CYCLES"
    scene.render.filepath = ""
    scene.view_layers = []

    with (
        mock.patch.object(api_mod.bpy, "context") as ctx,
        mock.patch.object(api_mod.bpy, "data") as bpy_data,
        mock.patch.object(api_mod, "get_active_scene_name", return_value="Scene"),
        mock.patch.object(api_mod, "get_frames", return_value="1-1"),
        mock.patch.object(api_mod, "resolve_gpu_settings", return_value=(True, "CUDA")),
        mock.patch.object(api_mod.ocio, "get_ocio_path", return_value=""),
    ):
        ctx.scene = scene
        bpy_data.filepath = "/proj/scene.blend"
        api_mod.bpy.path.basename.return_value = "scene.blend"
        api = api_mod.BlenderSubmitter()
        settings = api.get_settings()

    assert settings.enable_gpu is True
    assert settings.gpu_device == "CUDA"


def test_blender_submitter_settings_gpu_device_defaults_to_none_sentinel():
    """The default gpu_device must be the "NONE" sentinel, not "None"."""
    api_mod = _import_api()
    assert api_mod.BlenderSubmitterSettings().gpu_device == "NONE"


def test_get_settings_uses_scene_camera_when_present():
    api_mod = _import_api()

    scene = mock.MagicMock()
    scene.camera.name = "RenderCam"
    scene.render.engine = "CYCLES"
    scene.render.filepath = ""
    scene.view_layers = []

    with (
        mock.patch.object(api_mod.bpy, "context") as ctx,
        mock.patch.object(api_mod.bpy, "data") as bpy_data,
        mock.patch.object(api_mod, "get_active_scene_name", return_value="Scene"),
        mock.patch.object(api_mod, "get_frames", return_value="1-1"),
        mock.patch.object(api_mod.ocio, "get_ocio_path", return_value=""),
    ):
        ctx.scene = scene
        bpy_data.filepath = "/proj/scene.blend"
        api_mod.bpy.path.basename.return_value = "scene.blend"
        api = api_mod.BlenderSubmitter()
        settings = api.get_settings()

    assert settings.camera_selection == "RenderCam"


def test_get_settings_populates_ocio_config_path():
    api_mod = _import_api()

    scene = mock.MagicMock()
    scene.camera = None
    scene.render.engine = "CYCLES"
    scene.render.filepath = ""
    scene.view_layers = []

    with (
        mock.patch.object(api_mod.bpy, "context") as ctx,
        mock.patch.object(api_mod.bpy, "data") as bpy_data,
        mock.patch.object(api_mod, "get_active_scene_name", return_value="Scene"),
        mock.patch.object(api_mod, "get_frames", return_value="1-1"),
        mock.patch.object(api_mod.ocio, "get_ocio_path", return_value="/color/config.ocio"),
    ):
        ctx.scene = scene
        bpy_data.filepath = "/proj/scene.blend"
        api_mod.bpy.path.basename.return_value = "scene.blend"
        api = api_mod.BlenderSubmitter()
        settings = api.get_settings()

    assert settings.ocio_config_path == "/color/config.ocio"


def test_build_common_layer_settings_populates_renderable_cameras():
    """renderable_camera_names must be populated so 'All Renderable Cameras' works."""
    api_mod = _import_api()

    settings = api_mod.BlenderSubmitterSettings()
    settings.scene_name = "Scene"
    settings.frame_list = "1-1"

    with mock.patch.object(
        api_mod, "get_renderable_cameras", return_value=["CamA", "CamB"]
    ) as get_cams:
        api = api_mod.BlenderSubmitter()
        common = api._build_common_layer_settings(settings)

    get_cams.assert_called_once_with("Scene")
    assert common.renderable_camera_names == ["CamA", "CamB"]


def test_build_common_layer_settings_propagates_bad_scene_name():
    """An unresolvable scene name must surface (KeyError), not be swallowed —
    a silent [] would hide a real misconfiguration."""
    api_mod = _import_api()

    settings = api_mod.BlenderSubmitterSettings()
    settings.scene_name = "Nonexistent"
    settings.frame_list = "1-1"

    with mock.patch.object(api_mod, "get_renderable_cameras", side_effect=KeyError("Nonexistent")):
        api = api_mod.BlenderSubmitter()
        with pytest.raises(KeyError):
            api._build_common_layer_settings(settings)


def test_build_common_layer_settings_empty_when_no_cameras():
    """A scene with no renderable cameras yields an empty camera dimension."""
    api_mod = _import_api()

    settings = api_mod.BlenderSubmitterSettings()
    settings.scene_name = "Scene"
    settings.frame_list = "1-1"

    with mock.patch.object(api_mod, "get_renderable_cameras", return_value=[]):
        api = api_mod.BlenderSubmitter()
        common = api._build_common_layer_settings(settings)

    assert common.renderable_camera_names == []


# ---------------------------------------------------------------------------
# _resolve_view_layer_names — shared by the GUI and the unified API path so
# both honor view_layer_selection identically (the reviewer's dedup concern).
# ---------------------------------------------------------------------------


def test_resolve_view_layers_empty_selection_renders_all():
    """Empty selection expands to every renderable view layer."""
    api_mod = _import_api()

    settings = api_mod.BlenderSubmitterSettings()
    settings.scene_name = "Scene"
    settings.view_layer_selection = ""

    with mock.patch.object(
        api_mod, "get_renderable_view_layers", return_value=["View Layer", "Extra"]
    ) as get_layers:
        api = api_mod.BlenderSubmitter()
        layers = api._resolve_view_layer_names(settings)

    get_layers.assert_called_once_with("Scene")
    assert layers == ["View Layer", "Extra"]


def test_resolve_view_layers_all_sentinel_renders_all():
    """The 'All Renderable Layers' sentinel expands to every renderable layer."""
    api_mod = _import_api()

    settings = api_mod.BlenderSubmitterSettings()
    settings.scene_name = "Scene"
    settings.view_layer_selection = "All Renderable Layers"

    with mock.patch.object(api_mod, "get_renderable_view_layers", return_value=["A", "B"]):
        api = api_mod.BlenderSubmitter()
        layers = api._resolve_view_layer_names(settings)

    assert layers == ["A", "B"]


def test_resolve_view_layers_single_selection_renders_only_it():
    """A specific selection renders only that layer, without scanning all layers."""
    api_mod = _import_api()

    settings = api_mod.BlenderSubmitterSettings()
    settings.scene_name = "Scene"
    settings.view_layer_selection = "Beauty"

    with mock.patch.object(
        api_mod, "get_renderable_view_layers", side_effect=AssertionError("must not scan")
    ):
        api = api_mod.BlenderSubmitter()
        layers = api._resolve_view_layer_names(settings)

    assert layers == ["Beauty"]


def test_resolve_view_layers_empty_scene_name_raises():
    """An empty scene_name fails fast with an actionable error rather than
    falling back to job_name and producing a confusing KeyError downstream."""
    from deadline.client.exceptions import DeadlineOperationError

    api_mod = _import_api()

    settings = api_mod.BlenderSubmitterSettings()
    settings.job_name = "myfile.blend"  # a .blend name, NOT a scenes key
    settings.scene_name = ""

    api = api_mod.BlenderSubmitter()
    with pytest.raises(DeadlineOperationError, match="scene_name"):
        api._resolve_view_layer_names(settings)
