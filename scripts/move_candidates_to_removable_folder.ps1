[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$ConfigPath = Join-Path $ProjectRoot 'config.json'

function Resolve-ConfiguredPath {
    param(
        [Parameter(Mandatory = $true)]
        [string]$PathValue,
        [Parameter(Mandatory = $true)]
        [string]$BaseDirectory
    )

    if ([System.IO.Path]::IsPathRooted($PathValue)) {
        return [System.IO.Path]::GetFullPath($PathValue)
    }
    return [System.IO.Path]::GetFullPath((Join-Path $BaseDirectory $PathValue))
}

function Test-PathWithinRoot {
    param(
        [Parameter(Mandatory = $true)]
        [string]$CandidatePath,
        [Parameter(Mandatory = $true)]
        [string]$RootPath
    )

    $normalizedRoot = [System.IO.Path]::GetFullPath($RootPath).TrimEnd('\') + '\'
    $normalizedCandidate = [System.IO.Path]::GetFullPath($CandidatePath)
    return $normalizedCandidate.StartsWith($normalizedRoot, [System.StringComparison]::OrdinalIgnoreCase)
}

if (-not (Test-Path -LiteralPath $ConfigPath -PathType Leaf)) {
    throw "找不到配置文件：$ConfigPath"
}

$config = Get-Content -LiteralPath $ConfigPath -Raw -Encoding UTF8 | ConvertFrom-Json
if (-not $config.launch -or [string]::IsNullOrWhiteSpace($config.launch.input_dir)) {
    throw 'config.json 缺少 launch.input_dir。'
}
if ([string]::IsNullOrWhiteSpace($config.launch.output_dir)) {
    throw 'config.json 缺少 launch.output_dir。'
}
if (-not $config.deletion -or [string]::IsNullOrWhiteSpace($config.deletion.target_folder_name)) {
    throw 'config.json 缺少 deletion.target_folder_name。'
}

$InputRoot = Resolve-ConfiguredPath -PathValue $config.launch.input_dir -BaseDirectory $ProjectRoot
$ReportDirectory = Resolve-ConfiguredPath -PathValue $config.launch.output_dir -BaseDirectory $ProjectRoot
$ReportFileName = "report_$([System.IO.Path]::GetFileName($InputRoot.TrimEnd('\'))).csv"
$ReportPath = Join-Path $ReportDirectory $ReportFileName
if (-not (Test-Path -LiteralPath $InputRoot -PathType Container)) {
    throw "配置的视频输入目录不存在：$InputRoot"
}
if (-not (Test-Path -LiteralPath $ReportPath -PathType Leaf)) {
    throw "当前检查报告不存在：$ReportPath。请先运行 run_video_sorter.bat 完成检查。"
}

$TargetRoot = [System.IO.Path]::GetFullPath((Join-Path $InputRoot $config.deletion.target_folder_name))
if (-not (Test-PathWithinRoot -CandidatePath $TargetRoot -RootPath $InputRoot)) {
    throw "可删除文件夹必须位于源视频目录内：$TargetRoot"
}

$rows = @(Import-Csv -LiteralPath $ReportPath -Encoding UTF8)
$eligible = [System.Collections.Generic.List[object]]::new()
$seenPaths = [System.Collections.Generic.HashSet[string]]::new([System.StringComparer]::OrdinalIgnoreCase)
$alreadyAbsentCount = 0
$targetExistsCount = 0
$skippedCount = 0

foreach ($row in $rows) {
    $relativePath = [string]$row.relative_path
    if ([string]::IsNullOrWhiteSpace($relativePath) -or $row.status -ne 'ok' -or $row.result -ne '可删除候选') {
        $skippedCount++
        continue
    }
    if ([System.IO.Path]::IsPathRooted($relativePath)) {
        $skippedCount++
        continue
    }

    try {
        $sourcePath = [System.IO.Path]::GetFullPath((Join-Path $InputRoot $relativePath))
        $targetPath = [System.IO.Path]::GetFullPath((Join-Path $TargetRoot $relativePath))
    } catch {
        $skippedCount++
        continue
    }

    if (
        -not (Test-PathWithinRoot -CandidatePath $sourcePath -RootPath $InputRoot) -or
        (Test-PathWithinRoot -CandidatePath $sourcePath -RootPath $TargetRoot) -or
        -not (Test-PathWithinRoot -CandidatePath $targetPath -RootPath $TargetRoot) -or
        -not $seenPaths.Add($sourcePath)
    ) {
        $skippedCount++
        continue
    }
    if (-not (Test-Path -LiteralPath $sourcePath -PathType Leaf)) {
        $alreadyAbsentCount++
        continue
    }
    if (Test-Path -LiteralPath $targetPath) {
        $targetExistsCount++
        continue
    }

    $eligible.Add([PSCustomObject]@{
        RelativePath = $relativePath
        SourcePath = $sourcePath
        TargetPath = $targetPath
    })
}

Write-Host ''
Write-Host '============================================================' -ForegroundColor Yellow
Write-Host '开始移动当前检查报告中的可删除候选' -ForegroundColor Yellow
Write-Host "报告文件：$ReportPath"
Write-Host "视频输入目录：$InputRoot"
Write-Host "可删除文件夹：$TargetRoot"
Write-Host "CSV 行数：$($rows.Count)；即将移动：$($eligible.Count)；已不存在：$alreadyAbsentCount；目标已存在：$targetExistsCount；其他跳过：$skippedCount"
Write-Host '============================================================' -ForegroundColor Yellow

$movedCount = 0
$failedCount = 0
foreach ($item in $eligible) {
    try {
        New-Item -ItemType Directory -Path (Split-Path -Parent $item.TargetPath) -Force | Out-Null
        Move-Item -LiteralPath $item.SourcePath -Destination $item.TargetPath -ErrorAction Stop
        $movedCount++
        Write-Host "[已移动] $($item.RelativePath)" -ForegroundColor Green
    } catch {
        $failedCount++
        Write-Host "[失败] $($item.RelativePath)：$($_.Exception.Message)" -ForegroundColor Red
    }
}

Write-Host ''
Write-Host "完成：已移动 $movedCount 个，已不存在（跳过）$alreadyAbsentCount 个，目标已存在（跳过）$targetExistsCount 个，其他跳过 $skippedCount 个，失败 $failedCount 个。" -ForegroundColor Green
