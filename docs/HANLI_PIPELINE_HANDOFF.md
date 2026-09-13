# 韩立短片 Pipeline：接手执行规范

版本：`hanli-v1-controls-20260913`。本文件是今后复用的入口，优先于旧文档中的直接执行命令。

## 1. 当前结论与边界

用户已经验收 10 秒「接着奏乐，接着舞」版本，原话：

> 非常好了已经，虽然吞了一个字，但是整体没有任何问题

这代表当前样片可用，不代表没有缺陷。吞掉的具体字和时间尚未定位；不得写成“已修复”“逐字完全正确”。本次固化不重新训练、不重新生成、不修改旧成片。

- 权威基准目录：`D:\work\2026 video generation\projects\006-hanli-reuse-10s\retry_10fps`。
- 成片：该目录的 `output\hanli_reuse_10s.mp4`；对照：`output\before_after_10s.mp4`。
- 原始生成器：`D:\work\2026 video generation\scripts\hanli_reuse_pipeline.py`，保留原算法。
- 唯一推荐执行入口：`D:\work\2026 video generation\scripts\hanli_guard.py`。
- 锁文件：`D:\work\2026 video generation\workflows\hanli-v1\lock.json`。
- 原历史文档：`D:\work\2026 video generation\docs\HANLI_PIPELINE_V1.md`。
- 原归档：`D:\work\2026 video generation\releases\hanli-pipeline-v1-20260913`，不可覆盖。它早于最终验收，里面的 pending 不要篡改成历史上已通过。

本规范保证的是“按已锁方案执行，异常可定位并停止”，不是跨机器逐比特相同，也不是自动保证表演、口型和发音完美。没有独立口型模型；音色来源为角色参考，输出明确标注合成，不能冒充真实配音者或真实发言。新素材须确认使用权限；公开可看不等于自由转载。

## 2. 不得擅自变动的方案

| 部分 | 固定值 |
| --- | --- |
| 声音 | GPT-SoVITS v2，已训练 e8 GPT + e8 SoVITS，推理而非重训 |
| 声音参考 | `ref001.wav`，5.30 秒留出音频及原配对文本 |
| 音色参数 | seed=42、cut0、top_k=5、top_p=1、temperature=0.8、speed=1、repetition_penalty=1.35；完整字段由 profile 锁定 |
| 声音后期 | 仅响度、延迟和补静音；不加速、不变调、不截句 |
| 人物 | `assets/faces/hanli_01.jpg` |
| 画面 | Wan2.2-Animate 14B FP8 + LightX2V LoRA + relight LoRA |
| 采样 | 6 steps、CFG=1、shift=8、Euler/simple、seed=20260913 |
| 规格 | 10 秒；640×352 原生画面；10 fps、101 帧；成片 25 fps、250 帧 |
| 预处理 | SAM2 video；正负点按新镜头标注，身体和肩部须覆盖；DWPose 面部/身体分支 |
| 合成 | grow=16、block=16，遮罩羽化 gblur=2，保留遮罩外原画面 |
| 成片 | 640×384（32 像素 AI 标识栏），H.264 + AAC，48 kHz 单声道；原音轨完全替换 |

完整图包含节点连线、负面提示词、VAE 参数等，由 `render_baseline.json` 全图比对，不只检查几个常见参数。模型、参考文件、原生成器、控制脚本、核心源码和关键运行时版本都在锁中。

旧 profile 文本提到 cut3 fallback，这是历史备选，不是本控制版的自动回退。不得因失败擅改 cut3、e4、模型、分辨率、16fps 或训练数据。要改就先说明原因，得到用户同意，再建新版本；不得重算锁来掩盖漂移。

## 3. 接手前读取与准备

1. 先读本文、项目 `project.json`、最近 `checks` 报告和各阶段 `job_state.json`。先查状态，不能见到旧输出就重跑。
2. 保留所有旧目录、权重、源视频、失败日志和成片。不启动与本任务无关的下载器、自动化或训练任务。
3. 新视频用新项目目录，复制 `workflows\hanli-v1\project.example.json` 作为配置，**不可直接覆盖基准项目**。
4. 修改新项目的 `id`、`source`、`source_url`、`source_title`、`source_start`、裁剪框、正负点、场景提示词、台词、声音起点与 purpose。`source` 相对新项目目录；profile/template 相对工作区。示例的 source 相对路径只对原目录有效，复制后必须调整。
5. 新素材限定成人单人、连续近中景、10 秒、有足够身体区域、无明显切镜。尺寸/FPS/算法不改；裁剪语法只允许 `crop=W:H:X:Y,scale=640:352,setsar=1`。
6. 本机为 Windows / RTX 4090 24GB / 64GB RAM 基准。新机器的路径迁移、驱动及依赖重建需要另行复验；归档不包含全部大型模型和 Python 环境。

