# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

from __future__ import annotations

from unittest.mock import patch, MagicMock

from deadline.client.api import UpdateCheckResult, UpdateCheckStatus

from deadline.blender_submitter.addons.deadline_cloud_blender_submitter.update_utils import (
    _check_for_update,
    check_and_show_update_dialog,
)


class TestCheckForUpdate:
    """Tests for _check_for_update()."""

    @patch(
        "deadline.blender_submitter.addons.deadline_cloud_blender_submitter.update_utils.safe_check_for_updates"
    )
    def test_returns_result_on_success(self, mock_check):
        # GIVEN
        expected = UpdateCheckResult(
            status=UpdateCheckStatus.SUCCESS,
            current_version="0.9.0",
            update_available=True,
            latest_version="0.10.0",
        )
        mock_check.return_value = expected

        # WHEN
        result = _check_for_update()

        # THEN
        assert result is expected
        mock_check.assert_called_once()

    @patch(
        "deadline.blender_submitter.addons.deadline_cloud_blender_submitter.update_utils.safe_check_for_updates"
    )
    def test_returns_error_result_on_unexpected_error(self, mock_check):
        # GIVEN — safe_check_for_updates returns an error result, never raises
        expected = UpdateCheckResult(
            status=UpdateCheckStatus.UNEXPECTED_ERROR,
            current_version="0.9.0",
            error_message="Unexpected error: something broke",
        )
        mock_check.return_value = expected

        # WHEN
        result = _check_for_update()

        # THEN
        assert result is expected
        assert result.update_available is False

    @patch(
        "deadline.blender_submitter.addons.deadline_cloud_blender_submitter.update_utils.safe_check_for_updates"
    )
    def test_passes_correct_integration_name(self, mock_check):
        # GIVEN
        mock_check.return_value = UpdateCheckResult(
            status=UpdateCheckStatus.SUCCESS,
            current_version="0.9.0",
        )

        # WHEN
        _check_for_update()

        # THEN
        call_kwargs = mock_check.call_args[1]
        assert call_kwargs["integration_name"] == "deadline-cloud-for-blender"


class TestCheckAndShowUpdateDialog:
    """Tests for check_and_show_update_dialog()."""

    @patch(
        "deadline.blender_submitter.addons.deadline_cloud_blender_submitter.update_utils._check_for_update"
    )
    def test_returns_false_when_no_update(self, mock_check):
        # GIVEN
        mock_check.return_value = UpdateCheckResult(
            status=UpdateCheckStatus.SUCCESS,
            current_version="0.10.0",
            update_available=False,
        )

        # WHEN
        result = check_and_show_update_dialog()

        # THEN
        assert result is False

    @patch(
        "deadline.blender_submitter.addons.deadline_cloud_blender_submitter.update_utils._check_for_update"
    )
    def test_returns_false_on_error_status(self, mock_check):
        # GIVEN
        mock_check.return_value = UpdateCheckResult(
            status=UpdateCheckStatus.NETWORK_ERROR,
            current_version="0.9.0",
            update_available=False,
        )

        # WHEN
        result = check_and_show_update_dialog()

        # THEN
        assert result is False

    @patch(
        "deadline.blender_submitter.addons.deadline_cloud_blender_submitter.update_utils.UpdateAvailableDialog"
    )
    @patch(
        "deadline.blender_submitter.addons.deadline_cloud_blender_submitter.update_utils._check_for_update"
    )
    def test_shows_dialog_and_returns_true_when_user_downloads(self, mock_check, mock_dialog_cls):
        # GIVEN
        mock_check.return_value = UpdateCheckResult(
            status=UpdateCheckStatus.SUCCESS,
            current_version="0.9.0",
            update_available=True,
            latest_version="0.10.0",
            download_url="https://example.com/installer",
        )
        mock_dialog = MagicMock()
        mock_dialog.user_downloaded = True
        mock_dialog_cls.return_value = mock_dialog

        # WHEN
        result = check_and_show_update_dialog()

        # THEN
        assert result is True
        mock_dialog.exec_.assert_called_once()

    @patch(
        "deadline.blender_submitter.addons.deadline_cloud_blender_submitter.update_utils.UpdateAvailableDialog"
    )
    @patch(
        "deadline.blender_submitter.addons.deadline_cloud_blender_submitter.update_utils._check_for_update"
    )
    def test_shows_dialog_and_returns_false_when_user_dismisses(self, mock_check, mock_dialog_cls):
        # GIVEN
        mock_check.return_value = UpdateCheckResult(
            status=UpdateCheckStatus.SUCCESS,
            current_version="0.9.0",
            update_available=True,
            latest_version="0.10.0",
            download_url="https://example.com/installer",
        )
        mock_dialog = MagicMock()
        mock_dialog.user_downloaded = False
        mock_dialog_cls.return_value = mock_dialog

        # WHEN
        result = check_and_show_update_dialog()

        # THEN
        assert result is False
        mock_dialog.exec_.assert_called_once()
