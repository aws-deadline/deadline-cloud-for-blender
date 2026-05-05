# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
#
# Blender OpenJD Runner Testing Script (cross-platform PowerShell)
# Tests the deadline-cloud-for-blender adaptor via `openjd-cli run` against a job bundle template.
#
# Works on Linux, macOS, and Windows using PowerShell 7+ (pwsh).

param(
    [string]$JobBundleDir,
    [string]$WheelPath,
    [string]$BlenderExecutable = "",
    [string]$BlenderPython = "",
    [int]$Step = -1,
    [string]$PathMappingFile,
    [switch]$SkipInstall,
    [switch]$ShowOutput,
    [switch]$Help
)

# ------------------------------------------------------------------
# Interactive prompt helpers
# ------------------------------------------------------------------
function Prompt-ForValue {
    param(
        [string]$ParameterName,
        [string]$Description,
        [string]$DefaultValue = ""
    )
    $prompt = "$ParameterName"
    if (-not [string]::IsNullOrEmpty($Description)) { $prompt += " ($Description)" }
    if (-not [string]::IsNullOrEmpty($DefaultValue)) { $prompt += " [default: $DefaultValue]" }
    $prompt += ": "
    Write-Host $prompt -ForegroundColor Cyan -NoNewline
    $value = Read-Host
    if ([string]::IsNullOrEmpty($value) -and -not [string]::IsNullOrEmpty($DefaultValue)) {
        return $DefaultValue
    }
    return $value
}

function Prompt-ForStep {
    param([array]$Steps)
    Write-Host "`nAvailable steps:" -ForegroundColor Yellow
    for ($i = 0; $i -lt $Steps.Count; $i++) {
        Write-Host "  [$i] $($Steps[$i].name)" -ForegroundColor Cyan
    }
    while ($true) {
        Write-Host "Select step number [0-$($Steps.Count - 1)]: " -ForegroundColor Cyan -NoNewline
        $inputValue = Read-Host
        if ($inputValue -match '^\d+$') {
            $stepNum = [int]$inputValue
            if ($stepNum -ge 0 -and $stepNum -lt $Steps.Count) { return $stepNum }
        }
        Write-Host "Invalid selection. Enter a number between 0 and $($Steps.Count - 1)" -ForegroundColor Red
    }
}

# ------------------------------------------------------------------
# Help
# ------------------------------------------------------------------
if ($Help) {
    Write-Host "=== Blender OpenJD Runner Testing Script Help ===" -ForegroundColor Green
    Write-Host ""
    Write-Host "DESCRIPTION:" -ForegroundColor Yellow
    Write-Host "  Tests the deadline-cloud-for-blender adaptor via 'openjd-cli run' against a job bundle template."
    Write-Host "  Uses Blender's bundled Python. Parameters without values prompt interactively."
    Write-Host "  Runs on Linux, macOS, and Windows (requires PowerShell 7+)."
    Write-Host ""
    Write-Host "USAGE:" -ForegroundColor Yellow
    Write-Host "  pwsh ./scripts/test-blender-openjd-run.ps1" -ForegroundColor Cyan
    Write-Host "  pwsh ./scripts/test-blender-openjd-run.ps1 -JobBundleDir test_bundle" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "PARAMETERS:" -ForegroundColor Yellow
    Write-Host "  -JobBundleDir       Path to the job bundle directory (prompts if empty)" -ForegroundColor Cyan
    Write-Host "  -WheelPath          Path to the wheel file (auto-detects from dist/ if empty)" -ForegroundColor Cyan
    Write-Host "  -BlenderExecutable  Path to Blender (defaults to BLENDER_EXECUTABLE env or 'blender' on PATH)" -ForegroundColor Cyan
    Write-Host "  -BlenderPython      Path to Blender's bundled Python (derived from Blender install if empty)" -ForegroundColor Cyan
    Write-Host "  -Step               Step index to run (shows list if not provided)" -ForegroundColor Cyan
    Write-Host "  -PathMappingFile    Path to JSON file with path mapping rules (optional)" -ForegroundColor Cyan
    Write-Host "  -SkipInstall        Skip wheel installation" -ForegroundColor Cyan
    Write-Host "  -ShowOutput         Show detailed output" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "PREREQUISITES:" -ForegroundColor Yellow
    Write-Host "  - PowerShell 7+ (pwsh) for cross-platform use"
    Write-Host "  - Blender installed (ships its own Python; no system Python required)"
    Write-Host "  - PowerShell-Yaml module for YAML parsing:"
    Write-Host "    Install-Module powershell-yaml -Scope CurrentUser -Force" -ForegroundColor Cyan
    Write-Host ""
    exit 0
}

