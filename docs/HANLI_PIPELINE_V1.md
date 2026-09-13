# 韩立角色替换与配音 Pipeline v1

> 接手执行请先读 [HANLI_PIPELINE_HANDOFF.md](HANLI_PIPELINE_HANDOFF.md)。本文件保留研发历史；新控制版固定成功样片的 cut0、ref001、10fps 和完整图，使用 `hanli_guard.py` 分阶段检查与执行。下文的可配置备选和旧直跑命令不再是默认入口。

基线日期：2026-09-13。工作区：`D:\work\2026 video generation`。

## 1. 目标与验收状态

将短视频中的一个成年人物替换为韩立参考形象，再使用自定义中文台词和韩立风格的合成声音，输出约 10 秒本地审片。

用户已经试听并接受当前声音作为“先用起来”的版本，之前明确偏好第八轮模型。用户没有指定六组语气对照中的某一组为唯一最终版本，因此本文件固定**第八轮模型**，参考与分句保留为可配置项。

- 已跑通：参考素材整理、文本音频配对、真实 GPT/SoVITS 微调、声音对照、角色替换、蒙版合成、视频封装和解码检查。
- 声音：暂时验收可用；不是声纹鉴定或真人配音等价质量。
- 画面：买瓜版已出片，存在头发边缘、手部残影和跨镜头脸型变化；新素材仍须逐片审查。
- **未做专用口型同步**。DWPose 面部运动来自原片，不保证匹配新台词每个音节。
- 保留原素材，不自动发布，不自动批量抓取或训练；旧下载任务不属于本流程。

## 2. 分层设计

```text
一次性建立角色资产
韩立参考图片 ----------------------------> 形象资产
公开参考视频 -> 字幕与说话人核查 -> 切片 -> 人声分离
             -> 配对文本 -> 数据检查 -> GPT + SoVITS 微调
             -> 基础/e4/e8试听 -> 第八轮角色声音

每条新视频重复执行
源视频 + 来源记录 -> 选连续镜头 -> 10秒裁切 -> 单人蒙版 SAM2
                                            -> DWPose面部/身体姿态
形象资产 + 原背景 + 蒙版 + 姿态 ------------> Wan2.2-Animate
             -> 蒙版外恢复原片 -> 拼镜头 ---------------------+
角色声音 + 参考句 + 新台词 -> TTS -> 字词检查 -> 原速排入时间轴 --+-> MP4
                                                             -> 解码/抽帧/试听/用户验收
```

角色声音训练和逐条视频生成是两个独立环节。**换视频不用重新训练声音**；只有要改进角色声音时，才另建训练实验。

## 3. 固定资产与目录

| 内容 | 路径，相对工作区 |
|---|---|
| 形象参考 | `assets/faces/hanli_01.jpg` |
| 已接受声音配置 | `projects/004-hanli-voice-finetune/approved_profile_v1.json` |
| GPT 第八轮 | `projects/004-hanli-voice-finetune/weights/hanli_55s_v2-e8.ckpt` |
| SoVITS 第八轮 | `projects/004-hanli-voice-finetune/weights/hanli_55s_v2_e8_s192.pth` |
| 默认参考声音 | `projects/004-hanli-voice-finetune/dataset/wavs/ref001.wav` |
| 备选疑问参考 | `projects/004-hanli-voice-finetune/dataset/wavs/h015.wav` |
| 第一次完整视频实验 | `projects/003-hanli-seller-10s/` |
| 训练和声音实验 | `projects/004-hanli-voice-finetune/` |
| 六组语气对照 | `projects/004-hanli-voice-finetune/output/prosody_20260913/` |
| 新素材复用实验 | `projects/006-hanli-reuse-10s/` |

每条视频独立目录：

```text
project.json                 来源、裁切、坐标、台词、时间轴与角色配置
source/                      原视频，不覆盖
work/original_10s.mp4         归一化原始片段
work/render_input.mp4        16fps生成输入
work/profile_snapshot.json   本次角色参数快照
work/project_snapshot.json   本次视频参数快照
work/input_manifest.json     源视频、参考图、参考声的SHA256
work/preprocess.json         SAM2/DWPose预处理图
work/render.json             完整ComfyUI API图
output/preprocess/           蒙版、人物、姿态和执行记录
output/render/               生成视频、蒙版和执行记录
output/voice/                原始声音、响度版、时间轴声音、API参数和日志
output/hanli_reuse_10s.mp4    最终观看版
output/before_after_10s.mp4  原片/替换左右对照
output/verification.json    解码与媒体元数据
```

