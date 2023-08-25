# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

from __future__ import annotations

import os
import re
from unittest.mock import Mock, PropertyMock, patch

import pytest
import jsonschema  # type: ignore

import deadline_adaptor_for_blender.BlenderAdaptor.adaptor as adaptor_module
from deadline_adaptor_for_blender.BlenderAdaptor import BlenderAdaptor
from deadline_adaptor_for_blender.BlenderAdaptor.adaptor import BlenderNotRunningError


@pytest.fixture()
def init_data() -> dict:
    """
    Pytest fixture to return an init_data dictionary that passes validation

    Returns
        dict: An init_data dictionary
    """
    return {
        "project_file": "C:\\Users\\ewaschuk\\Downloads\\shiny_buster.blend",
        "strict_error_checking": True,
        "version": "3.3",
        "renderer": "BLENDER_WORKBENCH",
    }


@pytest.fixture()
def run_data() -> dict:
    """
    Pytest fixture to return a run_data dictionary that passes validation

    Returns
        dict: A run_data dictionary
    """
    return {
        "frame": 51,
        "animation": True,
        "scene": "Scene",
        "layer": "RenderLayer",
        "output_path": "//buster_####",
    }


class TestBlenderAdaptor_on_start:
    @patch.object(adaptor_module.os.path, "isfile", return_value=True)
    @patch(
        "deadline_adaptor_for_blender.BlenderAdaptor.adaptor.ActionsQueue.__len__", return_value=0
    )
    @patch("deadline_adaptor_for_blender.BlenderAdaptor.adaptor.LoggingSubprocess")
    @patch("deadline_adaptor_for_blender.BlenderAdaptor.adaptor.AdaptorServer")
    def test_on_start(
        self,
        mock_server: Mock,
        mock_logging_subprocess: Mock,
        mock_actions_queue: Mock,
        mock_isfile: Mock,
        init_data: dict,
    ) -> None:
        """Tests that on_start completes without error"""
        adaptor = BlenderAdaptor(init_data)
        mock_server.return_value.socket_path = "/tmp/9999"
        adaptor.on_start()

    @patch(
        "deadline_adaptor_for_blender.BlenderAdaptor.adaptor.ActionsQueue.__len__", return_value=0
    )
    @patch("deadline_adaptor_for_blender.BlenderAdaptor.adaptor.LoggingSubprocess")
    @patch("deadline_adaptor_for_blender.BlenderAdaptor.adaptor.AdaptorServer")
    def test_on_start_bad_project_file(
        self,
        mock_server: Mock,
        mock_logging_subprocess: Mock,
        mock_actions_queue: Mock,
        init_data: dict,
    ) -> None:
        """Tests that on_start throws FileNotFoundError when project_file cannot be found."""
        adaptor = BlenderAdaptor(init_data)
        mock_server.return_value.socket_path = "/tmp/9999"
        with pytest.raises(FileNotFoundError) as exc_info:
            adaptor.on_start()

        # THEN
        project_file = init_data["project_file"]
        assert str(exc_info.value) == f"Could not find project file at '{project_file}'"

    @patch.object(adaptor_module.os.path, "isfile", return_value=True)
    @patch("time.sleep")
    @patch(
        "deadline_adaptor_for_blender.BlenderAdaptor.adaptor.ActionsQueue.__len__", return_value=0
    )
    @patch("deadline_adaptor_for_blender.BlenderAdaptor.adaptor.LoggingSubprocess")
    @patch("deadline_adaptor_for_blender.BlenderAdaptor.adaptor.AdaptorServer")
    def test_waits_for_server_socket(
        self,
        mock_server: Mock,
        mock_logging_subprocess: Mock,
        mock_actions_queue: Mock,
        mock_sleep: Mock,
        mock_isfile: Mock,
        init_data: dict,
    ) -> None:
        """Tests that the adaptor waits until the server socket is available"""
        # GIVEN
        adaptor = BlenderAdaptor(init_data)
        socket_mock = PropertyMock(
            side_effect=[None, None, None, "/tmp/9999", "/tmp/9999", "/tmp/9999"]
        )
        type(mock_server.return_value).socket_path = socket_mock

        # WHEN
        adaptor.on_start()

        # THEN
        assert mock_sleep.call_count == 3

    @patch("threading.Thread")
    @patch("deadline_adaptor_for_blender.BlenderAdaptor.adaptor.AdaptorServer")
    def test_server_init_fail(self, mock_server: Mock, mock_thread: Mock, init_data: dict) -> None:
        """Tests that an error is raised if no socket becomes available"""
        # GIVEN
        adaptor = BlenderAdaptor(init_data)

        with patch.object(adaptor, "_SERVER_START_TIMEOUT_SECONDS", 0.01), pytest.raises(
            RuntimeError
        ) as exc_info:
            # WHEN
            adaptor.on_start()

        # THEN
        assert (
            str(exc_info.value)
            == "Could not find a socket path because the server did not finish initializing"
        )

    @patch.object(adaptor_module.os.path, "isfile", return_value=False)
    def test_client_not_found(
        self,
        mock_isfile: Mock,
        init_data: dict,
    ) -> None:
        """Tests that the an error is raised if the Blender client file cannot be found"""
        # GIVEN
        adaptor = BlenderAdaptor(init_data)
        test_dir = "test_dir"

        with patch.object(adaptor_module.sys, "path", ["unreported_dir", test_dir]):
            with pytest.raises(FileNotFoundError) as exc_info:
                # WHEN
                adaptor._get_blender_client_path()

        # THEN
        error_msg = (
            "Could not find blender_client.py. Check that the BlenderClient package is in "
            f"one of the following directories: {[test_dir]}"
        )
        assert str(exc_info.value) == error_msg
        mock_isfile.assert_called_with(
            os.path.join(
                test_dir, "deadline_adaptor_for_blender", "BlenderClient", "blender_client.py"
            )
        )

    def test_get_major_minor_will_truncate_full_version(
        self,
        init_data: dict,
    ) -> None:
        """
        Tests that _get_major_minor_version will return a non-standard version string as-is.
        """
        # GIVEN
        adaptor = BlenderAdaptor(init_data)
        blender_version = "1.2.3"
        expected_version = "1.2"

        # WHEN
        major_minor = adaptor._get_major_minor_version(blender_version)

        assert major_minor == expected_version

    def test_get_major_minor_will_return_nonstandard_version(
        self,
        init_data: dict,
    ) -> None:
        """
        Tests that _get_major_minor_version will return a non-standard version string as-is.
        """
        # GIVEN
        adaptor = BlenderAdaptor(init_data)
        blender_version = "1.2.3.4"

        # WHEN
        major_minor = adaptor._get_major_minor_version(blender_version)

        assert major_minor == blender_version

    @patch.object(adaptor_module.os.path, "isfile", return_value=True)
    @patch(
        "deadline_adaptor_for_blender.BlenderAdaptor.adaptor.ActionsQueue.__len__", return_value=1
    )
    @patch("deadline_adaptor_for_blender.BlenderAdaptor.adaptor.LoggingSubprocess")
    @patch("deadline_adaptor_for_blender.BlenderAdaptor.adaptor.AdaptorServer")
    def test_blender_init_timeout(
        self,
        mock_server: Mock,
        mock_logging_subprocess: Mock,
        mock_actions_queue: Mock,
        mock_isfile: Mock,
        init_data: dict,
    ) -> None:
        """
        Tests that a TimeoutError is raised if the Blender client does not complete initialization
        tasks within a given time frame
        """
        # GIVEN
        adaptor = BlenderAdaptor(init_data)
        mock_server.return_value.socket_path = "/tmp/9999"
        new_timeout = 0.01

        with patch.object(adaptor, "_BLENDER_START_TIMEOUT_SECONDS", new_timeout), pytest.raises(
            TimeoutError
        ) as exc_info:
            # WHEN
            adaptor.on_start()

        # THEN
        error_msg = (
            f"Blender did not complete initialization actions in {new_timeout} seconds and "
            "failed to start."
        )
        assert str(exc_info.value) == error_msg

    @patch.object(adaptor_module.os.path, "isfile", return_value=True)
    @patch.object(BlenderAdaptor, "_blender_is_running", False)
    @patch(
        "deadline_adaptor_for_blender.BlenderAdaptor.adaptor.ActionsQueue.__len__", return_value=1
    )
    @patch("deadline_adaptor_for_blender.BlenderAdaptor.adaptor.LoggingSubprocess")
    @patch("deadline_adaptor_for_blender.BlenderAdaptor.adaptor.AdaptorServer")
    def test_blender_init_fail(
        self,
        mock_server: Mock,
        mock_logging_subprocess: Mock,
        mock_actions_queue: Mock,
        mock_isfile: Mock,
        init_data: dict,
    ) -> None:
        """
        Tests that an RuntimeError is raised if the blender client encounters an exception
        """
        # GIVEN
        adaptor = BlenderAdaptor(init_data)
        mock_server.return_value.socket_path = "/tmp/9999"

        with pytest.raises(RuntimeError) as exc_info:
            # WHEN
            adaptor.on_start()

        # THEN
        error_msg = (
            "Blender encountered an error and was not able to complete initialization actions."
        )
        assert str(exc_info.value) == error_msg

    @patch.object(adaptor_module.os.path, "isfile", return_value=True)
    @patch.object(BlenderAdaptor, "_action_queue")
    @patch("deadline_adaptor_for_blender.BlenderAdaptor.adaptor.LoggingSubprocess")
    @patch("deadline_adaptor_for_blender.BlenderAdaptor.adaptor.AdaptorServer")
    def test_populate_action_queue_required_keys(
        self,
        mock_server: Mock,
        mock_logging_subprocess: Mock,
        mock_actions_queue: Mock,
        mock_isfile: Mock,
    ) -> None:
        """Tests that on_start completes without error"""
        mock_actions_queue.__len__.return_value = 0

        adaptor = BlenderAdaptor(
            {
                "project_file": "C:\\Users\\ewaschuk\\Downloads\\shiny_buster.blend",
                "version": "3.3",
                "renderer": "BLENDER_WORKBENCH",
            }
        )

        mock_server.return_value.socket_path = "/tmp/9999"

        adaptor.on_start()

        calls = mock_actions_queue.enqueue_action.call_args_list

        assert calls[0].args[0].name == "renderer"
        assert calls[1].args[0].name == "resolve_assets"

    @patch.object(adaptor_module.os.path, "isfile", return_value=True)
    @patch.object(BlenderAdaptor, "_blender_is_running", False)
    @patch(
        "deadline_adaptor_for_blender.BlenderAdaptor.adaptor.ActionsQueue.__len__", return_value=1
    )
    @patch("deadline_adaptor_for_blender.BlenderAdaptor.adaptor.LoggingSubprocess")
    @patch("deadline_adaptor_for_blender.BlenderAdaptor.adaptor.AdaptorServer")
    def test_init_data_wrong_schema(
        self,
        mock_server: Mock,
        mock_logging_subprocess: Mock,
        mock_actions_queue: Mock,
        mock_isfile: Mock,
    ) -> None:
        # GIVEN
        init_data = {"doesNot": "conform", "thisData": "isBad"}
        adaptor = BlenderAdaptor(init_data)

        with pytest.raises(jsonschema.exceptions.ValidationError) as exc_info:
            # WHEN
            adaptor.on_start()

        # THEN
        error_msg = " is a required property"
        assert error_msg in exc_info.value.message


