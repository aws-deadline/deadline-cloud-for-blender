# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

import bpy
from pathlib import Path
import sys
import argparse
import os

# Blender 5.1+ auto-populates the OCIO env var with its bundled default config.
# The submitter treats any OCIO env var as a user-configured custom path, so
# under 5.1+ a default-install submission would ship ~19 MB of Blender's
# bundled colormanagement tree and emit extra template entries not present in
# the baseline fixture. Force 5.1+ to match the 5.0 "no OCIO override" baseline
# by clearing OCIO before the submitter reads it.
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


def main(job_history_dir: str, output_dir: str):
    """
    This is a script that runs inside of Blender, it sets up the scene file and exports a  job bundle. This test covers multiple render layers and multiple cameras.
    """
    bpy.ops.wm.open_mainfile(filepath=str(Path(__file__).parent / "scene" / "test.blend"))

    bpy.context.scene.frame_start = 1
    bpy.context.scene.frame_end = 2
    bpy.context.scene.render.filepath = str(Path(output_dir) / "image_####")
    bpy.context.scene.render.engine = "CYCLES"
    bpy.context.scene.render.resolution_x = 640
    bpy.context.scene.render.resolution_y = 480

    QtWidgets.QApplication(sys.argv)
    widget = create_deadline_dialog()

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
    args = parser.parse_args(args=sys.argv[sys.argv.index("--") :])
    main(args.job_history_dir, args.output_dir)
