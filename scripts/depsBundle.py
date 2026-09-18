# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

from __future__ import annotations

import fnmatch
import re
import shutil
import subprocess
import sys

from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

SUPPORTED_PYTHON_VERSIONS = ["3.10", "3.11", "3.13"]
# Packages with compiled extension modules, fetched once per supported Python version so the
# bundle carries a loadable artifact for each interpreter.
#
# awscrt is here because its wheels are not uniformly abi3: Python 3.10 gets
# _awscrt.cpython-310-<platform>.so while 3.11+ get _awscrt.abi3.so. Resolving it only in
# the base environment would ship whichever the build host produced, so any Blender whose
# interpreter that single artifact does not cover would fail to import awscrt and AWS
# Console sign-in would break there.
# pyyaml is here because it ships a version-specific `_yaml` extension module: resolved only
# in the base environment it lands built for a single interpreter, and pyyaml hides that by
# falling back to its pure-Python parser on the others.
NATIVE_DEPENDENCIES = ["xxhash", "psutil", "awscrt", "pyyaml"]

PYSIDE6_VERSION = "6.8.3"
PYSIDE6_PACKAGES = [f"PySide6-Essentials=={PYSIDE6_VERSION}", f"shiboken6=={PYSIDE6_VERSION}"]

# Files to keep from PySide6 and shiboken6 pip packages after installation.
# Derived from the deadline-cloud pyinstaller allowlist to keep the bundle minimal.
# Everything not matching these patterns is deleted before zipping.
PYSIDE6_ALLOWLIST = {
    # -- shiboken6 --
    "shiboken6/__init__.py",
    "shiboken6/_config.py",
    "shiboken6/Shiboken.abi3.so",
    "shiboken6/Shiboken.pyd",
    "shiboken6/libshiboken6.abi3.*.dylib",
    "shiboken6/libshiboken6.abi3.so.*",
    "shiboken6/shiboken6.abi3.dll",
    "shiboken6/VCRUNTIME140.dll",
    "shiboken6/VCRUNTIME140_1.dll",
    "shiboken6/MSVCP140.dll",
    "shiboken6-*.dist-info/*",
    "shiboken6-*.dist-info/**/*",
    # -- PySide6 package metadata --
    "PySide6/__init__.py",
    "PySide6/_config.py",
    "PySide6/_git_pyside_version.py",
    "PySide6-*.dist-info/*",
    "PySide6-*.dist-info/**/*",
    "PySide6_Essentials-*.dist-info/*",
    # -- PySide6 Python bindings --
    "PySide6/Qt*.abi3.so",
    "PySide6/QtCore.pyd",
    "PySide6/QtGui.pyd",
    "PySide6/QtWidgets.pyd",
    "PySide6/QtDBus.pyd",
    "PySide6/QtSvg.pyd",
    "PySide6/QtNetwork.pyd",
    "PySide6/QtOpenGL.pyd",
    "PySide6/QtOpenGLWidgets.pyd",
    # -- PySide6/shiboken6 shared libraries --
    "PySide6/libpyside6.abi3.*.dylib",
    "PySide6/libpyside6.abi3.so.*",
    "PySide6/pyside6.abi3.dll",
    # -- Windows MSVC runtime bundled with PySide6 --
    "PySide6/VCRUNTIME140.dll",
    "PySide6/VCRUNTIME140_1.dll",
    "PySide6/MSVCP140.dll",
    "PySide6/MSVCP140_1.dll",
    "PySide6/MSVCP140_2.dll",
    # -- Windows OpenGL software renderer --
    "PySide6/opengl32sw.dll",
    # -- Qt core DLLs (Windows) --
    "PySide6/Qt6Core.dll",
    "PySide6/Qt6Gui.dll",
    "PySide6/Qt6Widgets.dll",
    "PySide6/Qt6DBus.dll",
    "PySide6/Qt6Svg.dll",
    # -- Qt frameworks (macOS) --
    # fnmatch's ** doesn't do recursive matching, so we need both * and **/* patterns
    "PySide6/Qt/lib/QtCore.framework/*",
    "PySide6/Qt/lib/QtCore.framework/**/*",
    "PySide6/Qt/lib/QtGui.framework/*",
    "PySide6/Qt/lib/QtGui.framework/**/*",
    "PySide6/Qt/lib/QtWidgets.framework/*",
    "PySide6/Qt/lib/QtWidgets.framework/**/*",
    "PySide6/Qt/lib/QtDBus.framework/*",
    "PySide6/Qt/lib/QtDBus.framework/**/*",
    "PySide6/Qt/lib/QtSvg.framework/*",
    "PySide6/Qt/lib/QtSvg.framework/**/*",
    # -- Qt shared libraries (Linux) --
    "PySide6/Qt/lib/libQt6Core.so.*",
    "PySide6/Qt/lib/libQt6Gui.so.*",
    "PySide6/Qt/lib/libQt6Widgets.so.*",
    "PySide6/Qt/lib/libQt6DBus.so.*",
    "PySide6/Qt/lib/libQt6Svg.so.*",
    "PySide6/Qt/lib/libQt6XcbQpa.so.*",
    "PySide6/Qt/lib/libQt6WaylandClient.so.*",
    "PySide6/Qt/lib/libQt6WaylandEglClientHwIntegration.so.*",
    "PySide6/Qt/lib/libQt6WlShellIntegration.so.*",
    "PySide6/Qt/lib/libQt6OpenGL.so.*",
    "PySide6/Qt/lib/libQt6EglFSDeviceIntegration.so.*",
    "PySide6/Qt/lib/libQt6EglFsKmsSupport.so.*",
    # ICU (required by Qt6Core on Linux)
    "PySide6/Qt/lib/libicui18n.so.*",
    "PySide6/Qt/lib/libicuuc.so.*",
    "PySide6/Qt/lib/libicudata.so.*",
    # -- Qt plugins (macOS/Linux: Qt/plugins/, Windows: plugins/) --
    # platforms
    "PySide6/Qt/plugins/platforms/libqcocoa.dylib",
    "PySide6/Qt/plugins/platforms/libqoffscreen.*",
    "PySide6/Qt/plugins/platforms/libqminimal.*",
    "PySide6/Qt/plugins/platforms/libqminimalegl.so",
    "PySide6/Qt/plugins/platforms/libqxcb.so",
    "PySide6/Qt/plugins/platforms/libqeglfs.so",
    "PySide6/Qt/plugins/platforms/libqlinuxfb.so",
    "PySide6/Qt/plugins/platforms/libqvkkhrdisplay.so",
    "PySide6/Qt/plugins/platforms/libqvnc.so",
    "PySide6/Qt/plugins/platforms/libqwayland*.so",
    "PySide6/plugins/platforms/qwindows.dll",
    "PySide6/plugins/platforms/qminimal.dll",
    "PySide6/plugins/platforms/qoffscreen.dll",
    "PySide6/plugins/platforms/qdirect2d.dll",
    # styles
    "PySide6/Qt/plugins/styles/libqmacstyle.dylib",
    "PySide6/plugins/styles/qwindowsvistastyle.dll",
    "PySide6/plugins/styles/qmodernwindowsstyle.dll",
    # iconengines
    "PySide6/Qt/plugins/iconengines/libqsvgicon.*",
    "PySide6/plugins/iconengines/qsvgicon.dll",
    # imageformats (svg only)
    "PySide6/Qt/plugins/imageformats/libqsvg.*",
    "PySide6/plugins/imageformats/qsvg.dll",
    # wayland (Linux)
    "PySide6/Qt/plugins/wayland-shell-integration/lib*.so",
    "PySide6/Qt/plugins/wayland-decoration-client/lib*.so",
    # platform themes (Linux)
    "PySide6/Qt/plugins/platformthemes/lib*.so",
    # -- Qt translations --
    "PySide6/Qt/translations/*",
    "PySide6/translations/*",
}


