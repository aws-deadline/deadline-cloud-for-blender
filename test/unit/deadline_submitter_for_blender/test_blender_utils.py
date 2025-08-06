# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

import sys
from pathlib import Path
from unittest.mock import patch

# Ensure the submitter can be imported.
SUBMITTER_DIR = (
    Path(__file__).parent.parent.parent.parent
    / "src"
    / "deadline"
    / "blender_submitter"
    / "addons"
    / "deadline_cloud_blender_submitter"
)
sys.path.append(str(SUBMITTER_DIR))

import blender_utils as bu  # noqa: E402


class TestFindFiles:

    def test_find_files(self, tmp_path):
        """Test all filtering functionality. temp files, non-existent files, and essential brushes."""

        # GIVEN

        project_dir = Path(tmp_path, "project")
        project_dir.mkdir()
        project_file = Path(project_dir, "test.blend")
        project_file.write_text("blend file content")

        # Create temp directory and file
        temp_dir = Path(tmp_path, "TEMP")
        temp_dir.mkdir()
        temp_file = Path(temp_dir, "temp_texture.png")
        temp_file.write_text("temp texture")

        # Create brush directory and files
        blender_resource_dir = Path(tmp_path, "blender", "XX")
        brush_dir = Path(blender_resource_dir, "datafiles", "assets", "brushes")
        brush_dir.mkdir(parents=True)
        essential_brush = Path(brush_dir, "essentials_brushes-sculpt.blend")
        custom_brush = Path(brush_dir, "custom_brush.blend")
        essential_brush.write_text("essential brush")
        custom_brush.write_text("custom brush")

        # Create valid project files
        texture_dir = Path(project_dir, "textures")
        texture_dir.mkdir(parents=True)
        valid_file1 = Path(project_dir, "valid_image.png")
        valid_file2 = Path(project_dir, "textures", "valid_texture2.png")
        valid_file1.write_text("valid image")
        valid_file2.write_text("valid texture")

        # File that doesn't exist
        missing_file = Path(project_dir, "missing_texture.png")

        all_files = [
            temp_file,
            missing_file,
            essential_brush,
            valid_file1,
            valid_file2,
            custom_brush,
        ]

        with (
            patch("blender_utils.bpy.utils.blend_paths", return_value=all_files),
            patch("blender_utils.bpy.utils.resource_path", return_value=blender_resource_dir),
            patch("blender_utils._get_blender_temp_dirs", return_value=[temp_dir]),
        ):

            # WHEN

            found_files = bu.find_files(project_file)

            # THEN

            # Verify filtered files are not in results
            assert temp_file not in found_files
            assert missing_file not in found_files
            assert essential_brush not in found_files

            # Verify included files are in results
            assert project_file in found_files
            assert valid_file1 in found_files
            assert valid_file2 in found_files
            assert custom_brush in found_files
            assert len(found_files) == 4
