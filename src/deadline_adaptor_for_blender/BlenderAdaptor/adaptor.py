# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

from __future__ import annotations

import logging
import os
import platform
import re
import sys
import threading
import time
from dataclasses import dataclass
from functools import wraps
from typing import Callable

from openjobio_adaptor_runtime import AdaptorDataValidators
from openjobio_adaptor_runtime_client import Action
from openjobio_adaptor_runtime import (
    Adaptor,
    AdaptorConfiguration,
    LoggingSubprocess,
    RegexCallback,
    RegexHandler,
)
from openjobio_adaptor_runtime.adaptors.adaptor_ipc import ActionsQueue, AdaptorServer

_logger = logging.getLogger(__name__)


class BlenderNotRunningError(Exception):
    """Error that is raised when attempting to use Blender while it is not running"""

    pass


@dataclass(frozen=True)
class ActionItem:
    name: str
    requires_path_mapping: bool = False


_FIRST_RUN_ACTIONS = [ActionItem("scene")]
_BLENDER_RUN_KEYS = {
    ActionItem("layer"),
    ActionItem("animation"),
    ActionItem("output_path", requires_path_mapping=True),
}

# Only capture the major minor group (ie. 3.3)
# patch version (ie .3) is a optional non-capturing subgroup.
_MAJOR_MINOR_RE = re.compile(r"^(\d+\.\d+)(\.\d+)?$")


def _check_for_exception(func: Callable) -> Callable:
    """
    Decorator that checks if an exception has been caught before calling the
    decorated function
    """

    @wraps(func)
    def wrapped_func(self, *args, **kwargs):
        if not self._has_exception:  # Raises if there is an exception  # pragma: no branch
            return func(self, *args, **kwargs)

    return wrapped_func


