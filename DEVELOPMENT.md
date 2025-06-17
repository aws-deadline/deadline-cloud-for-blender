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

### Build the installer
```bash
hatch run build-installer --local-dev-build --platform <PLATFORM> [--install-builder-location <LOCATION> --output-dir <DIR>]
```

Run `hatch run build-installer -h` to see the full list of arguments.

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

### Test a local installer
```bash
hatch run test-installer
```

### Run Integration Tests

1. If you can run `blender` from your terminal or on Windows/MacOS you did a default Blender install,
   the tests will find Blender automatically. Otherwise, set the environment variable `BLENDER_EXECUTABLE`
   to the location of your Blender application.
2. Run `hatch run integ:test`

### Manual Installation

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
    - For Blender 4.1-4.2 (uses python 3.11):
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

#### Experimental: Build and install a portable Blender add-on
There's an alternative packaging method for the add-on that's simpler to build and install.
1. Build the package with `hatch build`
1. From the repo root, run `hatch run build-addon`. The script will generate a portable Blender add-on under `dist_extras/deadline-cloud-blender-addon.zip`.
2. Go to Blender, click the Edit menu, select Preferences..., click the Add-ons tab, click the downward facing arrow in the upper right, then click Install from Disk... Select the zip file from the previous step.
3. The add-on is now installed! You can the new Submit to AWS Deadline Cloud option in the Render menu.

The `script/build_addon.py` script enables the add-on to be installed and updated inside Blender. The script generates a native Blender add-on `deadline-cloud-blender-addon.zip` which is a zip file with a specific structure. The zip contains a `blender_manifest.toml` file which describes the plug-in and a `wheels/` directory that contains the submitter dependencies. In addition to add-on itself, the script generates an `index.json` file which is a Blender extensions repository index. The index describes the available add-ons and where to download them. If the the addon and index are hosted on the web and if the index's URL is added to Blender as an extensions repository, Blender will present the add-on in the list of installable extensions.

See [Blender's extension docs](https://docs.blender.org/manual/en/latest/advanced/extensions/getting_started.html) for more detail. See the README.md for instructions on using this repo's releases as a Blender extension repository.

#### Usage

This repository comes with the addon: `deadline_cloud_blender_submitter`

You can enable this in "Edit" menu > "Preferences" menu item > "addons" tab.

## Deadline Cloud for Blender Adaptor

The deadline-cloud-for-blender Adaptor supports Linux, macOS and Windows.

### Installation

Build a wheel with `hatch build` and install it as a normal Python package.
