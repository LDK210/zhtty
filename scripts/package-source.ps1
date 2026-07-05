param(
    [string]$OutputPath = "hirepilot-source.zip"
)

$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$ResolvedOutputPath = if ([System.IO.Path]::IsPathRooted($OutputPath)) {
    $OutputPath
} else {
    Join-Path $Root $OutputPath
}

$PackageName = [System.IO.Path]::GetFileNameWithoutExtension($ResolvedOutputPath)
$StagingRoot = Join-Path ([System.IO.Path]::GetTempPath()) ("hirepilot-package-" + [System.Guid]::NewGuid().ToString("N"))
$StagingDir = Join-Path $StagingRoot $PackageName

$ExcludedDirectories = @(
    ".git",
    ".codex",
    ".agents",
    ".venv",
    "node_modules",
    "dist",
    "build",
    ".vite",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    "uploads",
    "coverage",
    ".browser-cdp"
)

$ExcludedFilePatterns = @(
    "*.db",
    "*.sqlite",
    "*.log",
    "*.tmp",
    "*.pyc",
    "*.pyo",
    "hirepilot-source.zip"
)

function Test-ExcludedDirectory {
    param([Parameter(Mandatory = $true)][System.IO.DirectoryInfo]$Directory)

    return $ExcludedDirectories -contains $Directory.Name -or $Directory.Name.StartsWith(".browser-")
}

function Test-ExcludedFile {
    param([Parameter(Mandatory = $true)][System.IO.FileInfo]$File)

    foreach ($Pattern in $ExcludedFilePatterns) {
        if ($File.Name -like $Pattern) {
            return $true
        }
    }
    return $false
}

function Copy-SourceTree {
    param(
        [Parameter(Mandatory = $true)][string]$Source,
        [Parameter(Mandatory = $true)][string]$Destination
    )

    New-Item -ItemType Directory -Path $Destination -Force | Out-Null

    Get-ChildItem -LiteralPath $Source -Force | ForEach-Object {
        if ($_.PSIsContainer) {
            if (Test-ExcludedDirectory $_) {
                return
            }
            Copy-SourceTree -Source $_.FullName -Destination (Join-Path $Destination $_.Name)
            return
        }

        if (Test-ExcludedFile $_) {
            return
        }

        Copy-Item -LiteralPath $_.FullName -Destination (Join-Path $Destination $_.Name)
    }
}

try {
    if (Test-Path $StagingRoot) {
        Remove-Item -LiteralPath $StagingRoot -Recurse -Force
    }

    Copy-SourceTree -Source $Root -Destination $StagingDir

    if (Test-Path $ResolvedOutputPath) {
        Remove-Item -LiteralPath $ResolvedOutputPath -Force
    }

    Compress-Archive -Path (Join-Path $StagingDir "*") -DestinationPath $ResolvedOutputPath -Force
    Write-Host "Source package created: $ResolvedOutputPath"
} finally {
    if (Test-Path $StagingRoot) {
        Remove-Item -LiteralPath $StagingRoot -Recurse -Force
    }
}
