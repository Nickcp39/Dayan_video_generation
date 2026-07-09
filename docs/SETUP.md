# 环境搭建 SOP(Windows + NVIDIA 独显)

按顺序装。每步有检查点,过了再往下。

> 前提:Windows 11,NVIDIA 独显,已装最新显卡驱动。C 盘或数据盘留 ≥ 50GB(模型很大)。

---

## 0. 基础工具

### 0.1 ffmpeg(合成必需)
- 下载:https://www.gyan.dev/ffmpeg/builds/ (取 `ffmpeg-release-essentials.zip`)
- 解压到如 `D:\tools\ffmpeg\`,把 `D:\tools\ffmpeg\bin` 加入系统环境变量 `Path`。
- **检查点**:新开 PowerShell 跑 `ffmpeg -version`,有版本号即可。

### 0.2 Git(已装可跳过)
- https://git-scm.com/download/win

---

## 1. FaceFusion(换脸)

推荐用**整合包**,免去 Python 配置。

- B 站搜「FaceFusion 3 整合包」,下载解压到 `D:\tools\facefusion\`(**放本仓库外**,别入 git)。
- 双击启动脚本(通常 `run.bat` / `一键启动.bat`),等它拉起浏览器 WebUI。
- 首次会下载模型,耐心等。
- **检查点**:浏览器打开 FaceFusion 界面,能选 Source(脸图)和 Target(视频)。

> 官方(自行配置 Python 版):https://github.com/facefusion/facefusion

**冒烟测试**:随便拿一张脸图 + 一段短视频,导出一次,能出换脸片即通过。

---

## 2. GPT-SoVITS v4(换声)

同样用整合包。

- B 站/官网搜「GPT-SoVITS v4 整合包」,解压到 `D:\tools\gpt-sovits\`。
- 官方:https://github.com/RVC-Boss/GPT-SoVITS ,说明站:https://gpt-sovits.org/
- 双击 `go-webui.bat` 启动,打开推理页(1-GPT-SoVITS-TTS → 推理)。
- 用**内置预训练模型**即可零样本克隆(无需自己训练)。
- **检查点**:上传一段 5–30s 参考音 + 填参考音对应文本 + 目标台词 → 点合成 → 出一段目标音色的语音。

**参考音要求**:干净人声,无 BGM、无混响,采样率不限(建议 ≥ 16kHz),内容任意但吐字清晰。

---

## 3.(后期)ComfyUI —— 对口型 / 全身替换

阶段 3、4 才需要,测试期先跳过。

- 装 ComfyUI(整合包或官方 https://github.com/comfyanonymous/ComfyUI )。
- 对口型:装 MuseTalk / LatentSync 自定义节点。
- 全身替换:装 Wan2.2-Animate 相关节点 + 模型。
- 工作流 json 存到本仓库 `comfyui/workflows/`。

---

## 装完自检清单

- [ ] `ffmpeg -version` 正常
- [ ] FaceFusion WebUI 能打开、能出一次换脸片
- [ ] GPT-SoVITS WebUI 能打开、能合成一段克隆语音
- [ ] 三个第三方工具都装在**仓库外**(如 `D:\tools\`),没进 git

全过 → 回到 `docs/PLAN.md` 阶段 2,开跑华强买瓜测试。
