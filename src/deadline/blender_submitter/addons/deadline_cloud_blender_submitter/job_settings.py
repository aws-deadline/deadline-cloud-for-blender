# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
from __future__ import annotations

import dataclasses
import json
import logging
import os
import traceback
from dataclasses import dataclass, field
from pathlib import Path

import bpy
from deadline.client.ui import block_signals
from PySide2.QtGui import QRegularExpressionValidator
from PySide2.QtCore import QSize, Qt, QRegularExpression
from PySide2.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QSpacerItem,
    QWidget,
)

_logger = logging.getLogger(__name__)

_SETTINGS_FILE_EXT = ".deadline_render_settings.json"

_ALL_CAMERAS = "ALL_CAMERAS"

# Default values for combo boxes in the addon UI.
COMBO_DEFAULT_ALL_RENDERABLE_CAMERAS = "All Renderable Cameras"
COMBO_DEFAULT_ALL_RENDERABLE_LAYERS = "All Renderable Layers"


def get_view_layers(saved_scene_name) -> list[str]:
    """Get the view layers associated with a scene.

    Args:
        saved_scene_name: The name of the scene.
    """
    # NOTE I am not sure what the difference is between `saved_scene_name` and `scene_name`.
    scene_name = bpy.data.scenes[saved_scene_name].name
    layers = [layer.name for layer in bpy.data.scenes[scene_name].view_layers]
    return layers


def get_renderable_cameras(saved_scene_name) -> list[str]:
    """Returns a list of all camera objects in the scene that are marked as renderable.

    Args:
        saved_scene_name: The name of the scene.
    """
    scene_name = bpy.data.scenes[saved_scene_name].name
    camera_names = [cam.name for cam in bpy.data.scenes[scene_name].objects if cam.type == "CAMERA"]
    return [cam for cam in camera_names if not bpy.data.objects[cam].hide_render]


def get_all_scenes() -> list[str]:
    """Returns a list of all scenes."""
    scene_names = [x.name for x in bpy.data.scenes]
    return scene_names


def get_scene_resolution(saved_scene_name):
    """Returns the resolution of the scene.

    Args:
        saved_scene_name: The name of the scene.
    """
    res_x = bpy.data.scenes[saved_scene_name].render.resolution_x
    res_y = bpy.data.scenes[saved_scene_name].render.resolution_y
    return res_x, res_y


def get_scene_name() -> str:
    """Construct and return a name for the current scene based on the currently opened `.blend` file."""
    scene_name = bpy.path.basename(bpy.context.blend_data.filepath).replace(".blend", "")
    return scene_name


def get_frames() -> str:
    """Returns the frame range of the active scene, formatted as a string e.g. `"1-10"`."""
    start = bpy.context.scene.frame_start
    end = bpy.context.scene.frame_end
    return str(start) + "-" + str(end)


def find_files(project_path, unique=True, skip_temp=True, skip_dead=True) -> list[Path]:
    """Returns a normalized list of paths to external files referenced by the loaded `.blend` file, augmented with `project_path`.

    Args:
        project_path: The path to the project directory.
        unique: If True, skip duplicate paths.
        skip_temp: if True, skip all files from any of Blender's potential temp directories.
        skip_dead: if True, skip all files that do not exist. When files are shared across machines, Blender may retain memory of original paths; this ensures that all retrieved paths exist on the local filesystem.
    """
    # TODO remove `project_path`. Should be handled by higher level.
    files = bpy.utils.blend_paths(absolute=True)
    files.append(project_path)
    files = (Path(f) for f in files)

    if unique:
        files = set(files)

    if skip_temp:
        temp_dirs = _get_blender_temp_dirs()
        _logger.debug(f"Resolved Blender temp directories: {temp_dirs}")

        def is_in_temp(f: Path):
            """Returns True if the given file is in any of Blender's temp directories."""
            return any(f.is_relative_to(temp_dir) for temp_dir in temp_dirs)

        files = (f for f in files if not is_in_temp(f))

    if skip_dead:
        files = (f for f in files if f.exists())

    return [f.resolve() for f in files]


def _get_blender_temp_dirs() -> list[Path]:
    """Returns a list of directories that Blender can try to use to store temporary files.

    Note that Blender actually uses only one of these at a time.

    Recreate the logic Blender uses to compute temp folders, as described here: https://docs.blender.org/manual/en/latest/advanced/blender_directory_layout.html#temporary-directory
    """
    dirs = []

    # `bpy.app.tempdir` seems to resolve to a project-specific directory, e.g. `'C:\\Users\\user\\AppData\\Local\\Temp\\blender_a07504\\'`. We want the parent directory, e.g. `'Temp\\'`.
    dirs.append(Path(bpy.app.tempdir).parent.resolve())

    # The user's preferences may specify a temp directory.
    user_pref_dir = bpy.context.preferences.filepaths.temporary_directory
    if user_pref_dir:
        dirs.append(Path(user_pref_dir).resolve())

    # System environment variables may specify a temp directory. Which one exists (if any) depends on the OS.
    for var in ["TEMP", "TMP", "TMP_DIR"]:
        if os.environ.get(var):
            dirs.append(Path(os.environ[var]).resolve())

    # The root temp directory is always a candidate.
    dirs.append(Path("/tmp").resolve())

    return list(set(dirs))


