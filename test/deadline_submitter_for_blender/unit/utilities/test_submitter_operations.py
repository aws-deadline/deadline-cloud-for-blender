# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest

from deadline_submitter_for_blender.utilities import submitter_operations

BLENDER_FINISHED_RESPONSE = {"FINISHED"}


@patch.object(submitter_operations, "deadline_login")
def test_deadline_login(mock_login):
    # GIVEN
    bea_login = submitter_operations.DeadlineLogin()

    # WHEN
    response = bea_login.execute()

    # THEN
    assert response == BLENDER_FINISHED_RESPONSE
    mock_login.assert_called_once()


@patch.object(submitter_operations, "deadline_logout")
def test_deadline_logout(mock_logout):
    # GIVEN
    bea_logout = submitter_operations.DeadlineLogout()

    # WHEN
    response = bea_logout.execute()

    # THEN
    assert response == BLENDER_FINISHED_RESPONSE
    mock_logout.assert_called_once()


def test_deadline_set_project_path():
    # GIVEN
    expected_dir = "/my/file"
    mock_context = Mock()
    mock_context.blend_data.filepath = expected_dir + "/" + "path.blend"
    bea_set_path = submitter_operations.DeadlineSetProjectPath()

    # WHEN
    response = bea_set_path.execute(mock_context)

    # Then
    assert response == BLENDER_FINISHED_RESPONSE
    assert mock_context.window_manager.deadline_project_path == expected_dir


@pytest.mark.parametrize(
    "job_name, logged_in, expected_result",
    [("job", True, True), ("job", False, False), ("", True, False)],
)
def test_deadline_submit_poll(job_name, logged_in, expected_result):
    # GIVEN
    mock_context = Mock()
    mock_context.window_manager.deadline_job_name = job_name
    mock_context.window_manager.deadline_logged_in = logged_in

    bea_submit = submitter_operations.DeadlineSubmit()

    # WHEN
    response = bea_submit.poll(mock_context)

    # THEN
    assert response == expected_result


@pytest.mark.parametrize(
    "render_engine, expected_result",
    [("CYCLES", False), ("BLENDER_EEVEE", True)],
)
@patch.object(submitter_operations.bpy, "data")
def test_deadline_submit_uses_eevee(mock_data, render_engine, expected_result):
    # GIVEN
    scene_name = "MyScene"
    mock_context = Mock()
    mock_context.window_manager.deadline_scene = "MyScene"

    mock_scene = Mock()
    mock_scene.render.engine = render_engine
    mock_data.scenes = {scene_name: mock_scene}

    bea_submit = submitter_operations.DeadlineSubmit()

    # WHEN
    result = bea_submit.uses_eevee(mock_context)

    # THEN
    assert result == expected_result


@patch.object(submitter_operations, "SubmitBackgroundThread")
@patch.object(submitter_operations, "build_submission")
@patch.object(submitter_operations, "build_config")
@patch.object(submitter_operations.bpy, "ops")
def test_deadline_submit_execute(
    mock_bpy_ops, mock_build_config, mock_build_submission, mock_submit
):
    # GIVEN
    expected_project_path = "/path/to/project.blend"

    mock_context = Mock()
    mock_context.window_manager.deadline_project_path = expected_project_path

    mock_config = Mock()
    mock_build_config.return_value = mock_config

    bea_submit = submitter_operations.DeadlineSubmit()

    # WHEN
    response = bea_submit.execute(mock_context)

    # THEN
    mock_bpy_ops.deadline.set_project_path.assert_not_called()
    mock_build_config.assert_called_once()
    mock_build_submission.assert_called_once_with(expected_project_path, mock_config)
    mock_submit.assert_called_once_with(expected_project_path, mock_config)

    assert response == BLENDER_FINISHED_RESPONSE


