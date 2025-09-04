# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

import os
import subprocess
import json

from pathlib import Path
from typing import Any


def run_command(args: list[str]) -> subprocess.CompletedProcess[bytes]:
    output = subprocess.run(args, capture_output=True, env=os.environ.copy())

    print(f"Ran the following: {' '.join(output.args)}")
    print(f"\nstdout:\n\n{output.stdout.decode('utf-8', errors='replace')}")
    print(f"\nstderr:\n\n{output.stderr.decode('utf-8', errors='replace')}")

    return output


def run_blender_submitter_test(
    blender_location: Path, test_script_location: Path, *additional_args
) -> subprocess.CompletedProcess[bytes]:
    args = [
        str(blender_location),
        "--background",
        "--python",
        str(test_script_location),
        # Don't allow automatic running of scripts in the scene
        # See https://docs.blender.org/manual/en/latest/advanced/scripting/security.html
        "--disable-autoexec",
        "--python-use-system-env",
        "--python-exit-code",
        "1",
        "--addons",
        "deadline_cloud_blender_submitter",
    ]

    if additional_args:
        args.extend(["--", *additional_args])

    return run_command(args)


def is_valid_template(template_location: Path) -> bool:
    output = run_command(["openjd", "check", str(template_location), "--output", "json"])

    output_json = json.loads(output.stdout)

    return output_json["status"] == "success"


def run_adaptor_test(template_path: Path, job_params: dict[str, Any], blender_location) -> None:
    import yaml

    # Set BLENDER_EXECUTABLE so the adaptor will find it
    os.environ["BLENDER_EXECUTABLE"] = str(blender_location)

    # Parse template to get step names
    with open(template_path) as f:
        template = yaml.safe_load(f)

    steps = [step["name"] for step in template.get("steps", [])]

    # Run each step separately to avoid connection file race condition
    for step_name in steps:
        output = run_command(
            [
                "openjd",
                "run",
                str(template_path),
                "--step",
                step_name,
                "--job-param",
                json.dumps(job_params),
            ]
        )
        assert output.returncode == 0
