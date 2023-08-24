# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

from ._version import __version__  # noqa  # pragma: no cover

__all__ = ["__version__"]

bl_info = {
    "name": "Amazon Deadline Cloud Submitter",
    "description": "Amazon Deadline Cloud Submitter",
    "blender": (3, 3, 3),
    "version": (0, 4, 0),
    "location": "Render",
    "category": "Render",
}


def register():  # pragma: no cover
    from importlib import reload
    from pathlib import Path

    import bpy

    from deadline_submitter_for_blender.data_classes import submitter_properties
    from deadline_submitter_for_blender.ui import deadline_submitter
    from deadline_submitter_for_blender.utilities import submitter_operations, utility_functions

    # These functions enable grabbing data on file load
    def _filename() -> str:
        if not bpy.data.filepath:
            return ""
        return Path(bpy.data.filepath).stem

    def _project_path() -> str:
        if not bpy.data.filepath:
            return ""
        return str(Path(bpy.data.filepath).parent)

    def _job_attachments() -> list:
        if not bpy.data.filepath:
            return []

        return utility_functions.get_assets()

    def _redraw(context):
        for window in context.window_manager.windows:
            for area in window.screen.areas:
                area.tag_redraw()

    # File name
    @bpy.app.handlers.persistent
    def _set_deadline_job_name(a, b):
        wm = bpy.context.window_manager
        if wm.deadline_job_name:
            return
        wm.deadline_job_name = _filename()
        _redraw(bpy.context)

    @bpy.app.handlers.persistent
    def _unset_deadline_job_name(a, b):
        wm = bpy.context.window_manager
        wm.deadline_job_name = ""

    # Project Path
    @bpy.app.handlers.persistent
    def _set_deadline_project_path(a, b):
        wm = bpy.context.window_manager
        if wm.deadline_project_path:
            return
        wm.deadline_project_path = _project_path()
        _redraw(bpy.context)

    @bpy.app.handlers.persistent
    def _unset_deadline_project_path(a, b):
        wm = bpy.context.window_manager
        wm.deadline_project_path = ""

    # Asset Attachments
    @bpy.app.handlers.persistent
    def _set_deadline_job_attachments(a, b):
        wm = bpy.context.window_manager
        if len(wm.deadline_job_attachments) > 0:
            return

        files = _job_attachments()
        for file in files:
            name = bpy.path.basename(file)
            path = str(file)
            if not name == "":
                attachment = wm.deadline_job_attachments.add()
                attachment.name = name
                attachment.path = path

        _redraw(bpy.context)

    @bpy.app.handlers.persistent
    def _unset_deadline_job_attachments(a, b):
        wm = bpy.context.window_manager
        wm.deadline_job_attachments.clear()

    classes = [
        submitter_properties,
        submitter_operations,
        deadline_submitter,
    ]

    for cls in classes:
        reload(cls)

    # Job Name
    bpy.app.handlers.load_post.append(_set_deadline_job_name)
    bpy.app.handlers.save_pre.append(_unset_deadline_job_name)
    bpy.app.handlers.save_post.append(_set_deadline_job_name)

    # Project Path
    bpy.app.handlers.load_post.append(_set_deadline_project_path)
    bpy.app.handlers.save_pre.append(_unset_deadline_project_path)
    bpy.app.handlers.save_post.append(_set_deadline_project_path)

    # File Attachments
    bpy.app.handlers.load_post.append(_set_deadline_job_attachments)
    bpy.app.handlers.save_pre.append(_unset_deadline_job_attachments)
    bpy.app.handlers.save_post.append(_set_deadline_job_attachments)

    for cls in classes:
        cls.register()


def unregister():  # pragma: no cover
    from deadline_submitter_for_blender.data_classes import submitter_properties
    from deadline_submitter_for_blender.ui import deadline_submitter
    from deadline_submitter_for_blender.utilities import submitter_operations

    classes = [
        submitter_properties,
        submitter_operations,
        deadline_submitter,
    ]

    classes.reverse()
    for cls in classes:
        cls.unregister()
