"""Build a local review page from actual saved artifacts only."""
import html, json, pathlib
P=pathlib.Path(__file__).resolve().parent
def esc(x):return html.escape(str(x),quote=True)
def rel(p):return p.relative_to(P).as_posix()
def cards(folder,ext):
    rows=[]
    for f in sorted((P/folder).rglob(ext)):
        if 'contact' in f.name or f.name=='cup_cutout.png':continue
        m=f.parent/'metrics.json'; timing=''
        if m.exists():timing=f"客户端等待 {json.loads(m.read_text())['seconds']:.1f} 秒（可能含排队与轮询）"
        if f.suffix=='.mp4': media=f'<video controls preload="metadata" src="{esc(rel(f))}"></video>'
        else: media=f'<a href="{esc(rel(f))}" target="_blank"><img loading="lazy" src="{esc(rel(f))}"></a>'
        rows.append(f'<article>{media}<div><b>{esc(f.parent.name)}</b><small>{esc(timing)}</small></div></article>')
    return ''.join(rows) or '<p class="muted">尚未生成。本页只显示实际文件。</p>'
finals=sorted((P/'output').glob('hanli_tea_dog*/*.mp4'))
hero=''.join(f'<video class="hero" controls preload="metadata" src="{esc(rel(f))}"></video><p>{esc(f.stem)}</p>' for f in finals) or '<div class="pending">分镜准备中 · 尚无新成片</div>'
page='''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>韩立 · 一盏怪茶</title><style>
*{box-sizing:border-box}body{margin:0;background:#101917;color:#e6ece5;font:16px/1.75 system-ui,"Microsoft YaHei",sans-serif}main{max-width:1160px;margin:auto;padding:44px 30px}header{border-bottom:1px solid #3a4942;margin-bottom:32px;padding-bottom:25px}h1{font-size:38px;font-weight:600;letter-spacing:.08em;margin:8px 0}h2{font-size:23px;margin-top:42px}p{max-width:860px}.eyebrow{color:#b7c998;font-size:12px;letter-spacing:.18em}.muted,small{color:#a9b7ad}.hero{width:100%;max-height:680px;background:#050807;border-radius:10px}.grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:18px}article{background:#1b2822;border:1px solid #34463c;border-radius:10px;overflow:hidden}article img,article video{width:100%;display:block}article div{padding:12px 18px}small{display:block}a{color:#cfdea9}.flow{padding:18px;background:#1b2822;border-left:3px solid #b7c998}.pending{padding:60px;text-align:center;background:#1b2822}.tag{display:inline-block;border:1px solid #52614d;border-radius:20px;padding:3px 13px;margin-right:8px;font-size:13px}details{margin:18px 0;padding:16px;border:1px solid #34463c}audio{width:100%;max-width:650px}@media(max-width:700px){main{padding:24px 16px}.grid{grid-template-columns:1fr}h1{font-size:29px}}
</style><main><header><div class="eyebrow">LOCAL ANIMATION STUDY / 007</div><h1>韩立 · 一盏怪茶</h1><p>“今天的茶水有股怪味啊，狗狗怎么也没精打采的。”</p><span class="tag">本地 RTX 4090</span><span class="tag">独立生成流程</span><span class="tag">10 秒 / 两镜头</span></header>'''+hero+'''
<p class="flow">角色参考与角度设定 → 场景、人物、道具组合成分镜 → Wan2.2 图生视频 → 动作审查 → 第八轮 SoVITS → 字幕与剪辑</p>
<p class="muted">此实验不使用原视频动作、SAM 蒙版或人物替换。对白采用内心独白处理，未执行精确口型。一次成功出片不代表批量质量已经稳定。</p>
<p>本次视频引擎执行：喝茶 250.9 秒（含加载），抚摸 117.1 秒，合计约 6 分 8 秒；图片准备、下载和人工审查另计。960×544 / 24fps，未超分。抚摸为小幅动作，人物脸型与原作仍有差别。</p>
<h2>角色设定</h2><img style="width:100%;border-radius:10px" src="assets/character_selected_views.png"><p class="muted">从两次生成中选出的正面、三分之四角度与侧面。作为角色设定检查；视频输入的是下面的单镜头首帧。</p>
<h2>前期资产与分镜</h2><p class="muted">保留失败草图和重试。采用 tea_frame_v2 与 dog_frame_selected；其余包含被淘汰的尝试。点击图片可检查原图；具体采用与淘汰原因见实验记录。</p><div class="grid">'''+cards('storyboards','*.png')+'''</div>
<h2>原始动画镜头</h2><div class="grid">'''+cards('renders','*.mp4')+'''</div>
<h2>原速配音</h2><audio controls src="output/voice/dialogue.wav"></audio><p class="muted">已接受的 GPT-SoVITS 第八轮权重；未重新训练。ASR 覆盖原文，细微咬字以试听为准。</p>
<details><summary>制作依据、复跑与执行证据</summary><p><a href="README.md">实验记录</a> · <a href="project.json">本片配置</a> · <a href="pipeline.py">生成入口</a> · <a href="evidence/model_manifest.json">模型来源与校验</a> · <a href="evidence/visual_review.json">视觉审查</a></p><p><a href="https://docs.comfy.org/tutorials/flux/flux-2-klein">ComfyUI Klein 教程</a> · <a href="https://docs.comfy.org/tutorials/video/wan/wan2_2">ComfyUI Wan2.2 教程</a> · <a href="https://help.runwayml.com/hc/en-us/articles/40042718905875-Creating-with-Gen-4-Image-References">Runway 参考资产方法</a></p></details></main></html>'''
(P/'review.html').write_text(page,encoding='utf-8')
print(P/'review.html')
