# Dayan Video Generation 🎬

AI 换脸 / 换声 / 换身材 视频生产线。一套可复用的本地管线,批量产出二创视频(番剧二创、影视鬼畜等)。

> ⚠️ 使用前必读 [`docs/COMPLIANCE.md`](docs/COMPLIANCE.md) —— AI 内容标识、肖像权/声音权、版权红线。

---

## 这是什么

不是做单条视频,而是一条**流水线**:素材库共享,每条视频是一个独立的 `project`,复制模板即可开新片。

四个可插拔环节:

| 环节 | 作用 | 工具 |
|------|------|------|
| ① 换脸 | 只换脸,保留原动作背景 | FaceFusion / ReActor |
| ② 换身材 | 全身替换(体型+动作) | Wan2.2-Animate(ComfyUI) |
| ③ 换声 | 克隆音色配音 | GPT-SoVITS v4 |
| ④ 对口型 | 嘴型对上新配音 | MuseTalk / LatentSync |

当前进度见 [`docs/PLAN.md`](docs/PLAN.md)。

---

## 快速开始

1. **装环境**:照 [`docs/SETUP.md`](docs/SETUP.md) 装 FaceFusion + GPT-SoVITS。
2. **开新项目**:
   ```powershell
   ./scripts/new_project.ps1 -Name "002-my-video"
   ```
3. **填素材**:把源片放进 `projects/002-*/source/`,把目标脸放 `assets/faces/`,声音参考放 `assets/voices/`,改好 `project.yaml`。
4. **跑管线**:按 [`docs/PIPELINE.md`](docs/PIPELINE.md) 各环节操作,中间产物落 `work/`。
5. **合成出片**:
   ```powershell
   ./scripts/compose.ps1 -Video projects/002-*/work/faceswap.mp4 -Audio projects/002-*/work/voice.wav -Out projects/002-*/output/final.mp4
   ```

---

## 目录结构

```
Dayan_video_generation/
├── README.md
├── docs/                      # 计划 / 管线 / 安装 / 合规 文档
│   ├── PLAN.md
│   ├── PIPELINE.md
│   ├── SETUP.md
│   └── COMPLIANCE.md
├── assets/                    # 跨项目共享素材库
│   ├── faces/                 #   目标脸图库
│   ├── voices/                #   目标声音参考库
│   └── bgm/                   #   背景音乐 / 音效
├── projects/                  # 每条视频一个文件夹
│   ├── _template/             #   新视频模板(复制它开新片)
│   └── 001-huaqiang-maigua/   #   第一个测试:华强买瓜
├── scripts/                   # 复用脚本(建项目 / 合成)
├── comfyui/workflows/         # ComfyUI 工作流(换身/对口型用)
└── tools/                     # 第三方整合包(不入 git)
```

每个 `project` 内部:

```
001-huaqiang-maigua/
├── project.yaml    # 该视频的配置:源片、用哪张脸、哪个声、台词
├── script.md       # 台词 / 分镜脚本
├── source/         # 原始素材片段
├── work/           # 中间产物(换脸视频、配音 wav)
└── output/         # 成片
```

> 媒体文件(mp4/wav/图片/模型)默认不入 git,只跟踪配置、脚本、文档。见 `.gitignore`。
