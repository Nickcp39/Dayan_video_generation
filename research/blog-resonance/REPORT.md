# 什么样的经济和技术博客能引起强烈共鸣

> 2026-10-02。数据：39 个英文经济/技术博客在 Hacker News（HN）上近 20 年的全部提交记录（12,868 篇文章、21,948 次提交）；其中 32 个博客的 107 对"爆款 vs 同作者同期冷门"文章，逐篇盲编码；中文试点为阮一峰博客 2,252 篇文章及其留言数。
> 代码在 `pipeline/`，统计结果在 `out/results.json`。原文和网页只保存在本机的 `data/`。

## 先看结论

在**同一个作者**的文章里比较爆款和冷门，作者名气、文笔和读者群大体被控制住了。剩下的差别主要在下面几处。

1. **情绪强度最关键。** 爆款让人产生的不只是"有点意思"。42 对里爆款的情绪唤醒度更高，只有 10 对相反（p < 0.001）；冷门文章最常见的情绪是平淡的好奇（78/107 篇）。多出来的主要是振奋、愤怒、惊叹和焦虑。
2. **替一群人说话。** 爆款更常替某个群体（程序员、打工人、投资者、父母）说出憋着的话，或者挑战这个群体的自我认同：43 对爆款更强，18 对相反（p = 0.002）。"这说的就是我"的感觉也更强（44 对 22）。
3. **有故事，而且作者自己在故事里。** 爆款更常用叙事（37 对 15）；以作者亲身经历为主体的文章，爆款 12 对、冷门 2 对。经济/理财类里，作者承认自己的失败或恐惧也是显著差别（9 对 1）。
4. **触及人生大事，而不只是手艺本身。** 爆款更常落在工作、家庭、地位、健康上（30 对 13）。冷门更常只讲工具或技术细节。
5. **标题给出判断，而不只是话题。** 冷门标题更常只是一个话题名，比如"Integration and Monopoly"、"The phone screen"（32 对 12，p = 0.004）。在全部 HN 标题里，唯一在各博客内部都稳定的形式特征是**否定句式**：Goodbye、Don't、Will not、Stop 这类（24 个博客爆款更多，7 个相反，p = 0.003）。问句、数字、标题长度、"你"都没有稳定差异。
6. **不起区分作用的维度同样重要。** 实用价值（教你怎么做）、时效性、具体程度、给现象起名字，在爆款和冷门里一样多。这些是好博客的标配，不是爆款的原因。
7. **爆款极度集中。** 36 个博客里，最热的 10% 文章拿走的总点赞占比中位数是 62%，最高 85%。一个作者的影响力基本由少数几篇决定。

这些结论跟已有传播研究基本一致：Berger & Milkman 分析《纽约时报》最多转发的文章，发现惊叹、愤怒、焦虑这类高唤醒情绪传播更广。只有一处不同：在同一作者内部，"实用价值"并不区分爆款和冷门。

## 1. 数据和"火"的定义

**为什么用 HN。** 英文技术和经济博客最大的公共讨论区是 HN，每次提交都有点赞数和评论数，可以通过公开接口完整抓取，不需要登录。同一篇文章被多次提交时，取最高分，评论数累加。Reddit 已经关闭匿名接口。

**名单。** 39 个博客，覆盖技术随笔（Paul Graham、Wait But Why、Joel on Software、Dan Luu 等）、AI（Simon Willison、Karpathy）、科技商业（Stratechery、Eugene Wei）和经济金融（Morgan Housel、Marginal Revolution、Noahpinion、Bits about Money、Matt Stoller、Mr. Money Mustache 等），完整名单在 `blogs.json`。7 个博客凑不出足够的配对：Early Retirement Now 和 JL Collins 在 HN 上几乎没人提交；Damodaran 最高只有 62 分；Howard Marks 的备忘录、Not Boring、Calculated Risk 过 50 分的都不超过 2 篇；rachelbythebay 从本机无法访问。理财博客的读者显然大多不在 HN，这本身也说明 HN 的读者面有局限。

