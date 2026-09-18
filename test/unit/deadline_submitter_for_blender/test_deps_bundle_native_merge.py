# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

"""Guards which compiled artifact the dependency bundle ships for each interpreter.

The bundle is one flat directory placed on ``PYTHONPATH``, so it holds a single file per
name no matter how many Python versions Blender might embed. ``scripts/depsBundle.py``
installs the compiled packages once per supported version and merges the results, and the
merge is where an interpreter can quietly lose its artifact: when two versions install the
same filename, the surviving copy is the only one any interpreter gets to load, and one
built for a newer Python fails to import on an older one.

These tests drive the merge over synthetic trees named the way the real wheels name their
extension modules, because a real build downloads a wheel per compiled package per
supported version. That is also their limit: they assert which artifact is selected, not
that it loads. Proving it loads needs the target interpreter, which the unit suite has no
access to -- ``test_console_signin_dependencies`` only reaches the interpreter running the
tests.
"""

import subprocess
import sys
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).parents[3] / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    # Appended rather than prepended: scripts/ holds generically named modules (common.py),
    # and prepending would shadow any same-named import for the rest of the pytest session.
    sys.path.append(str(SCRIPTS_DIR))

import depsBundle

# awscrt's abi3 wheels all install this one name, whatever Python they were built for.
ABI3_ARTIFACT = "_awscrt.abi3.so"

# awscrt ships a version-specific wheel through Python 3.10 and abi3 wheels from 3.11
# onward. Named explicitly, rather than left for the fixture and the assertion below to
# each infer from list position, so the two move together if SUPPORTED_PYTHON_VERSIONS ever
# drops 3.10 -- changing this constant changes which supported versions get an abi3 name at
# all, not which list index a test happens to read.
AWSCRT_LAST_NON_ABI3_VERSION = "3.10"


def _version_key(version: str) -> tuple[int, ...]:
    return tuple(int(part) for part in version.split("."))


def _tag(version: str) -> str:
    """The interpreter tag a wheel puts in a version-specific extension module name."""
    return version.replace(".", "")


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


@pytest.fixture
def supported_versions() -> list[str]:
    versions = sorted(depsBundle.SUPPORTED_PYTHON_VERSIONS, key=_version_key)
    assert len(versions) >= 2, "a filename collision needs at least two supported versions"
    return versions


@pytest.fixture
def merged_bundle(tmp_path, supported_versions) -> Path:
    """Run the merge over trees named the way the real wheels name their artifacts.

    Reproduces both naming schemes. awscrt installs the shared abi3 name from every abi3
    wheel and a version-specific name from the non-abi3 wheel it publishes for the oldest
    supported Python; xxhash and pyyaml install a version-specific name for every version;
    psutil ships one abi3 wheel that serves all of them, so every tree holds identical bytes.

    Each file's content records the version whose install produced it, so the merged tree
    reports where its own contents came from. The base environment is seeded with a sentinel
    rather than a real version, standing in for a build host whose interpreter is not one the
    bundle targets: a real version could coincide with the expected winner if
    SUPPORTED_PYTHON_VERSIONS ever held only one version above the abi3 boundary, letting the
    collision assertion pass even if the merge copied nothing.
    """
    base_env = tmp_path / "base_env"
    _write(base_env / ABI3_ARTIFACT, "build-host")

    boundary = _version_key(AWSCRT_LAST_NON_ABI3_VERSION)
    assert any(_version_key(v) <= boundary for v in supported_versions) and any(
        _version_key(v) > boundary for v in supported_versions
    ), (
        "AWSCRT_LAST_NON_ABI3_VERSION needs supported versions on both sides of it for this "
        "fixture to exercise both the version-specific and the abi3-collision case"
    )

    native_paths = []
    for version in supported_versions:
        tree = tmp_path / "native" / _tag(version)
        native_paths.append(tree)
        if _version_key(version) <= boundary:
            _write(tree / f"_awscrt.cpython-{_tag(version)}-darwin.so", version)
        else:
            _write(tree / ABI3_ARTIFACT, version)
        _write(tree / "xxhash" / f"_xxhash.cpython-{_tag(version)}-darwin.so", version)
        _write(tree / "yaml" / f"_yaml.cpython-{_tag(version)}-darwin.so", version)
        _write(tree / "psutil" / "_psutil_osx.abi3.so", "shared")

    depsBundle._copy_native_to_base_env(base_env, native_paths)
    return base_env


