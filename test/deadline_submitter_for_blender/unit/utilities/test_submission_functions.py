# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

from unittest.mock import Mock, call, patch

import pytest

from deadline_submitter_for_blender.utilities import submission_functions


@patch.object(submission_functions, "_get_init_data_attachment")
def test_get_blender_in_background_has_expected_sections(mock_get_init):
    # GIVEN
    expected_init = "BLENDER_INIT_SECTION"
    mock_get_init.return_value = expected_init

    # WHEN
    section = submission_functions._get_blender_in_background_environment()

    # THEN
    # Check that the script attachments has all the required sections
    assert "name" in section
    assert "description" in section
    assert "script" in section

    script_section = section.get("script", {})
    assert "embeddedFiles" in script_section
    assert "actions" in script_section

    embedded_files = script_section.get("embeddedFiles", {})
    assert expected_init in embedded_files


@pytest.mark.parametrize("version_tuple, expected_string", [((3, 3, 2), "3.3.2"), ((3, 4), "3.4")])
@patch.object(submission_functions.bpy, "app")
def test_get_blender_version_string(mock_bpy_app, version_tuple, expected_string):
    # GIVEN
    mock_bpy_app.version = version_tuple

    # WHEN
    result = submission_functions._get_blender_version_string()

    # THEN
    assert result == expected_string


@pytest.mark.parametrize("version_tuple, expected_string", [((3, 3, 2), "3.3"), ((3, 4), "3.4")])
@patch.object(submission_functions.bpy, "app")
def test_get_major_minor_blender_version_string(mock_bpy_app, version_tuple, expected_string):
    # GIVEN
    mock_bpy_app.version = version_tuple

    # WHEN
    result = submission_functions._get_major_minor_blender_version_string()

    # THEN
    assert result == expected_string


@patch.object(submission_functions.bpy.context, "scene")
@patch.object(submission_functions.bpy.context, "window_manager")
def test_get_output_path_no_override(mock_wm, mock_scene):
    # GIVEN
    expected_output = "/my/output/path"

    mock_wm.deadline_override_output_path = False
    mock_scene.render.filepath = expected_output

    # WHEN
    result = submission_functions._get_output_path()

    # THEN
    assert result == expected_output


@patch.object(submission_functions.bpy.context, "window_manager")
def test_get_output_path_with_override(mock_wm):
    # GIVEN
    expected_output = "/my/output/path"

    mock_wm.deadline_override_output_path = True
    mock_wm.deadline_output_path = expected_output

    # WHEN
    result = submission_functions._get_output_path()

    # THEN
    assert result == expected_output


@patch.object(submission_functions, "_get_major_minor_blender_version_string")
@patch.object(submission_functions.bpy.context, "window_manager")
def test_get_installation_requirements_no_override(mock_wm, mock_ver):
    # GIVEN
    blender_version = 3.3
    mock_ver.return_value = "3.3"
    mock_wm.deadline_override_installation_requirements = False

    # WHEN
    result = submission_functions._get_installation_requirements()

    # THEN
    assert (
        result
        == f"{submission_functions.INSTALLATION_REQUIREMENTS_DEFAULT} blender-{blender_version}"
    )


@patch.object(submission_functions.bpy.context, "window_manager")
def test_get_installation_requirements_with_override(mock_wm):
    # GIVEN
    expected_result = "package1 package2"
    mock_wm.deadline_installation_requirements = expected_result
    mock_wm.deadline_override_installation_requirements = True

    # WHEN
    result = submission_functions._get_installation_requirements()

    # THEN
    assert result == expected_result


@patch.object(submission_functions.bpy.context, "scene")
@patch.object(submission_functions.bpy.context, "window_manager")
def test_get_frame_list_no_override(mock_wm, mock_scene):
    # GIVEN
    frame_start = 1
    frame_end = 100
    mock_scene.frame_start = frame_start
    mock_scene.frame_end = frame_end
    mock_wm.deadline_override_frame_range = False

    # WHEN
    result = submission_functions._get_frame_list()

    # THEN
    assert result == f"{frame_start}-{frame_end}"


@patch.object(submission_functions.bpy.context, "window_manager")
def test_get_frame_list_with_override(mock_wm):
    # GIVEN
    expected_result = "50-75"
    mock_wm.deadline_frame_range = expected_result
    mock_wm.deadline_override_frame_range = True

    # WHEN
    result = submission_functions._get_frame_list()

    # THEN
    assert result == expected_result


@patch.object(submission_functions.bpy.context, "window_manager")
@patch.object(submission_functions.bpy, "data")
def test_get_scene_render_engine(mock_data, mock_wm):
    # GIVEN
    expected_engine = "CYCLES"
    scene_name = "MyScene"

    mock_scene = Mock()
    mock_scene.render.engine = expected_engine

    mock_data.scenes = {scene_name: mock_scene}

    mock_wm.deadline_scene = scene_name

    # WHEN
    result = submission_functions._get_scene_render_engine()

    # THEN
    assert result == expected_engine