class TestBlenderAdaptor_on_run:
    @patch.object(adaptor_module.os.path, "isfile", return_value=True)
    @patch("time.sleep")
    @patch(
        "deadline_adaptor_for_blender.BlenderAdaptor.adaptor.ActionsQueue.__len__", return_value=0
    )
    @patch("deadline_adaptor_for_blender.BlenderAdaptor.adaptor.LoggingSubprocess")
    @patch("deadline_adaptor_for_blender.BlenderAdaptor.adaptor.AdaptorServer")
    def test_on_run(
        self,
        mock_server: Mock,
        mock_logging_subprocess: Mock,
        mock_actions_queue: Mock,
        mock_sleep: Mock,
        mock_isfile: Mock,
        init_data: dict,
        run_data: dict,
    ) -> None:
        """Tests that on_run waits for completion"""
        # GIVEN
        adaptor = BlenderAdaptor(init_data)
        mock_server.return_value.socket_path = "/tmp/9999"
        # First side_effect value consumed by setter
        is_rendering_mock = PropertyMock(side_effect=[None, True, False])
        BlenderAdaptor._is_rendering = is_rendering_mock
        adaptor.on_start()

        # WHEN
        adaptor.on_run(run_data)

        # THEN
        mock_sleep.assert_called_once_with(0.1)

    @patch.object(adaptor_module.os.path, "isfile", return_value=True)
    @patch("time.sleep")
    @patch(
        "deadline_adaptor_for_blender.BlenderAdaptor.adaptor.ActionsQueue.__len__", return_value=0
    )
    @patch("deadline_adaptor_for_blender.BlenderAdaptor.adaptor.LoggingSubprocess")
    @patch("deadline_adaptor_for_blender.BlenderAdaptor.adaptor.AdaptorServer")
    def test_on_run_blender_not_running(
        self,
        mock_server: Mock,
        mock_logging_subprocess: Mock,
        mock_actions_queue: Mock,
        mock_sleep: Mock,
        mock_isfile: Mock,
        init_data: dict,
        run_data: dict,
    ) -> None:
        """Tests that on_run waits for completion"""
        # GIVEN
        adaptor = BlenderAdaptor(init_data)
        mock_server.return_value.socket_path = "/tmp/9999"
        mock_logging_subprocess.return_value.returncode = 1
        # First side_effect value consumed by setter
        is_rendering_mock = PropertyMock(side_effect=[None, True, False])
        BlenderAdaptor._is_rendering = is_rendering_mock
        adaptor.on_start()

        # WHEN
        with patch(
            "deadline_adaptor_for_blender.BlenderAdaptor.adaptor.BlenderAdaptor._blender_is_running",
            new_callable=PropertyMock,
        ) as mock_is_running:
            mock_is_running.side_effect = [True, False, False]
            with pytest.raises(BlenderNotRunningError) as exc_info:
                adaptor.on_run(run_data)

        # THEN
        assert str(exc_info.value) == (
            "Blender exited early and did not render successfully, please check render logs. "
            "Exit code 1"
        )

    @patch.object(adaptor_module.os.path, "isfile", return_value=True)
    @patch("time.sleep")
    @patch(
        "deadline_adaptor_for_blender.BlenderAdaptor.adaptor.ActionsQueue.__len__", return_value=0
    )
    @patch("deadline_adaptor_for_blender.BlenderAdaptor.adaptor.LoggingSubprocess")
    @patch("deadline_adaptor_for_blender.BlenderAdaptor.adaptor.AdaptorServer")
    def test_run_data_wrong_schema(
        self,
        mock_server: Mock,
        mock_logging_subprocess: Mock,
        mock_actions_queue: Mock,
        mock_sleep: Mock,
        mock_isfile: Mock,
        init_data: dict,
    ) -> None:
        # GIVEN
        adaptor = BlenderAdaptor(init_data)
        mock_server.return_value.socket_path = "/tmp/9999"
        mock_logging_subprocess.return_value.returncode = 1
        run_data = {"bad": "schema"}
        # First side_effect value consumed by setter
        adaptor.on_start()

        with pytest.raises(jsonschema.exceptions.ValidationError) as exc_info:
            # WHEN
            adaptor.on_run(run_data)

        # THEN
        error_msg = " is a required property"
        assert error_msg in exc_info.value.message


