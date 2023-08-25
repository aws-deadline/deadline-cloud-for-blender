# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

import os
from unittest.mock import Mock, patch

import bpy
import pytest

from deadline_adaptor_for_blender.BlenderClient.blender_client import BlenderClient, main


class TestBlenderClient:
    @patch("deadline_adaptor_for_blender.BlenderClient.blender_client.os.path.exists")
    @patch.dict(os.environ, {"BLENDER_ADAPTOR_SOCKET_PATH": "9999"})
    @patch("deadline_adaptor_for_blender.BlenderClient.BlenderClient.poll")
    @patch("deadline_adaptor_for_blender.BlenderClient.blender_client.HTTPClientInterface")
    def test_main(self, mock_httpclient: Mock, mock_poll: Mock, mock_exists: Mock) -> None:
        """Tests that the main method starts the blender client polling method"""
        # GIVEN
        mock_exists.return_value = True

        # WHEN
        main()

        # THEN
        mock_exists.assert_called_once_with("9999")
        mock_poll.assert_called_once()

    @patch.dict(os.environ, {}, clear=True)
    @patch("deadline_adaptor_for_blender.BlenderClient.BlenderClient.poll")
    def test_main_no_server_socket(self, mock_poll: Mock) -> None:
        """Tests that the main method raises an OSError if no server socket is found"""
        # WHEN
        with pytest.raises(OSError) as exc_info:
            main()

        # THEN
        assert str(exc_info.value) == (
            "BlenderClient cannot connect to the Adaptor because the environment variable "
            "BLENDER_ADAPTOR_SOCKET_PATH does not exist"
        )
        mock_poll.assert_not_called()

    @patch("deadline_adaptor_for_blender.BlenderClient.blender_client.os.path.exists")
    @patch.dict(os.environ, {"BLENDER_ADAPTOR_SOCKET_PATH": "/a/path/that/does/not/exist"})
    @patch("deadline_adaptor_for_blender.BlenderClient.BlenderClient.poll")
    def test_main_server_socket_not_exist(self, mock_poll: Mock, mock_exists: Mock) -> None:
        """Tests that the main method raises an OSError if the server socket does not exist"""
        # GIVEN
        mock_exists.return_value = False

        # WHEN
        with pytest.raises(OSError) as exc_info:
            main()

        # THEN
        mock_exists.assert_called_once_with("/a/path/that/does/not/exist")
        assert str(exc_info.value) == (
            "BlenderClient cannot connect to the Adaptor because the socket at the path defined by "
            "the environment variable BLENDER_ADAPTOR_SOCKET_PATH does not exist. Got: "
            f"{os.environ['BLENDER_ADAPTOR_SOCKET_PATH']}"
        )
        mock_poll.assert_not_called()

    @patch.object(bpy.ops.wm, "quit_blender")
    def test_close(self, mock_script_quit: Mock):
        """
        Test that blender closes and exits on client.close
        """
        # GIVEN
        client = BlenderClient(socket_path="/tmp/9999")

        # WHEN
        client.close()

        # THEN
        mock_script_quit.assert_called_once()

    @patch.object(bpy.ops.wm, "quit_blender")
    def test_graceful_shutdown(self, mock_script_quit: Mock):
        """
        Test that blender closes and exits on client.graceful_shutdown
        """
        # GIVEN
        client = BlenderClient(socket_path="/tmp/9999")

        # WHEN
        client.graceful_shutdown(1, Mock())

        # THEN
        mock_script_quit.assert_called_once()