class BlenderAdaptor(Adaptor[AdaptorConfiguration]):
    """
    Adaptor that creates a session in Blender to Render interactively.
    """

    _SERVER_START_TIMEOUT_SECONDS = 30
    _SERVER_END_TIMEOUT_SECONDS = 30
    _BLENDER_START_TIMEOUT_SECONDS = 300
    _BLENDER_END_TIMEOUT_SECONDS = 30

    _server: AdaptorServer | None = None
    _server_thread: threading.Thread | None = None
    _blender_client: LoggingSubprocess | None = None
    _action_queue = ActionsQueue()
    _is_rendering: bool = False
    # If a thread raises an exception we will update this to raise in the main thread
    _exc_info: Exception | None = None
    _performing_cleanup = False
    _regex_callbacks: list | None = None
    _validators: AdaptorDataValidators | None = None

    # Variables used for keeping track of produced outputs for progress reporting.
    # Will be optionally changed after the scene is set.
    _expected_outputs: int = 0  # Total number of renders to perform.
    _produced_outputs: int = 0  # Counter for tracking number of complete renders.

    @staticmethod
    def _get_timer(timeout: int | float) -> Callable[[], bool]:
        """
        Given a timeout length, returns a lambda which returns True until the timeout occurs.

        Args:
            timeout (int): The amount of time (in seconds) to wait before timing out.
        """
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
        """Property which indicates that the blender client is running

        Returns:
            bool: True if the blender client is running, false otherwise
        """
        return self._blender_client is not None and self._blender_client.is_running

    @property
    def _blender_is_rendering(self) -> bool:
        """Property which indicates if blender is rendering

        Returns:
            bool: True if blender is rendering, false otherwise
        """
        return self._blender_is_running and self._is_rendering

    @_blender_is_rendering.setter
    def _blender_is_rendering(self, value: bool) -> None:
        """Property setter which updates the private _is_rendering boolean.

        Args:
            value (bool): A boolean indicating if blender is rendering.
        """
        self._is_rendering = value

    def _wait_for_socket(self) -> str:
        """
        Performs a busy wait for the socket path that the adaptor server is running on, then
        returns it.

        Raises:
            RuntimeError: If the server does not finish initializing

        Returns:
            str: The socket path the adaptor server is running on.
        """
        is_not_timed_out = self._get_timer(self._SERVER_START_TIMEOUT_SECONDS)
        while (self._server is None or self._server.socket_path is None) and is_not_timed_out():
            time.sleep(0.01)

        if self._server is not None and self._server.socket_path is not None:
            return self._server.socket_path

        raise RuntimeError(
            "Could not find a socket path because the server did not finish initializing"
        )

    def _start_blender_server(self) -> None:
        """
        Starts a server with the given ActionsQueue, attaches the server to the adaptor and serves
        forever in a blocking call.
        """
        self._server = AdaptorServer(self._action_queue, self)
        self._server.serve_forever()

    def _start_blender_server_thread(self) -> None:
        """
        Starts the blender adaptor server in a thread.
        Sets the environment variable "BLENDER_ADAPTOR_SOCKET_PATH" to
        the socket the server is running
        on after the server has finished starting.
        """
        self._server_thread = threading.Thread(
            target=self._start_blender_server, name="BlenderAdaptorServerThread"
        )
        self._server_thread.start()
        os.environ["BLENDER_ADAPTOR_SOCKET_PATH"] = self._wait_for_socket()

    @property
    def validators(self) -> AdaptorDataValidators:
        if not self._validators:
            cur_dir = os.path.dirname(__file__)
            schema_dir = os.path.join(cur_dir, "schemas")
            self._validators = AdaptorDataValidators.for_adaptor(schema_dir)
        return self._validators

    def _get_regex_callbacks(self) -> list[RegexCallback]:
        """
        Returns a list of RegexCallbacks used by the Blender Adaptor

        Returns:
            list[RegexCallback]: List of Regex Callbacks to add
        """

        callback_list = []
        completed_regexes = [re.compile(".+ Finished")]
        progress_regexes = [re.compile(".+ Sample ([0-9]+)/([0-9]+)")]
        error_regexes = [re.compile(".*Error:.*|.*Exception:.*|.+ error: .+")]

        callback_list.append(RegexCallback(completed_regexes, self._handle_complete))
        callback_list.append(RegexCallback(progress_regexes, self._handle_progress))
        callback_list.append(
            RegexCallback(
                [re.compile("BlenderAdaptor Configuration: Performing ([0-9]+) renders.")],
                self._handle_set_expected_outputs,
            )
        )
        if self.init_data.get("strict_error_checking", False):
            callback_list.append(RegexCallback(error_regexes, self._handle_error))

        return callback_list

    @_check_for_exception
    def _handle_complete(self, match: re.Match) -> None:
        """
        Callback for stdout that indicate completeness of a render. Updates progress to 100
        Args:
            match (re.Match): The match object from the regex pattern that was matched in the
                              message.
        """
        self._produced_outputs += 1
        assert self._produced_outputs <= self._expected_outputs
        if self._produced_outputs == self._expected_outputs:
            self._blender_is_rendering = False
            self.update_status(progress=100)

    @_check_for_exception
    def _handle_progress(self, match: re.Match) -> None:
        """
        Callback for stdout that indicate progress of a render.
        Args:
            match (re.Match): The match object from the regex pattern that was matched in the
                              message.
        """
        numerator = float(
            (int(match.groups()[0]) / int(match.groups()[1])) + self._produced_outputs
        )
        denominator = self._expected_outputs
        progress = numerator / denominator * 100
        self.update_status(progress=progress)

    @_check_for_exception
    def _handle_set_expected_outputs(self, match: re.Match) -> None:
        """
        Set the `_expected_outputs` value to indicate the number of renders that will be performed.
        Used for proper progress reporting since Blender does not provide overall progress when
        doing multiple renders.
        Args:
            match (re.Match): The match object from the regex pattern that was matched in the
                              message.
        """
        self._expected_outputs = int(match.groups()[0])

    def _handle_error(self, match: re.Match) -> None:
        """
        Callback for stdout that indicates an error or warning.
        Args:
            match (re.Match): The match object from the regex pattern that was matched in the
                              message

        Raises:
            RuntimeError: Always raises a runtime error to halt the adaptor.
        """
        self._exc_info = RuntimeError(f"Blender Encountered an Error: {match.group(0)}")

    def _get_blender_client_path(self) -> str:
        """
        Obtains the blender_client.py path by searching directories in sys.path

        Raises:
            FileNotFoundError: If the blender_client.py file could not be found.

        Returns:
            str: The path to the blender_client.py file.
        """
        for dir_ in sys.path:
            path = os.path.join(
                dir_, "deadline_adaptor_for_blender", "BlenderClient", "blender_client.py"
            )
            if os.path.isfile(path):
                return path
        raise FileNotFoundError(
            "Could not find blender_client.py. Check that the "
            "BlenderClient package is in one of the "
            f"following directories: {sys.path[1:]}"
        )

    def _add_site_packages_to_pythonpath(self) -> None:
        """
        Blender does not include the site-packages directory containing the WorkerAdaptorRuntime in
        its sys.path. As the WorkerAdaptorRuntime site-package dir contains the IPC code we add it
        to the PYTHONPATH so Blender can import the IPC code.
        """
        site_package_dir = os.path.dirname(os.path.dirname(__file__))
        os.environ["PYTHONPATH"] = f"{os.getenv('PYTHONPATH', '')}{os.pathsep}{site_package_dir}"

    def _start_blender_client(self, blender_version: str) -> None:
        """
        Starts the blender client by launching Blender with the blender_client.py file.

        Args:
            blender_version (str): The version of Blender that we are launching.

        Raises:
            FileNotFoundError: If the blender_client.py file or the project file could not be found.
        """
        exe_path = self.config.get_executable_path(platform.system(), blender_version)
        blender_client_path = self._get_blender_client_path()
        regexhandler = RegexHandler(self._get_regex_callbacks())
        self._add_site_packages_to_pythonpath()

        project_file = self.init_data["project_file"]
        mapped_project_path = self.map_path(project_file)
        if not os.path.isfile(mapped_project_path):
            raise FileNotFoundError(f"Could not find project file at '{mapped_project_path}'")

        self._blender_client = LoggingSubprocess(
            args=[exe_path, "--background", mapped_project_path, "--python", blender_client_path],
            stdout_handler=regexhandler,
            stderr_handler=regexhandler,
        )

    @staticmethod
    def _get_major_minor_version(blender_version: str) -> str:
        """Grab the major minor information from the Blender version string.

        We may receive the whole version (ie. 3.3.4) or just the major minor
        version (ie. 3.3) from init_data. This function should handle both cases.

        Args:
            blender_version (str): The blender version passed with the init_data object

        Returns:
            str: The MAJOR.MINOR version of Blender
        """
        major_minor = blender_version
        match = _MAJOR_MINOR_RE.match(blender_version)
        if match:
            major_minor = match.group(1)
            _logger.info(f"Using {major_minor} to find Blender executable")
        else:
            _logger.warning(
                f"Could not find major.minor information from '{blender_version}', "
                f"using '{blender_version}' to find the Blender executable"
            )

        return major_minor

    def _action_from_action_item(self, item: ActionItem, data: dict) -> Action:
        """
        Return an Action object from an ActionItem object. Applies pathmapping if necessary.

        Args:
            item (ActionItem): The ActionItem to convert to an Action
            data (dict): The data dict to provide with the action

        Returns:
            Action: An Action object
        """
        value = data.get(item.name, "")
        # If item requires pathmapping and it is not a Blender relative path:
        if item.requires_path_mapping and not value.startswith("//"):
            value = self.map_path(value)

        return Action(item.name, {item.name: value})

    def on_start(self) -> None:
        """
        For job stickiness. Will start everything required for the Task. Will be used for all
        SubTasks.

        Raises:
            jsonschema.ValidationError: When init_data fails validation against the adaptor schema.
            jsonschema.SchemaError: When the adaptor schema itself is nonvalid.
            RuntimeError: If Blender did not complete initialization actions due to an exception
            TimeoutError: If Blender did not complete initialization actions due to timing out.
            FileNotFoundError: If the blender_client.py file could not be found.
            KeyError: If a configuration for the given platform and version does not exist.
        """
        self.validators.init_data.validate(self.init_data)

        self.update_status(progress=0, status_message="Initializing Blender")

        self._start_blender_server_thread()
        # Set up the render handler
        self._action_queue.enqueue_action(
            Action("renderer", {"renderer": self.init_data.get("renderer")})
        )

        # Resolve assets by applying pathmapping rules
        self._action_queue.enqueue_action(
            Action(
                "resolve_assets",
                {"strict_error_checking": self.init_data.get("strict_error_checking", False)},
            )
        )

        version = str(self.init_data.get("version"))
        version = self._get_major_minor_version(version)
        self._start_blender_client(version)

        is_not_timed_out = self._get_timer(self._BLENDER_START_TIMEOUT_SECONDS)
        while (
            self._blender_is_running
            and not self._has_exception
            and len(self._action_queue) > 0
            and is_not_timed_out()
        ):
            time.sleep(0.1)  # busy wait for blender to finish initialization

        if len(self._action_queue) > 0:
            if is_not_timed_out():
                raise RuntimeError(
                    "Blender encountered an error and was not "
                    "able to complete initialization actions."
                )
            else:
                raise TimeoutError(
                    "Blender did not complete initialization actions in "
                    f"{self._BLENDER_START_TIMEOUT_SECONDS} seconds and failed to start."
                )

    def on_run(self, run_data: dict) -> None:
        """
        This starts a render in Blender for the given frame, scene and layer(s) and
        performs a busy wait until the render completes.
        """
        if not self._blender_is_running:
            raise BlenderNotRunningError("Cannot render because Blender is not running.")

        self.validators.run_data.validate(run_data)
        self._produced_outputs = 0
        self._expected_outputs = 1
        self._is_rendering = True

        for action_item in _FIRST_RUN_ACTIONS:
            self._action_queue.enqueue_action(
                self._action_from_action_item(
                    action_item, {action_item.name: run_data[action_item.name]}
                )
            )

        for action_item in _BLENDER_RUN_KEYS:
            if action_item.name in run_data:
                self._action_queue.enqueue_action(
                    self._action_from_action_item(
                        action_item, {action_item.name: run_data[action_item.name]}
                    )
                )

        self._action_queue.enqueue_action(Action("start_render", {"frame": run_data["frame"]}))
        while self._blender_is_rendering and not self._has_exception:
            time.sleep(0.1)  # busy wait so that on_cleanup is not called

        if not self._blender_is_running and self._blender_client:  # Client will always exist here.
            #  This is always an error case because the Blender Client should still be running and
            #  waiting for the next command. If the thread finished, then we cannot continue
            exit_code = self._blender_client.returncode
            raise BlenderNotRunningError(
                "Blender exited early and did not render successfully, please check render logs. "
                f"Exit code {exit_code}"
            )

    def on_end(self) -> None:
        """
        No action needed but this function must be implemented
        """
        return

    def on_cleanup(self):
        """
        Cleans up the adaptor by closing the Blender client and adaptor server.
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

        self._blender_client.terminate(grace_time_s=0)
