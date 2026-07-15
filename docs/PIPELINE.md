# 管线技术说明

一条视频最多经过四个环节。每个环节独立、可插拔:测试期只用 ① + ③,后期再加 ④、②。

```
原片 ─▶ ①换脸 ─▶ ④对口型 ─▶ 成片画面
                    ▲
        ②换身材(替代①,换整个人)
                    │
参考音 ─▶ ③换声 ────┘(提供新配音)
```

---

## ⓪ 源片获取(下载)

管线的第一步是拿到源视频,放进 `projects/<项目>/source/`。

- **B 站**:用 **https://snapany.com/zh/bilibili** —— 粘贴链接直接下 mp4。
  - 不要用 yt-dlp 下 B 站:会撞 IP 风控 `HTTP 412`(强制登录态),而 Chrome 新版 App-Bound 加密又让 yt-dlp 读不到浏览器 cookie,无解。
- **YouTube**:用 yt-dlp(仓库已装),需绕过 SABR:
  ```powershell
  py -m yt_dlp --extractor-args "youtube:player_client=android,ios,tv" `
    --ffmpeg-location "tools/ffmpeg-8.1.2-essentials_build/bin" `
    -f "bv*[height<=720]+ba/b[height<=720]/b" --merge-output-format mp4 `
    -o "projects/<项目>/source/<名字>.%(ext)s" "<YouTube链接>"
  ```
- **要点**:很多梗片 YouTube 上也有(搜「刘华强买瓜 征服」),YouTube 走 yt-dlp 比 B 站顺;B 站则走 snapany。

---

## ① 换脸 —— FaceFusion

- **输入**:源视频 + 1 张目标正脸图
- **输出**:`work/faceswap.mp4`(只换脸,动作/背景/原声不变)
- **工具**:FaceFusion 3.x(免费开源、本地跑、不传数据)。进阶质量用 DeepFaceLab(需训练),ComfyUI 里用 ReActor 节点。
- **要点**:目标脸要清晰正脸、光照正常;源片人脸别太侧、别遮挡。

## ② 换身材 / 全身替换 —— Wan2.2-Animate(后期)

- **输入**:源视频 + 目标角色形象
- **输出**:换掉整个人(体型 + 姿态 + 动作,表情同步)
- **工具**:Wan2.2-Animate,跑在 ComfyUI,工作流存 `comfyui/workflows/`。RTX 3090/4090 跑 1080p 顺畅。
- **定位**:做「把华强换成另一个人」这种狠活时用;测试阶段先不碰。

## ③ 换声 —— GPT-SoVITS v4

- **输入**:5–30s 目标声音参考 + 台词文本
- **输出**:`work/voice.wav`(目标音色说新台词)
- **工具**:GPT-SoVITS v4(中文最强,5 秒即可克隆,48kHz)。多语言用 CosyVoice2,备选 Fish Speech。
- **要点**:参考音要干净(无背景音、无混响);台词尽量贴原片时长,减少后续对口型压力。

## ④ 对口型 —— MuseTalk / LatentSync(后期)

- **输入**:换脸后视频 + 新配音
- **输出**:`work/lipsync.mp4`(嘴型对上新音频)
- **工具**:MuseTalk(快、均衡,支持中文)、LatentSync(画质优先)、Wav2Lip(口型最准)。
- **定位**:换声后消除嘴型错位。测试阶段用「原台词」规避,阶段 3 再正式加。

---

## 合成 —— ffmpeg

最后把「画面轨」和「配音轨」合到一起:

```powershell
./scripts/compose.ps1 -Video work/faceswap.mp4 -Audio work/voice.wav -Out output/final.mp4
```

底层等价于:
```
ffmpeg -i faceswap.mp4 -i voice.wav -map 0:v -map 1:a -c:v copy -c:a aac -shortest final.mp4
```
需要卡点、字幕、BGM 时,再用剪映 / DaVinci 做后期。

---

## 硬件需求

| 场景 | 显卡 | 说明 |
|------|------|------|
| 换脸 + 换声 | RTX 3060 12GB 起 | 测试够用 |
| 加对口型 | RTX 3090/4090 24GB | 更稳 |
| 全身替换 | RTX 3090/4090 24GB | 1080p 流畅 |
| 显存不足 | 云端 AutoDL 租卡 / RunComfy | 按小时计费 |

---

## 工具与官方地址

- FaceFusion —— 开源换脸
- GPT-SoVITS —— https://gpt-sovits.org/
- Wan2.2-Animate —— ComfyUI 全身替换
- MuseTalk —— Tencent,实时对口型
- LatentSync —— ByteDance,高画质对口型
- ComfyUI —— 主平台,节点式工作流
