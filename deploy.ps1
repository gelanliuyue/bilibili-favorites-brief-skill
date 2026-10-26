#Requires -Version 5.1
<#
    BiliBrief server deployment (Windows)

    Turns a fresh clone of this repo into a runnable local BiliBrief backend:
      1. checks Python 3.10+
      2. creates server\backend\.venv and installs requirements.txt
      3. creates server\backend\.env from .env.example (once)
      4. checks ffmpeg availability
      5. optionally builds the frontend, or reports the prebuilt dist
      6. optionally starts the backend

    Examples:
      .\deploy.ps1
      .\deploy.ps1 -Start
      .\deploy.ps1 -Recreate
      .\deploy.ps1 -BuildFrontend
#>
[CmdletBinding()]
param(
    [string]$ServerDir = (Join-Path $PSScriptRoot 'server'),
    [string]$PythonExe = '',
    [switch]$Recreate,
    [switch]$BuildFrontend,
    [switch]$Start,
    [switch]$SkipInstall
)

$ErrorActionPreference = 'Stop'

function Write-Step($text) { Write-Host "==> $text" -ForegroundColor Cyan }
function Write-Ok($text) { Write-Host "    OK   $text" -ForegroundColor Green }
function Write-Warn2($text) { Write-Host "    WARN $text" -ForegroundColor Yellow }

$BackendDir = Join-Path $ServerDir 'backend'
$VenvDir = Join-Path $BackendDir '.venv'
$VenvPy = Join-Path $VenvDir 'Scripts\python.exe'
$Requirements = Join-Path $BackendDir 'requirements.txt'

Write-Step 'Checking server snapshot'
if (-not (Test-Path $Requirements)) {
    throw "requirements.txt not found at $Requirements. Run this script from the repo root."
}
Write-Ok "server: $ServerDir"

Write-Step 'Resolving Python 3.10+'
function Get-PythonVersion($exe) {
    try {
        $out = & $exe -c "import sys; print('%d.%d' % sys.version_info[:2])" 2>$null
        if ($LASTEXITCODE -eq 0 -and $out) { return [version]$out }
    } catch { }
    return $null
}

$chosen = $null
$chosenVer = $null
if ($PythonExe) {
    $chosen = $PythonExe
    $chosenVer = Get-PythonVersion $PythonExe
} else {
    foreach ($candidate in @('py -3', 'python', 'python3')) {
        $parts = $candidate.Split(' ')
        $cmd = Get-Command $parts[0] -ErrorAction SilentlyContinue
        if (-not $cmd) { continue }
        $ver = if ($parts.Length -gt 1) { Get-PythonVersion "$($cmd.Source) $($parts[1])" } else { Get-PythonVersion $cmd.Source }
        if ($ver -and $ver -ge [version]'3.10') {
            $chosen = if ($parts.Length -gt 1) { "$($cmd.Source) $($parts[1])" } else { $cmd.Source }
            $chosenVer = $ver
            Write-Ok "python $ver -> $chosen"
            break
        }
    }
}

if (-not $chosen) {
    # PATH 上没有，回退到常见安装位置（Windows 安装器默认落点）
    $patterns = @(
        (Join-Path $env:LOCALAPPDATA 'Programs\Python\Python3*\python.exe'),
        (Join-Path $env:ProgramFiles 'Python3*\python.exe'),
        'C:\Python3*\python.exe'
    )
    foreach ($pattern in $patterns) {
        if ($chosen) { break }
        foreach ($exe in (Get-ChildItem $pattern -ErrorAction SilentlyContinue | Sort-Object Name -Descending)) {
            $ver = Get-PythonVersion $exe.FullName
            if ($ver -and $ver -ge [version]'3.10') {
                $chosen = $exe.FullName
                $chosenVer = $ver
                Write-Ok "python $ver -> $chosen (found in default install path)"
                break
            }
        }
    }
}

if (-not $chosen) {
    throw 'Python 3.10+ not found. Install it from https://www.python.org/downloads/ and re-run, or pass -PythonExe "C:\path\python.exe".'
}
if ($chosenVer -and $chosenVer -ge [version]'3.13') {
    Write-Warn2 "python $chosenVer detected; 3.10-3.12 is recommended because onnxruntime / ctranslate2 wheels may be missing on 3.13."
}

