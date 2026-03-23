# Treadstone CLI installer for Windows
# Usage (PowerShell):
#   irm https://github.com/earayu/treadstone/releases/latest/download/install.ps1 | iex
#
# Environment variables:
#   $env:TREADSTONE_VERSION     Override version (e.g. "v0.1.4"). Default: latest release.
#   $env:TREADSTONE_INSTALL_DIR Override install directory. Default: $env:LOCALAPPDATA\treadstone

[System.Net.ServicePointManager]::SecurityProtocol = [System.Net.SecurityProtocolType]::Tls12

$ErrorActionPreference = "Stop"

$Repo    = "earayu/treadstone"
$Artifact = "treadstone-windows-amd64.exe"
$BinaryName = "treadstone.exe"

# ── Resolve version / URL ────────────────────────────────────────────────────

$Version = if ($env:TREADSTONE_VERSION) { $env:TREADSTONE_VERSION } else { "latest" }

if ($Version -eq "latest") {
    $BaseUrl = "https://github.com/$Repo/releases/latest/download"
} else {
    $BaseUrl = "https://github.com/$Repo/releases/download/$Version"
}

# ── Resolve install dir ──────────────────────────────────────────────────────

$InstallDir = if ($env:TREADSTONE_INSTALL_DIR) {
    $env:TREADSTONE_INSTALL_DIR
} else {
    Join-Path $env:LOCALAPPDATA "treadstone"
}

if (-not (Test-Path $InstallDir)) {
    New-Item -ItemType Directory -Path $InstallDir | Out-Null
}

$InstallPath = Join-Path $InstallDir $BinaryName

# ── Download ─────────────────────────────────────────────────────────────────

Write-Host "Downloading $Artifact from $BaseUrl ..."
Invoke-WebRequest -Uri "$BaseUrl/$Artifact" -OutFile $InstallPath -UseBasicParsing

# ── Checksum verification (best-effort) ──────────────────────────────────────

$ChecksumsUrl = "$BaseUrl/checksums.txt"
$TmpChecksums = Join-Path $env:TEMP "treadstone-checksums.txt"

try {
    Invoke-WebRequest -Uri $ChecksumsUrl -OutFile $TmpChecksums -UseBasicParsing -ErrorAction Stop
    $Lines = Get-Content $TmpChecksums
    $Expected = ($Lines | Where-Object { $_ -match $Artifact }) -replace "\s+.*", ""
    if ($Expected) {
        $Actual = (Get-FileHash -Path $InstallPath -Algorithm SHA256).Hash.ToLower()
        if ($Expected.ToLower() -eq $Actual) {
            Write-Host "Checksum verified."
        } else {
            Write-Error "Checksum mismatch! Removing download."
            Remove-Item $InstallPath -Force
            exit 1
        }
    }
} catch {
    Write-Host "Note: checksum file not available, skipping verification."
} finally {
    if (Test-Path $TmpChecksums) { Remove-Item $TmpChecksums -Force }
}

# ── Add to PATH (current user, permanent) ────────────────────────────────────

$UserPath = [System.Environment]::GetEnvironmentVariable("PATH", "User")
if ($UserPath -notlike "*$InstallDir*") {
    [System.Environment]::SetEnvironmentVariable("PATH", "$UserPath;$InstallDir", "User")
    Write-Host "Added $InstallDir to your PATH."
    Write-Host "Restart your terminal for the change to take effect."
}

# ── Done ─────────────────────────────────────────────────────────────────────

Write-Host ""
Write-Host "treadstone installed to $InstallPath"
Write-Host ""
Write-Host "Run: treadstone --help"
