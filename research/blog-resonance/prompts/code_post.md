下面是一篇英文或中文博客文章。你不知道作者是谁，也不知道它受不受欢迎；请只根据文本本身编码，即使认出了文章也不要据此判断。

标题：{{title}}
正文（过长时中间已省略）：
<<<
{{text}}
>>>

按下列维度逐项判断。分数项只用 0、1、2：0 = 基本没有，1 = 有但不是重点，2 = 是这篇文章的核心特征。自由文本字段用中文。

- post_type：文章类型。essay_argument 论证型随笔 ｜ personal_story 个人经历叙事 ｜ tutorial_howto 教程或操作指南 ｜ data_analysis 数据或实证分析 ｜ explainer 解释一个机制或概念 ｜ commentary_news 对新闻或事件的评论 ｜ announcement 产品、项目或个人公告 ｜ list_links 链接汇总或清单 ｜ other
- core_claim：作者最想让读者相信或记住的那一个判断，60 字以内。没有明确论点就写「无」。
- audience_scope：能读懂并产生共鸣的人有多广。1 = 只有该领域专家；2 = 该领域从业者；3 = 受过教育的普通读者；4 = 几乎任何人（普遍的人生经验）。
- life_domains：触及读者生活的哪些部分，选 1–2 个：career_work 工作职业 ｜ money 钱 ｜ family_relationships 家庭关系 ｜ health_aging 健康衰老 ｜ learning_thinking 学习与思考方式 ｜ status_identity 身份地位 ｜ society_politics 社会政治 ｜ tech_tools 技术工具本身 ｜ craft_expertise 专业手艺本身
- reader_mirror：读者会不会觉得"这说的就是我"（描述了读者自己的经历、处境或隐约感受）。
- named_concept：文章是否给一个读者模糊感受过、但说不出来的现象起了名字，或提出了一个好记的思考框架（例如 "Maker's Schedule"、"Bus Ticket Theory"）。填那个名字或短语原文；产品名、项目名、数据集名、人名、文章话题本身都不算，没有就填空字符串。
- contrarian：是否推翻了常识或读者原有的看法。
- surprise：是否包含让人意外的事实、数据或细节。
- emotion：读完最主要的情绪。awe 惊叹敬畏 ｜ anxiety 焦虑担忧 ｜ anger 愤怒不平 ｜ amusement 好笑 ｜ inspiration 振奋希望 ｜ tenderness 温情怀旧 ｜ sadness 悲伤 ｜ curiosity 好奇求知 ｜ none 平淡
- arousal：情绪唤醒度 low ｜ medium ｜ high
- valence：情绪方向 positive ｜ negative ｜ mixed ｜ neutral
- practical_value：读者能不能拿去直接用（方法、建议、决策规则）。
- social_currency：转发它能不能让转发者显得有见识、有品味或是内行。
- identity：是否替某个群体（程序员、创业者、投资者、父母等）说话，或挑战这个群体的自我认同。
- narrative：是否用故事讲（有人物、有经过、有转折）。
- vulnerability：作者是否承认自己的失败、恐惧、错误或弱点。
- authority：作者凭什么让人信。personal_experience 亲身经历 ｜ data_research 数据研究 ｜ insider_access 内部视角 ｜ reasoning 纯推理 ｜ aggregation 汇总他人观点
- concreteness：具体例子、数字、场景的密度。
- debate：是否容易引发争论或站队。
- timeliness：是否依赖当时的新闻热点。0 = 常青内容。
- accessibility：没有专业背景的人读起来是否顺畅。
- opening：开头怎么抓人。question 提问 ｜ scene 场景或故事 ｜ bold_claim 断言 ｜ surprising_fact 意外事实 ｜ context 背景铺垫 ｜ none 直接进入正文
- title_promise：标题承诺了什么。answer 回答一个问题 ｜ reveal 揭示内幕或真相 ｜ instruct 教你怎么做 ｜ name_concept 给出一个概念 ｜ provoke 挑衅或断言 ｜ topic 只说话题 ｜ announce 宣布一件事
- share_reason：如果有读者转发了它，最可能的理由，40 字以内。