**爆款和冷门怎么配。** 爆款是每个博客 HN 得分最高的几篇（至少 50 分，基本上了首页）；冷门是同一博客中被提交过、但不到 10 分的文章，并且和爆款的首次提交时间相差不超过两年（中位数相差 381 天），因为 HN 的用户量这些年变化很大。技术类博客每个取 3 对，经济金融类取 4 对，避免经济类样本被技术类淹没。最终爆款得分中位数 681 分，冷门中位数 3 分。

**怎么编码。** 每篇文章由 Claude Sonnet 5.5 按一份 24 项编码手册打分。编码时模型看不到作者名、点赞数，也不知道文章属于哪一组，文章顺序也打乱了；文末的读者评论预先切掉，免得评论数量泄露热度。维度来自两套常用框架：Berger & Milkman 的情绪与唤醒度，和 STEPPS（社交货币、情绪、实用价值、故事等）；另外加了群体身份、读者代入感、作者自曝、生活领域、标题承诺等几项。编码手册在 `prompts/code_post.md`。

**编码可靠吗。** 随机抽 30 篇让 Claude Opus 5.5 独立再编一遍。0–2 分的各项两次结果完全一致的比例是 73–93%，差距从未超过 1 分；分类项完全一致的比例是 67–90%，唤醒度最低（67%）。

## 2. 历史最热的文章

技术类前 10（HN 得分）：

| 分数 | 博客 | 标题 | 我的归类 |
|---:|---|---|---|
| 3363 | Simon Willison | Bing: "I will not harm you unless you harm me first" | AI 失控的荒诞截图，好笑又不安 |
| 2282 | antirez | The End of the Redis Adventure | 作者离开自己创造的项目 |
| 2115 | Simon Willison | How to succeed in MrBeast production (Leaked PDF) | 内部手册泄露 |
| 1992 | Paul Graham | Having Kids | 人生大事，坦承恐惧 |
| 1936 | Andrej Karpathy | Microgpt | 大神亲手把复杂东西拆到最小 |
| 1896 | antirez | Redis is open source again | 社区事件 |
| 1859 | Dan Luu | Willingness to look stupid | 说中一种普遍心理 |
| 1740 | Paul Graham | Jessica Livingston | 为被忽视的人正名 |
| 1678 | Dan Abramov | Goodbye, Clean Code | 自我反思，推翻自己信过的东西 |
| 1615 | Dan Luu | We only hire the trendiest | 替被筛掉的人鸣不平 |

经济金融类前 10：

| 分数 | 博客 | 标题 | 我的归类 |
|---:|---|---|---|
| 2450 | Slate Star Codex | I Am Deleting the Blog | 作者遭遇不公（媒体要公开他的真名） |
| 1271 | Bits about Money | Anatomy of a credit card rewards program | 揭开日常事物背后的机制 |
| 1158 | BIG (Matt Stoller) | WeWork and Counterfeit Capitalism | 揭露，愤怒 |
| 1057 | BIG | Amazon Prime inflates prices… | 揭露你每天在付的隐形成本 |
| 1036 | BIG | Judge rules Apple executive lied under oath… | 坏人被抓 |
| 1000 | Slate Star Codex | Heuristics that almost always work | 一个好记的思考框架 |
| 964 | Slate Star Codex | Bullshit Jobs | 普遍的职场体验 |
| 960 | Marginal Revolution | Jake Seliger has died | 悼念 |
| 898 | Slate Star Codex | Still alive | 作者回归 |
| 866 | Slate Star Codex | Statement on New York Times Article | 同一事件的后续 |

最热的文章大致分三类：作者的人生节点（关博客、离开项目、告别、回归），揭露一个"坏人"或制度性的荒谬，以及关于工作、孩子、时间的普遍经验。纯知识讲解很少进入最顶端。

## 3. 内容层面：爆款和同作者冷门差在哪

107 对，每项比较的是同一对内爆款减冷门；"爆款更高/更低"指有多少对爆款得分高于或低于冷门，相等的对不计；p 为双侧符号检验。最后一列是第一次抽样的复核：第一次抽样有一个网址合并错误，修正后重抽，见第 7 节。