配置中的角色路径以工作区为根；每条视频的 source 路径以该项目为根。不是跨机器安装包，迁移时还需要模型、引擎和依赖。

## 4. 今天实际做过的训练

具体片段及文字见 `projects/004-hanli-voice-finetune/dataset/selection.json`，不要凭记忆重新写标注。

- 收集 3 条 B 站素材，最终使用 2 条；排除另一条主要包含其他说话人/动作的素材。
- 原始训练数据是 **16 条、55.0899 秒、239 字符（含标点）**，不是 10 分钟。
- 5.30 秒参考和 5.64 秒测试单独留出，区间与训练集不重叠；字幕与 ASR 辅助核对，未执行声纹鉴定。
- 切出 44.1kHz 原始片段，间隔 0.5 秒拼成 montage，再用 BSRoformer 分离人声；按采样点索引拆回片段，避免重新猜时间。
- 最终训练声：32kHz 单声道，60Hz 高通、统一响度；没有改音高或语速。
- 特征：文字/BERT、CNHuBERT/32k、语义 token 三步，检查每一步是否覆盖全部 16 条。
- 使用整合包中的 **v2**，不是最新版模型。SoVITS batch=4、8 epochs、192 iterations；GPT batch=4、8 epochs；均保存 e4/e8。
- 数据加载器内部重复到 96 个调度项，不是 96 条独立训练样本。
- SoVITS 耗时约 215.3 秒，含显存争用；GPT 成功运行约 41.6 秒。不能当作每次运行的保证时间。
- GPT 第一次因 `num_workers=0` 和 `prefetch_factor` 不兼容失败；隔离配置改为 2 后成功，旧失败日志保留。
- 本地旧版 GPT 调度器把实际学习率写死为 **0.002**；不要把配置中的 lr 数字当作实际生效值。
- 权重有限值、哈希、相对基础权重的参数变化已检查。检查记录：`output/weight_verification.json`。

训练脚本 `scripts/hanli_finetune.py` 的实验目录写死为项目 004，已有检查点会恢复训练。**不要把它直接当成给任意新角色训练的通用入口**，也不要为了换视频重新运行它。

## 5. 配音基线与语气处理

默认参考文字必须精确对应参考音频：

> 元道友见谅，韩某确实没有将后背留给旁人的习惯。

基线参数：seed=42、temperature=0.8、top_k=5、top_p=1、speed_factor=1.0、batch_size=1、parallel_infer=true、repetition_penalty=1.35。

- 短对白默认 `cut0` 整段生成；出现漏句/重复时测试 `cut3` 按中文句号分段，保存两个结果。
- `fragment_interval=0.3` 是补零静音，不是呼吸建模。此前试过 0.18，不能因此宣称情绪更自然。
- 不要直接在台词里加入“[笑]”“[愤怒]”并假设旧接口支持情绪标签。
- 不把 ASR 当作音色或语气评分；“灵石/零食”等同音识别差异需人耳判断。
- 新台词先原速生成，再安排起点和停顿；超过时间窗时缩短台词或重新生成，**禁止默默截断/强行加速**。
- 第一版旧卖瓜声音曾有按句 atempo 拉伸，且最早使用普通 Edge 男声。它们是历史版本，不应误当成当前第八轮训练声音。
- 当前通用复用脚本做整段声音替换，没有自动保留原背景音乐或其他人的对白。多说话人场景需要另外设计分离和混音。

完整对照与研究链接：`projects/004-hanli-voice-finetune/PROSODY_REVIEW_20260913.md`。用户接受的是当前可用程度，不代表每一组参数都通过独立验收。

## 6. 画面基线

