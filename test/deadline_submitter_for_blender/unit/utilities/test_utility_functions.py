# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

from unittest.mock import Mock, patch

import pytest

from deadline_submitter_for_blender.utilities import utility_functions
from deadline_submitter_for_blender.utilities import submitter_operations


@patch.object(utility_functions.os, "path")
@patch.object(utility_functions, "bpy")
def test_get_assets_returns_expected(mock_bpy, mock_os_path):
    # GIVEN
    lib_path = "/path/to/lib.blend"
    img_path = "/path/to/image.png"

    data_obj = Mock(
        libraries=[Mock(filepath=lib_path, library="lib.blend")],
        images=[
            Mock(filepath=img_path, library="lib.blend"),
            Mock(filepath=None, library="lib.blend"),
        ],
        volumes=[],
        sounds=[],
        movieclips=[],
        fonts=[],
        texts=[],
        cache_files=[],
    )

    mock_bpy.data = data_obj

    mock_os_path.abspath.side_effect = [lib_path, img_path]

    # WHEN
    result = utility_functions.get_assets()

    # THEN
    assert len(result) == 2
    mock_bpy.path.abspath.call_count == 2
    mock_os_path.abspath.call_count == 2


@patch.object(utility_functions, "deadline_api")
def test_get_farms(mock_api):
    # GIVEN
    expected_farm = {
        "state": "ACTIVE",
        "farmId": "farm-1",
        "displayName": "farm 1",
        "description": "farm 1 description",
    }

    farms_response = {"farms": [expected_farm]}

    mock_api.list_farms.return_value = farms_response

    # WHEN
    result = utility_functions.get_farms()

    # THEN
    mock_api.list_farms.assert_called_once()

    assert len(result) == 1

    val_1, val_2, val_3 = result[0]
    assert val_1 == expected_farm["farmId"]
    assert val_2 == expected_farm["displayName"]
    assert val_3 == expected_farm["description"]


@patch.object(utility_functions, "deadline_api")
def test_get_queues(mock_api):
    # GIVEN
    expected_queue = {
        "state": "ACTIVE",
        "queueId": "queue-1",
        "displayName": "queue 1",
        "description": "queue 1 description",
    }

    queues_response = {"queues": [expected_queue]}

    mock_api.list_queues.return_value = queues_response

    # WHEN
    result = utility_functions.get_queues("farm-1")

    # THEN
    mock_api.list_queues.assert_called_once()

    assert len(result) == 1

    val_1, val_2, val_3 = result[0]
    assert val_1 == expected_queue["queueId"]
    assert val_2 == expected_queue["displayName"]
    assert val_3 == expected_queue["description"]


@patch.object(utility_functions, "active_profile")
@patch.object(utility_functions.bpy.context, "window_manager")
@patch.object(utility_functions, "get_queues")
@patch.object(utility_functions, "get_farms")
@patch.object(utility_functions.bpy.types, "WindowManager")
def test_set_farm_and_queue_lookups(
    mock_wm, mock_farms, mock_queues, mock_wm_context, mock_active_profile
):
    # GIVEN
    mock_wm_context.deadline_logged_in = True
    mock_active_profile.return_value = None

    returned_farms = [("farm-1", "farm", "farm")]
    returned_queues = [("queue-1", "queue", "queue")]

    mock_farms.return_value = returned_farms
    mock_queues.return_value = returned_queues

    initial_farm_lookup = Mock()
    initial_queue_lookup = Mock()

    mock_wm.deadline_farm_lookup = initial_farm_lookup
    mock_wm.deadline_queue_lookup = initial_queue_lookup

    # WHEN
    utility_functions.set_farm_and_queue_lookups()

    # THEN
    assert mock_wm.deadline_farm_lookup == returned_farms
    assert mock_wm.deadline_queue_lookup == {"farm-1": returned_queues}


@patch.object(utility_functions, "deadline_api")
def test_get_credentials_status(mock_api):
    # GIVEN
    status_name = "ALL GOOD"
    status_response = Mock()
    status_response.name = status_name

    mock_api.check_credentials_status.return_value = status_response

    # WHEN
    result = utility_functions.get_credentials_status()

    # THEN
    assert result == status_name


@patch.object(utility_functions, "deadline_api")
def test_get_credentials_type(mock_api):
    # GIVEN
    cred_type = "SSO_LOGIN"
    cred_response = Mock()
    cred_response.name = cred_type

    mock_api.get_credentials_type.return_value = cred_response

    # WHEN
    result = utility_functions.get_credentials_type()

    # THEN
    assert result == cred_type