| 维度 | 爆款均值 | 冷门均值 | 爆款更高 / 更低 | p | 第一次抽样也显著 |
|---|---:|---:|---:|---:|:---:|
| 情绪唤醒度（低0／中1／高2） | 0.71 | 0.41 | 42 / 10 | <0.001 | 是 |
| 有好奇以外的情绪 | 54% | 26% | 35 / 5 | <0.001 | 是 |
| 非专业读者也读得顺 | 1.48 | 1.24 | 31 / 8 | <0.001 | 否（0.06） |
| 替一个群体说话或挑战其认同 | 0.92 | 0.63 | 43 / 18 | 0.002 | 是 |
| 用故事讲 | 0.59 | 0.33 | 37 / 15 | 0.003 | 是 |
| 标题只是话题名 | 28% | 47% | 12 / 32 | 0.004 | 是 |
| 受众范围（1专家～4几乎任何人） | 2.89 | 2.65 | 30 / 11 | 0.004 | 是 |
| 意外的事实或细节 | 1.21 | 1.04 | 32 / 13 | 0.007 | 是 |
| 转发能让人显得有见识 | 1.36 | 1.21 | 27 / 10 | 0.008 | 否（0.06） |
| "这说的就是我" | 1.09 | 0.83 | 44 / 22 | 0.009 | 是 |
| 以作者亲身经历为主体 | 12% | 3% | 12 / 2 | 0.013 | 是 |
| 触及工作、家庭、地位、健康 | 53% | 37% | 30 / 13 | 0.014 | 是 |
| 作者承认失败、恐惧或弱点 | 0.46 | 0.28 | 24 / 10 | 0.024 | 否（0.08） |
| 容易引发争论 | 1.17 | 1.01 | 34 / 20 | 0.08 | 否 |
| 推翻常识 | 1.11 | 0.98 | 31 / 19 | 0.12 | 否 |
| 给现象起了名字 | 48% | 39% | 27 / 18 | 0.23 | 否 |
| 正文字数（中位数） | 2,259 | 1,534 | 60 / 47 | 0.25 | 是（0.03） |
| 具体程度 | 1.78 | 1.71 | 16 / 10 | 0.33 | 否 |
| 实用价值 | 0.96 | 0.93 | 24 / 23 | 1.0 | 否 |
| 时效性 | 0.73 | 0.73 | 28 / 28 | 1.0 | 否 |

一共检验了 22 项。按最严格的 Bonferroni 校正（p < 0.0023），只剩唤醒度、好奇以外的情绪、易读性和群体身份四项；故事（0.003）在边缘。表里的 p 值是未校正的，应当看作强弱排序，而不是逐项"证实"。

**具体是什么情绪**（107 篇爆款 / 107 篇冷门）：好奇 49/78，振奋 27/13，愤怒 11/6，惊叹 6/1，焦虑 5/1，好笑 5/5，温情 3/2。唤醒度：低 35/63，中 68/44，高 4/0。

**标题承诺了什么**：只说话题 30/50，挑衅或断言 27/18，揭示内幕 13/3，提出一个概念 17/11，回答一个问题 7/15，宣布一件事 9/5。

**技术和经济金融分开看**，方向大体一致，侧重不同：

| | 技术类（57 对） | 经济金融类（50 对） |
|---|---|---|
| 最显著 | 好奇以外的情绪 22/2，唤醒度 25/6，受众范围 18/4，**推翻常识 24/8（p = 0.007）**，社交货币 18/5，易读 14/3，群体身份 26/11 | 唤醒度 17/4，易读 17/5，**触及人生大事 15/4**，好奇以外的情绪 13/3，**作者自曝 9/1**，"这说的就是我" 21/8，意外事实 12/3，故事 18/7 |
| 含义 | 技术读者奖励推翻行业共识、走出技术圈的文章 | 经济读者奖励落到自己的钱、工作、处境上，并且作者自己也有代价的文章 |

## 4. 共鸣从哪里来：六种模式和例子

下面的例子都是同一作者的爆款和冷门对照，分数为 HN 得分。

