# AWS Deadline Cloud for Blender Development

### Installation

#### Install for Production

##### Submitter Installer

1. Run the submitter installer and ensure you select Blender

2. Add a script directory in Blender by "Edit" > "Preferences" > "File Paths" > "Script Directories"
  * Windows: `%USERPROFILE%\DeadlineCloudSubmitter\Submitters\Blender\python`
  * Linux: `~/DeadlineCloudSubmitter/Submitters/Blender/python`

  Or run this script from Blender

  ```
  import bpy
  import os
  bpy.ops.preferences.script_directory_add(directory=os.path.expanduser(os.path.normpath('~/DeadlineCloudSubmitter/Submitters/Blender/python')))
  ```

3. Restart Blender - changes to the script directory won't take effect until Blender has been restarted.

##### Manual Installation

1. Install `deadline[gui]` and `blender-qt-stylesheet` packages to `~/DeadlineCloudSubmitter/Submitters/Blender/python/modules`.
  - For Windows: `pip install deadline[gui] blender-qt-stylesheet -t %USERPROFILE%\DeadlineCloudSubmitter\Submitters\Blender\python\modules`
  - For Unix: `pip install deadline[gui] blender-qt-stylesheet -t ~/DeadlineCloudSubmitter/Submitters/Blender/python/modules`

  Currently, Python 3.10 is the Python version used by the latest Blender release.

2. Install addon in Blender

  Copy the contents of `src/deadline/blender_submitter/addons` to `~/DeadlineCloudSubmitter/Submitters/Blender/python/addons`

3. Add a script directory in Blender by "Edit" > "Preferences" > "File Paths" > "Script Directories"
  * Windows: `%USERPROFILE%\DeadlineCloudSubmitter\Submitters\Blender\python`
  * Linux: `~/DeadlineCloudSubmitter/Submitters/Blender/python`

  Or run this script from Blender

  ```
  import bpy
  import os
  bpy.ops.preferences.script_directory_add(directory=os.path.expanduser(os.path.normpath('~/DeadlineCloudSubmitter/Submitters/Blender/python')))
  ```

4. Restart Blender - changes to the script directory won't take effect until Blender has been restarted.

#### Usage

This repository comes with the addon: `deadline_cloud_blender_submitter`

You can enable this in "Edit" menu > "Preferences" menu item > "addons" tab.

## Deadline Cloud for Blender Adaptor

The deadline-cloud-for-blender Adaptor supports Linux and macOS.

### Installation

Build a wheel with `hatch build` and install it as a normal Python package.