# ------------------------------------------------------------------
# Resolve Blender executable
# ------------------------------------------------------------------
function Resolve-BlenderExecutable {
    param([string]$Override)
    if (-not [string]::IsNullOrEmpty($Override)) { return $Override }
    if (-not [string]::IsNullOrEmpty($env:BLENDER_EXECUTABLE)) { return $env:BLENDER_EXECUTABLE }

    $cmd = Get-Command "blender" -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }

    if ($IsWindows) {
        $candidates = Get-ChildItem "C:\Program Files\Blender Foundation" -Directory -ErrorAction SilentlyContinue |
                      Sort-Object Name -Descending
        foreach ($dir in $candidates) {
            $exe = Join-Path $dir.FullName "blender.exe"
            if (Test-Path $exe) { return $exe }
        }
    } elseif ($IsMacOS) {
        $mac = "/Applications/Blender.app/Contents/MacOS/Blender"
        if (Test-Path $mac) { return $mac }
    } else {
        foreach ($p in @("/usr/bin/blender", "/usr/local/bin/blender", "/snap/bin/blender")) {
            if (Test-Path $p) { return $p }
        }
    }
    return ""
}

# ------------------------------------------------------------------
# Resolve Blender's bundled Python from the Blender executable path.
# Blender ships Python under <install>/<X.Y>/python/bin/... (Resources on macOS).
# ------------------------------------------------------------------
function Resolve-BlenderPython {
    param(
        [string]$Override,
        [string]$BlenderExePath
    )
    if (-not [string]::IsNullOrEmpty($Override)) { return $Override }
    if ([string]::IsNullOrEmpty($BlenderExePath) -or -not (Test-Path $BlenderExePath)) {
        return ""
    }

    if ($IsMacOS -and $BlenderExePath -match "\.app/Contents/MacOS/") {
        $appRoot = $BlenderExePath -replace "/Contents/MacOS/.*$", ""
        $searchRoot = Join-Path $appRoot "Contents/Resources"
    } else {
        $searchRoot = Split-Path $BlenderExePath -Parent
    }

    if (-not (Test-Path $searchRoot)) { return "" }

    $versionDirs = Get-ChildItem -Path $searchRoot -Directory -ErrorAction SilentlyContinue |
                   Where-Object { $_.Name -match "^\d+\.\d+$" } |
                   Sort-Object { [version]$_.Name } -Descending
    foreach ($dir in $versionDirs) {
        $pythonBin = Join-Path $dir.FullName "python/bin"
        if (-not (Test-Path $pythonBin)) { continue }

        if ($IsWindows) {
            $exe = Join-Path $pythonBin "python.exe"
            if (Test-Path $exe) { return $exe }
        } else {
            $candidates = Get-ChildItem -Path $pythonBin -File -ErrorAction SilentlyContinue |
                          Where-Object { $_.Name -match "^python3\.\d+$" -or $_.Name -eq "python3" -or $_.Name -eq "python" } |
                          Sort-Object {
                              if ($_.Name -match "^python3\.(\d+)$") { [int]$Matches[1] }
                              elseif ($_.Name -eq "python3") { -1 }
                              else { -2 }
                          } -Descending
            if ($candidates) { return $candidates[0].FullName }
        }
    }
    return ""
}

# ------------------------------------------------------------------
# Interactive prompts for missing parameters
# ------------------------------------------------------------------
Write-Host "`n=== Parameter Configuration ===" -ForegroundColor Green

