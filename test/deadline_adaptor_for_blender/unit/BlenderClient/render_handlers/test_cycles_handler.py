# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
import io
from contextlib import redirect_stdout
from typing import Dict
from unittest.mock import Mock, patch

import bpy
import pytest

from deadline_adaptor_for_blender.BlenderClient.render_handlers.cycles_handler import CyclesHandler


@pytest.fixture()
def cycleshandler():
    return CyclesHandler()


class TestCyclesHandler:
    @pytest.mark.parametrize("args", [{"scene": "Scene"}])
    @patch.object(bpy.data, "scenes")
    @patch.object(bpy.context, "window")
    def test_set_scene(
        self, mock_window: Mock, mock_scenes: Mock, cycleshandler: CyclesHandler, args: Dict
    ):
        # GIVEN
        mock_scene = Mock(name="Scene")
        mock_scenes.get.return_value = mock_scene

        # Set mock scene to have three layers marked for rendering
        mock_scene.view_layers = [Mock(use=True), Mock(use=True), Mock(use=True)]
        out = io.StringIO()

        # WHEN
        with redirect_stdout(out):
            cycleshandler.set_scene(args)

        # THEN
        assert mock_window.scene == mock_scene
        # Test to make sure we're printing out the configuration string to set the number
        # of outputs in the Adaptor.
        assert out.getvalue() == "BlenderAdaptor Configuration: Performing 3 renders.\n"

    @pytest.mark.parametrize("args", [{"scene": "Scene"}])
    @patch.object(bpy.data, "scenes")
    @patch.object(bpy.context, "window")
    def test_set_scene_no_usable_layers(
        self, mock_window: Mock, mock_scenes: Mock, cycleshandler: CyclesHandler, args: Dict
    ):
        # GIVEN
        mock_scene = Mock(name="Scene")
        mock_scenes.get.return_value = mock_scene

        # Set mock scene to have three layers marked for rendering
        mock_scene.view_layers = [Mock(use=False), Mock(use=False), Mock(use=False)]
        out = io.StringIO()

        # WHEN
        with redirect_stdout(out):
            cycleshandler.set_scene(args)

        # THEN
        assert mock_window.scene == mock_scene
        assert out.getvalue() == ""

    @pytest.mark.parametrize("args", [{}])
    @patch.object(bpy.data, "scenes")
    @patch.object(bpy.context, "window")
    def test_set_scene_no_scene(
        self, mock_window: Mock, mock_scene: Mock, cycleshandler: CyclesHandler, args: Dict
    ):
        # GIVEN
        mock_window.scene = mock_scene["DefaultScene"]

        # WHEN
        cycleshandler.set_scene(args)

        # THEN
        assert mock_window.scene == mock_scene["DefaultScene"]

    @pytest.mark.parametrize("args", [{"scene": "BadScene"}])
    @patch.object(bpy.data, "scenes")
    @patch.object(bpy.context, "window")
    def test_set_scene_throws_exception(
        self, mock_window: Mock, mock_scenes: Mock, cycleshandler: CyclesHandler, args: Dict
    ):
        # WHEN
        mock_scenes.get.side_effect = Exception("ERROR")

        # THEN
        with pytest.raises(Exception) as exc_info:
            cycleshandler.set_scene(args)
        assert str(exc_info.value) == "ERROR"

    @pytest.mark.parametrize("args", [{"layer": "Layer"}])
    @patch.object(bpy.context, "scene")
    @patch.object(bpy.context, "window")
    def test_set_layer(
        self, mock_window: Mock, mock_scene: Mock, cycleshandler: CyclesHandler, args: Dict
    ):
        # GIVEN

        out = io.StringIO()

        # WHEN
        with redirect_stdout(out):
            cycleshandler.set_layer(args)

        # THEN
        mock_window.view_layer.assert_not_called()
        assert (
            out.getvalue()
            == "Active scene is set to use Cycles, rendering all renderable layers.\n"
        )

    @pytest.mark.parametrize("args", [{}])
    @patch.object(bpy.context, "scene")
    @patch.object(bpy.context, "window")
    def test_set_layer_no_layer(
        self, mock_window: Mock, mock_scene: Mock, cycleshandler: CyclesHandler, args: Dict
    ):
        # GIVEN
        mock_window.view_layer = mock_scene.view_layers["DefaultLayer"]

        # WHEN
        cycleshandler.set_layer(args)

        # THEN
        assert mock_window.view_layer == mock_scene.view_layers["DefaultLayer"]
