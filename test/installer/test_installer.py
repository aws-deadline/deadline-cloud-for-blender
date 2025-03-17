# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
from collections import defaultdict
import getpass
import os
from pathlib import Path
import re
import stat
import subprocess
import platform

import pytest


def _is_admin() -> bool:
    if platform.system() != "Windows":
        return os.getuid() == 0

    import ctypes

    try:
        return ctypes.windll.shell32.IsUserAnAdmin() == 1
    except Exception:
        return False


@pytest.fixture(scope="session")
def installer_path():
    path = "DeadlineCloudForBlenderSubmitter-{platform}-installer.{ext}"

    if platform.system() == "Darwin":
        path = os.path.join(
            path.format(platform="osx", ext="app"),
            "Contents",
            "MacOS",
            "installbuilder.sh",
        )
    elif platform.system() == "Windows":
        path = path.format(platform="windows-x64", ext="exe")
    elif platform.system() == "Linux":
        path = path.format(platform="linux", ext="run")

    if not os.path.isfile(path):
        raise FileNotFoundError(f"Installer not found at '{path}'")

    if not os.access(path, os.X_OK) and not platform.system() == "Darwin":
        raise PermissionError(f"Installer at '{path}' is not executable")

    yield Path(path).absolute()


def _run_installer(installer_path, install_scope, installation_path) -> Path:
    args = [
        installer_path,
        "--mode",
        "unattended",
        "--installscope",
        install_scope,
        "--prefix",
        installation_path,
        "--enable-components",
        "deadline_cloud_for_blender",
    ]
    result = subprocess.run(args, check=True)
    assert result.returncode == 0

    return Path(installation_path)


def _validate_files(installation_path: Path) -> None:
    if platform.system() == "Darwin":
        uninstaller = "uninstall.app"
    elif platform.system() == "Windows":
        uninstaller = "uninstall.exe"
    else:
        uninstaller = "uninstall"
    python_dir = installation_path / "python"

    # THEN
    top_level_dir = [f.name for f in installation_path.iterdir()]
    assert "python" in top_level_dir
    assert "installer_version.txt" in top_level_dir
    assert uninstaller in top_level_dir

    # Just check that we have dependencies in this folder
    module_dir = [f.name for f in (python_dir / "modules").iterdir()]
    assert "deadline" in module_dir
    assert "qtpy" in module_dir
    assert "xxhash" in module_dir

    # Check the blender module is here and there's a version file
    addon_dir = [
        f.name for f in (python_dir / "addons" / "deadline_cloud_blender_submitter").iterdir()
    ]
    assert "_version.py" in addon_dir


def _has_group_other_write(mode: int) -> bool:
    return bool(mode & (stat.S_IWGRP | stat.S_IWOTH))


def _has_user_read_write(mode: int) -> bool:
    return bool(mode & (stat.S_IRUSR | stat.S_IWUSR))


def _has_user_group_other_execute(mode: int) -> bool:
    return bool(mode & (stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH))


def _validate_posix_permissions(installation_path: Path):
    # GIVEN
    current_user = getpass.getuser()

    # WHEN
    bad_perms: defaultdict[Path, list[str]] = defaultdict(list)
    for entry in [installation_path, *installation_path.rglob("*")]:
        mode = stat.S_IMODE(entry.stat().st_mode)
        if _has_group_other_write(mode):
            bad_perms[entry].append("should not have group/other write permissions")
        if not _has_user_read_write(mode):
            bad_perms[entry].append("should have user read/write permissions")
        if entry.is_dir() and not _has_user_group_other_execute(mode):
            bad_perms[entry].append("is a directory and should have execute permissions")
        if entry.owner() != current_user:
            bad_perms[entry].append(f"is not owned by the '{current_user}'")

    error_message = [f"Found {len(bad_perms)} instance(s) of incorrect permissions"]
    for i, entry in enumerate(bad_perms):
        fmted_reasons = "\n  - ".join(reason for reason in bad_perms[entry])
        error_message.append(
            f"{i+1}. ({stat.S_IMODE(entry.stat().st_mode):o}) '{str(Path(*entry.parts[len(user_installation.parts):])):>3}'\n"
            f"  - {fmted_reasons}"
        )

    # THEN
    assert len(bad_perms) == 0, "\n".join(error_message)


def _validate_windows_permissions(installation_path: Path):
    # GIVEN
    current_user = getpass.getuser()

    # WHEN

    # THEN
    assert False


@pytest.fixture(scope="session")
def user_installation(installer_path, tmp_path_factory):
    """Used for tests that just want to assert some facts around the install but do not modify"""
    tmp_path = tmp_path_factory.mktemp("install")
    yield _run_installer(installer_path, "user", tmp_path)


@pytest.fixture(scope="session")
def system_installation(installer_path, tmp_path_factory):
    """Used for tests that just want to assert some facts around the install but do not modify"""
    tmp_path = tmp_path_factory.mktemp("install")
    yield _run_installer(installer_path, "system", tmp_path)


@pytest.fixture(scope="function")
def per_test_user_installation(installer_path, tmp_path):
    """Used for tests that modify the installation"""
    yield _run_installer(installer_path, "user", tmp_path)