## 4. 命令与阶段 Checker

PowerShell 先设置变量；之后每次只执行一阶段。例子中的 `$P` 是**只读复查基准**；生成时必须换新项目路径。

```powershell
Set-Location 'D:\work\2026 video generation'
$Py = 'D:\work\2026 video generation\.venv-video-test\Scripts\python.exe'
$Guard = 'D:\work\2026 video generation\scripts\hanli_guard.py'
$P = 'D:\work\2026 video generation\projects\006-hanli-reuse-10s\retry_10fps'
$env:PYTHONIOENCODING = 'utf-8'
& $Py $Guard check --project $P --stage all
```

检查命令不启动训练/TTS/视频生成，也不要求 ComfyUI 在线。会读取并哈希约几十 GB 的本机依赖，不是瞬间完成；只新增 `checks\check_*.json`。`environment` 才读取在线 ComfyUI。

退出码：`0=PASS`；`1=FAIL`；`2=BLOCKED`。FAIL 是不满足技术约束，BLOCKED 通常是等待人工确认、已有锁、提交结果不明或超时。非零必须停，禁止忽略返回码继续跑后续步骤。

| 顺序 | 执行命令（变量同上） | Checker / 放行条件 |
| --- | --- | --- |
| 0 环境 | `& $Py $Guard environment --project $P` | 文件 SHA256、关键 runtime 版本、在线 ComfyUI 版本/启动参数、节点存在、磁盘至少 10 GiB；不自动启动服务 |
| 1 输入 | `& $Py $Guard check --project $P --stage project` | 必填/未知字段、固定参数、时间范围、源视频存在、段落长度、点坐标、裁剪语法 |
| 2 声音 | `& $Py $Guard run --project $P --stage voice` | TTS request + inference.yaml 对应锁定模型/参数；原始与归一化 WAV 可解码；32 kHz mono、非静音、不明显削波；台词时长+offset ≤10秒 |
| 2A 试听 | 下面的 review 命令 | 按台词逐字试听、检查漏字、停顿、语气；ASR 只能辅助，不能代替听音 |
| 3 准备 | `& $Py $Guard run --project $P --stage prepare` | 输入 SHA、配置和 profile 快照、全图连线/参数、250 帧源段和101帧渲染输入 |
| 4 遮罩 | `& $Py $Guard run --project $P --stage preprocess --timeout 300` | 提交图=准备图=history 图、成功状态、三个输出可解码、10fps/101帧，无 .part；mask/person为640×352，DWPose为698×384 |
| 4A 看图 | 下面的 mask review 命令 | 看首/中/尾和转头/抬手帧，人物脸发衣肩覆盖，背景不被大面积误选，pose 正常 |
| 5 渲染 | `& $Py $Guard run --project $P --stage render --timeout 900` | 环境与前置检查、声音/遮罩已审、服务器上传内容 SHA、任务成功、四份视频格式及帧数正确 |
| 6 合成 | `& $Py $Guard run --project $P --stage compose` | 当前配置快照、对齐音频按源 WAV 重算字节相同、输出250帧/10秒、音视频均可完整解码、最终音轨与对齐音频相关系数>0.98、采样帧非空/非静止、有对照和联系表 |
| 7 交付 | `& $Py $Guard check --project $P --stage all` | 上述技术检查+**用户针对这份成片的验收记录**。未 review 则 BLOCKED，不伪装完成 |

单阶段 `check --stage X` 会检查从 lock 到 X 的技术前置项，不生成新媒体。每次 run 完成后也自动运行当前阶段 checker；run 不自动推进到下一阶段。

## 5. 人工 Checker 的证据规则

看/听过对应文件才可记录。voice/mask 可由确实检查过的操作者或 AI 记录，`--reviewer` 写真实身份；final 必须来自用户。不要把以下命令里的描述当成已经完成的事实。

```powershell
# 完成实际试听后，替换 evidence 为具体结果。
& $Py $Guard review --project $P --kind voice --reviewer operator --evidence '逐字试听结果与实际问题描述'
# 完成实际遮罩看片后。
& $Py $Guard review --project $P --kind mask --reviewer operator --evidence '实际检查的帧、肩部覆盖、背景和姿态结果'
# 用户看过最终输出并明确同意后，引用用户原话。
& $Py $Guard review --project $P --kind final --reviewer user --evidence '用户实际验收原话' --known-issue '用户接受的具体残留问题；无问题则省略此参数'
```