def test_build_data():
    # GIVEN
    mock_context = Mock()
    mock_context.window_manager.deadline_job_name = "my-job"
    mock_context.window_manager.deadline_job_description = "A test job"
    mock_context.window_manager.deadline_farm = "farm-1"
    mock_context.window_manager.deadline_queue = "queue-1"
    mock_context.window_manager.deadline_submission_status = "READY"
    mock_context.window_manager.deadline_max_retries_per_task = 1
    mock_context.window_manager.deadline_priority = 4
    mock_context.window_manager.deadline_max_failed_tasks_count = 1
    mock_context.window_manager.deadline_override_installation_requirements = True
    mock_context.window_manager.deadline_installation_requirements = "package1 package2"
    mock_context.window_manager.deadline_scene = "Scene"
    mock_context.window_manager.deadline_layer = "ViewLayer"
    mock_context.window_manager.deadline_project_path = "/path/to/project.blend"
    mock_context.window_manager.deadline_override_output_path = False
    mock_context.window_manager.deadline_output_path = ""
    mock_context.window_manager.deadline_render_animation = True
    mock_context.window_manager.deadline_override_frame_range = True
    mock_context.window_manager.deadline_frame_range = "1-10"
    mock_context.window_manager.deadline_job_attachments_index = 1
    mock_context.window_manager.deadline_job_attachments = [
        Mock(name="asset1.png", path="/path/to/asset1.png"),
        Mock(name="asset2.txt", path="/a/new/path/to/asset2.txt"),
    ]
    mock_context.window_manager.deadline_user_job_attachments_index = 0
    mock_context.window_manager.deadline_user_job_attachments = []
    mock_context.window_manager.deadline_job_output_attachments_index = 0
    mock_context.window_manager.deadline_job_output_attachments = [Mock(name="job-1")]

    bea_export = submitter_operations.DeadlineExport()

    # WHEN
    response = bea_export.build_data(mock_context)

    # THEN
    assert response["deadline_job_name"] == mock_context.window_manager.deadline_job_name
    assert (
        response["deadline_job_description"] == mock_context.window_manager.deadline_job_description
    )
    assert response["deadline_farm"] == mock_context.window_manager.deadline_farm
    assert response["deadline_queue"] == mock_context.window_manager.deadline_queue
    assert (
        response["deadline_submission_status"]
        == mock_context.window_manager.deadline_submission_status
    )
    assert (
        response["deadline_max_retries_per_task"]
        == mock_context.window_manager.deadline_max_retries_per_task
    )
    assert response["deadline_priority"] == mock_context.window_manager.deadline_priority
    assert (
        response["deadline_max_failed_tasks_count"]
        == mock_context.window_manager.deadline_max_failed_tasks_count
    )
    assert (
        response["deadline_override_installation_requirements"]
        == mock_context.window_manager.deadline_override_installation_requirements
    )
    assert (
        response["deadline_installation_requirements"]
        == mock_context.window_manager.deadline_installation_requirements
    )
    assert response["deadline_scene"] == mock_context.window_manager.deadline_scene
    assert response["deadline_layer"] == mock_context.window_manager.deadline_layer
    assert response["deadline_project_path"] == mock_context.window_manager.deadline_project_path
    assert (
        response["deadline_override_output_path"]
        == mock_context.window_manager.deadline_override_output_path
    )
    assert response["deadline_output_path"] == mock_context.window_manager.deadline_output_path
    assert (
        response["deadline_render_animation"]
        == mock_context.window_manager.deadline_render_animation
    )
    assert (
        response["deadline_override_frame_range"]
        == mock_context.window_manager.deadline_override_frame_range
    )
    assert response["deadline_frame_range"] == mock_context.window_manager.deadline_frame_range
    assert (
        response["deadline_job_attachments_index"]
        == mock_context.window_manager.deadline_job_attachments_index
    )
    assert len(response["deadline_job_attachments"]) == len(
        mock_context.window_manager.deadline_job_attachments
    )
    assert (
        response["deadline_user_job_attachments_index"]
        == mock_context.window_manager.deadline_user_job_attachments_index
    )
    assert len(response["deadline_user_job_attachments"]) == len(
        mock_context.window_manager.deadline_user_job_attachments
    )
    assert (
        response["deadline_job_output_attachments_index"]
        == mock_context.window_manager.deadline_job_output_attachments_index
    )
    assert len(response["deadline_job_output_attachments"]) == len(
        mock_context.window_manager.deadline_job_output_attachments
    )


@patch.object(submitter_operations.bpy, "ops")
def test_create_settings(mock_bpy_ops):
    # GIVEN
    mock_context = Mock()
    expected_job_name = "job name"
    expected_job_description = "job description"

    test_data = {
        "deadline_job_name": expected_job_name,
        "deadline_job_description": expected_job_description,
        "deadline_scene": "MyScene",
        "deadline_layer": "ViewLayer",
        "deadline_farm": "",
        "deadline_queue": "",
        "deadline_job_attachments": [{"name": "asset1", "path": "/path/asset1"}],
        "deadline_user_job_attachments": [{"name": "asset2", "path": "/path/asset2"}],
        "deadline_job_output_attachments": [],
    }

    bea_import = submitter_operations.DeadlineImport()

    # WHEN
    bea_import.create_settings(mock_context, test_data)

    # THEN
    assert mock_context.window_manager.deadline_job_name == expected_job_name
    assert mock_context.window_manager.deadline_job_description == expected_job_description

    mock_bpy_ops.deadline.clear_assets.assert_called_once()
    mock_bpy_ops.deadline.add_assets.assert_called_once()

    mock_bpy_ops.deadline.clear_user_assets.assert_called_once()
    mock_bpy_ops.deadline.add_user_assets.assert_called_once()

    mock_bpy_ops.deadline.clear_job_output_attachments.assert_called_once()
    mock_bpy_ops.deadline.add_job_output_attachments.assert_not_called()


