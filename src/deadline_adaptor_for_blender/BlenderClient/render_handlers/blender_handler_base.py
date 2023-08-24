# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

from __future__ import annotations

import io
import re
import uuid
from contextlib import redirect_stdout
from typing import Any, Callable, Dict, List, Set

try:
    import bpy
except ImportError:  # pragma: no cover
    raise OSError("Could not find the Blender module. Are you running this inside of Blender?")

from .render_handler_interface import RenderHandlerInterface


class BlenderHandlerBase(RenderHandlerInterface):
    action_dict: Dict[str, Callable[[Dict[str, Any]], None]] = {}
    render_kwargs: Dict[str, Any]

    _BLENDER_EXTERNAL_TYPES = [
        "libraries",
        "images",
        "volumes",
        "sounds",
        "movieclips",
        "fonts",
        "texts",
        "cache_files",
    ]

    def __init__(self) -> None:
        """
        Constructor for the Blender handler.
        """
        super().__init__()
        self.render_kwargs = {}

    def start_render(self, data: dict) -> None:
        """
        Starts a render in Blender.

        Args:
            data (dict): The data given from the Adaptor. Keys expected: ['frame']

        Raises:
            RuntimeError: If start_render is called without a frame number.
        """
        frame = data.get("frame")
        if frame is None:
            raise RuntimeError("BlenderClient: start_render called without a frame number.")
        bpy.context.scene.frame_start = frame
        bpy.context.scene.frame_end = frame

        bpy.ops.render.render(**self.render_kwargs)

    def output_path_override(self, data: dict) -> None:
        """
        Overrides the output file path.

        Args:
            data (dict): The data given from the Adaptor. Keys expected: ['output_path']
        """
        output_path = data.get("output_path", None)
        if output_path:
            bpy.context.scene.render.filepath = output_path

    def set_scene(self, data: dict) -> None:
        """
        Sets the active scene.

        Args:
            data (dict): The data given from the Adaptor. Keys expected: ['scene']
        """
        scene_name = data.get("scene", None)
        if scene_name:
            bpy.context.window.scene = bpy.data.scenes[scene_name]

    def set_layer(self, data: dict) -> None:
        """
        Sets the active layer.

        Args:
            data (dict): The data given from the Adaptor. Keys expected: ['layer']
        """
        layer = data.get("layer", None)
        if layer:
            bpy.context.window.view_layer = bpy.context.scene.view_layers[layer]

    def set_animation(self, data: dict) -> None:
        """
        Set animation render arg.

        Args:
            data (dict): The data given from the Adaptor. Keys expected: ['animation']

        Raises:
            RuntimeError: If set_animation is called without an animation value.
        """
        animation = data.get("animation")
        if animation is None:
            raise RuntimeError("BlenderClient: set_animation called without an animation value.")
        self.render_kwargs["animation"] = animation
        self.render_kwargs["write_still"] = not animation

    def resolve_assets(self, map_path_callback, data: dict) -> None:
        """
        Resolve paths to assets using absolute paths by applying pathmapping rules.

        Args:
            map_path_callback (function): A callback to the Client 'map_path' function.

        Raises:
            RuntimeError: If strict_error_checking is enabled and there are assets which cannot
                          be resolved.
        """
        # Workaround: There is a bug in Blender where if the active scene is from an external
        # library and that library is reloaded, Blender will crash. While resolving assets, we
        # will switch to a newly created temporary scene which will be cleaned up on script
        # completion. We will later switch to the proper scene during the `set_scene` action.

        # Generate a random name that will not clash with other scenes:
        temp_scene_name = str(uuid.uuid4())
        bpy.data.scenes.new(temp_scene_name)
        temp_scene = bpy.data.scenes[temp_scene_name]
        # Switch to temp scene
        bpy.context.window.scene = temp_scene

        # Used to keep track of which paths we've processed.
        processed_files: Set[str] = set()

        # Set prev_processed so that it doesn't match processed_files on the first loop.
        prev_processed = -1
        strict_error_checking = data.get("strict_error_checking", False)

        missing_assets = self._get_missing()
        # The main Blender project will be unaware of any missing assets it needs from
        # external libraries if those libraries are missing. We are looping here because
        # new missing assets may appear as we resolve and reload external libraries.
        while len(missing_assets) != 0:
            if len(processed_files) == prev_processed:
                error_str = f"Unable to resolve the following assets:\n{missing_assets}"
                if strict_error_checking:
                    raise RuntimeError(error_str)
                else:
                    print(error_str)
                    break

            prev_processed = len(processed_files)

            assets = self._get_assets()
            for asset in assets:
                if asset.filepath.startswith("//"):
                    # Skip assets using relative paths
                    continue

                if asset.name_full not in processed_files:
                    # If we haven't processed this path before, attempt to resolve it
                    # by applying pathmapping rules.
                    mapped_path = map_path_callback(asset.filepath)

                    # The map_path callback will return the same path if no rule is found.
                    # Since the path isn't changing, don't process it.
                    if asset.filepath != mapped_path:
                        asset.filepath = mapped_path
                        processed_files.add(asset.name_full)

                        if type(asset) is bpy.types.Library:
                            asset.reload()

            missing_assets = self._get_missing()

        # clean up temp scene
        bpy.data.scenes.remove(temp_scene)

    def _get_assets(self) -> List[bpy.types.bpy_struct]:
        """
        Builds a list of known external assets by performing asset introspection. The list of types
        are all the `bpy_struct` which have a filepath attribute (ie. all of the types which can be
        external to the main project)

        Returns:
            A set of external `bpy_struct` objects referenced by the project.
        """
        files = []  # type: ignore
        for ext_type in self._BLENDER_EXTERNAL_TYPES:
            for item in getattr(bpy.data, ext_type):
                filepath = getattr(item, "filepath", None)
                if filepath:  # If filepath exists, the asset is external
                    files.append(item)
        return files

    def _get_missing(self) -> List[str]:
        """
        Runs bpy.ops.file.report_missing_files() and parses the output to return a list of paths
        of missing assets.

        Returns:
            A list of strings representing paths to missing assets.
        """
        f = io.StringIO()
        with redirect_stdout(f):
            bpy.ops.file.report_missing_files()
        out = f.getvalue()
        out_lines = out.split("\n")

        missing_paths: List[str] = []
        for line in out_lines:
            found = re.search("Path '(.+)' not found", line)
            if found:
                missing_paths.append(found.group(1))

        return missing_paths
