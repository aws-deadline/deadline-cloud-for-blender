# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

from .default_blender_handler import DefaultBlenderHandler


class WorkbenchHandler(DefaultBlenderHandler):
    RENDER_ENGINE_NAME = "BLENDER_WORKBENCH"
