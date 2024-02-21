# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

from .default_blender_handler import DefaultBlenderHandler
from .cycles_blender_handler import CyclesHandler
from .workbench_blender_handler import WorkbenchHandler

__all__ = [
    "DefaultBlenderHandler",
    "CyclesHandler",
    "WorkbenchHandler",
    "get_render_handler",
]


def get_render_handler(renderer: str = "eevee") -> DefaultBlenderHandler:
    """
    Returns the render handler instance for the given renderer.

    Args:
        renderer (str, optional): The renderer to get the render handler of.
            Defaults to "Eevee".

    Returns the Render Handler instance for the given renderer.
    """
    if renderer == "eevee":
        return DefaultBlenderHandler()
    if renderer == "cycles":
        return CyclesHandler()
    if renderer == "workbench":
        return WorkbenchHandler()

    raise RuntimeError(f"Unsupported renderer: {renderer}")
