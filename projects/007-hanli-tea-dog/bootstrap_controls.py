"""一次性固化本次已验收样片；拒绝覆盖锁或验收声明。非日常生成入口。"""
import datetime, importlib.util, json, pathlib, sys
P=pathlib.Path(__file__).resolve().parent;ROOT=P.parents[1]
spec=importlib.util.spec_from_file_location('direct',ROOT/'scripts/direct_animation.py');d=importlib.util.module_from_spec(spec);spec.loader.exec_module(d)
recipe=ROOT/'workflows/direct-animation-v1'
if (recipe/'lock.json').exists():raise RuntimeError('Lock already exists; never refresh it to bypass a check')
production=dict(mode='direct-animation',recipe='direct-animation-v1',
    assets=['assets/character_selected_views.png','storyboards/dog_reference_v1/13_images_00002_.png','storyboards/tea_frame_v2/13_images_00005_.png','storyboards/dog_frame_selected/start.png'],
    shots=[dict(id='tea',run='tea_v1',reference='storyboards/tea_frame_v2/13_images_00005_.png',prompt='prompts/tea_video.txt',seconds=5,frames=121,seed=2026091320),
           dict(id='dog',run='dog_v1',reference='storyboards/dog_frame_selected/start.png',prompt='prompts/dog_video.txt',seconds=5,frames=121,seed=2026091321)],
    subtitles=[dict(start=2.1,end=4.5,text='今天的茶水有股怪味啊，'),dict(start=6.4,end=8.6,text='狗狗怎么也没精打采的。')],
    final='output/hanli_tea_dog_10s_v2/hanli_tea_dog_10s_v2.mp4')
d.save(P/'production.json',production)
paths=list(P.glob('*.py'))+list((P/'templates').glob('*.json'))+[ROOT/'scripts/direct_animation.py',ROOT/'scripts/hanli_reuse_pipeline.py',ROOT/'projects/004-hanli-voice-finetune/approved_profile_v1.json']
code={str(x.relative_to(ROOT)):d.sha(x) for x in paths}
deps={}
for x in d.read(P/'evidence/model_manifest.json'):
    p=pathlib.Path(x['target']);h=d.sha(p);d.need(h==x['sha256'],'Image model hash mismatch');deps[str(p)]=h
engine=pathlib.Path('D:/work/software/pinokio/api/comfyui.pinokio/ComfyUI')
for value in ['models/diffusion_models/wan2.2_ti2v_5B_fp16.safetensors','models/text_encoders/umt5_xxl_fp8_e4m3fn_scaled.safetensors','models/vae/wan2.2_vae.safetensors']:
    p=engine/value;deps[str(p)]=d.sha(p)
profile=d.read(ROOT/'projects/004-hanli-voice-finetune/approved_profile_v1.json')
for field in ('gpt_weights','sovits_weights','reference_audio','character_image'):
    p=ROOT/profile[field];deps[str(p)]=d.sha(p)
for p in (d.FF,d.PROBE):deps[str(p)]=d.sha(p)
lock=dict(recipe='direct-animation-v1',created_at=datetime.datetime.now().astimezone().isoformat(),code=code,dependencies=deps,
    baseline=str(P),limits=['Two five-second I2V shots, 960x544, 24fps, 121 frames per raw shot','No phoneme lip sync','Visual/action/voice quality still needs review','Not a complete portable runtime image'])
d.save(recipe/'lock.json',lock)
for kind,who,evidence,issue in [
    ('assets','assistant','前一制作回合已逐张检查角色角度、狗参考、tea_frame_v2 与 dog_frame_selected；多手和道具缺失图已淘汰。','人物外观偏卡通，桌面构图经审查采用。'),
    ('final','user','ok， 彻底通了。 太好了。 虽然图像质量有点卡通。 不知道为啥，但是逻辑是对的','用户接受当前流程和样片；画风偏卡通。已说明小幅抚摸、脸型还原有限和无精确口型。')]:
    d.save(P/'checks/reviews'/f'{kind}.json',dict(kind=kind,reviewer=who,evidence=evidence,known_issue=issue,artifacts=d.review_files(P,kind),recipe_lock_sha256=d.sha(recipe/'lock.json'),time=datetime.datetime.now().astimezone().isoformat()))
print('Frozen code, dependency hashes, selected inputs and actual user acceptance. No separate historical voice approval invented.')
