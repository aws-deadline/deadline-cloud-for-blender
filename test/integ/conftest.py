# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

import pytest
import os
import re
import shutil
import subprocess
import sys

from pathlib import Path


_BLENDER_VERSION_RE = re.compile(r"^Blender (?P<version>\d+\.\d+)\..*$")


@pytest.fixture
def blender_location() -> Path:
    # If BLENDER_EXECUTABLE is set, always use it
    location = os.environ.get("BLENDER_EXECUTABLE")
    if location:
        return Path(location)

    # If BLENDER_VERSION is set, use platform-specific path
    blender_version_env = os.environ.get("BLENDER_VERSION")
    if blender_version_env:
        if os.name == "nt":
            location = f"C:\\Tools\\blender-{blender_version_env}-windows-x64\\blender.exe"
            if os.path.exists(location):
                return Path(location)
        elif sys.platform == "darwin":
            location = f"/Applications/Blender-{blender_version_env}.app/Contents/MacOS/Blender"
            if os.path.exists(location):
                return Path(location)
        else:  # Linux
            location = f"/opt/blender-{blender_version_env}-linux-x64/blender"
            if os.path.exists(location):
                return Path(location)

    # If Blender is in the PATH, use that
    location = shutil.which("blender")
    if location:
        return Path(location)

    # On Windows and MacOS, look for Blender in the default install location
    if os.name == "nt":
        for version in ("5.1", "5.0", "4.5", "4.4", "4.3", "4.2", "4.1", "4.0", "3.6"):
            location = os.path.join(
                os.environ["ProgramFiles"],
                "Blender Foundation",
                f"Blender {version}",
                "blender.exe",
            )
            if os.path.exists(location):
                return Path(location)
    elif sys.platform == "darwin":
        location = "/Applications/Blender.app/Contents/MacOS/Blender"
        if os.path.exists(location):
            return Path(location)

    raise RuntimeError(
        "Blender could not be found, set the BLENDER_EXECUTABLE environment variable to fix this."
    )


@pytest.fixture
def blender_version(blender_location) -> str:
    cmd = [str(blender_location), "--version"]
    result = subprocess.run(
        cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
    )
    first_line = result.stdout.splitlines()[0]
    match = _BLENDER_VERSION_RE.match(first_line)
    if not match:
        raise RuntimeError(f"Could not parse Blender version from {first_line}")
    version = match.group("version")

    env_version = os.environ.get("BLENDER_VERSION")
    if env_version:
        # Compare only major.minor (e.g., "4.5" from "4.5.4")
        env_version_short = ".".join(env_version.split(".")[:2])
        assert version == env_version_short, (
            f"BLENDER_VERSION env var ({env_version}) does not match "
            f"blender --version output ({version})"
        )

    return version


@pytest.fixture
def script_location() -> Path:
    return Path(__file__).parent / "test_scripts"