def test_colliding_abi3_artifact_comes_from_the_lowest_supported_abi(
    merged_bundle, supported_versions
):
    """abi3 is forward compatible, so the lowest is the only copy that serves every version.

    A copy built for a newer Python links against symbols an older one does not export, so
    it fails to import there -- botocore then leaves its crypto binding unset and AWS
    Console sign-in reports that sign-in is needed, indefinitely.
    """
    lowest_abi3_version = min(
        (
            version
            for version in supported_versions
            if _version_key(version) > _version_key(AWSCRT_LAST_NON_ABI3_VERSION)
        ),
        key=_version_key,
    )
    shipped = (merged_bundle / ABI3_ARTIFACT).read_text()

    assert shipped == lowest_abi3_version, (
        f"{ABI3_ARTIFACT} was built for Python {shipped}, so it cannot be imported by "
        f"Python {lowest_abi3_version}; the copy built for the lowest supported abi3 "
        f"version is the one every supported interpreter can load"
    )


def test_version_specific_artifacts_are_kept_for_every_supported_version(
    merged_bundle, supported_versions
):
    """The other half of the rule: these names do not collide, so none may be dropped.

    Collapsing a colliding name to one copy is only safe because the names that encode an
    interpreter tag are distinct, and every supported version needs its own.
    """
    for version in supported_versions:
        for package, module in (("xxhash", "_xxhash"), ("yaml", "_yaml")):
            artifact = merged_bundle / package / f"{module}.cpython-{_tag(version)}-darwin.so"
            assert (
                artifact.exists()
            ), f"the bundle carries no {package} artifact for Python {version}"
            assert artifact.read_text() == version

    for version in supported_versions:
        if _version_key(version) > _version_key(AWSCRT_LAST_NON_ABI3_VERSION):
            continue
        awscrt_non_abi3 = merged_bundle / f"_awscrt.cpython-{_tag(version)}-darwin.so"
        assert (
            awscrt_non_abi3.exists()
        ), f"the bundle carries no awscrt artifact for Python {version}"


def test_native_trees_are_merged_lowest_python_version_first(tmp_path, monkeypatch):
    """The merge keeps the first tree to supply a name, so the download order picks the winner.

    Ordered numerically rather than as strings: sorted as text, "3.9" lands after "3.10".
    The versions here are chosen to expose that, not to describe what is supported.
    """
    monkeypatch.setattr(depsBundle, "SUPPORTED_PYTHON_VERSIONS", ["3.13", "3.9", "3.11", "3.10"])
    monkeypatch.setattr(depsBundle, "_get_package_version", lambda package, install_path: "1.2.3")

    requested_versions: list[str] = []

    def record(args, **kwargs):
        requested_versions.append(args[args.index("--python-version") + 1])
        return subprocess.CompletedProcess(args, 0)

    monkeypatch.setattr(depsBundle.subprocess, "run", record)

    tree_paths = depsBundle._download_native_dependencies(tmp_path, tmp_path / "base_env")

    assert requested_versions == ["3.9", "3.10", "3.11", "3.13"]
    assert [path.name for path in tree_paths] == ["3_9", "3_10", "3_11", "3_13"]


def test_get_package_version_matches_pip_list_casing(monkeypatch):
    """`pip list` prints the distribution's own casing, not the requirement's.

    NATIVE_DEPENDENCIES spells `pyyaml`, but pip reports it as `PyYAML`; a case-sensitive
    match would fail the per-version downloads for a package that is actually installed.
    """
    output = b"Package  Version\n-------- -------\nPyYAML   6.0.3\nxxhash   3.6.0\n"
    monkeypatch.setattr(
        depsBundle.subprocess,
        "run",
        lambda args, **kwargs: subprocess.CompletedProcess(args, 0, stdout=output),
    )

    assert depsBundle._get_package_version("pyyaml", Path("/unused")) == "6.0.3"
