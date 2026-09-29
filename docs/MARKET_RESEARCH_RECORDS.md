# 市场研究记录字段

`data.json` 含七个数组：discoveries、creators、videos、analyses、claims、reviews、evidence。所有记录均有唯一字符串id。下面是填写说明，尖括号内容不是已采集事实，也不能直接作为有效数据导入。

## evidence

通过 pipeline 的 evidence 子命令登记。字段：id、url、observed_at（ISO时间含时区）、method（browser_text/screenshot/search_snippet/analyst_note）、label、path（批次内相对路径）、sha256。browser_text 必须来自本次实际可见页面，不得把研究者回忆改标成原始页面。可手动概括的线索标 analyst_note。

## discoveries

```json
{"id":"d1","query":"投资","sort":"popular","url":"<实际搜索URL>","observed_at":"<时间>","evidence_ids":["<id>"],"actual_sort_label":"最多播放","results":[{"rank":1,"url":"<结果URL>","creator_id":"<已登记账号id，误命中可为null>","reason":"<纳入／排除理由>"}],"exhausted":false,"exhaustion_reason":""}
```

同一query/sort只有一条，分次采集追加results。排序和result顺序不得事后挑选。平台未提供排序时，在STATUS登记阻塞，不能伪造搜索完成。来源链接中的登录token等敏感参数不复制到公开报告。

## creators

```json
{"id":"c1","platform":"bilibili","name":"<实际昵称>","url":"<主页>","role":"head","decision":"candidate","reason":"<选择理由与相对头部判断依据>","current_followers":{"value":null,"raw":null,"precision":"unknown","reason":"<不可见原因>"},"evidence_ids":["<主页证据>"],"listing":{"sort":"newest","exclude_pinned":true,"video_ids":[],"evidence_ids":[],"excluded_items":[],"exhausted":false,"exhaustion_reason":""}}
```

role为head/peer/unclassified；decision为candidate/selected/excluded。尚未查看列表时可不填listing；选择为selected后缺listing会被阻塞。excluded_items记录太新、太旧、置顶重复等实际排除项与理由。current_followers仅表示观察时粉丝。

## videos

```json
{"id":"v1","creator_id":"c1","url":"<作品链接>","title":"<原标题>","published_at":"<含时区时间>","observed_at":"<含时区时间>","duration_seconds":null,"duration_missing_reason":"<未取得时长原因>","language":"zh","format":"unknown","topic":"unknown","topic_reason":"<实际分类依据>","metrics":{"views":{"value":null,"raw":null,"precision":"unknown","reason":"未公开"},"likes":{"value":null,"raw":null,"precision":"unknown","reason":"尚未读取"},"comments":{"value":null,"raw":null,"precision":"unknown","reason":"尚未读取"},"favorites":{"value":null,"raw":null,"precision":"unknown","reason":"尚未读取"},"shares":{"value":null,"raw":null,"precision":"unknown","reason":"尚未读取"}},"evidence_ids":["<详情页证据>"]}
```

format：original_talking_head/original_explainer/reposted_clip/other/unknown。topic：investment_principle/personal_finance/decision_psychology/market_news/other/unknown。图文使用other，不能填写虚构时长。只有发布日期而无时分时，在额外字段date_precision填day，并在局限说明日期分辨率；不要把发布时刻00:56当作56秒时长。日期精度在14天边界不确定时先不计入核心。

计数例：`{"value":156000,"raw":"15.6万","precision":"rounded","reason":"页面按万取整展示"}`。不支持的显示格式先登记缺失并保留原始证据，不能猜数。

## analyses

每个被checker选中的作品一条。字段id、video_id、evidence_ids，以及非空文字字段：audience_need_hypothesis、hook、structure、delivery、visuals、credibility、learnable_method、our_possible_contribution、do_not_copy、limitations。

comments对象包含status、sort、items（匿名评论概括的字符串数组）、missing_reason、evidence_ids。status为available/disabled/login_required/none/unavailable。不可见的评论不填假样本；可见不足10条说明原因。意见比例仅限本次可见样本，不能外推人群。

## claims

```json
{"id":"cl1","type":"hypothesis","scope":"style_comparison","text":"<待验证判断>","video_ids":["v1"],"evidence_ids":["<id>"],"limitation":"<可比性／数据限制>","next_evidence_needed":"<怎样验证或推翻>"}
```

type：observation/hypothesis/unknown。scope：sample_description/style_comparison/content_demand/causality/audience_profile/follower_conversion/market_ranking。后四项不能标为observation；公开样本不支持该强度的结论。观察必须有直接证据，假设／未知必须写还需什么证据。

## reviews

```json
{"id":"review1","kind":"content","target":"v1","binding_hash":"<binding命令给出的当前哈希>","decision":"accepted","reviewer_role":"agent","reviewer":"<真实复核者>","notes":"<实际核验内容与局限>","reviewed_at":"<真实复核时间>","basis":"full_watch"}
```

kind/target：selection/all；sampling/账号id；content/作品id；synthesis/all。只有实际完整观看才填full_watch。脚本没有生成通过复核的功能。用户未审阅时不得写human或用户已批准。选择复核需确认候选来源和相对头部依据；采样复核需确认连续性；综合复核需确认推断强度、评论代表性限制、原创增量与不可照搬部分。

先完成证据，再按selection→sampling→content→synthesis顺序复核。更新数据后重新看checker，不能复制旧绑定值骗过过期检查。
