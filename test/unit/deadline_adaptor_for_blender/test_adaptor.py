# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

from __future__ import annotations
from unittest.mock import Mock, patch
import pytest

from deadline.blender_adaptor.BlenderAdaptor import BlenderAdaptor


@pytest.fixture()
def init_data() -> dict:
    """
    Pytest Fixture to return an init_data dictionary that passes validation

    Returns:
        dict: An init_data dictionary
    """
    return {
        "scene_file": "C:\\This\\Is\\A\\Path\\test.blend",
        "render_engine": "cycles",
    }


class TestBlenderAdaptor:
    handle_progess_params = [
        pytest.param(
            0,
            "Fra:2 Mem:48.09M (Peak 48.09M) | Time:00:03.01 | Remaining:00:13.01 | Mem:38.37M, Peak:38.37M | Scene, ViewLayer | Sample 768/4096",
            18,
            id="TestCyclesProgressReporting",
        ),
        pytest.param(
            1,
            "Fra:1 Mem:43.82M (Peak 44.36M) | Time:00:00.28 | Rendering 17 / 64 samples",
            26,
            id="TestEeveeProgressReporting",
        ),
    ]

    @pytest.mark.parametrize("regex_index, stdout, expected_progress", handle_progess_params)
    @patch("deadline.blender_adaptor.BlenderAdaptor.BlenderAdaptor.update_status")
    def test_handle_progress(
        self,
        mock_update_status: Mock,
        regex_index: int,
        stdout: str,
        expected_progress: float,
        init_data: dict,
    ) -> None:
        """Tests that the _handle_progress method updates the progress correctly"""
        # GIVEN
        adaptor = BlenderAdaptor(init_data)
        regex_callbacks = adaptor._get_regex_callbacks()
        progress_regex = regex_callbacks[1].regex_list[regex_index]

        # WHEN
        match = progress_regex.search(stdout)
        assert match is not None
        adaptor._handle_progress(match)

        # THEN
        mock_update_status.assert_called_once_with(progress=expected_progress)
