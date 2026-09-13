# 本地运行环境

当前验证环境是 Windows、RTX 4090 24 GB、64 GB 内存。仓库只保存工作流源码和配置；模型、媒体、运行时和第三方整合包需要在本地准备。

| 部分 | 当前职责 / 本地位置 |
| --- | --- |
| ComfyUI | Pinokio 管理；HTTP API 默认 `127.0.0.1:8188`；在这里执行图片和视频模型 |
| 常规 Python | `.venv-video-test/Scripts/python.exe`；依赖 requests、numpy、Pillow，声音配置解析需 PyYAML |
| GPT-SoVITS | `GPT-SoVITS-v3lora-20250228`，内部 runtime；已有 e8 模型和 ref001，生成时不训练 |
| FFmpeg / FFprobe | `tools/ffmpeg-8.1.2-essentials_build/bin` |
| 可选 ASR | 本地 faster-whisper medium，辅助核对台词，不替代试听 |

## 模型与资产清单

- 换皮模式：`workflows/hanli-v1/lock.json`，配方、环境和参考见 [接手规范](HANLI_PIPELINE_HANDOFF.md)。
- 直接生成模式：`workflows/direct-animation-v1/lock.json`，图片模型来源见 `projects/007-hanli-tea-dog/evidence/model_manifest.json`。
- 共用声音 profile：`projects/004-hanli-voice-finetune/approved_profile_v1.json`。profile 记录的声音权重和参考图/参考声在本机，Git 不包含这些媒体。

不要按“最新版”批量升级已锁环境；不要下载整套模型来跑一次轻量仓库检查。迁移路径或环境变更应建立新版本复验，不重算旧锁来掩盖变化。

## 运行前

1. 根据实际输入选择 [模式](VIDEO_MODES.md)，阅读对应规范。
2. 恢复该模式清单中的模型和资产。历史样片的全量 Checker 还需要历史生成文件。
3. 如需启动 ComfyUI，通过 Pinokio/pterm 检查状态与队列，再用已验证 launcher；不要关闭未知 GPU 作业。
4. 新片放新目录，逐阶段检查；FAIL/BLOCKED 时停止下游执行。

具体已验证版本、参数、启动选项、恢复命令及局限都在对应模式规范中。[仓库与本地文件的边界](REPOSITORY_SCOPE.md)。