- ComfyUI 原生 Wan2.2-Animate 14B FP8。
- `Wan2_2-Animate-14B_fp8_e4m3fn_scaled_KJ.safetensors`。
- `lightx2v_I2V_14B_480p_cfg_step_distill_rank64_bf16.safetensors`，strength=1。
- `WanAnimate_relight_lora_fp16.safetensors`，strength=1。
- `umt5_xxl_fp8_e4m3fn_scaled.safetensors`、`wan_2.1_vae.safetensors`、`clip_vision_h.safetensors`。
- SAM2 `sam2_hiera_base_plus.safetensors`，视频分割；DWPose 提取被选人物的面部及身体，不应把旁人也输入姿态条件。
- 640×352、原生16fps、6 steps、CFG=1、shift=8、Euler/simple、seed=20260913。
- 帧数按 `4n+1` 准备；10 秒生成用 161 帧，输入尾部补一小段末帧，最终裁到精确 10 秒，不用静图循环替代视频生成。
- 连续10秒的161帧在本次新片测试中触发较重的CPU卸载，采样首步过慢，被主动中止；另用10fps/101帧重试成功，客户端耗时220.36秒。不要把“分段16fps可运行”推断成“任意10秒16fps都快”。低帧率重试保持片长，但运动流畅度有所取舍。
- 蒙版扩张16、BlockifyMask16；最终羽化 sigma=2 后 maskedmerge，把蒙版外像素恢复为原片。
- 输出25fps只是帧率转换，不等于额外生成了真实25fps运动。
- 观看版640×384，多出的32像素底栏标注 AI 合成人物及声音；原素材来源另存，不公开冒充原片。

SAM2 点击坐标必须在本次裁切缩放后的图上重新选。不同人物位置、快速运动或剪辑点不可盲目复用旧坐标。单镜头先做；遇到切镜头应分段建图，不能让分割跨镜头乱跟踪。

## 7. 环境与启动

| 用途 | 本机运行时 |
|---|---|
| 常规处理、ASR、Comfy API 客户端 | `.venv-video-test/Scripts/python.exe` |
| GPT-SoVITS 训练/TTS | `GPT-SoVITS-v3lora-20250228/runtime/python.exe` |
| 视频工具 | `tools/ffmpeg-8.1.2-essentials_build/bin/ffmpeg.exe` 与 `ffprobe.exe` |
| ASR | `tools/models/faster-whisper-medium`，CPU int8、4线程 |
| 图像视频推理 | Pinokio 管理的 ComfyUI HTTP API |

TTS 独立本地 API：127.0.0.1:9881，每次使用项目内配置；端口占用则拒绝接管，完成后关闭自己创建的 API。当前 `/control?command=exit` 使用 SIGTERM，退出码15不能独立判定生成失败，要看请求和生成文件。

ComfyUI 通过 Pinokio/pterm 搜索、确认状态并启动。旧启动器可能显示 running 但 HTTP 不通：需检查实际进程、最新日志和 `/system_stats`，不能只看 UI 标记。通过 `/queue` 确认没有其他任务后才恢复失效会话。

本机成功使用过的自定义启动器是 `D:\work\software\pinokio\api\comfyui.pinokio\start_hanli_test.json`，参数 `--reserve-vram 6 --disable-cuda-malloc --disable-async-offload --disable-pinned-memory`，OMP/MKL=4。这是一起调整后的可用组合，未逐项验证因果，不改原启动器。

`pterm run` 的默认选择在本机曾启动 `start.json` 而非期望的自定义脚本。必须复查 `/system_stats` 的 argv；必要时使用 pterm 的明确脚本启动，不绕过启动器直接运行 ComfyUI 内部 Python。Windows 后台启动窗口隐藏。

语音推理结束后再进行重型视频生成，避免两个模型同时占满显存。不要为了腾显存清理未知任务或关闭用户服务。

## 8. 新视频复用步骤

1. 新建项目目录，保留来源链接/标题/原文件，选择约10秒、单主角、少遮挡、少剪辑的片段。
2. 编写 `project.json`：源片起点、裁切滤镜、尺寸、人物正负点击坐标、视觉描述、台词、配音起点、角色 profile。
3. 先生成配音并 ASR/试听；原速时间必须能装入窗口。
4. 启动并确认 ComfyUI；prepare 生成视频、上传输入、验证节点并保存配置快照。
5. 提交 preprocess，抽帧看蒙版是否选中正确人物、姿态是否连续。
6. 提交 render，保存 prompt_id、完整 API 图、history、metrics 和下载的视频。
7. compose 恢复背景、合成新声、加 AI 标注、导出原片对照；解码、抽帧、试听。
8. 用户审片，记录可用/需改动；不要覆盖上一版。

示例命令，在工作区根目录运行；新项目请替换目录。`prepare/voice/compose` 对已有关键输出拒绝覆盖，以下是首次运行顺序，不是让已完成项目重复执行：

