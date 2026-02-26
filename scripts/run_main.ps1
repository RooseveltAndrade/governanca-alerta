param(
    [string]$ProjectRoot = (Split-Path -Parent $PSScriptRoot),
    [string]$PythonExe = "",
    [string]$EntryPoint = "main.py"
)

$ErrorActionPreference = "Continue"

if ($PSVersionTable.PSVersion.Major -ge 7) {
    $PSNativeCommandUseErrorActionPreference = $false
}

if ([string]::IsNullOrWhiteSpace($PythonExe)) {
    $PythonExe = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
}

if (-not (Test-Path $PythonExe)) {
    throw "Python não encontrado em: $PythonExe"
}

$LogsDir = Join-Path $ProjectRoot "logs"
New-Item -Path $LogsDir -ItemType Directory -Force | Out-Null

$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$logFile = Join-Path $LogsDir "main_$timestamp.log"

$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"

Push-Location $ProjectRoot
try {
    & $PythonExe $EntryPoint *>> $logFile
    $exitCode = $LASTEXITCODE
    if ($null -eq $exitCode) {
        $exitCode = 0
    }

    if ($exitCode -ne 0) {
        throw "Execução finalizada com erro. ExitCode=$exitCode"
    }

    "OK - Execução concluída com sucesso." | Tee-Object -FilePath $logFile -Append | Out-Null
    exit 0
}
catch {
    "ERRO - $($_.Exception.Message)" | Tee-Object -FilePath $logFile -Append | Out-Null
    exit 1
}
finally {
    Pop-Location
}
