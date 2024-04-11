# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

import os
import tempfile
from unittest import mock
import shutil
import filecmp
import difflib
import bpy

from datetime import datetime, timezone

from qtpy.QtWidgets import (  # pylint: disable=import-error; type: ignore
    QApplication,
    QFileDialog,
    QMessageBox,
)

from deadline.client.ui import gui_error_handler
from deadline.client.ui.dialogs import submit_job_to_deadline_dialog
from deadline.client.exceptions import DeadlineOperationError
from deadline_cloud_blender_submitter.open_deadline_cloud_dialog import create_deadline_dialog
from deadline_cloud_blender_submitter import blender_utils

# The following functions expose a DCC interface to the job bundle output test logic.


def _open_dcc_scene_file(filename: str) -> None:
    """Opens the scene file in Blender."""
    bpy.ops.wm.open_mainfile(filepath=filename, load_ui=False)


def _close_dcc_scene_file() -> None:
    """Returns to the 'home' file in Blender."""
    bpy.ops.wm.read_homefile(load_ui=False)


def _copy_dcc_scene_file(source_filename: str, dest_filename: str) -> None:
    # Copy all support files under the source filename's dirname
    shutil.copytree(
        os.path.dirname(source_filename), os.path.dirname(dest_filename), dirs_exist_ok=True
    )


def _show_deadline_cloud_submitter():
    """Shows the Deadline Cloud Submitter for Blender."""
    # Patch the return value so that assets are found when in temp dirs
    with mock.patch.object(blender_utils, "_get_blender_temp_dirs") as mock_get_temp_dirs:
        mock_get_temp_dirs.return_value = []
        return create_deadline_dialog()


# The following functions implement the test logic.
def _timestamp_string() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat()


def run_blender_render_submitter_job_bundle_output_test():
    """
    Runs a set of job bundle output tests from a directory.
    """
    count_succeeded = 0
    count_failed = 0

    with gui_error_handler("Error running job bundle output test"):
        tests_dir = QFileDialog.getExistingDirectory(
            caption="Select a Directory Containing Blender Job Bundle Tests"
        )

        if not tests_dir:
            return

        tests_dir = os.path.normpath(tests_dir)

        test_job_bundle_results_file = os.path.join(
            tests_dir, "blender-test-job-bundle-results.txt"
        )

        with open(test_job_bundle_results_file, "w", encoding="utf8") as report_fh:
            for test_name in os.listdir(tests_dir):
                job_bundle_test = os.path.join(tests_dir, test_name)
                if not os.path.isdir(job_bundle_test):
                    continue
                report_fh.write(f"\nTimestamp: {_timestamp_string()}\n")
                report_fh.write(f"Running job bundle output test: {job_bundle_test}\n")

                dcc_scene_file = os.path.join(job_bundle_test, "scene", f"{test_name}.blend")

                if not (os.path.exists(dcc_scene_file) and os.path.isfile(dcc_scene_file)):
                    raise DeadlineOperationError(
                        f"Directory {job_bundle_test} does not contain the expected .blend scene: {dcc_scene_file}."
                    )

                succeeded = _run_job_bundle_output_test(job_bundle_test, dcc_scene_file, report_fh)

                if succeeded:
                    count_succeeded += 1
                else:
                    count_failed += 1

            report_fh.write("\n")
            if count_failed:
                report_fh.write(f"Failed {count_failed} tests, succeeded {count_succeeded}.\n")
                QMessageBox.warning(
                    None,
                    "Some Job Bundle Tests Failed",
                    f"Failed {count_failed} tests, succeeded {count_succeeded}.\nSee the file {test_job_bundle_results_file} for a full report.",
                )
            else:
                report_fh.write(f"All tests passed, ran {count_succeeded} total.\n")
                QMessageBox.information(
                    None,
                    "All Job Bundle Tests Passed",
                    f"Success! Ran {count_succeeded} tests in total.",
                )
            report_fh.write(f"Timestamp: {_timestamp_string()}\n")


