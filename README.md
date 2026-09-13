# Dayan Video Generation

本地 RTX 4090 视频工作流：**原视频角色替换**与**从角色、分镜图直接生成动漫**。两种模式均有用户接受的 10 秒样片，共享已经训练好的韩立 GPT-SoVITS 声音。

| 模式 | 输入 → 输出 | 入口 |
| --- | --- | --- |
| 换皮 | 原视频＋人物参考 → SAM2 / DWPose → Wan2.2 Animate → 背景恢复与配音 | [hanli_guard.py](scripts/hanli_guard.py) |
| 直接生成 | 剧本＋角色资产 → 场景与分镜 → Wan2.2 TI2V-5B → 配音字幕 | [direct_animation.py](scripts/direct_animation.py) |

先读 [两种模式总览](docs/VIDEO_MODES.md)，再按实际输入选择流程：

- [换皮接手规范与 Checker](docs/HANLI_PIPELINE_HANDOFF.md)
- [直接生成接手规范与 Checker](docs/DIRECT_ANIMATION_HANDOFF.md)
- [流程图](docs/PIPELINE.md)
- [本地环境与资产](docs/SETUP.md)
- [仓库范围：什么上传、什么保留本地](docs/REPOSITORY_SCOPE.md)

## 仓库包含什么

控制脚本、Checker、模型/API 工作流、配置与提示词、依赖 SHA256 锁、制作说明和实测结论。模型、视频、音频、图片、第三方环境、完整本地归档和临时实验均不上传。

**这是一份工作流源码与设计仓库，不是 clone 后就能运行的整合包。** 完整生成和历史样片复查需要本地模型、参考资产、ComfyUI、SoVITS 及 FFmpeg。当前配置和锁基于 Windows 实测环境，换机器须单独复验。

## 先检查，再执行

```powershell
# 轻量源码检查，无需 GPU 或模型
python scripts/check_repository.py

# 以下需恢复本地环境与样片资产
& '.venv-video-test/Scripts/python.exe' scripts/hanli_guard.py check --project projects/006-hanli-reuse-10s/retry_10fps --stage all
& '.venv-video-test/Scripts/python.exe' scripts/direct_animation.py check --project projects/007-hanli-tea-dog --stage all
```

任何新片使用新项目目录，保留已接受样片。技术检查、看图试听、用户验收分别记录；不把一次成功出片当作批量稳定，也不声称已经解决精确口型。当前已知限制见各模式规范。
