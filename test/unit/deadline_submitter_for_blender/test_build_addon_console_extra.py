# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

"""Guards the Blender extension's dependency channel for AWS Console sign-in.

scripts/build_addon.py pulls the `deadline` requirement out of pyproject.toml's raw text and
feeds it to `pip download` for the extension's wheels/ directory -- a separate channel from
scripts/depsBundle.py's dependency bundle for the desktop submitter. Nothing ties the two
together, so a rewrite of one that is not mirrored in the other silently drops awscrt from
whichever channel was missed, and console sign-in breaks only there.
"""

import sys
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).parents[3] / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    # Appended rather than prepended: scripts/ holds generically named modules (common.py),
    # and prepending would shadow any same-named import for the rest of the pytest session.
    sys.path.append(str(SCRIPTS_DIR))

from build_addon import _get_deadline_requirement  # importable only after the sys.path append


def test_get_deadline_requirement_adds_the_console_extra():
    """The regression this test exists for: before this fix, the extracted requirement had no
    console extra, so the extension's wheels/ directory had no awscrt in it.
    """
    pyproject_contents = """
dependencies = [
    "deadline >= 0.60.4,< 0.61",
    "openjd-adaptor-runtime >= 0.7,< 0.10",
]

[project.optional-dependencies]
gui = [
    "deadline[gui,console] >= 0.60.4,< 0.61",
]
"""
    assert _get_deadline_requirement(pyproject_contents) == "deadline[console] >= 0.60.4,< 0.61"


def test_get_deadline_requirement_reads_the_base_line_not_the_gui_extra():
    """Pins the pre-existing regex behavior this function wraps: it matches the FIRST quoted
    `"deadline..."` line in the file, which is project.dependencies' unadorned entry -- not the
    `gui` extra's `deadline[gui,console]` line further down. If pyproject.toml is ever
    reordered so `gui` comes first, this documents the assumption in play, rather than letting
    the extraction silently start reading a different line.
    """
    pyproject_contents = """
dependencies = [
    "deadline >= 0.60.4,< 0.61",
]
"""
    assert _get_deadline_requirement(pyproject_contents) == "deadline[console] >= 0.60.4,< 0.61"


def test_get_deadline_requirement_raises_when_no_deadline_line_is_found():
    with pytest.raises(RuntimeError):
        _get_deadline_requirement("dependencies = []")
