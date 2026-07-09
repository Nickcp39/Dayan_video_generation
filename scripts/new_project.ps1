# 从模板创建一个新视频项目
# 用法: ./scripts/new_project.ps1 -Name "002-my-video"
param(
    [Parameter(Mandatory = $true)][string]$Name
)

$ErrorActionPreference = "Stop"
$root = Split-Path $PSScriptRoot -Parent
$template = Join-Path $root "projects/_template"
$dest = Join-Path $root "projects/$Name"

if (Test-Path $dest) {
    throw "项目已存在: $dest"
}

Copy-Item $template $dest -Recurse
# 用新 id 回填 project.yaml
$yaml = Join-Path $dest "project.yaml"
(Get-Content $yaml -Raw) -replace 'id: TEMPLATE', "id: $Name" | Set-Content $yaml -Encoding utf8

Write-Host "已创建新项目: projects/$Name"
Write-Host "下一步: 放源片到 source/ ,改 project.yaml ,准备 assets/faces 与 assets/voices"