@pytest.mark.parametrize(
    "filepath, expected_response",
    [("/path/to/file.txt", BLENDER_FINISHED_RESPONSE), (None, BLENDER_FINISHED_RESPONSE)],
)
@patch.object(submitter_operations.bpy, "ops")
def test_import_prompt_execute(mock_bpy_ops, filepath, expected_response):
    # GIVEN
    bea_import_prompt = submitter_operations.DeadlineImportPrompt()

    # WHEN
    response = bea_import_prompt.execute(filepath)

    # THEN
    assert response == expected_response

    if filepath:
        mock_bpy_ops.deadline.do_import.assert_called_once_with(filepath=filepath)


@pytest.mark.parametrize(
    "expected_name, expected_path",
    [("file.txt", "/path/to/file.txt"), ("", None)],
)
@patch.object(submitter_operations, "len")
def test_add_assets_execute(mock_len, expected_name, expected_path):
    # GIVEN
    mock_context = Mock()
    mock_attachment = Mock()

    mock_context.window_manager.deadline_job_attachments.add = Mock(return_value=mock_attachment)
    mock_len.return_value = 3

    bea_add_assets = submitter_operations.DeadlineAddAssets()

    # WHEN
    response = bea_add_assets.execute(mock_context, expected_name, expected_path)

    # THEN
    if not expected_name == "":
        assert mock_attachment.name == expected_name
        assert mock_attachment.path == expected_path
    else:
        mock_context.window_manager.deadline_job_attachments.add.assert_not_called()

    assert response == BLENDER_FINISHED_RESPONSE


@pytest.mark.parametrize(
    "expected_assets",
    [(["/path/to/item1", "/path/to/item2", "/path/to/item3"]), ([])],
)
@patch.object(submitter_operations, "get_assets")
@patch.object(submitter_operations.bpy, "path")
@patch.object(submitter_operations.bpy, "ops")
def test_parse_assets_execute(mock_bpy_ops, mock_bpy_path, mock_get_assets, expected_assets):
    # GIVEN
    mock_get_assets.return_value = expected_assets

    bea_parse_assets = submitter_operations.DeadlineParseAssets()

    # WHEN
    response = bea_parse_assets.execute()

    # THEN
    mock_bpy_ops.deadline.clear_assets.assert_called_once()
    mock_get_assets.assert_called_once()
    assert mock_bpy_ops.deadline.add_assets.call_count == len(expected_assets)
    assert response == BLENDER_FINISHED_RESPONSE


def test_clear_assets_execute():
    # GIVEN
    mock_context = Mock()

    bea_clear_assets = submitter_operations.DeadlineClearAssets()

    # WHEN
    response = bea_clear_assets.execute(mock_context)

    # THEN
    assert response == BLENDER_FINISHED_RESPONSE

    mock_context.window_manager.deadline_job_attachments.clear.assert_called_once()
    assert mock_context.window_manager.deadline_job_attachments_index == 0


def test_clear_user_assets_execute():
    # GIVEN
    mock_context = Mock()

    bea_clear_assets = submitter_operations.DeadlineClearUserAssets()

    # WHEN
    response = bea_clear_assets.execute(mock_context)

    # THEN
    assert response == BLENDER_FINISHED_RESPONSE

    mock_context.window_manager.deadline_user_job_attachments.clear.assert_called_once()
    assert mock_context.window_manager.deadline_user_job_attachments_index == 0


@pytest.mark.parametrize(
    "expected_name, expected_path",
    [("file.txt", "/path/to/file.txt"), ("", None)],
)
@patch.object(submitter_operations, "len")
def test_add_user_assets_execute(mock_len, expected_name, expected_path):
    # GIVEN
    mock_context = Mock()
    mock_attachment = Mock()

    mock_context.window_manager.deadline_user_job_attachments.add = Mock(
        return_value=mock_attachment
    )
    mock_len.return_value = 3

    bea_add_assets = submitter_operations.DeadlineAddUserAssets()

    # WHEN
    response = bea_add_assets.execute(mock_context, expected_name, expected_path)

    # THEN
    if not expected_name == "":
        assert mock_attachment.name == expected_name
        assert mock_attachment.path == expected_path
    else:
        mock_context.window_manager.deadline_user_job_attachments.add.assert_not_called()

    assert response == BLENDER_FINISHED_RESPONSE


