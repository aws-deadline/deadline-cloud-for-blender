# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

"""
submission_functions.py

This file contains the logic required for building the Job Bundle files and handling submission to
Deadline.
"""

import json
import os
import re
from configparser import ConfigParser
from pathlib import Path
from threading import Thread
from typing import Any, Dict, List

import bpy
import yaml  # type: ignore
from deadline.client import api, config
from deadline.client.job_bundle.adaptors import get_rez_environment
from .utility_functions import active_profile

INSTALLATION_REQUIREMENTS_DEFAULT = "deadline_blender"


def _get_blender_version_string():
    """
    Convert the Blender version from a tuple to a dot-separated version string.
    """
    return ".".join(map(str, bpy.app.version))


def _get_major_minor_blender_version_string():
    """
    Convert the blender version from a tuple to a dot-separated Major.Minor string.
    """
    major, minor, *rest = bpy.app.version

    return f"{major}.{minor}"


def _get_output_path():
    """
    Get output filepath based on whether or not it is being overridden.
    """
    wm = bpy.context.window_manager
    scene = bpy.context.scene

    return wm.deadline_output_path if wm.deadline_override_output_path else scene.render.filepath


def _get_installation_requirements():
    """
    Get installation requirements based on whether or not it is being overridden.
    """
    wm = bpy.context.window_manager
    if wm.deadline_override_installation_requirements:
        return wm.deadline_installation_requirements
    else:
        return f"{INSTALLATION_REQUIREMENTS_DEFAULT} blender-{_get_major_minor_blender_version_string()}"


def _get_frame_list():
    """
    Get frame list based on whether or not it is being overridden.
    """
    wm = bpy.context.window_manager
    scene = bpy.context.scene

    return (
        wm.deadline_frame_range
        if wm.deadline_override_frame_range
        else f"{scene.frame_start}-{scene.frame_end}"
    )


def _get_scene_render_engine() -> str:
    scene_name = bpy.context.window_manager.deadline_scene
    return bpy.data.scenes[scene_name].render.engine


def _get_init_data_attachment() -> Dict[str, Any]:
    plugin_settings = {
        "project_file": bpy.data.filepath,
        "strict_error_checking": False,
        "version": _get_blender_version_string(),
        "renderer": _get_scene_render_engine(),
    }
    data = yaml.safe_dump(plugin_settings, indent=2)

    return {
        "name": "initData",
        "type": "TEXT",
        "data": data,
    }


def _get_run_data_attachment() -> Dict[str, Any]:
    wm = bpy.context.window_manager

    plugin_settings = {
        "scene": wm.deadline_scene,
        "layer": wm.deadline_layer,
        "animation": wm.deadline_render_animation,
        "output_path": _get_output_path(),
    }
    data = yaml.safe_dump(plugin_settings, indent=2)
    data += "frame: {{ Task.Param.frame }}\n"

    return {"name": "runData", "type": "TEXT", "data": data}


def _parse_frame_range(frame_string: str) -> List[int]:
    framelist_re = re.compile(r"^(?P<start>-?\d+)(-(?P<stop>-?\d+)(:(?P<step>-?\d+))?)?$")
    match = framelist_re.match(frame_string)
    if not match:
        raise ValueError("Frame list not valid")

    start = int(match.group("start"))
    stop = int(match.group("stop")) if match.group("stop") is not None else start
    frame_step = (
        int(match.group("step")) if match.group("step") is not None else 1 if start < stop else -1
    )

    if frame_step == 0:
        raise ValueError("Frame step cannot be zero")
    if start > stop and frame_step > 0:
        raise ValueError("Start frame must be less than stop frame if step is positive")
    if start < stop and frame_step < 0:
        raise ValueError("Start frame must be greater than stop frame if step is negative")

    return list(range(start, stop + (1 if frame_step > 0 else -1), frame_step))


def _get_asset_references() -> Dict[str, Any]:
    wm = bpy.context.window_manager

    input_assets = [attachment.path for attachment in wm.deadline_job_attachments]
    input_assets.append(bpy.data.filepath)

    input_jobs = [job.name for job in wm.deadline_job_output_attachments]

    output_path = bpy.path.abspath(_get_output_path())

    output_directories = [os.path.dirname(output_path)]

    return {
        "inputs": {
            "filenames": input_assets,
            "directories": [],
            "deadline:jobs": [{"jobId": job_id} for job_id in input_jobs],
        },
        "outputs": {
            "filenames": [],
            "directories": output_directories,
        },
    }


