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
NATIVE_DEPENDENCIES = ["xxhash", "psutil"]

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
    return list(map(lambda dep: dep.replace(" ", ""), deps_noopenjd))


def _get_package_version_regex(package: str) -> re.Pattern:
    return re.compile(rf"^{re.escape(package)} *(.*)$")


def _get_package_version(package: str, install_path: Path) -> str:
    version_regex = _get_package_version_regex(package)
    pip_args = ["pip", "list", "--path", str(install_path)]
    output = subprocess.run(pip_args, check=True, capture_output=True).stdout.decode("utf-8")
    for line in output.split("\n"):
        match = version_regex.match(line)
        if match:
            return match.group(1)
    raise Exception(f"Could not find version for package {package}")


def _build_base_environment(working_directory: Path, dependencies: list[str]) -> Path:
    (working_directory / "base_env").mkdir()
    base_env_path = working_directory / "base_env"
    base_env_pip_args = [
        "pip",
        "install",
        "--target",
        str(base_env_path),
        "--only-binary=:all:",
        *dependencies,
    ]
    subprocess.run(base_env_pip_args, check=True)
    return base_env_path


def _download_native_dependencies(working_directory: Path, base_env: Path) -> list[Path]:
    versioned_native_dependencies = [
        f"{package_name}=={_get_package_version(package_name, base_env)}"
        for package_name in NATIVE_DEPENDENCIES
    ]
    native_dependency_paths = []
    for version in SUPPORTED_PYTHON_VERSIONS:
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
            *versioned_native_dependencies,
        ]
        subprocess.run(native_dependency_pip_args, check=True)
    return native_dependency_paths


def _copy_native_to_base_env(base_env: Path, native_dependency_paths: list[Path]) -> None:
    for native_dependency_path in native_dependency_paths:
        for file in native_dependency_path.rglob("*"):
            if file.is_file():
                relative = file.relative_to(native_dependency_path)
                in_base_env = base_env / relative
                if not in_base_env.exists():
                    in_base_env.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy(str(file), str(in_base_env))


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
