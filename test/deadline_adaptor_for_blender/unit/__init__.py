# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

import sys
from unittest.mock import MagicMock

# we must mock bpy before importing client code
bpy_modules = ["bpy", "bpy.ops", "bpy.context", "bpy.types", "bpy.data"]

for module in bpy_modules:
    sys.modules[module] = MagicMock()
