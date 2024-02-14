# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

"""Test the Deadline Cloud Blender Submitter."""

import sys
from pathlib import Path

import pytest

from deadline.client.exceptions import DeadlineOperationError

# Ensure the submitter can be imported.
SUBMITTER_DIR = (
    Path(__file__).parent.parent
    / "src"
    / "deadline"
    / "blender_submitter"
    / "addons"
    / "deadline_cloud_blender_submitter"
)
sys.path.append(str(SUBMITTER_DIR))
import template_filling

@pytest.fixture
def submitter_settings():
    """Return a submitter settings object."""
    settings = template_filling.BlenderSubmitterUISettings()
    return settings


@pytest.fixture
def common_layer_settings():
    """Return a common layer settings object."""
    settings = template_filling.CommonLayerSettings(
        renderer_name="dummy_renderer",
        frame_range="1-10",
        frames_parameter_name=None,
        renderable_camera_names=["dummy_camera"],
        output_directories=["/dummy/output/directory"],
        output_file_prefix="dummy_prefix",
        output_file_prefix_parameter_name=None,
        ui_group_label="dummy_group_label",
        image_width_parameter_name=None,
        image_height_parameter_name=None,
        image_resolution=(1920, 1080),
        scene_name="dummy_scene_name",
    )
    print(settings)
    return settings


@pytest.fixture
def layers(common_layer_settings):
    return [
        template_filling.Layer("layer_1", common_layer_settings),
        template_filling.Layer("layer_2", common_layer_settings),
    ]


