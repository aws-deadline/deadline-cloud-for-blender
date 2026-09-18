# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

"""Guards the dependency declarations that AWS Console sign-in depends on.

Console sign-in is not exercised by the integration tests: it needs an interactive
browser OAuth handshake and Deadline Cloud Monitor, while CI authenticates by
assuming a role, so credentials are host-provided and the console path is never
taken. What can break silently is the dependency declaration, which is what these
tests pin.

The tests read ``pyproject.toml`` rather than installed distribution metadata.
``importlib.metadata`` reflects what was captured at install time, so an edit to
``pyproject.toml`` would not be seen until the environment is reinstalled -- and
"somebody edited that line" is precisely the regression being guarded.

Scope matters as much as the versions. ``console`` belongs on the ``gui`` extra and
not on the base dependencies: the base list is resolved into the adaptor package by
``scripts/create_adaptor_packaging_artifact.sh`` under ``--only-binary=:all:
--platform <tag>``, and no awscrt wheel meeting the floor exists for the
``macosx_10_9_x86_64`` tag that script uses, so pip would silently walk back to a
release with no usable crypto support.
"""

import sys
from pathlib import Path

import pytest
from packaging.requirements import Requirement

if sys.version_info >= (3, 11):
    import tomllib
else:  # pragma: no cover - exercised on Python 3.9/3.10 only
    import tomli as tomllib

PYPROJECT = Path(__file__).parents[3] / "pyproject.toml"

# Console sign-in landed in deadline 0.60.4 and nowhere earlier: 0.60.1 through
# 0.60.3 have no AWS_CONSOLE_LOGIN credentials source and do not declare a
# `console` extra at all. 0.60.3 is the highest version that must be excluded.
HIGHEST_DEADLINE_WITHOUT_CONSOLE_SIGNIN = "0.60.3"


def _requirements(*table_path: str) -> list[Requirement]:
    """Parse a requirement list out of pyproject.toml by table path."""
    node = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))
    for key in table_path:
        assert key in node, f"pyproject.toml has no {'.'.join(table_path)}"
        node = node[key]
    return [Requirement(r) for r in node]


def _named(requirements: list[Requirement], name: str) -> list[Requirement]:
    return [r for r in requirements if r.name == name]


@pytest.fixture
def base_dependencies() -> list[Requirement]:
    return _requirements("project", "dependencies")


@pytest.fixture
def gui_dependencies() -> list[Requirement]:
    return _requirements("project", "optional-dependencies", "gui")


def test_gui_extra_requests_the_console_extra(gui_dependencies):
    """The submitter resolves through the gui extra, so console belongs there."""
    deadline_reqs = _named(gui_dependencies, "deadline")
    assert deadline_reqs, "the gui extra declares no requirement on deadline"
    for req in deadline_reqs:
        assert "console" in req.extras, f"missing console extra in: {req}"


def test_base_dependencies_do_not_request_the_console_extra(base_dependencies):
    """Keeps awscrt out of the adaptor package.

    The base list is resolved into the adaptor artifact under --only-binary=:all:
    --platform <tag>. For macosx_10_9_x86_64 no awscrt wheel meets the floor, so pip
    resolves backwards to one whose crypto support botocore will not accept -- the build
    succeeds and console sign-in is quietly broken. The adaptor never signs in
    interactively, so it has no use for the extra.
    """
    for req in _named(base_dependencies, "deadline"):
        assert (
            "console" not in req.extras
        ), f"console extra leaks into the adaptor's dependency closure via: {req}"

    # Copying the requirement in directly is the likelier mistake, and has the same effect.
    assert not _named(
        base_dependencies, "awscrt"
    ), "awscrt must not be a base dependency; it would be resolved into the adaptor package"


@pytest.mark.parametrize("table", ["base_dependencies", "gui_dependencies"])
def test_deadline_floor_excludes_releases_without_console_signin(table, request):
    """Guards the floor itself, not whatever a resolver happened to select.

    An installed-version check cannot do this: with a loosened ">= 0.60.2"
    requirement, pip still resolves the newest 0.60.x, so the regression passes
    unnoticed.
    """
    for req in _named(request.getfixturevalue(table), "deadline"):
        assert not req.specifier.contains(HIGHEST_DEADLINE_WITHOUT_CONSOLE_SIGNIN), (
            f"allows deadline {HIGHEST_DEADLINE_WITHOUT_CONSOLE_SIGNIN}, which has no "
            f"console sign-in support: {req}"
        )
