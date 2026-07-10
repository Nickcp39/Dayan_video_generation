# 下载 B 站源片段到某个项目的 source/
# 用法:
#   ./scripts/fetch_source.ps1                                   # 默认下华强买瓜原版到 001
#   ./scripts/fetch_source.ps1 -Url "https://www.bilibili.com/video/BVxxxx/" -Project 002-xxx -Name myclip
#
# 需要 B 站【登录态】cookie 过风控(否则会 HTTP 412):
#   1) 浏览器装扩展「Get cookies.txt LOCALLY」
#   2) 登录 bilibili.com,点扩展导出 cookies.txt
#   3) 把文件放到  tools/bili_cookies.txt
param(
    [string]$Url     = "https://www.bilibili.com/video/BV1zB4y1N7Hq/",
    [string]$Project = "001-huaqiang-maigua",
    [string]$Name    = "huaqiang_maigua",
    [int]$MaxHeight  = 720
)
$ErrorActionPreference = "Stop"
$root = Split-Path $PSScriptRoot -Parent

# 找本地 ffmpeg(tools/ 里那份)
$ff = Get-ChildItem -Path (Join-Path $root "tools") -Recurse -Filter ffmpeg.exe -ErrorAction SilentlyContinue | Select-Object -First 1
$dest = Join-Path $root "projects/$Project/source"
if (-not (Test-Path $dest)) { New-Item -ItemType Directory -Force $dest | Out-Null }
$cookies = Join-Path $root "tools/bili_cookies.txt"
$ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"

$ytArgs = @(
    "-m", "yt_dlp",
    "-f", "bv*[height<=$MaxHeight]+ba/b[height<=$MaxHeight]/b",
    "--merge-output-format", "mp4",
    "-o", (Join-Path $dest "$Name.%(ext)s"),
    "--user-agent", $ua
)
if ($ff)    { $ytArgs += @("--ffmpeg-location", $ff.DirectoryName) }
if (Test-Path $cookies) {
    $ytArgs += @("--cookies", $cookies)
    Write-Host "使用登录 cookie: tools/bili_cookies.txt"
} else {
    Write-Warning "未找到 tools/bili_cookies.txt —— 匿名下载大概率被 B 站 412 拦截。请先按脚本头部说明导出 cookie。"
}

Write-Host "下载: $Url  ->  projects/$Project/source/$Name.mp4"
py @ytArgs $Url
