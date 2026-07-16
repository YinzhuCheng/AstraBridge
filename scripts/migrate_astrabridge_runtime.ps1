[CmdletBinding()]
param(
    [string]$Destination = 'D:\AstraBridgeRuntime',
    [switch]$Apply,
    [switch]$Finalize
)

$ErrorActionPreference = 'Stop'

if ($Finalize -and -not $Apply) {
    throw '-Finalize requires -Apply.'
}

$runtimeSource = Join-Path $env:APPDATA 'AstraBridge\runtime'
$codexHomeSource = Join-Path $env:LOCALAPPDATA 'AstraBridge\cx'
$codexHomeDestination = Join-Path $Destination 'embedded_codex_home'

function Get-AstraBridgeSidecars {
    $all = @(Get-CimInstance Win32_Process | Where-Object {
        $name = [string]$_.Name
        $commandLine = [string]$_.CommandLine
        $isSidecarProcess = $name -match '^(python|pythonw)(\.exe)?$|^astrabridge-sidecar(\.exe)?$|^sidecar_server(\.exe)?$'
        $hasSidecarMarker = $commandLine -match 'astrabridge[-_]sidecar|sidecar_server\.py'
        $isSidecarProcess -and $hasSidecarMarker -and $commandLine -match '(?:^|\s)--serve(?:\s|$)'
    })
    $matchingPids = @{}
    foreach ($item in $all) {
        $matchingPids[[int]$item.ProcessId] = $true
    }
    return @($all | Where-Object { -not $matchingPids.ContainsKey([int]$_.ParentProcessId) })
}

