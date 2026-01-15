# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

import json
import os
import subprocess
import tempfile
import time
from pathlib import Path

import pytest


@pytest.mark.adaptor
class TestDaemonMode:
    """
    Tests that validate the Blender adaptor daemon mode functionality.
    """

    def test_daemon_start_and_stop(self, blender_location: Path, script_location: Path) -> None:
        """Test that the blender-openjd daemon can start and stop successfully."""
        # Set BLENDER_EXECUTABLE environment variable
        os.environ["BLENDER_EXECUTABLE"] = str(blender_location)

        # Use the test.blend file from minimal test directory
        scene_file = script_location / "minimal_test" / "scene" / "test.blend"

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            connection_file = temp_path / "connection.json"
            init_data_file = temp_path / "init-data.yaml"

            # Create init data file
            init_data_content = f"""scene_file: {scene_file}
render_engine: cycles
gpu_device: NONE
render_scene: Scene
view_layer: ViewLayer
output_dir: {temp_path}
output_file_name: output_####
output_format: PNG
"""
            init_data_file.write_text(init_data_content)

            try:
                # Start daemon
                start_cmd = [
                    "blender-openjd",
                    "daemon",
                    "start",
                    "--connection-file",
                    str(connection_file),
                    "--init-data",
                    f"file://{init_data_file}",
                ]

                start_process = subprocess.run(
                    start_cmd,
                    capture_output=True,
                    text=True,
                    timeout=60,
                )

                # Verify daemon started successfully
                assert start_process.returncode == 0, f"Daemon start failed: {start_process.stderr}"
                assert connection_file.exists(), "Connection file should be created"

                # Verify connection file contains valid JSON
                connection_data = json.loads(connection_file.read_text())
                assert "socket" in connection_data, "Connection file should contain socket"

                # Wait briefly to ensure daemon is fully started
                time.sleep(2)

            finally:
                # Stop daemon
                if connection_file.exists():
                    stop_cmd = [
                        "blender-openjd",
                        "daemon",
                        "stop",
                        "--connection-file",
                        str(connection_file),
                    ]

                    stop_process = subprocess.run(
                        stop_cmd,
                        capture_output=True,
                        text=True,
                        timeout=30,
                    )

                    # Verify daemon stopped successfully
                    assert (
                        stop_process.returncode == 0
                    ), f"Daemon stop failed: {stop_process.stderr}"

    def test_daemon_run_command(self, blender_location: Path, script_location: Path) -> None:
        """Test that the daemon can execute a run command successfully."""
        os.environ["BLENDER_EXECUTABLE"] = str(blender_location)
        scene_file = script_location / "minimal_test" / "scene" / "test.blend"

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            connection_file = temp_path / "connection.json"
            init_data_file = temp_path / "init-data.yaml"
            run_data_file = temp_path / "run-data.yaml"

            # Create init data file
            init_data_content = f"""scene_file: {scene_file}
render_engine: cycles
gpu_device: NONE
render_scene: Scene
view_layer: ViewLayer
output_dir: {temp_path}
output_file_name: output_####
output_format: PNG
"""
            init_data_file.write_text(init_data_content)

            # Create run data file
            run_data_content = """frame: 1
camera: Camera
"""
            run_data_file.write_text(run_data_content)

            try:
                # Start daemon
                start_process = subprocess.run(
                    [
                        "blender-openjd",
                        "daemon",
                        "start",
                        "--connection-file",
                        str(connection_file),
                        "--init-data",
                        f"file://{init_data_file}",
                    ],
                    capture_output=True,
                    text=True,
                    timeout=60,
                )

                assert start_process.returncode == 0, f"Daemon start failed: {start_process.stderr}"
                time.sleep(2)

                # Execute run command
                run_process = subprocess.run(
                    [
                        "blender-openjd",
                        "daemon",
                        "run",
                        "--connection-file",
                        str(connection_file),
                        "--run-data",
                        f"file://{run_data_file}",
                    ],
                    capture_output=True,
                    text=True,
                    timeout=120,
                )

                # Verify run command succeeded
                assert run_process.returncode == 0, f"Daemon run failed: {run_process.stderr}"

            finally:
                if connection_file.exists():
                    subprocess.run(
                        [
                            "blender-openjd",
                            "daemon",
                            "stop",
                            "--connection-file",
                            str(connection_file),
                        ],
                        capture_output=True,
                        timeout=30,
                    )
