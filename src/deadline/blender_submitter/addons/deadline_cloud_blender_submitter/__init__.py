# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

"""
Registration of Deadline Cloud Submitter Addon + activate logger
"""
import logging
from pathlib import Path
import subprocess
import sys

import bpy  # noqa
from bpy.types import Operator

from . import logutil

# NOTE: Variables are NOT allowed to be in bl_info since
#       blender parses this __init__.py source for this variable
#       and is not aware of any additional context.
#       ref: https://developer.blender.org/docs/handbook/addons/addon_meta_info/
bl_info = {
    "name": "Deadline Cloud for Blender",
    "description": "Submit to AWS Deadline Cloud",
    "author": "AWS",
    "version": (0, 5, 5),
    "blender": (3, 6, 0),
    "category": "Render",
}

# Configure logging.
logutil.add_file_handler()

_logger = logging.getLogger(__name__)

addon_keymaps = []


class DEADLINE_CLOUD_OT_open_dialog(Operator):
    """Open deadline cloud dialog."""

    bl_idname = "ops.open_deadline_cloud_dialog"
    bl_label = "AWS Deadline Cloud"
    bl_options = {"REGISTER"}

    # Execution after the window was closed with ok button.
    def execute(self, context):
        """Execute the operator.

        See the bpy Operator docs: https://docs.blender.org/api/current/bpy.types.Operator.html
        """
        if not self.has_gui_deps():
            self.install_gui()

        from qtpy import QtCore, QtWidgets
        from .open_deadline_cloud_dialog import (
            create_deadline_dialog,
        )

        self.app = QtWidgets.QApplication.instance()
        if not self.app:
            self.app = QtWidgets.QApplication(sys.argv)

        try:
            # optionally use the blender_stylesheet if it exists
            import blender_stylesheet

            blender_stylesheet.setup()
        except ImportError:
            _logger.info("blender_stylesheet package is not available. Skipping")

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
        self.widget.setWindowFlags(self.widget.windowFlags() & ~QtCore.Qt.WindowStaysOnTopHint | QtCore.Qt.WindowCloseButtonHint)  # type: ignore
        # Option 2: tool window.
        # Setting the window to be a tool window has the desired effect of making it stay on top
        # of the Blender window only. But the disadvantage that, without a presence in the menu bar,
        # it gets lost when focusing away from Blender.
        # self.widget.setWindowFlags(self.widget.windowFlags() & ~QtCore.Qt.WindowStaysOnTopHint)
        # self.widget.setWindowFlags(self.widget.windowFlags() | QtCore.Qt.Tool)
        _logger.debug(flag_info)

        self.widget.exec_()
        self.report({"INFO"}, "OK!")
        return {"FINISHED"}

    def draw(self, context):
        layout = self.layout
        col = layout.column()
        col.label(text="Press 'OK' to install GUI dependencies. Please wait...")

    def invoke(self, context, event):
        if self.has_gui_deps():
            # don't prompt user if gui deps exist
            return self.execute(context)
        wm = context.window_manager
        return wm.invoke_props_dialog(self)

    def has_gui_deps(self):
        try:
            import qtpy  # noqa
            from .open_deadline_cloud_dialog import (  # noqa
                create_deadline_dialog,
            )
        except Exception as e:
            # qtpy throws a QtBindingsNotFoundError when running
            # from qtpy import QtBindingsNotFoundError
            if not (type(e).__name__ == "QtBindingsNotFoundError" or isinstance(e, ImportError)):
                raise
            return False

        return True

    def install_gui(self):
        import deadline.client

        deadline.client.version
        pip_install_command = [
            sys.executable,
            "-m",
            "pip",
            "install",
            f"deadline[gui]=={deadline.client.version}",
        ]
        # module_directory assumes relative install location of:
        #   * [installdir]/Submitters/Blender/python/addons/deadline_cloud_blender_submitter/__init__.py
        #   * [installdir]/Submitters/Blender/python/modules/
        module_directory = Path(__file__).parent.parent.parent / "modules"
        if module_directory.exists():
            _logger.info(f"Missing GUI libraries, installing deadline[gui] to {module_directory}")
            pip_install_command.extend(["--target", str(module_directory)])
        else:
            _logger.info(
                "Missing GUI libraries with non-standard set-up, installing deadline[gui] into Blender's python"
            )

        subprocess.run(pip_install_command)


def deadline_cloud_dialog_topbar_btn(self, context):
    """Deadline Cloud Dialog button."""
    self.layout.separator()
    self.layout.operator(
        DEADLINE_CLOUD_OT_open_dialog.bl_idname, text="Submit to AWS Deadline Cloud"
    )


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
