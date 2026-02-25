# Build and Test Workflow

Complete build and test workflow for deadline-cloud-for-blender.

## Step 1: Build the Wheel

Always build a fresh wheel before testing:

```bash
hatch build
```

This creates a wheel in `dist/deadline_cloud_for_blender-*.whl`

## Step 2: Run Linting and Formatting

Before committing, ensure code passes all checks:

```bash
# Format code
hatch run fmt

# Run linter
hatch run lint

# Run type checker (mypy)
hatch run typing
```

## Step 3: Run Unit Tests

Run the full unit test suite:

```bash
hatch run test
```

For faster iteration, run specific tests:

```bash
# Run tests for a specific module
hatch run test test/unit/deadline/blender_adaptor/BlenderClient/

# Run a single test file
hatch run test test/unit/deadline/blender_adaptor/BlenderClient/render_handlers/test_default_blender_handler.py

# Run tests matching a pattern
hatch run test -k "test_cycles"
```

## Step 4: Run Integration Tests

Integration tests require Blender to be installed.

### Set Blender Executable

If Blender is not in your PATH, set the environment variable:

```bash
# Linux/macOS
export BLENDER_EXECUTABLE=/path/to/blender

# Windows (PowerShell)
$env:BLENDER_EXECUTABLE = "C:\Program Files\Blender Foundation\Blender 4.2\blender.exe"

# Windows (CMD)
set BLENDER_EXECUTABLE=C:\Program Files\Blender Foundation\Blender 4.2\blender.exe
```

### Run Integration Tests

```bash
hatch run integ:test
```

### Windows-Specific: Install pywin32

On Windows, you need to install pywin32 to Blender's Python:

```bash
# For Blender 4.1+ (Python 3.11)
pip install -r requirements-integ-testing.txt --python-version=3.11 --only-binary=:all: --target "C:\Program Files\Blender Foundation\Blender 4.2\4.2\python\lib\site-packages\"

# For Blender 3.6-4.0 (Python 3.10)
pip install -r requirements-integ-testing.txt --python-version=3.10 --only-binary=:all: --target "C:\Program Files\Blender Foundation\Blender 4.0\4.0\python\lib\site-packages\"
```

### CI Integration Tests

For testing with multiple Blender versions:

```bash
# Build package first
hatch build

# Setup Blender versions (downloads from blender.org)
hatch run integ-ci:setup --public-urls

# Run tests
hatch run integ-ci:test
```

Setup script options:
- `--public-urls`: Download from blender.org with SHA256 verification
- `--install-x11`: Install X11 libraries and start Xvfb on Linux (for headless rendering)
- `--versions 4.2.12 4.5.4`: Specify Blender versions to install
- `--python-version 3.11`: Specify Python version for pip installs

## Step 5: Build Portable Add-on

Build a portable Blender add-on that can be installed directly in Blender:

```bash
hatch build
hatch run build-addon
```

This creates `dist_extras/deadline-cloud-blender-addon.zip` which includes:
- The add-on code
- All dependencies (deadline, openjd-adaptor-runtime, etc.)
- `blender_manifest.toml` for Blender 4.2+ extension system

### Install Portable Add-on

1. Open Blender
2. Edit > Preferences > Add-ons
3. Click the dropdown arrow in the upper right
4. Click "Install from Disk..."
5. Select `dist_extras/deadline-cloud-blender-addon.zip`
6. Enable the "AWS Deadline Cloud" add-on

## Step 6: Build Adaptor Wheels (Developer Option)

For testing adaptor changes on a live Deadline Cloud farm, build wheels for all dependencies.

### Prerequisites

The sibling repositories must be cloned:
```
workspace/
├── openjd-adaptor-runtime-for-python/
├── deadline-cloud/
└── deadline-cloud-for-blender/
```

Clone missing repositories:
```bash
cd ~/workspace/blender
git clone https://github.com/OpenJobDescription/openjd-adaptor-runtime-for-python.git
git clone https://github.com/aws-deadline/deadline-cloud.git
```

### Build Wheels Script

Create a script to build all wheels:

```bash
#!/bin/bash
# build_wheels.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKSPACE_DIR="$(dirname "$SCRIPT_DIR")"
WHEELS_DIR="$SCRIPT_DIR/wheels"

# Clean wheels directory if requested
if [ "$1" == "--clean" ]; then
    rm -rf "$WHEELS_DIR"
fi

mkdir -p "$WHEELS_DIR"

# Build openjd-adaptor-runtime
if [ -d "$WORKSPACE_DIR/openjd-adaptor-runtime-for-python" ]; then
    echo "Building openjd-adaptor-runtime..."
    cd "$WORKSPACE_DIR/openjd-adaptor-runtime-for-python"
    hatch build -t wheel
    cp dist/*.whl "$WHEELS_DIR/"
fi

# Build deadline-cloud
if [ -d "$WORKSPACE_DIR/deadline-cloud" ]; then
    echo "Building deadline-cloud..."
    cd "$WORKSPACE_DIR/deadline-cloud"
    hatch build -t wheel
    cp dist/*.whl "$WHEELS_DIR/"
fi

# Build deadline-cloud-for-blender
echo "Building deadline-cloud-for-blender..."
cd "$SCRIPT_DIR"
hatch build -t wheel
cp dist/*.whl "$WHEELS_DIR/"

echo "Wheels built in $WHEELS_DIR"
ls -lh "$WHEELS_DIR"
```

### Testing Adaptor Wheels on Workers

1. **Enable developer options** in Blender submitter settings

2. **Add wheels directory** to Job Attachments:
   - In the submitter, go to Job Attachments tab
   - Add the `wheels/` directory

3. **Submit the job** - The worker will:
   - Create a Python virtual environment
   - Install your development wheels
   - Use your modified adaptor to run the job

## Step 7: Check Logs

Blender logs are typically found at:

```bash
# Linux
tail -n 100 ~/.config/blender/*/scripts/startup.log

# macOS
tail -n 100 ~/Library/Application\ Support/Blender/*/scripts/startup.log

# Windows (PowerShell)
Get-Content "$env:APPDATA\Blender Foundation\Blender\*\scripts\startup.log" -Tail 100
```

For adaptor logs during integration tests, check the test output directory.

## Common Issues

### Wrong Python Version
Ensure Blender Python is being used:
```bash
blender --background --python-expr "import sys; print(sys.version)"
```

### Wheel Not Found
Build the wheel first: `hatch build`

### Blender Not Found
Set BLENDER_EXECUTABLE environment variable or add Blender to PATH

### Add-on Not Loading
1. Verify script directory is added in Blender preferences
2. Restart Blender after adding script directory
3. Check for errors in Blender's system console (Window > Toggle System Console on Windows)

### Integration Tests Fail on Linux
Install X11 libraries and use Xvfb for headless rendering:
```bash
hatch run integ-ci:setup --install-x11
```