def test_fill_job_template(submitter_settings, layers):
    """Test filling the job template."""

    # NOTE This is not the most elegant way to test this; brittle to changes in the template.

    expected = {
        "specificationVersion": "jobtemplate-2023-09",
        "name": "Blender Submission",
        "description": None,
        "parameterDefinitions": [
            {
                "name": "BlenderFile",
                "type": "PATH",
                "objectType": "FILE",
                "dataFlow": "IN",
                "userInterface": {
                    "control": "CHOOSE_INPUT_FILE",
                    "label": "Blender File",
                    "fileFilters": [
                        {"label": "Blender Files", "patterns": ["*.blend"]},
                        {"label": "All Files", "patterns": ["*"]},
                    ],
                },
                "description": "Choose the Blender scene file you want to render.",
            },
            {
                "name": "RenderEngine",
                "type": "STRING",
                "default": "cycles",
                "allowedValues": ["eevee", "workbench", "cycles"],
            },
            {
                "name": "RenderScene",
                "type": "STRING",
                "userInterface": {
                    "control": "LINE_EDIT",
                    "label": "Scene",
                    "groupLabel": "Blender Settings",
                },
                "default": "Scene",
                "description": "The scene you want to render (scene name).",
            },
            {
                "name": "ViewLayer",
                "type": "STRING",
                "userInterface": {"control": "LINE_EDIT", "label": "view_layer"},
                "description": "Choose the layer to render.",
                "default": "ViewLayer",
            },
            {
                "name": "Frames",
                "type": "STRING",
                "userInterface": {
                    "control": "LINE_EDIT",
                    "label": "Frames",
                    "groupLabel": "Blender Settings",
                },
                "default": "1-1",
                "description": "The frames to render. E.g. 1-3,8,11-15",
            },
            {
                "name": "OutputDir",
                "type": "PATH",
                "objectType": "DIRECTORY",
                "dataFlow": "OUT",
                "userInterface": {"control": "CHOOSE_DIRECTORY", "label": "Output Directory"},
                "description": "Choose the render output directory.",
            },
            {
                "name": "OutputFileName",
                "type": "STRING",
                "userInterface": {"control": "LINE_EDIT", "label": "Output File Name"},
                "default": "output_####",
                "description": "Enter the output filename (without extension).",
            },
            {
                "name": "OutputFormat",
                "type": "STRING",
                "userInterface": {"control": "DROPDOWN_LIST", "label": "Output File Format"},
                "description": "Choose the file format to render as.",
                "default": "PNG",
                "allowedValues": [
                    "TGA",
                    "RAWTGA",
                    "JPEG",
                    "IRIS",
                    "IRIZ",
                    "PNG",
                    "HDR",
                    "TIFF",
                    "OPEN_EXR",
                    "OPEN_EXR_MULTILAYER",
                    "CINEON",
                    "DPX",
                    "DDS",
                    "JP2",
                    "WEBP",
                ],
            },
            {
                "name": "StrictErrorChecking",
                "type": "STRING",
                "userInterface": {
                    "control": "CHECK_BOX",
                    "label": "Strict Error Checking",
                    "groupLabel": "Blender Settings",
                },
                "description": "Fail when errors occur.",
                "default": "false",
                "allowedValues": ["true", "false"],
            },
            {
                "name": None,
                "type": "INT",
                "userInterface": {
                    "control": "SPIN_BOX",
                    "label": "Image Width",
                    "groupLabel": "dummy_group_label",
                },
                "minValue": 1,
                "description": "The image width.",
            },
            {
                "name": None,
                "type": "INT",
                "userInterface": {
                    "control": "SPIN_BOX",
                    "label": "Image Height",
                    "groupLabel": "dummy_group_label",
                },
                "minValue": 1,
                "description": "The image height.",
            },
        ],
        "steps": [
            {
                "name": "layer_1",
                "parameterSpace": {
                    "taskParameterDefinitions": [
                        {"name": "Frame", "type": "INT", "range": "{{Param.Frames}}"},
                        {"name": "Camera", "type": "STRING", "range": ["Camera"]},
                    ]
                },
                "stepEnvironments": [
                    {
                        "name": "Blender",
                        "description": "Runs Blender in the background.",
                        "script": {
                            "embeddedFiles": [
                                {
                                    "name": "initData",
                                    "filename": "init-data.yaml",
                                    "type": "TEXT",
                                    "data": "scene_file: {{Param.BlenderFile}}\nrender_engine: {{Param.RenderEngine}}\nrender_scene: {{Param.RenderScene}}\nview_layer: layer_1\noutput_dir: {{Param.OutputDir}}\noutput_file_name: {{Param.OutputFileName}}\noutput_format: {{Param.OutputFormat}}\nrenderer: dummy_renderer\noutput_file_prefix: {{Param.OutputFilePrefix}}\nimage_width: {{Param.ImageWidth}}\nimage_height: {{Param.ImageHeight}}",
                                }
                            ],
                            "actions": {
                                "onEnter": {
                                    "command": "BlenderAdaptor",
                                    "args": [
                                        "daemon",
                                        "start",
                                        "--connection-file",
                                        "{{Session.WorkingDirectory}}/connection.json",
                                        "--init-data",
                                        "file://{{Env.File.initData}}",
                                    ],
                                    "cancelation": {"mode": "NOTIFY_THEN_TERMINATE"},
                                },
                                "onExit": {
                                    "command": "BlenderAdaptor",
                                    "args": [
                                        "daemon",
                                        "stop",
                                        "--connection-file",
                                        "{{ Session.WorkingDirectory }}/connection.json",
                                    ],
                                    "cancelation": {"mode": "NOTIFY_THEN_TERMINATE"},
                                },
                            },
                        },
                    }
                ],
                "script": {
                    "embeddedFiles": [
                        {
                            "name": "runData",
                            "filename": "run-data.yaml",
                            "type": "TEXT",
                            "data": "frame: {{Task.Param.Frame}}\ncamera: '{{Task.Param.Camera}}'\n",
                        }
                    ],
                    "actions": {
                        "onRun": {
                            "command": "BlenderAdaptor",
                            "args": [
                                "daemon",
                                "run",
                                "--connection-file",
                                "{{ Session.WorkingDirectory }}/connection.json",
                                "--run-data",
                                "file://{{ Task.File.runData }}",
                            ],
                            "cancelation": {"mode": "NOTIFY_THEN_TERMINATE"},
                        }
                    },
                },
            },
            {
                "name": "layer_2",
                "parameterSpace": {
                    "taskParameterDefinitions": [
                        {"name": "Frame", "type": "INT", "range": "{{Param.Frames}}"},
                        {"name": "Camera", "type": "STRING", "range": ["Camera"]},
                    ]
                },
                "stepEnvironments": [
                    {
                        "name": "Blender",
                        "description": "Runs Blender in the background.",
                        "script": {
                            "embeddedFiles": [
                                {
                                    "name": "initData",
                                    "filename": "init-data.yaml",
                                    "type": "TEXT",
                                    "data": "scene_file: {{Param.BlenderFile}}\nrender_engine: {{Param.RenderEngine}}\nrender_scene: {{Param.RenderScene}}\nview_layer: layer_2\noutput_dir: {{Param.OutputDir}}\noutput_file_name: {{Param.OutputFileName}}\noutput_format: {{Param.OutputFormat}}\nrenderer: dummy_renderer\noutput_file_prefix: {{Param.OutputFilePrefix}}\nimage_width: {{Param.ImageWidth}}\nimage_height: {{Param.ImageHeight}}",
                                }
                            ],
                            "actions": {
                                "onEnter": {
                                    "command": "BlenderAdaptor",
                                    "args": [
                                        "daemon",
                                        "start",
                                        "--connection-file",
                                        "{{Session.WorkingDirectory}}/connection.json",
                                        "--init-data",
                                        "file://{{Env.File.initData}}",
                                    ],
                                    "cancelation": {"mode": "NOTIFY_THEN_TERMINATE"},
                                },
                                "onExit": {
                                    "command": "BlenderAdaptor",
                                    "args": [
                                        "daemon",
                                        "stop",
                                        "--connection-file",
                                        "{{ Session.WorkingDirectory }}/connection.json",
                                    ],
                                    "cancelation": {"mode": "NOTIFY_THEN_TERMINATE"},
                                },
                            },
                        },
                    }
                ],
                "script": {
                    "embeddedFiles": [
                        {
                            "name": "runData",
                            "filename": "run-data.yaml",
                            "type": "TEXT",
                            "data": "frame: {{Task.Param.Frame}}\ncamera: '{{Task.Param.Camera}}'\n",
                        }
                    ],
                    "actions": {
                        "onRun": {
                            "command": "BlenderAdaptor",
                            "args": [
                                "daemon",
                                "run",
                                "--connection-file",
                                "{{ Session.WorkingDirectory }}/connection.json",
                                "--run-data",
                                "file://{{ Task.File.runData }}",
                            ],
                            "cancelation": {"mode": "NOTIFY_THEN_TERMINATE"},
                        }
                    },
                },
            },
        ],
    }
    filled = template_filling.fill_job_template(submitter_settings, layers, host_requirements=None)
    assert filled == expected

    # Adding host requirements to the call adds them to each step.
    host_reqs = {"GPU": "1"}
    filled = template_filling.fill_job_template(
        submitter_settings, layers, host_requirements=host_reqs
    )
    for step in filled["steps"]:
        assert step["hostRequirements"] == host_reqs