@patch.object(submission_functions, "_get_scene_render_engine")
@patch.object(submission_functions, "_get_blender_version_string")
@patch.object(submission_functions.bpy, "data")
def test_get_init_data_attachment_has_expected_values(mock_bpy_data, mock_ver, mock_renderer):
    # GIVEN
    expected_renderer = "CYCLES"
    expected_filepath = "/my/filepath/file.blend"
    expected_version = "3.3.3"
    mock_bpy_data.filepath = expected_filepath
    mock_ver.return_value = expected_version
    mock_renderer.return_value = expected_renderer

    # WHEN
    result = submission_functions._get_init_data_attachment()

    # THEN
    assert result["type"] == "TEXT"
    assert f"project_file: {expected_filepath}" in result.get("data", {})
    assert f"version: {expected_version}" in result.get("data", {})
    assert f"renderer: {expected_renderer}" in result.get("data", {})


@patch.object(submission_functions, "_get_output_path")
@patch.object(submission_functions.bpy.context, "window_manager")
def test_get_run_data_attachment_has_expected_values(mock_wm, mock_output_path):
    # GIVEN
    expected_output = "/test/output/path"
    expected_scene = "MyScene"
    expected_layer = "MyLayer"
    expected_animation = False

    mock_wm.deadline_scene = expected_scene
    mock_wm.deadline_layer = expected_layer
    mock_wm.deadline_render_animation = expected_animation
    mock_output_path.return_value = expected_output

    # WHEN
    result = submission_functions._get_run_data_attachment()

    # THEN
    assert result["type"] == "TEXT"
    assert f"scene: {expected_scene}" in result.get("data", {})
    assert f"layer: {expected_layer}" in result.get("data", {})
    assert "animation: false" in result.get("data", {})
    assert f"output_path: {expected_output}" in result.get("data", {})


@pytest.mark.parametrize(
    "frame_range, frame_count", [("1-100", 100), ("1-100:2", 50), ("100-1:-2", 50)]
)
def test_parse_frame_range_valid_range(frame_range, frame_count):
    # WHEN
    result = submission_functions._parse_frame_range(frame_range)

    # THEN
    assert len(result) == frame_count


def test_parse_frame_range_bad_input():
    # WHEN
    with pytest.raises(ValueError) as exc_info:
        submission_functions._parse_frame_range("bad frame range")

    # THEN
    assert str(exc_info.value) == "Frame list not valid"


@patch.object(submission_functions.os.path, "dirname")
@patch.object(submission_functions, "_get_output_path")
@patch.object(submission_functions.bpy, "path")
@patch.object(submission_functions.bpy, "data")
@patch.object(submission_functions.bpy.context, "window_manager")
def test_get_asset_references(
    mock_wm, mock_bpy_data, mock_bpy_path, mock_output_path, mock_dirname
):
    # GIVEN
    expected_filepath = "/project/file/path.blend"
    mock_bpy_data.filepath = expected_filepath

    mock_job_attachment = Mock(path="/mock/attachment/path")
    mock_wm.deadline_job_attachments = [mock_job_attachment, mock_job_attachment]

    expected_output_dir = "/path/to/output"
    mock_dirname.return_value = expected_output_dir

    expected_job_id = "job-123"
    mock_output_job = Mock()
    mock_output_job.name = expected_job_id
    mock_wm.deadline_job_output_attachments = [mock_output_job]

    # WHEN
    result = submission_functions._get_asset_references()

    # THEN
    assert "inputs" in result
    assert "outputs" in result

    filenames = result.get("inputs", {}).get("filenames", [])
    assert len(filenames) == 3
    assert expected_filepath in filenames
    assert mock_job_attachment.path in filenames

    jobs = result.get("inputs", {}).get("deadline:jobs", [])
    job_id = jobs[0].get("jobId", None)
    assert len(jobs) == 1
    assert job_id == expected_job_id

    outputs = result.get("outputs", {}).get("directories", [])
    assert expected_output_dir in outputs


