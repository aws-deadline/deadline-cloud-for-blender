# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

"""UI widgets for the Scene Settings tab."""

from __future__ import annotations

import logging
import os

from deadline.client.ui import block_signals
from . import blender_utils
from .template_filling import BlenderSubmitterUISettings
from . import ocio_utils as ocio
from qtpy.QtCore import QRegularExpression, QSize, Qt  # type: ignore
from qtpy.QtGui import QRegularExpressionValidator  # type: ignore
from qtpy.QtWidgets import (  # type: ignore
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

# Default values for combo boxes in the addon UI.
COMBO_DEFAULT_ALL_RENDERABLE_CAMERAS = "All Renderable Cameras"
COMBO_DEFAULT_ALL_RENDERABLE_LAYERS = "All Renderable Layers"


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
        self.op_dir_txt = FileSearchLineEdit(directory_only=True)
        layout.addWidget(QLabel("Output Directory"), qt_pos_index, 0)
        layout.addWidget(self.op_dir_txt, qt_pos_index, 1)

        qt_pos_index += 1
        self.op_file_txt = QLineEdit(self)
        layout.addWidget(QLabel("Output File Prefix"), qt_pos_index, 0)
        layout.addWidget(self.op_file_txt, qt_pos_index, 1)

        qt_pos_index += 1
        self.scenes_box = QComboBox(self)
        layout.addWidget(QLabel("Scene"), qt_pos_index, 0)
        layout.addWidget(self.scenes_box, qt_pos_index, 1)

        qt_pos_index += 1
        self.render_engine_box = QComboBox(self)
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
        self.enable_gpu_check = QCheckBox("Cycles GPU Rendering", self)
        self.gpu_device_box = QComboBox(self)
        # Natively supported GPU devices for Blender 3.6 and 4.2:
        # https://docs.blender.org/manual/en/3.6/render/cycles/gpu_rendering.html
        # https://docs.blender.org/manual/en/4.2/render/cycles/gpu_rendering.html
        gpu_device_options = ["CUDA", "OptiX", "HIP", "oneAPI", "Metal"]
        for device in gpu_device_options:
            self.gpu_device_box.addItem(device, device.upper())

        # If the user wants to use another device type, let them edit the value manually
        self.gpu_device_box.setEditable(True)

        layout.addWidget(self.enable_gpu_check, qt_pos_index, 0)
        layout.addWidget(self.gpu_device_box, qt_pos_index, 1)
        self.enable_gpu_check.stateChanged.connect(self.activate_enable_gpu_changed)

        qt_pos_index += 1
        self.frame_override_check = QCheckBox("Override Frame Range", self)
        self.frame_override_txt = QLineEdit(self)
        layout.addWidget(self.frame_override_check, qt_pos_index, 0)
        layout.addWidget(self.frame_override_txt, qt_pos_index, 1)
        self.frame_override_check.stateChanged.connect(self.activate_frame_override_changed)

        # Frame range validation
        # E.g.: 1-4,6,8,9-12
        # Note: ?: in regex groups all together as one result
        regex = QRegularExpression(
            r"\d+"  # unlimited numbers
            r"(?:-\d+)?"  # optional dash (-) and one or more digits
            r"(?:,(\s)?\d+"  # new parts split by commas (,) , allow 1 space for readability
            r"(?:-\d+)?)*"
        )  # can be repeated endlessly
        validator = QRegularExpressionValidator(regex, self.frame_override_txt)
        self.frame_override_txt.setValidator(validator)

        if self.dev_options:
            qt_pos_index += 1
            self.include_adaptor_wheels = QCheckBox(
                "Developer Option: Include Adaptor Wheels", self
            )
            layout.addWidget(self.include_adaptor_wheels, qt_pos_index, 0)

        layout.addItem(QSpacerItem(0, 0, QSizePolicy.Minimum, QSizePolicy.Expanding), 10, 0)

        self._fill_scenes_box()
        self._fill_cameras_box()
        self._fill_view_layers_box()

    def _fill_cameras_box(self):
        """Populate the cameras box with all available cameras."""
        saved_scene_name = self.scenes_box.currentData()
        selectable_cameras = blender_utils.get_renderable_cameras(saved_scene_name)
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
        scenes = blender_utils.get_all_scenes()
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
            for layer in blender_utils.get_renderable_view_layers(scene):
                self.layers_box.addItem(layer, layer)

            # Re-select the layer if possible
            index = self.layers_box.findData(saved_view_layer_name)
            if index >= 0:
                self.layers_box.setCurrentIndex(index)

    def _load(self, settings: BlenderSubmitterUISettings):
        """Set the UI to load sticky settings values."""
        self.proj_path_txt.setText(settings.project_path)
        self.op_dir_txt.set_text(settings.output_path)
        self.op_file_txt.setText(settings.output_file_prefix)

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

        self.enable_gpu_check.setChecked(settings.enable_gpu)
        i = self.gpu_device_box.findData(settings.gpu_device)
        if i >= 0:
            self.gpu_device_box.setCurrentIndex(i)
        self.gpu_device_box.setEnabled(settings.enable_gpu)

        self.frame_override_check.setChecked(settings.override_frame_range)
        self.frame_override_txt.setEnabled(settings.override_frame_range)
        self.frame_override_txt.setText(settings.frame_list)

        if self.dev_options:
            self.include_adaptor_wheels.setChecked(settings.include_adaptor_wheels)

    def update_settings(self, settings: BlenderSubmitterUISettings):
        """Update a scene settings object with the latest values."""
        settings.project_path = self.proj_path_txt.text()
        settings.output_path = self.op_dir_txt.get_text()
        settings.output_file_prefix = self.op_file_txt.text()
        settings.scene_name = self.scenes_box.currentData()
        settings.renderer_name = self.render_engine_box.currentData()
        settings.ocio_config_path = ocio.get_ocio_path()
        settings.view_layer_selection = self.layers_box.currentData()
        settings.camera_selection = self.cameras_box.currentData()
        settings.enable_gpu = self.enable_gpu_check.isChecked()

        if settings.enable_gpu:
            # Blender's natively-supported options should be converted to uppercase from the menu options.
            # Custom options won't have associated data, so we use `currentText` to set the GPU device setting.
            settings.gpu_device = (
                self.gpu_device_box.currentData()
                if self.gpu_device_box.currentData()
                else self.gpu_device_box.currentText()
            )
        else:
            settings.gpu_device = "NONE"

        settings.override_frame_range = self.frame_override_check.isChecked()
        settings.frame_list = self.frame_override_txt.text()
        settings.include_adaptor_wheels = (
            self.include_adaptor_wheels.isChecked() if self.dev_options else False
        )

    def activate_enable_gpu_changed(self, state):
        """Set the activated/deactivated status of the GPU Device text box."""
        self.gpu_device_box.setEnabled(Qt.CheckState(state) == Qt.Checked)

    def activate_frame_override_changed(self, state):
        """Set the activated/deactivated status of the Frame override text box."""
        self.frame_override_txt.setEnabled(Qt.CheckState(state) == Qt.Checked)


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
