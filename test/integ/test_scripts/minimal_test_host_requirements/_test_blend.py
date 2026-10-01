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


def main(job_history_dir: str, output_dir_in_scene: str, output_dir_in_submitter: str):
    """
    This is a script that runs inside of Blender, it sets up the scene file and exports a  job bundle. This test covers one camera being selected and one render layer being selected.
    """
    bpy.ops.wm.open_mainfile(filepath=str(Path(__file__).parent / "scene" / "test.blend"))

    bpy.context.scene.frame_start = 1
    bpy.context.scene.frame_end = 2
    bpy.context.scene.render.filepath = str(Path(output_dir_in_scene) / "image_####.png")
    bpy.context.scene.render.engine = "CYCLES"
    bpy.context.scene.render.resolution_x = 640
    bpy.context.scene.render.resolution_y = 480

    QtWidgets.QApplication(sys.argv)
    widget = create_deadline_dialog()

    settings = widget.job_settings_type()
    widget.shared_job_settings.update_settings(settings)
    widget.job_settings.update_settings(settings)

    settings.view_layer_selection = "ViewLayer_001"
    settings.camera_selection = "Camera.001"
    settings.description = "host_test"
    settings.include_adaptor_wheels = False
    settings.override_frame_range = True
    settings.frame_list = "3-5"
    settings.output_path = str(Path(output_dir_in_submitter))

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

    host_requirements_widget = widget.host_requirements

    host_requirements_widget.mode_selection_box.use_custom_button.setChecked(True)

    host_requirements_widget.os_requirements_box.os_row.combo_box.setCurrentIndex(
        1
    )  # The first item is "linux"
    host_requirements_widget.os_requirements_box.cpu_row.combo_box.setCurrentIndex(
        1
    )  # The first item is "x86_64"

    hardware_requirements_box = host_requirements_widget.hardware_requirements_box

    hardware_requirements_box.cpu_row.min_spin_box.setValue(1)
    hardware_requirements_box.cpu_row.max_spin_box.setValue(5)

    hardware_requirements_box.memory_row.min_spin_box.setValue(1)
    hardware_requirements_box.memory_row.max_spin_box.setValue(5)

    hardware_requirements_box.gpu_row.min_spin_box.setValue(1)
    hardware_requirements_box.gpu_row.max_spin_box.setValue(5)

    hardware_requirements_box.gpu_memory_row.min_spin_box.setValue(1)
    hardware_requirements_box.gpu_memory_row.max_spin_box.setValue(5)

    hardware_requirements_box.scratch_space_row.min_spin_box.setValue(1)
    hardware_requirements_box.scratch_space_row.max_spin_box.setValue(5)

    custom_requirements_box = widget.host_requirements.custom_requirements_box

    # First we need to make the customer requirements available, so click the buttons.
    # This will result in the custom amount being the first in the list widget and
    # the custom attribute being the second in the list widget
    custom_requirements_box.add_amount_button.click()
    custom_requirements_box.add_attr_button.click()

    custom_requirements_list_widget = custom_requirements_box.list_widget

    custom_amount_widget = custom_requirements_list_widget.itemWidget(
        custom_requirements_list_widget.item(0)
    )
    custom_attr_widget = custom_requirements_list_widget.itemWidget(
        custom_requirements_list_widget.item(1)
    )

    custom_amount_widget.name_line_edit.setText("custom_amount")
    custom_amount_widget.min_spin_box.setValue(1)
    custom_amount_widget.max_spin_box.setValue(5)

    custom_attr_widget.name_line_edit.setText("custom_attr")
    custom_attr_value = custom_attr_widget.value_list_widget.itemWidget(
        custom_attr_widget.value_list_widget.item(0)
    )
    custom_attr_value.line_edit.setText("custom_attr_value")

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
    parser.add_argument("output_dir_in_scene")
    parser.add_argument("output_dir_in_submitter")
    args = parser.parse_args(args=sys.argv[sys.argv.index("--") :])
    main(args.job_history_dir, args.output_dir_in_scene, args.output_dir_in_submitter)
