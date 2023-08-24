# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
from typing import Dict, List
from unittest.mock import Mock, patch

import bpy
import pytest

from deadline_adaptor_for_blender.BlenderClient.render_handlers.blender_handler_base import (
    BlenderHandlerBase,
)


@pytest.fixture()
def blenderhandler():
    return BlenderHandlerBase()


class TestBlenderHandler:
    @pytest.mark.parametrize("args", [{"frame": 99}])
    @patch.object(bpy.ops.render, "render")
    @patch.object(bpy.context, "scene")
    def test_start_render(
        self,
        mock_scene: Mock,
        bpy_ops_render: Mock,
        blenderhandler: BlenderHandlerBase,
        args: Dict,
    ):
        """Tests that starting a render calls the correct bpy functions"""
        # GIVEN
        blenderhandler.render_kwargs = {"animation": True, "write_still": False}
        # WHEN
        blenderhandler.start_render(args)

        # THEN
        assert mock_scene.frame_start == args["frame"]
        assert mock_scene.frame_end == args["frame"]
        bpy_ops_render.assert_called_once_with(
            animation=blenderhandler.render_kwargs["animation"],
            write_still=blenderhandler.render_kwargs["write_still"],
        )

    @pytest.mark.parametrize("args", [{}])
    @patch.object(bpy.ops.render, "render")
    def test_start_render_no_frame(
        self, bpy_ops_render: Mock, blenderhandler: BlenderHandlerBase, args: Dict
    ):
        # GIVEN
        blenderhandler.render_kwargs = {"animation": True}
        # WHEN
        with pytest.raises(RuntimeError) as exc_info:
            blenderhandler.start_render(args)

        # THEN
        assert str(exc_info.value) == "BlenderClient: start_render called without a frame number."
        bpy_ops_render.assert_not_called()

    @pytest.mark.parametrize("args", [{"output_path": "/some/output/path_####"}])
    @patch.object(bpy.context, "scene")
    def test_output_path_override(
        self, mock_scene: Mock, blenderhandler: BlenderHandlerBase, args: Dict
    ):
        # WHEN
        blenderhandler.output_path_override(args)

        # THEN
        assert mock_scene.render.filepath == args["output_path"]

    @pytest.mark.parametrize("args", [{}])
    @patch.object(bpy.context, "scene")
    def test_output_path_override_no_path(
        self, mock_scene: Mock, blenderhandler: BlenderHandlerBase, args: Dict
    ):
        # GIVEN
        default_path = "/default/path"
        mock_scene.render.filepath = default_path

        # WHEN
        blenderhandler.output_path_override(args)

        # THEN
        assert mock_scene.render.filepath == default_path

    @pytest.mark.parametrize("args", [{"output_path": ""}])
    @patch.object(bpy.context, "scene")
    def test_output_path_override_empty_string(
        self, mock_scene: Mock, blenderhandler: BlenderHandlerBase, args: Dict
    ):
        # GIVEN
        default_path = "/default/path"
        mock_scene.render.filepath = default_path

        # WHEN
        blenderhandler.output_path_override(args)

        # THEN
        assert mock_scene.render.filepath == default_path

    @pytest.mark.parametrize("args", [{"scene": "Scene"}])
    @patch.object(bpy.data, "scenes")
    @patch.object(bpy.context, "window")
    def test_set_scene(
        self, mock_window: Mock, mock_scene: Mock, blenderhandler: BlenderHandlerBase, args: Dict
    ):
        # WHEN
        blenderhandler.set_scene(args)

        # THEN
        assert mock_window.scene == mock_scene[args["scene"]]

    @pytest.mark.parametrize("args", [{}])
    @patch.object(bpy.data, "scenes")
    @patch.object(bpy.context, "window")
    def test_set_scene_no_scene(
        self, mock_window: Mock, mock_scene: Mock, blenderhandler: BlenderHandlerBase, args: Dict
    ):
        # GIVEN
        mock_window.scene = mock_scene["DefaultScene"]

        # WHEN
        blenderhandler.set_scene(args)

        # THEN
        assert mock_window.scene == mock_scene["DefaultScene"]

    @pytest.mark.parametrize("args", [{"scene": "BadScene"}])
    @patch.object(bpy.data, "scenes")
    @patch.object(bpy.context, "window")
    def test_set_scene_throws_exception(
        self, mock_window: Mock, mock_scene: Mock, blenderhandler: BlenderHandlerBase, args: Dict
    ):
        # WHEN
        mock_scene.__getitem__.side_effect = Exception("ERROR")

        # THEN
        with pytest.raises(Exception) as exc_info:
            blenderhandler.set_scene(args)
        assert str(exc_info.value) == "ERROR"

    @pytest.mark.parametrize("args", [{"layer": "Layer"}])
    @patch.object(bpy.context, "scene")
    @patch.object(bpy.context, "window")
    def test_set_layer(
        self, mock_window: Mock, mock_scene: Mock, blenderhandler: BlenderHandlerBase, args: Dict
    ):
        # WHEN
        blenderhandler.set_layer(args)

        # THEN
        assert mock_window.view_layer == mock_scene.view_layers[args["layer"]]

    @pytest.mark.parametrize("args", [{}])
    @patch.object(bpy.context, "scene")
    @patch.object(bpy.context, "window")
    def test_set_layer_no_layer(
        self, mock_window: Mock, mock_scene: Mock, blenderhandler: BlenderHandlerBase, args: Dict
    ):
        # GIVEN
        mock_window.view_layer = mock_scene.view_layers["DefaultLayer"]

        # WHEN
        blenderhandler.set_layer(args)

        # THEN
        assert mock_window.view_layer == mock_scene.view_layers["DefaultLayer"]

    @pytest.mark.parametrize("args", [{"animation": True}])
    def test_set_animation(self, blenderhandler: BlenderHandlerBase, args: Dict):
        # WHEN
        blenderhandler.set_animation(args)

        # THEN
        assert blenderhandler.render_kwargs["animation"] == args["animation"]
        assert blenderhandler.render_kwargs["write_still"] != args["animation"]

    @pytest.mark.parametrize("args", [{}])
    def test_set_animation_no_value(self, blenderhandler: BlenderHandlerBase, args: Dict):
        # WHEN
        with pytest.raises(RuntimeError) as exc_info:
            blenderhandler.set_animation(args)

        # THEN
        assert (
            str(exc_info.value) == "BlenderClient: set_animation called without an animation value."
        )
        assert "animation" not in blenderhandler.render_kwargs
        assert "write_still" not in blenderhandler.render_kwargs

    @pytest.mark.parametrize(
        "stdout, expected_matches",
        [
            (
                "An output string that should not match",
                0,
            ),
            (
                "Path '/some/path/to/file.txt' not found\n"
                + "Path '/another/matching/path.jpeg' not found",
                2,
            ),
            (
                "Path '/some/path/to/file.txt' not found\n"
                + "Another line that should not match\n"
                + "Path '/another/matching/path.jpeg' not found",
                2,
            ),
            (
                "Path '/some/path/to/file.txt' not found\n"
                + "Path 'C:\\a\\windows\\style\\path' not found\n"
                + "Another line that should not match\n"
                + "Path '/another/matching/path.jpeg' not found\n"
                + "Path 'C:\\a\\path\\with\\a\\trailing\\newline' not found\n",
                4,
            ),
        ],
    )
    @patch("io.StringIO")
    def test_get_missing(
        self,
        mock_stringio: Mock,
        stdout: str,
        expected_matches: int,
        blenderhandler: BlenderHandlerBase,
    ):
        # GIVEN
        mock = Mock()
        mock_stringio.return_value = mock
        mock.getvalue.return_value = stdout

        # WHEN
        missing_paths = blenderhandler._get_missing()

        # THEN
        assert len(missing_paths) == expected_matches

    @pytest.mark.parametrize(
        "assets_list, expected_assets",
        [
            (
                [Mock(filepath="//test_asset.png")],
                1,
            ),
            (
                [
                    Mock(filepath="//test_asset.png"),
                    Mock(filepath=None),
                ],
                1,
            ),
            (
                [
                    Mock(filepath="//test_asset.png"),
                    Mock(filepath=""),
                    Mock(filepath=None),
                    Mock(filepath="C:\\windows\\path\\to\\test_asset.png"),
                    Mock(filepath="//../../another_asset.jpeg"),
                ],
                3,
            ),
        ],
    )
    def test_get_assets(
        self,
        assets_list: List,
        expected_assets: int,
        blenderhandler: BlenderHandlerBase,
        monkeypatch,
    ):
        # GIVEN
        blenderhandler._BLENDER_EXTERNAL_TYPES = ["images"]
        monkeypatch.setattr(bpy.data, "images", assets_list)

        # WHEN
        returned_assets = blenderhandler._get_assets()

        # THEN
        assert len(returned_assets) == expected_assets

    @patch.object(bpy, "data")
    @patch.object(bpy, "context")
    def test_resolve_assets(
        self,
        mock_bpy_context: Mock,
        mock_bpy_data: Mock,
        blenderhandler: BlenderHandlerBase,
        monkeypatch,
    ):
        # GIVEN
        asset_path_1 = "/directory/A/test/path"

        mock_get_missing = Mock()
        mock_get_missing.side_effect = [[asset_path_1], []]

        mock_get_assets = Mock()
        mock_get_assets.side_effect = [[Mock(filepath=asset_path_1)]]

        data = {"strict_error_checking": False}

        mock_map_path = Mock()

        monkeypatch.setattr(blenderhandler, "_get_assets", mock_get_assets)
        monkeypatch.setattr(blenderhandler, "_get_missing", mock_get_missing)

        # WHEN
        blenderhandler.resolve_assets(mock_map_path, data)

        # THEN
        assert mock_get_missing.call_count == 2
        assert mock_get_assets.call_count == 1
        assert mock_map_path.call_count == 1

    @patch.object(bpy, "data")
    @patch.object(bpy, "context")
    def test_resolve_assets_fail_strict_error_checking(
        self,
        mock_bpy_context: Mock,
        mock_bpy_data: Mock,
        blenderhandler: BlenderHandlerBase,
        monkeypatch,
    ):
        # GIVEN
        asset_path_1 = "/A/test/path/asset1"
        asset_path_2 = "/A/test/path/asset2"
        asset_path_3 = "/A/test/path/asset3"

        mapped_path_1 = "/B/test/path/asset1"
        mapped_path_2 = "/B/test/path/asset2"

        mock_get_missing = Mock()
        mock_get_missing.side_effect = [
            [asset_path_1, asset_path_2],
            [asset_path_3],
            [asset_path_3],
        ]

        mock_get_assets = Mock()
        mock_get_assets.side_effect = [
            [
                Mock(filepath=asset_path_1, name_full="asset1"),
                Mock(filepath=asset_path_2, name_full="asset2"),
                Mock(filepath="//../a/relative/asset", name_full="relative1"),
            ],
            [
                Mock(filepath=mapped_path_1, name_full="asset1"),
                Mock(filepath=mapped_path_2, name_full="asset2"),
                Mock(filepath="//../a/relative/asset", name_full="relative1"),
                Mock(filepath=asset_path_3, name_full="asset3"),
            ],
        ]

        data = {"strict_error_checking": True}

        mock_map_path = Mock()
        mock_map_path.side_effect = [mapped_path_1, mapped_path_2, asset_path_3]

        monkeypatch.setattr(blenderhandler, "_get_assets", mock_get_assets)
        monkeypatch.setattr(blenderhandler, "_get_missing", mock_get_missing)

        # WHEN
        with pytest.raises(RuntimeError) as exc_info:
            blenderhandler.resolve_assets(mock_map_path, data)

        # THEN
        assert mock_get_missing.call_count == 3
        assert mock_get_assets.call_count == 2
        assert mock_map_path.call_count == 3
        assert str(exc_info.value).startswith("Unable to resolve the following assets:")

    @patch.object(bpy, "data")
    @patch.object(bpy, "context")
    def test_resolve_assets_fail_no_strict_error_checking(
        self,
        mock_bpy_context: Mock,
        mock_bpy_data: Mock,
        blenderhandler: BlenderHandlerBase,
        monkeypatch,
    ):
        # GIVEN
        asset_path_1 = "/A/test/path/asset1"
        asset_path_2 = "/A/test/path/asset2"
        asset_path_3 = "/A/test/path/asset3"

        mapped_path_1 = "/B/test/path/asset1"
        mapped_path_2 = "/B/test/path/asset2"

        mock_get_missing = Mock()
        mock_get_missing.side_effect = [
            [asset_path_1, asset_path_2],
            [asset_path_3],
            [asset_path_3],
        ]

        mock_get_assets = Mock()
        mock_get_assets.side_effect = [
            [
                Mock(filepath=asset_path_1, name_full="asset1"),
                Mock(filepath=asset_path_2, name_full="asset2"),
                Mock(filepath="//../a/relative/asset", name_full="relative1"),
            ],
            [
                Mock(filepath=mapped_path_1, name_full="asset1"),
                Mock(filepath=mapped_path_2, name_full="asset2"),
                Mock(filepath="//../a/relative/asset", name_full="relative1"),
                Mock(filepath=asset_path_3, name_full="asset3"),
            ],
        ]

        data = {"strict_error_checking": False}

        mock_map_path = Mock()
        mock_map_path.side_effect = [mapped_path_1, mapped_path_2, asset_path_3]

        monkeypatch.setattr(blenderhandler, "_get_assets", mock_get_assets)
        monkeypatch.setattr(blenderhandler, "_get_missing", mock_get_missing)

        # WHEN
        blenderhandler.resolve_assets(mock_map_path, data)

        # THEN
        assert mock_get_missing.call_count == 3
        assert mock_get_assets.call_count == 2
        assert mock_map_path.call_count == 3
