# Troubleshooting Guide

Common issues and solutions for deadline-cloud-for-blender development.

## Build Issues

### Hatch Not Found

**Symptom**: `hatch: command not found`

**Solution**:
```bash
# Install hatch
pip install hatch

# Add to PATH (Linux/macOS)
export PATH="$HOME/.local/bin:$PATH"

# Add to PATH (Windows PowerShell)
$env:PATH = "$env:USERPROFILE\AppData\Roaming\Python\Python311\Scripts;$env:PATH"
```

### Build Fails with Missing Dependencies

**Symptom**: Build fails with import errors

**Solution**:
```bash
# Install development dependencies
pip install --upgrade -r requirements-development.txt

# Rebuild
hatch build
```

### Version File Not Generated

**Symptom**: `_version.py` not found

**Solution**:
```bash
# Ensure hatch-vcs is installed
pip install hatch-vcs

# Clean and rebuild
rm -rf dist/ build/
hatch build
```

## Blender Add-on Issues

### Add-on Not Appearing in Blender

**Symptom**: Add-on not visible in Preferences > Add-ons

**Solution**:
1. Verify script directory is added:
   - Edit > Preferences > File Paths > Script Directories
   - Add: `~/DeadlineCloudSubmitter/Submitters/Blender/python` (Linux/macOS)
   - Add: `%USERPROFILE%\DeadlineCloudSubmitter\Submitters\Blender\python` (Windows)

2. Restart Blender (required after adding script directory)

3. Check add-on is copied correctly:
   ```bash
   ls ~/DeadlineCloudSubmitter/Submitters/Blender/python/addons/deadline_cloud_blender_submitter/
   ```

### Add-on Fails to Load

**Symptom**: Error when enabling add-on in Blender

**Solution**:
1. Check Blender's system console for errors:
   - Windows: Window > Toggle System Console
   - Linux/macOS: Run Blender from terminal to see output

2. Verify dependencies are installed:
   ```bash
   # For Blender 4.1+ (Python 3.11)
   pip install --python-version 3.11 --only-binary=:all: "deadline[gui]" blender-qt-stylesheet -t ~/DeadlineCloudSubmitter/Submitters/Blender/python/modules
   
   # For Blender 3.6-4.0 (Python 3.10)
   pip install --python-version 3.10 --only-binary=:all: "deadline[gui]" blender-qt-stylesheet -t ~/DeadlineCloudSubmitter/Submitters/Blender/python/modules
   ```

3. Check Python version matches Blender:
   ```bash
   blender --background --python-expr "import sys; print(sys.version)"
   ```

### Import Errors in Add-on

**Symptom**: `ModuleNotFoundError` when using add-on

**Solution**:
1. Verify modules directory exists and contains packages:
   ```bash
   ls ~/DeadlineCloudSubmitter/Submitters/Blender/python/modules/
   ```

2. Reinstall dependencies with correct Python version

3. Check for conflicting packages in Blender's Python

## Adaptor Issues

### Blender Executable Not Found

**Symptom**: `BLENDER_EXECUTABLE not set` or `blender: command not found`

**Solution**:
```bash
# Set environment variable (Linux/macOS)
export BLENDER_EXECUTABLE=/path/to/blender

# Set environment variable (Windows PowerShell)
$env:BLENDER_EXECUTABLE = "C:\Program Files\Blender Foundation\Blender 4.2\blender.exe"

# Or add Blender to PATH
export PATH="/path/to/blender/directory:$PATH"
```

### Adaptor Fails to Start

**Symptom**: `blender-openjd daemon start` fails

**Solution**:
1. Check Blender can run in background mode:
   ```bash
   blender --background --python-expr "print('OK')"
   ```

2. Verify adaptor is installed:
   ```bash
   pip show deadline-cloud-for-blender
   ```

3. Check for port conflicts (adaptor uses socket communication)

### Render Fails with Scene File Error

**Symptom**: Cannot load scene file