function Stop-AstraBridgeSidecars {
    $roots = @(Get-AstraBridgeSidecars)
    foreach ($root in $roots) {
        $killer = Start-Process `
            -FilePath "$env:WINDIR\System32\taskkill.exe" `
            -ArgumentList @('/PID', [string]$root.ProcessId, '/T', '/F') `
            -WindowStyle Hidden `
            -Wait `
            -PassThru
        if ($killer.ExitCode -ne 0 -and (Get-Process -Id $root.ProcessId -ErrorAction SilentlyContinue)) {
            throw "Could not stop AstraBridge sidecar root $($root.ProcessId)."
        }
    }
    Start-Sleep -Milliseconds 750
    $remaining = @(Get-AstraBridgeSidecars)
    if ($remaining.Count -ne 0) {
        throw "AstraBridge sidecars are still running: $($remaining.Count)."
    }
    return $roots.Count
}

function Copy-Tree {
    param(
        [Parameter(Mandatory)] [string]$Source,
        [Parameter(Mandatory)] [string]$Target
    )
    if (-not (Test-Path -LiteralPath $Source)) {
        return 0
    }
    New-Item -ItemType Directory -Path $Target -Force | Out-Null
    $copy = Start-Process `
        -FilePath "$env:WINDIR\System32\robocopy.exe" `
        -ArgumentList @($Source, $Target, '/E', '/COPY:DAT', '/DCOPY:DAT', '/R:2', '/W:1', '/XJ', '/NP', '/NFL', '/NDL') `
        -WindowStyle Hidden `
        -Wait `
        -PassThru
    if ($copy.ExitCode -gt 7) {
        throw "Robocopy failed with code $($copy.ExitCode): $Source -> $Target"
    }
    return $copy.ExitCode
}

function Compare-Tree {
    param(
        [Parameter(Mandatory)] [string]$Source,
        [Parameter(Mandatory)] [string]$Target
    )
    if (-not (Test-Path -LiteralPath $Source)) {
        return [pscustomobject]@{
            Source = $Source
            Target = $Target
            Files = 0
            Bytes = 0
            Missing = 0
            SizeMismatch = 0
        }
    }
    $sourceRoot = (Get-Item -LiteralPath $Source).FullName.TrimEnd('\')
    $files = @(Get-ChildItem -LiteralPath $Source -File -Recurse -Force)
    $missing = 0
    $sizeMismatch = 0
    $bytes = [long]0
    foreach ($file in $files) {
        $bytes += [long]$file.Length
        $relative = $file.FullName.Substring($sourceRoot.Length).TrimStart('\')
        $targetFile = Join-Path $Target $relative
        if (-not (Test-Path -LiteralPath $targetFile -PathType Leaf)) {
            $missing += 1
        }
        elseif ([long](Get-Item -LiteralPath $targetFile -Force).Length -ne [long]$file.Length) {
            $sizeMismatch += 1
        }
    }
    return [pscustomobject]@{
        Source = $Source
        Target = $Target
        Files = $files.Count
        Bytes = $bytes
        Missing = $missing
        SizeMismatch = $sizeMismatch
    }
}

function Set-CompatibilityJunction {
    param(
        [Parameter(Mandatory)] [string]$Path,
        [Parameter(Mandatory)] [string]$Target
    )
    if (Test-Path -LiteralPath $Path) {
        Remove-Item -LiteralPath $Path -Recurse -Force
    }
    New-Item -ItemType Junction -Path $Path -Target $Target | Out-Null
    $junction = Get-Item -LiteralPath $Path -Force
    if (-not ($junction.Attributes -band [IO.FileAttributes]::ReparsePoint)) {
        throw "Compatibility junction verification failed: $Path"
    }
    return $junction
}

function Test-JunctionTarget {
    param(
        [Parameter(Mandatory)] [string]$Path,
        [Parameter(Mandatory)] [string]$Target
    )
    if (-not (Test-Path -LiteralPath $Path)) {
        return $false
    }
    $item = Get-Item -LiteralPath $Path -Force
    if (-not ($item.Attributes -band [IO.FileAttributes]::ReparsePoint)) {
        return $false
    }
    $expected = [IO.Path]::GetFullPath($Target).TrimEnd('\')
    return @($item.Target | Where-Object {
        [IO.Path]::GetFullPath([string]$_).TrimEnd('\') -ieq $expected
    }).Count -gt 0
}

$runtimeAlreadyMigrated = Test-JunctionTarget -Path $runtimeSource -Target $Destination
$codexHomeAlreadyMigrated = Test-JunctionTarget -Path $codexHomeSource -Target $codexHomeDestination
$unexpectedReparsePoints = @(
    @($runtimeSource, $codexHomeSource) | Where-Object {
        if (-not (Test-Path -LiteralPath $_)) { return $false }
        $item = Get-Item -LiteralPath $_ -Force
        return [bool]($item.Attributes -band [IO.FileAttributes]::ReparsePoint)
    }
).Count -gt 0 -and -not ($runtimeAlreadyMigrated -and $codexHomeAlreadyMigrated)
if ($unexpectedReparsePoints) {
    throw 'A legacy source is already a reparse point with an unexpected or incomplete target. No changes were made.'
}

$preview = [pscustomobject]@{
    RuntimeSource = $runtimeSource
    CodexHomeSource = $codexHomeSource
    Destination = $Destination
    SidecarRoots = @(Get-AstraBridgeSidecars).Count
    AlreadyMigrated = $runtimeAlreadyMigrated -and $codexHomeAlreadyMigrated
    Apply = [bool]$Apply
    Finalize = [bool]$Finalize
}

if (-not $Apply) {
    $preview | ConvertTo-Json -Depth 4
    exit 0
}

if ($runtimeAlreadyMigrated -and $codexHomeAlreadyMigrated) {
    $destinationFiles = @(Get-ChildItem -LiteralPath $Destination -File -Recurse -Force)
    [pscustomobject]@{
        Ok = $true
        AlreadyMigrated = $true
        RemainingSidecars = @(Get-AstraBridgeSidecars).Count
        Destination = [pscustomobject]@{
            Path = $Destination
            Files = $destinationFiles.Count
            Bytes = [long](($destinationFiles | Measure-Object Length -Sum).Sum)
        }
    } | ConvertTo-Json -Depth 4
    exit 0
}

$cFreeBefore = [long](Get-PSDrive C).Free
$stoppedSidecars = Stop-AstraBridgeSidecars
New-Item -ItemType Directory -Path $Destination -Force | Out-Null
$runtimeCopyCode = Copy-Tree -Source $runtimeSource -Target $Destination
$codexHomeCopyCode = Copy-Tree -Source $codexHomeSource -Target $codexHomeDestination
$runtimeVerification = Compare-Tree -Source $runtimeSource -Target $Destination
$codexHomeVerification = Compare-Tree -Source $codexHomeSource -Target $codexHomeDestination
$verified = (
    $runtimeVerification.Missing -eq 0 -and
    $runtimeVerification.SizeMismatch -eq 0 -and
    $codexHomeVerification.Missing -eq 0 -and
    $codexHomeVerification.SizeMismatch -eq 0
)
if (-not $verified) {
    throw 'Copy verification failed. C-drive sources were preserved.'
}

$runtimeJunction = $null
$codexHomeJunction = $null
if ($Finalize) {
    $runtimeJunction = Set-CompatibilityJunction -Path $runtimeSource -Target $Destination
    $codexHomeJunction = Set-CompatibilityJunction -Path $codexHomeSource -Target $codexHomeDestination
}

$destinationFiles = @(Get-ChildItem -LiteralPath $Destination -File -Recurse -Force)
[pscustomobject]@{
    Ok = $true
    StoppedSidecarRoots = $stoppedSidecars
    RemainingSidecars = @(Get-AstraBridgeSidecars).Count
    RuntimeCopyCode = $runtimeCopyCode
    CodexHomeCopyCode = $codexHomeCopyCode
    RuntimeVerification = $runtimeVerification
    CodexHomeVerification = $codexHomeVerification
    Destination = [pscustomobject]@{
        Path = $Destination
        Files = $destinationFiles.Count
        Bytes = [long](($destinationFiles | Measure-Object Length -Sum).Sum)
    }
    RuntimeJunction = if ($runtimeJunction) {
        [pscustomobject]@{
            Path = $runtimeJunction.FullName
            Target = @($runtimeJunction.Target)
            Attributes = [string]$runtimeJunction.Attributes
        }
    } else { $null }
    CodexHomeJunction = if ($codexHomeJunction) {
        [pscustomobject]@{
            Path = $codexHomeJunction.FullName
            Target = @($codexHomeJunction.Target)
            Attributes = [string]$codexHomeJunction.Attributes
        }
    } else { $null }
    CFreeBefore = $cFreeBefore
    CFreeAfter = [long](Get-PSDrive C).Free
} | ConvertTo-Json -Depth 6
