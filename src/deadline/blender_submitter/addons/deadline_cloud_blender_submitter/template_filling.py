# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

"""Functions to fill Blender job templates."""

from __future__ import annotations

import dataclasses
import json
import logging
import os
import traceback
from copy import deepcopy
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

import yaml
from deadline.client.exceptions import DeadlineOperationError

_logger = logging.getLogger(__name__)

_ALL_CAMERAS = "ALL_CAMERAS"
_SETTINGS_FILE_EXT = ".deadline_render_settings.json"


@dataclass
class BlenderSubmitterUISettings:
    """Settings that the submitter UI will use."""

    name: str = field(default="Blender Submission", metadata={"sticky": True})
    description: str = field(default="", metadata={"sticky": True})

    submitter_name: str = field(default="Blender")
    renderer_name: str = field(default="cycles", metadata={"sticky": True})
    scene_name: str = field(default="Scene", metadata={"sticky": True})
    enable_gpu: bool = field(default=False, metadata={"sticky": True})
    gpu_device: str = field(default="None", metadata={"sticky": True})

    ui_group_label: str = field(default="Blender Settings")

    # Frame settings.
    # Whether to override the frame range.
    override_frame_range: bool = field(default=False, metadata={"sticky": True})
    # The frame range to use if override_frame_range_check is True.
    frame_list: str = field(default="1", metadata={"sticky": True})

    # Paths and files.
    project_path: str = field(default="")
    output_path: str = field(default="", metadata={"sticky": True})
    output_file_prefix: str = field(default="output_####", metadata={"sticky": True})
    input_filenames: list[str] = field(default_factory=list, metadata={"sticky": True})
    input_directories: list[str] = field(default_factory=list, metadata={"sticky": True})
    output_directories: list[str] = field(default_factory=list, metadata={"sticky": True})

    # OCIO config file is specified here.
    ocio_config_path: str = field(default="")

    # Layers settings.
    view_layer_selection: str = field(default="ViewLayer", metadata={"sticky": True})

    # Camera settings.
    all_layer_selectable_cameras: list[str] = field(default_factory=lambda: [_ALL_CAMERAS])
    current_layer_selectable_cameras: list[str] = field(default_factory=lambda: [_ALL_CAMERAS])
    camera_selection: str = field(default="Camera", metadata={"sticky": True})

    # Resolution settings.
    image_resolution: str = field(default="1920, 1080")

    # Parameter names.
    scene_name_parameter_name: str = field(default="RenderScene", metadata={"sticky": True})
    frames_parameter_name: str = field(default="Frames")
    output_file_prefix_parameter_name: str = field(default="OutputFileName")
    image_width_parameter_name: str = field(default="ResolutionX")
    image_height_parameter_name: str = field(default="ResolutionY")

    # developer options
    include_adaptor_wheels: bool = field(default=False, metadata={"sticky": True})

    def load_sticky_settings(self, scene: str) -> None:
        """Load and set sticky settings for the given scene.

        The path to the sticky settings file is determined by appending the `_SETTINGS_FILE_EXT` extension to the scene name.

        If the file does not exist, or if it is malformed, the default settings will be used instead.

        Args:
            scene: The name of the scene.
        """

        def warn(cause=None):
            traceback.print_exc()
            msg = f"Failed to load sticky settings from {sticky_file}."
            if cause:
                msg += " " + cause
            _logger.warn(msg)

        sticky_file = Path(scene).with_suffix(_SETTINGS_FILE_EXT)
        if not sticky_file.exists() or not sticky_file.is_file():
            warn("File does not exist.")
            return

        try:
            with open(sticky_file, encoding="utf8") as fh:
                sticky_settings = json.load(fh)
            if not isinstance(sticky_settings, dict):
                warn("Settings are not formatted as a dictionary.")
                return
            sticky_fields = {
                field.name: field
                for field in dataclasses.fields(self)
                if field.metadata.get("sticky")
            }
            for name, value in sticky_settings.items():
                if name in sticky_fields:
                    setattr(self, name, value)
        except (OSError, json.JSONDecodeError) as e:
            warn(str(e))

        _logger.info(f"Loaded sticky settings from {sticky_file}.")

    def save_sticky_settings(self, scene: str):
        """Save sticky settings to a file. Create or overwrite it if necessary, but don't create parent directories.

        The path to the sticky settings file is determined by appending the `_SETTINGS_FILE_EXT` extension to the scene name.
        """
        file = Path(scene).with_suffix(_SETTINGS_FILE_EXT)
        with open(file, "w", encoding="utf8") as fh:
            sticky_settings = {
                field.name: getattr(self, field.name)
                for field in dataclasses.fields(self)
                if field.metadata.get("sticky")
            }
            json.dump(sticky_settings, fh, indent=1)
        _logger.info(f"Saved sticky settings to {file}.")


