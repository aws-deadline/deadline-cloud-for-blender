# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
#
# Blender Adaptor Testing Script (cross-platform PowerShell)
# Tests the deadline-cloud-for-blender adaptor directly without worker agent setup.
#
# Works on Linux, macOS, and Windows using PowerShell 7+ (pwsh).

param(
    [string]$JobBundleDir,
    [string]$WheelPath = "",
    [string]$BlenderExecutable = "",
    [string]$BlenderPython = "",
    [int]$Step = 0,
    [string]$PathMappingFile = "",
    [switch]$SkipInstall,
    [switch]$ShowOutput,
    [switch]$Help
)

# ------------------------------------------------------------------
# Help
# ------------------------------------------------------------------
if ($Help) {
    Write-Host "=== Blender Adaptor Testing Script Help ===" -ForegroundColor Green
    Write-Host ""
    Write-Host "DESCRIPTION:" -ForegroundColor Yellow
    Write-Host "  Tests the deadline-cloud-for-blender adaptor directly without worker agent setup."
    Write-Host "  Uses Blender's bundled Python (Blender ships Python at <install>/<X.Y>/python/bin/...)."
    Write-Host "  Runs on Linux, macOS, and Windows (requires PowerShell 7+)."
    Write-Host ""
    Write-Host "USAGE:" -ForegroundColor Yellow
    Write-Host "  Run this script from the repository root directory:" -ForegroundColor Yellow
    Write-Host "  pwsh ./scripts/test-blender-adapter-run.ps1 -JobBundleDir <path>" -ForegroundColor Cyan
    Write-Host "  Example: pwsh ./scripts/test-blender-adapter-run.ps1 -JobBundleDir test_bundle" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "PARAMETERS:" -ForegroundColor Yellow
    Write-Host "  -JobBundleDir       (Required) Path to the job bundle directory" -ForegroundColor Cyan
    Write-Host "  -WheelPath          Path to the wheel file (auto-detected from dist/ if empty)" -ForegroundColor Cyan
    Write-Host "  -BlenderExecutable  Path to Blender (defaults to BLENDER_EXECUTABLE env or 'blender' on PATH)" -ForegroundColor Cyan
    Write-Host "  -BlenderPython      Path to Blender's bundled Python (derived from Blender install if empty)" -ForegroundColor Cyan
    Write-Host "  -Step               Step index to run (default: 0)" -ForegroundColor Cyan
    Write-Host "  -PathMappingFile    Path to JSON file with path mapping rules (optional)" -ForegroundColor Cyan
    Write-Host "  -SkipInstall        Skip wheel installation (optional)" -ForegroundColor Cyan
    Write-Host "  -ShowOutput         Show detailed output (optional)" -ForegroundColor Cyan
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
# Validate required parameters
# ------------------------------------------------------------------
if ([string]::IsNullOrEmpty($JobBundleDir)) {
    Write-Error "JobBundleDir parameter is required. Use -Help for usage information."
    exit 1
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
#
# Blender bundles Python at:
#   Linux:   <install>/<X.Y>/python/bin/python3.<Y>
#   macOS:   <Blender.app>/Contents/Resources/<X.Y>/python/bin/python3.<Y>
#   Windows: <install>\<X.Y>\python\bin\python.exe
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

    # Base directory that contains the Blender version folder (e.g., "5.0")
    if ($IsMacOS -and $BlenderExePath -match "\.app/Contents/MacOS/") {
        $appRoot = $BlenderExePath -replace "/Contents/MacOS/.*$", ""
        $searchRoot = Join-Path $appRoot "Contents/Resources"
    } else {
        $searchRoot = Split-Path $BlenderExePath -Parent
    }

    if (-not (Test-Path $searchRoot)) { return "" }

    # Find the newest version subdirectory that contains python/bin
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
            # Look for python3.<minor> (e.g., python3.11), then python3, then python
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

$BlenderExe = Resolve-BlenderExecutable -Override $BlenderExecutable
if ([string]::IsNullOrEmpty($BlenderExe)) {
    Write-Error "Could not locate Blender. Pass -BlenderExecutable or set BLENDER_EXECUTABLE."
    exit 1
}
if (-not (Test-Path $BlenderExe)) {
    Write-Error "Blender executable not found: $BlenderExe"
    exit 1
}

$PythonPath = Resolve-BlenderPython -Override $BlenderPython -BlenderExePath $BlenderExe
if ([string]::IsNullOrEmpty($PythonPath)) {
    Write-Error "Could not locate Blender's bundled Python under '$BlenderExe'. Pass -BlenderPython to override."
    exit 1
}
if (-not (Test-Path $PythonPath)) {
    Write-Error "Blender Python not found: $PythonPath"
    exit 1
}

# ------------------------------------------------------------------
# Auto-detect wheel file
# ------------------------------------------------------------------
if ([string]::IsNullOrEmpty($WheelPath)) {
    $distDir = Join-Path (Get-Location) "dist"
    if (Test-Path $distDir) {
        $wheelFiles = Get-ChildItem -Path $distDir -Filter "deadline_cloud_for_blender-*.whl" -ErrorAction SilentlyContinue |
                      Sort-Object LastWriteTime -Descending
        if ($wheelFiles) {
            $WheelPath = $wheelFiles[0].FullName
            Write-Host "Auto-detected wheel file: $WheelPath" -ForegroundColor Gray
        }
    }
    if ([string]::IsNullOrEmpty($WheelPath)) {
        Write-Error "No wheel files found in dist/. Build one with 'hatch build' or pass -WheelPath."
        exit 1
    }
}

Write-Host "=== Blender Adaptor Testing Script ===" -ForegroundColor Green
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

    # Put Blender's Python and Blender's executable FIRST on PATH (like 3ds Max script)
    $blenderPythonDir = Split-Path $PythonPath -Parent
    $blenderExeDir = Split-Path $BlenderExe -Parent
    Write-Host "Prepending Blender directories to PATH..." -ForegroundColor Gray
    $env:PATH = "$blenderPythonDir$pathSep$blenderExeDir$pathSep$env:PATH"
    Write-Host "  - Blender Python dir: $blenderPythonDir" -ForegroundColor Green
    Write-Host "  - Blender exe dir:    $blenderExeDir" -ForegroundColor Green

    # PYTHONPATH for in-repo submitter code
    if ([string]::IsNullOrEmpty($env:PYTHONPATH)) {
        $env:PYTHONPATH = "$srcPath$pathSep$submitterPath"
    } else {
        $env:PYTHONPATH = "$srcPath$pathSep$submitterPath$pathSep$env:PYTHONPATH"
    }
    Write-Host "PYTHONPATH: $env:PYTHONPATH" -ForegroundColor Green

    $env:BLENDER_EXECUTABLE = $BlenderExe
    Write-Host "BLENDER_EXECUTABLE: $env:BLENDER_EXECUTABLE" -ForegroundColor Green

    # Verify Blender's Python is the default
    Write-Host "`n--- Verifying Python Priority ---" -ForegroundColor Yellow
    $pythonName = if ($IsWindows) { "python" } else { "python3" }
    $resolved = Get-Command $pythonName -ErrorAction SilentlyContinue
    if ($resolved) {
        $actual = $resolved.Source
        $expectedNorm = $PythonPath.ToLower().Replace('\', '/')
        $actualNorm = $actual.ToLower().Replace('\', '/')
        Write-Host "Expected Blender Python: $PythonPath" -ForegroundColor Cyan
        Write-Host "Actual default Python:   $actual" -ForegroundColor Cyan
        if ($actualNorm -eq $expectedNorm) {
            Write-Host "SUCCESS: Blender Python is now the default Python" -ForegroundColor Green
        } else {
            Write-Host "WARNING: '$pythonName' on PATH does not resolve to Blender's Python" -ForegroundColor Yellow
            Write-Host "Commands in this script explicitly use the Blender Python path, so this is a soft warning." -ForegroundColor Yellow
        }
    }

    Write-Host "Note: Environment changes are temporary for this session only" -ForegroundColor Yellow
    return $true
}

# ------------------------------------------------------------------
# Install adaptor
# ------------------------------------------------------------------
function Install-Adaptor {
    Write-Host "`n--- Installing Adaptor ---" -ForegroundColor Yellow
    Write-Host "Running: $PythonPath -m pip install `"$WheelPath`" --force-reinstall" -ForegroundColor Cyan

    & $PythonPath -m pip install $WheelPath --force-reinstall
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Failed to install adaptor (exit code: $LASTEXITCODE)"
        return $false
    }
    Write-Host "Adaptor installed successfully into Blender's Python environment" -ForegroundColor Green
    return $true
}

# ------------------------------------------------------------------
# Build test command from job bundle
# ------------------------------------------------------------------
function Build-TestCommand {
    Write-Host "`n--- Building Test Command ---" -ForegroundColor Yellow

    try {
        Import-Module powershell-yaml -ErrorAction Stop
    } catch {
        Write-Error "powershell-yaml module is required. Install with: Install-Module powershell-yaml -Scope CurrentUser -Force"
        return $null
    }

    $paramFile = Join-Path $JobBundleDir "parameter_values.yaml"
    if (-not (Test-Path $paramFile)) {
        Write-Error "Parameter values file not found: $paramFile"; return $null
    }

    $templateFile = Join-Path $JobBundleDir "template.yaml"
    if (-not (Test-Path $templateFile)) {
        Write-Error "Template file not found: $templateFile"; return $null
    }

    $yamlData = ConvertFrom-Yaml (Get-Content $paramFile -Raw)
    $templateData = ConvertFrom-Yaml (Get-Content $templateFile -Raw)

    if (-not $templateData.steps -or $templateData.steps.Count -eq 0) {
        Write-Error "No steps found in template file"; return $null
    }
    if ($Step -lt 0 -or $Step -ge $templateData.steps.Count) {
        Write-Error "Step number $Step is out of range. Available: 0..$($templateData.steps.Count - 1)"
        for ($i = 0; $i -lt $templateData.steps.Count; $i++) {
            Write-Host "  Step $i`: $($templateData.steps[$i].name)" -ForegroundColor Gray
        }
        return $null
    }

    $selectedStep = $templateData.steps[$Step]
    Write-Host "Selected step: $($selectedStep.name)" -ForegroundColor Green

    # Merge defaults from template parameterDefinitions with parameter_values.yaml
    $mergedParams = [ordered]@{}
    if ($templateData.parameterDefinitions) {
        foreach ($pd in $templateData.parameterDefinitions) {
            $hasDefault = $false
            if ($pd -is [System.Collections.IDictionary]) {
                $hasDefault = $pd.Contains('default')
            } elseif ($pd.PSObject.Properties.Name -contains 'default') {
                $hasDefault = $true
            }
            if ($hasDefault) {
                $mergedParams[$pd.name] = $pd.default
            }
        }
    }
    foreach ($p in $yamlData.parameterValues) {
        $mergedParams[$p.name] = $p.value
    }

    $getValue = {
        param($name)
        if ($mergedParams.Contains($name)) { return $mergedParams[$name] } else { return "" }
    }

    $frames = & $getValue "Frames"
    if ([string]::IsNullOrEmpty($frames)) { $frames = "1" }

    # Camera - from task parameter definitions if present
    $defaultCamera = ""
    if ($selectedStep.parameterSpace -and $selectedStep.parameterSpace.taskParameterDefinitions) {
        $cameraParam = $selectedStep.parameterSpace.taskParameterDefinitions | Where-Object { $_.name -eq "Camera" }
        if ($cameraParam -and $cameraParam.range -and $cameraParam.range.Count -gt 0) {
            $defaultCamera = $cameraParam.range[0]
            Write-Host "Found camera parameter: $defaultCamera" -ForegroundColor Green
        }
    }

    # Find initData embedded file
    $initDataSection = $null
    if ($selectedStep.stepEnvironments) {
        foreach ($stepEnv in $selectedStep.stepEnvironments) {
            if ($stepEnv.script -and $stepEnv.script.embeddedFiles) {
                $match = $stepEnv.script.embeddedFiles | Where-Object { $_.name -eq "initData" }
                if ($match) { $initDataSection = $match; break }
            }
        }
    }
    if (-not $initDataSection) {
        Write-Error "Could not find initData embedded file in step '$($selectedStep.name)'"
        return $null
    }

    # Substitute parameter placeholders using merged values
    $initDataTemplate = $initDataSection.data
    $placeholderRegex = [regex]'\{\{\s*Param\.([A-Za-z0-9_]+)\s*\}\}'
    $initDataTemplate = $placeholderRegex.Replace($initDataTemplate, {
        param($m)
        $name = $m.Groups[1].Value
        if ($mergedParams.Contains($name)) {
            return [string]$mergedParams[$name]
        }
        Write-Host "Warning: unresolved parameter Param.$name; substituting empty string" -ForegroundColor Yellow
        return ""
    })

    Write-Host "Substituted initData template:" -ForegroundColor Gray
    Write-Host $initDataTemplate -ForegroundColor Gray

    $initDataYaml = ConvertFrom-Yaml $initDataTemplate

    # Drop empty-string / null values so the adaptor schema doesn't reject them
    $cleaned = [ordered]@{}
    foreach ($key in $initDataYaml.Keys) {
        $v = $initDataYaml[$key]
        if ($null -ne $v -and -not ($v -is [string] -and [string]::IsNullOrEmpty($v))) {
            $cleaned[$key] = $v
        }
    }
    $initData = $cleaned | ConvertTo-Json -Compress -Depth 10

    # First frame only for one-shot adapter run
    $firstFrame = 1
    $firstToken = $frames.Split(',')[0].Trim()
    $firstRangeStart = $firstToken.Split('-')[0]
    if ($firstRangeStart -match '^\d+$') { $firstFrame = [int]$firstRangeStart }

    $runDataObj = [ordered]@{ frame = $firstFrame }
    if (-not [string]::IsNullOrEmpty($defaultCamera)) {
        $runDataObj["camera"] = $defaultCamera
    }
    $runData = $runDataObj | ConvertTo-Json -Compress

    # Write JSON to temp files (UTF-8, no BOM)
    $tempDir = [System.IO.Path]::GetTempPath()
    $initDataFile = Join-Path $tempDir "blender-init-data.json"
    $runDataFile  = Join-Path $tempDir "blender-run-data.json"
    $utf8NoBom = New-Object System.Text.UTF8Encoding $false
    [System.IO.File]::WriteAllText($initDataFile, $initData, $utf8NoBom)
    [System.IO.File]::WriteAllText($runDataFile,  $runData,  $utf8NoBom)

    Write-Host "`nInit Data JSON ($initDataFile):" -ForegroundColor Yellow
    Write-Host $initData -ForegroundColor Gray
    Write-Host "`nRun Data JSON ($runDataFile):" -ForegroundColor Yellow
    Write-Host $runData -ForegroundColor Gray

    # file:// URIs use forward slashes on all platforms
    $initDataUri = "file://" + ($initDataFile -replace '\\', '/')
    $runDataUri  = "file://" + ($runDataFile  -replace '\\', '/')

    $cmdArgs = @(
        "-m", "deadline.blender_adaptor.BlenderAdaptor",
        "run",
        "--init-data", $initDataUri,
        "--run-data",  $runDataUri
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

    $testCommand = Build-TestCommand
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
