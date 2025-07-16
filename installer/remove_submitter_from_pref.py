# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

# Disables the Deadline Blender Submitter plugin.
# Then removes all instances of the Deadline Cloud install path from Blender's scripts directories list.

import bpy
import addon_utils
import argparse
import sys


class ArgumentParserForBlender(argparse.ArgumentParser):
    def _get_argv_after_doubledash(self):
        try:
            return sys.argv[sys.argv.index("--") + 1 :]  # the list after '--'
        except ValueError:  # '--' not in the list:
            return []

    def parse_args(self):
        return super().parse_args(args=self._get_argv_after_doubledash())


def main():
    parser = ArgumentParserForBlender(description="Remove Submitter Script Directory")
    parser.add_argument(
        "--deadline_cloud_install_path", required=True, help="Path to Deadline Cloud installation"
    )
    args = parser.parse_args()

    addon_utils.disable("deadline_cloud_blender_submitter", default_set=True)

    for index, script_dir in enumerate(bpy.context.preferences.filepaths.script_directories):
        if script_dir.directory == args.deadline_cloud_install_path:
            bpy.ops.preferences.script_directory_remove(index)

    bpy.ops.wm.save_userpref()


if __name__ == "__main__":
    main()