if ([string]::IsNullOrEmpty($JobBundleDir)) {
    $JobBundleDir = Prompt-ForValue -ParameterName "JobBundleDir" -Description "Path to job bundle directory"
    if ([string]::IsNullOrEmpty($JobBundleDir)) {
        Write-Error "JobBundleDir is required."; exit 1
    }
}
if (-not (Test-Path $JobBundleDir)) {
    Write-Error "Job bundle directory not found: $JobBundleDir"; exit 1
}

$BlenderExe = Resolve-BlenderExecutable -Override $BlenderExecutable
if ([string]::IsNullOrEmpty($BlenderExe)) {
    $BlenderExe = Prompt-ForValue -ParameterName "BlenderExecutable" -Description "Path to Blender"
    if ([string]::IsNullOrEmpty($BlenderExe)) {
        Write-Error "Blender executable is required."; exit 1
    }
}
if (-not (Test-Path $BlenderExe)) {
    Write-Error "Blender executable not found: $BlenderExe"; exit 1
}

$PythonPath = Resolve-BlenderPython -Override $BlenderPython -BlenderExePath $BlenderExe
if ([string]::IsNullOrEmpty($PythonPath)) {
    Write-Error "Could not locate Blender's bundled Python under '$BlenderExe'. Pass -BlenderPython to override."
    exit 1
}
if (-not (Test-Path $PythonPath)) {
    Write-Error "Blender Python not found: $PythonPath"; exit 1
}

# Wheel auto-detect
if ([string]::IsNullOrEmpty($WheelPath)) {
    $distDir = Join-Path (Get-Location) "dist"
    $defaultWheel = ""
    if (Test-Path $distDir) {
        $wheelFiles = Get-ChildItem -Path $distDir -Filter "deadline_cloud_for_blender-*.whl" -ErrorAction SilentlyContinue |
                      Sort-Object LastWriteTime -Descending
        if ($wheelFiles) { $defaultWheel = $wheelFiles[0].FullName }
    }
    $WheelPath = Prompt-ForValue -ParameterName "WheelPath" -Description "Path to wheel file" -DefaultValue $defaultWheel
    if ([string]::IsNullOrEmpty($WheelPath)) {
        Write-Error "No wheel file specified and none found in dist/. Build with 'hatch build' first."
        exit 1
    }
}

if (-not $PSBoundParameters.ContainsKey('PathMappingFile')) {
    $PathMappingFile = Prompt-ForValue -ParameterName "PathMappingFile" -Description "Optional path to JSON path mapping file"
}

# Template + step selection
$templateFile = Join-Path $JobBundleDir "template.yaml"
if (-not (Test-Path $templateFile)) {
    Write-Error "Template file not found: $templateFile"; exit 1
}

try {
    Import-Module powershell-yaml -ErrorAction Stop
} catch {
    Write-Error "powershell-yaml module is required. Install with: Install-Module powershell-yaml -Scope CurrentUser -Force"
    exit 1
}

$templateData = ConvertFrom-Yaml (Get-Content $templateFile -Raw)
if (-not $templateData.steps -or $templateData.steps.Count -eq 0) {
    Write-Error "No steps found in template file"; exit 1
}

if ($Step -lt 0) {
    $Step = Prompt-ForStep -Steps $templateData.steps
}

Write-Host "`n=== Blender OpenJD Runner Testing Script ===" -ForegroundColor Green
Write-Host "Blender:        $BlenderExe" -ForegroundColor Cyan
Write-Host "Blender Python: $PythonPath" -ForegroundColor Cyan
Write-Host "Wheel:          $WheelPath" -ForegroundColor Cyan
Write-Host "JobBundle:      $JobBundleDir" -ForegroundColor Cyan
Write-Host "Step:           $Step" -ForegroundColor Cyan

