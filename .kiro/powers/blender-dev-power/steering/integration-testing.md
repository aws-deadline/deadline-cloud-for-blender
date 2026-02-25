# Integration Testing Guide

Guide for running and creating integration tests for deadline-cloud-for-blender.

## Overview

Integration tests verify that the Blender adaptor correctly:
- Launches Blender
- Loads scene files
- Configures render settings
- Renders frames
- Handles different render engines (Cycles, Eevee)
- Manages asset references and paths

## Running Integration Tests

### Prerequisites

1. **Blender installed** (3.6-5.0)
2. **BLENDER_EXECUTABLE set** (if not in PATH):
   ```bash
   export BLENDER_EXECUTABLE=/path/to/blender
   ```
3. **pywin32 installed** (Windows only):
   ```bash
   pip install -r requirements-integ-testing.txt --python-version=3.11 --only-binary=:all: --target "C:\Program Files\Blender Foundation\Blender 4.2\4.2\python\lib\site-packages\"
   ```

### Run All Integration Tests

```bash
hatch run integ:test
```

### Run Specific Tests

```bash
# Run tests for a specific module
hatch run integ:test test/integ/test_adaptor.py

# Run tests matching a pattern
hatch run integ:test -k "cycles"

# Run with verbose output
hatch run integ:test -v
```

## Test Structure

Integration tests are located in `test/integ/` and typically include:

```
test/integ/
├── test_adaptor.py           # Main adaptor tests
├── test_scripts/             # Test job bundles
│   ├── cycles_test/
│   │   ├── expected_job_bundle/
│   │   │   ├── template.yaml
│   │   │   ├── parameter_values.json
│   │   │   └── asset_references.json
│   │   └── scene.blend
│   └── eevee_test/
│       └── ...
└── conftest.py               # Pytest fixtures
```

## Creating a New Integration Test

### Step 1: Create Test Scene

Create a simple Blender scene that tests your feature:

```python
import bpy

# Clear default scene
bpy.ops.wm.read_homefile(use_empty=True)

# Add a simple object
bpy.ops.mesh.primitive_cube_add()

# Configure render settings
scene = bpy.context.scene
scene.render.engine = 'CYCLES'
scene.cycles.samples = 10
scene.render.resolution_x = 640
scene.render.resolution_y = 480
scene.frame_start = 1
scene.frame_end = 1

# Save scene
bpy.ops.wm.save_as_mainfile(filepath='/path/to/test_scene.blend')
```

### Step 2: Create Job Bundle

Create a job bundle directory structure:

```
test/integ/test_scripts/my_feature_test/
├── expected_job_bundle/
│   ├── template.yaml
│   ├── parameter_values.json
│   └── asset_references.json
└── test_scene.blend
```

#### template.yaml

```yaml
specificationVersion: 'jobtemplate-2023-09'
name: Blender My Feature Test
parameterDefinitions:
  - name: BlenderFile
    type: PATH
    objectType: FILE
    dataFlow: IN
  - name: Frames
    type: STRING
    default: '1'

steps:
  - name: Render
    parameterSpace:
      taskParameterDefinitions:
        - name: Frame
          type: INT
          range: "{{Param.Frames}}"
    stepEnvironments:
      - name: Blender
        script:
          actions:
            onEnter:
              command: blender-openjd
              args:
                - daemon
                - start
                - --path-mapping-rules
                - file://{{Session.PathMappingRulesFile}}
            onExit:
              command: blender-openjd
              args:
                - daemon
                - stop
    script:
      actions:
        onRun:
          command: blender-openjd
          args:
            - daemon
            - run
            - --render-scene
            - file://{{Param.BlenderFile}}
            - --frame
            - "{{Task.Frame}}"
```

#### parameter_values.json

```json
{
  "parameterValues": [
    {
      "name": "BlenderFile",
      "value": "{{Session.WorkingDirectory}}/test_scene.blend"
    },
    {
      "name": "Frames",
      "value": "1"
    }
  ]
}
```

#### asset_references.json

