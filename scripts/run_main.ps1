param(
    [string]$ProjectRoot = (Split-Path -Parent $PSScriptRoot),
    [string]$PythonExe = "",
    [string]$EntryPoint = "main.py",
    [string]$LogPrefix = "main"
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


$now = Get-Date
$ano = $now.Year
$mes = $now.ToString("MM")
$dia = $now.ToString("dd-MM-yyyy")
$LogsDir = Join-Path $ProjectRoot "logs"
$LogsDirAno = Join-Path $LogsDir $ano
$LogsDirMes = Join-Path $LogsDirAno $mes
$LogsDirDia = Join-Path $LogsDirMes $dia
New-Item -Path $LogsDirDia -ItemType Directory -Force | Out-Null

$timestamp = $now.ToString("yyyyMMdd_HHmmss")
$safeLogPrefix = if ([string]::IsNullOrWhiteSpace($LogPrefix)) { "main" } else { $LogPrefix }
$logFile = Join-Path $LogsDirDia "${safeLogPrefix}_$timestamp.log"
$alertScript = Join-Path $PSScriptRoot "send_failure_alert.py"

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

    if (Test-Path $alertScript) {
        try {
            & $PythonExe $alertScript `
                --subject "[ALERTA] Falha na execução automática - $EntryPoint" `
                --message $_.Exception.Message `
                --log-file $logFile | Out-Null
        }
        catch {
            "ERRO - Falha ao enviar alerta de execução: $($_.Exception.Message)" | Tee-Object -FilePath $logFile -Append | Out-Null
        }
    }

    exit 1
}
finally {
    Pop-Location
}
