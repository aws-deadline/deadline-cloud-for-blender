---
name: "blender-dev-power"
displayName: "Blender Dev Power"
description: "Development power for deadline-cloud-for-blender - build, lint, test, and run integration tests with Blender."
keywords: ["blender", "deadline", "build", "test", "lint", "integration", "adaptor", "cycles", "eevee"]
author: "AWS Deadline Cloud Team"
---

# Blender Dev Power

Development power for building, testing, and debugging the deadline-cloud-for-blender project.

## Overview

This project is a Python package that provides:
- **Blender Adaptor**: Runs Blender renders on Deadline Cloud workers
- **Blender Submitter**: Add-on for submitting jobs from Blender to Deadline Cloud

## Available Steering Files

- **build-and-test.md** - Complete build and test workflow
- **integration-testing.md** - Guide for running and creating integration tests
- **troubleshooting.md** - Common issues and solutions

## Prerequisites

- Python 3.9-3.12
- Blender 3.6-5.1 (Blender 3.6-4.0 uses Python 3.10, Blender 4.1+ uses Python 3.11)
- Hatch (Python build tool): `pip install hatch`

## Quick Commands

### Build
```bash
hatch build
```

### Lint & Format
```bash
hatch run fmt      # Format code
hatch run lint     # Run linter
hatch run typing   # Type checking (mypy)
```

### Unit Tests
```bash
hatch run test                              # All tests
hatch run test test/unit/path/to/test.py   # Specific file
hatch run test -k "test_cycles"            # Pattern match
```

### Integration Tests

Set `BLENDER_EXECUTABLE` environment variable if Blender is not in PATH:
```bash
export BLENDER_EXECUTABLE=/path/to/blender  # Linux/macOS
set BLENDER_EXECUTABLE=C:\Path\To\blender.exe  # Windows
```

Run integration tests:
```bash
hatch run integ:test
```

For CI testing with multiple Blender versions:
```bash
hatch build  # Must build first
hatch run integ-ci:setup --public-urls  # Download from blender.org
hatch run integ-ci:test
```

## Test Bundles

Integration tests are located in `test/integ/` and cover various rendering scenarios:
- Cycles renderer tests
- Eevee renderer tests
- Scene file handling
- Path mapping tests

## Checking Logs

Blender logs are typically found at:
- **Linux**: `~/.config/blender/{version}/scripts/`
- **macOS**: `~/Library/Application Support/Blender/{version}/scripts/`
- **Windows**: `%APPDATA%\Blender Foundation\Blender\{version}\scripts\`

View recent errors:
```bash
# Linux/macOS
tail -n 100 ~/.config/blender/*/scripts/startup/bl_app_templates_system/*/startup.log

# Windows (PowerShell)
Get-Content "$env:APPDATA\Blender Foundation\Blender\*\scripts\startup.log" -Tail 100
```

## Project Structure

```
src/deadline/
├── blender_adaptor/      # Adaptor (runs on worker)
│   └── BlenderClient/    # Blender client and render handlers
└── blender_submitter/    # Submitter add-on (runs in Blender)
    └── addons/           # Blender add-on structure
test/
├── unit/                 # Unit tests
└── integ/                # Integration tests
scripts/                  # Build and test scripts
```

## Blender Add-on Development

### Manual Installation

1. Build the package: `hatch build`
2. Copy add-on to Blender scripts directory:
   ```bash
   # Linux/macOS
   cp -r src/deadline/blender_submitter/addons/ ~/DeadlineCloudSubmitter/Submitters/Blender/python/addons
   
   # Windows
   xcopy /E /I src\deadline\blender_submitter\addons %USERPROFILE%\DeadlineCloudSubmitter\Submitters\Blender\python\addons
   ```
3. Install dependencies to Blender's Python:
   ```bash
   # For Blender 3.6-4.0 (Python 3.10)
   pip install --python-version 3.10 --only-binary=:all: "deadline[gui]" blender-qt-stylesheet -t ~/DeadlineCloudSubmitter/Submitters/Blender/python/modules
   
   # For Blender 4.1+ (Python 3.11)
   pip install --python-version 3.11 --only-binary=:all: "deadline[gui]" blender-qt-stylesheet -t ~/DeadlineCloudSubmitter/Submitters/Blender/python/modules
   ```
4. Add script directory in Blender: Edit > Preferences > File Paths > Script Directories
5. Restart Blender

### Experimental: Portable Add-on

Build a portable Blender add-on:
```bash
hatch build
hatch run build-addon
```

This creates `dist_extras/deadline-cloud-blender-addon.zip` which can be installed directly in Blender via Edit > Preferences > Add-ons > Install from Disk.

## Adaptor Usage

After installation, the adaptor is available as a command-line tool:
```bash
blender-openjd --help
```

Set `BLENDER_EXECUTABLE` environment variable to specify Blender location if not in PATH.