Write-Step 'Preparing virtual environment'
if ($Recreate -and (Test-Path $VenvDir)) {
    Remove-Item -Recurse -Force $VenvDir
    Write-Ok 'old venv removed'
}
if (-not (Test-Path $VenvPy)) {
    Push-Location $BackendDir
    try {
        $parts = $chosen.Split(' ')
        if ($parts.Length -gt 1) { & $parts[0] $parts[1] -m venv .venv } else { & $chosen -m venv .venv }
        if ($LASTEXITCODE -ne 0) { throw 'venv creation failed' }
    } finally { Pop-Location }
    Write-Ok "venv created: $VenvDir"
} else {
    Write-Ok 'venv already present'
}

if (-not $SkipInstall) {
    Write-Step 'Installing Python dependencies (this takes several minutes)'
    & $VenvPy -m pip install --upgrade pip --quiet
    & $VenvPy -m pip install -r $Requirements
    if ($LASTEXITCODE -ne 0) { throw 'pip install failed' }

    # ctranslate2==4.6.0 在 import 时依赖 pkg_resources，setuptools>=81 已移除它。
    # requirements.txt 里已锁 setuptools<81；这里再兜一次，防止旧 venv 残留新版。
    & $VenvPy -m pip install --quiet 'setuptools<81'
    $smoke = & $VenvPy -c "import ctranslate2, faster_whisper, fastapi; print('ok')" 2>&1
    if ($LASTEXITCODE -ne 0) {
        Write-Warn2 "dependency import smoke test failed: $smoke"
        Write-Host '         Try: & "' -NoNewline; Write-Host "$VenvPy" -NoNewline
        Write-Host '" -m pip install "setuptools<81"  then re-run this script.' -ForegroundColor Yellow
    } else {
        Write-Ok 'dependencies installed (import smoke test passed)'
    }
} else {
    Write-Warn2 'dependency install skipped (-SkipInstall)'
}

Write-Step 'Configuring backend .env'
$envFile = Join-Path $BackendDir '.env'
$envExample = Join-Path $BackendDir '.env.example'
if (Test-Path $envFile) {
    Write-Ok '.env already exists (left untouched)'
} elseif (Test-Path $envExample) {
    Copy-Item $envExample $envFile
    Write-Ok ".env created from .env.example -> $envFile"
} else {
    Write-Warn2 '.env.example missing, skipped'
}

Write-Step 'Checking ffmpeg'
function Set-EnvValue($path, $key, $value) {
    # 只改目标行，保留其余内容和 UTF-8 无 BOM 编码
    if (-not (Test-Path $path)) { return $false }
    $lines = [System.IO.File]::ReadAllLines($path)
    $hit = $false
    for ($i = 0; $i -lt $lines.Length; $i++) {
        if ($lines[$i] -match ('^\s*' + [regex]::Escape($key) + '\s*=')) { $lines[$i] = "$key=$value"; $hit = $true }
    }
    if (-not $hit) { $lines = @($lines) + "$key=$value" }
    [System.IO.File]::WriteAllLines($path, $lines, (New-Object System.Text.UTF8Encoding($false)))
    return $true
}

function Find-FfmpegDir {
    # winget 装完当前 shell 的 PATH 往往还没刷新，Get-Command 会漏掉，这里直接扫常见落点
    $onPath = Get-Command ffmpeg -ErrorAction SilentlyContinue
    if ($onPath) { return (Split-Path $onPath.Source -Parent) }

    $candidates = @(
        (Join-Path $env:USERPROFILE 'scoop\shims\ffmpeg.exe'),
        'C:\ProgramData\chocolatey\bin\ffmpeg.exe',
        'C:\ffmpeg\bin\ffmpeg.exe'
    )
    foreach ($c in $candidates) {
        if (Test-Path $c) { return (Split-Path $c -Parent) }
    }

    $wingetRoot = Join-Path $env:LOCALAPPDATA 'Microsoft\WinGet\Packages'
    if (Test-Path $wingetRoot) {
        $hit = Get-ChildItem -Path $wingetRoot -Filter 'ffmpeg.exe' -Recurse -Depth 5 -ErrorAction SilentlyContinue |
            Select-Object -First 1
        if ($hit) { return (Split-Path $hit.FullName -Parent) }
    }
    return $null
}

