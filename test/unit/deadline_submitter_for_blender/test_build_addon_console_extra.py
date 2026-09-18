# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

"""Guards the Blender extension's dependency channel for AWS Console sign-in.

scripts/build_addon.py pulls the `deadline` requirement out of pyproject.toml and feeds it to
`pip download` for the extension's wheels/ directory -- a separate channel from
scripts/depsBundle.py's dependency bundle for the desktop submitter. Nothing ties the two
together, so a rewrite of one that is not mirrored in the other silently drops awscrt from
whichever channel was missed, and console sign-in breaks only there.
"""

import sys
from pathlib import Path

import pytest
from packaging.version import Version

SCRIPTS_DIR = Path(__file__).parents[3] / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    # Appended rather than prepended: scripts/ holds generically named modules (common.py),
    # and prepending would shadow any same-named import for the rest of the pytest session.
    sys.path.append(str(SCRIPTS_DIR))

from build_addon import (  # importable only after the sys.path append
    _get_deadline_requirement,
    _requirement_floor,
    _verify_platform_download,
)


def test_get_deadline_requirement_adds_the_console_extra():
    """The regression this test exists for: before this fix, the extracted requirement had no
    console extra, so the extension's wheels/ directory had no awscrt in it.
    """
    pyproject_contents = """
[project]
dependencies = [
    "deadline >= 0.60.4,< 0.61",
    "openjd-adaptor-runtime >= 0.7,< 0.10",
]

[project.optional-dependencies]
gui = [
    "deadline[gui,console] >= 0.60.4,< 0.61",
]
"""
    assert _get_deadline_requirement(pyproject_contents) == "deadline[console]>=0.60.4,<0.61"


def test_get_deadline_requirement_reads_project_dependencies_not_the_gui_extra():
    """Pins that the extraction reads project.dependencies specifically, not whichever
    `deadline` requirement happens to appear first in the file.

    Puts the `gui` extra's `deadline[gui,console]` line before `dependencies` in the text --
    a naive first-match scan over raw text would return that line instead. tomllib table
    access does not care about a file's textual order, so this still returns
    project.dependencies' entry.

    Load-bearing: if this picked up the `gui` extra's line, build_addon.py would pull
    PySide6 into the extension's wheels/, which -- combined with the manylinux2014_x86_64
    platform tag change in the same diff as this fix -- would turn into a hard `pip download`
    failure (PySide6-Essentials only ships manylinux_2_28_x86_64 wheels for linux).
    """
    pyproject_contents = """
[project.optional-dependencies]
gui = [
    "deadline[gui,console] >= 0.60.4,< 0.61",
]

[project]
dependencies = [
    "deadline >= 0.60.4,< 0.61",
]
"""
    assert _get_deadline_requirement(pyproject_contents) == "deadline[console]>=0.60.4,<0.61"


def test_get_deadline_requirement_raises_when_no_deadline_dependency_is_found():
    with pytest.raises(RuntimeError):
        _get_deadline_requirement("[project]\ndependencies = []\n")


def test_requirement_floor_reads_the_gte_specifier():
    assert _requirement_floor("deadline[console]>=0.60.4,<0.61") == Version("0.60.4")


def test_requirement_floor_raises_without_a_gte_specifier():
    with pytest.raises(ValueError):
        _requirement_floor("deadline[console]<0.61")


def test_verify_platform_download_passes_when_deadline_and_awscrt_are_present(tmp_path):
    (tmp_path / "deadline-0.60.7-py3-none-any.whl").touch()
    (tmp_path / "awscrt-0.36.0-cp311-abi3-manylinux2014_x86_64.whl").touch()

    _verify_platform_download(str(tmp_path), "manylinux2014_x86_64", Version("0.60.4"))


def test_verify_platform_download_raises_when_deadline_is_missing(tmp_path):
    (tmp_path / "awscrt-0.36.0-cp311-abi3-manylinux2014_x86_64.whl").touch()

    with pytest.raises(RuntimeError, match="no deadline wheel resolved"):
        _verify_platform_download(str(tmp_path), "manylinux2014_x86_64", Version("0.60.4"))


def test_verify_platform_download_raises_when_deadline_backtracked_below_the_floor(tmp_path):
    """The regression this exists for: pip resolving an older, wheel-having `deadline` for a
    platform where a transitive dependency (e.g. awscrt) has stopped publishing a compatible
    wheel, exiting 0 with no other signal.
    """
    (tmp_path / "deadline-0.60.3-py3-none-any.whl").touch()
    (tmp_path / "awscrt-0.36.0-cp311-abi3-manylinux2014_x86_64.whl").touch()

    with pytest.raises(RuntimeError, match="below the required floor"):
        _verify_platform_download(str(tmp_path), "manylinux2014_x86_64", Version("0.60.4"))


def test_verify_platform_download_raises_when_awscrt_is_missing(tmp_path):
    (tmp_path / "deadline-0.60.7-py3-none-any.whl").touch()

    with pytest.raises(RuntimeError, match="no awscrt wheel resolved"):
        _verify_platform_download(str(tmp_path), "manylinux2014_x86_64", Version("0.60.4"))