记录保存到 `checks\reviews`，绑定**当前配置、锁文件、对应产物 SHA256**。改台词、offset、源路径、配置或产物会使 review 失效。已有 review 不覆盖；改变方案/产物请用新 attempt 目录。

这是可审计的验收声明，不是身份认证系统；脚本无法判断输入的“用户原话”是否属实。AI 严禁代用户批准。既有样片只回填真实最终验收，不虚构历史 voice/mask 的单独门禁记录。

## 6. 断点、超时和失败处理

- 全工作流执行互斥锁：`workflows\hanli-v1\execution.lock`。异常断电可能留下锁：先核对 PID、任务日志和 ComfyUI queue/history，无活跃所有者且明确确认后才可手工清理。不能按“锁太旧”自动删。
- `job_state.json` 在 HTTP 提交前就写入意图，记录 client_id/graph_hash；收到 prompt_id 才转 submitted。POST 超时或崩溃导致结果不明确时**不自动再 POST**。
- prompt_id 已知的超时/网络中断，使用同一个项目、同一 stage：

```powershell
& $Py $Guard run --project $P --stage render --resume --timeout 900
```

- 等待超时只结束客户端等待，不代表服务器任务失败，也不自动打断别人的 GPU 任务。轮询总预算默认900秒，单次 HTTP 还有30/180秒上限，因此退出时间可能略超预算。
- 无 prompt_id：依据保存的 client_id、提交时间和完整图人工核对 `/queue` 与 `/history`。不能定位就保持 BLOCKED；不得换目录偷偷重复提交。恢复 state 前必须有确切任务匹配证据。
- 历史旧客户端目录有 submission/history 但没有 job_state：可复查，不自动接管/重提。成功样片无需 resume。明确失败才新建 attempt，并在其 purpose 中记前一次 prompt_id、失败原因与获准变更。
- TTS 输出目录、FFmpeg 成片已有就拒绝覆盖。保留部分产物，诊断后在新 attempt 执行；不要删除原输出来“修复”检查。
- 本版只为 ComfyUI 的提交/等待提供断点状态；声音和本地合成不是通用断点引擎。原 worker 的 FFmpeg 调用没有总截止时间；卡住时先查该 PID 与子进程，不能对整机 Python/FFmpeg 批量结束。
- 源素材不同可以重设分割点/裁剪/场景提示词/台词。算不动不能自动降品质；原16fps曾677秒仍停采样，成功10fps渲染约220秒，这是本机一次实测，不是 SLA。

## 7. 服务与依赖恢复

ComfyUI 由 Pinokio/pterm 管理，不在此脚本内直接启动内部 Python。先阅读本机 Pinokio skill，再检查服务状态与队列。8188 已有服务时复用并校验；9881 已被占用时声音 worker 会停止，不杀占用进程。

已用的 ComfyUI launcher：`D:\work\software\pinokio\api\comfyui.pinokio\start_hanli_test.json`；关键启动参数：`--reserve-vram 6 --disable-cuda-malloc --disable-async-offload --disable-pinned-memory`。关键库版本以 lock 内实时冻结值为准，不照网络最新版本升级。

本次锁住列出的文件和四个关键 Python 包版本；不是整个 OS、驱动和所有转依赖的可重建容器。源码新增文件/未列出的第三方包仍可能影响行为。环境有更新时应停用这一验收结论，保留环境快照并新建版本复测，不能只修改版本号通过门禁。

## 8. 给下一位 AI 的交付清单

交付时给出：实际项目目录、源片与截取区间、台词、profile/recipe版本、两次prompt_id、checker报告、成片/对照/联系表、人工审查证据、残留问题、是否等用户 review。明确区分“技术完成”“人工待验”“用户接受但有已知缺陷”。

不要重新采集训练数据：此前16段约55.09秒、239字符及e8结果已经可用。训练入口有硬编码项目路径，不能拿它当新视频生成入口。

自动化回归测试（不会实际提交 GPU 作业）：

```powershell
& $Py 'D:\work\2026 video generation\scripts\test_hanli_guard.py'
```

测试覆盖并发锁、已验收图匹配、参数漂移、非法输入、坏视频、缺失/过期 review、提交超时、未知提交结果、已知任务恢复、队列占用与重复提交防护。完整的真实检查结果见同目录 `HANLI_PIPELINE_CHECK_RESULTS.md`。
