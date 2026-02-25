---
name: blender-dev-setup
version: 1.0.0
displayName: Blender Dev Setup
description: Automated development environment setup for deadline-cloud-for-blender - builds packages, installs dependencies, and configures environment variables
keywords:
  - blender
  - deadline
  - setup
  - build
  - install
  - environment
  - development
  - hatch
  - openjd
author: AWS Deadline Cloud
---

# Blender Dev Setup Power

Automated development environment setup for deadline-cloud-for-blender project.

## What This Power Does

This power automates the complete development environment setup for working on the deadline-cloud-for-blender project. It handles everything from reading documentation to building packages, installing dependencies, and configuring environment variables.

## Setup Steps Performed

1. **Documentation Review** - Reads README.md and DEVELOPMENT.md to understand project requirements
2. **Hatch Installation** - Installs and configures Hatch build tool
3. **Package Build** - Builds wheel and source distributions
4. **Blender Detection** - Verifies Blender installation (3.6-5.0)
5. **Add-on Installation** - Installs the Blender submitter add-on
6. **Dependencies Installation** - Installs deadline[gui], blender-qt-stylesheet
7. **Wheel Installation** - Installs the built wheel for adaptor
8. **OpenJD CLI Installation** - Installs openjd-cli for running integration tests
9. **Test Packages Installation** - Installs pytest, coverage, and test dependencies
10. **Environment Configuration** - Sets up BLENDER_EXECUTABLE and PYTHONPATH

## Prerequisites

- Python 3.9-3.12 installed on system
- Blender 3.6-5.0 installed
- Linux, macOS, or Windows operating system

## Usage

The power will prompt you for:
- **Blender Version** (e.g., 3.6, 4.0, 4.2, 5.0)
- **Blender Installation Path** (if not in standard location)

If Blender is not found, the setup will provide instructions for installation.

## What Gets Installed

### System Python Packages
- `hatch` - Build tool and environment manager

### Blender Python Packages (via pip to modules directory)
- `deadline[gui]` - AWS Deadline Cloud client library with GUI support
- `blender-qt-stylesheet` - Qt stylesheet for Blender integration
- All required dependencies

### Development Packages
- `deadline-cloud-for-blender` - The built wheel from dist/
- `openjd-adaptor-runtime` - OpenJD adaptor runtime
- `openjd-cli` - OpenJD command-line interface
- `pytest` - Test framework
- `pytest-cov` - Coverage plugin for pytest
- `pytest-xdist` - Parallel test execution
- `coverage` - Code coverage measurement

### Environment Variables
- `BLENDER_EXECUTABLE` - Points to blender executable
- `PYTHONPATH` - Configures Python module search paths (if needed)

## Platform-Specific Paths

### Linux
- Add-on: `~/DeadlineCloudSubmitter/Submitters/Blender/python/addons`
- Modules: `~/DeadlineCloudSubmitter/Submitters/Blender/python/modules`
- Blender config: `~/.config/blender/{version}/scripts/`

### macOS
- Add-on: `~/DeadlineCloudSubmitter/Submitters/Blender/python/addons`
- Modules: `~/DeadlineCloudSubmitter/Submitters/Blender/python/modules`
- Blender config: `~/Library/Application Support/Blender/{version}/scripts/`

### Windows
- Add-on: `%USERPROFILE%\DeadlineCloudSubmitter\Submitters\Blender\python\addons`
- Modules: `%USERPROFILE%\DeadlineCloudSubmitter\Submitters\Blender\python\modules`
- Blender config: `%APPDATA%\Blender Foundation\Blender\{version}\scripts\`

## Output Files

The power creates several reference documents:
- `HATCH_SETUP.md` - Hatch usage guide
- `configure_blender_env.sh` or `.ps1` - Environment configuration script
- `verify_blender_paths.sh` or `.ps1` - Path verification script
- `INSTALLATION_SUMMARY.md` - Complete installation summary
- `OPENJD_SETUP_COMPLETE.md` - OpenJD usage guide

## After Setup

Once setup is complete, you can:

### Run Unit Tests
```bash
hatch run test
```

### Run Integration Tests
```bash
hatch run integ:test
```

### Build Package
```bash
hatch build
```

### Format and Lint Code
```bash
hatch run fmt
hatch run lint
```

### Build Portable Add-on
```bash
hatch run build-addon
```

## Troubleshooting

### Hatch Not Found
If hatch is not found after installation, restart your terminal or add to PATH:
```bash
# Linux/macOS
export PATH="$HOME/.local/bin:$PATH"

# Windows (PowerShell)
$env:PATH = "$env:USERPROFILE\AppData\Roaming\Python\Python311\Scripts;$env:PATH"
```

### Blender Python Issues
Verify the correct Python version for your Blender:
- Blender 3.6-4.0: Python 3.10
- Blender 4.1+: Python 3.11

Check Blender's Python:
```bash
blender --background --python-expr "import sys; print(sys.version)"
```

### Add-on Not Appearing
1. Verify script directory is added in Blender: Edit > Preferences > File Paths
2. Restart Blender after adding script directory
3. Enable add-on in Edit > Preferences > Add-ons (search for "AWS Deadline Cloud")

### Integration Tests Failing
Check Blender logs and ensure BLENDER_EXECUTABLE is set:
```bash
# Linux/macOS
export BLENDER_EXECUTABLE=/path/to/blender

# Windows
set BLENDER_EXECUTABLE=C:\Path\To\blender.exe
```

### Windows-Specific: pywin32 Required
On Windows, install pywin32 to Blender's Python:
```bash
pip install -r requirements-integ-testing.txt --python-version=3.11 --only-binary=:all: --target "C:\Program Files\Blender Foundation\Blender {version}\{version}\python\lib\site-packages\"
```

## Notes

- Setup works on Linux, macOS, and Windows
- Blender 4.2+ supports the experimental extension repository method
- The adaptor requires Blender executable to be in PATH or BLENDER_EXECUTABLE set
- Integration tests may require X11/Xvfb on Linux for headless rendering
