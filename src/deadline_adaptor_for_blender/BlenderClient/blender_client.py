# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

from __future__ import annotations

import os
from types import FrameType
from typing import Optional

from openjobio_adaptor_runtime_client import HTTPClientInterface

from deadline_adaptor_for_blender.BlenderClient.render_handlers.get_render_handler import (
    get_render_handler,
)
from deadline_adaptor_for_blender.BlenderClient.render_handlers.render_handler_interface import (
    RenderHandlerInterface,
)

try:
    import bpy
except ImportError:  # pragma: no cover
    raise OSError("Could not find the Blender module. Are you running this inside of Blender?")


class BlenderClient(HTTPClientInterface):
    """
    Client that runs in Blender for the Blender Adaptor
    """

    handler: RenderHandlerInterface

    def __init__(self, socket_path: str) -> None:
        super().__init__(socket_path=socket_path)
        self.actions.update(
            {
                "renderer": self.set_renderer,
            }
        )

    def set_renderer(self, data: dict):
        self.handler = get_render_handler(data["renderer"])
        self.actions.update(self.handler.action_dict)

        # Wrap the handler's `resolve_assets` so we can pass the `map_path` callback to it.
        self.actions.update(
            {
                "resolve_assets": self.resolve_assets,
            }
        )

    def resolve_assets(self, data: dict) -> None:
        self.handler.resolve_assets(self.map_path, data)

    def close(self, args: Optional[dict] = None) -> None:
        bpy.ops.wm.quit_blender()

    def graceful_shutdown(self, signum: int, frame: FrameType | None):
        bpy.ops.wm.quit_blender()


def main():
    socket_path = os.environ.get("BLENDER_ADAPTOR_SOCKET_PATH")
    if not socket_path:
        raise OSError(
            "BlenderClient cannot connect to the Adaptor because the environment variable "
            "BLENDER_ADAPTOR_SOCKET_PATH does not exist"
        )

    if not os.path.exists(socket_path):
        raise OSError(
            "BlenderClient cannot connect to the Adaptor because the socket at the path defined by "
            "the environment variable BLENDER_ADAPTOR_SOCKET_PATH does not exist. Got: "
            f"{os.environ['BLENDER_ADAPTOR_SOCKET_PATH']}"
        )

    client = BlenderClient(socket_path)
    client.poll()


if __name__ == "__main__":  # pragma: no cover
    main()
