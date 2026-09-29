# AI 社交视频调研：现成工具选型

日期：2026-09-28。范围：别人如何用 AI 研究社交内容，以及哪些已有工具可复用。证据等级：项目作者文档、官方产品资料与局部源码审阅；没有安装、登录、运行第三方采集器，也没有验证真实账号采集成功率。

## 结论

无需从零编写扫码登录器。现成方案已经包含登录、会话保存、搜索、作品详情与评论读取。建议先用现有浏览器核对少量页面，再评估小红书专用 MCP；抖音专用工具保留候选。已有 pipeline/checker 负责采样与证据质量，外部工具只作为数据来源，不能自行宣布研究完成。

当前短名单：小红书优先评估 xpzouying/xiaohongshu-mcp；跨平台通用后备为 Microsoft Playwright MCP；抖音本地候选为 juziguai/douyin-mcp-server。MediaCrawler 适合研究其采集架构，但许可和导出字段使其不适合直接当成商业账号调研的默认工具。需要历史趋势与榜单时，再评估有预算的数据服务。

## 别人的实现方式

**浏览器代理。** 用户在浏览器登录，工具保存会话，AI 接着搜索、看主页和抽取页面。Microsoft Playwright MCP 文档提供持久化用户目录与复用浏览器会话的方案；Browser Use 的作者指南也将本地浏览器配置和持久化登录作为路线。它们提供浏览能力，本身不附带投资内容研究口径。[Playwright MCP](https://github.com/microsoft/playwright-mcp#user-profile)、[Browser Use 登录指南](https://browser-use.com/posts/web-agent-authentication)

**平台专用工具。** 将搜索、详情、主页、评论封装成结构化调用，再交给 AI 分类和比较。优点是省去反复点页面；接口返回多少条、是否有下一页、哪些字段缺失仍须检查。[小红书 MCP API](https://github.com/xpzouying/xiaohongshu-mcp/blob/main/docs/API.md)

**数据服务加 AI 分析。** 例如千瓜作者介绍了按关键词找高热笔记、批量解析图文／视频结构、比较达人内容风格的流程。这与我们研究头部表达的目标相近，但属于厂商功能介绍，并非已核验的分析准确率；其曝光、阅读等部分数据被标为预估。[千瓜 AI 功能案例](https://wap.qian-gua.com/Home/ArticleDetail?id=3330)、[预估数据说明](https://qian-gua.com/Home/IndexAnalysisTool)

由此可借鉴的工作链是：登录与取数 → 保留原始结果 → 按规则选高／中／低样本 → 阅读视频和评论 → AI 汇总 → 回查证据。不要从“抓到了标题”直接跳到“已看懂视频风格”。这是本研究的综合建议，不声称是全行业统一标准。

## 工具对照

| 工具 | 作者资料可确认的能力 | 与我们任务的关系 | 本轮结论 |
|---|---|---|---|
| [xiaohongshu-mcp](https://github.com/xpzouying/xiaohongshu-mcp) | Windows 登录程序、搜索筛选、笔记详情、评论、用户主页；Apache-2.0 | 最接近“你扫码，AI 搜索并研究小红书”的需求 | 优先做小规模可用性验证，尚未运行 |
| [Microsoft Playwright MCP](https://github.com/microsoft/playwright-mcp) | 浏览器页面操作、结构化页面读取、持久化登录 | 可跨抖音／小红书／B站看页面；需要逐站操作与提取 | 通用后备，不等于各平台现成爬虫 |
| [juziguai/douyin-mcp-server](https://github.com/juziguai/douyin-mcp-server) | 文档列出扫码、搜索、用户作品、评论、创作者样本分析 | 本地抖音方向功能匹配 | 待验候选；许可证、安装依赖和端到端效果尚未审完 |
| [MediaCrawler](https://github.com/NanmiCoder/MediaCrawler) | 多平台搜索、创作者作品与评论采集、登录态缓存 | 适合了解跨平台采集与输出架构 | 暂不作为默认部署选择 |
| [SocialDataX Douyin MCP](https://github.com/DevinChen2014/douyin-mcp) | 托管接口提供搜索、详情、分页评论／作品和转写 | 可减少本地浏览器维护；需服务 API key | 备选，费用与数据质量未验证；公开仓库不是完整后台源码 |
| [X-MCP](https://github.com/xpzouying/x-mcp) | 浏览器扩展复用登录态，并接远端 MCP | 安装可能较省事，项目偏重创作发布 | 备选，不与纯本地 xiaohongshu-mcp 混称 |
| [千瓜](https://www.qian-gua.com/Home/AllPrice)／[飞瓜](https://www.feigua.cn/) | 达人、内容、榜单等商业分析功能 | 历史表现／行业发现可补公开页面不足 | 暂不购买；先核对样本覆盖、导出与计费 |

小红书 MCP 除读取外也包含发布、评论和互动工具。我们的研究只需要登录状态、搜索、主页、详情与评论读取；选择它不意味着启用发布流程。其 API 明确提供登录二维码接口，可直接给用户扫码，无须重写登录程序。[API 端点与登录说明](https://github.com/xpzouying/xiaohongshu-mcp/blob/main/docs/API.md)

## 核实到的限制

### 小红书：主页读取不等于连续作品已收齐

检视 `user_profile.go`，当前实现组装所选 tab 中已加载的笔记列表；本轮未确认持续滚动／游标翻页能完整取得20条。验收时必须核对数量、置顶和发布时间，不能把返回列表直接标为连续样本。[主页实现](https://github.com/xpzouying/xiaohongshu-mcp/blob/main/xiaohongshu/user_profile.go)

API 文档指出推荐流有些互动字段为空；搜索和详情的字段覆盖不同。空字符串不能变成零。详情评论默认少量返回，扩展读取需显式设置；评论样本量不能凭“接口成功”判断。[字段与评论说明](https://github.com/xpzouying/xiaohongshu-mcp/blob/main/docs/API.md)

### MediaCrawler：许可证和输出要分别审查

当前 LICENSE 是 NON-COMMERCIAL LEARNING LICENSE 1.1，商业使用要求作者书面同意。因此不能因 GitHub 可见就按通用宽松开源许可使用。我们暂列架构参考，不推断当前账号研究已获授权。[许可证原文](https://github.com/NanmiCoder/MediaCrawler/blob/main/LICENSE)

抖音 `core.py` 中存在创作者作品采集路径，说明不只支持单条链接；但要限制实际批量范围。[采集实现](https://github.com/NanmiCoder/MediaCrawler/blob/main/media_platform/douyin/core.py)

更关键的是所读 `store/douyin/__init__.py`：作品输出含赞、藏、评、分享、发布时间与链接，却未见保存播放量、时长；`save_creator()` 当前直接返回，注释说明创作者资料不落库。这是本次读取版本的静态观察，不能外推到其他分支或 Pro 版本。它不能原样满足我们的所有字段。[存储实现](https://github.com/NanmiCoder/MediaCrawler/blob/main/store/douyin/__init__.py)

### 扩展或托管 MCP 不等于纯本地

X-MCP 的接入需要 aredink 服务 token，其隐私政策写明请求参数和操作结果传到服务后台。因此它与自托管小红书 MCP 是两种数据路径，不能只因操作发生在本机浏览器就称全部本地。[X-MCP 接入](https://github.com/xpzouying/x-mcp)、[隐私政策](https://github.com/xpzouying/x-mcp/blob/main/PRIVACY_POLICY.md)

SocialDataX 的公开仓库说明业务后台私有托管，使用 API key，仓库 MIT 许可仅覆盖公开文档／配置。服务不提供用户登录、发帖等账号操作。它是购买数据服务的路线，不能当成免费下载后独立运行的完整采集器。[项目说明](https://github.com/DevinChen2014/douyin-mcp)

## Codex 内置浏览器：纠正此前的停止方式

本次读取的当前 OpenAI 官方 Browser 文档明确允许在独立的内置浏览器配置中登录；已有 Chrome 登录会话则可走浏览器扩展。旧文档镜像有不同描述，本次采用官方当前页面，不沿用镜像。上次 Windows Computer Use 的 URL 识别失败，只能证明那次窗口操作被阻止，不能证明 Codex 内置浏览器无法登录。[官方 Browser 文档](https://learn.chatgpt.com/docs/browser?surface=app)、[官方浏览器扩展说明](https://learn.chatgpt.com/docs/chrome-extension)

本轮当前可调用工具清单未暴露此前使用的内置浏览器控制入口；插件目录搜索也没有返回抖音／小红书专用连接。它们说明当前会话接入未确认，不等于产品不存在该功能。本轮按用户要求只研究工具，没有再次登录、修改浏览器设置或安装插件。

## 接入已有 pipeline 的办法

保留现有抽样设计，另加小型数据适配层即可，不另造登录软件：

1. 工具返回保存为原始 JSON，记录工具版本、来源URL、采集时间、分页／截断／错误状态。
2. 映射成我们的视频台账：作品ID、账号ID、发布时间、时长、各自独立的互动计数。字段缺失存unknown；接口整数不要伪造页面原始显示值。
3. 原始接口结果作为新的证据类型，并与页面抽查相互核对。当前 checker 只把 browser_text/screenshot 当直接证据，尚不能直接接收这些 API 输出；后续应显式扩展类型和字段口径，并增加测试，不把 API JSON 假标成截图来过检。
4. 登录无效、列表为空、分页截断分别记录；任何一种都不自动解释为内容无人看。
5. 按已定规则选高／中／低作品后，结合实际视频、必要的转写与画面抽查分析。标题／ASR不能证明镜头、剪辑或观众动机。

如果进入验证阶段，先限一个账号、20条作品、每条至多10条可见评论，并与网页抽核至少3条；再检查重启后登录是否复用。小样本失败保留原始错误，不以扩大采集或换字段掩盖失败。这只是后续验收方案，本轮没有执行。

## 已完成与未完成

已完成：比较通用浏览器、专用MCP、跨平台采集器、托管数据服务；核对上述主要作者文档和部分源码；定位扫码入口、许可限制、字段缺口和接入方式。

未完成：运行和安全审计第三方工具、版本固定、扫码登录、真实20条连续采样、调用成本验证。本轮结论为“有现成工具可借用，短名单明确”，不是“已部署并采集成功”。
