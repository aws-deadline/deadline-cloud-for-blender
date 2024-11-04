# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

from __future__ import annotations

import logging
import os
from typing import Optional

import bpy  # type: ignore

_logger = logging.getLogger(__name__)


class DefaultBlenderHandler:
    RENDER_ENGINE_NAME = "BLENDER_EEVEE_NEXT" if bpy.app.version >= (4, 2, 0) else "BLENDER_EEVEE"

    def __init__(self):
        """Initialize this handler."""

        # Define Blender actions to perform, each keyed to a callback function.
        # These cross-reference the Action instances created and queued in the Blender adaptor.
        self.action_dict = {
            "scene_file": self.set_scene_file,
            "render_scene": self.set_render_scene,
            "view_layer": self.set_view_layer,
            "camera": self.set_camera,
            "output_dir": self.set_output_dir,
            "output_file_name": self.set_output_file_name,
            "output_format": self.set_output_format,
            "start_render": self.start_render,
        }

        # Set default values.
        self.camera_name = None
        self.scene_name = None
        self.output_dir = None
        self.output_file_name = None
        self.format = None
        self.view_layer_name = None

        _logger.debug(f"Initialized {self.__class__.__name__}")

    def _ensure_camera(self, data: dict) -> str:
        """
        Ensure that the camera provided in `data` exists in the scene and is renderable.
        Raises a RuntimeError otherwise.

        Returns the name of the camera.
        """
        camera: str = data.get("camera", self.camera_name)
        if camera is None:
            raise RuntimeError(f"No camera specified in data: {data}")

        # The ls function returns all cameras if they are set to renderable.
        scene_cameras = [
            cam.name for cam in bpy.data.scenes[self.scene_name].objects if cam.type == "CAMERA"
        ]
        if camera not in scene_cameras:
            raise RuntimeError(f"Camera {camera} does not exist.")

        if bpy.data.objects[camera].hide_render:
            raise RuntimeError(f"Camera {camera} is not renderable.")

        _logger.debug(f"Fetched camera to render: {camera}")
        return camera

    def _get_layer_to_render(self, data: dict) -> Optional[str]:
        """Gets the view_layer to render from the provided data.

        If no view_layer is specified in `data`, return None.
        """
        target = data.get("view_layer")
        if not target:
            _logger.debug("No view_layer specified in data.")
            return None

        # In Blender, set the right scene.
        scene = bpy.data.scenes[self.scene_name]
        bpy.context.window.scene = scene

        # Collect all layers that are set to render.
        enabled = {lyr.name for lyr in scene.view_layers if scene.view_layers[lyr.name].use}
        if target in enabled:
            _logger.debug(f"Fetched layer to render: {target}.")
            return target
        raise RuntimeError(
            f"view_layer {target} not found among available layers {sorted(enabled)}"
        )

    def start_render(self, data: dict) -> None:
        """
        Starts a render in Blender.

        Args:
            data (dict): The data given from the Adaptor. Keys expected: ['frame', 'camera']

        Raises:
            RuntimeError: If no camera was specified and no renderable camera was found
        """

        frame = data.get("frame")
        if frame is None:
            raise RuntimeError("BlenderClient: start_render called without a frame number.")

        bpy.context.scene.frame_start = frame
        bpy.context.scene.frame_end = frame

        # The camera fetched here is only for logging purposes.
        # The actual camera to render is set in the set_camera function,
        # and should have already been called as an Action.
        camera = self._ensure_camera(data)

        # Add layer and camera info to the output file path.
        bpy.context.scene.render.filepath = (
            f"{self.output_dir}/{self.view_layer_name}_{camera}_{self.output_file_name}"
        )
        _logger.debug(f"Set output file path to {bpy.context.scene.render.filepath}")
        _logger.debug(f"Rendering camera: {camera}")
        # The `animation` flag is required to correctly set the output file name.
        # See: https://docs.blender.org/api/current/bpy.ops.render.html#bpy.ops.render.render
        bpy.ops.render.render(animation=True, scene=self.scene_name)

        # This print statement (including flush) is required for Deadline to pick up successful task completion
        # See the Regex callbacks defined at `BlenderAdaptor/adaptor.py:_get_regex_callbacks`.
        print(f"BlenderClient: Finished Rendering Frame {frame}", flush=True)

    def set_camera(self, data: dict) -> None:
        """
        Sets the Camera that will be rendered.

        Args:
            data (dict): The data given from the Adaptor. Keys expected: ['camera']

        Raises:
            RuntimeError: If the camera is not renderable or does not exist
        """
        self.camera_name = data.get("camera")
        camera = self._ensure_camera(data)
        assert self.camera_name == camera, "Camera name mismatch: this should never happen."
        bpy.context.scene.camera = bpy.data.objects[camera]

    def set_render_scene(self, data: dict) -> None:
        """
        Sets the Scene that will be rendered and ensures it is set to the
        correct renderer.
        """
        self.scene_name = data.get("render_scene")
        bpy.context.window.scene = bpy.data.scenes[self.scene_name]
        _logger.debug(f"Set render engine: {self.RENDER_ENGINE_NAME}")
        bpy.context.scene.render.engine = self.RENDER_ENGINE_NAME

    def set_output_dir(self, data: dict) -> None:
        """
        Sets the output directory path.

        Args:
            data (dict): The data given from the Adaptor. Keys expected: ['output_dir']
        """
        output_dir = data.get("output_dir")
        if output_dir:
            self.output_dir = output_dir

    def set_output_file_name(self, data: dict) -> None:
        """
        Sets the output file name.

        Args:
            data (dict): The data given from the Adaptor. Keys expected: ['output_file_name']
        """
        output_file_name = data.get("output_file_name")
        _logger.debug(f"Set output file name: {output_file_name}")
        if output_file_name:
            self.output_file_name = output_file_name

    def set_output_format(self, data: dict) -> None:
        """
        Sets the output format.
        """
        format_ = data.get("output_format")
        _logger.debug(f"Set output format to {format_}")
        if format_:
            self.format = format_

    def set_view_layer(self, data: dict) -> None:
        """
        Sets the view_layer.

        For Blender, this means disable all layers except the one to render.

        Args:
            data (dict): The data given from the Adaptor. Keys expected: ['view_layer']

        Raises:
            RuntimeError: If the view_layer cannot be found
        """
        view_layer_name = self._get_layer_to_render(data)

        if view_layer_name is None:
            return

        for layer in bpy.context.window.scene.view_layers:
            layer.use = layer.name == view_layer_name
            _logger.debug(f"Set layer {layer.name} to render: {layer.use}")

        self.view_layer_name = view_layer_name

    def set_scene_file(self, data: dict):
        """Opens a Blender scene file.

        Args:
            data (dict): The data given from the Adaptor. Keys expected: ['scene_file']

        Raises:
            FileNotFoundError: If the file provided in the data dictionary does not exist.
        """
        file_path = data.get("scene_file", "")
        if not os.path.isfile(file_path):
            raise FileNotFoundError(f"The scene file '{file_path}' does not exist")
        bpy.ops.wm.open_mainfile(filepath=file_path)
