# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

"""
common.py

This file contains common values and UI elements used across multiple Blender Submitter panels.
"""

DEADLINE_PT_PANEL_NAME = "PROPERTIES_PT_DeadlineSubmitter"
SERVICE_NAME = "Amazon Deadline Cloud"


def section_label(parent, label):
    row = parent.row()
    row.separator()
    row.separator()
    row.label(text=label)