# ------------------------------------------------------------------
# Prerequisites
# ------------------------------------------------------------------
function Test-Prerequisites {
    Write-Host "`n--- Checking Prerequisites ---" -ForegroundColor Yellow

    if (-not (Test-Path $WheelPath)) {
        Write-Error "Wheel file not found: $WheelPath"; return $false
    }
    Write-Host "Wheel file found" -ForegroundColor Green

    if (-not (Test-Path $JobBundleDir)) {
        Write-Error "Job bundle directory not found: $JobBundleDir"; return $false
    }
    Write-Host "Job bundle directory found" -ForegroundColor Green

    Write-Host "Checking openjd-cli installation..." -ForegroundColor Gray
    & $PythonPath -c "import openjd.cli" 2>$null
    if ($LASTEXITCODE -ne 0) {
        Write-Host "openjd-cli not found in Blender Python, installing..." -ForegroundColor Yellow
        & $PythonPath -m pip install openjd-cli
        if ($LASTEXITCODE -ne 0) {
            Write-Error "Failed to install openjd-cli"; return $false
        }
    }
    Write-Host "openjd-cli is installed in Blender Python" -ForegroundColor Green

    return $true
}

# ------------------------------------------------------------------
# Setup environment
# ------------------------------------------------------------------
function Setup-Environment {
    Write-Host "`n--- Setting Up Environment ---" -ForegroundColor Yellow

    $repoPath = (Get-Location).Path
    $submitterPath = Join-Path $repoPath "src/deadline/blender_submitter"
    $srcPath = Join-Path $repoPath "src"
    $pathSep = [System.IO.Path]::PathSeparator

    # Prioritize Blender's Python and exe on PATH
    $blenderPythonDir = Split-Path $PythonPath -Parent
    $blenderExeDir = Split-Path $BlenderExe -Parent
    Write-Host "Prepending Blender directories to PATH..." -ForegroundColor Gray
    $env:PATH = "$blenderPythonDir$pathSep$blenderExeDir$pathSep$env:PATH"
    Write-Host "  - Blender Python dir: $blenderPythonDir" -ForegroundColor Green
    Write-Host "  - Blender exe dir:    $blenderExeDir" -ForegroundColor Green

    if ([string]::IsNullOrEmpty($env:PYTHONPATH)) {
        $env:PYTHONPATH = "$srcPath$pathSep$submitterPath"
    } else {
        $env:PYTHONPATH = "$srcPath$pathSep$submitterPath$pathSep$env:PYTHONPATH"
    }
    Write-Host "PYTHONPATH: $env:PYTHONPATH" -ForegroundColor Green

    $env:BLENDER_EXECUTABLE = $BlenderExe
    Write-Host "BLENDER_EXECUTABLE: $env:BLENDER_EXECUTABLE" -ForegroundColor Green

    Write-Host "Note: Environment changes are temporary for this session only" -ForegroundColor Yellow
    return $true
}