```json
{
  "assetReferences": {
    "inputs": {
      "directories": [],
      "filenames": [
        "test_scene.blend"
      ]
    },
    "outputs": {
      "directories": []
    }
  }
}
```

### Step 3: Write Test Code

Add test to `test/integ/test_adaptor.py`:

```python
import pytest
from pathlib import Path

@pytest.mark.adaptor
@pytest.mark.scene_files("test_scene.blend")
def test_my_feature(
    blender_client,
    job_bundle_dir: Path,
    output_dir: Path,
):
    """Test my feature with Blender adaptor."""
    # Run the job bundle
    blender_client.run_job_bundle(
        job_bundle_dir=job_bundle_dir / "expected_job_bundle",
        output_dir=output_dir,
    )
    
    # Verify output
    output_file = output_dir / "0001.png"
    assert output_file.exists(), "Render output not found"
    
    # Optional: Verify image content
    from PIL import Image
    img = Image.open(output_file)
    assert img.size == (640, 480), "Unexpected image size"
```

## Testing Different Render Engines

### Cycles Test

```python
@pytest.mark.adaptor
@pytest.mark.scene_files("cycles_scene.blend")
def test_cycles_render(blender_client, job_bundle_dir, output_dir):
    """Test Cycles renderer."""
    blender_client.run_job_bundle(
        job_bundle_dir=job_bundle_dir / "expected_job_bundle",
        output_dir=output_dir,
    )
    # Verify output...
```

### Eevee Test

```python
@pytest.mark.adaptor
@pytest.mark.scene_files("eevee_scene.blend")
def test_eevee_render(blender_client, job_bundle_dir, output_dir):
    """Test Eevee renderer."""
    blender_client.run_job_bundle(
        job_bundle_dir=job_bundle_dir / "expected_job_bundle",
        output_dir=output_dir,
    )
    # Verify output...
```

## Testing Path Mapping

Create a test with path mapping rules:

```python
@pytest.mark.adaptor
@pytest.mark.scene_files("scene_with_textures.blend")
def test_path_mapping(blender_client, job_bundle_dir, output_dir, tmp_path):
    """Test path mapping for texture references."""
    # Create path mapping rules
    path_mapping_rules = {
        "version": "pathmapping-1.0",
        "path_mappings": [
            {
                "source_path_format": "POSIX",
                "source_path": "/original/path",
                "destination_path": str(tmp_path / "remapped")
            }
        ]
    }
    
    # Run with path mapping
    blender_client.run_job_bundle(
        job_bundle_dir=job_bundle_dir / "expected_job_bundle",
        output_dir=output_dir,
        path_mapping_rules=path_mapping_rules,
    )
    # Verify output...
```

## CI Integration Tests

For testing with multiple Blender versions in CI:

```bash
# Setup (downloads Blender versions)
hatch run integ-ci:setup --public-urls --versions "4.2.12 4.5.4"

# Run tests
hatch run integ-ci:test
```

The `integ-ci` environment uses a matrix to test against multiple Blender versions defined in `pyproject.toml`.

## Debugging Integration Tests

### Enable Verbose Logging

```bash
hatch run integ:test -v -s
```

### Check Blender Output

Integration tests capture Blender's stdout/stderr. Check test output for errors.

### Run Blender Manually

Test the adaptor manually:

```bash
# Start daemon
blender-openjd daemon start

# Run render
blender-openjd daemon run --render-scene /path/to/scene.blend --frame 1

# Stop daemon
blender-openjd daemon stop
```

### Inspect Test Output

Integration tests create output in a temporary directory. Use `--basetemp` to specify a location:

```bash
hatch run integ:test --basetemp=/tmp/blender-test-output
```

## Common Issues

### Blender Not Found
Set BLENDER_EXECUTABLE or add Blender to PATH

### Headless Rendering on Linux
Install X11 libraries and use Xvfb:
```bash
hatch run integ-ci:setup --install-x11
```

### Scene File Not Found
Ensure scene files are in the correct location relative to the job bundle

### Render Output Missing
Check Blender logs and verify render settings in the scene file