**① 替一群人说出憋着的话。** Dan Luu《We only hire the trendiest》（1615）说的是招聘只看光鲜履历的荒谬；Julia Evans《Making Hard Things Easy》（1134）说"学技术总觉得自己笨，不是你的问题"；Dan Abramov《Npm Audit: broken by design?》（872）说出了很多开发者想说没说的话；Of Dollars and Data《The Upper Middle Class Trap》（71）和《The Rise of the Forever Renter Class》（154）都比同期的投资技巧文高很多。

**② 作者拿自己的人生下注。** Jeff Atwood《Farewell Stack Exchange》（1233）：为了陪孩子，离开自己创办的公司。Paul Graham《Having Kids》（1992）：坦承生孩子前的恐惧是怎么变成喜悦的。Mr. Money Mustache《I Just Gave Up $4000 Per Month to Keep My Freedom of Speech》（271）。对照组里，同样讲方法、讲道理的文章只有个位数分数。

**③ 有一个具体的"坏人"或制度性荒谬。** Matt Stoller 的爆款几乎全是这一类：WeWork（1158）、Amazon Prime（1057）、McKinsey 一年 300 万美元（781）。Marginal Revolution《"Get Out of Jail Free" Cards in New York》（621）；Bits about Money《Credit card debt collection》（778）。对照很说明问题：Stoller 另一篇同样批评麦肯锡的《Keep McKinsey Away from Biden's Infrastructure Push》只有 6 分。爆款揭露的是一件已经发生、有名有姓有金额的事；冷门是在提政策主张。

**④ 尺度或能力带来的惊叹。** Wait But Why《The Fermi Paradox》（223）和"如果仙女座更亮你会看到什么"（272）；Simon Willison 演示 Gemini 把视频当输入（1136）；Construction Physics《How to build a 50k ton forging press》（451）。

**⑤ 人生大事，压成一句话。** Sam Altman《The days are long but the decades are short》（1163）、Kevin Kelly《Bits of advice I wish I had known》（1109）、Morgan Housel《How I think about debt》（247，核心一句"债务越多，你能承受的人生波动范围越窄"）、Wait But Why《How to Pick Your Life Partner》（362）。

**⑥ 标题直接下判断。** 爆款：《Goodbye, Clean Code》《Please don't learn to code》《This AI Boom Will Also Bust》《Honestly, It's Probably the Phones》。冷门：《Integration and Monopoly》《The phone screen》《Physics and Perception》。

**不起作用的方向。** 同作者的冷门文章一样实用、一样具体、一样会造新词，在经济类里也一样经常推翻常识。这些是这批作者写作的底色，不是爆款和冷门的分界线。

## 5. 中文试点：阮一峰的网络日志

中文博客没有 HN 这样的公共计数，知乎要登录，新浪博客的计数接口已经全部返回 0。所以中文侧只用阮一峰博客自带的留言数做了试点：2,252 篇，去掉每周的链接周刊后 1,770 篇，留言中位数 19 条，最高 442 条。

16 对爆款-冷门（同年发表）的结果和英文方向一致：爆款更常替一群人说话（8 对比 0，p = 0.008），更常让读者觉得"说的就是我"（8 比 1），更少只讲技术细节（0 比 6），更长（15 比 1）；5 篇爆款以愤怒为主，冷门里没有一篇。爆款包括"我的 Google Adsense 帐户被关"（站长们的共同遭遇）、"外挂代练何罪之有？"（为被重判的小人物发声）、"你的命运不是一头骡子"，以及一批教程（React、Flex、OAuth、RSA）。

两点限制：教程下面的留言很多是读者提问，留言数会高估教程的共鸣程度；部分爆款涉及政治议题（谷歌退出中国、中国和津巴布韦），这类内容在国内平台不可用。标题特征在中文样本里没有稳定差异（只有 5 个时期可比，样本太小）。

## 6. 对做视频的含义（推论，未在视频上验证）

这些结论来自博客和 HN 读者。迁移到中文短视频之前，最好用你已有的视频数据检验一遍（见第 8 节）。如果直接借用，按证据强弱排序：