# ------------------------------------------------------------------
# Install adaptor
# ------------------------------------------------------------------
function Install-Adaptor {
    Write-Host "`n--- Installing Adaptor ---" -ForegroundColor Yellow
    Write-Host "Running: $PythonPath -m pip install `"$WheelPath`" --force-reinstall --no-deps" -ForegroundColor Cyan
    & $PythonPath -m pip install $WheelPath --force-reinstall --no-deps
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Failed to install adaptor (exit code: $LASTEXITCODE)"
        return $false
    }
    Write-Host "Adaptor installed into Blender's Python environment" -ForegroundColor Green
    return $true
}

# ------------------------------------------------------------------
# Expand frame specification
# ------------------------------------------------------------------
function Expand-Frames {
    param([string]$Frames)
    $result = @()
    foreach ($part in $Frames.Split(',')) {
        $p = $part.Trim()
        if ($p -match '^(\d+)-(\d+)$') {
            for ($f = [int]$Matches[1]; $f -le [int]$Matches[2]; $f++) { $result += $f }
        } elseif ($p -match '^\d+$') {
            $result += [int]$p
        } else {
            Write-Host "Warning: Unrecognized frame spec '$p', skipping" -ForegroundColor Yellow
        }
    }
    if ($result.Count -eq 0) { $result = @(1) }
    return $result
}

# ------------------------------------------------------------------
# Build test command
# ------------------------------------------------------------------
function Build-TestCommand {
    param(
        [object]$TemplateData,
        [int]$StepNumber
    )
    Write-Host "`n--- Building Test Command ---" -ForegroundColor Yellow

    $paramFile = Join-Path $JobBundleDir "parameter_values.yaml"
    if (-not (Test-Path $paramFile)) {
        Write-Error "Parameter values file not found: $paramFile"; return $null
    }

    $yamlData = ConvertFrom-Yaml (Get-Content $paramFile -Raw)
    $selectedStep = $TemplateData.steps[$StepNumber]
    $stepName = $selectedStep.name
    Write-Host "Selected step: $stepName" -ForegroundColor Green

    $getValue = {
        param($name)
        $p = $yamlData.parameterValues | Where-Object { $_.name -eq $name }
        if ($p) { return $p.value } else { return "" }
    }

    $frames = & $getValue "Frames"
    if ([string]::IsNullOrEmpty($frames)) { $frames = "1" }
    Write-Host "Frames parameter: $frames" -ForegroundColor Green

    $defaultCamera = ""
    if ($selectedStep.parameterSpace -and $selectedStep.parameterSpace.taskParameterDefinitions) {
        $cameraParam = $selectedStep.parameterSpace.taskParameterDefinitions | Where-Object { $_.name -eq "Camera" }
        if ($cameraParam -and $cameraParam.range -and $cameraParam.range.Count -gt 0) {
            $defaultCamera = $cameraParam.range[0]
        }
    }
    if ([string]::IsNullOrEmpty($defaultCamera)) {
        $defaultCamera = & $getValue "Camera"
    }
    Write-Host "Using camera: $defaultCamera" -ForegroundColor Green

    $taskParamTypes = @{}
    if ($selectedStep.parameterSpace -and $selectedStep.parameterSpace.taskParameterDefinitions) {
        foreach ($pd in $selectedStep.parameterSpace.taskParameterDefinitions) {
            $taskParamTypes[$pd.name] = $pd.type
        }
    }

    $frameList = Expand-Frames -Frames $frames
    Write-Host "Expanded frames: $($frameList -join ', ')" -ForegroundColor Green

    $taskParamsArray = @()
    foreach ($frame in $frameList) {
        $taskParams = [ordered]@{}
        if ($taskParamTypes["Frame"] -eq "INT") {
            $taskParams["Frame"] = [int]$frame
        } else {
            $taskParams["Frame"] = [string]$frame
        }
        if (-not [string]::IsNullOrEmpty($defaultCamera)) {
            $taskParams["Camera"] = $defaultCamera
        }
        $taskParamsArray += $taskParams
    }

    # Build the set of parameter names declared in the template so we can drop
    # queue-environment extras (Conda*, deadline:*) that openjd-cli rejects.
    $declaredParams = @{}
    if ($TemplateData.parameterDefinitions) {
        foreach ($pd in $TemplateData.parameterDefinitions) {
            $declaredParams[$pd.name] = $true
        }
    }

    $filteredJobParams = [ordered]@{}
    foreach ($param in $yamlData.parameterValues) {
        if ($param.name.StartsWith("deadline:")) { continue }
        if (-not $declaredParams.ContainsKey($param.name)) { continue }
        $filteredJobParams[$param.name] = $param.value
    }

    $tempDir = [System.IO.Path]::GetTempPath()
    $jobParamsFile  = Join-Path $tempDir "blender-job-params.json"
    $taskParamsFile = Join-Path $tempDir "blender-task-params.json"
    $utf8NoBom = New-Object System.Text.UTF8Encoding $false

    $jobParamsJson = $filteredJobParams | ConvertTo-Json -Compress -Depth 10
    [System.IO.File]::WriteAllText($jobParamsFile, $jobParamsJson, $utf8NoBom)

    if ($taskParamsArray.Count -eq 1) {
        $taskParamsJson = "[" + ($taskParamsArray[0] | ConvertTo-Json -Compress -Depth 10) + "]"
    } else {
        $taskParamsJson = $taskParamsArray | ConvertTo-Json -Compress -Depth 10
    }
    [System.IO.File]::WriteAllText($taskParamsFile, $taskParamsJson, $utf8NoBom)

    $jobParamsUri  = "file://" + ($jobParamsFile  -replace '\\', '/')
    $taskParamsUri = "file://" + ($taskParamsFile -replace '\\', '/')

    $cmdArgs = @(
        "-m", "openjd", "run", $templateFile,
        "--step", $stepName,
        "--job-param", $jobParamsUri,
        "--tasks", $taskParamsUri
    )

    if (-not [string]::IsNullOrEmpty($PathMappingFile)) {
        if (-not (Test-Path $PathMappingFile)) {
            Write-Error "Path mapping file not found: $PathMappingFile"; return $null
        }
        $absPathMapping = (Resolve-Path $PathMappingFile).Path
        $pmUri = "file://" + ($absPathMapping -replace '\\', '/')
        $cmdArgs += @("--path-mapping-rules", $pmUri)
        Write-Host "`nPath Mapping Rules File: $absPathMapping" -ForegroundColor Yellow
        Write-Host (Get-Content $PathMappingFile -Raw) -ForegroundColor Gray
    }

    Write-Host "`nJob Parameters JSON ($jobParamsFile):" -ForegroundColor Yellow
    Write-Host $jobParamsJson -ForegroundColor Gray
    Write-Host "`nTask Parameters JSON ($taskParamsFile):" -ForegroundColor Yellow
    Write-Host $taskParamsJson -ForegroundColor Gray
    Write-Host "Frames: $($frameList -join ', ')" -ForegroundColor Cyan
    Write-Host "Camera: $defaultCamera" -ForegroundColor Cyan
    Write-Host "`nTest Command:" -ForegroundColor Yellow
    Write-Host "$PythonPath $($cmdArgs -join ' ')" -ForegroundColor White

    $fullCommand = @($PythonPath) + $cmdArgs
    return , $fullCommand
}

