# Amazon Deadline Cloud for Blender Development

### Installation

#### Install for Production

1. Install `deadline` and `PySide2` and `blender-qt-stylesheet` packages to `~/DeadlineCloudSubmitter/Submitters/Blender/python/modules`.
  - For Windows: `pip install deadline PySide2 blender-qt-stylesheet -t %USERPROFILE%\DeadlineCloudSubmitter\Submitters\Blender\python\modules`
  - For Unix: `pip install deadline PySide2 blender-qt-stylesheet -t ~/DeadlineCloudSubmitter/Submitters/Blender/python/modules`

  Currently, Python 3.10 is the Python version used by the latest Blender release.

2. Install addon in Blender

  Copy the contents of `src/deadline/blender_submitter/addons` to `~/DeadlineCloudSubmitter/Submitters/Blender/python/addons`

3. Add path to Blender script directory

  The path to add is `%USERPROFILE%\DeadlineCloudSubmitter\Submitters\Blender\python` or `~/DeadlineCloudSubmitter/Submitters/Blender/python`
  depending on your OS.

  This can be done manually in Blender under "Edit" > "Preferences" > "File Paths" > "Script Directories".

  Alternatively, you can run this `bpy` command:

  ```
  import os
  bpy.ops.preferences.script_directory_add(directory=os.path.expanduser(os.path.normpath('~/DeadlineCloudSubmitter/Submitters/Blender/python')))
  ```

  Changes to the script directory won't take effect until Blender has been restarted.


#### Install for Development

1. Install required packages. Same as step 1 for Production.

2. Install addon for development

You can run the addon directly from this repository by configuring `src/deadline/blender_submitter` 
of this repository as a script directory in Blender.

You can find this setting under "Edit > Preferences... > File Paths > Script Directories".

Make sure to add the `blender_submitter` directory, not the addons folder!

See: https://docs.blender.org/manual/en/latest/editors/preferences/addons.html#installing-add-ons

Note that the addons directory from the Production installation will conflict with this. It will need to be removed if it exists.

3. Add path to Blender script directory

  The path to add is `%USERPROFILE%\DeadlineCloudSubmitter\Submitters\Blender\python` or `~/DeadlineCloudSubmitter/Submitters/Blender/python`
  depending on your OS.

  This can be done manually in Blender under "Edit" > "Preferences" > "File Paths" > "Script Directories".

  Alternatively, you can run this `bpy` command:

  ```
  import os
  bpy.ops.preferences.script_directory_add(directory=os.path.expanduser(os.path.normpath('~/DeadlineCloudSubmitter/Submitters/Blender/python')))
  ```

  Changes to the script directory won't take effect until Blender has been restarted.

#### Usage

This repository comes with two addons: `deadline_cloud_blender_submitter` and `addonreloader`.

You can enable this in "Edit" menu > "Preferences" menu item > "addons" tab.

* The `addonreloader` is for development purposes only. It is not intended to
  be shipped with the installation. It allows for hot-reloading of the submitter
  addon during development.

## Deadline Cloud for Blender Adaptor

The deadline-cloud-for-blender Adaptor only supports Linux.

### Installation

Build a wheel with `hatch build` and install it as a normal Python package.

## Development notes

### Blender addon version

The Blender addon version is set during the build process via a custom hatch hook.
For new versions, this will require a separate commit after the fact to be tracked properly.

This should instead be done as a pre-build step instead.
