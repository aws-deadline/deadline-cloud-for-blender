# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
import os
import subprocess
import time
from pathlib import Path
import platform

import pytest


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
        path = path.format(platform="linux-x64", ext="run")

    if not os.path.isfile(path):
        raise FileNotFoundError(f"Installer not found at '{path}'")

    if not os.access(path, os.X_OK) and not platform.system() == "Darwin":
        raise PermissionError(f"Installer at '{path}' is not executable")

    yield Path(path).absolute()


@pytest.fixture(scope="function")
def installed(installer_path, tmp_path):
    args = [
        installer_path,
        "--mode",
        "unattended",
        "--installscope",
        "user",
        "--prefix",
        tmp_path,
        "--enable-components",
        "deadline_cloud_for_blender",
    ]
    result = subprocess.run(args, check=True)
    assert result.returncode == 0

    yield Path(tmp_path)


def test_install(installed: Path):
    # GIVEN / WHEN
    if platform.system() == "Darwin":
        uninstaller = "uninstall.app"
    elif platform.system() == "Windows":
        uninstaller = "uninstall.exe"
    else:
        uninstaller = "uninstall"
    python_dir = installed / "python"

    # THEN
    top_level_dir = [f.name for f in installed.iterdir()]
    assert python_dir.name in top_level_dir
    assert "installer_version.txt" in top_level_dir
    assert uninstaller in top_level_dir

    # Just check that we have dependencies in this folder
    module_dir = [f.name for f in (python_dir / "modules").iterdir()]
    assert "deadline" in module_dir
    assert "qtpy" in module_dir

    # Check the blender module is here and there's a version file
    addon_dir = [
        f.name for f in (python_dir / "addons" / "deadline_cloud_blender_submitter").iterdir()
    ]
    assert "_version.py" in addon_dir


def test_uninstall(installed: Path):
    # GIVEN
    if platform.system() == "Darwin":
        uninstaller_path = os.path.join(
            installed, "uninstall.app", "Contents", "MacOS", "installbuilder.sh"
        )
    elif platform.system() == "Windows":
        uninstaller_path = os.path.join(installed, "uninstall.exe")
    else:
        uninstaller_path = os.path.join(installed, "uninstall")

    # WHEN
    result = subprocess.run([uninstaller_path, "--mode", "unattended"], check=True)

    # THEN
    assert result.returncode == 0

    # The uninstall process will return before the uninstallation is complete.
    # If necessary, wait for up to one minute before timing out.
    for _ in range(6):
        if not installed.exists():
            break
        time.sleep(10)
    assert not installed.exists()