def _get_project_dict() -> dict[str, Any]:
    if sys.version_info < (3, 11):
        with TemporaryDirectory() as toml_env:
            toml_install_pip_args = ["pip", "install", "--target", toml_env, "toml"]
            subprocess.run(toml_install_pip_args, check=True)
            sys.path.insert(0, toml_env)
            import toml  # type: ignore
        mode = "r"
    else:
        import tomllib as toml

        mode = "rb"

    with open("pyproject.toml", mode) as pyproject_toml:
        return toml.load(pyproject_toml)


def _get_dependencies(pyproject_dict: dict[str, Any]) -> list[str]:
    if "project" not in pyproject_dict:
        raise Exception("pyproject.toml is missing project section")
    if "dependencies" not in pyproject_dict["project"]:
        raise Exception("pyproject.toml is missing dependencies section")

    dependencies = pyproject_dict["project"]["dependencies"]
    deps_noopenjd = filter(lambda dep: not dep.startswith("openjd"), dependencies)
    return [dep.replace(" ", "") for dep in deps_noopenjd]


def _get_package_version_regex(package: str) -> re.Pattern:
    # Case-insensitive because `pip list` prints the distribution's own casing, which need not
    # match how the requirement is spelled -- `pyyaml` is reported as `PyYAML`. The required
    # whitespace keeps a prefix sibling like `pyyaml-env-tag` from matching.
    return re.compile(rf"^{re.escape(package)}\s+(\S+)\s*$", re.IGNORECASE)


