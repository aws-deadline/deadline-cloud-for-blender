# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

from collections import defaultdict

from .blender_handler_base import BlenderHandlerBase
from .cycles_handler import CyclesHandler
from .render_handler_interface import RenderHandlerInterface

renderers = defaultdict(
    lambda: CyclesHandler,
    {
        "BLENDER_WORKBENCH": BlenderHandlerBase,
        "CYCLES": CyclesHandler,
    },
)


def get_render_handler(renderer: str) -> RenderHandlerInterface:
    """
    Returns the render handler instance for the given renderer.

    Args:
        renderer (str, optional): The renderer to get the render handler of.
            Defaults to "mayaSoftware".

    Returns:
        _RenderHandlerInterface: The Render Handler instance for the given renderer
    """
    return renderers[renderer]()
