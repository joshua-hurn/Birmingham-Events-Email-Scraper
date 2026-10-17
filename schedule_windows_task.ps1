<#
.SYNOPSIS
    Registers (or runs) a weekly Windows Scheduled Task to scrape Birmingham, AL events,
    sync your YouTube Music artists/podcasts, generate Proton Calendar (.ics) files,
    and send your review digest email via Proton Mail Bridge.
#>
param(
    [switch]$RegisterTask,
    [string]$DayOfWeek = "Thursday",
    [string]$Time = "08:30AM"
)

$ErrorActionPreference = "Stop"
$ProjectDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$PythonExe = Join-Path $ProjectDir ".venv\Scripts\python.exe"
$MainScript = Join-Path $ProjectDir "main.py"

if (-not (Test-Path $PythonExe)) {
    Write-Error "Virtual environment not found at $PythonExe. Run: python -m venv .venv"
}

if ($RegisterTask) {
    $TaskName = "BirminghamEventCuratorDigest"
    $Action = New-ScheduledTaskAction -Execute $PythonExe -Argument "`"$MainScript`" --new-only" -WorkingDirectory $ProjectDir
    $Trigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek $DayOfWeek -At $Time
    $Settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable

    Register-ScheduledTask -TaskName $TaskName -Action $Action -Trigger $Trigger -Settings $Settings -Description "Scrapes Birmingham, AL music, comedy, food & theater events and sends a Proton Calendar (.ics) digest email." -Force
    Write-Host "Registered Windows Scheduled Task '$TaskName' to run every $DayOfWeek at $Time!"
} else {
    & $PythonExe$MainScript
}