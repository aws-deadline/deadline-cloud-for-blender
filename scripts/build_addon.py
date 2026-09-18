# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

import argparse
from glob import glob
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
from tempfile import TemporaryDirectory
import hashlib
import re

from packaging.requirements import Requirement
from packaging.version import Version

from depsBundle import _add_console_extra, _get_dependencies, _parse_requirement, _strip_pyside6

if sys.version_info >= (3, 11):
    import tomllib
else:  # pragma: no cover - exercised on Python 3.9/3.10 only
    import tomli as tomllib

SUPPORTED_PLATFORMS = [
    "win_amd64",
    # awscrt (pulled in below via the console extra) publishes manylinux2014_x86_64 /
    # manylinux_2_17_x86_64 wheels for linux, not manylinux_2_28_x86_64: `pip download
    # --platform manylinux_2_28_x86_64` does not treat those as compatible (pip's tag
    # generation for an explicit --platform only walks to older manylinux aliases, it does
    # not walk up), so requesting the newer tag here would make this download fail outright
    # once the console extra is requested. manylinux2014_x86_64 resolved every dependency this
    # script downloads, including awscrt, at the time of writing; verified via `pip download
    # --only-binary=:all: --python-version=3.11 --platform=manylinux2014_x86_64
    # "deadline[console]>=<floor>"`. That is a point-in-time check of today's wheel-publishing
    # policy for the whole dependency closure, not a guarantee -- _verify_platform_download
    # below is what catches it if a future dependency stops publishing a compatible wheel and
    # pip silently backtracks under this narrower tag.
    "manylinux2014_x86_64",
    "macosx_12_0_arm64",
    "macosx_12_0_x86_64",
]
ADDON_NAME = "Deadline Cloud for Blender"
ADDON_TAGLINE = "Submit to AWS Deadline Cloud"


def _get_deadline_requirement(pyproject_contents: str) -> str:
    """Find project.dependencies' `deadline` requirement in pyproject.toml and add the
    console extra, mirroring depsBundle.py's _build_base_environment. Without this, the
    extension's wheels/ directory silently ships without awscrt while the desktop
    submitter's dependency bundle has it, since the two channels declare the requirement
    independently and neither enforces the other.

    Parses project.dependencies via tomllib rather than scanning the file's raw text for the
    first quoted `"deadline..."` line: the substring scan this replaced picked up whichever
    `"deadline..."` line appeared first in the file, which would have silently become the
    `gui` extra's `deadline[gui,console]` line -- pulling PySide6 into the extension -- had
    pyproject.toml ever been reordered.
    """
    dependencies = _get_dependencies(tomllib.loads(pyproject_contents))
    for dependency in dependencies:
        parsed = _parse_requirement(dependency)
        if parsed and parsed[0].lower() == "deadline":
            return _add_console_extra(dependency)
    raise RuntimeError("Could not find a `deadline` requirement in project.dependencies")


def _requirement_floor(requirement: str) -> Version:
    """The version a requirement's `>=` specifier allows as its lowest, used to check pip's
    resolution didn't silently backtrack below the floor this PR depends on.
    """
    for spec in Requirement(requirement).specifier:
        if spec.operator == ">=":
            return Version(spec.version)
    raise ValueError(f"requirement has no >= floor to check against: {requirement}")


def _verify_platform_download(dest: str, platform: str, floor: Version) -> None:
    """Fail the build if pip silently backtracked `deadline` below its floor, or resolved no
    awscrt wheel, while resolving the console extra's dependency closure for `platform`.

    Both are the same silent-failure mechanism this PR exists to close on macOS/the adaptor,
    reachable here instead if some future transitive dependency stops publishing a wheel
    compatible with this platform's tag and pip backtracks to satisfy the rest of the
    closure. `dest` must hold only this platform's own download (a shared destination across
    platforms would let an earlier platform's compliant wheel mask a later one's backtrack).
    """
    deadline_wheels = glob(f"{dest}/deadline-*-py3-none-any.whl")
    if not deadline_wheels:
        raise RuntimeError(f"no deadline wheel resolved for platform {platform}")
    resolved = [Version(os.path.basename(wheel).split("-")[1]) for wheel in deadline_wheels]
    if not any(version >= floor for version in resolved):
        raise RuntimeError(
            f"deadline resolved to {[str(v) for v in resolved]} for platform {platform}, "
            f"below the required floor {floor} -- pip silently backtracked instead of "
            "failing the download"
        )
    if not glob(f"{dest}/awscrt-*"):
        raise RuntimeError(f"no awscrt wheel resolved for platform {platform}")