@pytest.mark.parametrize(
    "files_names, directory, expected_response",
    [
        (
            ["file.txt", "file2.txt"],
            "/path/to/",
            BLENDER_FINISHED_RESPONSE,
        ),
        ([], "/path/to/", BLENDER_FINISHED_RESPONSE),
    ],
)
@patch.object(submitter_operations.bpy, "path")
@patch.object(submitter_operations.bpy, "ops")
def test_user_file_selector_execute(
    mock_bpy_ops, mock_bpy_path, files_names, directory, expected_response
):
    # GIVEN
    bea_user_file_selector = submitter_operations.DeadlineUserFileSelector()

    # name is an argument of MagicMock's constructor, so it can only be set after
    # the MagicMock is already created
    files = [MagicMock(definitely_not_name=name) for name in files_names]
    for file in files:
        file.name = file.definitely_not_name

    # WHEN
    response = bea_user_file_selector.execute(files, directory)

    # THEN
    assert response == expected_response

    if len(files) > 0:
        directory_path = Path(directory)
        mock_bpy_ops.deadline.add_user_assets.assert_any_call(
            name=files[0].name, path=str(directory_path / files[0].name)
        )
        mock_bpy_ops.deadline.add_user_assets.assert_any_call(
            name=files[1].name, path=str(directory_path / files[1].name)
        )
    else:
        mock_bpy_ops.deadline.add_user_assets.assert_not_called()


@pytest.mark.parametrize(
    "curr_index, num_attachments",
    [
        (2, 3),
        (1, 3),
    ],
)
@patch.object(submitter_operations, "len")
def test_remove_assets_execute(mock_len, curr_index, num_attachments):
    # GIVEN
    mock_context = Mock()
    mock_context.window_manager.deadline_job_attachments_index = curr_index

    mock_len.side_effect = [num_attachments - 1, num_attachments - 2]

    bea_remove_assets = submitter_operations.DeadlineRemoveAssets()

    # WHEN
    response = bea_remove_assets.execute(mock_context)

    # THEN
    assert response == BLENDER_FINISHED_RESPONSE
    mock_context.window_manager.deadline_job_attachments.remove.assert_called_once_with(curr_index)


@pytest.mark.parametrize(
    "curr_index, num_attachments",
    [
        (2, 3),
        (1, 3),
    ],
)
@patch.object(submitter_operations, "len")
def test_remove_user_assets_execute(mock_len, curr_index, num_attachments):
    # GIVEN
    mock_context = Mock()
    mock_context.window_manager.deadline_user_job_attachments_index = curr_index

    mock_len.side_effect = [num_attachments - 1, num_attachments - 2]

    bea_remove_assets = submitter_operations.DeadlineRemoveUserAssets()

    # WHEN
    response = bea_remove_assets.execute(mock_context)

    # THEN
    assert response == BLENDER_FINISHED_RESPONSE
    mock_context.window_manager.deadline_user_job_attachments.remove.assert_called_once_with(
        curr_index
    )


@pytest.mark.parametrize(
    "expected_name",
    [("job-123"), ("")],
)
@patch.object(submitter_operations, "len")
def test_add_job_outputs_execute(mock_len, expected_name):
    # GIVEN
    mock_context = Mock()
    mock_attachment = Mock()

    mock_context.window_manager.deadline_job_output_attachments.add = Mock(
        return_value=mock_attachment
    )
    mock_len.return_value = 3

    bea_add_job_output = submitter_operations.DeadlineJobOutputAddAttachments()

    # WHEN
    response = bea_add_job_output.execute(mock_context, expected_name)

    # THEN
    if not expected_name == "":
        assert mock_attachment.name == expected_name
    else:
        mock_context.window_manager.deadline_job_output_attachments.add.assert_not_called()

    assert response == BLENDER_FINISHED_RESPONSE


@pytest.mark.parametrize(
    "curr_index, num_attachments",
    [
        (2, 3),
        (1, 3),
    ],
)
@patch.object(submitter_operations, "len")
def test_remove_job_outputs_execute(mock_len, curr_index, num_attachments):
    # GIVEN
    mock_context = Mock()
    mock_context.window_manager.deadline_job_output_attachments_index = curr_index

    mock_len.side_effect = [num_attachments - 1, num_attachments - 2]

    bea_remove_job_outputs = submitter_operations.DeadlineJobOutputRemoveAttachments()

    # WHEN
    response = bea_remove_job_outputs.execute(mock_context)

    # THEN
    assert response == BLENDER_FINISHED_RESPONSE
    mock_context.window_manager.deadline_job_output_attachments.remove.assert_called_once_with(
        curr_index
    )


def test_clear_job_output_attachments_execute():
    # GIVEN
    mock_context = Mock()

    bea_clear_assets = submitter_operations.DeadlineClearJobOutputs()

    # WHEN
    response = bea_clear_assets.execute(mock_context)

    # THEN
    assert response == BLENDER_FINISHED_RESPONSE

    mock_context.window_manager.deadline_job_output_attachments.clear.assert_called_once()
    assert mock_context.window_manager.deadline_job_output_attachments_index == 0
