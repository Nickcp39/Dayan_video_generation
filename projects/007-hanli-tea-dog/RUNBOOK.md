# 独立生成流程复跑说明

后续执行以 [控制版接手规范](../../docs/DIRECT_ANIMATION_HANDOFF.md) 为准，入口为 `scripts/direct_animation.py`。以下是研发阶段命令记录；新片必须使用新目录，不能直接覆盖本样片。合成已支持独立项目 `project.json` 和 `production.json`，checker 与提交恢复规则见新规范。

此入口使用已经由 Pinokio 启动的本机 ComfyUI HTTP API，不安装/升级引擎。声音使用已有第八轮权重，只读引用旧声音配置。项目级生成脚本、分镜和输出均在本目录。

## 阶段

1. 查看 `README.md` 的分镜计划及 `prompts/`。剧情动作、人物和道具约束先写清楚。
2. `prepare_models.py` 从已保存的官方清单下载图片编辑所需模型。`--mirror` 只改变传输站点；最终仍按官方 SHA256 校验。模型保存在引擎模型目录的 `007_tea_dog` 子目录，不覆盖原模型。
3. 用 `pipeline.py image` 制作角度图与镜头图；以原人物图作为身份参考，以选定镜头图作为下一镜头的环境/道具参考。每张图经视觉检查，淘汰原因保存到 `evidence/visual_review.json`。
4. 用 `pipeline.py video` 将选定单张分镜图输入 Wan2.2 TI2V-5B。此阶段没有源视频、姿态视频或蒙版输入。
5. 读取声音配置进行 SoVITS 合成。ASR 只辅助检查正文，原 WAV 保留。
6. 用 `compose.py` 合成两个镜头，字幕显示用户原文；配音只按静音处分开排布，不变速。
7. `build_review.py` 汇集实际存在的分镜、原始动画与成片。全片解码通过后，仍需人工检查动作与身份，再交用户审片。

## 示例命令

在工作区根目录运行，Python 使用 `.venv-video-test/Scripts/python.exe`：

```powershell
.\.venv-video-test\Scripts\python.exe projects/007-hanli-tea-dog/pipeline.py init
.\.venv-video-test\Scripts\python.exe projects/007-hanli-tea-dog/pipeline.py image --name character_v1 --prompt-file projects/007-hanli-tea-dog/prompts/character.txt --ref assets/faces/hanli_01.jpg --width 1536 --height 768
```

其他镜头使用不同 `--name`、`--prompt-file` 和 `--ref`；`--ref` 可重复用于图片编辑。视频只接受一个首帧参考；用 `--steps`、`--frames`、`--width`、`--height` 设定参数。

本次选定镜头与合成命令（重试请换新名字，保留旧结果）：

```powershell
.\.venv-video-test\Scripts\python.exe projects/007-hanli-tea-dog/pipeline.py video --name tea_v1 --prompt-file projects/007-hanli-tea-dog/prompts/tea_video.txt --ref projects/007-hanli-tea-dog/storyboards/tea_frame_v2/13_images_00005_.png --width 960 --height 544 --frames 121 --steps 24 --seed 2026091320
.\.venv-video-test\Scripts\python.exe projects/007-hanli-tea-dog/pipeline.py video --name dog_v1 --prompt-file projects/007-hanli-tea-dog/prompts/dog_video.txt --ref projects/007-hanli-tea-dog/storyboards/dog_frame_selected/start.png --width 960 --height 544 --frames 121 --steps 24 --seed 2026091321
.\.venv-video-test\Scripts\python.exe projects/007-hanli-tea-dog/compose.py --tea projects/007-hanli-tea-dog/renders/tea_v1/58_video_00001_.mp4 --dog projects/007-hanli-tea-dog/renders/dog_v1/58_video_00002_.mp4 --name hanli_tea_dog_10s_v3
.\.venv-video-test\Scripts\python.exe projects/007-hanli-tea-dog/build_review.py
```

本次交付为 `output/hanli_tea_dog_10s_v2/hanli_tea_dog_10s_v2.mp4`。v1 合成在 FFmpeg 分流混音时停滞，只终止了该次合成进程；改为按 PCM 样本直接排时间轴，v2 已验证两段声音样本逐字节保留、10 秒时长和全片解码。字体配置有环境提示，但实际中文渲染已检查正常。

已经完成且请求一致的运行会复用记录；失败/未完成运行不会盲目重投，需先看保存的 ComfyUI prompt ID 和 history，采用新名字保留重试。

## 隔离与限制

- 不修改 `scripts/hanli_reuse_pipeline.py`、已接受的声音权重和换皮工作流。
- 本次开始后发现旧流程说明文档被并行工作补充，记录到 `baseline_check.json`，没有回滚或覆盖别人的修改。
- 初次释放已缓存的旧量化 Animate 模型时遇到引擎卸载崩溃，通过原 `start_hanli_test.json` 恢复服务，未修改引擎依赖。声音实际完成后旧打印语句出现控制台编码错误，WAV 与验证文件完整；新入口使用 UTF-8。
- 当前属于可复跑的单片实验；长期稳定性须由多条不同动作的成功率和返工量验证。
