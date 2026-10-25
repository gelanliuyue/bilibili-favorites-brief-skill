#Requires -Version 5.1
<#
    bilibili-favorites-brief  skill installer (Windows)

    Installs the skill into WorkBuddy and/or Codex skill directories and writes
    the machine-specific config.json that the skill reads at runtime.

    Examples:
      .\install.ps1 -ProjectRoot "D:\code\bili-brief"
      .\install.ps1 -Target codex -ProjectRoot "D:\code\bili-brief" -Force
      .\install.ps1 -Target custom -TargetDir "C:\my\skills" -ProjectRoot "D:\code\bili-brief"
#>
[CmdletBinding()]
param(
    [ValidateSet('workbuddy', 'codex', 'both', 'custom')]
    [string]$Target = 'both',

    [string]$TargetDir = '',

    [string]$ProjectRoot = '',

    [string]$BackendUrl = 'http://127.0.0.1:8483',

    [string]$OutputRoot = '',

    [string]$PythonExe = '',

    [string]$ProviderId = 'deepseek',

    [string]$ModelName = 'deepseek-chat',

    [switch]$Force
)

$ErrorActionPreference = 'Stop'
$SkillName = 'bilibili-favorites-brief'
$PackageRoot = $PSScriptRoot
$Source = Join-Path $PackageRoot $SkillName

function Write-Step($text) { Write-Host "==> $text" -ForegroundColor Cyan }
function Write-Ok($text) { Write-Host "    OK   $text" -ForegroundColor Green }
function Write-Warn2($text) { Write-Host "    WARN $text" -ForegroundColor Yellow }

Write-Step "Checking package contents"
if (-not (Test-Path (Join-Path $Source 'SKILL.md'))) {
    throw "SKILL.md not found under $Source. Run this script from the extracted package folder."
}
foreach ($required in @('scripts\bili_favorites.py', 'scripts\render_report.py', 'references\batch-manifest.md')) {
    if (-not (Test-Path (Join-Path $Source $required))) {
        throw "Package is incomplete: missing $required"
    }
}
Write-Ok "package layout verified"

function Read-WithDefault($prompt, $default) {
    if ([string]::IsNullOrWhiteSpace($default)) {
        $value = Read-Host $prompt
        if ([string]::IsNullOrWhiteSpace($value)) { throw "$prompt is required." }
        return $value.Trim()
    }
    return $default
}

$ProjectRoot = Read-WithDefault "Path to the bili-brief project root" $ProjectRoot
$ProjectRoot = $ProjectRoot.TrimEnd('\', '/')

if ([string]::IsNullOrWhiteSpace($OutputRoot)) {
    $OutputRoot = Join-Path $env:USERPROFILE 'Documents\BiliBrief'
}

if ([string]::IsNullOrWhiteSpace($PythonExe)) {
    $candidate = Join-Path $ProjectRoot 'backend\.venv\Scripts\python.exe'
    if (Test-Path $candidate) {
        $PythonExe = $candidate
    } else {
        $fallback = (Get-Command python -ErrorAction SilentlyContinue)
        if ($fallback) { $PythonExe = $fallback.Source }
    }
}

Write-Step "Resolving skill target directories"
$targets = @()
switch ($Target) {
    'workbuddy' { $targets += ,@('WorkBuddy', (Join-Path $env:USERPROFILE '.workbuddy\skills')) }
    'codex' { $targets += ,@('Codex', (Join-Path $env:USERPROFILE '.codex\skills')) }
    'both' {
        $targets += ,@('WorkBuddy', (Join-Path $env:USERPROFILE '.workbuddy\skills'))
        $targets += ,@('Codex', (Join-Path $env:USERPROFILE '.codex\skills'))
    }
    'custom' {
        if ([string]::IsNullOrWhiteSpace($TargetDir)) { throw "-TargetDir is required when -Target custom is used." }
        $targets += ,@('Custom', $TargetDir)
    }
}
foreach ($t in $targets) { Write-Ok "$($t[0]): $($t[1])" }

Write-Step "Installing skill files"
$installedPaths = @()
foreach ($t in $targets) {
    $label = $t[0]
    $root = $t[1]
    if (-not (Test-Path $root)) { New-Item -ItemType Directory -Path $root -Force | Out-Null }
    $dest = Join-Path $root $SkillName

    if (Test-Path $dest) {
        if ($Force) {
            Remove-Item -Recurse -Force $dest
            Write-Ok "$label existing copy replaced"
        } else {
            $backup = "$dest.bak-" + (Get-Date -Format 'yyyyMMdd-HHmmss')
            Rename-Item -Path $dest -NewName (Split-Path $backup -Leaf)
            Write-Warn2 "$label existing copy moved to $backup"
        }
    }

    Copy-Item -Path $Source -Destination $root -Recurse -Force
    $installedPaths += $dest
    Write-Ok "$label installed to $dest"
}

Write-Step "Writing config.json"
$config = [ordered]@{
    project_root = $ProjectRoot
    backend_url  = $BackendUrl
    output_root  = $OutputRoot
    provider_id  = $ProviderId
    model_name   = $ModelName
}
$configJson = $config | ConvertTo-Json -Depth 4
foreach ($dest in $installedPaths) {
    $configPath = Join-Path $dest 'config.json'
    [System.IO.File]::WriteAllText($configPath, $configJson, (New-Object System.Text.UTF8Encoding($false)))
    Write-Ok "$configPath"
}

Write-Step "Verifying runtime"
if (-not $PythonExe -or -not (Test-Path $PythonExe)) {
    Write-Warn2 "Python interpreter not found. Set it after install by editing project_root or use a PATH python."
} else {
    $markdownOk = & $PythonExe -c "import markdown, sys; print(sys.version.split()[0] + ' markdown ' + markdown.__version__)" 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Ok "python: $PythonExe ($markdownOk)"
    } else {
        Write-Warn2 "python found but 'markdown' import failed. Run: `"$PythonExe`" -m pip install markdown"
    }
    & $PythonExe (Join-Path $installedPaths[0] 'scripts\bili_favorites.py') --help | Out-Null
    if ($LASTEXITCODE -eq 0) { Write-Ok "bili_favorites.py CLI loads" } else { Write-Warn2 "bili_favorites.py failed to load" }
}

try {
    $resp = Invoke-WebRequest -Uri $BackendUrl -UseBasicParsing -TimeoutSec 5
    Write-Ok "backend $BackendUrl responding (HTTP $($resp.StatusCode))"
} catch {
    $code = $null
    if ($_.Exception.Response) { $code = [int]$_.Exception.Response.StatusCode }
    if ($code) {
        Write-Ok "backend $BackendUrl responding (HTTP $code)"
    } else {
        Write-Warn2 "backend $BackendUrl not reachable. Start BiliBrief backend before using the skill."
    }
}

Write-Host ""
Write-Host "Done. Installed to:" -ForegroundColor Cyan
foreach ($p in $installedPaths) { Write-Host "  $p" }
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Cyan
Write-Host "  1. Restart the agent app so the skill is discovered."
Write-Host "  2. Make sure the BiliBrief backend is running at $BackendUrl"
Write-Host "  3. Smoke test:  `"$PythonExe`" `"$(Join-Path $installedPaths[0] 'scripts\bili_favorites.py')`" --config `"$(Join-Path $installedPaths[0] 'config.json')`" list"
Write-Host ""