@pytest.mark.parametrize(
    "available_response, expected_result", [(True, "AUTHORIZED"), (False, "UNAVAILABLE")]
)
@patch.object(
    utility_functions,
    "deadline_api",
)
def test_deadline_api_available(mock_api, available_response, expected_result):
    # GIVEN
    mock_api.check_deadline_api_available.return_value = available_response

    # WHEN
    result = utility_functions.get_deadline_api_available()

    # THEN
    assert result == expected_result


@patch.object(utility_functions, "active_profile")
@patch.object(utility_functions, "get_deadline_api_available")
@patch.object(utility_functions, "get_credentials_type")
@patch.object(utility_functions, "get_credentials_status")
@patch.object(utility_functions.bpy.types, "WindowManager")
@patch.object(utility_functions.bpy.context, "window_manager")
@patch.object(utility_functions, "deadline_api")
def test_deadline_logout(
    mock_api,
    mock_wm_instance,
    mock_wm_type,
    mock_get_creds,
    mock_get_type,
    mock_get_api,
    mock_active_profile,
):
    # GIVEN
    initial_farm_lookup = Mock()
    initial_queue_lookup = Mock()

    expected_creds = "NEEDS_LOGIN"
    expected_type = "SSO_LOGIN"
    expected_api_status = "UNAVAILABLE"

    mock_get_creds.return_value = expected_creds
    mock_get_type.return_value = expected_type
    mock_get_api.return_value = expected_api_status
    mock_active_profile.return_value = None

    mock_wm_type.deadline_farm_lookup = initial_farm_lookup
    mock_wm_type.deadline_queue_lookup = initial_queue_lookup

    # WHEN
    utility_functions.deadline_logout()

    # THEN
    mock_api.logout.assert_called_once()
    mock_get_creds.assert_called_once()
    mock_get_type.assert_called_once()
    mock_get_api.assert_called_once()

    assert mock_wm_instance.deadline_status == expected_creds
    assert mock_wm_instance.deadline_creds == expected_type
    assert mock_wm_instance.deadline_api_status == expected_api_status

    assert not hasattr(mock_wm_type, "deadline_farm_lookup")
    assert not hasattr(mock_wm_type, "deadline_queue_lookup")


@patch.object(utility_functions, "active_profile")
@patch.object(utility_functions, "set_farm_and_queue_lookups")
@patch.object(utility_functions, "get_deadline_api_available")
@patch.object(utility_functions, "get_credentials_type")
@patch.object(utility_functions, "get_credentials_status")
@patch.object(utility_functions, "deadline_api")
@patch.object(utility_functions.bpy, "context")
def test_deadline_login_success(
    mock_context,
    mock_api,
    mock_get_creds,
    mock_get_type,
    mock_get_api,
    mock_set_farm_queue,
    mock_active_profile,
):
    # GIVEN
    login = submitter_operations.DeadlineLogin()

    expected_creds = "AUTHENTICATED"
    expected_type = "SSO_LOGIN"
    expected_api_status = "AVAILABLE"

    mock_get_creds.return_value = expected_creds
    mock_get_type.return_value = expected_type
    mock_get_api.return_value = expected_api_status
    mock_active_profile.return_value = None

    # WHEN
    login.execute()

    # THEN
    mock_api.login.assert_called_once()
    mock_get_creds.assert_called_once()
    mock_get_type.assert_called_once()
    mock_get_api.assert_called_once()
    mock_set_farm_queue.assert_called_once()

    assert mock_context.window_manager.deadline_status == expected_creds
    assert mock_context.window_manager.deadline_creds == expected_type
    assert mock_context.window_manager.deadline_api_status == expected_api_status
    assert mock_context.window_manager.deadline_logged_in is True


@patch.object(utility_functions, "active_profile")
@patch.object(utility_functions, "set_farm_and_queue_lookups")
@patch.object(utility_functions, "get_deadline_api_available")
@patch.object(utility_functions, "get_credentials_type")
@patch.object(utility_functions, "get_credentials_status")
@patch.object(utility_functions, "deadline_api")
@patch.object(utility_functions.bpy, "context")
def test_deadline_login_failure(
    mock_context,
    mock_api,
    mock_get_creds,
    mock_get_type,
    mock_get_api,
    mock_set_farm_queue,
    mock_active_profile,
):
    mock_active_profile.return_value = None
    # GIVEN
    login_thread = submitter_operations.DeadlineLogin()

    expected_creds = "ERROR"
    mock_get_creds.return_value = expected_creds

    mock_context.window_manager.deadline_logged_in = False

    # WHEN
    login_thread.execute()

    # THEN
    mock_set_farm_queue.assert_not_called()

    assert mock_context.window_manager.deadline_status == expected_creds
    assert mock_context.window_manager.deadline_logged_in is False