**Solution**:
1. Verify scene file path is absolute or properly resolved
2. Check file permissions
3. Ensure scene file is compatible with Blender version
4. Test loading scene manually:
   ```bash
   blender --background /path/to/scene.blend --python-expr "import bpy; print(bpy.context.scene.name)"
   ```

## Integration Test Issues

### Tests Fail to Find Blender

**Symptom**: Integration tests skip or fail with "Blender not found"

**Solution**:
```bash
# Set BLENDER_EXECUTABLE before running tests
export BLENDER_EXECUTABLE=/path/to/blender
hatch run integ:test
```

### Windows: pywin32 Missing

**Symptom**: `ImportError: No module named 'win32api'`

**Solution**:
```bash
# Install pywin32 to Blender's Python
pip install -r requirements-integ-testing.txt --python-version=3.11 --only-binary=:all: --target "C:\Program Files\Blender Foundation\Blender 4.2\4.2\python\lib\site-packages\"
```

### Linux: Headless Rendering Fails

**Symptom**: Tests fail with display errors

**Solution**:
```bash
# Install X11 libraries and Xvfb
hatch run integ-ci:setup --install-x11

# Or manually install
sudo apt-get install xvfb libxxf86vm1 libxfixes3 libxi6 libxkbcommon0 libgl1

# Run with Xvfb
xvfb-run -a hatch run integ:test
```

### Test Output Not Generated

**Symptom**: Render output files not created

**Solution**:
1. Check Blender logs for render errors
2. Verify output path is writable
3. Check render settings in scene file
4. Test render manually:
   ```bash
   blender --background scene.blend --render-output /tmp/output --render-frame 1
   ```

## Linting and Type Checking Issues

### Ruff Linting Errors

**Symptom**: `hatch run lint` fails

**Solution**:
```bash
# Auto-fix issues
hatch run fmt

# Check specific files
hatch run lint src/deadline/blender_adaptor/
```

### Mypy Type Errors

**Symptom**: `hatch run typing` fails

**Solution**:
1. Check mypy configuration in `pyproject.toml`
2. Add type stubs for missing packages:
   ```bash
   pip install types-requests types-PyYAML
   ```
3. Use `# type: ignore` for unavoidable errors (sparingly)

## Performance Issues

### Slow Integration Tests

**Solution**:
1. Run specific tests instead of full suite:
   ```bash
   hatch run integ:test -k "test_name"
   ```

2. Use parallel test execution:
   ```bash
   hatch run integ:test -n auto
   ```

3. Skip slow tests during development:
   ```bash
   hatch run integ:test -m "not slow"
   ```

### Slow Blender Startup

**Solution**:
1. Use sticky rendering (adaptor keeps Blender open between tasks)
2. Reduce scene complexity for tests
3. Use lower sample counts for test renders

## Debugging Tips

### Enable Debug Logging

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

### Run Adaptor in Debug Mode

```bash
# Set debug environment variable
export OPENJD_LOG_LEVEL=DEBUG

# Run adaptor
blender-openjd daemon start
```

### Inspect Blender Scene

```bash
# Open scene in Blender GUI
blender /path/to/scene.blend

# Inspect scene from command line
blender --background /path/to/scene.blend --python-expr "
import bpy
scene = bpy.context.scene
print(f'Render engine: {scene.render.engine}')
print(f'Frame range: {scene.frame_start}-{scene.frame_end}')
print(f'Resolution: {scene.render.resolution_x}x{scene.render.resolution_y}')
"
```

### Check Blender Python Environment

```bash
blender --background --python-expr "
import sys
print('Python version:', sys.version)
print('Python path:', sys.path)
import pip
installed = pip.get_installed_distributions()
for pkg in installed:
    print(f'{pkg.key}: {pkg.version}')
"
```

## Getting Help

If you're still stuck:

1. Check the [GitHub Issues](https://github.com/aws-deadline/deadline-cloud-for-blender/issues)
2. Review the [Blender Python API documentation](https://docs.blender.org/api/current/)
3. Check [OpenJD documentation](https://github.com/OpenJobDescription/openjd-specifications/wiki)
4. Review [AWS Deadline Cloud documentation](https://docs.aws.amazon.com/deadline-cloud/)
