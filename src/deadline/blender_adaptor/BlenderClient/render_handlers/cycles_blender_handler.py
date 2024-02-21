# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

from .default_blender_handler import DefaultBlenderHandler


class CyclesHandler(DefaultBlenderHandler):
    RENDER_ENGINE_NAME = "CYCLES"