BLENDER_BACKGROUND_START_SCRIPT = """#!/bin/env bash

set -e

_term() {
    echo "Being canceled"
    date
    kill -s TERM $CHILD_PID
    wait $CHILD_PID
    exit 1
}
trap _term SIGTERM

# Activate the Rez environment to populate environment variables.
. /usr/local/bin/deadline-rez activate -d "{{ Session.WorkingDirectory }}"

# Start the adaptor as a background process with the adaptor class constructed.
# This command exits once that background process is started & operational, but
# leaves the background process running.
# Will also connect to that background process to make sure it's operational.
# Returns non-zero if there are any issues getting the background process started.
BlenderAdaptor background init \
    --connection-file {{ Session.WorkingDirectory }}/connection.json \
    --init-data file://{{ Env.File.initData }} &
CHILD_PID=$!
# If the shell isn't waiting then the signal trap will not happen
wait $CHILD_PID

# Send the start signal to the adaptor background process to run up to 'StartJob'
# Monitor the process as it runs (heartbeats), and collect logging output from the
# background process. Logging output is sent to stdout.
# This process will return a non-zero exit code if the 'StartJob' has an error
BlenderAdaptor background start \
    --connection-file {{ Session.WorkingDirectory }}/connection.json &
CHILD_PID=$!
# If the shell isn't waiting then the signal trap will not happen
wait $CHILD_PID
"""

BLENDER_BACKGROUND_END_SCRIPT = """#!/bin/env bash
set -e

# Set up a SIGTERM trap for handling cancellation. This forwards the SIGTERM
# to the current process.
_term() {
    echo "Being canceled"
    date
    kill -s TERM $CHILD_PID
    wait $CHILD_PID
    exit 1
}
trap _term SIGTERM

# Activate the Rez environment to populate environment variables.
. /usr/local/bin/deadline-rez activate -d "{{ Session.WorkingDirectory }}"

# Tells the adaptor background process to run the 'EndJob' phase, and then exit.
# Monitors as it is exiting. Will explicitly kill the background process if
# it becomes unresponsive or takes 'too long'
BlenderAdaptor background end \
    --connection-file {{ Session.WorkingDirectory }}/connection.json &
CHILD_PID=$!
# If the shell isn't waiting then the signal trap will not happen
wait $CHILD_PID
"""


def _get_blender_in_background_environment() -> Dict[str, Any]:
    return {
        "name": "Blender",
        "description": "Environment that starts the Blender Adaptor in background mode.",
        "script": {
            "embeddedFiles": [
                _get_init_data_attachment(),
                {
                    "name": "start",
                    "type": "TEXT",
                    "runnable": True,
                    "data": BLENDER_BACKGROUND_START_SCRIPT,
                },
                {
                    "name": "end",
                    "type": "TEXT",
                    "runnable": True,
                    "data": BLENDER_BACKGROUND_END_SCRIPT,
                },
            ],
            "actions": {
                "onEnter": {
                    "command": "{{ Env.File.start }}",
                    "cancelation": {
                        "mode": "NOTIFY_THEN_TERMINATE",
                        "notifyPeriodInSeconds": 90,
                    },
                },
                "onExit": {
                    "command": "{{ Env.File.end }}",
                    "cancelation": {
                        "mode": "NOTIFY_THEN_TERMINATE",
                        "notifyPeriodInSeconds": 90,
                    },
                },
            },
        },
    }


RUN_SCRIPT = """#!/bin/env bash
set -e

# Set up a SIGTERM trap for handling cancellation. This uses the
# adaptor's cancel command to cancel the running task.
_term() {
echo "Being canceled"
date
# Sending the run a SIGTERM will initiate a cancelation
kill -s TERM $CHILD_PID
wait $CHILD_PID
exit 1
}
trap _term SIGTERM

# Activate the Rez environment to populate environment variables.
. /usr/local/bin/deadline-rez activate -d "{{ Session.WorkingDirectory }}"

# Send a signal to the adaptor background process to render a frame.
# Only exits once the frame has finished rendering. While waiting this will monitor
# the background process's heartbeats, and forward the background process's
# logging to stdout.
BlenderAdaptor background run \
--connection-file {{ Session.WorkingDirectory }}/connection.json \
--run-data file://{{ Task.File.runData }} &
CHILD_PID=$!
# If the shell isn't waiting then the signal trap will not happen
wait $CHILD_PID
"""


