# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

from __future__ import annotations

import logging
import os
import re
import sys
import threading
import time
from typing import Callable

from openjd.adaptor_runtime._version import version as openjd_adaptor_version
from openjd.adaptor_runtime.adaptors import Adaptor, AdaptorDataValidators, SemanticVersion
from openjd.adaptor_runtime.adaptors.configuration import AdaptorConfiguration
from openjd.adaptor_runtime.app_handlers import RegexCallback, RegexHandler
from openjd.adaptor_runtime.application_ipc import ActionsQueue, AdaptorServer
from openjd.adaptor_runtime.process import LoggingSubprocess
from openjd.adaptor_runtime_client import Action

from deadline.client.api import TelemetryClient, get_deadline_cloud_library_telemetry_client

from .._version import version as adaptor_version

_logger = logging.getLogger(__name__)


class BlenderNotRunningError(Exception):
    """Error that is raised when attempting
    to use Blender while it is not running"""


# Actions which must be queued before any others.
_FIRST_BLENDER_ACTIONS = ["scene_file", "gpu_device"]

# Order of execution is important.
_BLENDER_INIT_KEYS = [
    "render_scene",
    "view_layer",
    "camera",
    "output_dir",
    "output_file_name",
    "output_format",
]


def _check_for_exception(func: Callable) -> Callable:
    """
    Decorator that checks if an exception has been caught before calling the
    decorated function
    """

    def wrapped_func(self, *args, **kwargs):
        if not self._has_exception:  # Raises if there is an exception
            return func(self, *args, **kwargs)

    return wrapped_func