def _get_package_version(package: str, install_path: Path) -> str:
    version_regex = _get_package_version_regex(package)
    pip_args = ["pip", "list", "--path", str(install_path)]
    output = subprocess.run(pip_args, check=True, capture_output=True).stdout.decode("utf-8")
    for line in output.split("\n"):
        match = version_regex.match(line)
        if match:
            return match.group(1)
    raise Exception(f"Could not find version for package {package}")


def _add_console_extra(requirement: str) -> str:
    """Add deadline's `console` extra to a requirement string, preserving its specifier."""
    match = re.fullmatch(
        r"(?P<name>[A-Za-z0-9._-]+)(?:\[(?P<extras>[^\]]*)\])?(?P<spec>.*)", requirement
    )
    if not match or match.group("name").lower() != "deadline":
        return requirement
    extras = [extra for extra in (match.group("extras") or "").split(",") if extra]
    if "console" not in extras:
        extras.append("console")
    return f"{match.group('name')}[{','.join(extras)}]{match.group('spec')}"


def _build_base_environment(working_directory: Path, dependencies: list[str]) -> Path:
    (working_directory / "base_env").mkdir()
    base_env_path = working_directory / "base_env"
    # The bundle is the submitter, which needs AWS Console sign-in. The console extra is
    # requested here rather than declared in project.dependencies, because those are also
    # resolved into the adaptor package, where a compiled awscrt wheel is both unusable and
    # unavailable for one of the platform tags that build targets (see pyproject.toml).
    #
    # Requesting the extra rather than installing awscrt directly means the bundle tracks
    # whatever the extra actually requires -- notably a botocore floor, since the console
    # login provider lives in botocore, not in deadline -- and takes awscrt from the exact
    # version botocore's crt extra pins, rather than resolving it independently and drifting.
    dependencies_for_pip = [_add_console_extra(dep) for dep in dependencies]
    base_env_pip_args = [
        "pip",
        "install",
        "--target",
        str(base_env_path),
        "--only-binary=:all:",
        *dependencies_for_pip,
    ]
    subprocess.run(base_env_pip_args, check=True)
    return base_env_path


def _python_version_key(version: str) -> tuple[int, ...]:
    return tuple(int(part) for part in version.split("."))


def _download_native_dependencies(working_directory: Path, base_env: Path) -> list[Path]:
    versioned_native_dependencies = [
        f"{package_name}=={_get_package_version(package_name, base_env)}"
        for package_name in NATIVE_DEPENDENCIES
    ]
    native_dependency_paths = []
    # Ascending order is load-bearing: _copy_native_to_base_env resolves a filename
    # collision in favour of the tree it sees first.
    for version in sorted(SUPPORTED_PYTHON_VERSIONS, key=_python_version_key):
        native_dependency_path = working_directory / "native" / f"{version.replace('.', '_')}"
        native_dependency_paths.append(native_dependency_path)
        native_dependency_path.mkdir(parents=True)
        native_dependency_pip_args = [
            "pip",
            "install",
            "--target",
            str(native_dependency_path),
            "--python-version",
            version,
            "--only-binary=:all:",
            # These trees exist only for their compiled artifacts, and they overwrite the
            # base environment during the merge. Without --no-deps each tree would carry the
            # packages' full transitive closures, resolved independently of the base
            # environment's, and clobber whatever it had resolved for anything they share.
            # Today none of NATIVE_DEPENDENCIES has runtime dependencies, but that is a
            # property of the current graph, not of this code.
            "--no-deps",
            *versioned_native_dependencies,
        ]
        subprocess.run(native_dependency_pip_args, check=True)
    return native_dependency_paths


