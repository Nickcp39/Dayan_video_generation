频道：{{channel}}（{{region}}，标题语言：{{lang}}）

下面是这个频道的 {{n}} 条视频标题。每条前面是编号和播放量在本频道的分位（p90 表示比 90% 的视频播放多）。
逐条拆解标题的写法：只分析手法，不评价好坏，不翻译标题。

字段说明：
- template：把标题抽象成句式模板，具体内容换成槽位，功能词、标点、固定标签原样保留。
  槽位只用这几个：[主体] [事件] [数字] [时间] [结论] [设问] [人称动作] [标签]
  例：「一口气了解[主体]」「[主体][事件]，[设问]？」「BREAKING: [主体] Just [事件] - [结论]」「【[标签]】[主体]の[数字]選」
- hooks：这个标题靠什么让人点开，从下列选 1–3 个，最主要的放第一个：
  question 疑问或设问句 ｜ curiosity_gap 故意只说一半、留悬念 ｜ urgency 突发、时效、刚刚 ｜ warning 警告、危机、损失恐惧 ｜
  contrarian 反常识、颠覆认知 ｜ big_number 具体或夸张的数字 ｜ listicle 清单式（N 个理由、3選）｜ personal 作者本人的亲历或行动 ｜
  reveal 揭秘、内幕、真相、背后 ｜ explainer 承诺讲清楚、讲透 ｜ howto_benefit 方法、赚钱、省钱、怎么做 ｜
  conflict 对立、冲突、人物或国家博弈 ｜ prediction 预测、即将发生 ｜ emotion_slang 情绪化口语、夸张形容、粗口 ｜ series_label 固定栏目标签或前后缀
- gap：标题故意不告诉你、要点进去才知道的东西，一句中文；没有就写「无」
- persona：标题的说话人：first_person 我 ｜ we 我们 ｜ you 直呼观众 ｜ third 第三方或事件本身 ｜ none 无主语短语
- register：情绪基调：calm ｜ curious ｜ urgent ｜ alarmed ｜ excited ｜ angry ｜ ironic ｜ playful
- numbers：数字的作用：none ｜ scale 规模冲击 ｜ precision 精确可信 ｜ list 清单条数 ｜ date 日期或期号 ｜ price 价格或收益
- label：固定栏目标签或后缀原文（如「【硬核】」「| Economics Explained」「【お金のニュース】」），没有就填空字符串

标题：
{{titles}}

按编号逐条输出，不要遗漏。
