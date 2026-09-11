# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

from __future__ import annotations
from unittest.mock import Mock, PropertyMock, patch
import pytest

from deadline.blender_adaptor.BlenderAdaptor import BlenderAdaptor


@pytest.fixture()
def init_data() -> dict:
    """
    Pytest Fixture to return an init_data dictionary that passes validation

    Returns:
        dict: An init_data dictionary
    """
    return {
        "scene_file": "C:\\This\\Is\\A\\Path\\test.blend",
        "render_engine": "cycles",
        "gpu_device": "NONE",
    }


@pytest.fixture()
def run_data() -> dict:
    """
    Pytest Fixture to return a run_data dictionary that passes validation

    Returns:
        dict: A run_data dictionary
    """
    return {"frame": 1}


class TestBlenderAdaptor:
    handle_progess_params = [
        pytest.param(
            0,
            "Fra:2 Mem:48.09M (Peak 48.09M) | Time:00:03.01 | Remaining:00:13.01 | Mem:38.37M, Peak:38.37M | Scene, ViewLayer | Sample 768/4096",
            18,
            id="TestCyclesProgressReporting",
        ),
        pytest.param(
            1,
            "Fra:1 Mem:43.82M (Peak 44.36M) | Time:00:00.28 | Rendering 17 / 64 samples",
            26,
            id="TestEeveeProgressReporting",
        ),
    ]

    @pytest.mark.parametrize("regex_index, stdout, expected_progress", handle_progess_params)
    @patch("deadline.blender_adaptor.BlenderAdaptor.BlenderAdaptor.update_status")
    def test_handle_progress(
        self,
        mock_update_status: Mock,
        regex_index: int,
        stdout: str,
        expected_progress: float,
        init_data: dict,
    ) -> None:
        """Tests that the _handle_progress method updates the progress correctly"""
        # GIVEN
        adaptor = BlenderAdaptor(init_data)
        regex_callbacks = adaptor._get_regex_callbacks()
        progress_regex = regex_callbacks[1].regex_list[regex_index]

        # WHEN
        match = progress_regex.search(stdout)
        assert match is not None
        adaptor._handle_progress(match)

        # THEN
        mock_update_status.assert_called_once_with(progress=expected_progress)

    @staticmethod
    def _blender_client_that_exits(returncode: int) -> Mock:
        """
        Returns a mock Blender client that starts out running, so that on_run starts the render, and
        that reports the given return code once a test stops it.
        """
        client = Mock(returncode=returncode)
        client.is_running = True
        return client

    @patch("time.sleep")
    @patch(
        "deadline.blender_adaptor.BlenderAdaptor.adaptor.BlenderAdaptor._get_deadline_telemetry_client"
    )
    def test_on_run_blender_crashed(
        self,
        mock_telemetry_client: Mock,
        mock_sleep: Mock,
        init_data: dict,
        run_data: dict,
    ) -> None:
        """Tests that a Blender crash during the render is raised and recorded as an error"""
        # GIVEN
        adaptor = BlenderAdaptor(init_data)
        adaptor._action_queue = Mock()
        client = self._blender_client_that_exits(-11)
        adaptor._blender_client = client
        mock_sleep.side_effect = lambda *args: setattr(client, "is_running", False)

        # WHEN
        with pytest.raises(RuntimeError) as exc_info:
            adaptor.on_run(run_data)

        # THEN
        assert str(exc_info.value) == (
            "Blender exited early and did not render successfully, please check render logs. "
            "Exit code -11"
        )
        mock_telemetry_client.return_value.record_error.assert_called_once_with(
            {"exit_code": -11, "exception_scope": "caught", "error_operation": "on_run"},
            str(RuntimeError),
        )

    @patch("time.sleep")
    @patch(
        "deadline.blender_adaptor.BlenderAdaptor.adaptor.BlenderAdaptor._get_deadline_telemetry_client"
    )
    def test_on_run_blender_exits_after_render_completed(
        self,
        mock_telemetry_client: Mock,
        mock_sleep: Mock,
        init_data: dict,
        run_data: dict,
    ) -> None:
        """
        Tests that a render which reported completion is not failed when Blender exits before on_run
        checks whether it is still running.
        """
        # GIVEN
        adaptor = BlenderAdaptor(init_data)
        adaptor._action_queue = Mock()
        client = self._blender_client_that_exits(0)
        adaptor._blender_client = client

        def complete_render_then_exit(*args) -> None:
            adaptor._blender_is_rendering = False
            client.is_running = False

        mock_sleep.side_effect = complete_render_then_exit

        # WHEN
        adaptor.on_run(run_data)

        # THEN
        mock_telemetry_client.return_value.record_error.assert_not_called()

    @patch("time.sleep")
    @patch(
        "deadline.blender_adaptor.BlenderAdaptor.adaptor.BlenderAdaptor._get_deadline_telemetry_client"
    )
    def test_on_run_blender_exits_nonzero_after_render_completed(
        self,
        mock_telemetry_client: Mock,
        mock_sleep: Mock,
        init_data: dict,
        run_data: dict,
    ) -> None:
        """Tests that a nonzero exit after render completion is raised and recorded as an error"""
        # GIVEN
        adaptor = BlenderAdaptor(init_data)
        adaptor._action_queue = Mock()
        client = self._blender_client_that_exits(1)
        adaptor._blender_client = client

        def complete_render_then_exit(*args) -> None:
            adaptor._blender_is_rendering = False
            client.is_running = False

        mock_sleep.side_effect = complete_render_then_exit

        # WHEN
        with pytest.raises(RuntimeError) as exc_info:
            adaptor.on_run(run_data)

        # THEN
        assert str(exc_info.value) == (
            "Blender reported render completion but exited with a nonzero code. Exit code 1"
        )
        mock_telemetry_client.return_value.record_error.assert_called_once_with(
            {"exit_code": 1, "exception_scope": "caught", "error_operation": "on_run"},
            str(RuntimeError),
        )

    @patch.dict("os.environ", {}, clear=False)
    @patch("deadline.blender_adaptor.BlenderAdaptor.adaptor.LoggingSubprocess")
    @patch(
        "deadline.blender_adaptor.BlenderAdaptor.adaptor.BlenderAdaptor.blender_client_path",
        new_callable=PropertyMock,
    )
    def test_start_blender_client_sets_python_exit_code(
        self,
        mock_blender_client_path: Mock,
        mock_logging_subprocess: Mock,
        init_data: dict,
    ) -> None:
        """
        Tests that Blender is asked to exit with a nonzero code when the client script raises,
        instead of masking the failure as a clean exit.
        """
        # GIVEN
        mock_blender_client_path.return_value = "/path/to/blender_client.py"
        adaptor = BlenderAdaptor(init_data)

        # WHEN
        adaptor._start_blender_client()

        # THEN
        args = mock_logging_subprocess.call_args.kwargs["args"]
        assert args[args.index("--python-exit-code") + 1] == "1"
        # Blender applies command line arguments in order, so this must come before the script.
        assert args.index("--python-exit-code") < args.index("--python")
