# 韩立 Pipeline 固化验收记录

日期：2026-09-13。控制版本：`hanli-v1-controls-20260913`。

## 本次实际完成

- 保留原 `hanli_reuse_pipeline.py` 的生成算法、e8 权重、参考音频/图像、旧样片和历史归档。
- 增加分阶段执行/检查入口、全图比对、SHA256 锁、人工验收绑定、执行互斥、ComfyUI 提交意图和已知 prompt_id 续等机制。
- 锁文件覆盖 **1,359 个文件，合计 30.54 GiB**，包括相关大模型、核心源码、控制脚本、FFmpeg、参考资产等；另记录 GPT-SoVITS 和 ComfyUI 的 Python 与四个关键库版本。
- `AGENTS.md` 指向唯一交接文档，旧 pipeline 文档顶部也已注明新的执行入口。

## 实测结果

自动测试 **18/18 PASS**。包含真实旧产物检查和离线异常模拟，不向 ComfyUI 提交生成任务。

机器记录：[tests.json](../workflows/hanli-v1/validation/tests.json)。测试代码和 guard 的 SHA 随记录保存。

对已验收项目的完整检查 **8/8 PASS，退出码 0**：

| Checker | 结果 |
| --- | --- |
| lock：全部锁定文件与关键 runtime | PASS |
| project：输入及固定配置 | PASS |
| voice：TTS请求、模型配置、音频格式/时长/信号 | PASS |
| prepared：工作流与输入快照、源视频/渲染输入 | PASS |
| preprocess：成功任务历史及三个输出 | PASS |
| render：成功任务历史及四个输出 | PASS |
| compose：音视频完整解码、帧数/时长、对齐音频字节、最终音轨与非空/非静止采样 | PASS |
| delivery：真实用户验收与当前配置/产物绑定 | PASS |

报告：[check_1789287355390035700.json](../projects/006-hanli-reuse-10s/retry_10fps/checks/check_1789287355390035700.json)，检查开始于 `2026-09-13T08:15:28Z`。

控制锁 SHA256：`d96000f97ec59bb0d4cdb0bf8673ac4f7e4fae4b2a65f6de3754ac285fb8fdae`。

基准成片与根目录交付副本均仍为 SHA256：

`8f2c8933fba9137f0837eff6e6300b217d88134bb197b64b4430d9107079ebbe`

## 开发期间发现和修正

第一轮检查将 DWPose 输出错误地按成片尺寸检查，导致 preprocess/render FAIL。实查显示 mask/person/generated 为640×352，而 DWPose 的短边384模式输出698×384。本次修正的是 checker，并新增针对原始成功产物的测试，**没有改模型、图或成片来迁就检查**。初次失败报告保留在原 checks 目录；最终冻结仅更新本次新控制脚本和测试脚本的校验值。

此前的用户验收原话已追记到 [final.json](../projects/006-hanli-reuse-10s/retry_10fps/checks/reviews/final.json)。它不是本次重新试听，也没有虚构历史 voice/mask 的单独放行记录。保留已知问题：用户报告吞了一个字，具体字和时间点未知，尚未修复。

## 没有做的事

- 没有重新训练、合成声音、渲染新片、启动下载或修改旧归档。
- 首次访问本机8188时连接被拒绝，未擅自启动 ComfyUI。本次完成了离线文件/环境版本和已有产物验证，**没有宣称当前在线环境检查已通过**。下次生成前须执行 `environment`。
- 新控制入口的“未知提交不重提、已知任务恢复”等使用模拟 HTTP 回归验证；没有为了测试而新开真实 GPU 作业。实际服务重启/网络断开时的生产表现仍需下一次授权生成验证。
- 自动检查不能判断声音是否百分之百像、所有字是否清晰、语气是否自然、人物细节是否完美。新项目仍须按交接规范实际试听/看片并由用户最终验收。

后续执行入口：[HANLI_PIPELINE_HANDOFF.md](HANLI_PIPELINE_HANDOFF.md)。
