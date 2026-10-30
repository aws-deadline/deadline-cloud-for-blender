# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

"""GUI test for the Blender submitter.

Launches real (non-background) Blender with this repo's submitter add-on, opens the submitter
dialog through its Blender operator, uses xa11y to drive the Qt dialog, and submits a job to an
in-process mock Deadline Cloud backend (plus moto for S3 job attachments).

Adapted from aws-deadline/deadline-cloud test/blender_submitter_ui/test_blender_submitter_ui.py.
The difference is that Blender loads the add-on and deadline.blender_submitter from this repo's
src/, so the test covers the revision under test rather than the latest PyPI release.

Requirements: a GUI session that exposes accessibility (Xvfb + AT-SPI on Linux, the
Accessibility permission on macOS), Blender at BLENDER_EXECUTABLE, and a test Python whose
major.minor matches Blender's bundled Python. See DEVELOPMENT.md.
"""

from __future__ import annotations

import os
import platform
import shutil
import subprocess
import sys
import sysconfig
import time
from pathlib import Path
from typing import IO, Any, Iterator

import boto3
import pytest
import xa11y
import yaml
from moto.server import ThreadedMotoServer
from openjd.model import (
    ParameterValue,
    ParameterValueType,
    UnsupportedSchema,
    create_job,
    decode_job_template,
)

from .mock_deadline_backend import (
    MockDeadlineBackend,
    _validation_exception,
    route,
    start_server,
)

REGION = "us-west-2"
BUCKET = "blender-integ-test"
ROOT_PREFIX = "DeadlineCloud"
ACCESS_KEY = "testing"
SECRET_KEY = "testing"

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = REPO_ROOT / "src"
ADDONS_DIR = SRC_DIR / "deadline" / "blender_submitter" / "addons"
OPEN_SUBMITTER_SCRIPT = Path(__file__).parent / "open_submitter.py"

STARTUP_TIMEOUT = 30.0
SUBMIT_TIMEOUT = 60.0
FARM_RESOLVE_TIMEOUT = 15.0

IS_WINDOWS = platform.system() == "Windows"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _find_blender() -> Path:
    location = os.environ.get("BLENDER_EXECUTABLE")
    if location:
        return Path(location)
    location = shutil.which("blender")
    if location:
        return Path(location)
    if IS_WINDOWS:
        p = Path(os.environ.get("ProgramFiles", "C:\\Program Files")) / "Blender Foundation"
        if p.exists():
            for d in sorted(p.iterdir(), reverse=True):
                candidate = d / "blender.exe"
                if candidate.exists():
                    return candidate
    elif platform.system() == "Darwin":
        candidate = Path("/Applications/Blender.app/Contents/MacOS/Blender")
        if candidate.exists():
            return candidate
    else:
        opt = Path("/opt")
        if opt.exists():
            for d in sorted(opt.glob("blender-*-linux-x64"), reverse=True):
                candidate = d / "blender"
                if candidate.exists():
                    return candidate
    pytest.fail(
        "Blender not found. Set BLENDER_EXECUTABLE or install Blender to a standard location."
    )


