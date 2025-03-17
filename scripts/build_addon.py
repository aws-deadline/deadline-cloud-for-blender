# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

import argparse
from glob import glob
import json
import os
from pathlib import Path
import shutil
import subprocess
from tempfile import TemporaryDirectory
import hashlib
import re

parser = argparse.ArgumentParser(description="Experimental: Builds a Blender extension")
parser.add_argument("--version", required=False)
args = parser.parse_args()
version = args.version or "0.0.0"


SUPPORTED_PLATFORMS = [
    "win_amd64",
    "manylinux_2_17_x86_64",
    "macosx_11_0_arm64",
    "macosx_10_9_x86_64",
]
ADDON_NAME = "Deadline Cloud for Blender"
ADDON_TAGLINE = "Submit to AWS Deadline Cloud"

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
    match = re.search(r"\"deadline .+ .+\"", project_toml_contents)
    if not match:
        raise RuntimeError("Could not find the deadline version requirement in project.toml")
    deadline_version_requirement = match.group(0).replace('"', "")
    print(f"Found requirement {deadline_version_requirement} in project.toml")

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
