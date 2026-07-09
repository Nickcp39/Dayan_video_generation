# 计划 / 路线图

## 总目标
搭一条可复用的本地 AI 视频生产线,批量产出换脸/换声/换身二创视频。先用「华强买瓜」跑通最小管线,再逐步加能力、上量产。

---

## 阶段路线图

### ✅ 阶段 0 —— 工程骨架(已完成)
- [x] 仓库结构、模板、脚本、文档
- [x] 连接 GitHub 远程仓库
- [x] 合规文档

### ▶ 阶段 1 —— 环境搭建(进行中)
目标:本地(独显)装好换脸 + 换声两套工具。
- [ ] 装 FaceFusion(整合包)—— 见 `docs/SETUP.md`
- [ ] 装 GPT-SoVITS v4(整合包)
- [ ] 装 ffmpeg(合成用)
- **检查点**:两个工具能开界面,`ffmpeg -version` 有输出。

### 阶段 2 —— 第一个测试:华强买瓜(换脸 + 换声)
项目目录:`projects/001-huaqiang-maigua/`
- [ ] 拿到源片段 `source/huaqiang_maigua.mp4`(《征服》华强买瓜 ~20s)
- [ ] 准备目标脸图 → `assets/faces/`
- [ ] 准备目标声音参考 5–30s → `assets/voices/`
- [ ] FaceFusion 换脸 → `work/faceswap.mp4`
- [ ] GPT-SoVITS 克隆配音(原台词)→ `work/voice.wav`
- [ ] `compose.ps1` 合成 → `output/final.mp4`
- **检查点**:一条能看的成片。
- **已知取舍**:未做对口型,新配音用原台词以减少嘴型错位。

### 阶段 3 —— 加对口型
- [ ] 装 MuseTalk / LatentSync(ComfyUI 节点)
- [ ] 管线插入 ④ 对口型,换声后嘴型对齐
- 产物升级:`work/faceswap.mp4` + `work/voice.wav` → `work/lipsync.mp4`

### 阶段 4 —— 加全身替换
- [ ] 装 Wan2.2-Animate(ComfyUI)
- [ ] 工作流存到 `comfyui/workflows/`
- 能力升级:不止换脸,能换整个人(体型+动作)

### 阶段 5 —— 量产化
- [ ] `project.yaml` 驱动的半自动流程
- [ ] 批处理脚本(一次跑多个 project)
- [ ] 素材库规范化、命名规范、成片归档

---

## 华强买瓜测试 —— 数据流

```
source/huaqiang_maigua.mp4 ─┐
                            ├─① FaceFusion(目标脸)→ work/faceswap.mp4 ─┐
assets/faces/<target>.jpg ──┘                                          ├─③ compose → output/final.mp4
                                                                       │
assets/voices/<ref>.wav ───② GPT-SoVITS(原台词)→ work/voice.wav ──────┘
```

## 需要人工提供的输入
1. **目标脸**:1 张清晰正脸图(建议虚构/授权形象,勿用明星,见合规)。
2. **目标声音**:5–30s 干净人声音频。
3. **源片段**:华强买瓜片段(可从公开视频截取)。

## 待确认
- [ ] 具体显卡型号(定显存参数、跑不跑得动全身替换)
- [ ] 目标脸 / 目标声 用谁的
