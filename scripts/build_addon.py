# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

import argparse
from glob import glob
import json
import os
from pathlib import Path
import shutil
import subprocess
import tarfile
from tempfile import TemporaryDirectory
import hashlib
import re

from depsBundle import _strip_pyside6, _add_console_extra

SUPPORTED_PLATFORMS = [
    "win_amd64",
    # awscrt (pulled in below via the console extra) publishes manylinux2014_x86_64 /
    # manylinux_2_17_x86_64 wheels for linux, not manylinux_2_28_x86_64: `pip download
    # --platform manylinux_2_28_x86_64` does not treat those as compatible (pip's tag
    # generation for an explicit --platform only walks to older manylinux aliases, it does
    # not walk up), so requesting the newer tag here would make this download fail outright
    # once the console extra is requested. manylinux2014_x86_64 resolves every dependency
    # this script downloads, including awscrt; verified via `pip download --only-binary=:all:
    # --python-version=3.11 --platform=manylinux2014_x86_64 "deadline[console]>=<floor>"`.
    "manylinux2014_x86_64",
    "macosx_12_0_arm64",
    "macosx_12_0_x86_64",
]
ADDON_NAME = "Deadline Cloud for Blender"
ADDON_TAGLINE = "Submit to AWS Deadline Cloud"


def _get_deadline_requirement(pyproject_contents: str) -> str:
    """Extract project.dependencies' `deadline` requirement from pyproject.toml's raw text and
    add the console extra, mirroring depsBundle.py's _build_base_environment. Without this,
    the extension's wheels/ directory silently ships without awscrt while the desktop
    submitter's dependency bundle has it, since the two channels declare the requirement
    independently and neither enforces the other.

    Reads pyproject.toml as text rather than parsing it, matching this script's original
    behavior: it has always matched the FIRST quoted `"deadline..."` line, which is
    project.dependencies' unadorned entry (no extras) -- never the `gui` extra's
    `deadline[gui,console]` line that comes later in the file.
    """
    match = re.search(r"\"deadline\S* .+ .+\"", pyproject_contents)
    if not match:
        raise RuntimeError("Could not find the deadline version requirement in project.toml")
    return _add_console_extra(match.group(0).replace('"', ""))


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

        # Download the wheels of the deadline library and its dependencies
        for platform in SUPPORTED_PLATFORMS:
            subprocess.run(
                [
                    "pip",
                    "download",
                    deadline_version_requirement,
                    "--dest",
                    f"{temp}/wheels",
                    "--only-binary=:all:",
                    "--python-version=3.11",
                    f"--platform={platform}",
                ],
                check=True,
            )

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