@dataclass
class CommonLayerSettings:
    """Parameters common to a number of rendering layers."""

    renderer_name: str
    frame_range: str
    frames_parameter_name: Optional[str]
    renderable_camera_names: list[str]
    output_directories: str
    output_file_prefix: str
    output_file_prefix_parameter_name: Optional[str]
    ui_group_label: str
    image_width_parameter_name: Optional[str]
    image_height_parameter_name: Optional[str]
    image_resolution: tuple[int, int]
    scene_name: str


def fill_job_template(
    settings: BlenderSubmitterUISettings,
    view_layer_names: list[str],
    common_layer_settings: CommonLayerSettings,
    host_requirements: Optional[dict],
):
    """Create and return a filled-in job template."""

    # Read the default job template.
    with open(Path(__file__).parent / "default_blender_template.yaml") as fh:
        job_template = yaml.safe_load(fh)

    job_template["name"] = settings.name
    if settings.description:
        job_template["description"] = settings.description

    # Add resolution parameters.
    job_template["parameterDefinitions"].append(
        {
            "name": common_layer_settings.image_width_parameter_name,
            "type": "INT",
            "userInterface": {
                "control": "SPIN_BOX",
                "label": "Image Width",
                "groupLabel": common_layer_settings.ui_group_label,
            },
            "minValue": 1,
            "description": "The image width.",
        }
    )
    job_template["parameterDefinitions"].append(
        {
            "name": common_layer_settings.image_height_parameter_name,
            "type": "INT",
            "userInterface": {
                "control": "SPIN_BOX",
                "label": "Image Height",
                "groupLabel": common_layer_settings.ui_group_label,
            },
            "minValue": 1,
            "description": "The image height.",
        }
    )

    # If an OCIO config file is set, we will have to add a job parameter and environment for it.
    if settings.ocio_config_path:
        _add_ocio_template_data(job_template)

    # For each layer, create a step based on the default step template.
    steps = []
    default_step_template = job_template["steps"][0]
    for layer in view_layer_names:
        step = _fill_step_template(
            layer, default_step_template, settings, common_layer_settings, host_requirements
        )
        _logger.info(f"Generated step definition for scene {settings.scene_name}")
        steps.append(step)
    job_template["steps"] = steps

    # If this developer option is enabled, merge the adaptor_override_environment.
    if settings.include_adaptor_wheels:
        override_env_file = Path(__file__).parent / "adaptor_override_environment.yaml"
        with open(override_env_file) as f:
            override_environment = yaml.safe_load(f)

        err_msg = "The Developer Option 'Include Adaptor Wheels' is enabled, but "

        # Read DEVELOPMENT.md for instructions to create the wheels directory.
        wheels_path = Path(__file__).parent.parent.parent.parent / "wheels"
        if not wheels_path.exists() and wheels_path.is_dir():
            raise RuntimeError(
                err_msg + "the wheels directory does not exist:\n" + str(wheels_path)
            )

        wheels_path_package_names = {
            path.split("-", 1)[0] for path in os.listdir(wheels_path) if path.endswith(".whl")
        }
        expected = {"openjd_adaptor_runtime", "deadline", "deadline_cloud_for_blender"}
        if wheels_path_package_names != expected:
            raise RuntimeError(
                err_msg
                + "the wheels directory contains the wrong wheels:\n"
                + f"Expected: {expected}\n"
                + f"Actual: {wheels_path_package_names}"
            )

        override_adaptor_name_param = [
            param
            for param in override_environment["parameterDefinitions"]
            if param["name"] == "OverrideAdaptorName"
        ][0]
        override_adaptor_name_param["default"] = "blender-openjd"

        # There are no parameter conflicts between these two templates, so this works
        job_template["parameterDefinitions"].extend(override_environment["parameterDefinitions"])

        # Add the environment to the end of the template's job environments
        if "jobEnvironments" not in job_template:
            job_template["jobEnvironments"] = []
        job_template["jobEnvironments"].append(override_environment["environment"])

    return job_template


