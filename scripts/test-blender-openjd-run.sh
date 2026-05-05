#!/usr/bin/env bash
# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
#
# Blender OpenJD Runner Testing Script (Bash)
# Tests the deadline-cloud-for-blender adaptor via `openjd-cli run` against a job bundle template.
# Uses Blender's bundled Python.
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
STEP=-1
PATH_MAPPING_FILE=""
PATH_MAPPING_PROVIDED=0
SKIP_INSTALL=0
SHOW_OUTPUT=0

usage() {
    cat <<EOF
=== Blender OpenJD Runner Testing Script Help ===

DESCRIPTION:
  Tests the deadline-cloud-for-blender adaptor via 'openjd-cli run' against a job bundle template.
  Uses Blender's bundled Python. Prompts interactively for any parameter not provided.
  Runs on Linux, macOS, and Windows (via Git Bash / WSL).

USAGE:
  ./scripts/test-blender-openjd-run.sh [options]
  ./scripts/test-blender-openjd-run.sh --job-bundle-dir test_bundle

OPTIONS:
  -j, --job-bundle-dir <dir>    Path to the job bundle directory (prompts if empty)
  -w, --wheel-path <path>       Path to the wheel file (auto-detects dist/*.whl if omitted)
  -b, --blender <path>          Path to the Blender executable
  -p, --blender-python <path>   Path to Blender's bundled Python (derived from Blender install if omitted)
  -s, --step <n>                Step index to run (shows list if not provided)
  -m, --path-mapping-file <p>   Path to JSON file with path mapping rules (optional)
      --skip-install            Skip wheel installation
      --show-output             Show detailed output
  -h, --help                    Show this help and exit

PREREQUISITES:
  - Blender installed (ships its own Python; no system Python required)
EOF
}

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
        -m|--path-mapping-file)  PATH_MAPPING_FILE="$2"; PATH_MAPPING_PROVIDED=1; shift 2 ;;
        --path-mapping-file=*)   PATH_MAPPING_FILE="${1#*=}"; PATH_MAPPING_PROVIDED=1; shift ;;
        --skip-install)          SKIP_INSTALL=1; shift ;;
        --show-output)           SHOW_OUTPUT=1; shift ;;
        -h|--help)               usage; exit 0 ;;
        *) err "Unknown argument: $1"; usage; exit 1 ;;
    esac
done

# ------------------------------------------------------------------
# Interactive prompt helper
# ------------------------------------------------------------------
prompt_for_value() {
    local name="$1" desc="$2" default="${3:-}"
    local prompt="$name"
    [ -n "$desc" ] && prompt="$prompt ($desc)"
    [ -n "$default" ] && prompt="$prompt [default: $default]"
    prompt="$prompt: "
    printf "%s%s%s" "$C_CYAN" "$prompt" "$C_RESET" >&2
    local val
    IFS= read -r val
    if [ -z "$val" ] && [ -n "$default" ]; then echo "$default"; else echo "$val"; fi
}

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

resolve_blender_python() {
    local blender_exe="$1"
    if [ -n "$BLENDER_PYTHON" ]; then echo "$BLENDER_PYTHON"; return; fi
    if [ -z "$blender_exe" ] || [ ! -e "$blender_exe" ]; then echo ""; return; fi

    local search_root
    case "$(uname -s)" in
        Darwin)
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
                exe="$(ls -1 "$python_bin"/python3.* 2>/dev/null | grep -E '/python3\.[0-9]+$' | sort -V | tail -n 1)"
                if [ -n "$exe" ] && [ -x "$exe" ]; then echo "$exe"; return; fi
                [ -x "$python_bin/python3" ] && { echo "$python_bin/python3"; return; }
                [ -x "$python_bin/python" ] && { echo "$python_bin/python"; return; }
                ;;
        esac
    done
    echo ""
}

# ------------------------------------------------------------------
# Interactive prompts
# ------------------------------------------------------------------
echo
ok "=== Parameter Configuration ==="

if [ -z "$JOB_BUNDLE_DIR" ]; then
    JOB_BUNDLE_DIR="$(prompt_for_value "JobBundleDir" "Path to job bundle directory")"
    [ -z "$JOB_BUNDLE_DIR" ] && { err "JobBundleDir is required."; exit 1; }
fi
[ -d "$JOB_BUNDLE_DIR" ] || { err "Job bundle directory not found: $JOB_BUNDLE_DIR"; exit 1; }

BLENDER_EXE="$(resolve_blender)"
if [ -z "$BLENDER_EXE" ]; then
    BLENDER_EXE="$(prompt_for_value "BlenderExecutable" "Path to Blender")"
    [ -z "$BLENDER_EXE" ] && { err "Blender executable is required."; exit 1; }
fi
[ -e "$BLENDER_EXE" ] || { err "Blender executable not found: $BLENDER_EXE"; exit 1; }

PYTHON_PATH="$(resolve_blender_python "$BLENDER_EXE")"
if [ -z "$PYTHON_PATH" ]; then
    err "Could not locate Blender's bundled Python under '$BLENDER_EXE'. Pass --blender-python to override."
    exit 1
fi
[ -x "$PYTHON_PATH" ] || { err "Blender Python not executable: $PYTHON_PATH"; exit 1; }

# Ensure PyYAML is available in Blender Python
if ! "$PYTHON_PATH" -c "import yaml" >/dev/null 2>&1; then
    warn "PyYAML is not installed in Blender's Python. Installing..."
    "$PYTHON_PATH" -m pip install pyyaml || { err "Failed to install PyYAML into Blender Python"; exit 1; }
fi

if [ -z "$WHEEL_PATH" ]; then
    default_wheel="$(ls -t dist/deadline_cloud_for_blender-*.whl 2>/dev/null | head -n 1 || true)"
    WHEEL_PATH="$(prompt_for_value "WheelPath" "Path to wheel file" "$default_wheel")"
    if [ -z "$WHEEL_PATH" ]; then
        err "No wheel file specified and none found in dist/. Build with 'hatch build' first."
        exit 1
    fi
fi

if [ "$PATH_MAPPING_PROVIDED" -eq 0 ]; then
    PATH_MAPPING_FILE="$(prompt_for_value "PathMappingFile" "Optional path to JSON path mapping file")"
fi

# ------------------------------------------------------------------
# Parse template to list steps (via Blender Python)
# ------------------------------------------------------------------
TEMPLATE_FILE="$JOB_BUNDLE_DIR/template.yaml"
[ -f "$TEMPLATE_FILE" ] || { err "Template file not found: $TEMPLATE_FILE"; exit 1; }

list_step_names() {
    "$PYTHON_PATH" - "$TEMPLATE_FILE" <<'PYEOF'
import sys, yaml
with open(sys.argv[1]) as f:
    t = yaml.safe_load(f) or {}
for i, s in enumerate(t.get("steps") or []):
    print(f"{i}\t{s.get('name')}")
PYEOF
}

# Portable array population (works on bash 3.2 without mapfile)
STEP_LINES=()
while IFS= read -r line; do
    STEP_LINES+=("$line")
done < <(list_step_names)

if [ ${#STEP_LINES[@]} -eq 0 ]; then
    err "No steps found in template file"
    exit 1
fi

if [ "$STEP" -lt 0 ]; then
    section "Available steps"
    for line in "${STEP_LINES[@]}"; do
        idx="${line%%$'\t'*}"
        name="${line#*$'\t'}"
        info "  [$idx] $name"
    done
    max_idx=$((${#STEP_LINES[@]} - 1))
    while true; do
        printf "%sSelect step number [0-%d]: %s" "$C_CYAN" "$max_idx" "$C_RESET" >&2
        IFS= read -r step_input
        if [[ "$step_input" =~ ^[0-9]+$ ]] && [ "$step_input" -ge 0 ] && [ "$step_input" -le "$max_idx" ]; then
            STEP="$step_input"
            break
        fi
        err "Invalid selection."
    done
fi

echo
ok "=== Blender OpenJD Runner Testing Script ==="
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

    gray "Checking openjd-cli installation..."
    if ! "$PYTHON_PATH" -c "import openjd.cli" >/dev/null 2>&1; then
        warn "openjd-cli not found in Blender Python, installing..."
        "$PYTHON_PATH" -m pip install openjd-cli || { err "Failed to install openjd-cli"; return 1; }
    fi
    ok "openjd-cli is installed in Blender Python"

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

    warn "Note: Environment changes are temporary for this session only"
    return 0
}

# ------------------------------------------------------------------
# Install adaptor
# ------------------------------------------------------------------
install_adaptor() {
    section "Installing Adaptor"
    info "Running: $PYTHON_PATH -m pip install \"$WHEEL_PATH\" --force-reinstall --no-deps"
    if "$PYTHON_PATH" -m pip install "$WHEEL_PATH" --force-reinstall --no-deps; then
        ok "Adaptor installed into Blender's Python environment"
        return 0
    fi
    err "Failed to install adaptor"
    return 1
}

# ------------------------------------------------------------------
# Build job-param / task-param JSON via Blender Python
# ------------------------------------------------------------------
build_params_via_python() {
    local temp_dir
    temp_dir="$(mktemp -d)"
    local job_file="$temp_dir/blender-job-params.json"
    local task_file="$temp_dir/blender-task-params.json"
    local meta_file="$temp_dir/blender-meta.env"

    "$PYTHON_PATH" - "$JOB_BUNDLE_DIR" "$STEP" "$job_file" "$task_file" "$meta_file" <<'PYEOF'
import json, os, sys
import yaml

bundle_dir, step_str, job_out, task_out, meta_out = sys.argv[1:6]
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

steps = template.get("steps") or []
if step_idx < 0 or step_idx >= len(steps):
    die(f"Step {step_idx} out of range (0..{len(steps)-1})")
selected = steps[step_idx]

pv = {p["name"]: p["value"] for p in (params.get("parameterValues") or [])}
frames = str(pv.get("Frames", "1")).strip() or "1"

# Set of parameter names actually declared in the template — used to filter out
# queue-environment extras (Conda*, deadline:*) that the openjd CLI rejects.
declared_params = {pd["name"] for pd in (template.get("parameterDefinitions") or [])}

camera = ""
pspace = selected.get("parameterSpace") or {}
task_defs = pspace.get("taskParameterDefinitions") or []
task_param_types = {pd["name"]: pd.get("type") for pd in task_defs}
for pd in task_defs:
    if pd.get("name") == "Camera":
        rng = pd.get("range") or []
        if rng:
            camera = rng[0]
            break
if not camera:
    camera = pv.get("Camera", "") or ""

def expand(f):
    out = []
    for part in f.split(","):
        part = part.strip()
        if "-" in part:
            try:
                a, b = part.split("-", 1)
                out.extend(range(int(a), int(b) + 1))
            except ValueError:
                pass
        elif part.isdigit():
            out.append(int(part))
    return out or [1]

frame_list = expand(frames)

tasks = []
for fr in frame_list:
    t = {}
    if task_param_types.get("Frame") == "INT":
        t["Frame"] = int(fr)
    else:
        t["Frame"] = str(fr)
    if camera:
        t["Camera"] = camera
    tasks.append(t)

# Only pass parameters declared in the template; drops 'deadline:' and any
# queue-environment-only values (e.g. Conda* from the Conda queue env).
filtered = {
    k: v for k, v in pv.items()
    if k in declared_params and not str(k).startswith("deadline:")
}

with open(job_out, "w", encoding="utf-8") as f:
    json.dump(filtered, f)
with open(task_out, "w", encoding="utf-8") as f:
    json.dump(tasks, f)

step_name = selected.get("name") or ""
with open(meta_out, "w", encoding="utf-8") as f:
    f.write(f"STEP_NAME={step_name}\n")
    f.write(f"CAMERA={camera}\n")
    f.write(f"FRAME_LIST={','.join(str(x) for x in frame_list)}\n")
PYEOF

    local rc=$?
    if [ $rc -ne 0 ]; then return $rc; fi

    STEP_NAME="$(grep '^STEP_NAME=' "$meta_file" | head -n 1 | cut -d= -f2-)"
    CAMERA="$(grep '^CAMERA=' "$meta_file" | head -n 1 | cut -d= -f2-)"
    FRAME_LIST="$(grep '^FRAME_LIST=' "$meta_file" | head -n 1 | cut -d= -f2-)"

    JOB_PARAMS_FILE="$job_file"
    TASK_PARAMS_FILE="$task_file"
    return 0
}

# ------------------------------------------------------------------
# Build and run test
# ------------------------------------------------------------------
build_and_run() {
    section "Building Test Command"

    if ! build_params_via_python; then
        err "Failed to prepare job/task parameters"
        return 1
    fi

    info "Selected step: $STEP_NAME"
    info "Camera: $CAMERA"
    info "Frames: $FRAME_LIST"
    info "Job Parameters JSON ($JOB_PARAMS_FILE):"
    gray "$(cat "$JOB_PARAMS_FILE")"
    info "Task Parameters JSON ($TASK_PARAMS_FILE):"
    gray "$(cat "$TASK_PARAMS_FILE")"

    local job_uri="file://${JOB_PARAMS_FILE//\\/\/}"
    local task_uri="file://${TASK_PARAMS_FILE//\\/\/}"

    local -a cmd=(
        "$PYTHON_PATH" -m openjd run "$TEMPLATE_FILE"
        --step "$STEP_NAME"
        --job-param "$job_uri"
        --tasks "$task_uri"
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
