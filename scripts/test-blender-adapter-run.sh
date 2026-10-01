#!/usr/bin/env bash
# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
#
# Blender Adaptor Testing Script (Bash)
# Tests the deadline-cloud-for-blender adaptor directly without worker agent setup.
# Uses Blender's bundled Python (Blender ships Python under <install>/<X.Y>/python/bin/...).
#
# Works on Linux, macOS, and Windows (via Git Bash / WSL).

set -u

# ------------------------------------------------------------------
# Color helpers
# ------------------------------------------------------------------
if [ -t 1 ]; then
    C_RESET=$'\033[0m'
    C_RED=$'\033[31m'
    C_GREEN=$'\033[32m'
    C_YELLOW=$'\033[33m'
    C_CYAN=$'\033[36m'
    C_GRAY=$'\033[90m'
else
    C_RESET="" C_RED="" C_GREEN="" C_YELLOW="" C_CYAN="" C_GRAY=""
fi

info()    { printf "%s%s%s\n" "$C_CYAN"   "$*" "$C_RESET"; }
ok()      { printf "%s%s%s\n" "$C_GREEN"  "$*" "$C_RESET"; }
warn()    { printf "%s%s%s\n" "$C_YELLOW" "$*" "$C_RESET"; }
err()     { printf "%s%s%s\n" "$C_RED"    "$*" "$C_RESET" >&2; }
section() { printf "\n%s--- %s ---%s\n" "$C_YELLOW" "$*" "$C_RESET"; }
gray()    { printf "%s%s%s\n" "$C_GRAY"   "$*" "$C_RESET"; }

# ------------------------------------------------------------------
# Defaults
# ------------------------------------------------------------------
JOB_BUNDLE_DIR=""
WHEEL_PATH=""
BLENDER_EXE=""
BLENDER_PYTHON=""
STEP=0
PATH_MAPPING_FILE=""
SKIP_INSTALL=0
SHOW_OUTPUT=0

