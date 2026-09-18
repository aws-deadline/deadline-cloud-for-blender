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
--platform <tag>``, and awscrt ships no ``macosx_10_9_*`` wheel at all, so resolving
the console extra under the ``macosx_10_9_x86_64`` tag that script uses would fail
the adaptor build outright.

The tests above guard the negative side: the extra and awscrt must be absent from
project.dependencies. The tests below guard the positive side -- that
``_add_console_extra`` adds the extra correctly, that ``_build_base_environment``
still passes it to pip, and that ``NATIVE_DEPENDENCIES`` still carries awscrt and
pyyaml -- so that removing any of those silently breaks console sign-in in the
shipped bundle without failing the negative-side tests above.
"""

import subprocess
import sys
from pathlib import Path

import pytest
from packaging.requirements import Requirement

if sys.version_info >= (3, 11):
    import tomllib
else:  # pragma: no cover - exercised on Python 3.9/3.10 only
    import tomli as tomllib

SCRIPTS_DIR = Path(__file__).parents[3] / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    # Appended rather than prepended: scripts/ holds generically named modules (common.py),
    # and prepending would shadow any same-named import for the rest of the pytest session.
    sys.path.append(str(SCRIPTS_DIR))

import depsBundle  # importable only after the sys.path append above

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
    --platform <tag>. awscrt ships no macosx_10_9_x86_64 wheel at all, so resolving the
    console extra there has no candidate to fall back to -- the adaptor build fails
    outright rather than silently shipping broken crypto support. The adaptor never signs
    in interactively, so it has no use for the extra either way.
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


def test_native_dependencies_include_awscrt_and_pyyaml():
    """Pins the packages depsBundle.py fetches per-version for their compiled artifacts.

    Console sign-in needs awscrt to be importable under whichever Python Blender embeds;
    pyyaml needs the same because it silently falls back to a pure-Python parser otherwise.
    Dropping either from NATIVE_DEPENDENCIES would ship a bundle where a subset of
    interpreters cannot load one of them, with nothing here to catch it.
    """
    assert "awscrt" in depsBundle.NATIVE_DEPENDENCIES
    assert "pyyaml" in depsBundle.NATIVE_DEPENDENCIES


def test_build_base_environment_requests_the_console_extra(tmp_path, monkeypatch):
    """Pins the positive half of the console sign-in fix: the extra actually reaches pip.

    test_base_dependencies_do_not_request_the_console_extra guards that the extra is absent
    from project.dependencies; this guards that _build_base_environment still adds it back
    before invoking pip, mirroring the subprocess.run monkeypatch already used in
    test_deps_bundle_native_merge.py. If the _add_console_extra call here were dropped, that
    other test would stay green while the shipped bundle silently lost console sign-in.
    """
    captured_args: list[str] = []

    def record(args, **kwargs):
        captured_args.extend(args)
        return subprocess.CompletedProcess(args, 0)

    monkeypatch.setattr(depsBundle.subprocess, "run", record)

    depsBundle._build_base_environment(tmp_path, ["deadline>=0.60.4,<0.61", "xxhash"])

    console_reqs = [arg for arg in captured_args if arg.lower().startswith("deadline[")]
    assert console_reqs, f"no deadline requirement with an extra was passed to pip: {captured_args}"
    assert "console" in console_reqs[0], f"console extra missing from pip argv: {console_reqs[0]}"


def test_build_base_environment_accepts_a_deadline_requirement_already_requesting_console(
    tmp_path, monkeypatch
):
    """_add_console_extra is idempotent, so a `deadline[console]` requirement declared
    directly in project.dependencies is a correct input, not a config the guard should
    reject. A changed-something check on the guard would fail this case even though pip
    ends up asking for the console extra either way.
    """
    monkeypatch.setattr(
        depsBundle.subprocess, "run", lambda args, **kwargs: subprocess.CompletedProcess(args, 0)
    )

    # Raises if the guard rejects an already-correct dependency list.
    depsBundle._build_base_environment(tmp_path, ["deadline[console]>=0.60.4,<0.61"])


def test_build_base_environment_raises_when_nothing_requests_console(tmp_path, monkeypatch):
    """The guard still fails loudly on the drift it exists to catch: no requirement that
    _add_console_extra recognizes as `deadline`, so nothing ends up requesting the console
    extra.
    """
    monkeypatch.setattr(
        depsBundle.subprocess, "run", lambda args, **kwargs: subprocess.CompletedProcess(args, 0)
    )

    with pytest.raises(Exception, match="no dependency requests deadline's `console` extra"):
        depsBundle._build_base_environment(tmp_path, ["deadline-cloud>=0.60.4,<0.61", "xxhash"])


@pytest.mark.parametrize(
    "requirement,expected",
    [
        ("deadline>=0.60.4,<0.61", "deadline[console]>=0.60.4,<0.61"),
        ("deadline[gui]>=0.60.4", "deadline[gui,console]>=0.60.4"),
        ("deadline[gui,console]>=0.60.4", "deadline[gui,console]>=0.60.4"),
        ("deadline[console]>=0.60.4", "deadline[console]>=0.60.4"),
        ("xxhash>=3.0", "xxhash>=3.0"),
    ],
)
def test_add_console_extra_pins_behavior(requirement, expected):
    """Pins _add_console_extra's contract: preserve existing extras, be idempotent, and leave
    non-deadline requirements untouched.
    """
    assert depsBundle._add_console_extra(requirement) == expected


def test_add_console_extra_makes_the_real_base_dependencies_request_console():
    """Stronger than the parametrized behavior test above: proves the injection takes effect
    against pyproject.toml's actual dependencies, not just a synthetic requirement string.

    Checks the postcondition -- that some entry ends up requesting deadline's ``console``
    extra -- rather than that ``_add_console_extra`` changed something. ``_add_console_extra``
    is idempotent, so if ``project.dependencies`` ever declared ``deadline[console]``
    directly, a changed-something check would fail a config that is already correct. This
    still fails loudly if the `deadline` requirement is ever renamed, wrapped, or split --
    say the base dependency became ``deadline-cloud`` -- which is exactly how the bundle
    would otherwise ship with no awscrt and no build-time signal.
    """
    pyproject_dict = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))
    dependencies = depsBundle._get_dependencies(pyproject_dict)
    dependencies_for_pip = [depsBundle._add_console_extra(dep) for dep in dependencies]

    assert any(depsBundle._requests_console_extra(dep) for dep in dependencies_for_pip), (
        "no real base dependency requests deadline's `console` extra after "
        "_add_console_extra; the `deadline` requirement it targets may have been renamed, "
        "wrapped, or removed from project.dependencies"
    )
