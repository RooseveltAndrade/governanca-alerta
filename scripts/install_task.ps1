
param(
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

$horarios = @("09:00", "14:00")
$nomes = @("GovernancaAlertaAcessos_09h", "GovernancaAlertaAcessos_14h")

for ($i = 0; $i -lt $horarios.Count; $i++) {
    $args = @(
        "/Create",
        "/TN", $nomes[$i],
        "/TR", $taskCommand,
        "/SC", "DAILY",
        "/ST", $horarios[$i],
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
        throw "Falha ao criar tarefa agendada ($nomes[$i]). ExitCode=$LASTEXITCODE"
    }

    schtasks.exe /Query /TN $nomes[$i] /V /FO LIST
}