def _run_job_bundle_output_test(test_dir: str, dcc_scene_file: str, report_fh) -> bool:

    with tempfile.TemporaryDirectory(prefix="job_bundle_output_test") as tempdir:
        temp_job_bundle_dir = os.path.join(tempdir, "job_bundle")
        os.makedirs(temp_job_bundle_dir, exist_ok=True)

        temp_dcc_scene_file = os.path.join(tempdir, os.path.basename(dcc_scene_file))

        # Copy the DCC scene file to the temp directory, transforming any
        # internal paths as necessary.
        _copy_dcc_scene_file(dcc_scene_file, temp_dcc_scene_file)

        # Open the DCC scene file
        _open_dcc_scene_file(temp_dcc_scene_file)
        QApplication.processEvents()

        # Open the AWS Deadline Cloud submitter
        submitter = _show_deadline_cloud_submitter()
        QApplication.processEvents()

        # Save the Job Bundle
        # Use patching to set the job bundle directory and skip the success messagebox
        with (
            mock.patch.object(
                submit_job_to_deadline_dialog,
                "create_job_history_bundle_dir",
                return_value=temp_job_bundle_dir,
            ),
            mock.patch.object(submit_job_to_deadline_dialog, "QMessageBox"),
            mock.patch.object(
                os,
                "startfile",
                create=True,  # only exists on win. Just create to avoid AttributeError
            ),
        ):
            submitter.on_export_bundle()
        QApplication.processEvents()

        # Close the DCC scene file
        _close_dcc_scene_file()

        # Process every file in the job bundle to replace the temp dir with a standardized path
        for filename in os.listdir(temp_job_bundle_dir):
            full_filename = os.path.join(temp_job_bundle_dir, filename)
            with open(full_filename, encoding="utf8") as f:
                contents = f.read()
            contents = contents.replace(tempdir + "\\", "/normalized/job/bundle/dir/")
            contents = contents.replace(
                tempdir.replace("\\", "/") + "/", "/normalized/job/bundle/dir/"
            )
            contents = contents.replace(tempdir, "/normalized/job/bundle/dir")
            contents = contents.replace(tempdir.replace("\\", "/"), "/normalized/job/bundle/dir")
            with open(full_filename, "w", encoding="utf8") as f:
                f.write(contents)

        # If there's an expected job bundle to compare with, do the comparison,
        # otherwise copy the one we created to be that expected job bundle.
        expected_job_bundle_dir = os.path.join(test_dir, "expected_job_bundle")
        if os.path.exists(expected_job_bundle_dir):
            test_job_bundle_dir = os.path.join(test_dir, "test_job_bundle")
            if os.path.exists(test_job_bundle_dir):
                shutil.rmtree(test_job_bundle_dir)
            shutil.copytree(temp_job_bundle_dir, test_job_bundle_dir)

            dcmp = filecmp.dircmp(expected_job_bundle_dir, test_job_bundle_dir)
            report_fh.write("\n")
            report_fh.write(f"{os.path.basename(test_dir)}\n")
            if dcmp.left_only or dcmp.right_only or dcmp.diff_files:
                report_fh.write("Test failed, found differences\n")
                if dcmp.left_only:
                    report_fh.write(f"Missing files: {dcmp.left_only}\n")
                if dcmp.right_only:
                    report_fh.write(f"Extra files: {dcmp.right_only}\n")
                for file in dcmp.diff_files:
                    with (
                        open(os.path.join(expected_job_bundle_dir, file), encoding="utf8") as fleft,
                        open(os.path.join(test_job_bundle_dir, file), encoding="utf8") as fright,
                    ):
                        diff = "".join(
                            difflib.unified_diff(
                                list(fleft), list(fright), "expected/" + file, "test/" + file
                            )
                        )
                        report_fh.write(diff)

                # Failed the test
                return False
            else:
                report_fh.write("Test succeeded\n")
                # Succeeded the test
                return True
        else:
            shutil.copytree(temp_job_bundle_dir, expected_job_bundle_dir)

            report_fh.write("Test cannot compare. Saved new reference to expected_job_bundle.\n")
            # We generated the original expected job bundle, so did not succeed a test.
            return False