class TestBlenderAdaptor_on_end:
    @patch.object(adaptor_module.os.path, "isfile", return_value=True)
    @patch("time.sleep")
    @patch(
        "deadline_adaptor_for_blender.BlenderAdaptor.adaptor.ActionsQueue.__len__", return_value=0
    )
    @patch("deadline_adaptor_for_blender.BlenderAdaptor.adaptor.LoggingSubprocess")
    @patch("deadline_adaptor_for_blender.BlenderAdaptor.adaptor.AdaptorServer")
    def test_on_end(
        self,
        mock_server: Mock,
        mock_logging_subprocess: Mock,
        mock_actions_queue: Mock,
        mock_sleep: Mock,
        mock_isfile: Mock,
        init_data: dict,
        run_data: dict,
    ) -> None:
        # GIVEN
        adaptor = BlenderAdaptor(init_data)
        mock_server.return_value.socket_path = "/tmp/9999"
        is_rendering_mock = PropertyMock(return_value=False)
        BlenderAdaptor._is_rendering = is_rendering_mock
        adaptor.on_start()
        adaptor.on_run(run_data)

        try:
            # WHEN
            adaptor.on_end()
        except Exception as e:
            pytest.fail(f"Test raised an exception when it shouldn't have: {e}")
        else:
            # THEN
            pass  # on_end ran without exception


