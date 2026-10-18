#Requires -Version 5.1
<#
.SYNOPSIS
    通过 Chrome 企业策略静默强制安装 yt-cookie-auto 扩展。
.DESCRIPTION
    写入 ExtensionInstallForcelist 注册表项，Chrome 下次启动时自动安装扩展，
    不需要开发者模式，用户不需要点任何东西。

    重要前置条件：扩展必须已经上架 Chrome 网上应用店。
    未上架的自托管扩展在普通个人 Windows 上会被 Chrome 标记为 [BLOCKED]
    （官方限制：非商店扩展的强制安装要求设备加入 AD 域或 Chrome Enterprise Core）。
.PARAMETER ExtensionId
    上架后由 Google 分配的 32 位扩展 ID。
.PARAMETER Machine
    写入 HKLM（机器级，所有用户生效）。需要管理员权限。
    默认写入 HKCU（仅当前用户，不需要管理员）。
.PARAMETER Uninstall
    删除策略项，而不是写入。
.EXAMPLE
    powershell -ExecutionPolicy Bypass -File install_extension_policy.ps1 -ExtensionId "abcdefghijklmnopabcdefghijklmnop"
.EXAMPLE
    powershell -ExecutionPolicy Bypass -File install_extension_policy.ps1 -Uninstall
#>
[CmdletBinding()]
param(
    [string]$ExtensionId,
    [switch]$Machine,
    [switch]$Uninstall
)

$ErrorActionPreference = "Stop"

$StoreUpdateUrl = "https://clients2.google.com/service/update2/crx"
$Placeholders = @("", "<上架后拿到的扩展ID>", "<EXTENSION_ID>", "YOUR_EXTENSION_ID")

if ($Machine) {
    $Root  = "HKLM:\SOFTWARE\Policies\Google\Chrome"
    $Scope = "HKLM（机器级，所有用户）"
} else {
    $Root  = "HKCU:\SOFTWARE\Policies\Google\Chrome"
    $Scope = "HKCU（当前用户）"
}
$KeyPath = Join-Path $Root "ExtensionInstallForcelist"

