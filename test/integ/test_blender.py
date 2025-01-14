# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

import yaml
import os
import pytest

from pathlib import Path
from typing import Any

from .helpers.test_runners import run_adaptor_test, run_blender_submitter_test, is_valid_template
from .helpers.image_comparison import assert_all_images_close


@pytest.mark.submitter
def test_minimal_scene_submitter(
    blender_location: Path, script_location: Path, tmp_path: Path
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
            {"name": "OutputFileName", "value": "image_####.png"},
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

    with open(job_history_dir / "parameter_values.yaml") as actual:
        actual_parameter_values = yaml.safe_load(actual)
        # Compare the lengths before we turn it into a set so that we can cover the case of duplicate assets.
        assert len(actual_parameter_values["parameterValues"]) == len(
            expected_parameter_values["parameterValues"]
        )

        # The order of the list of parameter values doesn't matter,
        for parameter_value in expected_parameter_values["parameterValues"]:
            assert parameter_value in actual_parameter_values["parameterValues"]

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


@pytest.mark.xfail(
    run=True,
    reason="There's a bug where multiple view layers are rendered when it should only be one.",
)
@pytest.mark.adaptor
def test_minimal_scene_adaptor(script_location: Path, tmp_path: Path) -> None:
    test_file_location = script_location / "minimal_test"
    scene_location = test_file_location / "scene" / "test.blend"
    output_path = tmp_path / "output"

    job_params = {
        "BlenderFile": str(scene_location),
        "OutputFileName": "image_####.png",
        "OutputDir": str(output_path),
        "RenderScene": "Scene",
        "RenderEngine": "cycles",
        "Frames": "1-2",
        "ResolutionX": 640,
        "ResolutionY": 480,
    }

    run_adaptor_test(test_file_location / "expected_job_bundle" / "template.yaml", job_params)
    assert_all_images_close(
        expected_image_directory=test_file_location / "expected_images",
        actual_image_directory=output_path,
    )
