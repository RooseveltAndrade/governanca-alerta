param(
    [string]$TaskName = "GovernancaAlertaAcessos",
    [string]$StartTime = "07:30",
    [string]$RunAsUser = "",
    [string]$RunAsPassword = "",
    [string]$ProjectRoot = (Split-Path -Parent $PSScriptRoot)
)

$ErrorActionPreference = "Stop"

$runnerScript = Join-Path $PSScriptRoot "run_main.ps1"
if (-not (Test-Path $runnerScript)) {
    throw "Script de execução não encontrado: $runnerScript"
}

$taskCommand = "`"powershell.exe`" -NoProfile -ExecutionPolicy Bypass -File `"$runnerScript`" -ProjectRoot `"$ProjectRoot`""

$args = @(
    "/Create",
    "/TN", $TaskName,
    "/TR", $taskCommand,
    "/SC", "DAILY",
    "/ST", $StartTime,
    "/F"
)

if (-not [string]::IsNullOrWhiteSpace($RunAsUser)) {
    $args += @("/RU", $RunAsUser)

    if (-not [string]::IsNullOrWhiteSpace($RunAsPassword)) {
        $args += @("/RP", $RunAsPassword)
    }
    else {
        $args += @("/RP", "*")
    }
}

& schtasks.exe @args | Out-Null
if ($LASTEXITCODE -ne 0) {
    throw "Falha ao criar tarefa agendada. ExitCode=$LASTEXITCODE"
}

schtasks.exe /Query /TN $TaskName /V /FO LIST
