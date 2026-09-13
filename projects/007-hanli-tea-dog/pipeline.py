"""独立制片入口：参考资产、分镜制图、图生视频。旧流水线只读。

每一次调用指定唯一名称；保存提示词/工作流/执行证据，已有结果按哈希复用。
"""
import argparse, hashlib, importlib.util, json, pathlib, shutil, sys, time, subprocess, threading
import requests
import safe_runner

SESSION = requests.Session()
SESSION.trust_env = False

P = pathlib.Path(__file__).resolve().parent
ROOT = P.parents[1]
BASE = 'http://127.0.0.1:8188'
sys.stdout.reconfigure(encoding='utf-8')

def js(path, obj):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(obj,ensure_ascii=False,indent=2),encoding='utf-8')

def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for b in iter(lambda:f.read(8*1024*1024),b''): h.update(b)
    return h.hexdigest()

def initialize():
    for d in ['assets','storyboards','renders','workflows','evidence','logs','output']:
        (P/d).mkdir(exist_ok=True)
    paths=[ROOT/'scripts/hanli_reuse_pipeline.py',ROOT/'docs/HANLI_PIPELINE_V1.md',
        ROOT/'projects/004-hanli-voice-finetune/approved_profile_v1.json',ROOT/'projects/006-hanli-reuse-10s/project.json',
        ROOT/'assets/faces/hanli_01.jpg']
    target=P/'evidence/preserved_baseline.json'
    if not target.exists(): js(target,{str(p):sha(p) for p in paths})
    differences=[p for p,h in json.loads(target.read_text()).items() if sha(pathlib.Path(p))!=h]
    js(P/'evidence/baseline_check.json',dict(changed_since_snapshot=differences,note='This pipeline never writes these paths. Report concurrent drift without reverting shared files.'))
    if differences: print('BASELINE DRIFT (left untouched)',differences,flush=True)
    for name in ['hanli_01.jpg','hanli_02.jpg']:
        target=P/'assets'/name
        if not target.exists(): shutil.copy2(ROOT/'assets/faces'/name,target)
    js(P/'evidence/system_stats.json',SESSION.get(BASE+'/system_stats',timeout=30).json())

def upload(path):
    with path.open('rb') as f:
        r=SESSION.post(BASE+'/upload/image',data={'overwrite':'true','subfolder':'007_tea_dog'},files={'image':('007_'+sha(path)[:12]+'_'+path.name,f)},timeout=60)
    r.raise_for_status(); d=r.json()
    return (d.get('subfolder','')+'/'+d['name']).lstrip('/')

def node(t,**inputs): return dict(class_type=t,inputs=inputs)

def sdxl(prompt, width, height, seed):
    # 先用已安装 SDXL 制作环境/道具资产；人物一致性由后续参考编辑处理。
    return {
      '1':node('CheckpointLoaderSimple',ckpt_name='sd_xl_base_1.0.safetensors'),
      '2':node('CLIPTextEncode',clip=['1',1],text=prompt),
      '3':node('CLIPTextEncode',clip=['1',1],text='text, watermark, low quality, blurry, deformed, extra legs, extra paws, duplicate dog, people, person'),
      '4':node('EmptyLatentImage',width=width,height=height,batch_size=1),
      '5':node('KSampler',model=['1',0],positive=['2',0],negative=['3',0],latent_image=['4',0],seed=seed,steps=28,cfg=6.5,sampler_name='dpmpp_2m',scheduler='karras',denoise=1.0),
      '6':node('VAEDecode',samples=['5',0],vae=['1',2]),
      '7':node('SaveImage',images=['6',0],filename_prefix='007_tea_dog/assets'),
    }

def flux(prompt, references, width, height, seed):
    # 对应官方 Klein Distilled 图：文本与参考图 latent → CFG1 → 4步采样。
    g={
      '1':node('UNETLoader',unet_name='007_tea_dog/flux-2-klein-4b-fp8.safetensors',weight_dtype='default'),
      '2':node('CLIPLoader',clip_name='007_tea_dog/qwen_3_4b.safetensors',type='flux2',device='default'),
      '3':node('VAELoader',vae_name='007_tea_dog/flux2-vae.safetensors'),
      '4':node('CLIPTextEncode',clip=['2',0],text=prompt),
      '5':node('ConditioningZeroOut',conditioning=['4',0]),
      '6':node('EmptyFlux2LatentImage',width=width,height=height,batch_size=1),
      '7':node('RandomNoise',noise_seed=seed),
      '8':node('KSamplerSelect',sampler_name='euler'),
      '9':node('Flux2Scheduler',steps=4,width=width,height=height),
      '10':node('CFGGuider',model=['1',0],positive=['4',0],negative=['5',0],cfg=1.0),
      '11':node('SamplerCustomAdvanced',noise=['7',0],guider=['10',0],sampler=['8',0],sigmas=['9',0],latent_image=['6',0]),
      '12':node('VAEDecode',samples=['11',0],vae=['3',0]),
      '13':node('SaveImage',images=['12',0],filename_prefix='007_tea_dog/images'),
    }
    pos,neg=['4',0],['5',0]
    for i,path in enumerate(references):
        n=20+i*5
        g[str(n)]=node('LoadImage',image=upload(path))
        g[str(n+1)]=node('ImageScaleToTotalPixels',image=[str(n),0],upscale_method='lanczos',megapixels=0.6,resolution_steps=1)
        g[str(n+2)]=node('VAEEncode',pixels=[str(n+1),0],vae=['3',0])
        g[str(n+3)]=node('ReferenceLatent',conditioning=pos,latent=[str(n+2),0])
        g[str(n+4)]=node('ReferenceLatent',conditioning=neg,latent=[str(n+2),0])
        pos,neg=[str(n+3),0],[str(n+4),0]
    g['10']['inputs'].update(positive=pos,negative=neg)
    return g