$ffmpegOk = $false
$ffmpegEnv = $null
if (Test-Path $envFile) {
    $line = Select-String -Path $envFile -Pattern '^\s*FFMPEG_BIN_PATH\s*=\s*(.+)$' -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($line) {
        $ffmpegEnv = $line.Matches[0].Groups[1].Value.Trim().Trim('"').Trim("'")
        if ($ffmpegEnv) {
            $resolved = if ([System.IO.Path]::IsPathRooted($ffmpegEnv)) { $ffmpegEnv } else { Join-Path $BackendDir $ffmpegEnv }
            if (Test-Path (Join-Path $resolved 'ffmpeg.exe')) { $ffmpegOk = $true; Write-Ok "FFMPEG_BIN_PATH -> $resolved" }
        }
    }
}
if (-not $ffmpegOk) {
    $bundled = Join-Path $BackendDir 'tools\ffmpeg'
    if (Test-Path (Join-Path $bundled 'ffmpeg.exe')) { $ffmpegOk = $true; Write-Ok "bundled ffmpeg: $bundled" }
}
if (-not $ffmpegOk) {
    $found = Find-FfmpegDir
    if ($found) {
        $ffmpegOk = $true
        Write-Ok "ffmpeg found: $found"
        # 关键：找到了但可能不在当前（或后端进程的）PATH 里，写进 .env 才真正生效
        if ((Test-Path $envFile) -and -not $ffmpegEnv) {
            if (Set-EnvValue $envFile 'FFMPEG_BIN_PATH' $found) {
                $ffmpegOk = $true
                Write-Ok "FFMPEG_BIN_PATH written to .env"
            }
        } elseif ($ffmpegEnv) {
            Write-Warn2 "FFMPEG_BIN_PATH in .env is '$ffmpegEnv' but ffmpeg.exe is not there; using $found instead"
            Set-EnvValue $envFile 'FFMPEG_BIN_PATH' $found | Out-Null
            Write-Ok 'FFMPEG_BIN_PATH updated in .env'
        }
    }
}
if (-not $ffmpegOk) {
    Write-Warn2 'ffmpeg not found. Video/audio download and slicing will fail without it.'
    Write-Host '         Install one of these ways, then re-run:' -ForegroundColor Yellow
    Write-Host '           winget install --id Gyan.FFmpeg -e'
    Write-Host '           or download ffmpeg, put ffmpeg.exe/ffprobe.exe into server\backend\tools\ffmpeg\'
    Write-Host "           or add to server\backend\.env :  FFMPEG_BIN_PATH=D:\ffmpeg\bin"
}

Write-Step 'Frontend'
$distIndex = Join-Path $ServerDir 'BillNote_frontend\dist\index.html'
if ($BuildFrontend) {
    $npm = Get-Command npm -ErrorAction SilentlyContinue
    if (-not $npm) {
        Write-Warn2 'npm not found; skipping frontend build. Prebuilt dist stays in use.'
    } else {
        Push-Location (Join-Path $ServerDir 'BillNote_frontend')
        try {
            if (Test-Path 'pnpm-lock.yaml') {
                $pnpm = Get-Command pnpm -ErrorAction SilentlyContinue
                if ($pnpm) { & pnpm install; & pnpm run build } else { & npm install; & npm run build }
            } else {
                & npm install; & npm run build
            }
            Write-Ok 'frontend built'
        } finally { Pop-Location }
    }
} elseif (Test-Path $distIndex) {
    Write-Ok "prebuilt frontend present: $(Join-Path $ServerDir 'BillNote_frontend\dist')"
} else {
    Write-Warn2 'no prebuilt dist; pass -BuildFrontend on a machine with Node.js'
}

Write-Step 'Summary'
Write-Host "    python : $VenvPy"
Write-Host "    backend: $BackendDir"
Write-Host "    .env   : $envFile"
Write-Host ''
Write-Host 'Next steps:' -ForegroundColor Cyan
Write-Host "  1. Start backend (terminal A):  cd `"$BackendDir`" ; .\.venv\Scripts\python.exe main.py"
Write-Host '     default listener: http://127.0.0.1:8483  (override with BACKEND_PORT in .env)'
Write-Host "  2. Start web UI (terminal B):   cd `"$ServerDir`" ; .\backend\.venv\Scripts\python.exe serve_web.py"
Write-Host '     -> http://127.0.0.1:3015   (serves dist AND proxies /api to 8483)'
Write-Host '     Do NOT use "python -m http.server": it has no /api proxy, the UI will'
Write-Host '     report "backend failed to start" after 60s.'
Write-Host '  3. Open the UI, sign in to Bilibili, and save your model API key in Settings.'
Write-Host '  4. Install the skill against this server:'
Write-Host "     powershell -ExecutionPolicy Bypass -File .\install.ps1 -ProjectRoot `"$ServerDir`""
Write-Host ''

if ($Start) {
    Write-Step 'Starting backend (Ctrl+C to stop)'
    Push-Location $BackendDir
    try { & $VenvPy main.py } finally { Pop-Location }
}
