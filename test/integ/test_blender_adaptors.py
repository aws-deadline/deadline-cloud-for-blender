# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

from pathlib import Path

import pytest

from .helpers.image_comparison import assert_all_images_close
from .helpers.test_runners import run_adaptor_test


@pytest.mark.adaptor
class TestAdaptors:
    """
    Tests that ensure correct output from the Blender adaptor given a job bundle and scene file.
    """

    def test_minimal_scene_adaptor(
        self,
        script_location: Path,
        tmp_path: Path,
        blender_location: Path,
        blender_version: str,
    ) -> None:
        test_file_location = script_location / "minimal_test"
        scene_location = test_file_location / "scene" / "test.blend"
        output_path = tmp_path / "output"

        job_params = {
            "BlenderFile": str(scene_location),
            "OutputFileName": "image_####",
            "OutputDir": str(output_path),
            "RenderScene": "Scene",
            "RenderEngine": "cycles",
            "Frames": "1-2",
            "ResolutionX": 640,
            "ResolutionY": 480,
        }

        run_adaptor_test(
            test_file_location / "expected_job_bundle" / "template.yaml",
            job_params,
            blender_location,
        )
        assert_all_images_close(
            expected_image_directory=test_file_location / "expected_images" / blender_version,
            actual_image_directory=output_path,
        )

    def test_minimal_scene_with_host_requirements_adaptor(
        self,
        script_location: Path,
        tmp_path: Path,
        blender_location: Path,
        blender_version: str,
    ) -> None:
        test_file_location = script_location / "minimal_test_host_requirements"
        scene_location = test_file_location / "scene" / "test.blend"
        output_path = tmp_path / "output_submitter"

        job_params = {
            "BlenderFile": str(scene_location),
            "OutputFileName": "image_####.png",
            "OutputDir": str(output_path),
            "RenderScene": "Scene",
            "RenderEngine": "cycles",
            "GPUDevice": "NONE",
            "Frames": "3-5",
            "ResolutionX": 640,
            "ResolutionY": 480,
        }

        run_adaptor_test(
            test_file_location / "expected_job_bundle" / "template.yaml",
            job_params,
            blender_location,
        )
        assert_all_images_close(
            expected_image_directory=test_file_location / "expected_images" / blender_version,
            actual_image_directory=output_path,
        )