@pytest.fixture(scope="function")
def per_test_system_installation(installer_path, tmp_path):
    """Used for tests that modify the installation"""
    yield _run_installer(installer_path, "system", tmp_path)


@pytest.fixture(scope="function")
def uninstaller_path():
    uninstaller_path = Path("uninstall")
    if platform.system() == "Darwin":
        uninstaller_path = Path("uninstall.app", "Contents", "MacOS", "installbuilder.sh")
    elif platform.system() == "Windows":
        uninstaller_path = uninstaller_path.with_suffix("exe")

    yield uninstaller_path


def test_default_location(installer_path: Path):
    """Ensures that the default output location reported by the installer is accurate.
       The help text will only show it for the default scope (user). Example help output:

    --prefix <prefix>                           Installation Directory
                                                Default: /home/<user>/DeadlineCloudForBlenderSubmitter
    """
    # GIVEN
    default_install_location = Path("~/DeadlineCloudForBlenderSubmitter").expanduser()
    default_pattern = r"Default: (.*)"
    location = ""

    # WHEN
    help_result = subprocess.run(
        [installer_path, "--mode", "text", "--help"], check=True, capture_output=True
    )

    # THEN
    assert help_result.returncode == 0

    help_output = iter(help_result.stdout.decode("utf-8").splitlines())
    while (line := next(help_output, None)) is not None:
        if line.strip().startswith("--prefix"):
            location = re.match(default_pattern, next(help_output, "").strip(), flags=re.IGNORECASE)
            break

    assert (
        location
    ), f"Could not find default install location in help output:\n{help_result.stdout.decode('utf-8')}"
    if platform.system() != "Windows":
        assert location.group(1) == default_install_location.as_posix()
    else:
        assert location.group(1) == str(default_install_location())


def test_does_not_use_evaluation_mode(installer_path: Path, tmp_path: Path):
    """Ensure the installer is not built with the evaluation mode of the installer software"""
    # GIVEN
    eval_text = r"Created with an evaluation version of InstallBuilder"

    # WHEN
    result = subprocess.run(
        [installer_path, "--mode", "text", "--prefix", tmp_path], check=True, capture_output=True
    )

    # THEN
    assert eval_text not in result.stdout.decode("utf-8")


@pytest.mark.skipif(platform.system() != "Darwin", reason="Only run on macOS")
class TestMacOS:

    def test_user_permissions(self, user_installation: Path):
        # GIVEN / WHEN / THEN
        _validate_posix_permissions(user_installation)

    @pytest.mark.skipif(not _is_admin(), reason="Tests requires admin privileges")
    def test_system_permissions(self, system_installation):
        # GIVEN / WHEN / THEN
        _validate_posix_permissions(system_installation)


@pytest.mark.skipif(platform.system() != "Linux", reason="Only run on Linux")
class TestLinux:
    def test_user_permissions(self, user_installation):
        # GIVEN / WHEN / THEN
        _validate_posix_permissions(user_installation)

    @pytest.mark.skipif(not _is_admin(), reason="Tests requires admin privileges")
    def test_system_permissions(self, system_installation):
        # GIVEN / WHEN / THEN
        _validate_posix_permissions(system_installation)


@pytest.mark.skipif(platform.system() != "Windows", reason="Only run on Windows")
class TestWindows:
    def test_user_permissions(self, user_installation):
        # GIVEN / WHEN / THEN
        _validate_windows_permissions(user_installation)

    @pytest.mark.skipif(not _is_admin(), reason="Tests requires admin privileges")
    def test_system_permissions(self, system_installation):
        # GIVEN / WHEN / THEN
        _validate_windows_permissions(system_installation)


class TestUserInstall:

    def test_install(self, user_installation: Path):
        # GIVEN / WHEN / THEN
        _validate_files(user_installation)

    def test_uninstall(self, per_test_user_installation: Path, uninstaller_path: Path):
        # GIVEN / WHEN
        result = subprocess.run(
            [per_test_user_installation / uninstaller_path, "--mode", "unattended"], check=True
        )

        # THEN
        assert result.returncode == 0
        assert not per_test_user_installation.exists()

        # The uninstall process will return before the uninstallation is complete.
        # If necessary, wait for up to one minute before timing out.
        # for _ in range(6):
        #     if not per_test_user_installation.exists():
        #         break
        #     time.sleep(10)


@pytest.mark.skipif(not _is_admin(), reason="Tests requires admin privileges")
class TestSystemInstall:

    def test_install(self, system_installation: Path):
        # GIVEN / WHEN / THEN
        _validate_files(system_installation)

    def test_uninstall(self, per_test_system_installation: Path, uninstaller_path: Path):
        # GIVEN / WHEN
        result = subprocess.run(
            [per_test_system_installation / uninstaller_path, "--mode", "unattended"],
            capture_output=True,
            check=True,
        )

        # THEN
        assert result.returncode == 0

        # The uninstall process will return before the uninstallation is complete.
        # If necessary, wait for up to one minute before timing out.
        # for _ in range(6):
        #     if not per_test_system_installation.exists():
        #         break
        #     time.sleep(10)
        assert not per_test_system_installation.exists()
