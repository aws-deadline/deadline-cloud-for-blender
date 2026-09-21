# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

"""Guards the Blender extension's dependency channel for AWS Console sign-in.

scripts/build_addon.py pulls the `deadline` requirement out of pyproject.toml and feeds it to
`pip download` for the extension's wheels/ directory -- a separate channel from
scripts/depsBundle.py's dependency bundle for the desktop submitter. Nothing ties the two
together, so a rewrite of one that is not mirrored in the other silently drops awscrt from
whichever channel was missed, and console sign-in breaks only there.
"""

import subprocess
import sys
from pathlib import Path

import pytest
from packaging.version import Version

SCRIPTS_DIR = Path(__file__).parents[3] / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    # Appended rather than prepended: scripts/ holds generically named modules (common.py),
    # and prepending would shadow any same-named import for the rest of the pytest session.
    sys.path.append(str(SCRIPTS_DIR))

import build_addon  # importable only after the sys.path append above
from build_addon import (
    _download_wheels,
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
    """Pins that the extraction reads project.dependencies specifically, regardless of where
    in the file it appears -- not whichever `deadline` requirement comes first textually.
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


def test_download_wheels_leaves_only_wheels_under_temp(tmp_path, monkeypatch):
    """Regression test: staging used to be nested under `temp`, which is zipped wholesale
    into the shipped extension archive.
    """
    monkeypatch.setattr(build_addon, "SUPPORTED_PLATFORMS", ["win_amd64", "manylinux2014_x86_64"])

    def fake_pip_download(args, **kwargs):
        dest = Path(args[args.index("--dest") + 1])
        platform = args[-1].split("=", 1)[1]
        (dest / "deadline-0.60.7-py3-none-any.whl").touch()
        (dest / f"awscrt-0.36.0-cp311-abi3-{platform}.whl").touch()
        return subprocess.CompletedProcess(args, 0)

    monkeypatch.setattr(build_addon.subprocess, "run", fake_pip_download)

    _download_wheels(str(tmp_path), "deadline[console]>=0.60.4,<0.61", Version("0.60.4"))

    assert {entry.name for entry in tmp_path.iterdir()} == {"wheels"}, (
        "expected only a wheels/ directory directly under temp; anything else nested there "
        "would be zipped into the shipped extension archive alongside it"
    )
    assert (tmp_path / "wheels" / "deadline-0.60.7-py3-none-any.whl").exists()
    assert (tmp_path / "wheels" / "awscrt-0.36.0-cp311-abi3-win_amd64.whl").exists()
    assert (tmp_path / "wheels" / "awscrt-0.36.0-cp311-abi3-manylinux2014_x86_64.whl").exists()
