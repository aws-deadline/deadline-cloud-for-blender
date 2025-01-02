# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

import bpy
import logging

from .default_blender_handler import DefaultBlenderHandler

_logger = logging.getLogger(__name__)


class CyclesHandler(DefaultBlenderHandler):
    RENDER_ENGINE_NAME = "CYCLES"

    def set_gpu_device(self, data: dict) -> None:
        """
        Enables GPU rendering on the worker if specified in the user's configuration.

        Args:
            data (dict): The data given from the Adaptor. Keys expected: ['gpu_device']

        Raises:
            RuntimeError: If no devices of the specified type are available
        """

        gpu_device = data.get("gpu_device", "NONE")
        if gpu_device == "NONE":
            bpy.context.scene.cycles.device = "CPU"
            return

        # Supported GPU devices for Blender 3.6 and 4.2:
        # https://docs.blender.org/manual/en/3.6/render/cycles/gpu_rendering.html
        # https://docs.blender.org/manual/en/4.2/render/cycles/gpu_rendering.html
        GPU_DEVICE_TYPES_ITER = iter(["OPTIX", "CUDA", "HIP", "ONEAPI", "METAL"])

        cycles_preferences = bpy.context.preferences.addons["cycles"].preferences
        cycles_preferences.refresh_devices()

        # Attempt to set the user's chosen render device.
        # If it isn't available, loop through device types to find another GPU to use.
        devices = self._list_compatible_render_devices(cycles_preferences, gpu_device)
        while not devices and gpu_device != "NONE":
            _logger.warning(f'Device type "{gpu_device}" is not available on this worker.')
            gpu_device = next(GPU_DEVICE_TYPES_ITER, "NONE")
            _logger.warning(f'Attempting to use "{gpu_device}" instead.')
            devices = self._list_compatible_render_devices(cycles_preferences, gpu_device)

        bpy.context.scene.cycles.device = "GPU" if gpu_device != "NONE" else "CPU"
        cycles_preferences.compute_device_type = gpu_device
        _logger.debug(f"Set render device to {gpu_device}.")

    def _list_compatible_render_devices(self, preferences, gpu_device: str) -> list[str]:
        try:
            return preferences.get_devices_for_type(gpu_device)
        except ValueError as ve:
            _logger.warning(str(ve))
            return []
