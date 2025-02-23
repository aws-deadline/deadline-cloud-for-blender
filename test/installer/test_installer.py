# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
import os
import subprocess
from pathlib import Path
import platform

import pytest


@pytest.fixture(scope="session")
def installer_path():
    path = os.getenv("INSTALLER_PATH")
    if not path:
        pytest.skip("INSTALLER_PATH environment variable is not set")

    if platform.system() == "Darwin" and Path(path).suffix == ".app":
        path = os.path.join(path, "Contents", "MacOS", "installbuilder.sh")

    if not os.path.isfile(path):
        raise FileNotFoundError(f"Installer not found at '{path}'")

    if not os.access(path, os.X_OK) and not platform.system() == "Darwin":
        raise PermissionError(f"Installer at '{path}' is not executable")

    yield path


@pytest.fixture(scope="function")
def installed(installer_path, tmpdir):
    args = [
        installer_path,
        "--mode",
        "unattended",
        "--installscope",
        "user",
        "--prefix",
        tmpdir,
        "--enable-components",
        "deadline_cloud_for_blender",
    ]
    result = subprocess.run(args, check=True)
    assert result.returncode == 0

    yield Path(tmpdir)


def test_install(installed: Path):
    # GIVEN / WHEN
    uninstaller = "uninstall.app" if platform.system() == "Darwin" else "uninstall"
    python_dir = installed / "Submitters" / "Blender" / "python"

    # THEN
    top_level_dir = [f.name for f in installed.iterdir()]
    assert "Submitters" in top_level_dir
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
    uninstaller_path = os.path.join(installed, "uninstall")
    if platform.system() == "Darwin":
        uninstaller_path = os.path.join(
            installed, "uninstall.app", "Contents", "MacOS", "installbuilder.sh"
        )

    # WHEN
    result = subprocess.run([uninstaller_path, "--mode", "unattended"], check=True)

    # THEN
    assert result.returncode == 0
    assert not os.path.exists(installed)
