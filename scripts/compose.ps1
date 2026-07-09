# 合成出片:把换脸后的视频画面 + 新配音合到一起
# 用法: ./scripts/compose.ps1 -Video work/faceswap.mp4 -Audio work/voice.wav -Out output/final.mp4
param(
    [Parameter(Mandatory = $true)][string]$Video,
    [Parameter(Mandatory = $true)][string]$Audio,
    [Parameter(Mandatory = $true)][string]$Out
)

$ErrorActionPreference = "Stop"

if (-not (Get-Command ffmpeg -ErrorAction SilentlyContinue)) {
    throw "找不到 ffmpeg,请先按 docs/SETUP.md 装好并加入 PATH"
}
if (-not (Test-Path $Video)) { throw "视频不存在: $Video" }
if (-not (Test-Path $Audio)) { throw "音频不存在: $Audio" }

$outDir = Split-Path $Out -Parent
if ($outDir -and -not (Test-Path $outDir)) { New-Item -ItemType Directory -Force $outDir | Out-Null }

# 用新音频替换原声;-shortest 以较短轨为准
ffmpeg -y -i $Video -i $Audio -map 0:v:0 -map 1:a:0 -c:v copy -c:a aac -shortest $Out

if ($LASTEXITCODE -eq 0) {
    Write-Host "成片已生成: $Out"
} else {
    throw "ffmpeg 合成失败 (exit $LASTEXITCODE)"
}