def strip_pyside6_wheel(whl_path: str) -> None:
    """Strip a PySide6/shiboken6 wheel in-place, keeping only files in PYSIDE6_ALLOWLIST."""
    with TemporaryDirectory() as extract_dir:
        # Extract, strip, re-zip
        shutil.unpack_archive(whl_path, extract_dir, "zip")
        _strip_pyside6(Path(extract_dir))

        # Rewrite RECORD from remaining files
        dist_info = next(Path(extract_dir).glob("*.dist-info"))
        record_path = dist_info / "RECORD"
        with open(record_path, "w") as f:
            for file in sorted(Path(extract_dir).rglob("*")):
                if file.is_file() and file != record_path:
                    f.write(f"{file.relative_to(extract_dir)},,\n")
            f.write(f"{record_path.relative_to(extract_dir)},,\n")

        os.remove(whl_path)
        shutil.make_archive(whl_path.removesuffix(".whl"), "zip", extract_dir)
        os.rename(whl_path.removesuffix(".whl") + ".zip", whl_path)


def main() -> None:
    parser = argparse.ArgumentParser(description="Experimental: Builds a Blender extension")
    parser.add_argument("--version", required=False)
    args = parser.parse_args()
    version = args.version or "0.0.0"

    with TemporaryDirectory() as temp:
        shutil.copytree(
            Path(__file__).parent.parent
            / "src"
            / "deadline"
            / "blender_submitter"
            / "addons"
            / "deadline_cloud_blender_submitter",
            temp,
            dirs_exist_ok=True,
        )

        # Find the version of the deadline library specified in project.toml
        project_toml_contents = (Path(__file__).parent.parent / "pyproject.toml").read_text()
        deadline_version_requirement = _get_deadline_requirement(project_toml_contents)
        print(f"Found requirement {deadline_version_requirement} in project.toml")

        # Extract the bare version spec (without extras) for downloading the sdist
        deadline_version_spec = re.sub(r"\[.*?\]", "", deadline_version_requirement)
        deadline_floor = _requirement_floor(deadline_version_requirement)

        # Download the wheels of the deadline library and its dependencies. Each platform
        # gets its own destination -- not the shared {temp}/wheels -- so
        # _verify_platform_download can check what THIS platform's resolution actually
        # produced; a shared destination would let an earlier, compliant platform's deadline
        # wheel mask a later platform's silent backtrack below the floor.
        wheels_dir = Path(f"{temp}/wheels")
        wheels_dir.mkdir(parents=True, exist_ok=True)
        for platform in SUPPORTED_PLATFORMS:
            platform_dest = f"{temp}/wheels_by_platform/{platform}"
            os.makedirs(platform_dest, exist_ok=True)
            subprocess.run(
                [
                    "pip",
                    "download",
                    deadline_version_requirement,
                    "--dest",
                    platform_dest,
                    "--only-binary=:all:",
                    "--python-version=3.11",
                    f"--platform={platform}",
                ],
                check=True,
            )
            _verify_platform_download(platform_dest, platform, deadline_floor)
            for wheel in glob(f"{platform_dest}/*"):
                shutil.copy(wheel, wheels_dir)

        # Strip PySide6/shiboken6 wheels to only keep the modules we need
        for whl in glob(f"{temp}/wheels/[Pp][Yy][Ss]ide6*") + glob(f"{temp}/wheels/shiboken6*"):
            print(f"Stripping {os.path.basename(whl)}")
            strip_pyside6_wheel(whl)

        # Extract THIRD_PARTY_LICENSES files from the deadline sdist
        licenses_dir = Path(temp) / "THIRD_PARTY_LICENSES"
        licenses_dir.mkdir()
        with TemporaryDirectory() as sdist_dir:
            subprocess.run(
                [
                    "pip",
                    "download",
                    deadline_version_spec,
                    "--no-binary=:all:",
                    "--no-deps",
                    "--dest",
                    sdist_dir,
                ],
                check=True,
            )
            sdist_tarball = next(Path(sdist_dir).glob("deadline-*.tar.gz"))
            with tarfile.open(sdist_tarball) as tar:
                for member in tar.getmembers():
                    if member.name.endswith("/THIRD_PARTY_LICENSES"):
                        # e.g. deadline-0.54.2/scripts/attributions/approved_text/Linux/THIRD_PARTY_LICENSES
                        platform_name = Path(member.name).parent.name
                        content = tar.extractfile(member)
                        if content:
                            (licenses_dir / f"THIRD_PARTY_LICENSES-{platform_name}").write_bytes(
                                content.read()
                            )
        wheel_filenames = [os.path.basename(wheel) for wheel in glob(f"{temp}/wheels/*")]
        wheel_block = "\n".join([f'"./wheels/{filename}",' for filename in wheel_filenames])

        manifest = f"""schema_version = "1.0.0"

id = "deadline_cloud"
version = "{version}"
name = "{ADDON_NAME}"
tagline = "{ADDON_TAGLINE}"
maintainer = "AWS"
type = "add-on"
website = "https://github.com/aws-deadline/deadline-cloud-for-blender"
tags = ["Render"] # https://docs.blender.org/manual/en/dev/advanced/extensions/tags.html
blender_version_min = "4.2.0"

license = [
"SPDX:Apache-2.0", # https://spdx.org/licenses/
]
copyright = [
"Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.",
]

platforms = ["windows-x64", "macos-arm64", "linux-x64"]

# https://docs.blender.org/manual/en/dev/advanced/extensions/python_wheels.html
wheels = [
{wheel_block}
]

[permissions]
network = "Connect to AWS Deadline Cloud and upload assets"
files = "Read related assets"
    """
        with open(str(Path(temp) / "blender_manifest.toml"), "w") as file:
            file.write(manifest)

        Path("dist_extras").mkdir(exist_ok=True)

        zip = shutil.make_archive("dist_extras/deadline-cloud-blender-addon", "zip", temp)

        with open(zip, "rb") as file:
            bytes = file.read()
            sha256 = hashlib.sha256(bytes).hexdigest()

        with open(Path("dist_extras") / "index.json", "w") as file:
            file.write(
                json.dumps(
                    {
                        "version": "v1",
                        "blocklist": [],
                        "data": [
                            {
                                "schema_version": "1.0.0",
                                "id": "deadline_cloud",
                                "name": ADDON_NAME,
                                "tagline": ADDON_TAGLINE,
                                "version": version,
                                "type": "add-on",
                                "maintainer": "AWS",
                                "license": ["SPDX:Apache-2.0"],
                                "blender_version_min": "4.2.0",
                                "website": "https://github.com/aws-deadline/deadline-cloud-for-blender",
                                "copyright": [
                                    "Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved."
                                ],
                                "permissions": {
                                    "network": "Connect to AWS Deadline Cloud and upload assets",
                                    "files": "Read related assets",
                                },
                                "tags": ["Render"],
                                "python_versions": ["3.11"],
                                "archive_url": "./deadline-cloud-blender-addon.zip",
                                "archive_size": Path(zip).stat().st_size,
                                "archive_hash": f"sha256:{sha256}",
                            }
                        ],
                    },
                    indent=2,
                )
            )


if __name__ == "__main__":
    main()