1. **选题先问"这替谁说话"。** 优先选打工人、普通投资者、小老板、父母这类群体正在经历却说不出来的处境，而不是一个知识点。
2. **每条要有一种比好奇更强的情绪**：振奋、愤怒（有具体的人、机构、数字）、惊叹（尺度）、焦虑（处境）。只让人觉得"涨知识"的内容，在冷门里最常见。
3. **用一个人的故事带，最好是讲述者自己付出的代价。** 在经济金融类里，作者承认自己的失败或恐惧，是少数显著的差别之一。
4. **落到钱、工作、家庭、地位上**，而不是停在工具和技术细节。
5. **标题和封面给判断，不给话题名**；可以优先试否定句式。
6. **实用技巧不是卖点，是标配。** 有用但平淡的内容，在同作者的冷门里一样多。

合规提醒：愤怒类内容最容易传播，也最容易出事。指向具体机构或个人的说法必须有可核实的公开事实；政治议题在国内平台不可用。

## 7. 局限

- **HN 读者不代表所有人。** 主要是英语、技术背景的读者；理财博客的真实读者大多不在 HN。分数还受提交时间和首页运气影响：同一篇文章在不同时间提交，结果可能差几十倍（多次提交取最高分，只能部分缓解）。
- **只覆盖被提交过的文章。** 冷门指"提交了但没火"，从没被提交的文章不在样本里。
- **编码由同一家族的模型完成。** Sonnet 和 Opus 的一致度不错，但都是 Claude；隐去了作者名，模型仍可能认出名篇。
- **相关不等于因果。** 同作者、同时期的配对能排除名气和时代，但排除不了选题本身的差别，比如"关博客"这种事件本身就会火。
- **抽样修正过一次。** 第一次抽样时，同一篇文章的 `.htm` 和 `.html` 网址没有合并，导致 Paul Graham 一篇 1,164 分的文章被当成了冷门。修正后冷门样本几乎全部重抽。两次抽样里，唤醒度、情绪、群体身份、故事、标题只给话题、受众范围、意外事实、读者代入、亲身经历、人生领域这 10 项都显著且同向；易读性、社交货币、作者自曝只在修正后的样本里显著（第一次 p 在 0.06–0.08）。
- **中文只是试点。** 只有一个技术博客、16 对，用的是留言数。中文经济类博客缺少公开计数，是本研究最大的缺口。

## 8. 下一步

1. **用视频数据检验。** `title-replication` 已经抓了 9 个财经频道的播放量和字幕。可以用同一份编码手册给每个频道的高播放和低播放视频编码，直接回答"这些规律在财经视频里是否成立"。数据现成，大约一两百次模型调用。
2. **补中文经济类。** 需要知乎、雪球或公众号的数据，都要登录。你可以在内置浏览器里自己登录，我只读页面上可见的计数，不接触密码和 cookie。

## 复现

```powershell
cd research/blog-resonance/pipeline
python b1_hn.py                 # HN 提交记录，按博客聚合（data/hn/，out/hn_summary.json）
python b2_ruanyifeng.py         # 中文试点：阮一峰全部文章和留言数
python b3_sample.py             # 爆款-冷门配对并抓取正文（data/sample.json）
python b3_sample_zh.py          # 中文配对
python b4_code.py               # 盲编码（Claude CLI，结果缓存在 data/llm_cache/）
$env:BR_MODEL="claude-opus-5-5"; python b4b_reliability.py   # 30 篇复编，计算一致度
python b5_analyze.py            # 统计（out/results.json）
```

所有网络和模型调用都有缓存，重跑不会重复下载或计费。编码模型通过环境变量 `BR_MODEL` 切换，并发数用 `BR_WORKERS` 控制。

## 来源

- Berger, J. & Milkman, K. L. (2012). [What Makes Online Content Viral?](https://cssh.northeastern.edu/pandemic-teaching-initiative/wp-content/uploads/sites/43/2020/09/What-Makes-Online-Content-Viral.pdf) *Journal of Marketing Research*.
- Tan, C., Lee, L. & Pang, B. (2014). [The effect of wording on message propagation: Topic- and author-controlled natural experiments on Twitter](https://arxiv.org/pdf/1405.1438). 同作者、同话题对照的设计思路与本研究相同。
- [HN Algolia API](https://hn.algolia.com/api)；各博客原文链接见 `out/results.json` 的 `top_posts` 与 `examples`。
