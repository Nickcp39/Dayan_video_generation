# 当前脚本入口

| 模式 / 用途 | 文件 |
| --- | --- |
| 原视频角色替换控制与检查 | `hanli_guard.py` |
| 已锁换皮/声音 worker | `hanli_reuse_pipeline.py`，不要直接绕过 guard 改参数 |
| 直接生成控制与检查 | `direct_animation.py` |
| 两种模式的本地媒体回归测试 | `test_hanli_guard.py`、`test_direct_animation.py` |
| 无模型的仓库检查 | `check_repository.py` |
| 归档维护 | `archive_direct_animation.py`、`hanli_freeze_controls.py`；不覆盖既有锁或归档 |

直接生成的分镜、图生视频、合成 worker 与提示词位于 `projects/007-hanli-tea-dog`。日常使用先读 [两种模式总览](../docs/VIDEO_MODES.md)。旧下载/对比/脚手架脚本仍在本机，不作为当前 Git 工作流入口。
