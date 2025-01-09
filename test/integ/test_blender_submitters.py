# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

import yaml
import os
import pytest

from pathlib import Path
from typing import Any
from pytest import FixtureRequest, Mark

from .helpers.test_runners import run_blender_submitter_test, is_valid_template


@pytest.mark.submitter
class TestSubmitters:
    """
    Tests that ensure submitters produce the correct job bundle given a scene file.
    """

    @pytest.fixture(autouse=True)
    def _cleanup_sticky_settings(self, request: FixtureRequest, script_location: Path):
        """
        We need to clean the sticky settings before the test runs so that we can ensure
        a clean environment.
        """
        scene_location_marker: Mark = request.keywords["scene_files"]

        scene_file: Path
        for scene_file in scene_location_marker.args:
            sticky_settings_location = scene_file.with_name(
                f"{scene_file.stem}.deadline_render_settings.json"
            )
            Path(script_location / sticky_settings_location).unlink(missing_ok=True)

    def assert_parameter_values(
        self, job_history_dir: Path, expected_parameter_values: dict[str, list]
    ):
        """
        Helper function that asserts that parameter values in the job bundle are what's expected.
        """
        with open(job_history_dir / "parameter_values.yaml") as actual:
            actual_parameter_values = yaml.safe_load(actual)
            # Compare the lengths before we turn it into a set so that we can cover the case of duplicate parameters.
            assert len(actual_parameter_values["parameterValues"]) == len(
                expected_parameter_values["parameterValues"]
            )

            # The order of the list of parameter values doesn't matter,
            for parameter_value in expected_parameter_values["parameterValues"]:
                assert parameter_value in actual_parameter_values["parameterValues"]

    def assert_asset_references(
        self, job_history_dir: Path, expected_asset_references: dict[str, dict[str, Any]]
    ):
        """
        Helper function that asserts that asset reference values in the job bundle are what's expected.
        """
        with open(job_history_dir / "asset_references.yaml") as actual:
            actual_asset_reference = yaml.safe_load(actual)
            # We don't care what order the filenames list is in, so turn it into a set for easier comparison.
            # Compare the lengths before we turn it into a set so that we can cover the case of duplicate assets.
            assert len(actual_asset_reference["assetReferences"]["inputs"]["filenames"]) == len(
                expected_asset_references["assetReferences"]["inputs"]["filenames"]
            )
            actual_asset_reference["assetReferences"]["inputs"]["filenames"] = set(
                actual_asset_reference["assetReferences"]["inputs"]["filenames"]
            )
            assert actual_asset_reference == expected_asset_references

    @pytest.mark.scene_files(Path("minimal_test") / "scene" / "test.blend")
    def test_minimal_scene_submitter(
        self, blender_location: Path, script_location: Path, tmp_path: Path
    ) -> None:
        job_history_dir = tmp_path / "jobhistory"
        output_path = tmp_path / "output"
        scene_location = script_location / "minimal_test" / "scene" / "test.blend"

        os.makedirs(job_history_dir, exist_ok=True)
        os.makedirs(output_path, exist_ok=True)

        output = run_blender_submitter_test(
            blender_location,
            script_location / "minimal_test" / "_test_blend.py",
            str(job_history_dir),
            str(output_path),
        )

        assert output.returncode == 0

        # Check that we have a valid template
        assert is_valid_template(job_history_dir / "template.yaml")

        # Check that the template is as expected.
        with (
            open(
                script_location / "minimal_test" / "expected_job_bundle" / "template.yaml"
            ) as expected,
            open(job_history_dir / "template.yaml") as actual,
        ):
            assert yaml.safe_load(expected) == yaml.safe_load(actual)

        # Check that the parameter values are as expected.
        expected_parameter_values = {
            "parameterValues": [
                {"name": "BlenderFile", "value": str(scene_location)},
                {"name": "OutputFileName", "value": "image_####"},
                {"name": "OutputDir", "value": str(output_path)},
                {"name": "RenderScene", "value": "Scene"},
                {"name": "RenderEngine", "value": "cycles"},
                {"name": "GPUDevice", "value": "NONE"},
                {"name": "Frames", "value": "1-2"},
                {"name": "ResolutionX", "value": 640},
                {"name": "ResolutionY", "value": 480},
                {"name": "deadline:targetTaskRunStatus", "value": "READY"},
                {"name": "deadline:maxFailedTasksCount", "value": 20},
                {"name": "deadline:maxRetriesPerTask", "value": 5},
                {"name": "deadline:priority", "value": 50},
            ]
        }

        self.assert_parameter_values(job_history_dir, expected_parameter_values)

        # Check that the asset references are as expected.
        expected_asset_references: dict[str, dict[str, Any]] = {
            "assetReferences": {
                "inputs": {
                    "directories": [],
                    "filenames": {str(scene_location)},
                },
                "outputs": {
                    "directories": [],
                },
                "referencedPaths": [],
            }
        }

        self.assert_asset_references(job_history_dir, expected_asset_references)

    @pytest.mark.scene_files(Path("minimal_test_host_requirements") / "scene" / "test.blend")
    def test_minimal_scene_with_host_requirements_submitter(
        self, blender_location: Path, script_location: Path, tmp_path: Path
    ) -> None:
        job_history_dir = tmp_path / "jobhistory"
        output_path_in_scene = tmp_path / "output"
        output_dir_in_submitter = tmp_path / "output_submitter"
        test_artifact_dir = script_location / "minimal_test_host_requirements"
        expected_job_bundle_location = test_artifact_dir / "expected_job_bundle"
        scene_location = test_artifact_dir / "scene" / "test.blend"

        os.makedirs(job_history_dir, exist_ok=True)
        os.makedirs(output_path_in_scene, exist_ok=True)
        os.makedirs(output_dir_in_submitter, exist_ok=True)

        output = run_blender_submitter_test(
            blender_location,
            test_artifact_dir / "_test_blend.py",
            str(job_history_dir),
            str(output_path_in_scene),
            str(output_dir_in_submitter),
        )

        assert output.returncode == 0

        assert is_valid_template(job_history_dir / "template.yaml")

        # Check that the template is as expected.
        with (
            open(expected_job_bundle_location / "template.yaml") as expected,
            open(job_history_dir / "template.yaml") as actual,
        ):
            assert yaml.safe_load(expected) == yaml.safe_load(actual)

        # Check that the parameter values are as expected.
        expected_parameter_values = {
            "parameterValues": [
                {"name": "BlenderFile", "value": str(scene_location)},
                {"name": "OutputFileName", "value": "image_####.png"},
                {"name": "OutputDir", "value": str(output_dir_in_submitter)},
                {"name": "RenderScene", "value": "Scene"},
                {"name": "RenderEngine", "value": "cycles"},
                {"name": "GPUDevice", "value": "NONE"},
                {"name": "Frames", "value": "3-5"},
                {"name": "ResolutionX", "value": 640},
                {"name": "ResolutionY", "value": 480},
                {"name": "deadline:targetTaskRunStatus", "value": "READY"},
                {"name": "deadline:maxFailedTasksCount", "value": 20},
                {"name": "deadline:maxRetriesPerTask", "value": 5},
                {"name": "deadline:priority", "value": 50},
            ]
        }

        self.assert_parameter_values(job_history_dir, expected_parameter_values)

        # Check that the asset references are as expected.
        expected_asset_references: dict[str, dict[str, Any]] = {
            "assetReferences": {
                "inputs": {
                    "directories": [],
                    "filenames": {str(scene_location)},
                },
                "outputs": {
                    "directories": [],
                },
                "referencedPaths": [],
            }
        }

        self.assert_asset_references(job_history_dir, expected_asset_references)
