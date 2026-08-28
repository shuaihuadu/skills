[CmdletBinding()]
param(
    [Parameter(Mandatory = $true, Position = 0)]
    [string]$Source,

    [Parameter()]
    [string]$Target = (Join-Path $HOME ".copilot\skills"),

    [Parameter()]
    [ValidateSet("Junction", "SymbolicLink")]
    [string]$LinkType = "Junction",

    [Parameter()]
    [switch]$Force
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Get-NormalizedPath {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path
    )

    return [System.IO.Path]::GetFullPath($Path).TrimEnd(
        [System.IO.Path]::DirectorySeparatorChar,
        [System.IO.Path]::AltDirectorySeparatorChar)
}

$sourceItem = Get-Item -LiteralPath $Source -Force
if (-not $sourceItem.PSIsContainer) {
    throw "Source is not a directory: $Source"
}

$sourcePath = Get-NormalizedPath -Path $sourceItem.FullName
$skillFiles = @(
    Get-ChildItem -LiteralPath $sourcePath -Directory -Force |
    Where-Object {
        Test-Path -LiteralPath (Join-Path $_.FullName "SKILL.md") -PathType Leaf
    }
)
if ($skillFiles.Count -eq 0) {
    throw "Source must contain at least one <skill-name>\SKILL.md file."
}

$targetPath = $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($Target)
$targetPath = Get-NormalizedPath -Path $targetPath
if ([string]::Equals($sourcePath, $targetPath, [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "Source and target directories must be different."
}

$targetParent = Split-Path -Parent $targetPath
$null = New-Item -ItemType Directory -Path $targetParent -Force
$existingItem = Get-Item -LiteralPath $targetPath -Force -ErrorAction SilentlyContinue

if ($null -ne $existingItem -and
    ($existingItem.LinkType -eq "Junction" -or $existingItem.LinkType -eq "SymbolicLink")) {
    $existingTarget = [string]($existingItem.Target | Select-Object -First 1)
    if (-not [System.IO.Path]::IsPathRooted($existingTarget)) {
        $existingTarget = Join-Path $targetParent $existingTarget
    }

    $existingTarget = Get-NormalizedPath -Path $existingTarget
    if ([string]::Equals($sourcePath, $existingTarget, [System.StringComparison]::OrdinalIgnoreCase)) {
        Write-Host "Copilot Skills is already linked to: $sourcePath"
        exit 0
    }
}

if ($null -ne $existingItem) {
    if (-not $Force) {
        throw "Target already exists: $targetPath. Run again with -Force to back it up before linking."
    }

    $timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
    $backupPath = "$targetPath.backup.$timestamp"
    Move-Item -LiteralPath $targetPath -Destination $backupPath
    Write-Host "Existing target backed up to: $backupPath"
}

$null = New-Item -ItemType $LinkType -Path $targetPath -Target $sourcePath

Write-Host "Copilot Skills link created:"
Write-Host "  $targetPath -> $sourcePath"
Write-Host "Reload the VS Code window and start a new Copilot Chat session."
