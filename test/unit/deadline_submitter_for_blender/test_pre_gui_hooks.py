# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

"""Unit tests for the Blender submitter's pre-GUI hook integration.

``create_deadline_dialog`` calls deadline-cloud's ``run_pre_gui_hooks`` (env-only, since Blender
has no on-disk bundle) and then maps the merged output with deadline-cloud's generic
``apply_pre_gui_output``. The full submitter needs a running Blender, so it is exercised in the
integration suite; here we verify the DCC-owned pieces headless:

* ``apply_pre_gui_output`` routes hook output correctly against Blender's own
  ``BlenderSubmitterUISettings`` — which has no ``.parameters`` list, so every hook parameter must
  land in the shared parameter values. This guards against a regression where
  ``BlenderSubmitterUISettings`` gains a ``parameters`` attribute that would misroute hook params.
* ``_pre_gui_hook_confirm_callback`` honours the ``settings.auto_accept`` setting.

The bpy / qtpy modules are stubbed by the package ``__init__`` so imports resolve.
"""

from unittest.mock import patch

from deadline.client.ui.pre_gui_hooks import apply_pre_gui_output
from deadline.blender_submitter.addons.deadline_cloud_blender_submitter.template_filling import (
    BlenderSubmitterUISettings,
)
from deadline.blender_submitter.addons.deadline_cloud_blender_submitter import (
    open_deadline_cloud_dialog,
)


def _settings() -> BlenderSubmitterUISettings:
    s = BlenderSubmitterUISettings()
    s.name = "Original"
    s.description = ""
    return s


def test_name_and_description_applied_to_settings():
    """A hook's name/description overwrite the settings fields (Blender has no .parameters list,
    so these land directly on the dataclass)."""
    settings = _settings()
    shared = {"RezPackages": "blender-4.2 deadline_cloud_for_blender"}

    apply_pre_gui_output({"name": "PREGUI RAN", "description": "from pipeline"}, settings, shared)

    assert settings.name == "PREGUI RAN"
    assert settings.description == "from pipeline"


def test_hook_parameters_routed_to_shared_values():
    """BlenderSubmitterUISettings has no .parameters list, so every hook parameter (queue params,
    deadline: properties) is routed into the shared values the dialog is seeded with, overriding
    the Blender-computed defaults on key collision."""
    settings = _settings()
    shared = {
        "RezPackages": "blender-4.2 deadline_cloud_for_blender",
        "CondaPackages": "blender=4.2.*",
    }

    apply_pre_gui_output(
        {
            "parameters": {
                "deadline:priority": 88,
                "RezPackages": "blender-4.2 custom_pkg",  # overrides the default
            }
        },
        settings,
        shared,
    )

    assert shared["deadline:priority"] == 88
    assert shared["RezPackages"] == "blender-4.2 custom_pkg"
    assert shared["CondaPackages"] == "blender=4.2.*"  # untouched keys preserved


def test_empty_output_is_a_noop():
    """No pre-GUI hook output leaves the settings and shared values unchanged."""
    settings = _settings()
    shared = {"RezPackages": "pkg"}

    apply_pre_gui_output({}, settings, shared)

    assert settings.name == "Original"
    assert settings.description == ""
    assert shared == {"RezPackages": "pkg"}


def test_partial_output_only_touches_present_keys():
    """Only the keys present in the output are applied; others keep their prior values."""
    settings = _settings()
    settings.description = "keep me"
    shared: dict = {}

    apply_pre_gui_output({"name": "NewName"}, settings, shared)

    assert settings.name == "NewName"
    assert settings.description == "keep me"  # not overwritten
    assert shared == {}  # no parameters in output


@patch.object(open_deadline_cloud_dialog, "get_setting", return_value="true")
def test_confirm_callback_none_when_auto_accept_enabled(mock_get_setting):
    """With settings.auto_accept enabled, hooks run without a confirmation prompt."""
    assert open_deadline_cloud_dialog._pre_gui_hook_confirm_callback(parent=None) is None
    mock_get_setting.assert_called_once_with("settings.auto_accept")


@patch.object(open_deadline_cloud_dialog, "qt_hook_confirmation")
@patch.object(open_deadline_cloud_dialog, "get_setting", return_value="false")
def test_confirm_callback_prompts_when_auto_accept_disabled(mock_get_setting, mock_qt_confirm):
    """With settings.auto_accept disabled, the standard Qt confirmation callback is used.

    We assert at the deadline-cloud API boundary — that ``qt_hook_confirmation`` is invoked with
    the submitter window and its callback returned — rather than driving the real ``QMessageBox``.
    The test bootstrap stubs ``qtpy.QtWidgets`` as a ``MagicMock``, so asserting on the actual
    ``QMessageBox.question`` call through that stub is unreliable; patching ``qt_hook_confirmation``
    keeps the test to the DCC-owned contract (the confirmation path fires, parented correctly)."""
    sentinel = object()
    mock_qt_confirm.return_value = sentinel

    result = open_deadline_cloud_dialog._pre_gui_hook_confirm_callback(parent="mainwin")

    assert result is sentinel
    mock_qt_confirm.assert_called_once_with("mainwin")