def test_get_param_values(submitter_settings, common_layer_settings):
    """Test getting param values."""
    expected = {
        "BlenderFile": submitter_settings.project_path,
        common_layer_settings.frames_parameter_name: common_layer_settings.frame_range,
        "OutputFileName": common_layer_settings.output_file_prefix,
        common_layer_settings.image_width_parameter_name: common_layer_settings.image_resolution[0],
        common_layer_settings.image_height_parameter_name: common_layer_settings.image_resolution[
            1
        ],
        "OutputDir": common_layer_settings.output_directories,
        "RenderScene": common_layer_settings.scene_name,
        "RenderEngine": common_layer_settings.renderer_name,
    }
    expected = [{"name": k, "value": v} for k, v in expected.items()]

    filled = template_filling.get_parameter_values(
        submitter_settings, common_layer_settings, queue_params=[]
    )
    assert filled == expected

    # If queue params are passed, their keys should not conflict with existing keys. Expect an error if they do.
    queue_params = [
        {"name": "RenderScene", "value": common_layer_settings.scene_name + "_some_value"}
    ]
    with pytest.raises(DeadlineOperationError):
        filled = template_filling.get_parameter_values(
            submitter_settings, common_layer_settings, queue_params=queue_params
        )

    # If queue params are passed, and they don't conflict with existing keys, they should be added.
    queue_params = [{"name": "SomeParam", "value": "some_value"}]
    filled = template_filling.get_parameter_values(
        submitter_settings, common_layer_settings, queue_params=queue_params
    )
    assert filled[-1] == queue_params[0]

    # Test RezPackages resolution.
    # WHEN queue params include "deadline_cloud_for_blender"
    queue_params = [
        {
            "name": "RezPackages",
            "value": "some_other_package deadline_cloud_for_blender another_package",
        }
    ]

    # IF `settings.include_adaptor_wheels` is False > keep "deadline_cloud_for_blender" in the final template
    submitter_settings.include_adaptor_wheels = False
    filled = template_filling.get_parameter_values(
        submitter_settings, common_layer_settings, queue_params=queue_params
    )
    assert filled[-1]["value"] == "some_other_package deadline_cloud_for_blender another_package"

    # IF `settings.include_adaptor_wheels` is True > remove "deadline_cloud_for_blender"
    submitter_settings.include_adaptor_wheels = True
    filled = template_filling.get_parameter_values(
        submitter_settings, common_layer_settings, queue_params=queue_params
    )
    assert filled[-1]["value"] == "some_other_package another_package"