@dataclass
class BlenderSubmitterUISettings:
    """Settings that the submitter UI will use."""

    name: str = field(default="Blender Submission", metadata={"sticky": True})
    description: str = field(default="", metadata={"sticky": True})

    submitter_name: str = field(default="Blender")
    renderer_name: str = field(default="cycles", metadata={"sticky": True})
    scene_name: str = field(default="Scene", metadata={"sticky": True})

    ui_group_label: str = field(default="Blender Settings")

    # Frame settings.
    # Whether to override the frame range.
    override_frame_range: bool = field(default=False, metadata={"sticky": True})
    # The frame range to use if override_frame_range_check is True.
    frame_list: str = field(default="1-3", metadata={"sticky": True})

    # Paths and files.
    project_path: str = field(default="")
    output_path: str = field(default="")
    input_filenames: list[str] = field(default_factory=list, metadata={"sticky": True})
    input_directories: list[str] = field(default_factory=list, metadata={"sticky": True})
    output_directories: list[str] = field(default_factory=list, metadata={"sticky": True})

    # Layers settings.
    view_layer_selection: str = field(default="ViewLayer", metadata={"sticky": True})

    # Camera settings.
    all_layer_selectable_cameras: list[str] = field(default_factory=lambda: [_ALL_CAMERAS])
    current_layer_selectable_cameras: list[str] = field(default_factory=lambda: [_ALL_CAMERAS])
    camera_selection: str = field(default="Camera", metadata={"sticky": True})

    # Resolution settings.
    image_resolution: str = field(default="1920, 1080")

    # Parameter names.
    scene_name_parameter_name: str = field(default="RenderScene", metadata={"sticky": True})
    frames_parameter_name: str = field(default="Frames")
    output_file_prefix_parameter_name: str = field(default="OutputFileName")
    image_width_parameter_name: str = field(default="ResolutionX")
    image_height_parameter_name: str = field(default="ResolutionY")

    # developer options
    include_adaptor_wheels: bool = field(default=False, metadata={"sticky": True})

    def load_sticky_settings(self, scene: str) -> None:
        """Load and set sticky settings for the given scene.

        The path to the sticky settings file is determined by appending the `_SETTINGS_FILE_EXT` extension to the scene name.

        If the file does not exist, or if it is malformed, the default settings will be used instead.

        Args:
            scene: The name of the scene.
        """

        def warn(cause=None):
            traceback.print_exc()
            msg = f"Failed to load sticky settings from {sticky_file}."
            if cause:
                msg += " " + cause
            _logger.warn(msg)

        sticky_file = Path(scene).with_suffix(_SETTINGS_FILE_EXT)
        if not sticky_file.exists() or not sticky_file.is_file():
            warn("File does not exist.")
            return

        try:
            with open(sticky_file, encoding="utf8") as fh:
                sticky_settings = json.load(fh)
            if not isinstance(sticky_settings, dict):
                warn("Settings are not formatted as a dictionary.")
                return
            sticky_fields = {
                field.name: field
                for field in dataclasses.fields(self)
                if field.metadata.get("sticky")
            }
            for name, value in sticky_settings.items():
                if name in sticky_fields:
                    setattr(self, name, value)
        except (OSError, json.JSONDecodeError) as e:
            warn(str(e))

        _logger.info(f"Loaded sticky settings from {sticky_file}.")

    def save_sticky_settings(self, scene: str):
        """Save sticky settings to a file. Create or overwrite it if necessary, but don't create parent directories.

        The path to the sticky settings file is determined by appending the `_SETTINGS_FILE_EXT` extension to the scene name.
        """
        file = Path(scene).with_suffix(_SETTINGS_FILE_EXT)
        with open(file, "w", encoding="utf8") as fh:
            sticky_settings = {
                field.name: getattr(self, field.name)
                for field in dataclasses.fields(self)
                if field.metadata.get("sticky")
            }
            json.dump(sticky_settings, fh, indent=1)
        _logger.info(f"Saved sticky settings to {file}.")


##########################################
# UI widgets for the Scene Settings tab. #
##########################################


