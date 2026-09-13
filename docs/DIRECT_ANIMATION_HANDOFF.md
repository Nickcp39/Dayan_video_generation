# 直接生成模式 v1：Pipeline 与 Checker

这是独立于换皮模式的新流程。用户已看过 10 秒喝茶撸狗成片并说：“ok， 彻底通了。 太好了。 虽然图像质量有点卡通。 不知道为啥，但是逻辑是对的”。这一声明绑定到本次最终 MP4 和配置的 SHA256，没有扩大为任何未来成片的验收。

## 保存位置

- 控制入口：`scripts/direct_animation.py`。
- 锁：`workflows/direct-animation-v1/lock.json`，记录代码和所用模型、声音参考、FFmpeg 等依赖 SHA256。
- 已接受项目：`projects/007-hanli-tea-dog`；成片：`output/hanli_tea_dog_10s_v2/hanli_tea_dog_10s_v2.mp4`。
- 配置：项目 `project.json` 定义台词、规格、语音分割/起点；`production.json` 定义角色资产、两个选定首帧、动作提示、种子、字幕及成片路径。
- 实际图像生成入口：项目 007 的 `pipeline.py`；独立 `templates/wan5b_api.json`，不再依赖项目 002 的测试图。
- 断点客户端：`safe_runner.py`；合成：`compose.py`；图像、失败尝试、原始动画和执行 history 均保留。
- 固化快照：`releases/direct-animation-v1-20260913`。它保存代码、配置、审查、选定资产、原始镜头和成片；基础大模型与 Python 环境按锁引用，不重复打包。

## 固定配方

图片用 FLUX.2 Klein 4B FP8 + Qwen3 4B + Flux2 VAE；先准备人物角度、狗、环境和分镜，再检查多手、道具、服装、构图。多面图是角色设定资产，不能直接作为视频首帧。

每个首帧输入 Wan2.2 TI2V-5B FP16，UMT5 FP8、Wan2.2 VAE，960×544、24fps、121帧、24步、CFG5、UniPC/simple、shift8。两个约5秒镜头各取5秒，最终10秒。当前只固化这个两镜头规格；修改模型/规格要另建配方版本，不重算现有锁来掩盖改变。

声音只读引用第八轮 GPT-SoVITS profile，cut0、ref001、seed42、原速；本片静音处 2.4 秒切开，两段分别从 2.1 和 5.9 秒放入。换台词后必须重新确定切分点和字幕时间，不能沿用这组时刻。没有口型模型，按内心独白处理。

公开方法依据和模型文档在项目 `README.md`：参考资产 → 分镜迭代 → I2V → 动作挑选 → 配音和剪辑。不是宣称复制了某厂内部系统。

## 日常入口

在工作区根目录，使用 `.venv-video-test/Scripts/python.exe`：

```powershell
$Py = '.venv-video-test/Scripts/python.exe'
$Control = 'scripts/direct_animation.py'
$P = 'projects/007-hanli-tea-dog'
& $Py $Control plan --project $P
& $Py $Control check --project $P --stage all
# 首次执行或环境改变后，完整读取并校验模型/工具文件（可能耗时数分钟）
& $Py $Control check --project $P --stage all --dependencies
```

退出码：0 PASS、1 FAIL、2 BLOCKED。非零停止下游执行，检查 JSON 报告。不为通过检查而降低标准、改参数或覆盖旧文件。

| Checker 阶段 | 核查内容 |
| --- | --- |
| project | 模式、配方、两镜头规格、路径不越界、字幕与台词一致、语音窗口不重叠 |
| assets | 资产可解码、选定首帧和提示存在、审图声明绑定到当前资产/配置/提示哈希 |
| voice | 真正的 WAV、非静音/过度削波、原速能放进时间窗、请求与锁定 profile 一致、权重哈希、已有 ASR 正文 |
| renders | 两次 history 成功、prompt ID 一致、history 图等于提交图、全图匹配配方、参考哈希、121帧/24fps、完整解码、采样非空非静止 |
| final | 上述检查；10秒240帧、H.264/AAC，原始配音逐样本重建时间轴，最终音轨相关度 >0.98；指定镜头与成片采样画面相关度 >0.98，字幕正文存在 |
| all | 技术检查 + 用户针对当前成片/配置/配方的实际验收记录 |

