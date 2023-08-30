# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

from unittest.mock import Mock, patch

from deadline_submitter_for_blender.data_classes import submitter_properties


@patch.object(submitter_properties.bpy.types, "WindowManager")
def test_farm_callback_has_farms(mock_wm):
    # GIVEN
    farms = [("Farm1", "Farm1", "Farm1")]
    mock_wm.deadline_farm_lookup = farms

    # WHEN
    result = submitter_properties.farm_callback(None, None)

    # THEN
    assert result == farms


@patch.object(submitter_properties.bpy.types, "WindowManager")
def test_farm_callback_has_no_farms(mock_wm):
    # GIVEN
    del mock_wm.deadline_farm_lookup

    # WHEN
    result = submitter_properties.farm_callback(None, None)

    # THEN
    assert result == ()


@patch.object(submitter_properties.bpy.types, "WindowManager")
def test_queue_callback_has_queues(mock_wm_type):
    # GIVEN
    queues = [("queue1", "queue1", "queue1")]

    mock_wm_context = Mock()
    mock_wm_context.deadline_farm = "farm1"
    mock_context = Mock()
    mock_context.window_manager = mock_wm_context

    mock_wm_type.deadline_queue_lookup = {"farm1": queues}

    # WHEN
    result = submitter_properties.queue_callback(None, mock_context)

    # THEN
    assert result == queues


@patch.object(submitter_properties.bpy.types, "WindowManager")
def test_queue_callback_has_no_queues(mock_wm_type):
    # GIVEN
    mock_context = Mock()
    del mock_wm_type.deadline_queue_lookup

    # WHEN
    result = submitter_properties.queue_callback(None, mock_context)

    # THEN
    assert result == ()


@patch.object(submitter_properties.bpy.types, "WindowManager")
def test_storage_profile_callback_has_storage_profiles(mock_wm_type):
    # GIVEN
    storage_profiles = [("sp1", "sp2", "sp3")]

    mock_wm_context = Mock()
    mock_wm_context.deadline_farm = "farm1"
    mock_wm_context.deadline_queue = "queue1"
    mock_context = Mock()
    mock_context.window_manager = mock_wm_context

    mock_wm_type.deadline_storage_profile_lookup = {("farm1", "queue1"): storage_profiles}

    # WHEN
    result = submitter_properties.storage_profile_callback(None, mock_context)

    # THEN
    assert result == storage_profiles


@patch.object(submitter_properties.bpy.types, "WindowManager")
def test_storage_profile_callback_has_no_storage_profiles(mock_wm_type):
    # GIVEN
    mock_context = Mock()
    del mock_wm_type.deadline_storage_profile_lookup

    # WHEN
    result = submitter_properties.storage_profile_callback(None, mock_context)

    # THEN
    assert result == ()


def test_submission_status_callback():
    # GIVEN
    submission_statuses = (
        ("READY", "Ready", "Ready"),
        ("PAUSED", "Paused", "Paused"),
    )

    # WHEN
    result = submitter_properties.submission_status_callback(None, None)

    # THEN
    assert result == submission_statuses


@patch.object(submitter_properties.bpy, "data")
def test_scene_callback_returns_expected_tuple(mock_bpy_data):
    # GIVEN
    mock_scene = Mock()
    mock_scene.name = "MyScene"
    mock_scene.name_full = "MyScene [MyLib]"

    mock_bpy_data.scenes = [mock_scene]

    # WHEN
    result = submitter_properties.scene_callback(None, None)

    # THEN
    assert len(result) == 1
    assert result[0] == (mock_scene.name, mock_scene.name, mock_scene.name_full)


@patch.object(submitter_properties.bpy, "data")
def test_scene_callback_can_return_multiples(mock_bpy_data):
    # GIVEN
    mock_scene = Mock()

    mock_bpy_data.scenes = [mock_scene, mock_scene, mock_scene]

    # WHEN
    result = submitter_properties.scene_callback(None, None)

    # THEN
    assert len(result) == 3


@patch.object(submitter_properties.bpy, "data")
def test_scene_callback_can_return_none(mock_bpy_data):
    # GIVEN
    mock_bpy_data.scenes = []

    # WHEN
    result = submitter_properties.scene_callback(None, None)

    # THEN
    assert len(result) == 0


@patch.object(submitter_properties.bpy, "data")
def test_layer_callback_returns_expected_tuple(mock_bpy_data):
    # GIVEN
    mock_wm_context = Mock(deadline_scene="MyScene")
    mock_context = Mock(window_manager=mock_wm_context)

    mock_layer = Mock(name="MyLayer")
    mock_scene = Mock(view_layers=[mock_layer])
    mock_bpy_data.scenes = {"MyScene": mock_scene}

    # WHEN
    result = submitter_properties.layer_callback(None, mock_context)

    # THEN
    assert len(result) == 1
    assert result[0] == (mock_layer.name, mock_layer.name, mock_layer.name)


@patch.object(submitter_properties.bpy, "data")
def test_layer_callback_can_return_multiples(mock_bpy_data):
    # GIVEN
    mock_wm_context = Mock(deadline_scene="MyScene")
    mock_context = Mock(window_manager=mock_wm_context)

    mock_layer = Mock()
    mock_scene = Mock(view_layers=[mock_layer, mock_layer, mock_layer, mock_layer])
    mock_bpy_data.scenes = {"MyScene": mock_scene}

    # WHEN
    result = submitter_properties.layer_callback(None, mock_context)

    # THEN
    assert len(result) == 4


@patch.object(submitter_properties.bpy, "data")
def test_layer_callback_can_return_none(mock_bpy_data):
    # GIVEN
    mock_wm_context = Mock(deadline_scene="MyScene")
    mock_context = Mock(window_manager=mock_wm_context)

    mock_scene = Mock(view_layers=[])
    mock_bpy_data.scenes = {"MyScene": mock_scene}

    # WHEN
    result = submitter_properties.layer_callback(None, mock_context)

    # THEN
    assert len(result) == 0
