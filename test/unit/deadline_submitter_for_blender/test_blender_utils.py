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

    def test_find_files_udim_tiles(self, tmp_path):
        """Test that UDIM tiled images have their tile files resolved and included."""
        from unittest.mock import MagicMock

        # GIVEN
        project_dir = Path(tmp_path, "project")
        project_dir.mkdir()
        project_file = Path(project_dir, "test.blend")
        project_file.write_text("blend file content")

        texture_dir = Path(project_dir, "textures")
        texture_dir.mkdir()

        # Create UDIM tile files on disk
        tile_1001 = Path(texture_dir, "skin_diffuse.1001.png")
        tile_1002 = Path(texture_dir, "skin_diffuse.1002.png")
        tile_1003 = Path(texture_dir, "skin_diffuse.1003.png")
        tile_1001.write_text("tile 1001")
        tile_1002.write_text("tile 1002")
        tile_1003.write_text("tile 1003")

        # The token path that blend_paths() returns (doesn't exist on disk)
        udim_token_path = str(Path(texture_dir, "skin_diffuse.<UDIM>.png"))

        # Mock a TILED image with 3 tiles
        mock_tile_1001 = MagicMock()
        mock_tile_1001.number = 1001
        mock_tile_1002 = MagicMock()
        mock_tile_1002.number = 1002
        mock_tile_1003 = MagicMock()
        mock_tile_1003.number = 1003

        mock_image = MagicMock()
        mock_image.source = "TILED"
        mock_image.filepath = str(Path(texture_dir, "skin_diffuse.<UDIM>.png"))
        mock_image.library = None
        mock_image.tiles = [mock_tile_1001, mock_tile_1002, mock_tile_1003]

        blender_resource_dir = Path(tmp_path, "blender", "XX")
        blender_resource_dir.mkdir(parents=True)

        with (
            patch("blender_utils.bpy.utils.blend_paths", return_value=[udim_token_path]),
            patch("blender_utils.bpy.utils.resource_path", return_value=blender_resource_dir),
            patch("blender_utils.bpy.data.images", [mock_image]),
            patch("blender_utils.bpy.path.abspath", side_effect=lambda p, **kw: p),
            patch("blender_utils._get_blender_temp_dirs", return_value=[]),
        ):

            # WHEN
            found_files = bu.find_files(project_file)

            # THEN
            # Token path should be filtered out
            assert Path(udim_token_path) not in found_files

            # All tile files should be included
            assert tile_1001 in found_files
            assert tile_1002 in found_files
            assert tile_1003 in found_files

            # Project file + 3 tiles = 4
            assert len(found_files) == 4

    def test_find_files_uvtile_tokens(self, tmp_path):
        """Test that <UVTILE> tokens are also resolved correctly."""
        from unittest.mock import MagicMock

        # GIVEN
        project_dir = Path(tmp_path, "project")
        project_dir.mkdir()
        project_file = Path(project_dir, "test.blend")
        project_file.write_text("blend file content")

        texture_dir = Path(project_dir, "textures")
        texture_dir.mkdir()

        # Create UVTILE files on disk
        tile_u1_v1 = Path(texture_dir, "skin_diffuse.u1_v1.png")
        tile_u2_v1 = Path(texture_dir, "skin_diffuse.u2_v1.png")
        tile_u1_v1.write_text("tile u1_v1")
        tile_u2_v1.write_text("tile u2_v1")

        uvtile_token_path = str(Path(texture_dir, "skin_diffuse.<UVTILE>.png"))

        # Tile 1001 = u1_v1, tile 1002 = u2_v1 (u = (n-1001)%10, v = (n-1001)//10)
        mock_tile_1001 = MagicMock()
        mock_tile_1001.number = 1001
        mock_tile_1002 = MagicMock()
        mock_tile_1002.number = 1002

        mock_image = MagicMock()
        mock_image.source = "TILED"
        mock_image.filepath = str(Path(texture_dir, "skin_diffuse.<UVTILE>.png"))
        mock_image.library = None
        mock_image.tiles = [mock_tile_1001, mock_tile_1002]

        blender_resource_dir = Path(tmp_path, "blender", "XX")
        blender_resource_dir.mkdir(parents=True)

        with (
            patch("blender_utils.bpy.utils.blend_paths", return_value=[uvtile_token_path]),
            patch("blender_utils.bpy.utils.resource_path", return_value=blender_resource_dir),
            patch("blender_utils.bpy.data.images", [mock_image]),
            patch("blender_utils.bpy.path.abspath", side_effect=lambda p, **kw: p),
            patch("blender_utils._get_blender_temp_dirs", return_value=[]),
        ):

            # WHEN
            found_files = bu.find_files(project_file)

            # THEN
            assert Path(uvtile_token_path) not in found_files
            assert tile_u1_v1 in found_files
            assert tile_u2_v1 in found_files
            assert len(found_files) == 3  # project + 2 tiles