def _copy_native_to_base_env(base_env: Path, native_dependency_paths: list[Path]) -> None:
    """Flatten the per-version native trees into the bundle, lowest version first.

    ``native_dependency_paths`` is ordered by ascending Python version and the first tree
    to supply a path wins, overwriting the base environment. The base environment resolved
    these packages for whatever interpreter the build host happens to run, which is not a
    version the bundle targets, so it must not decide which artifact ships.

    Which artifacts survive follows from how the wheels name their extension modules, so no
    rule is needed per package. A version-specific name is unique per version and so cannot
    collide: ``xxhash`` ships one wheel per version and every interpreter keeps its own
    ``_xxhash.cpython-<tag>-<platform>.so``, and ``pyyaml`` is the same case, one wheel per
    version installing ``yaml/_yaml.cpython-<tag>-<platform>.so``. An abi3 name is the same
    for every version and so collides, and there the two cases differ. ``psutil`` publishes
    a single abi3 wheel
    that serves all of them, so every tree holds identical bytes and the collision is a
    no-op. ``awscrt`` publishes a separate abi3 wheel per Python, each installing
    ``_awscrt.abi3.so``, so the copies differ and only one can ship; abi3 is forward
    compatible, which makes the one built for the lowest supported Python the only copy
    that loads on all of them, and taking the first tree is what keeps it.
    """
    copied: set[Path] = set()
    for native_dependency_path in native_dependency_paths:
        for file in native_dependency_path.rglob("*"):
            if file.is_file():
                relative = file.relative_to(native_dependency_path)
                if relative in copied:
                    continue
                in_base_env = base_env / relative
                in_base_env.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy(str(file), str(in_base_env))
                copied.add(relative)


def _get_zip_path(working_directory: Path, project_dict: dict[str, Any]) -> Path:
    if "project" not in project_dict:
        raise Exception("pyproject.toml is missing project section")
    if "name" not in project_dict["project"]:
        raise Exception("pyproject.toml is missing name section")
    transformed_project_name = (
        f"{project_dict['project']['name'].replace('-', '_')}_submitter-deps.zip"
    )
    return working_directory / transformed_project_name


def _zip_bundle(base_env: Path, zip_path: Path) -> None:
    shutil.make_archive(str(zip_path.with_suffix("")), "zip", str(base_env))


def _copy_zip_to_destination(zip_path: Path) -> Path:
    dependency_bundle_dir = Path.cwd() / "dependency_bundle"
    dependency_bundle_dir.mkdir(exist_ok=True)
    zip_destination = dependency_bundle_dir / zip_path.name
    if zip_destination.exists():
        zip_destination.unlink()
    shutil.copy(str(zip_path), str(zip_destination))

    return zip_destination


def _install_pyside6(install_path: Path) -> None:
    """Install PySide6 and shiboken6, then strip to only the files in PYSIDE6_ALLOWLIST."""
    pip_args = [
        "pip",
        "install",
        "--target",
        str(install_path),
        "--only-binary=:all:",
        *PYSIDE6_PACKAGES,
    ]
    subprocess.run(pip_args, check=True)
    _strip_pyside6(install_path)


def _strip_pyside6(install_path: Path) -> None:
    """Remove PySide6/shiboken6 files not in PYSIDE6_ALLOWLIST."""
    for prefix in (
        "PySide6",
        "shiboken6",
        "PySide6_Essentials-*.dist-info",
        "shiboken6-*.dist-info",
    ):
        for pkg_dir in install_path.glob(prefix):
            if not pkg_dir.is_dir():
                continue
            for path in list(pkg_dir.rglob("*")):
                if not path.is_file():
                    continue
                rel = str(path.relative_to(install_path))
                if not any(fnmatch.fnmatch(rel, pat) for pat in PYSIDE6_ALLOWLIST):
                    path.unlink()
            # Clean up empty directories
            for dirpath in sorted(pkg_dir.rglob("*"), reverse=True):
                if dirpath.is_dir() and not any(dirpath.iterdir()):
                    dirpath.rmdir()


def build_deps_bundle() -> None:
    with TemporaryDirectory() as wd:
        working_directory = Path(wd)
        project_dict = _get_project_dict()
        dependencies = _get_dependencies(project_dict)
        base_env = _build_base_environment(working_directory, dependencies)
        native_dependency_paths = _download_native_dependencies(working_directory, base_env)
        _copy_native_to_base_env(base_env, native_dependency_paths)
        _install_pyside6(base_env)
        zip_path = _get_zip_path(working_directory, project_dict)
        _zip_bundle(base_env, zip_path)
        print(list(working_directory.glob("*")))
        _copy_zip_to_destination(zip_path)


if __name__ == "__main__":
    build_deps_bundle()