def wan(prompt, image, width, height, seed, steps, frames):
    g=json.loads((pathlib.Path(__file__).resolve().parent/'templates/wan5b_api.json').read_text())
    g['6']['inputs']['text']=prompt
    g['7']['inputs']['text']='text, subtitles, watermark, distorted face, deformed hands, extra fingers, extra limbs, fused hand and cup, duplicate cup, duplicate dog, dog morphing, sudden cut, scene change, flickering, low quality, oversaturated, flat still image'
    g['55']['inputs'].update(width=width,height=height,length=frames,start_image=['60',0])
    g['60']=node('LoadImage',image=upload(image))
    g['3']['inputs'].update(seed=seed,steps=steps,cfg=5.0)
    g['58']['inputs']['filename_prefix']='007_tea_dog/video'
    return g

def execute(g,name,kind,inputs,timeout=900):
    out=P/kind/name
    signature=hashlib.sha256(json.dumps(g,sort_keys=True).encode()).hexdigest()
    if out.exists():
        saved=out/'request.json'
        if saved.exists() and json.loads(saved.read_text())['signature']==signature and (out/'metrics.json').exists():
            print('CACHED',out); return
        raise RuntimeError('Run name already exists. Preserve it and use a new --name; never resubmit a pending prompt blindly.')
    out.mkdir(parents=True)
    js(out/'request.json',dict(signature=signature,inputs=inputs,external_inference_calls=0))
    js(P/'workflows'/(name+'.json'),g)
    objects=SESSION.get(BASE+'/object_info',timeout=30).json()
    assert all(n['class_type'] in objects for n in g.values())
    # 标准路径归一化到运行中服务公布的 Windows 模型名称。
    for n in g.values():
        for field in ('unet_name','clip_name','vae_name'):
            if field in n['inputs']:
                names=objects[n['class_type']]['input']['required'][field][0]
                value=n['inputs'][field]
                match=next((x for x in names if x.replace('\\','/')==value.replace('\\','/')),None)
                if match is None: raise RuntimeError('Required model not yet available: '+value)
                n['inputs'][field]=match
    stop=threading.Event();started=time.monotonic()
    def monitor():
        with (out/'gpu.jsonl').open('w',encoding='utf-8') as log:
            while not stop.is_set():
                r=subprocess.run(['nvidia-smi','--query-gpu=memory.used,utilization.gpu','--format=csv,noheader,nounits'],capture_output=True,text=True,creationflags=subprocess.CREATE_NO_WINDOW)
                log.write(json.dumps(dict(seconds=time.monotonic()-started,total_gpu_memory_and_utilization=r.stdout.strip()))+'\n');log.flush();stop.wait(3)
    thread=threading.Thread(target=monitor,daemon=True);thread.start()
    try: safe_runner.run(BASE,g,out,timeout=timeout)
    finally: stop.set();thread.join(timeout=10)

def main():
    global BASE,P
    p=argparse.ArgumentParser()
    p.add_argument('stage',choices=['init','sdimage','image','video','verify-baseline','resume'])
    p.add_argument('--project',type=pathlib.Path,default=P)
    p.add_argument('--timeout',type=int,default=900)
    p.add_argument('--kind',choices=['storyboards','renders'],default='renders')
    p.add_argument('--base-url',default=BASE)
    p.add_argument('--name'); p.add_argument('--prompt-file',type=pathlib.Path)
    p.add_argument('--ref',action='append',type=pathlib.Path,default=[])
    p.add_argument('--width',type=int,default=960); p.add_argument('--height',type=int,default=544)
    p.add_argument('--seed',type=int,default=2026091307); p.add_argument('--steps',type=int,default=24)
    p.add_argument('--frames',type=int,default=121)
    a=p.parse_args()
    if a.name is not None and (not a.name or pathlib.Path(a.name).name!=a.name or a.name in ('.','..') or '/' in a.name or '\\' in a.name):
        p.error('name must be a single directory name')
    if a.stage not in ('init','verify-baseline') and not a.name:p.error('--name required')
    if a.stage in ('image','sdimage','video') and not a.prompt_file:p.error('--prompt-file required')
    if a.timeout<=0:p.error('--timeout must be positive')
    P=a.project.resolve()
    BASE=a.base_url.rstrip('/')
    if a.stage=='resume':
        out=P/a.kind/a.name
        safe_runner.run(BASE,json.loads((out/'workflow_api.json').read_text()),out,timeout=a.timeout,resume=True);return
    if a.stage in ('init','verify-baseline'): initialize(); return
    prompt=a.prompt_file.read_text(encoding='utf-8')
    inputs=dict(prompt=prompt,references={str(x.resolve()):sha(x) for x in a.ref},width=a.width,height=a.height,seed=a.seed,steps=a.steps,frames=a.frames)
    if a.stage=='sdimage':
        execute(sdxl(prompt,a.width,a.height,a.seed),a.name,'storyboards',inputs,a.timeout)
    elif a.stage=='image':
        execute(flux(prompt,a.ref,a.width,a.height,a.seed),a.name,'storyboards',inputs,a.timeout)
    else:
        assert len(a.ref)==1,'I2V uses one shot-specific starting frame'
        execute(wan(prompt,a.ref[0],a.width,a.height,a.seed,a.steps,a.frames),a.name,'renders',inputs,a.timeout)

if __name__=='__main__': main()