class BlenderAdaptor(Adaptor[AdaptorConfiguration]):
    """
    Adaptor that creates a session in Blender to Render interactively.
    """

    _SERVER_START_TIMEOUT_SECONDS = 30
    _SERVER_END_TIMEOUT_SECONDS = 30
    _BLENDER_START_TIMEOUT_SECONDS = 3600
    _BLENDER_END_TIMEOUT_SECONDS = 30

    _server: AdaptorServer | None = None
    _server_thread: threading.Thread | None = None
    _blender_client: LoggingSubprocess | None = None
    _action_queue = ActionsQueue()
    _is_rendering: bool = False
    # If a thread raises an exception we will update this to raise in the main thread
    _exc_info: Exception | None = None
    _performing_cleanup = False
    _telemetry_client: TelemetryClient | None = None
    _blender_version: str = ""

    @property
    def integration_data_interface_version(self) -> SemanticVersion:
        return SemanticVersion(major=0, minor=1)

    @staticmethod
    def _get_timer(timeout: int | float) -> Callable[[], bool]:
        """Given a timeout length, returns a lambda which returns True until the timeout occurs"""
        timeout_time = time.time() + timeout
        return lambda: time.time() < timeout_time

    @property
    def _has_exception(self) -> bool:
        """Property which checks the private _exc_info property for an exception

        Raises:
            self._exc_info: An exception if there is one

        Returns:
            bool: False there is no exception waiting to be raised
        """
        if self._exc_info and not self._performing_cleanup:
            raise self._exc_info
        return False

    @property
    def _blender_is_running(self) -> bool:
        """Property which indicates that the Blender client is running

        Returns:
            bool: True if the blender client is running, false otherwise
        """
        return self._blender_client is not None and self._blender_client.is_running

    @property
    def _blender_is_rendering(self) -> bool:
        """Property which indicates if blender is rendering

        Returns:
            bool: True if Blender is rendering, false otherwise
        """
        return self._blender_is_running and self._is_rendering

    @_blender_is_rendering.setter
    def _blender_is_rendering(self, value: bool) -> None:
        """Property setter which updates the private _is_rendering boolean.

        Args:
            value (bool): A boolean indicated if blender is rendering.
        """
        self._is_rendering = value

    def _wait_for_server(self) -> str:
        """
        Performs a busy wait for the server path that the adaptor server is running on, then
        returns it.

        Raises:
            RuntimeError: If the server does not finish initializing

        Returns:
            str: The server path the adaptor server is running on.
        """
        is_not_timed_out = self._get_timer(self._SERVER_START_TIMEOUT_SECONDS)
        while (self._server is None or self._server.server_path is None) and is_not_timed_out():
            time.sleep(0.01)

        if self._server is not None and self._server.server_path is not None:
            return self._server.server_path

        raise RuntimeError(
            "Could not find a server path because the server did not finish initializing"
        )

    def _start_blender_server(self) -> None:
        """
        Starts a server with the given ActionsQueue, attaches the server to
        the adaptor and serves forever in a blocking call.
        """
        self._server = AdaptorServer(self._action_queue, self)
        self._server.serve_forever()

    def _start_blender_server_thread(self) -> None:
        """
        Starts the Blender adaptor server in a thread.
        Sets the environment variable "BLENDER_ADAPTOR_SERVER_PATH" to the path the server is running
        on after the server has finished starting.
        """
        self._server_thread = threading.Thread(
            target=self._start_blender_server, name="BlenderAdaptorServerThread"
        )
        self._server_thread.start()
        os.environ["BLENDER_ADAPTOR_SERVER_PATH"] = self._wait_for_server()

    def _get_regex_callbacks(self) -> list[RegexCallback]:
        """
        Returns a list of RegexCallbacks used by the blender Adaptor

        Returns:
            list[RegexCallback]: List of Regex Callbacks to add
        """

        callback_list = []
        # Completion message is emitted by default_blender_handler.py::start_render
        completed_regexes = [re.compile("BlenderClient: Finished Rendering Frame [0-9]+")]
        progress_regexes = [
            re.compile(r"^Fra:.*Sample\s(\d+)\/(\d+)$"),  # Cycles
            re.compile(r"^Fra:.*Rendering\s(\d+)\s/\s(\d+)\ssamples$"),  # Eevee
            # Workbench renderer has no progress output
        ]
        error_regexes = [re.compile(".*Exception:.*|.*Error:.*|.*Warning.*")]
        # Capture the major minor patch version.
        version_regexes = [re.compile("BlenderClient: Blender Version ([0-9]+.[0-9]+.[0-9]+)")]

        callback_list.append(RegexCallback(completed_regexes, self._handle_complete))
        callback_list.append(RegexCallback(progress_regexes, self._handle_progress))
        if self.init_data.get("strict_error_checking", False):
            callback_list.append(RegexCallback(error_regexes, self._handle_error))
        callback_list.append(RegexCallback(version_regexes, self._handle_version))

        return callback_list

    @_check_for_exception
    def _handle_complete(self, match: re.Match) -> None:
        """
        Callback for stdout that indicate completeness of a render. Updates progress to 100
        Args:
            match (re.Match): The match object from the regex pattern that was matched the message
        """
        self._blender_is_rendering = False
        self.update_status(progress=100)

    @_check_for_exception
    def _handle_progress(self, match: re.Match) -> None:
        """
        Callback for stdout that indicate progress of a render.
        Args:
            match (re.Match): The match object from the regex pattern that was matched the message
        """
        capture_group = match.groups()
        progress = int(capture_group[0]) / int(capture_group[1]) * 100  # float
        progress = int(progress)  # Equivalent to math.floor
        self.update_status(progress=progress)

    def _handle_error(self, match: re.Match) -> None:
        """
        Callback for stdout that indicates an error or warning.
        Args:
            match (re.Match): The match object from the regex pattern that was matched the message

        Raises:
            RuntimeError: Always raises a runtime error to halt the adaptor.
        """
        self._exc_info = RuntimeError(f"Blender Encountered an Error: {match.group(0)}")

    def _handle_version(self, match: re.Match) -> None:
        """
        Callback for stdout that records the Blender version.
        Args:
            match (re.Match): The match object from the regex pattern that was matched the message
        """
        self._blender_version = match.groups()[0]

    @property
    def blender_client_path(self) -> str:
        """
        Obtains the blender_client.py path by searching directories in sys.path

        Raises:
            FileNotFoundError: If the blender_client.py file could not be found.

        Returns:
            str: The path to the blender_client.py file.
        """
        for dir_ in sys.path:
            path = os.path.join(
                dir_, "deadline", "blender_adaptor", "BlenderClient", "blender_client.py"
            )
            if os.path.isfile(path):
                return path
        raise FileNotFoundError(
            "Could not find blender_client.py. Check that the BlenderClient package is in one of the "
            f"following directories: {sys.path[1:]}"
        )

    def _start_blender_client(self) -> None:
        """
        Starts the blender client by launching Blender with the blender_client.py file.

        Blender and blenderPy must be on the system PATH, for example due to a Rez environment being active.

        Raises:
            FileNotFoundError: If the blender_client.py file could not be found.
        """
        blender_exe = os.environ.get("BLENDER_EXECUTABLE", "blender")
        regexhandler = RegexHandler(self._get_regex_callbacks())

        # Add the openjd namespace directory to PYTHONPATH, so that adaptor_runtime_client
        # will be available directly to the adaptor client.
        import openjd.adaptor_runtime_client

        from deadline import blender_adaptor

        openjd_namespace_dir = os.path.dirname(
            os.path.dirname(openjd.adaptor_runtime_client.__file__)
        )
        deadline_namespace_dir = os.path.dirname(os.path.dirname(blender_adaptor.__file__))
        python_path_addition = f"{openjd_namespace_dir}{os.pathsep}{deadline_namespace_dir}"
        if "PYTHONPATH" in os.environ:
            os.environ["PYTHONPATH"] = (
                f"{os.environ['PYTHONPATH']}{os.pathsep}{python_path_addition}"
            )
        else:
            os.environ["PYTHONPATH"] = python_path_addition

        if self.init_data["render_engine"] == "cycles":
            _logger.warning("Missing configuration for cycles render engine.")

        self._blender_client = LoggingSubprocess(
            args=[
                blender_exe,
                "--background",
                "--python",
                self.blender_client_path,
                "--python-use-system-env",
            ],
            stdout_handler=regexhandler,
            stderr_handler=regexhandler,
        )

    def _populate_action_queue(self) -> None:
        """
        Populates the adaptor server's action queue with actions from the init_data that the blender
        Client will request and perform. The action must be present in the _FIRST_blender_ACTIONS or
        _blender_INIT_KEYS set to be added to the action queue.
        """

        # Set up the renderer
        self._action_queue.enqueue_action(
            Action("render_engine", {"render_engine": self.init_data["render_engine"]})
        )

        for action_name in _FIRST_BLENDER_ACTIONS:
            self._action_queue.enqueue_action(self._action_from_action_item(action_name))

        for action_name in _BLENDER_INIT_KEYS:
            if action_name in self.init_data:
                _logger.info(f"ENQUEUING ACTION {action_name}")
                self._action_queue.enqueue_action(self._action_from_action_item(action_name))
            else:
                _logger.info(f"SKIPPING ACTION {action_name}: NOT IN INIT DATA")

    def on_start(self) -> None:
        """
        For job stickiness. Will start everything required for the Task.

        Raises:
            jsonschema.ValidationError: When init_data fails validation against the adaptor schema.
            jsonschema.SchemaError: When the adaptor schema itself is nonvalid.
            RuntimeError: If Blender did not complete initialization actions due to an exception
            TimeoutError: If Blender did not complete initialization actions due to timing out.
            FileNotFoundError: If the blender_client.py file could not be found.
        """
        cur_dir = os.path.dirname(__file__)
        schema_dir = os.path.join(cur_dir, "schemas")
        validators = AdaptorDataValidators.for_adaptor(schema_dir)
        validators.init_data.validate(self.init_data)

        self.update_status(progress=0, status_message="Initializing blender")
        self._start_blender_server_thread()
        self._populate_action_queue()

        self._start_blender_client()

        is_not_timed_out = self._get_timer(self._BLENDER_START_TIMEOUT_SECONDS)
        while (
            self._blender_is_running
            and not self._has_exception
            and len(self._action_queue) > 0
            and is_not_timed_out()
        ):
            time.sleep(0.1)  # busy wait for blender to finish initialization

        self._get_deadline_telemetry_client().record_event(
            event_type="com.amazon.rum.deadline.adaptor.runtime.start", event_details={}
        )

        if len(self._action_queue) > 0:
            if is_not_timed_out():
                raise RuntimeError(
                    "Blender encountered an error and was not able to complete initialization actions."
                )
            else:
                raise TimeoutError(
                    "Blender did not complete initialization actions in "
                    f"{self._BLENDER_START_TIMEOUT_SECONDS} seconds and failed to start."
                )

    def on_run(self, run_data: dict) -> None:
        """
        This starts a render in Blender for the given frame and performs a busy wait until the render
        completes.
        """
        if not self._blender_is_running:
            raise BlenderNotRunningError("Cannot render because Blender is not running.")

        # Run the camera action.
        self._action_queue.enqueue_action(Action("camera", run_data))

        # Load the validation schemas and validate the run data.
        cur_dir = os.path.dirname(__file__)
        schema_dir = os.path.join(cur_dir, "schemas")
        validators = AdaptorDataValidators.for_adaptor(schema_dir)
        validators.run_data.validate(run_data)

        # Queue the rendering tasks.
        self._blender_is_rendering = True
        self._action_queue.enqueue_action(Action("start_render", run_data))
        while self._blender_is_rendering and not self._has_exception:
            # Wait for the render to finish.
            time.sleep(0.1)

        if not self._blender_is_running and self._blender_client:
            # blender Client will always exist here.
            #  This is always an error case because the blender Client should still be running and
            #  waiting for the next command. If the thread finished, then we cannot continue
            exit_code = self._blender_client.returncode
            self._get_deadline_telemetry_client().record_error(
                {"exit_code": exit_code, "exception_scope": "on_run"}, str(RuntimeError)
            )
            raise RuntimeError(
                "Blender exited early and did not render successfully, please check render logs. "
                f"Exit code {exit_code}"
            )

    def on_stop(self) -> None:
        return

    def on_cleanup(self):
        """
        Cleans up the adaptor by closing the blender client and adaptor server.
        """
        self._performing_cleanup = True

        self._action_queue.enqueue_action(Action("close"), front=True)
        is_not_timed_out = self._get_timer(self._BLENDER_END_TIMEOUT_SECONDS)
        while self._blender_is_running and is_not_timed_out():
            time.sleep(0.1)
        if self._blender_is_running and self._blender_client:
            _logger.error(
                "Blender did not complete cleanup actions and failed to gracefully shutdown. "
                "Terminating."
            )
            self._blender_client.terminate()

        if self._server:
            self._server.shutdown()

        if self._server_thread and self._server_thread.is_alive():
            self._server_thread.join(timeout=self._SERVER_END_TIMEOUT_SECONDS)
            if self._server_thread.is_alive():
                _logger.error("Failed to shutdown the Blender Adaptor server.")

        self._performing_cleanup = False

    def on_cancel(self):
        """
        Cancels the current render if Blender is rendering.
        """
        _logger.info("CANCEL REQUESTED")
        if not self._blender_client or not self._blender_is_running:
            _logger.info("Nothing to cancel because Blender is not running")
            return

        # Terminate immediately since the Blender client does not have a graceful shutdown
        self._blender_client.terminate(grace_time_s=0)

    def _action_from_action_item(self, item_name: str) -> Action:
        """Shortcut to create an Action from the init_data."""
        return Action(
            item_name,
            {item_name: self.init_data[item_name]},
        )

    def _get_deadline_telemetry_client(self):
        """
        Wrapper around the Deadline Client Library telemetry client, in order to set package-specific information
        """
        if not self._telemetry_client:
            self._telemetry_client = get_deadline_cloud_library_telemetry_client()
            self._telemetry_client.update_common_details(
                {
                    "deadline-cloud-for-blender-adaptor-version": adaptor_version,
                    "blender-version": self._blender_version,
                    "open-jd-adaptor-runtime-version": openjd_adaptor_version,
                }
            )
        return self._telemetry_client
