# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

import bpy
from pathlib import Path
import sys
import argparse
import os

# Blender 5.1+ auto-populates the OCIO env var with its bundled default config.
# The submitter treats any OCIO env var as a user-configured custom path, so
# under 5.1+ a default-install submission would ship Blender's bundled
# colormanagement tree and emit extra template entries not present in the
# baseline fixture. Clear OCIO before the submitter reads it, as minimal_test does.
if bpy.app.version >= (5, 1):
    os.environ.pop("OCIO", None)

from deadline_cloud_blender_submitter.open_deadline_cloud_dialog import (
    create_deadline_dialog,
    _create_bundle_internal,
)
from qtpy import QtWidgets

from deadline_cloud_blender_submitter.scene_settings_widget import (
    COMBO_DEFAULT_ALL_RENDERABLE_CAMERAS,
    COMBO_DEFAULT_ALL_RENDERABLE_LAYERS,
)

# Must match TASK_RUN_TIMEOUT_SECONDS in test_blender_submitters.py and the
# expected template: 1 hour 30 minutes.
TASK_RUN_TIMEOUT_HOURS = 1
TASK_RUN_TIMEOUT_MINUTES = 30


def main(job_history_dir: str, output_dir: str, scene_file: str):
    """
    Runs inside Blender. Opens the submitter dialog on scene_file (a copy of the
    minimal_test scene), turns on the Task Run timeout through the Timeouts box,
    and exports a job bundle.
    """
    bpy.ops.wm.open_mainfile(filepath=scene_file)

    bpy.context.scene.frame_start = 1
    bpy.context.scene.frame_end = 2
    bpy.context.scene.render.filepath = str(Path(output_dir) / "image_####")
    bpy.context.scene.render.engine = "CYCLES"
    bpy.context.scene.render.resolution_x = 640
    bpy.context.scene.render.resolution_y = 480

    QtWidgets.QApplication(sys.argv)
    widget = create_deadline_dialog()

    # Set the timeout through the widget, as a user would, so the test covers the
    # widget -> settings -> template path.
    row = widget.job_settings.timeouts_box.timeout_rows["Task Run"]
    if row.checkbox.isChecked():
        raise RuntimeError("The Task Run timeout should be off by default")
    row.checkbox.click()
    row.days_box.setValue(0)
    row.hours_box.setValue(TASK_RUN_TIMEOUT_HOURS)
    row.minutes_box.setValue(TASK_RUN_TIMEOUT_MINUTES)

    settings = widget.job_settings_type()
    widget.shared_job_settings.update_settings(settings)
    widget.job_settings.update_settings(settings)

    settings.view_layer_selection = COMBO_DEFAULT_ALL_RENDERABLE_LAYERS
    settings.camera_selection = COMBO_DEFAULT_ALL_RENDERABLE_CAMERAS
    settings.description = ""
    settings.include_adaptor_wheels = False
    settings.override_frame_range = False

    widget.shared_job_settings.shared_job_properties_box.set_parameter_value(
        {"name": "deadline:targetTaskRunStatus", "value": "READY"}
    )
    widget.shared_job_settings.shared_job_properties_box.set_parameter_value(
        {"name": "deadline:maxFailedTasksCount", "value": 20}
    )
    widget.shared_job_settings.shared_job_properties_box.set_parameter_value(
        {"name": "deadline:maxRetriesPerTask", "value": 5}
    )
    widget.shared_job_settings.shared_job_properties_box.set_parameter_value(
        {"name": "deadline:priority", "value": 50}
    )

    _create_bundle_internal(
        widget,
        job_history_dir,
        settings,
        widget.shared_job_settings.get_parameters(),
        widget.job_attachments.get_asset_references(),
        widget.host_requirements.get_requirements(),
        purpose="export",
        prompt_for_saving=False,
    )

    bpy.ops.wm.window_close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("job_history_dir")
    parser.add_argument("output_dir")
    parser.add_argument("scene_file")
    args = parser.parse_args(args=sys.argv[sys.argv.index("--") + 1 :])
    main(args.job_history_dir, args.output_dir, args.scene_file)
