# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

"""
Registration of Deadline Cloud Submitter Addon + activate logger
"""
import logging

import bpy  # noqa
from bpy.types import Operator
from deadline_cloud_blender_submitter import logutil
from deadline_cloud_blender_submitter._version import version_tuple as adaptor_version_tuple

bl_info = {
    "name": "Deadline Cloud for Blender Addon",
    "description": "Deadline Cloud for Blender",
    "author": "AWS Thinkbox",
    "version": adaptor_version_tuple,
    "blender": (3, 5, 0),
    "category": "Render",
}

# Configure logging.
logutil.add_file_handler()

_logger = logging.getLogger(__name__)

addon_keymaps = []


class DEADLINE_CLOUD_OT_open_dialog(Operator):
    """Open deadline cloud dialog."""

    bl_idname = "ops.open_deadline_cloud_dialog"
    bl_label = "Deadline Cloud pop-out"
    bl_options = {"REGISTER"}

    # Execution after the window was closed with ok button.
    def execute(self, context):
        """Execute the operator.

        See the bpy Operator docs: https://docs.blender.org/api/current/bpy.types.Operator.html
        """
        try:
            import blender_stylesheet
            from deadline_cloud_blender_submitter.open_deadline_cloud_dialog import (
                create_deadline_dialog,
            )
            from PySide2 import QtCore, QtWidgets
        except ImportError as e:
            self.report({"ERROR"}, f"The submitter installation is incomplete. {e} .")
            return {"CANCELLED"}

        self.app = QtWidgets.QApplication.instance()
        if not self.app:
            self.app = QtWidgets.QApplication(["Deadline Cloud Submitter"])

        blender_stylesheet.setup()

        _logger.info("Initializing Deadline Cloud Blender Submitter UI")
        try:
            self.widget = create_deadline_dialog()
        except RuntimeError as e:
            self.report({"ERROR"}, str(e))
            return {"CANCELLED"}

        # Set window flags.
        flag_info = f"Current window flags: {bin(int(self.widget.windowFlags()))}"
        _logger.debug(flag_info)
        # Option 0: Default behaviour: window will always stay on top of other windows.
        # self.widget.setWindowFlags(self.widget.windowFlags() | QtCore.Qt.WindowStaysOnTopHint)
        # Option 1: go into background when focus is lost, keep a taskbar entry.
        self.widget.setWindowFlags(self.widget.windowFlags() & ~QtCore.Qt.WindowStaysOnTopHint)
        # Option 2: tool window.
        # Setting the window to be a tool window has the desired effect of making it stay on top
        # of the Blender window only. But the disadvantage that, without a presence in the menu bar,
        # it gets lost when focusing away from Blender.
        # self.widget.setWindowFlags(self.widget.windowFlags() & ~QtCore.Qt.WindowStaysOnTopHint)
        # self.widget.setWindowFlags(self.widget.windowFlags() | QtCore.Qt.Tool)
        _logger.debug(flag_info)

        self.widget.show()
        self.report({"INFO"}, "OK!")
        return {"FINISHED"}


def deadline_cloud_dialog_topbar_btn(self, context):
    """Deadline Cloud Dialog button."""
    self.layout.separator()
    self.layout.operator(DEADLINE_CLOUD_OT_open_dialog.bl_idname, text="Deadline Cloud Dialog")


def register():
    """Register the addon to the Blender UI."""
    bpy.utils.register_class(DEADLINE_CLOUD_OT_open_dialog)
    bpy.types.TOPBAR_MT_render.append(deadline_cloud_dialog_topbar_btn)

    # keymapping for pop-out window
    wm = bpy.context.window_manager
    kc = wm.keyconfigs.addon
    if kc:
        km = kc.keymaps.new(name="3D View", space_type="VIEW_3D")
        kmi = km.keymap_items.new(
            "ops.open_deadline_cloud_dialog", type="F", value="PRESS", shift=True
        )
        addon_keymaps.append((km, kmi))


def unregister():
    """Unregister the addon from the Blender UI."""
    for km, kmi in addon_keymaps:
        km.keymap_items.remove(kmi)
    addon_keymaps.clear()
    bpy.utils.unregister_class(DEADLINE_CLOUD_OT_open_dialog)
    bpy.types.TOPBAR_MT_render.remove(deadline_cloud_dialog_topbar_btn)


if __name__ == "__main__":
    register()
