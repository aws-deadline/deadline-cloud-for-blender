# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

import pytest
import os
import shutil
import sys

from pathlib import Path


@pytest.fixture
def blender_location() -> Path:
    # If BLENDER_EXECUTABLE is set, always use it
    location = os.environ.get("BLENDER_EXECUTABLE")
    if location:
        return Path(location)

    # If Blender is in the PATH, use that
    location = shutil.which("blender")
    if location:
        return Path(location)

    # On Windows and MacOS, look for Blender in the default install location
    if os.name == "nt":
        for version in ("4.4", "4.3", "4.2", "3.6"):
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
def script_location() -> Path:
    return Path(__file__).parent / "test_scripts"
