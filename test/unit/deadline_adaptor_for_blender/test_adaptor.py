# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

from __future__ import annotations
import logging
from pathlib import Path
from unittest.mock import Mock, PropertyMock, patch
import pytest
from openjd.adaptor_runtime.app_handlers import RegexHandler

from deadline.blender_adaptor.BlenderAdaptor import BlenderAdaptor

_OBSERVED_OUTPUT = Path(__file__).parent / "data" / "observed-blender-5.0-gpu-oom-output.txt"


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


@pytest.fixture()
def observed_output() -> dict[str, list[str]]:
    """
    Pytest Fixture to return the observed Blender 5.0 output around a GPU out-of-memory error, by
    section: "Not out of memory", "Case A" and "Case B". Lines keep their whitespace.

    Returns:
        dict[str, list[str]]: The lines of each section, in order
    """
    sections: dict[str, list[str]] = {}
    section: str | None = None
    for line in _OBSERVED_OUTPUT.read_text(encoding="utf-8").splitlines():
        if line.startswith("## "):
            section = line[3:].split(":")[0]
            sections[section] = []
        elif section is not None and line:
            sections[section].append(line)
    return sections


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

    # Each out-of-memory message in its Blender 4.x and 5.x format, on the stream Blender uses.
    out_of_memory_params = [
        pytest.param("stderr", "System is out of GPU memory", id="GPUMemory-Blender4"),
        pytest.param(
            "stdout",
            "00:12.345  cycles           | ERROR System is out of GPU memory",
            id="GPUMemory-Blender5",
        ),
        pytest.param(
            "stderr",
            "System is out of GPU and shared host memory",
            id="GPUAndHostMemory-Blender4",
        ),
        pytest.param(
            "stdout",
            "00:12.345  cycles           | ERROR System is out of GPU and shared host memory",
            id="GPUAndHostMemory-Blender5",
        ),
        pytest.param(
            "stderr",
            "Out of memory in CUDA queue enqueue (integrator_init_from_camera)",
            id="CUDAError-Blender4",
        ),
        pytest.param(
            "stdout",
            "00:12.345  cycles           | ERROR Out of memory in CUDA queue enqueue (integrator_init_from_camera)",
            id="CUDAError-Blender5",
        ),
        pytest.param(
            "stderr",
            "Failed to retain CUDA context (Out of memory)",
            id="CUDAContextError-Blender4",
        ),
        pytest.param(
            "stdout",
            "00:12.345  cycles           | ERROR Failed to retain CUDA context (Out of memory)",
            id="CUDAContextError-Blender5",
        ),
        pytest.param("stderr", "Error: run out of memory!", id="FailedAllocation-Blender4"),
        pytest.param(
            "stdout",
            "00:12.345  cycles           | ERROR Out of memory",
            id="FailedAllocation-Blender5",
        ),
        # Blender 4.x prints OptiX messages only with --debug-cycles or --verbose.
        pytest.param(
            "stderr",
            "E0101 00:12:34.567890 12345 device_impl.cpp:74] cblCudaReconfigureLocalMemory failed with out of memory",
            id="OptiXLocalMemory-Blender4",
        ),
        pytest.param(
            "stdout",
            "00:12.345  cycles           | ERROR cblCudaReconfigureLocalMemory failed with out of memory",
            id="OptiXLocalMemory-Blender5",
        ),
        pytest.param("stdout", "Error: System is out of GPU memory", id="Report-Blender4"),
        pytest.param(
            "stdout",
            "00:12.345  reports          | ERROR System is out of GPU memory",
            id="Report-Blender5",
        ),
    ]

    # Other GPU errors, and an ordinary line whose scene and object names are the messages.
    not_out_of_memory_params = [
        pytest.param(
            "00:12.345  cycles           | ERROR Illegal address in cuMemFree_v2((CUdeviceptr)device_pointer) (intern/cycles/device/cuda/device_impl.cpp:533)",
            id="IllegalAddress",
        ),
        pytest.param(
            "00:12.345  cycles           | ERROR Failed to query command list event (CUDA error string: unspecified launch failure, CUDA error code: 719)",
            id="LaunchFailure",
        ),
        pytest.param(
            "00:12.345  cycles           | ERROR Refer to the Cycles GPU rendering documentation for possible solutions:",
            id="GPUDocumentationHint",
        ),
        pytest.param(
            "Fra:1 Mem:48.09M (Peak 48.09M) | Time:00:03.01 | Mem:38.37M, Peak:38.37M | System is out of GPU memory, ViewLayer | Synchronizing object | Out of memory",
            id="NamesContainingTheMessages",
        ),
    ]

    @pytest.mark.parametrize("stream, line", out_of_memory_params)
    @patch.dict("os.environ", {}, clear=False)
    @patch("time.sleep")
    @patch("deadline.blender_adaptor.BlenderAdaptor.adaptor.LoggingSubprocess")
    @patch(
        "deadline.blender_adaptor.BlenderAdaptor.adaptor.BlenderAdaptor.blender_client_path",
        new_callable=PropertyMock,
    )
    def test_on_run_fails_when_blender_runs_out_of_memory(
        self,
        mock_blender_client_path: Mock,
        mock_logging_subprocess: Mock,
        mock_sleep: Mock,
        stream: str,
        line: str,
        init_data: dict,
        run_data: dict,
    ) -> None:
        """
        Tests that the task fails at the first check after Blender prints an out-of-memory error,
        while Blender is still running, for a job that does not set strict_error_checking
        """
        # GIVEN
        assert "strict_error_checking" not in init_data
        mock_blender_client_path.return_value = "blender_client.py"
        adaptor = BlenderAdaptor(init_data)
        adaptor._action_queue = Mock()
        adaptor._start_blender_client()
        blender = mock_logging_subprocess.return_value
        blender.is_running = True
        handler = mock_logging_subprocess.call_args.kwargs[f"{stream}_handler"]
        # Blender prints the line once, so a second check raises StopIteration instead of hanging.
        lines = iter([line])
        mock_sleep.side_effect = lambda *args: handler.emit(
            logging.makeLogRecord({"msg": next(lines)})
        )

        # WHEN
        with pytest.raises(RuntimeError) as exc_info:
            adaptor.on_run(run_data)

        # THEN
        assert str(exc_info.value) == f"Blender ran out of memory: {line}"
        mock_sleep.assert_called_once()
        assert blender.is_running
        blender.terminate.assert_not_called()

    @pytest.mark.parametrize("line", not_out_of_memory_params)
    def test_other_output_does_not_fail_the_task(self, line: str, init_data: dict) -> None:
        """
        Tests that other GPU errors, and ordinary lines that contain the out-of-memory messages, do
        not fail the task
        """
        # GIVEN
        adaptor = BlenderAdaptor(init_data)
        handler = RegexHandler(adaptor._get_regex_callbacks())

        # WHEN
        handler.emit(logging.makeLogRecord({"msg": line}))

        # THEN
        assert adaptor._exc_info is None

    @pytest.mark.parametrize(
        "case",
        [pytest.param("Case A", id="CaseA-CUDA"), pytest.param("Case B", id="CaseB-OptiX")],
    )
    @patch.dict("os.environ", {}, clear=False)
    @patch("time.sleep")
    @patch("deadline.blender_adaptor.BlenderAdaptor.adaptor.LoggingSubprocess")
    @patch(
        "deadline.blender_adaptor.BlenderAdaptor.adaptor.BlenderAdaptor.blender_client_path",
        new_callable=PropertyMock,
    )
    def test_on_run_fails_on_observed_blender_5_out_of_memory(
        self,
        mock_blender_client_path: Mock,
        mock_logging_subprocess: Mock,
        mock_sleep: Mock,
        case: str,
        observed_output: dict[str, list[str]],
        init_data: dict,
        run_data: dict,
    ) -> None:
        """
        Tests that the observed Blender 5.0 output fails the task at its out-of-memory line while
        Blender keeps running, and not at any warning or error printed before it
        """
        # GIVEN
        mock_blender_client_path.return_value = "blender_client.py"
        adaptor = BlenderAdaptor(init_data)
        adaptor._action_queue = Mock()
        adaptor._start_blender_client()
        blender = mock_logging_subprocess.return_value
        blender.is_running = True
        handler = mock_logging_subprocess.call_args.kwargs["stdout_handler"]
        before = observed_output["Not out of memory"]
        lines = iter(before + observed_output[case])
        mock_sleep.side_effect = lambda *args: handler.emit(
            logging.makeLogRecord({"msg": next(lines)})
        )

        # WHEN
        with pytest.raises(RuntimeError) as exc_info:
            adaptor.on_run(run_data)

        # THEN
        assert str(exc_info.value) == f"Blender ran out of memory: {observed_output[case][0]}"
        assert mock_sleep.call_count == len(before) + 1
        assert blender.is_running

    def test_observed_output_around_the_error_does_not_fail_the_task(
        self, observed_output: dict[str, list[str]], init_data: dict
    ) -> None:
        """
        Tests that the observed Blender 5.0 lines other than the out-of-memory errors do not fail
        the task: the warnings and errors printed before them, and the GPU errors printed after them
        """
        # GIVEN
        adaptor = BlenderAdaptor(init_data)
        handler = RegexHandler(adaptor._get_regex_callbacks())
        lines = (
            observed_output["Not out of memory"]
            + observed_output["Case A"][1:]
            + observed_output["Case B"][1:]
        )

        # WHEN
        for line in lines:
            handler.emit(logging.makeLogRecord({"msg": line}))

        # THEN
        assert adaptor._exc_info is None