def _add_ocio_template_data(job_template: dict):
    job_template["parameterDefinitions"].append(
        {
            "name": "OCIOConfigPath",
            "type": "PATH",
            "objectType": "FILE",
            "dataFlow": "IN",
            "description": "The colour management info to render with.",
        }
    )

    if "jobEnvironments" not in job_template:
        job_template["jobEnvironments"] = []

    # Insert at index 0 so that OCIO is set before Blender runs
    job_template["jobEnvironments"].insert(
        0, {"name": "Set OCIO Path", "variables": {"OCIO": "{{Param.OCIOConfigPath}}"}}
    )


def _fill_step_template(
    view_layer_name: str,
    default_step_template: dict,
    settings: BlenderSubmitterUISettings,
    common_layer_settings: CommonLayerSettings,
    host_requirements: Optional[dict],
):
    """Return a defined step.

    Each step corresponds to a view layer in Blender. Its defined state is a dict that will be serialized to YAML and written to the job template. The default step template contains the basic structure of a step, but it is not filled in with the specific values for this layer.

    There are four steps to defining a step:
    - Update the step name to the name of the layer.
    - Update the init data.
    - Create a parameter space dimension for the selected frames.
    - Create a parameter space dimension for the selected cameras.
    - Inject the host requirements, if provided.

    NOTE: In f-strings, doubling { escapes it.
    """

    step = deepcopy(default_step_template)

    # Update the step name.
    step["name"] = view_layer_name

    def decode(bad_yaml: str) -> dict:
        """Some yaml inside the template cannot be parsed because it contains unescaped characters like {}. This function parses it manually.

        Parse a string like `'a: b\\nc: d\\ne: f'` to a dict `{'a': 'b', 'c': 'd', 'e': 'f'}`.
        """
        d = {}
        for line in bad_yaml.splitlines():
            key, value = line.split(": ", 1)
            d[key] = value
        return d

    def encode(d: dict) -> str:
        """Encode a dict `{'a': 'b', 'c': 'd', 'e': 'f'}` to a string `'a: b\nc: d\ne: f'`.

        The reverse operation of `decode`.
        """
        return "\n".join(f"{k}: {v}" for k, v in d.items())

    # Update the init data.
    # init_data["data"] is a string of key/values separated by newlines.
    # Parse it and update the values, then re-serialize it.
    updated_init_data = {
        "renderer": common_layer_settings.renderer_name,
        "view_layer": view_layer_name,
        "output_file_prefix": "{{{{Param.{}}}}}".format(
            common_layer_settings.output_file_prefix_parameter_name or "OutputFilePrefix"
        ),
        "image_width": "{{{{Param.{}}}}}".format(
            common_layer_settings.image_width_parameter_name or "ImageWidth"
        ),
        "image_height": "{{{{Param.{}}}}}".format(
            common_layer_settings.image_height_parameter_name or "ImageHeight"
        ),
    }
    init_data = step["stepEnvironments"][0]["script"]["embeddedFiles"][0]
    d = decode(init_data["data"])
    d.update(updated_init_data)
    init_data["data"] = encode(d)

    # Update the 'Param.Frames' reference in the Frame task parameter.
    param_defs = step["parameterSpace"]["taskParameterDefinitions"]
    if common_layer_settings.frames_parameter_name:
        param_defs[0]["range"] = "{{{{Param.{}}}}}".format(
            common_layer_settings.frames_parameter_name
        )

    # Create a parameter space dimension for the selected cameras.
    # Should be a list of strings, even if only one camera is selected.
    # NOTE this string var cross-references the constant defined in `scene_settings_widget.py`. Duplicated to avoid importing that file.
    if settings.camera_selection == "All Renderable Cameras":
        cameras = common_layer_settings.renderable_camera_names
    else:
        cameras = [settings.camera_selection]
    param_defs.append({"name": "Camera", "type": "STRING", "range": cameras})
    run_data = step["script"]["embeddedFiles"][0]
    run_data["data"] += "camera: '{{Task.Param.Camera}}'\n"

    # If host requirements are provided, inject them into the step template.
    if host_requirements:
        step["hostRequirements"] = host_requirements
        _logger.debug(
            f"Injected host requirements into step {view_layer_name}: {host_requirements}"
        )

    return step


