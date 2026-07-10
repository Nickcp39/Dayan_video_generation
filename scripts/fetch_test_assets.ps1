# 下载「安全的」测试素材:AI 合成人脸(非真人)+ 免费语音样本
# 这些文件被 .gitignore 忽略,不会进仓库。
# 用法: ./scripts/fetch_test_assets.ps1
$ErrorActionPreference = "Stop"
$root = Split-Path $PSScriptRoot -Parent
$faces = Join-Path $root "assets/faces"
$voices = Join-Path $root "assets/voices"
$ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"

# 1) AI 合成人脸(StyleGAN2,非真实人物)。注意:必须带 Referer 才能过反爬。
foreach ($i in "01", "02") {
    curl.exe -sL -A $ua -e "https://thispersondoesnotexist.com/" `
        "https://thispersondoesnotexist.com/random-person.jpeg" `
        -o (Join-Path $faces "test_face_$i.jpg")
    Start-Sleep -Seconds 1
}

# 2) 免费语音样本(Open Speech Repository,英文,可免费用于测试)
curl.exe -sL "https://www.voiptroubleshooter.com/open_speech/american/OSR_us_000_0010_8k.wav" `
    -o (Join-Path $voices "test_voice_en.wav")

Write-Host "完成。测试脸: assets/faces/test_face_0*.jpg ;测试声: assets/voices/test_voice_en.wav"
Write-Host "注意:这些是占位/冒烟测试用。正式做中文配音,建议换成干净的中文参考音。"