@patch.object(submission_functions, "get_rez_environment")
@patch.object(submission_functions, "_get_blender_in_background_environment")
@patch.object(submission_functions, "_get_run_data_attachment")
@patch.object(submission_functions, "_get_installation_requirements")
@patch.object(submission_functions, "_parse_frame_range")
@patch.object(submission_functions, "_get_frame_list")
@patch.object(submission_functions.bpy.context, "window_manager")
def test_build_job_template(
    mock_wm,
    mock_frames,
    mock_parse_frames,
    mock_reqs,
    mock_run,
    mock_background,
    mock_rez_env,
):
    # GIVEN
    expected_job_name = "my-job"
    expected_frame_list = ["1", "2", "3"]
    expected_step_parameter_space = {
        "parameters": [{"name": "frame", "range": expected_frame_list, "type": "INT"}]
    }
    expected_installation_reqs = "package1 package2"
    expected_run = "RUN_DATA"
    expected_background = "BACKGROUND_DATA"
    expected_rez_env = "REZ_ENV_DATA"

    mock_wm.deadline_job_name = expected_job_name
    mock_parse_frames.return_value = expected_frame_list
    mock_reqs.return_value = expected_installation_reqs
    mock_run.return_value = expected_run
    mock_background.return_value = expected_background
    mock_rez_env.return_value = expected_rez_env

    mock_config = Mock()

    # WHEN
    result = submission_functions._build_job_template(mock_config)

    # THEN
    mock_background.assert_called_once()
    mock_rez_env.assert_called_once()
    mock_run.assert_called_once()

    assert "name" in result and result.get("name") == expected_job_name

    step = result.get("steps", [])[0]
    assert "parameterSpace" in step and step.get("parameterSpace") == expected_step_parameter_space

    environments = step.get("environments", {})
    assert expected_rez_env in environments
    assert expected_background in environments

    embedded_files = step.get("script", {}).get("embeddedFiles", {})
    assert expected_run in embedded_files


@patch.object(submission_functions.bpy.context, "window_manager")
def test_build_parameter_values(mock_wm):
    # GIVEN
    expected_max_retries_per_task = 1
    expected_priority = 1
    expected_max_failed_tasks_count = 1
    expected_state = "READY"

    mock_wm.deadline_max_retries_per_task = expected_max_retries_per_task
    mock_wm.deadline_priority = expected_priority
    mock_wm.deadline_max_failed_tasks_count = expected_max_failed_tasks_count
    mock_wm.deadline_submission_status = expected_state

    # WHEN
    result = submission_functions._build_parameter_values()

    # THEN
    values = result.get("parameterValues")
    assert len(values) == 4

    max_retries_per_task = values[0]
    assert (
        "name" in max_retries_per_task
        and max_retries_per_task.get("name") == "deadline:maxRetriesPerTask"
    )
    assert (
        "value" in max_retries_per_task
        and max_retries_per_task.get("value") == expected_max_retries_per_task
    )

    priority = values[1]
    assert "name" in priority and priority.get("name") == "deadline:priority"
    assert "value" in priority and priority.get("value") == expected_priority

    max_failed_tasks_count = values[2]
    assert (
        "name" in max_failed_tasks_count
        and max_failed_tasks_count.get("name") == "deadline:maxFailedTasksCount"
    )
    assert (
        "value" in max_failed_tasks_count
        and max_failed_tasks_count.get("value") == expected_max_failed_tasks_count
    )

    state = values[3]
    assert "name" in state and state.get("name") == "deadline:targetTaskRunStatus"
    assert "value" in state and state.get("value") == expected_state


@patch.object(submission_functions, "json")
@patch.object(submission_functions, "_get_asset_references")
@patch.object(submission_functions, "_build_parameter_values")
@patch.object(submission_functions, "_build_job_template")
@patch("builtins.open")
def test_build_submission(mock_open, mock_jobs, mock_params, mock_assets, mock_json):
    # GIVEN
    mock_config = Mock()
    job_bundle_dir = "/path/to/dir"

    # WHEN
    submission_functions.build_submission(job_bundle_dir, mock_config)

    # THEN
    mock_jobs.assert_called_once_with(mock_config)
    mock_params.assert_called_once()
    mock_assets.assert_called_once()

    assert mock_open.call_count == 3
    assert mock_json.dump.call_count == 3


@patch.object(submission_functions, "_rename_AmazonDeadlineCliAccess_sections")
@patch.object(submission_functions, "active_profile")
@patch.object(submission_functions, "ConfigParser")
@patch.object(submission_functions, "config")
@patch.object(submission_functions.bpy.context, "window_manager")
def test_build_config(mock_wm, mock_config, mock_cp_const, mock_active_profile, mock_rename):
    # GIVEN
    expected_farm = "my-farm"
    mock_wm.deadline_farm = expected_farm

    expected_queue = "my-queue"
    mock_wm.deadline_queue = expected_queue

    mock_config_parser = Mock()
    mock_cp_const.return_value = mock_config_parser

    expected_calls = [
        call("defaults.farm_id", expected_farm, mock_config_parser),
        call("defaults.queue_id", expected_queue, mock_config_parser),
    ]

    # WHEN
    result = submission_functions.build_config()

    # THEN
    mock_config.set_setting.assert_has_calls(expected_calls)

    assert result == mock_config_parser