def get_parameter_values(
    settings: BlenderSubmitterUISettings,
    layer_settings: CommonLayerSettings,
    queue_params: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Collect the parameter values for the job bundle as a list of name/value dicts."""

    param_dict: dict[str, Any] = {
        "BlenderFile": settings.project_path,
        "OutputFileName": layer_settings.output_file_prefix,
        "OutputDir": layer_settings.output_directories,
        "RenderScene": layer_settings.scene_name,
        "RenderEngine": layer_settings.renderer_name,
        "GPUDevice": settings.gpu_device,
    }

    if layer_settings.frames_parameter_name:
        param_dict[layer_settings.frames_parameter_name] = layer_settings.frame_range
    if layer_settings.image_width_parameter_name:
        param_dict[layer_settings.image_width_parameter_name] = layer_settings.image_resolution[0]
    if layer_settings.image_height_parameter_name:
        param_dict[layer_settings.image_height_parameter_name] = layer_settings.image_resolution[1]

    # Format the parameter values as a list of dicts, each with a "name" and a "value" key.
    params = [{"name": k, "value": v} for k, v in param_dict.items()]

    # Check for any overlap between the job parameters we've defined and the queue parameters. This is an error, as we weren't synchronizing the values between the two different tabs where they came from.
    overlap: set[str] = {p["name"] for p in params}.intersection({p["name"] for p in queue_params})
    if overlap:
        raise DeadlineOperationError(
            "The following queue parameters conflict with the Blender job parameters:\n"
            + f"{', '.join(overlap)}"
        )

    # If specified, add the parameter value for OCIO here
    if settings.ocio_config_path:
        params.append({"name": "OCIOConfigPath", "value": settings.ocio_config_path})

    # If we're overriding the adaptor with wheels, remove the adaptor from the Packages
    if settings.include_adaptor_wheels:
        wheels_path = str(Path(__file__).parent.parent.parent.parent / "wheels")
        params.append({"name": "OverrideAdaptorWheels", "value": wheels_path})
        rez_param = {}
        conda_param = {}
        # Find the Packages parameter definition in the queue params.
        for param in queue_params:
            if param["name"] == "RezPackages":
                rez_param = param
            if param["name"] == "CondaPackages":
                conda_param = param

        # Remove the deadline_cloud_for_blender/blender-openjd rez package.
        if rez_param:
            rez_param["value"] = " ".join(
                pkg
                for pkg in rez_param["value"].split()
                if not pkg.startswith("deadline_cloud_for_blender")
            )
        if conda_param:
            conda_param["value"] = " ".join(
                pkg for pkg in conda_param["value"].split() if not pkg.startswith("blender-openjd")
            )

    params.extend({"name": param["name"], "value": param["value"]} for param in queue_params)

    return params