class FileSearchLineEdit(QWidget):
    """Widget used to contain a line edit and a button which opens a file search box."""

    def __init__(self, directory_only=False, parent=None):
        super().__init__(parent=parent)

        self.directory_only = directory_only

        self.text_line = QLineEdit(self)

        self.button = QPushButton("...", parent=self)
        self.button.setMaximumSize(QSize(100, 40))
        self.button.clicked.connect(self._on_button_clicked)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setMargin(0)
        layout.addWidget(self.text_line)
        layout.addWidget(self.button)

    def _on_button_clicked(self):
        """Open a file picker to allow users to choose a file or directory."""
        if self.directory_only:
            new_txt = QFileDialog.getExistingDirectory(
                self,
                "Open Directory",
                self.get_text(),
                QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks,
            )
        else:
            new_txt = QFileDialog.getOpenFileName(self, "Select File", self.get_text())

        if new_txt:
            self.set_text(new_txt)

    def set_text(self, txt: str) -> None:
        """Sets the text of the internal line edit."""
        self.text_line.setText(txt)

    def get_text(self) -> str:
        """Retrieves the text from the internal line edit."""
        return self.text_line.text()


class SceneSettingsWidget(QWidget):
    """Widget containing all top level scene settings."""

    def __init__(self, initial_settings: BlenderSubmitterUISettings, parent=None):
        super().__init__(parent=parent)

        self.dev_options = os.environ.get("DEADLINE_ENABLE_DEVELOPER_OPTIONS", "").upper() == "TRUE"

        # Save the two lists of selectable cameras.
        self.all_layer_selectable_cameras = initial_settings.all_layer_selectable_cameras
        self.current_layer_selectable_cameras = initial_settings.current_layer_selectable_cameras

        self._build_ui()
        self._load(initial_settings)

    def _build_ui(self):
        """Set up the UI."""

        layout = QGridLayout(self)

        qt_pos_index = 0
        self.proj_path_txt = QLineEdit(self)
        layout.addWidget(QLabel("Project Path"), qt_pos_index, 0)
        layout.addWidget(self.proj_path_txt, qt_pos_index, 1)
        self.proj_path_txt.setReadOnly(True)

        qt_pos_index += 1
        self.op_path_txt = FileSearchLineEdit(directory_only=True)
        layout.addWidget(QLabel("Output Path"), qt_pos_index, 0)
        layout.addWidget(self.op_path_txt, qt_pos_index, 1)

        qt_pos_index += 1
        self.scenes_box = QComboBox(self)
        layout.addWidget(QLabel("Scene"), qt_pos_index, 0)
        layout.addWidget(self.scenes_box, qt_pos_index, 1)

        qt_pos_index += 1
        self.render_engine_box = QComboBox(self)
        # TODO make constant? Enum?
        engine_items = [
            ("eevee", "eevee"),
            ("cycles", "cycles"),
            ("workbench", "workbench"),
        ]
        for engine_value, text in engine_items:
            self.render_engine_box.addItem(text, engine_value)
        layout.addWidget(QLabel("Render Engine"), qt_pos_index, 0)
        layout.addWidget(self.render_engine_box, qt_pos_index, 1)

        qt_pos_index += 1
        self.layers_box = QComboBox(self)
        self.scenes_box.currentIndexChanged.connect(self._fill_view_layers_box)
        layout.addWidget(QLabel("View Layers"), qt_pos_index, 0)
        layout.addWidget(self.layers_box, qt_pos_index, 1)

        qt_pos_index += 1
        self.scenes_box.currentIndexChanged.connect(self._fill_cameras_box)
        self.cameras_box = QComboBox(self)
        layout.addWidget(QLabel("Cameras"), qt_pos_index, 0)
        layout.addWidget(self.cameras_box, qt_pos_index, 1)

        qt_pos_index += 1
        self.frame_override_check = QCheckBox("Override Frame Range", self)
        self.frame_override_txt = QLineEdit(self)
        layout.addWidget(self.frame_override_check, qt_pos_index, 0)
        layout.addWidget(self.frame_override_txt, qt_pos_index, 1)
        self.frame_override_check.stateChanged.connect(self.activate_frame_override_changed)

        # Frame range validation
        # E.g.: 1-4,6,8,9-12
        # Note: ?: in regex groups all together as one result
        regex = QRegularExpression(r"\d+"  # unlimited numbers
                                   r"(?:-\d+)?"  # optional dash (-) and one or more digits
                                   r"(?:,(\s)?\d+"  # new parts split by commas (,) , allow 1 space for readability
                                   r"(?:-\d+)?)*")  # can be repeated endlessly
        validator = QRegularExpressionValidator(regex, self.frame_override_txt)
        self.frame_override_txt.setValidator(validator)

        if self.dev_options:
            self.include_adaptor_wheels = QCheckBox(
                "Developer Option: Include Adaptor Wheels", self
            )
            layout.addWidget(self.include_adaptor_wheels, 5, 0)

        layout.addItem(QSpacerItem(0, 0, QSizePolicy.Minimum, QSizePolicy.Expanding), 10, 0)

        self._fill_scenes_box()
        self._fill_cameras_box()
        self._fill_view_layers_box()

    def _fill_cameras_box(self):
        """Populate the cameras box with all available cameras."""
        saved_scene_name = self.scenes_box.currentData()
        selectable_cameras = get_renderable_cameras(saved_scene_name)
        _logger.info(f"filling cameras: {selectable_cameras}")
        with block_signals(self.cameras_box):
            # Save the current camera and reset the camera box list.
            saved_camera_name = self.cameras_box.currentData()
            self.cameras_box.clear()

            # Collect data and fill the combo box.
            self.cameras_box.addItem(
                COMBO_DEFAULT_ALL_RENDERABLE_CAMERAS, COMBO_DEFAULT_ALL_RENDERABLE_CAMERAS
            )
            for cam in selectable_cameras:
                self.cameras_box.addItem(cam, cam)

            # Re-select the camera if possible.
            index = self.cameras_box.findData(saved_camera_name)
            if index >= 0:
                self.cameras_box.setCurrentIndex(index)

    def _fill_scenes_box(self):
        """Populate the scenes box with all available scenes."""
        scenes = get_all_scenes()
        _logger.info(f"Filling scenes: {scenes}")
        with block_signals(self.scenes_box):
            # Save the current scene and reset the scene box list
            saved_scene_name = self.scenes_box.currentData()
            self.scenes_box.clear()
            for scene_name in scenes:
                self.scenes_box.addItem(scene_name, scene_name)

            # Re-select the Scene if possible.
            index = self.scenes_box.findData(saved_scene_name)
            if index >= 0:
                self.scenes_box.setCurrentIndex(index)

    def _fill_view_layers_box(self):
        """Populate the view layers box with all available view layers."""
        scene = self.scenes_box.currentData()
        _logger.info(f"Filling view layers for scene: {scene}")
        with block_signals(self.layers_box):
            # Save the current layer and reset the box list.
            saved_view_layer_name = self.layers_box.currentData()
            self.layers_box.clear()

            # Collect layer data to display.
            self.layers_box.addItem(
                COMBO_DEFAULT_ALL_RENDERABLE_LAYERS, COMBO_DEFAULT_ALL_RENDERABLE_LAYERS
            )
            for layer in get_view_layers(scene):
                self.layers_box.addItem(layer, layer)

            # Re-select the layer if possible
            index = self.layers_box.findData(saved_view_layer_name)
            if index >= 0:
                self.layers_box.setCurrentIndex(index)

    def _load(self, settings: BlenderSubmitterUISettings):
        """Set the UI to reflect the given settings."""
        self.proj_path_txt.setText(settings.project_path)
        self.op_path_txt.set_text(settings.output_path)

        i = self.scenes_box.findData(settings.scene_name)
        if i >= 0:
            self.scenes_box.setCurrentIndex(i)

        i = self.render_engine_box.findData(settings.renderer_name)
        if i >= 0:
            self.render_engine_box.setCurrentIndex(i)

        i = self.layers_box.findData(settings.view_layer_selection)
        if i >= 0:
            self.layers_box.setCurrentIndex(i)

        i = self.cameras_box.findData(settings.camera_selection)
        if i >= 0:
            self.cameras_box.setCurrentIndex(i)

        self.frame_override_check.setChecked(settings.override_frame_range)
        self.frame_override_txt.setEnabled(settings.override_frame_range)
        self.frame_override_txt.setText(settings.frame_list)

        if self.dev_options:
            self.include_adaptor_wheels.setChecked(settings.include_adaptor_wheels)

    def update_settings(self, settings: BlenderSubmitterUISettings):
        """Update a scene settings object with the latest values."""
        settings.project_path = self.proj_path_txt.text()
        settings.output_path = self.op_path_txt.get_text()
        settings.scene_name = self.scenes_box.currentData()
        settings.renderer_name = self.render_engine_box.currentData()
        settings.view_layer_selection = self.layers_box.currentData()
        settings.camera_selection = self.cameras_box.currentData()
        settings.override_frame_range = self.frame_override_check.isChecked()
        settings.frame_list = self.frame_override_txt.text()
        settings.include_adaptor_wheels = (
            self.include_adaptor_wheels.isChecked() if self.dev_options else False
        )

    def activate_frame_override_changed(self, state):
        """Set the activated/deactivated status of the Frame override text box."""
        self.frame_override_txt.setEnabled(state == Qt.Checked)
