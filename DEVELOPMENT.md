# AWS Deadline Cloud for Blender Development

This package has two active branches:

- `mainline` -- For active development. This branch is not intended to be consumed by other packages. Any commit to this branch may break APIs, dependencies, and so on, and thus break any consumer without notice.
- `release` -- The official release of the package intended for consumers. Any breaking releases will be accompanied with an increase to this package's interface version.

The deadline.blender_adaptor package is an adaptor that renders blender scenes through the blender executable. It uses the Open Job Description adaptor_runtime and supports job stickiness.

## Build / Test / Release

### Build the package

```bash
hatch run build
```

### Run tests

```bash
hatch run test
```

### Run linting

```bash
hatch run lint
```

### Run formatting

```bash
hatch run fmt
```

### Run tests for all supported Python versions

```bash
hatch run all:test
```

### Installation

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

These instructions make the following assumptions:
  * You have a [git clone of this repository](https://docs.github.com/en/repositories/creating-and-managing-repositories/cloning-a-repository#cloning-a-repository)
  * You have `pip` available in your terminal

1. Set-up development environment:
    - `pip install --upgrade -r requirements-development.txt`
1. Install addon in Blender
    - run `hatch build` in your local git repository
    - `cp -r src/deadline/blender_submitter/addons/ ~/DeadlineCloudSubmitter/Submitters/Blender/python/addons`
1. Install addon dependencies:
    - For Blender 3.6-4.0 (uses python 3.10):
        - Windows: `pip install --python-version 3.10 --only-binary=:all: "deadline[gui]" blender-qt-stylesheet -t %USERPROFILE%\DeadlineCloudSubmitter\Submitters\Blender\python\modules`
        - Linux/macOS: `pip install --python-version 3.10 --only-binary=:all: "deadline[gui]" blender-qt-stylesheet -t ~/DeadlineCloudSubmitter/Submitters/Blender/python/modules`
    - For Blender 4.1 (uses python 3.11):
        - Windows: `pip install --python-version 3.11 --only-binary=:all: "deadline[gui]" blender-qt-stylesheet -t %USERPROFILE%\DeadlineCloudSubmitter\Submitters\Blender\python\modules`
        - Linux/macOS: `pip install --python-version 3.11 --only-binary=:all: "deadline[gui]" blender-qt-stylesheet -t ~/DeadlineCloudSubmitter/Submitters/Blender/python/modules`
1. Add a script directory in Blender by "Edit" > "Preferences" > "File Paths" > "Script Directories"
    * Windows: `%USERPROFILE%\DeadlineCloudSubmitter\Submitters\Blender\python`
    * Linux/macOS: `~/DeadlineCloudSubmitter/Submitters/Blender/python`

    Or run this script from Blender

    ```
    import bpy
    from os.path import expanduser, normpath
    bpy.ops.preferences.script_directory_add(directory=expanduser(normpath('~/DeadlineCloudSubmitter/Submitters/Blender/python')))
    ```
1. Restart Blender - changes to the script directory won't take effect until Blender has been restarted.

#### Usage

This repository comes with the addon: `deadline_cloud_blender_submitter`

You can enable this in "Edit" menu > "Preferences" menu item > "addons" tab.

## Deadline Cloud for Blender Adaptor

The deadline-cloud-for-blender Adaptor supports Linux and macOS.

### Installation

Build a wheel with `hatch build` and install it as a normal Python package.
