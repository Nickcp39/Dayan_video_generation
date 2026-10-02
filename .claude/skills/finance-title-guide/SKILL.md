---
name: finance-title-guide
description: 按测试过的财经大V写作指南（小Lin说、Graham Stephan、両学長等 9 个频道），把一个选题、方向或一篇博客变成视频标题候选和中心思想。用户给出选题或博客、想要"像某个大V那样起标题/立论"、或说"用写作指南出标题"时使用。Turns a finance topic or blog post into creator-style video titles and a central thesis using the evaluated per-channel guidelines in research/title-replication.
---

# 按写作指南出标题和中心思想

这套指南来自 `research/title-replication/`：先在训练集上归纳，再用调试集修订，最后在 180 期没见过的视频上做了测试。
测试结果：中心思想有 88% 与原作者方向一致；标题在 22% 的情况下能骗过评审（零样本基线只有 12%）。
所以**标题是候选，最后由用户挑**；中心思想比较可靠。

关键原则：**由指南来写，不由你来写。** 你负责准备中性素材、运行脚本、核对事实；标题和论点必须来自 `write.py` 的输出，不要自己另编。

## 步骤

### 1. 明确输入
- **选题**：用户给的话题或标题。
- **素材**：用户给的博客原文或事实。如果没有，或者涉及利率、价格、规模这类时效性数据，就用 WebSearch 查最新数字，并记下来源。
- **频道**：默认 `cn_xiao_lin_shuo`（小Lin说，中文）。用户想对比时用 `--channels all`。可选频道见 `research/title-replication/channels.json` 中 `replicate: true` 的条目。
- **用户自己的观点**：测试时的输入只有中性事实，论点由指南决定。如果用户坚持要表达自己的观点，就在 facts 末尾加一条「本期要表达的观点：……」，并告诉用户这偏离了测试条件。

### 2. 写中性素材
写入 `research/title-replication/drafts/<英文短名>.json`：

```json
{"topic": "一句中性描述，30 字以内，不带观点", "facts": ["8–15 条事实，每条一句"]}
```

规则与 `research/title-replication/prompts/neutral_brief.md` 相同：只写数据、事件、时间、人物、机制；去掉判断、预测、建议、比喻、口号、设问和广告。数字要和来源一致，不要四舍五入成另一个数。

### 3. 运行
```powershell
cd research/title-replication/pipeline
python write.py ../drafts/<英文短名>.json                  # 只跑小Lin说
python write.py ../drafts/<英文短名>.json --channels all   # 9 个频道
```
结果会打印出来，并保存到 `drafts/<英文短名>.out.json`。所有调用都有缓存，同一份素材重跑不会重复调用模型。

运行失败时：
- `401` 或「未登录」：请用户在自己的终端运行 `claude auth login --claudeai`，在浏览器里点授权。
- 「version too old」：运行 `claude update`，Opus 5.5 需要 CLI 2.1.280 或以上。
- 撞上 Max 额度：等额度恢复后重跑同一条命令。

### 4. 核对后交付
- 把标题和论点里的每个数字、事实和素材逐一对照。例如素材是 1.67%，标题写成"1.6%"，就要指出来并给出修正写法。
- 先给主推频道的结果：标题、另外的候选、中心思想，并用一句话说明用了指南里的哪个公式。
- 跑了多个频道时，用表格对比：频道 | 标题 | 论点取向。
- 有些论点带投资建议，比如"该买美债"，那是在模仿创作者的风格，不是投资建议，要提醒用户。
- 用了网上数据时，最后列出来源链接。

## 相关文件
- 写作指南：`research/title-replication/out/guidelines/<频道>.v2.md`
- 测试报告：`research/title-replication/out/REPORT_test.md`
- 生成提示词：`research/title-replication/prompts/generate.md`（与测试时完全相同）