def _build_job_template(config_file: ConfigParser) -> Dict[str, Any]:
    wm = bpy.context.window_manager

    job_template: Dict[str, Any] = {
        "specificationVersion": "2022-09-01",
        "name": wm.deadline_job_name,
    }

    frame_string = _get_frame_list()
    frame_list: List[int] = _parse_frame_range(frame_string)
    step_parameter_space = {"parameters": [{"name": "frame", "range": frame_list, "type": "INT"}]}
    installation_requirements = _get_installation_requirements()

    steps: List[Dict[str, Any]] = [
        {
            "name": wm.deadline_job_name,
            "parameterSpace": step_parameter_space,
            "environments": [
                get_rez_environment([installation_requirements]),
                _get_blender_in_background_environment(),
            ],
            "script": {
                "embeddedFiles": [
                    _get_run_data_attachment(),
                    {
                        "name": "run",
                        "type": "TEXT",
                        "runnable": True,
                        "data": RUN_SCRIPT,
                    },
                ],
                "actions": {
                    "onRun": {
                        "command": "{{ Task.File.run }}",
                        "cancelation": {
                            "mode": "NOTIFY_THEN_TERMINATE",
                            "notifyPeriodInSeconds": 90,
                        },
                    }
                },
            },
        }
    ]

    job_template["steps"] = steps

    return job_template


def _build_parameter_values():
    wm = bpy.context.window_manager

    return {
        "parameterValues": [
            {"name": "deadline:maxRetriesPerTask", "value": wm.deadline_max_retries_per_task},
            {"name": "deadline:priority", "value": wm.deadline_priority},
            {"name": "deadline:maxFailedTasksCount", "value": wm.deadline_max_failed_tasks_count},
            {"name": "deadline:targetTaskRunStatus", "value": wm.deadline_submission_status},
        ]
    }


def build_submission(job_bundle_dir: str, config_file: ConfigParser):
    job_bundle_path = Path(job_bundle_dir)

    job_template = _build_job_template(config_file)
    with open(job_bundle_path / "template.json", "w", encoding="utf8") as f:
        json.dump(job_template, f, indent=1)

    parameters = _build_parameter_values()
    with open(job_bundle_path / "parameter_values.json", "w", encoding="utf8") as f:
        json.dump(parameters, f, indent=1)

    asset_references = {"assetReferences": _get_asset_references()}
    with open(job_bundle_path / "asset_references.json", "w", encoding="utf8") as f:
        json.dump(asset_references, f, indent=1)


def build_config() -> ConfigParser:
    wm = bpy.context.window_manager

    config_file = ConfigParser()
    config.set_setting("defaults.farm_id", wm.deadline_farm, config_file)
    config.set_setting("defaults.queue_id", wm.deadline_queue, config_file)
    config.set_setting("settings.storage_profile_id", wm.deadline_storage_profile, config_file)
    endpoint_url = config.get_setting("settings.deadline_endpoint_url")
    config.set_setting("settings.deadline_endpoint_url", endpoint_url, config_file)
    active_profile(config=config_file)
    _rename_AmazonDeadlineCliAccess_sections(
        config_file, config.get_setting("defaults.aws_profile_name", config=config_file)
    )
    return config_file


# temp function whil Deadline client lib defaults to AmazonDeadlineCliAccess
def _rename_AmazonDeadlineCliAccess_sections(config, new_name):
    name = "AmazonDeadlineCliAccess"
    section_names = [s for s in config.sections() if name in s]
    for section_from in section_names:
        section_to = section_from.replace(name, new_name)
        items = config.items(section_from)
        config.add_section(section_to)
        for item in items:
            config.set(section_to, item[0], item[1])
        config.remove_section(section_from)


class SubmitBackgroundThread(Thread):
    def __init__(self, job_bundle_dir: str, config_file: ConfigParser):
        super().__init__()
        self.job_bundle_dir = job_bundle_dir
        self.config = config_file

    def run(self):
        """
        This function is started as a background thread to run the submit process so that the UI is still available.
        """
        api.create_job_from_job_bundle(self.job_bundle_dir, config=self.config)
