# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

import sys
from unittest.mock import MagicMock

# Mock out UI code to test functions that use the submitter dialog.
mock_modules = [
    "PySide2",
    "PySide2.QtCore",
    "PySide2.QtGui",
    "PySide2.QtWidgets",
    "qtpy",
    "qtpy.QtCore",
    "qtpy.QtWidgets",
    "qtpy.QtGui",
    "deadline.client.ui.dialogs.submit_job_to_deadline_dialog",
    "bpy",
    "bpy.types",
]

for module in mock_modules:
    sys.modules[module] = MagicMock()