# ------------------------------------------------------------------
# Run
# ------------------------------------------------------------------
function Run-Test {
    param([string[]]$TestCommand)

    Write-Host "`n--- Running Test ---" -ForegroundColor Yellow
    $startTime = Get-Date
    Write-Host "Started at: $startTime" -ForegroundColor Gray

    $exe  = $TestCommand[0]
    $rest = $TestCommand[1..($TestCommand.Length - 1)]

    $capturedOutput = $null
    if ($ShowOutput) {
        & $exe @rest
    } else {
        $capturedOutput = & $exe @rest 2>&1
    }
    $exitCode = $LASTEXITCODE

    $duration = (Get-Date) - $startTime
    Write-Host "`nTest completed in $($duration.TotalSeconds) seconds (exit code: $exitCode)" -ForegroundColor Gray

    if ($exitCode -eq 0) {
        Write-Host "Test completed successfully!" -ForegroundColor Green
        return $true
    } else {
        Write-Host "Test failed (exit code: $exitCode)" -ForegroundColor Red
        if (-not $ShowOutput -and $capturedOutput) {
            Write-Host "`nOutput:" -ForegroundColor Gray
            $capturedOutput | ForEach-Object { Write-Host $_ -ForegroundColor Red }
        }
        return $false
    }
}

# ------------------------------------------------------------------
# Main
# ------------------------------------------------------------------
try {
    if (-not (Test-Prerequisites)) { exit 1 }
    if (-not (Setup-Environment))  { exit 1 }

    if (-not $SkipInstall) {
        if (-not (Install-Adaptor)) { exit 1 }
    } else {
        Write-Host "`n--- Skipping Installation ---" -ForegroundColor Yellow
    }

    $testCommand = Build-TestCommand -TemplateData $templateData -StepNumber $Step
    if (-not $testCommand) { exit 1 }

    $success = Run-Test -TestCommand $testCommand
    if ($success) {
        Write-Host "`nTest completed successfully!" -ForegroundColor Green
        exit 0
    } else {
        Write-Host "`nTest failed. Check the output above for details." -ForegroundColor Red
        exit 1
    }
} catch {
    Write-Error "Unexpected error: $($_.Exception.Message)"
    exit 1
}
