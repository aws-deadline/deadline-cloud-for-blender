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
    parser = ArgumentParserForBlender(description="Add Deadline Cloud to Blender preferences")
    parser.add_argument(
        "--deadline_cloud_install_path", required=True, help="Path to Deadline Cloud installation"
    )
    args = parser.parse_args()

    bpy.ops.preferences.script_directory_add(directory=args.deadline_cloud_install_path)
    bpy.utils.load_scripts(refresh_scripts=True)

    for script_dir in bpy.context.preferences.filepaths.script_directories:
        if script_dir.directory == args.deadline_cloud_install_path:
            script_dir.name == "Deadline for Blender"

    addon_utils.enable("deadline_cloud_blender_submitter", default_set=True)

    bpy.ops.wm.save_userpref()


if __name__ == "__main__":
    main()