class TestBlenderAdaptor_on_cleanup:
    @patch("time.sleep")
    @patch("deadline_adaptor_for_blender.BlenderAdaptor.adaptor._logger")
    def test_on_cleanup_blender_not_graceful_shutdown(
        self, mock_logger: Mock, mock_sleep: Mock, init_data: dict
    ) -> None:
        """Tests that on_cleanup reports when blender does not gracefully shutdown"""
        # GIVEN
        adaptor = BlenderAdaptor(init_data)

        with patch(
            "deadline_adaptor_for_blender.BlenderAdaptor.adaptor.BlenderAdaptor._blender_is_running",
            new_callable=lambda: True,
        ), patch.object(adaptor, "_BLENDER_END_TIMEOUT_SECONDS", 0.01), patch.object(
            adaptor, "_blender_client"
        ) as mock_client:
            # WHEN
            adaptor.on_cleanup()

        # THEN
        mock_logger.error.assert_called_once_with(
            "Blender did not complete cleanup actions and failed "
            "to gracefully shutdown. Terminating."
        )
        mock_client.terminate.assert_called_once()

    @patch("time.sleep")
    @patch("deadline_adaptor_for_blender.BlenderAdaptor.adaptor._logger")
    def test_on_cleanup_server_not_graceful_shutdown(
        self, mock_logger: Mock, mock_sleep: Mock, init_data: dict
    ) -> None:
        """Tests that on_cleanup reports when the server does not shutdown"""
        # GIVEN
        adaptor = BlenderAdaptor(init_data)

        with patch(
            "deadline_adaptor_for_blender.BlenderAdaptor.adaptor.BlenderAdaptor._blender_is_running",
            new_callable=lambda: False,
        ), patch.object(adaptor, "_SERVER_END_TIMEOUT_SECONDS", 0.01), patch.object(
            adaptor, "_server_thread"
        ) as mock_server_thread:
            mock_server_thread.is_alive.return_value = True
            # WHEN
            adaptor.on_cleanup()

        # THEN
        mock_logger.error.assert_called_once_with("Failed to shutdown the Blender Adaptor server.")
        mock_server_thread.join.assert_called_once_with(timeout=0.01)

    @patch.object(adaptor_module.os.path, "isfile", return_value=True)
    @patch("time.sleep")
    @patch(
        "deadline_adaptor_for_blender.BlenderAdaptor.adaptor.ActionsQueue.__len__", return_value=0
    )
    @patch("deadline_adaptor_for_blender.BlenderAdaptor.adaptor.LoggingSubprocess")
    @patch("deadline_adaptor_for_blender.BlenderAdaptor.adaptor.AdaptorServer")
    def test_on_cleanup(
        self,
        mock_server: Mock,
        mock_logging_subprocess: Mock,
        mock_actions_queue: Mock,
        mock_sleep: Mock,
        mock_isfile: Mock,
        init_data: dict,
        run_data: dict,
    ) -> None:
        # GIVEN
        adaptor = BlenderAdaptor(init_data)
        mock_server.return_value.socket_path = "/tmp/9999"
        is_rendering_mock = PropertyMock(return_value=False)
        BlenderAdaptor._is_rendering = is_rendering_mock

        adaptor.on_start()
        adaptor.on_run(run_data)
        adaptor.on_end()

        with patch(
            "deadline_adaptor_for_blender.BlenderAdaptor.adaptor.BlenderAdaptor._blender_is_running",
            new_callable=lambda: False,
        ):
            # WHEN
            adaptor.on_cleanup()

        # THEN
        return  # Assert no errors occured

    def test_regex_callbacks_cache(self, init_data):
        """Test that regex callbacks are generated exactly once"""
        # GIVEN
        adaptor = BlenderAdaptor(init_data)

        # WHEN
        regex_callbacks = adaptor._regex_callbacks

        # THEN
        assert regex_callbacks is adaptor._regex_callbacks

    @patch("deadline_adaptor_for_blender.BlenderAdaptor.adaptor.BlenderAdaptor.update_status")
    def test_handle_complete(self, mock_update_status: Mock, init_data: dict):
        """Tests that the _handle_complete method updates the progress correctly"""
        # GIVEN
        adaptor = BlenderAdaptor(init_data)
        adaptor._produced_outputs = 0
        adaptor._expected_outputs = 1
        regex_callbacks = adaptor._get_regex_callbacks()

        # WHEN
        # Apply the available regexes to handle the example log. We should have a match.
        for callback in regex_callbacks:
            for regex in callback.regex_list:
                match = regex.search(
                    "Fra:15 Mem:326.11M (Peak 460.58M) | Time:02:18.56 | Mem:197.63M, Peak:197.63M "
                    "| Scene, RenderLayer | Finished"
                )
                if match:
                    # Check that callback function matches what we expect
                    assert callback.callback.__name__ is adaptor._handle_complete.__name__
                    break
            if match:
                break
        else:
            # The way these tests are defined, we should always have a match.
            assert False, "No regex callback matched _handle_complete STDOUT string"

        adaptor._handle_complete(match)

        # THEN
        mock_update_status.assert_called_once_with(progress=100)

    @patch("deadline_adaptor_for_blender.BlenderAdaptor.adaptor.BlenderAdaptor.update_status")
    def test_handle_complete_remaining_renders(self, mock_update_status: Mock, init_data: dict):
        """Tests that the _handle_complete method updates the progress correctly"""
        # GIVEN
        adaptor = BlenderAdaptor(init_data)
        adaptor._produced_outputs = 0
        adaptor._expected_outputs = 2
        regex_callbacks = adaptor._get_regex_callbacks()

        # WHEN
        # Apply the available regexes to handle the example log. We should have a match.
        for callback in regex_callbacks:
            for regex in callback.regex_list:
                match = regex.search(
                    "Fra:15 Mem:326.11M (Peak 460.58M) | Time:02:18.56 | Mem:197.63M, Peak:197.63M "
                    "| Scene, RenderLayer | Finished"
                )
                if match:
                    # Check that callback function matches what we expect
                    assert callback.callback.__name__ is adaptor._handle_complete.__name__
                    break
            if match:
                break
        else:
            # The way these tests are defined, we should always have a match.
            assert False, "No regex callback matched _handle_complete STDOUT string"

        adaptor._handle_complete(match)

        # THEN
        mock_update_status.assert_not_called()

    handle_progess_params = [
        (
            0,
            1,
            "Fra:13 Mem:223.28M (Peak 460.58M) | Time:00:35.83 | "
            + "Remaining:01:35.54 | Mem:197.63M, Peak:197.63M | "
            + "Scene, RenderLayer | Sample 129/500",
            25.8,
        ),
        (
            0,
            1,
            "Fra:17 Mem:223.28M (Peak 460.58M) | Time:01:42.38 | "
            + "Remaining:00:29.79 | Mem:197.63M, Peak:197.63M | "
            + "Scene, RenderLayer | Sample 3600/5000",
            72,
        ),
        (
            0,
            2,
            "Fra:17 Mem:223.28M (Peak 460.58M) | Time:01:42.38 | "
            + "Remaining:00:29.79 | Mem:197.63M, Peak:197.63M | "
            + "Scene, RenderLayer | Sample 3600/5000",
            36,
        ),
        (
            1,
            2,
            "Fra:17 Mem:223.28M (Peak 460.58M) | Time:01:42.38 | "
            + "Remaining:00:29.79 | Mem:197.63M, Peak:197.63M | "
            + "Scene, RenderLayer | Sample 0/5000",
            50,
        ),
    ]

    @pytest.mark.parametrize(
        "produced_outputs, num_outputs, stdout, expected_progress", handle_progess_params
    )
    @patch("deadline_adaptor_for_blender.BlenderAdaptor.adaptor.BlenderAdaptor.update_status")
    def test_handle_progress(
        self,
        mock_update_status: Mock,
        produced_outputs: int,
        num_outputs: int,
        stdout: str,
        expected_progress: float,
        init_data: dict,
    ) -> None:
        # GIVEN
        adaptor = BlenderAdaptor(init_data)
        adaptor._produced_outputs = produced_outputs
        adaptor._expected_outputs = num_outputs
        regex_callbacks = adaptor._get_regex_callbacks()

        # WHEN
        # Apply the available regexes to handle the example log. We should have a match.
        for callback in regex_callbacks:
            for regex in callback.regex_list:
                match = regex.search(stdout)
                if match:
                    # Check that callback function matches what we expect
                    assert callback.callback.__name__ is adaptor._handle_progress.__name__
                    break
            if match:
                break
        else:
            # The way these tests are defined, we should always have a match.
            assert False, "No regex callback matched _handle_progress STDOUT string"

        adaptor._handle_progress(match)

        # THEN
        mock_update_status.assert_called_once_with(progress=expected_progress)

    @pytest.mark.parametrize(
        "stdout, error_regex",
        [
            (
                "AttributeError: 'BlendData' object has no attribute 'test'",
                re.compile(".*Error:.*"),
            ),
        ],
    )
    def test_handle_error(self, init_data: dict, stdout: str, error_regex: re.Pattern) -> None:
        """Tests that the _handle_error method throws a runtime error correctly"""
        # GIVEN
        adaptor = BlenderAdaptor(init_data)

        # WHEN
        match = error_regex.search(stdout)

        # The way these tests are defined, we should always have a match.
        if match is None:
            assert False
        adaptor._handle_error(match)

        # THEN
        assert str(adaptor._exc_info) == f"Blender Encountered an Error: {stdout}"

    @pytest.mark.parametrize("strict_error_checking", [True, False])
    def test_strict_error_checking(self, init_data: dict, strict_error_checking: bool) -> None:
        """
        Tests that the strict_error_checking flag in the init_data determines if the handle_error
        RegexCallback is returned in the _get_regex_callbacks function
        """
        # GIVEN
        init_data["strict_error_checking"] = strict_error_checking
        adaptor = BlenderAdaptor(init_data)
        error_regexes = [re.compile(".*Error:.*|.*Exception:.*|.+ error: .+")]

        # WHEN
        callbacks = adaptor._get_regex_callbacks()

        # THEN
        assert (
            any(error_regexes == regex_callback.regex_list for regex_callback in callbacks)
            == strict_error_checking
        )

    @pytest.mark.parametrize("adaptor_exc_info", [RuntimeError("Something Bad Happened!"), None])
    def test_has_exception(self, init_data: dict, adaptor_exc_info: Exception | None) -> None:
        """
        Validates that the adaptor._has_exception property raises when adaptor._exc_info is not None
        and returns false when adaptor._exc_info is None
        """
        adaptor = BlenderAdaptor(init_data)
        adaptor._exc_info = adaptor_exc_info

        if adaptor_exc_info:
            with pytest.raises(RuntimeError) as exc_info:
                adaptor._has_exception

            assert exc_info.value == adaptor_exc_info
        else:
            assert not adaptor._has_exception

    @patch.object(
        BlenderAdaptor, "_blender_is_running", new_callable=PropertyMock(return_value=False)
    )
    def test_raises_if_blender_not_running(
        self,
        init_data: dict,
        run_data: dict,
    ) -> None:
        """Tests that on_run raises a BlenderNotRunningError if blender is not running"""
        # GIVEN
        adaptor = BlenderAdaptor(init_data)

        # WHEN
        with pytest.raises(BlenderNotRunningError) as raised_err:
            adaptor.on_run(run_data)

        # THEN
        assert raised_err.match("Cannot render because Blender is not running.")


class TestBlenderAdaptor_on_cancel:
    """Tests for BlenderAdaptor.on_cancel"""

    def test_terminates_blender_client(self, init_data: dict, caplog: pytest.LogCaptureFixture):
        """Tests that the blender client is terminated on cancel"""
        # GIVEN
        caplog.set_level(0)
        adaptor = BlenderAdaptor(init_data)
        adaptor._blender_client = mock_client = Mock()

        # WHEN
        adaptor.on_cancel()

        # THEN
        mock_client.terminate.assert_called_once_with(grace_time_s=0)
        assert "CANCEL REQUESTED" in caplog.text

    def test_does_nothing_if_blender_not_running(
        self, init_data: dict, caplog: pytest.LogCaptureFixture
    ):
        """Tests that nothing happens if a cancel is requested when blender is not running"""
        # GIVEN
        caplog.set_level(0)
        adaptor = BlenderAdaptor(init_data)
        adaptor._blender_client = None

        # WHEN
        adaptor.on_cancel()

        # THEN
        assert "CANCEL REQUESTED" in caplog.text
        assert "Nothing to cancel because Blender is not running" in caplog.text