@pytest.fixture(scope="session")
def blender_exe() -> Path:
    exe = _find_blender()
    # Blender imports deadline, PySide6 and the other dependencies from this Python's
    # site-packages, so compiled wheels only load if both Pythons have the same major.minor.
    result = subprocess.run(
        [
            str(exe),
            "--background",
            "--factory-startup",
            "--python-expr",
            "import sys; print('BLENDER_PYTHON=%d.%d' % sys.version_info[:2])",
        ],
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    blender_python = next(
        (
            line.split("=", 1)[1].strip()
            for line in result.stdout.splitlines()
            if line.startswith("BLENDER_PYTHON=")
        ),
        None,
    )
    test_python = f"{sys.version_info.major}.{sys.version_info.minor}"
    if blender_python != test_python:
        pytest.fail(
            f"{exe} bundles Python {blender_python}, but the test runs on Python {test_python}. "
            "Run the test with a Python matching Blender's bundled Python."
        )
    return exe


@pytest.fixture(scope="session")
def artifact_dir(tmp_path_factory) -> Path:
    """Where failure diagnostics go. CI sets GUI_TEST_ARTIFACT_DIR and uploads it."""
    configured = os.environ.get("GUI_TEST_ARTIFACT_DIR")
    path = Path(configured) if configured else tmp_path_factory.mktemp("gui-test-artifacts")
    path.mkdir(parents=True, exist_ok=True)
    return path


@pytest.fixture(scope="session")
def moto_server() -> Iterator[str]:
    # The S3/STS mock has no authentication, so listen on loopback only.
    server = ThreadedMotoServer(ip_address="127.0.0.1", port=0)
    server.start()
    _, port = server.get_host_and_port()
    try:
        yield f"http://127.0.0.1:{port}"
    finally:
        server.stop()


# CreateJob job parameter value types, as sent by the submitter.
_PARAMETER_VALUE_TYPES = {
    "string": ParameterValueType.STRING,
    "int": ParameterValueType.INT,
    "float": ParameterValueType.FLOAT,
    "path": ParameterValueType.PATH,
}


class RecordingDeadlineBackend(MockDeadlineBackend):
    """The mock Deadline Cloud backend, plus a record of every CreateJob request.

    The base mock instantiates each submitted template with no parameter values, which rejects any
    template with required parameters (the Blender one has several). This subclass instantiates it
    with the values CreateJob actually sent, so openjd-model validates the template and the values.
    """

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.create_job_requests: list[dict] = []

    def clear(self) -> None:
        super().clear()
        self.create_job_requests = []

    @route("POST", "/farms/{farmId}/queues/{queueId}/jobs", "CreateJob")
    def create_job(self, **kwargs: Any) -> dict:
        self.create_job_requests.append(kwargs)
        return super().create_job(**kwargs)

    def _parse_template(self, template: str) -> Any:
        request = self.create_job_requests[-1] if self.create_job_requests else {}
        submitted = request.get("parameters") or {}
        try:
            job_template = decode_job_template(
                template=yaml.safe_load(template), supported_extensions=["TASK_CHUNKING"]
            )
            values = {
                name: ParameterValue(type=_PARAMETER_VALUE_TYPES[kind], value=value)
                for name, typed_value in submitted.items()
                for kind, value in typed_value.items()
            }
            return create_job(job_template=job_template, job_parameter_values=values)
        except (yaml.YAMLError, ValueError, UnsupportedSchema, TypeError, KeyError) as e:
            raise _validation_exception(f"Invalid job template or parameters: {e!r}", "CreateJob")


@pytest.fixture(scope="session")
def mock_backend_server() -> Iterator[tuple[RecordingDeadlineBackend, str]]:
    backend = RecordingDeadlineBackend(validate_params=False)
    server, base_url, _ = start_server(backend)
    base_url = base_url.replace("127.0.0.1", "localhost")
    try:
        yield backend, base_url
    finally:
        server.shutdown()
        server.server_close()


@pytest.fixture
def mock_backend(mock_backend_server) -> tuple[RecordingDeadlineBackend, str]:
    backend, base_url = mock_backend_server
    backend.clear()
    return backend, base_url


@pytest.fixture
def s3_client(moto_server):
    return boto3.client(
        "s3",
        endpoint_url=moto_server,
        aws_access_key_id=ACCESS_KEY,
        aws_secret_access_key=SECRET_KEY,
        region_name=REGION,
    )


@pytest.fixture
def blender_env(tmp_path, mock_backend, moto_server, s3_client):
    """Set up env vars, config, farm/queue, and S3 bucket for the Blender subprocess."""
    backend, deadline_url = mock_backend

    farm = backend.create_farm(displayName="TestFarm", description="")
    queue = backend.create_queue(
        farmId=farm["farmId"],
        displayName="TestQueue",
        description="",
        defaultBudgetAction="NONE",
        jobAttachmentSettings={"s3BucketName": BUCKET, "rootPrefix": ROOT_PREFIX},
    )

    try:
        s3_client.create_bucket(
            Bucket=BUCKET,
            CreateBucketConfiguration={"LocationConstraint": REGION},
        )
    except s3_client.exceptions.BucketAlreadyOwnedByYou:
        pass

    config_file = tmp_path / "deadline.config"
    config_file.write_text(
        "[defaults]\n"
        "aws_profile_name = (default)\n"
        "\n"
        "[profile-(default) defaults]\n"
        f"farm_id = {farm['farmId']}\n"
        "\n"
        f"[profile-(default) {farm['farmId']} defaults]\n"
        f"queue_id = {queue['queueId']}\n"
        "\n"
        "[profile-(default) settings]\n"
        f"job_history_dir = {tmp_path / 'job_history'}\n"
        "\n"
        # The submitter checks a remote manifest at startup and, if it advertises a newer
        # version than the installed one, opens a blocking "update available" dialog that
        # nobody dismisses in CI. Turn the notification off so the test exercises the
        # submitter, not the update prompt.
        "[settings]\n"
        "submitter_update_notification = false\n"
    )

    scene_dir = tmp_path / "scene"
    scene_dir.mkdir()
    blender_user_dir = tmp_path / "blender-user"

    # Blender imports packages from PYTHONPATH (--python-use-system-env). Put this repo's
    # src/ and the add-on directory first so the code under test wins over any installed
    # copy, then this Python's site-packages for deadline, PySide6, and the other
    # dependencies. Editable installs don't help here: Blender doesn't process .pth files
    # in PYTHONPATH entries.
    pythonpath = [
        str(p)
        for p in [
            SRC_DIR,
            ADDONS_DIR,
            sysconfig.get_path("purelib"),
            sysconfig.get_path("platlib"),
            os.environ.get("PYTHONPATH"),
        ]
        if p
    ]

    env = {
        # Drop the caller's AWS settings (profile, region, credential files), which would point
        # Blender at real accounts or at profiles that don't exist under the redirected HOME.
        **{k: v for k, v in os.environ.items() if not k.upper().startswith("AWS_")},
        "HOME": str(tmp_path / "home"),
        "USERPROFILE": str(tmp_path / "home"),
        # Keep Blender's own user files out of the developer's profile.
        "BLENDER_USER_CONFIG": str(blender_user_dir / "config"),
        "BLENDER_USER_SCRIPTS": str(blender_user_dir / "scripts"),
        "BLENDER_USER_DATAFILES": str(blender_user_dir / "datafiles"),
        "AWS_ENDPOINT_URL_DEADLINE": deadline_url,
        "AWS_ENDPOINT_URL_S3": moto_server,
        "AWS_ENDPOINT_URL_STS": moto_server,
        "AWS_ACCESS_KEY_ID": ACCESS_KEY,
        "AWS_SECRET_ACCESS_KEY": SECRET_KEY,
        "AWS_DEFAULT_REGION": REGION,
        "DEADLINE_CONFIG_FILE_PATH": str(config_file),
        "DEADLINE_CLOUD_TELEMETRY_OPT_OUT": "true",
        "PYTHONPATH": os.pathsep.join(pythonpath),
        "PYTHONUNBUFFERED": "1",
        "QT_ACCESSIBILITY": "1",
        "QT_LINUX_ACCESSIBILITY_ALWAYS_ON": "1",
    }
    (tmp_path / "home").mkdir(exist_ok=True)

    return {
        "backend": backend,
        "env": env,
        "scene_dir": str(scene_dir),
        "farm_id": farm["farmId"],
        "queue_id": queue["queueId"],
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


# Depth bound for tree-text searches. Caps `app.dump()` traversal so heavy
# trees (Blender's main window) don't blow the test timeout. Submitter dialog
# labels we look for ("Submit", "Deadline", "TestFarm") sit within ~10 levels
# of the root.
_TREE_SEARCH_MAX_DEPTH = 12

# The submitter's own "Scene has unsaved changes." prompt (sanity_checks.py).
_DONT_SAVE_BUTTONS = ("Don't Save", "Don\u2019t Save")


def _list_apps() -> list:
    """List accessible apps, or return [] if the platform accessibility API times out.

    On Windows, UI Automation can time out (PlatformError 0x80131505) while a window in the
    session is busy, for example Blender while it builds the dialog. Every caller polls, so treat
    a timeout as "nothing yet" and let the caller's own timeout decide.
    """
    try:
        return list(xa11y.App.list())
    except xa11y.PlatformError as e:
        print(f"Listing accessible apps failed, will retry: {e}", flush=True)
        return []


def _blender_apps(proc: subprocess.Popen) -> list:
    """The accessible apps owned by the Blender process under test.

    Only these are searched or clicked, so a terminal or editor showing the same text can't be
    mistaken for the dialog, and other apps' prompts are never answered.
    """
    return [a for a in _list_apps() if a.pid == proc.pid]


def _tree_text(app) -> str:
    """The app's accessibility tree as text (names and values), or "" if it can't be read."""
    try:
        return app.dump(max_depth=_TREE_SEARCH_MAX_DEPTH)
    except xa11y.XA11yError:
        return ""


def _press_if_present(app, selector: str) -> bool:
    """Press the first element matching *selector*; False if absent or gone mid-press."""
    try:
        button = app.locator(selector)
        if button.exists():
            button.press()
            return True
    except xa11y.XA11yError as e:
        print(f"Pressing {selector} failed, will retry: {e}", flush=True)
    return False


def _dump_tree(app, out: IO[str], max_depth: int | None = None) -> None:
    """Write the accessibility tree for diagnostics."""
    out.write("\n--- accessibility tree ---\n")
    try:
        out.write(app.dump(max_depth=max_depth))
        out.write("\n")
    except Exception as e:
        out.write(f"<tree error: {e}>\n")
    out.write("--- end tree ---\n")


def _screenshot(path: Path) -> None:
    try:
        xa11y.screenshot().save_png(str(path))
    except Exception as e:
        print(f"screenshot({path.name}) failed: {e}", flush=True)


# ---------------------------------------------------------------------------
# Test
# ---------------------------------------------------------------------------


class TestBlenderSubmitterGUI:
    """Open the Blender submitter dialog, submit a job via xa11y, verify the mock backend."""

    def test_submit_job_via_gui(self, blender_exe, blender_env, artifact_dir):
        backend = blender_env["backend"]
        env = blender_env["env"]
        scene_dir = blender_env["scene_dir"]

        # Launch Blender in the foreground with the submitter script. --factory-startup keeps
        # the developer's preferences, add-ons and startup file out of the test.
        cmd = [
            str(blender_exe),
            "--factory-startup",
            "--python",
            str(OPEN_SUBMITTER_SCRIPT),
            "--python-use-system-env",
            "--python-exit-code",
            "1",
            "--",
            "--output-dir",
            scene_dir,
        ]
        # Send Blender's output to a file rather than an unread pipe, which could fill up and
        # block Blender. The file is printed and kept as an artifact if the test fails.
        blender_log = artifact_dir / "blender.log"
        log_file = blender_log.open("w", encoding="utf-8", errors="replace")
        popen_kwargs: dict = {"env": env, "stdout": log_file, "stderr": subprocess.STDOUT}
        if not IS_WINDOWS:
            popen_kwargs["start_new_session"] = True

        proc = subprocess.Popen(cmd, **popen_kwargs)

        try:
            app = self._wait_for_dialog_app(proc)
            self._wait_farm_resolved(app)

            submit_btn = app.locator('button[name="Submit"]')
            submit_btn.wait_visible(timeout=STARTUP_TIMEOUT)
            submit_btn.press()

            self._wait_submission_complete(proc, backend, artifact_dir)

            # Close the progress dialog.
            for blender_app in _blender_apps(proc):
                for ok_name in ("OK", "Ok"):
                    if _press_if_present(blender_app, f'button[name="{ok_name}"]'):
                        break

            assert (
                len(backend.create_job_requests) == 1
            ), f"Expected 1 CreateJob request, got {len(backend.create_job_requests)}"
            assert len(backend.jobs) == 1, f"Expected 1 job, got {len(backend.jobs)}"
            parameters = backend.create_job_requests[0].get("parameters") or {}
            blender_file = (parameters.get("BlenderFile") or {}).get("path", "")
            assert (
                Path(blender_file).name == "cube.blend"
            ), f"Expected BlenderFile to be the saved cube.blend, got {blender_file!r}"

        except BaseException:
            # Catch BaseException, not Exception: the dialog-wait timeout raises
            # pytest.Failed (a BaseException subclass), so a bare `except Exception`
            # never fires and the failure diagnostics below are skipped.
            _screenshot(artifact_dir / "blender_submitter_failure.png")
            try:
                # Blender's tree in full, and only the names of the other apps: a full dump of
                # every app on a busy desktop can take longer than the job's timeout.
                with (artifact_dir / "accessibility_tree.txt").open("w", encoding="utf-8") as out:
                    for a in _list_apps():
                        if a.pid == proc.pid:
                            out.write(f"--- Blender app: {a.name} (pid {a.pid}) ---\n")
                            _dump_tree(a, out)
                        else:
                            out.write(f"--- other app: {a.name} (pid {a.pid}) ---\n")
            except Exception as e:
                print(f"Could not dump the accessibility trees: {e}", file=sys.stderr)
            raise
        finally:
            if proc.poll() is None:
                proc.terminate()
                try:
                    proc.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait()
            log_file.close()
            sys.stderr.write(f"\n--- Blender output ({blender_log}) ---\n")
            sys.stderr.write(blender_log.read_text(encoding="utf-8", errors="replace"))
            sys.stderr.write("--- end Blender output ---\n")

    def _wait_for_dialog_app(
        self, proc: subprocess.Popen, timeout: float = STARTUP_TIMEOUT
    ) -> xa11y.App:
        """Wait for the submitter dialog to appear in Blender's accessibility tree."""
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            if proc.poll() is not None:
                pytest.fail(
                    f"Blender exited early with code {proc.returncode}. "
                    "Its output is printed below the test failure."
                )
            for app in _blender_apps(proc):
                text = _tree_text(app)
                if "Submit" in text and "Deadline" in text:
                    return app
            time.sleep(0.5)
        apps = ", ".join(f"{a.name} (pid {a.pid})" for a in _list_apps())
        pytest.fail(
            f"Submitter dialog not found in Blender (pid {proc.pid}) within {timeout}s. "
            f"Accessible apps: {apps}"
        )

    def _wait_farm_resolved(self, app: xa11y.App, timeout: float = FARM_RESOLVE_TIMEOUT):
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            if "TestFarm" in _tree_text(app):
                return
            time.sleep(0.5)
        _dump_tree(app, sys.stderr)
        pytest.fail(f"Farm name 'TestFarm' not resolved within {timeout}s")

    def _wait_submission_complete(
        self,
        proc: subprocess.Popen,
        backend: RecordingDeadlineBackend,
        artifact_dir: Path,
        timeout: float = SUBMIT_TIMEOUT,
    ) -> None:
        """Wait for the progress dialog to report "Submission complete", answering prompts.

        A CreateJob request alone isn't success: the submitter must also report completion.
        """
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            if proc.poll() is not None:
                pytest.fail(f"Blender exited with code {proc.returncode} during submission")
            for app in _blender_apps(proc):
                text = _tree_text(app)
                if "Submission complete" in text:
                    return
                # "Error occurred:" is what the progress dialog's log shows when a request
                # such as CreateJob raises; the other two are its status label on failure.
                for failed in ("Error occurred:", "Submission error", "Submission canceled"):
                    if failed in text:
                        _screenshot(artifact_dir / "submission_error.png")
                        _dump_tree(app, sys.stderr)
                        pytest.fail(
                            f"Submission failed with status {failed!r}. "
                            f"CreateJob requests: {backend.create_job_requests}"
                        )
                if "Scene has unsaved changes" in text:
                    for name in _DONT_SAVE_BUTTONS:
                        if _press_if_present(app, f'button[name="{name}"]'):
                            break
                if "Job Submission Confirmation" in text:
                    _press_if_present(app, 'button[name="OK"]')
            time.sleep(0.5)
        _screenshot(artifact_dir / "submission_timeout.png")
        for app in _blender_apps(proc):
            _dump_tree(app, sys.stderr)
        pytest.fail(
            f"Submission did not complete within {timeout}s. Backend calls: {backend.call_counts}"
        )
