# 本地视频的两种已跑通模式

截至 2026-09-13，两条模式分别有用户接受的 10 秒样片。共同使用已训练的韩立第八轮声音；无需为每条新片重新训练。

| 模式 | 实际输入与处理 | 控制入口 | 已接受样片 |
| --- | --- | --- | --- |
| 换皮 / 角色替换 | 原视频 → SAM2 人物蒙版、DWPose 姿态 → Wan2.2 Animate → 恢复蒙版外背景 → SoVITS | `scripts/hanli_guard.py` | `projects/006-hanli-reuse-10s/retry_10fps` |
| 直接生成 / 动漫制作 | 角色参考、场景与分镜图 → Wan2.2 TI2V-5B 图生视频 → SoVITS → 剪辑字幕；不需要动作源视频 | `scripts/direct_animation.py` | `projects/007-hanli-tea-dog` |

## 接手顺序

1. 先确认输入是原视频，还是角色参考与剧本。根据输入选模式，不将换皮的蒙版/姿态步骤硬套到直接生成。
2. 换皮读 [原模式接手规范](HANLI_PIPELINE_HANDOFF.md)，继续用原 guard 和锁，保留原来的已知漏字问题。
3. 直接生成读 [直接生成接手规范](DIRECT_ANIMATION_HANDOFF.md)，使用新控制入口、独立锁和项目目录。
4. 任何新片先建新目录；不要覆盖两个已接受样片。两种模式都要做视觉与声音审查，技术 PASS 不等于人物、表演、口型完美。

两个只读复查命令，在工作区根目录运行：

```powershell
& '.venv-video-test/Scripts/python.exe' scripts/hanli_guard.py check --project projects/006-hanli-reuse-10s/retry_10fps --stage all
& '.venv-video-test/Scripts/python.exe' scripts/direct_animation.py check --project projects/007-hanli-tea-dog --stage all
```

直接生成完整依赖哈希复查加 `--dependencies`。检查只新增报告，不启动生成、下载、训练或服务。两种模式共享本机 GPU，重型任务按队列依次执行。

## 当前质量边界

- 直接生成：本地 4090 已完成喝茶、抚摸狗、指定对白与字幕；人物风格偏卡通，面部还原有限，抚摸较小，没有精确口型。用户接受的是流程和这条样片的可用程度。
- 两种模式均不因一次成功就成为无人值守的批量生产系统。新增人物、动作、风格、模型或大幅改规格需要新的实验与审查。
- 历史 `docs/PIPELINE.md` 包含更早的 FaceFusion 等探索，以本页及两份接手规范选择当前模式。