```powershell
$env:PYTHONIOENCODING='utf-8'
$project='projects/006-hanli-reuse-10s/retry_10fps'
# 1. 原速配音。不会触发训练。
.\GPT-SoVITS-v3lora-20250228\runtime\python.exe scripts\hanli_reuse_pipeline.py voice --project $project
# 2. 确认ComfyUI可用后准备输入和API图。
.\.venv-video-test\Scripts\python.exe scripts\hanli_reuse_pipeline.py prepare --project $project --base-url http://127.0.0.1:8188
# 3. 预处理，先审查蒙版。
.\.venv-video-test\Scripts\python.exe pinokio_agent\skills\api\comfyui.pinokio\clients\run_graph.py --base-url http://127.0.0.1:8188 --graph "$project/work/preprocess.json" --output-dir "$project/output/preprocess"
# 4. 渲染，等命令完成。
.\.venv-video-test\Scripts\python.exe pinokio_agent\skills\api\comfyui.pinokio\clients\run_graph.py --base-url http://127.0.0.1:8188 --graph "$project/work/render.json" --output-dir "$project/output/render"
# 5. 合成和解码验证。
.\.venv-video-test\Scripts\python.exe scripts\hanli_reuse_pipeline.py compose --project $project
```

复用脚本当前只支持一个连续镜头；多镜头可参考旧 `hanli_seller_test.py` 和 `hanli_seller_compose.py` 的镜头时间轴，但它们包含买瓜片的固定坐标和时刻，不可直接拿来套别的视频。

## 9. 重跑与验收门槛

- 模型：推理前检查 approved_profile 的 GPT/SoVITS SHA256；改变则报错，不静默使用其他权重。已测试正确哈希通过、故意错误的期望哈希被拒绝，未修改真实权重。
- TTS：检查 WAV 非空/可解码、完整台词、参考文本匹配、总时长；未试听不宣称自然度通过。
- 时间轴：配音按源音频字节、起点和总时长生成签名文件，已有相同对齐可复用；已测试重复对齐复用，以及超出时间窗时拒绝生成。早期 `voice_10s.wav` 是旧测试文件，最终以合成 verification 中的 `aligned_voice` 为准。
- 分割：查看首、中、尾及抬手/转头帧；选错人先改坐标，别直接大模型渲染。
- 渲染：提交成功不是生成成功，必须 history completed 且下载到视频。API 断线先查历史 ID，避免重复提交。
- Comfy 客户端会持续轮询，当前没有自动总超时；如果日志长期无推进，先人工诊断再决定停止，不放任无限无人值守。
- 合成：视频/音频约10秒、H.264/AAC、全片解码、非黑屏、不是静图、音量合理、AI标注可见。
- 同一硬件/seed也不保证跨版本位级一致，保留真实输出才是回溯依据。
- 某阶段失败时保存整个失败目录；重试另起命名，不回滚不相关工作。脚本没有全自动断点恢复，不应宣传为一键可靠批处理。
- 优先改台词/参考/镜头；新模型升级、追加训练、专用口型、背景分离分别另做实验。

## 10. 当日历史索引

1. 买瓜10秒角色替换：`projects/003-hanli-seller-10s/README.md`。
2. 短参考零样本克隆：`projects/003-hanli-seller-10s/voice_hanli/README.md`，质量较差，作为历史保留。
3. 55秒实际微调与 e4/e8 对照：`projects/004-hanli-voice-finetune/README.md`。
4. 增加两句台词、六组语气消融：`projects/004-hanli-voice-finetune/PROSODY_REVIEW_20260913.md`。
5. 用户接受当前声音，建立 approved_profile_v1 和本文档。
6. 新三国片段复用：`projects/006-hanli-reuse-10s/README.md`。连续10秒16fps尝试过慢后中止，10fps重试成功；新配音原速5.86秒，最终成片10.000秒、250帧、H.264/AAC，解码和抽帧检查通过。快速转头、眼手细节与口型仍有局限。
7. 用户观看后接受整体效果：“非常好了已经，虽然吞了一个字，但是整体没有任何问题”。声音与新片复用流程据此作为可用基线；漏字具体位置未定位，记录为已知问题，暂不改变模型或参数。

## 11. 基线快照

`releases/hanli-pipeline-v1-20260913/` 保存本次固定的代码、文档、角色配置、形象参考、训练配对音频和第八轮模型副本。复制资产时逐文件核对SHA256，不依靠同名文件判断一致。

此快照不含完整运行环境和Wan等大型基础模型，不是直接拷走即可运行的安装包。新的实验继续在 `projects/` 中进行，不在快照中训练。后续只有明确通过的改进才升为 v2；不要修改本版名称后假装还是同一条基线。

用户对新片的验收在快照创建后补充，原快照保留归档时状态；最新验收以本文及项目006的README为准。