usage() {
    cat <<EOF
=== Blender Adaptor Testing Script Help ===

DESCRIPTION:
  Tests the deadline-cloud-for-blender adaptor directly without worker agent setup.
  Uses Blender's bundled Python. Runs on Linux, macOS, and Windows (via Git Bash / WSL).

USAGE:
  Run from the repository root directory:
  ./scripts/test-blender-adapter-run.sh --job-bundle-dir <path> [options]

OPTIONS:
  -j, --job-bundle-dir <dir>    (Required) Path to the job bundle directory
  -w, --wheel-path <path>       Path to the wheel file (auto-detects dist/*.whl if omitted)
  -b, --blender <path>          Path to the Blender executable (defaults to BLENDER_EXECUTABLE env or 'blender' on PATH)
  -p, --blender-python <path>   Path to Blender's bundled Python (derived from Blender install if omitted)
  -s, --step <n>                Step index to run (default: 0)
  -m, --path-mapping-file <p>   Path to JSON file with path mapping rules (optional)
      --skip-install            Skip wheel installation
      --show-output             Show detailed output
  -h, --help                    Show this help and exit

PREREQUISITES:
  - Blender installed (ships its own Python; no system Python required)
EOF
}

# ------------------------------------------------------------------
# Argument parsing
# ------------------------------------------------------------------
while [ $# -gt 0 ]; do
    case "$1" in
        -j|--job-bundle-dir)     JOB_BUNDLE_DIR="$2"; shift 2 ;;
        --job-bundle-dir=*)      JOB_BUNDLE_DIR="${1#*=}"; shift ;;
        -w|--wheel-path)         WHEEL_PATH="$2"; shift 2 ;;
        --wheel-path=*)          WHEEL_PATH="${1#*=}"; shift ;;
        -b|--blender|--blender-executable) BLENDER_EXE="$2"; shift 2 ;;
        --blender=*|--blender-executable=*) BLENDER_EXE="${1#*=}"; shift ;;
        -p|--blender-python)     BLENDER_PYTHON="$2"; shift 2 ;;
        --blender-python=*)      BLENDER_PYTHON="${1#*=}"; shift ;;
        -s|--step)               STEP="$2"; shift 2 ;;
        --step=*)                STEP="${1#*=}"; shift ;;
        -m|--path-mapping-file)  PATH_MAPPING_FILE="$2"; shift 2 ;;
        --path-mapping-file=*)   PATH_MAPPING_FILE="${1#*=}"; shift ;;
        --skip-install)          SKIP_INSTALL=1; shift ;;
        --show-output)           SHOW_OUTPUT=1; shift ;;
        -h|--help)               usage; exit 0 ;;
        *) err "Unknown argument: $1"; usage; exit 1 ;;
    esac
done

if [ -z "$JOB_BUNDLE_DIR" ]; then
    err "JobBundleDir is required. Use --help for usage information."
    exit 1
fi

# ------------------------------------------------------------------
# Resolve Blender executable
# ------------------------------------------------------------------
resolve_blender() {
    if [ -n "$BLENDER_EXE" ]; then echo "$BLENDER_EXE"; return; fi
    if [ -n "${BLENDER_EXECUTABLE:-}" ]; then echo "$BLENDER_EXECUTABLE"; return; fi
    if command -v blender >/dev/null 2>&1; then command -v blender; return; fi

    case "$(uname -s)" in
        Darwin)
            [ -x "/Applications/Blender.app/Contents/MacOS/Blender" ] \
                && echo "/Applications/Blender.app/Contents/MacOS/Blender" && return ;;
        Linux|*)
            for p in /usr/bin/blender /usr/local/bin/blender /snap/bin/blender; do
                [ -x "$p" ] && echo "$p" && return
            done ;;
    esac
    if [ -d "/c/Program Files/Blender Foundation" ]; then
        for dir in $(ls -1d "/c/Program Files/Blender Foundation"/* 2>/dev/null | sort -r); do
            [ -x "$dir/blender.exe" ] && echo "$dir/blender.exe" && return
        done
    fi
    echo ""
}

# ------------------------------------------------------------------
# Resolve Blender's bundled Python from the Blender executable path.
#
# Blender ships Python at:
#   Linux:   <install>/<X.Y>/python/bin/python3.<Y>
#   macOS:   <Blender.app>/Contents/Resources/<X.Y>/python/bin/python3.<Y>
#   Windows: <install>\<X.Y>\python\bin\python.exe
# ------------------------------------------------------------------
resolve_blender_python() {
    local blender_exe="$1"
    if [ -n "$BLENDER_PYTHON" ]; then echo "$BLENDER_PYTHON"; return; fi
    if [ -z "$blender_exe" ] || [ ! -e "$blender_exe" ]; then echo ""; return; fi

    # Determine the search root (the directory that contains the <X.Y> version folder)
    local search_root
    case "$(uname -s)" in
        Darwin)
            # /Applications/Blender.app/Contents/MacOS/Blender -> /Applications/Blender.app/Contents/Resources
            if [[ "$blender_exe" == *".app/Contents/MacOS/"* ]]; then
                local app_root="${blender_exe%/Contents/MacOS/*}"
                search_root="$app_root/Contents/Resources"
            else
                search_root="$(dirname "$blender_exe")"
            fi
            ;;
        *)
            search_root="$(dirname "$blender_exe")"
            ;;
    esac

    if [ ! -d "$search_root" ]; then echo ""; return; fi

    # Find version subdirs (e.g. "4.2", "5.0"), newest first
    local dir python_bin exe
    for dir in $(ls -1d "$search_root"/[0-9]*.[0-9]* 2>/dev/null | sort -rV); do
        python_bin="$dir/python/bin"
        if [ ! -d "$python_bin" ]; then continue; fi

        case "$(uname -s)" in
            CYGWIN*|MINGW*|MSYS*)
                exe="$python_bin/python.exe"
                [ -x "$exe" ] && { echo "$exe"; return; }
                ;;
            *)
                # Prefer python3.<minor>, then python3, then python
                exe="$(ls -1 "$python_bin"/python3.* 2>/dev/null | grep -E '/python3\.[0-9]+$' | sort -V | tail -n 1)"
                if [ -n "$exe" ] && [ -x "$exe" ]; then echo "$exe"; return; fi
                [ -x "$python_bin/python3" ] && { echo "$python_bin/python3"; return; }
                [ -x "$python_bin/python" ] && { echo "$python_bin/python"; return; }
                ;;
        esac
    done
    echo ""
}

BLENDER_EXE="$(resolve_blender)"
if [ -z "$BLENDER_EXE" ]; then
    err "Could not locate Blender. Pass --blender or set BLENDER_EXECUTABLE."
    exit 1
fi
if [ ! -e "$BLENDER_EXE" ]; then
    err "Blender executable not found: $BLENDER_EXE"
    exit 1
fi

PYTHON_PATH="$(resolve_blender_python "$BLENDER_EXE")"
if [ -z "$PYTHON_PATH" ]; then
    err "Could not locate Blender's bundled Python under '$BLENDER_EXE'. Pass --blender-python to override."
    exit 1
fi
if [ ! -x "$PYTHON_PATH" ]; then
    err "Blender Python not executable: $PYTHON_PATH"
    exit 1
fi

# Ensure PyYAML is available in Blender's Python (install into Blender Python if missing)
if ! "$PYTHON_PATH" -c "import yaml" >/dev/null 2>&1; then
    warn "PyYAML is not installed in Blender's Python. Installing..."
    "$PYTHON_PATH" -m pip install pyyaml || { err "Failed to install PyYAML into Blender Python"; exit 1; }
fi

# ------------------------------------------------------------------
# Auto-detect wheel file
# ------------------------------------------------------------------
if [ -z "$WHEEL_PATH" ]; then
    WHEEL_PATH="$(ls -t dist/deadline_cloud_for_blender-*.whl 2>/dev/null | head -n 1 || true)"
    if [ -n "$WHEEL_PATH" ]; then
        gray "Auto-detected wheel file: $WHEEL_PATH"
    else
        err "No wheel files found in dist/. Build one with 'hatch build' or pass --wheel-path."
        exit 1
    fi
fi

echo
ok "=== Blender Adaptor Testing Script ==="
info "Blender:        $BLENDER_EXE"
info "Blender Python: $PYTHON_PATH"
info "Wheel:          $WHEEL_PATH"
info "JobBundle:      $JOB_BUNDLE_DIR"
info "Step:           $STEP"

# ------------------------------------------------------------------
# Prerequisites
# ------------------------------------------------------------------
check_prereqs() {
    section "Checking Prerequisites"
    [ -f "$WHEEL_PATH" ] || { err "Wheel file not found: $WHEEL_PATH"; return 1; }
    ok "Wheel file found"
    [ -d "$JOB_BUNDLE_DIR" ] || { err "Job bundle directory not found: $JOB_BUNDLE_DIR"; return 1; }
    ok "Job bundle directory found"
    return 0
}

# ------------------------------------------------------------------
# Setup environment
# ------------------------------------------------------------------
setup_env() {
    section "Setting Up Environment"

    local repo_path submitter_path src_path sep
    repo_path="$(pwd)"
    submitter_path="$repo_path/src/deadline/blender_submitter"
    src_path="$repo_path/src"
    sep=":"
    case "$(uname -s)" in CYGWIN*|MINGW*|MSYS*) sep=";" ;; esac

    # Put Blender's Python and executable FIRST on PATH (mirrors the 3ds Max pattern)
    local blender_python_dir blender_exe_dir
    blender_python_dir="$(dirname "$PYTHON_PATH")"
    blender_exe_dir="$(dirname "$BLENDER_EXE")"
    gray "Prepending Blender directories to PATH..."
    export PATH="$blender_python_dir:$blender_exe_dir:$PATH"
    ok "  - Blender Python dir: $blender_python_dir"
    ok "  - Blender exe dir:    $blender_exe_dir"

    if [ -z "${PYTHONPATH:-}" ]; then
        export PYTHONPATH="$src_path$sep$submitter_path"
    else
        export PYTHONPATH="$src_path$sep$submitter_path$sep$PYTHONPATH"
    fi
    ok "PYTHONPATH: $PYTHONPATH"

    export BLENDER_EXECUTABLE="$BLENDER_EXE"
    ok "BLENDER_EXECUTABLE: $BLENDER_EXECUTABLE"

    # Verify Blender's Python is the default python3/python on PATH
    section "Verifying Python Priority"
    local which_python expected_norm actual_norm
    which_python="$(command -v python3 || command -v python || true)"
    if [ -n "$which_python" ]; then
        info "Expected Blender Python: $PYTHON_PATH"
        info "Actual default Python:   $which_python"
        expected_norm="$(printf '%s' "$PYTHON_PATH" | tr '[:upper:]' '[:lower:]' | tr '\\' '/')"
        actual_norm="$(printf '%s' "$which_python" | tr '[:upper:]' '[:lower:]' | tr '\\' '/')"
        if [ "$expected_norm" = "$actual_norm" ]; then
            ok "SUCCESS: Blender Python is now the default Python"
        else
            warn "WARNING: 'python3' on PATH does not resolve to Blender's Python."
            warn "         Commands in this script use the Blender Python path explicitly, so this is a soft warning."
        fi
    fi

    warn "Note: Environment changes are temporary for this session only"
    return 0
}

# ------------------------------------------------------------------
# Install adaptor
# ------------------------------------------------------------------
install_adaptor() {
    section "Installing Adaptor"
    info "Running: $PYTHON_PATH -m pip install \"$WHEEL_PATH\" --force-reinstall"
    if "$PYTHON_PATH" -m pip install "$WHEEL_PATH" --force-reinstall; then
        ok "Adaptor installed into Blender's Python environment"
        return 0
    fi
    err "Failed to install adaptor"
    return 1
}

# ------------------------------------------------------------------
# Build init-data and run-data JSON via a Python helper run with Blender Python
# ------------------------------------------------------------------
build_json_via_python() {
    local temp_dir
    temp_dir="$(mktemp -d)"
    local init_file="$temp_dir/blender-init-data.json"
    local run_file="$temp_dir/blender-run-data.json"

    "$PYTHON_PATH" - "$JOB_BUNDLE_DIR" "$STEP" "$init_file" "$run_file" <<'PYEOF'
import json, os, re, sys
import yaml

bundle_dir, step_str, init_out, run_out = sys.argv[1:5]
step_idx = int(step_str)

def die(msg):
    print(f"ERROR: {msg}", file=sys.stderr)
    sys.exit(1)

param_file = os.path.join(bundle_dir, "parameter_values.yaml")
template_file = os.path.join(bundle_dir, "template.yaml")
if not os.path.isfile(param_file):
    die(f"parameter_values.yaml not found: {param_file}")
if not os.path.isfile(template_file):
    die(f"template.yaml not found: {template_file}")

with open(param_file) as f:
    params = yaml.safe_load(f) or {}
with open(template_file) as f:
    template = yaml.safe_load(f) or {}

# Start with defaults from the template's parameterDefinitions
param_values = {}
for pd in (template.get("parameterDefinitions") or []):
    if "default" in pd:
        param_values[pd["name"]] = pd["default"]
# Override with explicit parameter values from parameter_values.yaml
for p in (params.get("parameterValues") or []):
    param_values[p["name"]] = p["value"]

steps = template.get("steps") or []
if step_idx < 0 or step_idx >= len(steps):
    names = [f"  [{i}] {s.get('name')}" for i, s in enumerate(steps)]
    die("Step {} out of range. Available steps:\n{}".format(step_idx, "\n".join(names)))
selected = steps[step_idx]

print(f"Selected step: {selected.get('name')}", file=sys.stderr)

# Camera from task parameter definitions if present
camera = ""
pspace = selected.get("parameterSpace") or {}
for pd in pspace.get("taskParameterDefinitions") or []:
    if pd.get("name") == "Camera":
        rng = pd.get("range") or []
        if rng:
            camera = rng[0]
            break

# Find the initData embedded file
init_template = None
for env in selected.get("stepEnvironments") or []:
    script = env.get("script") or {}
    for ef in script.get("embeddedFiles") or []:
        if ef.get("name") == "initData":
            init_template = ef.get("data")
            break
    if init_template:
        break
if init_template is None:
    die("Could not find initData embedded file in selected step")

# Substitute {{Param.X}} with parameter values; leave unknowns as empty strings
def sub_placeholder(match):
    name = match.group(1)
    if name in param_values:
        return str(param_values[name])
    print(f"Warning: unresolved parameter Param.{name}; substituting empty string", file=sys.stderr)
    return ""
substituted = re.sub(r"\{\{\s*Param\.([A-Za-z0-9_]+)\s*\}\}", sub_placeholder, init_template)

init_data = yaml.safe_load(substituted) or {}

# Drop empty-string / None values so the adaptor schema doesn't reject them
init_data = {k: v for k, v in init_data.items() if v not in ("", None)}

# Pick first frame from the Frames parameter
frames = str(param_values.get("Frames", "1")).strip() or "1"
first_token = frames.split(",")[0].strip()
first_num = first_token.split("-")[0].strip()
try:
    first_frame = int(first_num)
except ValueError:
    first_frame = 1

run_data = {"frame": first_frame}
if camera:
    run_data["camera"] = camera

with open(init_out, "w", encoding="utf-8") as f:
    json.dump(init_data, f)
with open(run_out, "w", encoding="utf-8") as f:
    json.dump(run_data, f)
PYEOF

    local rc=$?
    if [ $rc -ne 0 ]; then return $rc; fi

    INIT_DATA_FILE="$init_file"
    RUN_DATA_FILE="$run_file"
    return 0
}

# ------------------------------------------------------------------
# Build and run test
# ------------------------------------------------------------------
build_and_run() {
    section "Building Test Command"

    if ! build_json_via_python; then
        err "Failed to prepare init/run data"
        return 1
    fi

    info "Init Data JSON ($INIT_DATA_FILE):"
    gray "$(cat "$INIT_DATA_FILE")"
    info "Run Data JSON ($RUN_DATA_FILE):"
    gray "$(cat "$RUN_DATA_FILE")"

    local init_uri="file://${INIT_DATA_FILE//\\/\/}"
    local run_uri="file://${RUN_DATA_FILE//\\/\/}"

    local -a cmd=(
        "$PYTHON_PATH" -m deadline.blender_adaptor.BlenderAdaptor
        run
        --init-data "$init_uri"
        --run-data  "$run_uri"
    )

    if [ -n "$PATH_MAPPING_FILE" ]; then
        if [ ! -f "$PATH_MAPPING_FILE" ]; then
            err "Path mapping file not found: $PATH_MAPPING_FILE"
            return 1
        fi
        local abs_pm
        abs_pm="$("$PYTHON_PATH" -c "import os,sys; print(os.path.abspath(sys.argv[1]))" "$PATH_MAPPING_FILE")"
        local pm_uri="file://${abs_pm//\\/\/}"
        cmd+=(--path-mapping-rules "$pm_uri")
        info "Path Mapping Rules File: $abs_pm"
        gray "$(cat "$PATH_MAPPING_FILE")"
    fi

    info "Test Command: ${cmd[*]}"

    section "Running Test"
    local start_ts end_ts duration exit_code
    start_ts=$(date +%s)

    if [ $SHOW_OUTPUT -eq 1 ]; then
        "${cmd[@]}"
        exit_code=$?
    else
        local tmp_out
        tmp_out="$(mktemp)"
        "${cmd[@]}" >"$tmp_out" 2>&1
        exit_code=$?
        if [ $exit_code -ne 0 ]; then
            err "Output:"
            cat "$tmp_out"
        fi
        rm -f "$tmp_out"
    fi

    end_ts=$(date +%s)
    duration=$((end_ts - start_ts))
    gray "Test completed in ${duration}s (exit code: $exit_code)"

    if [ $exit_code -eq 0 ]; then
        ok "Test completed successfully!"
        return 0
    fi
    err "Test failed"
    return 1
}

# ------------------------------------------------------------------
# Main
# ------------------------------------------------------------------
check_prereqs || exit 1
setup_env || exit 1
if [ $SKIP_INSTALL -eq 0 ]; then
    install_adaptor || exit 1
else
    section "Skipping Installation"
fi
build_and_run
