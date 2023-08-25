# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

from abc import ABC, abstractmethod
from typing import Any, Callable, Dict


class RenderHandlerInterface(ABC):
    action_dict: Dict[str, Callable] = {}
    render_kwargs: Dict[str, Any]

    def __init__(self) -> None:
        """
        Constructor for the Blender handler.
        """
        self.action_dict = {
            "scene": self.set_scene,
            "layer": self.set_layer,
            "output_path": self.output_path_override,
            "animation": self.set_animation,
            "start_render": self.start_render,
            "resolve_assets": self.resolve_assets,
        }

        self.render_kwargs = {}

    @abstractmethod
    def start_render(self, data: dict) -> None:
        """
        Starts a render in Blender.

        Args:
            data (dict): The data given from the Adaptor. Keys expected: ['frame']
        """
        pass  # pragma: no cover

    @abstractmethod
    def output_path_override(self, data: dict) -> None:
        """
        Overrides the output file path.

        Args:
            data (dict): The data given from the Adaptor. Keys expected: ['output_path']
        """
        pass  # pragma: no cover

    @abstractmethod
    def set_scene(self, data: dict) -> None:
        """
        Sets the active scene.

        Args:
            data (dict): The data given from the Adaptor. Keys expected: ['scene']
        """
        pass  # pragma: no cover

    @abstractmethod
    def set_layer(self, data: dict) -> None:
        """
        Sets the active layer.

        Args:
            data (dict): The data given from the Adaptor. Keys expected: ['layer']
        """
        pass  # pragma: no cover

    @abstractmethod
    def set_animation(self, data: dict) -> None:
        """
        Set animation render arg.

        Args:
            data (dict): The data given from the Adaptor. Keys expected: ['animation']
        """
        pass  # pragma: no cover

    @abstractmethod
    def resolve_assets(self, map_path_callback, data: dict) -> None:
        """
        Resolve paths to assets using absolute paths by applying pathmapping rules.

        Args:
            map_path_callback (function): A callback to the Client 'map_path' function.
        """
        pass  # pragma: no cover
