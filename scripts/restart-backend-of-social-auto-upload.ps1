# ==================================================================
#  重启后端服务（Flask：sau_backend.py，默认端口 5409）
#
#  做的事：
#    1. 结束占用 5409 端口的进程（后端没在运行时跳过这一步）
#    2. 用项目 venv 的 python.exe 重新启动 sau_backend.py
#       输出追加写入 logs\backend.log（超过 5MB 自动轮转为 .1）
#    3. 等待端口就绪并报告结果；失败时打印日志尾部
#
#  用法（直接双击 restart-backend-of-social-auto-upload.bat 即可）：
#    restart-backend-of-social-auto-upload.bat                  重启后端
#    restart-backend-of-social-auto-upload.bat -Port 5409       指定端口
#    restart-backend-of-social-auto-upload.bat -TimeoutSeconds 60
# ==================================================================
[CmdletBinding()]
param(
    [int]$Port = 5409,
    [int]$TimeoutSeconds = 30
)

$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

function Get-PortOwner {
    # 返回监听指定端口的进程 PID 列表
    param([int]$Port)

    $owners = New-Object System.Collections.Generic.List[int]
    foreach ($line in (& netstat -ano -p TCP 2>$null)) {
        $parts = @(($line -split '\s+') | Where-Object { $_ })
        if ($parts.Count -ge 5 -and $parts[3] -eq 'LISTENING' -and $parts[1] -match ":$Port$") {
            if ($parts[4] -match '^\d+$') { $owners.Add([int]$parts[4]) }
        }
    }
    return @($owners | Select-Object -Unique)
}

function Test-PortOpen {
    param([int]$Port)

    $client = New-Object System.Net.Sockets.TcpClient
    try {
        $async = $client.BeginConnect('127.0.0.1', $Port, $null, $null)
        if (-not $async.AsyncWaitHandle.WaitOne(400)) { return $false }
        $client.EndConnect($async)
        return $true
    } catch {
        return $false
    } finally {
        $client.Close()
    }
}

function Stop-Backend {
    param([int]$Port)

    $owners = @(Get-PortOwner -Port $Port)
    if ($owners.Count -eq 0) {
        Write-Host "[1/3] 端口 $Port 空闲，后端未在运行，无需结束进程"
        return $true
    }

    foreach ($ownerId in $owners) {
        Write-Host "[1/3] 结束占用端口 $Port 的进程 PID $ownerId"
        & taskkill /F /T /PID $ownerId 2>&1 | Out-Null
    }

    # 等端口真正释放，最多 10 秒
    for ($i = 0; $i -lt 20; $i++) {
        if (-not (Test-PortOpen -Port $Port)) { return $true }
        Start-Sleep -Milliseconds 500
    }
    Write-Host "      端口 $Port 仍被占用，无法重启（可能不是本项目进程）" -ForegroundColor Red
    return $false
}

function Resolve-Python {
    param([string]$Root, [string]$ScriptDir)

    $venv = Join-Path $Root '.venv\Scripts\python.exe'
    if (Test-Path $venv) { return $venv }

    $pathsFile = Join-Path $ScriptDir 'paths.json'
    if (Test-Path $pathsFile) {
        try {
            $cfg = Get-Content $pathsFile -Raw | ConvertFrom-Json
            if ($cfg.python -and (Test-Path $cfg.python)) { return $cfg.python }
        } catch { }
    }

    $cmd = Get-Command python.exe -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }
    return $null
}

function Start-Backend {
    # 窗口完全隐藏；cmd 负责把 python 的 stdout/stderr 追加到日志文件，
    # 这样本脚本退出后子进程和日志写入都不受影响。
    param([string]$Python, [string]$Root, [string]$LogFile)

    $logDir = Split-Path -Parent $LogFile
    if (-not (Test-Path $logDir)) {
        New-Item -ItemType Directory -Force -Path $logDir | Out-Null
    }
    if ((Test-Path $LogFile) -and (Get-Item $LogFile).Length -gt 5MB) {
        Move-Item $LogFile "$LogFile.1" -Force
    }

    $command = '/c ""{0}" -u sau_backend.py >> "{1}" 2>&1"' -f $Python, $LogFile
    return Start-Process -FilePath $env:ComSpec -ArgumentList $command `
        -WorkingDirectory $Root -WindowStyle Hidden -PassThru
}

function Show-LogTail {
    param([string]$LogFile, [int]$Lines = 20)

    if (-not (Test-Path $LogFile)) { return }
    Write-Host "      最近日志（$LogFile）：" -ForegroundColor DarkGray
    Get-Content $LogFile -Tail $Lines | ForEach-Object {
        Write-Host "        $_" -ForegroundColor DarkGray
    }
}

# ---------------- 主流程 ----------------
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$root = Split-Path -Parent $scriptDir
$logFile = Join-Path $root 'logs\backend.log'

$python = Resolve-Python -Root $root -ScriptDir $scriptDir
if (-not $python) {
    Write-Host "未找到 python.exe，请先创建虚拟环境：python -m venv .venv" -ForegroundColor Red
    exit 1
}

Write-Host "后端目录：$root"
Write-Host ""

if (-not (Stop-Backend -Port $Port)) { exit 1 }

Write-Host "[2/3] 启动后端：$python -u sau_backend.py"
$process = Start-Backend -Python $python -Root $root -LogFile $logFile

Write-Host "[3/3] 等待端口 $Port 就绪（最多 $TimeoutSeconds 秒）"
$deadline = (Get-Date).AddSeconds($TimeoutSeconds)
$ready = $false
while ((Get-Date) -lt $deadline) {
    if ($process.HasExited) { break }
    if (Test-PortOpen -Port $Port) { $ready = $true; break }
    Start-Sleep -Milliseconds 500
}

if (-not $ready) {
    Write-Host ""
    Write-Host "后端启动失败（进程已退出：$($process.HasExited)）" -ForegroundColor Red
    Show-LogTail -LogFile $logFile
    exit 1
}

Write-Host ""
Write-Host "后端已启动：http://localhost:$Port" -ForegroundColor Green
Write-Host "日志：$logFile"
exit 0
