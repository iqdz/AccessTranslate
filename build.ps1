<#
.SYNOPSIS
    Sets up a virtual environment, installs all dependencies, and
    builds Access-Translate into a single portable .exe using
    PyInstaller.

.NOTES
    "Portable" here means no installer is needed - the resulting exe
    can be placed and run from anywhere. Settings always live in
    %AppData%\Access-Translate\ regardless of where the exe sits, so
    moving or replacing the exe never loses configuration.

.USAGE
    .\build.ps1
#>

$ScriptDir = $PSScriptRoot
$TranscriptPath = Join-Path $ScriptDir "build_log.txt"
try { Start-Transcript -Path $TranscriptPath -Append -ErrorAction SilentlyContinue | Out-Null } catch {}

function Write-Step($msg) {
    Write-Host ""
    Write-Host "==== $msg ====" -ForegroundColor Cyan
}

try {
    $VenvDir = Join-Path $ScriptDir "build_env"

    Write-Step "Checking for Python"
    if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
        throw "Python was not found on PATH. Install it from https://www.python.org/downloads/windows/, then re-run this script."
    }
    Write-Host "Found Python: $(python --version)" -ForegroundColor Green

    Write-Step "Setting up virtual environment"
    $VenvPython = Join-Path $VenvDir "Scripts\python.exe"

    $needsRebuild = $false
    if (-not (Test-Path $VenvPython)) {
        $needsRebuild = $true
    } else {
        try {
            & $VenvPython -c "import ensurepip" 2>$null
            if ($LASTEXITCODE -ne 0) { $needsRebuild = $true }
        } catch {
            $needsRebuild = $true
        }
    }

    if ($needsRebuild -and (Test-Path $VenvDir)) {
        Write-Host "Existing virtual environment looks incomplete, rebuilding it." -ForegroundColor Yellow
        Remove-Item -Recurse -Force $VenvDir
    }

    if (-not (Test-Path $VenvDir)) {
        python -m venv $VenvDir
    } else {
        Write-Host "Virtual environment already exists and looks valid, reusing it." -ForegroundColor Yellow
    }

    Write-Step "Ensuring pip is available"
    & $VenvPython -m ensurepip --upgrade
    & $VenvPython -m pip install --upgrade pip

    Write-Step "Installing dependencies"
    & $VenvPython -m pip install -r (Join-Path $ScriptDir "requirements.txt")
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to install dependencies. See the pip output above for the actual error."
    }
    & $VenvPython -m pip install pyinstaller
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to install PyInstaller. See the pip output above for the actual error."
    }

    Write-Step "Building Access-Translate.exe"
    Push-Location $ScriptDir
    & $VenvPython -m PyInstaller --onefile --windowed --name "Access-Translate" --clean run.py
    $buildExit = $LASTEXITCODE
    Pop-Location

    if ($buildExit -ne 0) {
        throw "PyInstaller build failed. See the output above for the actual error."
    }

    $ExePath = Join-Path $ScriptDir "dist\Access-Translate.exe"

    Write-Step "Summary"
    if (Test-Path $ExePath) {
        Write-Host "Build complete: $ExePath" -ForegroundColor Green
        Write-Host ""
        Write-Host "This exe is portable - place it anywhere and run it directly, no installer."
        Write-Host "Settings will be created automatically at:"
        Write-Host "  %AppData%\Access-Translate\config.json"
        Write-Host "on first run, regardless of where you put the exe."
        Write-Host ""
        Write-Host "First run will show a welcome dialog and offer to create a desktop shortcut."
    } else {
        Write-Host "Build did not produce the expected exe. Check the PyInstaller output above and in build_log.txt." -ForegroundColor Yellow
    }

} catch {
    Write-Host ""
    Write-Host "==== ERROR ====" -ForegroundColor Red
    Write-Host $_.Exception.Message -ForegroundColor Red
    Write-Host ""
    Write-Host "Full details were also saved to: $TranscriptPath"
} finally {
    try { Stop-Transcript | Out-Null } catch {}
    Write-Host ""
    Read-Host "Press Enter to close this window"
}
