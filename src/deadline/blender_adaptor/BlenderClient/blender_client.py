# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

from __future__ import annotations

import os
from types import FrameType
from typing import Optional

import bpy

# The blender Adaptor adds the `openjd` namespace directory to PYTHONPATH,
# so that importing just the adaptor_runtime_client should work.
try:
    from adaptor_runtime_client import ClientInterface
    from blender_adaptor.BlenderClient.render_handlers import get_render_handler
except (ImportError, ModuleNotFoundError):
    from openjd.adaptor_runtime_client import ClientInterface

    from deadline.blender_adaptor.BlenderClient.render_handlers import get_render_handler


class BlenderClient(ClientInterface):
    def __init__(self, server_path: str) -> None:
        super().__init__(server_path=server_path)
        print(f"BlenderClient: Blender Version {bpy.app.version_string}")
        self.actions.update({"render_engine": self.set_renderer})

    def set_renderer(self, renderer: dict):
        render_handler = get_render_handler(renderer["render_engine"])
        self.actions.update(render_handler.action_dict)

    def close(self, args: Optional[dict] = None) -> None:
        bpy.ops.wm.quit_blender()

    def graceful_shutdown(self, signum: int, frame: FrameType | None):
        bpy.ops.wm.quit_blender()


def main():
    server_path = os.environ.get("BLENDER_ADAPTOR_SERVER_PATH")
    if not server_path:
        raise OSError(
            "BlenderClient cannot connect to the Adaptor because the environment variable "
            "BLENDER_ADAPTOR_SERVER_PATH does not exist"
        )

    if not os.path.exists(server_path):
        raise OSError(
            "BlenderClient cannot connect to the Adaptor because the server at the path defined by "
            "the environment variable BLENDER_ADAPTOR_SERVER_PATH does not exist. Got: "
            f"{os.environ['BLENDER_ADAPTOR_SERVER_PATH']}"
        )

    client = BlenderClient(server_path)
    client.poll()


if __name__ == "__main__":  # pragma: no cover
    main()
