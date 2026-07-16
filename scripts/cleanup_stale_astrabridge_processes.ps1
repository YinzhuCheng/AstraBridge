param(
    [switch]$Quiet
)

$ErrorActionPreference = "Stop"

function Write-Note {
    param([string]$Message)
    if (-not $Quiet) {
        Write-Host $Message
    }
}

$all = Get-CimInstance Win32_Process
$byPid = $all | Group-Object -Property ProcessId -AsHashTable -AsString
$targets = $all | Where-Object {
    $cmd = [string]($_.CommandLine)
    if (-not $cmd) { return $false }
    $cmd -match 'AstraBridge|astrabridge|astrabridge-sidecar|vite'
}

$stopped = New-Object System.Collections.Generic.List[string]

foreach ($proc in $targets) {
    $name = [string]$proc.Name
    $commandLine = [string]$proc.CommandLine
    $parentAlive = $byPid.ContainsKey([string]$proc.ParentProcessId)
    $children = @($targets | Where-Object { $_.ParentProcessId -eq $proc.ProcessId })

    $isFrontendWrapper = $name -ieq "cmd.exe" -and $commandLine -match 'vite|npm run dev'
    $isSidecarWrapper = $name -ieq "cmd.exe" -and $commandLine -match 'astrabridge_sidecar\.server'
    $isSidecarBootstrap = $name -ieq "python.exe" -and $commandLine -match 'astrabridge_sidecar\.server'

    $shouldStop = $false
    $reason = ""

    if (($isFrontendWrapper -or $isSidecarWrapper) -and -not $parentAlive -and $children.Count -eq 0) {
        $shouldStop = $true
        $reason = "orphaned wrapper with dead parent and no child"
    } elseif ($isSidecarBootstrap -and -not $parentAlive -and $children.Count -eq 0) {
        $shouldStop = $true
        $reason = "orphaned sidecar bootstrap with dead parent and no child"
    }

    if (-not $shouldStop) {
        continue
    }

    $running = Get-Process -Id $proc.ProcessId -ErrorAction SilentlyContinue
    if (-not $running) {
        continue
    }
    Stop-Process -Id $proc.ProcessId -Force
    $stopped.Add("$($proc.ProcessId): $reason")
}

if ($stopped.Count -eq 0) {
    Write-Note "No clearly stale AstraBridge wrapper processes found."
} else {
    foreach ($entry in $stopped) {
        Write-Note "Stopped $entry"
    }
}