function Test-IsAdmin {
    $id = [Security.Principal.WindowsIdentity]::GetCurrent()
    $p  = New-Object Security.Principal.WindowsPrincipal($id)
    return $p.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

function Get-ChromeRunning {
    return [bool](Get-Process -Name "chrome" -ErrorAction SilentlyContinue)
}

# ------------------------------------------------------------------ 卸载
if ($Uninstall) {
    if (-not (Test-Path $KeyPath)) {
        Write-Host "策略项不存在，无需卸载：$KeyPath" -ForegroundColor Yellow
        exit 0
    }
    $values = Get-ItemProperty $KeyPath
    $removed = 0
    foreach ($name in ($values.PSObject.Properties | Where-Object {
                $_.Name -notlike "PS*" -and $_.Name -ne "(default)" }).Name) {
        try {
            Remove-ItemProperty -Path $KeyPath -Name $name -Force
            Write-Host "已删除：$name" -ForegroundColor Green
            $removed++
        } catch {
            Write-Host "删除 $name 失败：$($_.Exception.Message)" -ForegroundColor Red
        }
    }
    Write-Host ""
    Write-Host "已从 $Scope 卸载策略（共 $removed 条）。"
    Write-Host "完全退出 Chrome 后重开，扩展会被移除。"
    exit 0
}

# ------------------------------------------------------------------ 安装
if ($Placeholders -contains $ExtensionId) {
    Write-Host "错误：需要提供扩展 ID。" -ForegroundColor Red
    Write-Host ""
    Write-Host "扩展 ID 在扩展上架 Chrome 网上应用店后由 Google 分配（32 位字符）。"
    Write-Host "用法："
    Write-Host "  powershell -ExecutionPolicy Bypass -File install_extension_policy.ps1 -ExtensionId `"<扩展ID>`""
    Write-Host ""
    Write-Host "还没上架？那只能先用开发者模式加载："
    Write-Host "  chrome://extensions -> 开发者模式 -> 加载已解压的扩展程序 -> 选 chrome-extension 目录"
    exit 1
}

if ($ExtensionId.Length -ne 32) {
    Write-Host "警告：扩展 ID 通常是 32 位字符，你给的是 $($ExtensionId.Length) 位。" -ForegroundColor Yellow
    $ans = Read-Host "仍然继续？(y/N)"
    if ($ans -notmatch "^[Yy]$") { exit 1 }
}

if ($Machine -and -not (Test-IsAdmin)) {
    Write-Host "错误：写 HKLM 需要管理员权限。" -ForegroundColor Red
    Write-Host "请以管理员身份运行 PowerShell，或去掉 -Machine 改用 HKCU。"
    exit 1
}

$Value = "$ExtensionId;$StoreUpdateUrl"

# 找一个可用的索引：优先复用已经指向同一扩展的位置，否则用下一个空位
$Index = $null
if (Test-Path $KeyPath) {
    $existing = Get-ItemProperty $KeyPath
    foreach ($p in $existing.PSObject.Properties) {
        if ($p.Name -like "PS*" -or $p.Name -eq "(default)") { continue }
        if ($p.Value -eq $Value) {
            Write-Host "策略已存在且指向同一扩展，无需重复写入（索引 $($p.Name)）。" -ForegroundColor Green
            $Index = $p.Name
            break
        }
    }
}
if (-not $Index) {
    for ($i = 1; $i -le 50; $i++) {
        $n = [string]$i
        if (Test-Path $KeyPath) {
            $v = Get-ItemProperty -Path $KeyPath -Name $n -ErrorAction SilentlyContinue
            if ($v) { continue }
        }
        $Index = $n
        break
    }
}
if (-not $Index) {
    Write-Host "错误：索引 1-50 都被占用了。" -ForegroundColor Red
    exit 1
}

try {
    if (-not (Test-Path $KeyPath)) {
        New-Item -Path $KeyPath -Force | Out-Null
        Write-Host "已创建：$KeyPath" -ForegroundColor Green
    }
    New-ItemProperty -Path $KeyPath -Name $Index -Value $Value -PropertyType String -Force | Out-Null
} catch {
    Write-Host ""
    Write-Host "写入注册表失败：$($_.Exception.Message)" -ForegroundColor Red
    Write-Host ""
    Write-Host "常见原因："
    if (-not $Machine -and -not (Test-IsAdmin)) {
        Write-Host "  1. 当前 PowerShell 被安全软件 / 沙箱限制了注册表写入（最常见）"
        Write-Host "     -> 换一个普通的 PowerShell 窗口（非 IDE 内置终端）再试"
    }
    Write-Host "  2. 公司电脑由 IT 统一管理，策略被锁定 -> 联系 IT"
    Write-Host "  3. 想写 HKLM 却没用管理员身份 -> 以管理员身份运行，或去掉 -Machine"
    Write-Host ""
    Write-Host "不想折腾注册表的话，开发者模式加载一样能用，只是要点 3 下："
    Write-Host "  chrome://extensions -> 开发者模式 -> 加载已解压的扩展程序"
    exit 1
}

Write-Host ""
Write-Host "已写入策略：$Scope" -ForegroundColor Green
Write-Host "  索引 $Index = $Value"
Write-Host ""

if (Get-ChromeRunning) {
    Write-Host "检测到 Chrome 正在运行。" -ForegroundColor Yellow
    Write-Host "必须完全退出 Chrome 再重开才会生效（任务管理器里确认没有残留的 chrome.exe）。"
} else {
    Write-Host "Chrome 未运行，下次启动会自动安装扩展。"
}

Write-Host ""
Write-Host "验证：打开 chrome://policy，搜索 ExtensionInstallForcelist，"
Write-Host "      状态应为『正常』；若显示 [BLOCKED]，说明扩展尚未上架商店。"
Write-Host "      再打开 chrome://extensions 确认扩展已启用。"
Write-Host ""
Write-Host "卸载：powershell -ExecutionPolicy Bypass -File install_extension_policy.ps1 -Uninstall"
