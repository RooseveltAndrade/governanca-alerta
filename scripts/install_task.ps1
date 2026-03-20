
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

$diasSemana = "MON,TUE,WED,THU,FRI"

$tarefas = @(
    @{
        Nome = "GovernancaAlertaAcessos_09h"
        Horario = "09:00"
        EntryPoint = "main.py"
        LogPrefix = "main"
    },
    @{
        Nome = "GovernancaAlertaAcessos_14h"
        Horario = "14:00"
        EntryPoint = "main.py"
        LogPrefix = "main"
    },
    @{
        Nome = "GovernancaDesligamentos_0930"
        Horario = "09:30"
        EntryPoint = "main_desligamentos.py"
        LogPrefix = "desligamentos"
    },
    @{
        Nome = "GovernancaDesligamentos_1430"
        Horario = "14:30"
        EntryPoint = "main_desligamentos.py"
        LogPrefix = "desligamentos"
    }
)

$tarefas | ForEach-Object {
    $taskCommand = "`"powershell.exe`" -NoProfile -ExecutionPolicy Bypass -File `"$runnerScript`" -ProjectRoot `"$ProjectRoot`" -EntryPoint `"$($_.EntryPoint)`" -LogPrefix `"$($_.LogPrefix)`""
    $args = @(
        "/Create",
        "/TN", $_.Nome,
        "/TR", $taskCommand,
        "/SC", "WEEKLY",
        "/D", $diasSemana,
        "/ST", $_.Horario,
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
        throw "Falha ao criar tarefa agendada ($($_.Nome)). ExitCode=$LASTEXITCODE"
    }

    schtasks.exe /Query /TN $_.Nome /V /FO LIST
}
