# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

from __future__ import annotations

import os
import ctypes
import sys
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


def windows_pipe_exists(pipe_path: str) -> bool:
    """Checks if a Windows Named Pipe exists using native kernel32 calls."""
    if not pipe_path:
        return False

    # Standard disk file fallback
    if sys.platform != "win32":
        return os.path.exists(pipe_path)

    # Call Win32 WaitNamedPipeW with a 0ms timeout
    # Returns non-zero if a pipe instance exists
    result = ctypes.windll.kernel32.WaitNamedPipeW(pipe_path, 0)
    if result != 0:
        return True

    # GetLastError check
    # ERROR_PIPE_BUSY (231) or ERROR_ACCESS_DENIED (5) means the pipe exists!
    last_error = ctypes.GetLastError()
    return last_error in (231, 5)


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

    if not windows_pipe_exists(server_path):
        raise OSError(
            "BlenderClient cannot connect to the Adaptor because the server at the path defined by "
            "the environment variable BLENDER_ADAPTOR_SERVER_PATH does not exist. Got: "
            f"{os.environ['BLENDER_ADAPTOR_SERVER_PATH']}"
        )

    client = BlenderClient(server_path)
    client.poll()


if __name__ == "__main__":  # pragma: no cover
    main()
