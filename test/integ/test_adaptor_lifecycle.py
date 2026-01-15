# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

import os
import psutil
import time
from pathlib import Path

import pytest

from deadline.blender_adaptor.BlenderAdaptor import BlenderAdaptor


@pytest.mark.adaptor
class TestAdaptorLifecycle:
    """
    Tests that validate the Blender adaptor can start and close the Blender application.
    """

    def test_adaptor_start_and_close_blender(
        self, blender_location: Path, script_location: Path
    ) -> None:
        """Test that the adaptor can start and properly close Blender."""
        # Set BLENDER_EXECUTABLE environment variable
        os.environ["BLENDER_EXECUTABLE"] = str(blender_location)

        # Use the test.blend file from minimal test directory
        scene_file = script_location / "minimal_test" / "scene" / "test.blend"

        # Create minimal init data with all required fields
        init_data = {
            "scene_file": str(scene_file),
            "render_engine": "cycles",
            "gpu_device": "NONE",
        }

        # Initialize adaptor
        adaptor = BlenderAdaptor(init_data)

        try:
            # Start the adaptor (should start Blender)
            adaptor.on_start()

            # Verify Blender is running
            assert adaptor._blender_is_running, "Blender should be running after on_start()"

            # Get process ID and verify process is running
            assert adaptor._blender_client
            blender_pid = adaptor._blender_client.pid
            assert psutil.pid_exists(
                blender_pid
            ), f"Blender process {blender_pid} should be running"

            # Wait briefly to ensure stable state
            time.sleep(1)

            # Verify the process is still alive
            assert adaptor._blender_client is not None
            assert adaptor._blender_client.is_running
            assert psutil.pid_exists(
                blender_pid
            ), f"Blender process {blender_pid} should still be running"

        finally:
            # Clean up (should close Blender)
            adaptor.on_cleanup()

            # Verify Blender is no longer running
            assert not adaptor._blender_is_running, "Blender should not be running after cleanup"

    def test_adaptor_cancel_closes_blender(
        self, blender_location: Path, script_location: Path
    ) -> None:
        """Test that the adaptor closes Blender when a task is canceled."""
        # Set BLENDER_EXECUTABLE environment variable
        os.environ["BLENDER_EXECUTABLE"] = str(blender_location)

        # Use the test.blend file from minimal test directory
        scene_file = script_location / "minimal_test" / "scene" / "test.blend"

        # Create init data with all required fields
        init_data = {
            "scene_file": str(scene_file),
            "render_engine": "cycles",
            "gpu_device": "NONE",
        }

        # Initialize adaptor
        adaptor = BlenderAdaptor(init_data)

        try:
            # Start the adaptor
            adaptor.on_start()

            # Verify Blender is running
            assert adaptor._blender_is_running, "Blender should be running after on_start()"

            # Get process ID and verify process is running
            assert adaptor._blender_client
            blender_pid = adaptor._blender_client.pid
            assert psutil.pid_exists(
                blender_pid
            ), f"Blender process {blender_pid} should be running"

            # Cancel the task
            adaptor.on_cancel()

            # Wait briefly for cancellation to take effect
            time.sleep(1)

            # Verify Blender is no longer running after cancel
            assert not adaptor._blender_is_running, "Blender should not be running after cancel"
            assert not psutil.pid_exists(
                blender_pid
            ), f"Blender process {blender_pid} should be terminated"

        finally:
            # Ensure cleanup in case cancel didn't work
            if adaptor._blender_is_running:
                adaptor.on_cleanup()