`check` 可离线执行；不要求 ComfyUI 在线。`--dependencies` 才全量哈希视频/图片基础模型，普通 check 检查代码和每次使用的声音权重。运动检测只排除明显静图，不能证明“正确喝茶/撸狗”；发音、相似度和动作仍要看片试听。ASR 不是人耳验收。

## 新片步骤

```powershell
# 新目录名按任务修改；已有目录会拒绝覆盖。
& $Py $Control new --project projects/008-direct-animation
$P = 'projects/008-direct-animation'
```

new 复制当前设定与选定图片作为可修改草稿，不复制生成视频、声音和验收。先修改新项目配置、提示和首帧；新人物应重新准备角色设定和参考图。两个首帧的道具/衣服/场景保持一致。局部修图可用图片模型或确定性素材合成，并记录决定。

图片生成仍用已固化的 worker，所有输出写入新项目：

```powershell
& $Py projects/007-hanli-tea-dog/pipeline.py image --project $P --name frame_trial_01 --prompt-file "$P/prompts/tea_video.txt" --ref "$P/assets/hanli_01.jpg" --width 1024 --height 576
```

上面只示范参数形式，正式制图应写专门的构图提示，不能机械沿用动作提示。图像挑选后更新 `production.json` 的 assets/reference；完成实际审查后记录：

```powershell
& $Py $Control review --project $P --kind assets --reviewer operator --evidence '填写实际审查的角色、道具、手部和场景结果'
& $Py $Control run --project $P --stage voice
# 完成实际逐字试听，再执行下面的记录命令。
& $Py $Control review --project $P --kind voice --reviewer operator --evidence '填写实际试听结果和残留问题'
& $Py $Control run --project $P --stage render --shot tea
& $Py $Control run --project $P --stage render --shot dog
& $Py $Control run --project $P --stage compose
& $Py $Control check --project $P --stage final
# 用户看过并明确接受这份成片后，原话如实记录，不能由 AI 假冒批准。
& $Py $Control review --project $P --kind final --reviewer user --evidence '填写用户实际验收原话' --known-issue '填写明确保留的问题'
& $Py $Control check --project $P --stage all
```

这些 review 是可审计声明，不是身份认证。旧样片只回填实际审图和用户最终验收，不捏造历史上单独进行过的声音审查门禁。已有 review 不覆盖；修改配置后请用新 attempt，避免沿用过期验收。

## 服务、断点与隔离

- 本机 ComfyUI 由 Pinokio/pterm 管理；启动/恢复前读 Pinokio skill。控制器只检查 HTTP，不自动安装/升级/重启服务。9881 被占用时 SoVITS worker 停止，不接管别人的进程。
- render 前检查已锁依赖、环境版本/启动选项和队列。新控制执行使用独立 execution.lock；不能按“锁很旧”自动删除，先查 PID 与服务器任务。
- safe_runner 在 POST 前保存提交意图和 client_id，收到 prompt_id 才标为已提交。超时只停止等待，不取消服务器作业；HTTP 请求自身另有超时。
- 已知 prompt_id 用相同 project/shot 恢复：`run --stage render --shot tea --resume --timeout 900`。恢复只查历史和下载，不再 POST。队列仍有任务时先等其完成再恢复。
- 没收到 prompt_id 的提交保持现场，人工按 client_id、时间与图核对 queue/history；不换名称偷偷重提。图片任务可用 worker 的 `resume --project ... --kind storyboards --name ...` 恢复已知任务。
- 既有样片禁止 run；new 建新项目。不自动删除失败文件，不改原换皮 guard、worker、锁或归档；声音共享已验收权重，不训练。
- 字幕与画面采样检查、声音时间轴技术检查通过后，仍需人检查具体表演和口型。批量可靠性尚未验证。

## Checker 自测

```powershell
& $Py scripts/test_direct_animation.py
```

用临时副本验证错误尺寸、路径越界、错误字幕、重叠音轨、缺失/过期验收、执行图变更、坏视频会被拒绝；模拟队列占用、提交超时和恢复时保证不重复 POST。它不生成视频；真实样片还要执行 all check。
