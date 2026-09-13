"""直接生成模式 v1：两镜头制片的阶段控制与只读 Checker；不改变换皮模式。"""
import argparse, datetime, hashlib, importlib.util, json, os, pathlib, re, shutil, subprocess, sys, wave
from fractions import Fraction
import numpy as np
from PIL import Image
import requests

ROOT=pathlib.Path(__file__).resolve().parents[1]
WORKER=ROOT/'projects/007-hanli-tea-dog'
RECIPE=ROOT/'workflows/direct-animation-v1'
FF=ROOT/'tools/ffmpeg-8.1.2-essentials_build/bin/ffmpeg.exe';PROBE=FF.with_name('ffprobe.exe')
sys.stdout.reconfigure(encoding='utf-8')

class Blocked(RuntimeError):pass
def read(p):return json.loads(p.read_text(encoding='utf-8'))
def save(p,d):
    p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(d,ensure_ascii=False,indent=2),encoding='utf-8')
def sha(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(8*1024*1024),b''):h.update(b)
    return h.hexdigest()
def need(ok,message):
    if not ok:raise ValueError(message)
def local(p,value):
    q=(p/value).resolve()
    need(q.is_relative_to(p.resolve()),'Project path escapes project: '+str(value))
    return q
def name(value):
    need(bool(re.fullmatch(r'[A-Za-z0-9_-]+',value)), 'Use a simple unique directory name')
    return value
def command(args,timeout=120):
    return subprocess.run(list(map(str,args)),check=True,capture_output=True,timeout=timeout)
def norm(text):return ''.join(c for c in text if c.isalnum())
def configs(p):return read(p/'project.json'),read(p/'production.json')
def config_hash(p):
    return hashlib.sha256(((p/'project.json').read_text(encoding='utf-8')+(p/'production.json').read_text(encoding='utf-8')).encode()).hexdigest()

def lock_check(dependencies=False):
    lock=read(RECIPE/'lock.json')
    for value,h in lock['code'].items():need(sha(ROOT/value)==h,'Recipe code changed: '+value)
    if dependencies:
        for value,h in lock['dependencies'].items():need(sha(pathlib.Path(value))==h,'Dependency changed: '+value)
    return {'code_files':len(lock['code']),'dependency_hashes_checked':dependencies}

def project_check(p):
    cfg,pr=configs(p)
    need(pr['mode']=='direct-animation' and pr['recipe']=='direct-animation-v1','Wrong mode/recipe')
    need((cfg['seconds'],cfg['width'],cfg['height'],cfg['fps'],cfg['steps'])==(10,960,544,24,24),'v1 recipe parameters changed; use a new recipe version')
    need(len(pr['shots'])==2 and len(cfg['voice_offsets'])==2,'v1 requires two shots/voice segments')
    need(bool(cfg['voice_text'].strip()),'Empty dialogue')
    need(0<cfg['voice_split_seconds']<10,'Invalid voice split')
    need(0<=cfg['voice_offsets'][0] and cfg['voice_offsets'][0]+cfg['voice_split_seconds']<=cfg['voice_offsets'][1]<10,'Invalid/overlapping voice timeline')
    need(norm(''.join(x['text'] for x in pr['subtitles']))==norm(cfg['voice_text']),'Subtitle text differs from dialogue')
    previous=0
    for x in pr['subtitles']:
        need(previous<=x['start']<x['end']<=10,'Invalid subtitle times');previous=x['end']
    for x in pr['shots']:
        name(x['id']);name(x['run']);need(x['seconds']==5 and x['frames']==121,'Invalid shot length')
        local(p,x['reference']);local(p,x['prompt']);need(isinstance(x['seed'],int),'Missing seed')
    for value in pr['assets']:local(p,value)
    local(p,pr['final'])
    need(cfg['profile']=='projects/004-hanli-voice-finetune/approved_profile_v1.json','v1 voice profile changed')
    return cfg,pr

def review_files(p,kind):
    cfg,pr=configs(p)
    if kind=='assets':files=[p/'project.json',p/'production.json']+[local(p,x) for x in pr['assets']]+[local(p,x['prompt']) for x in pr['shots']]
    elif kind=='voice':files=[p/'project.json',p/'production.json',p/'output/voice/dialogue.wav',p/'output/voice/request.json']
    elif kind=='final':files=[p/'project.json',p/'production.json',local(p,pr['final'])]
    else:raise ValueError('Unknown review kind')
    return {str(x.relative_to(p)):sha(x) for x in files}

def review_check(p,kind):
    target=p/'checks/reviews'/f'{kind}.json'
    if not target.exists():raise Blocked('Missing '+kind+' review; inspect actual artifacts first')
    r=read(target)
    need(r['artifacts']==review_files(p,kind),'Stale '+kind+' review: files/config changed')
    need(r['recipe_lock_sha256']==sha(RECIPE/'lock.json'),'Review refers to a different recipe lock')
    need(bool(r['evidence'].strip()),'Review evidence empty')
    if kind=='final':need(r['reviewer']=='user','Final acceptance must come from the user')
    return r['reviewer']

def assets_check(p):
    cfg,pr=project_check(p)
    for value in pr['assets']:
        f=local(p,value)
        with Image.open(f) as im:im.verify()
    for x in pr['shots']:
        need(local(p,x['reference']).is_file(),'Missing selected frame')
        need(bool(local(p,x['prompt']).read_text(encoding='utf-8').strip()),'Empty motion prompt')
        need(x['reference'] in pr['assets'],'Selected reference missing from reviewed assets')
    review_check(p,'assets')
    return {'selected_assets':len(pr['assets'])}

def pcm(path):
    with wave.open(str(path),'rb') as f:
        need((f.getnchannels(),f.getsampwidth(),f.getframerate())==(1,2,32000),'Expected mono PCM16 32 kHz')
        return f.readframes(f.getnframes())

def voice_check(p):
    cfg,pr=project_check(p);folder=p/'output/voice'
    raw=pcm(folder/'dialogue.wav');a=np.frombuffer(raw,dtype='<i2').astype(float)/32768
    need(len(a)>0 and np.sqrt(np.mean(a*a))>0.001,'Empty or silent voice')
    need(np.mean(np.abs(a)>.999)<.01,'Voice clipping exceeds threshold')
    need(0<cfg['voice_split_seconds']<len(a)/32000,'Split outside voice')
    need(cfg['voice_offsets'][1]+len(a)/32000-cfg['voice_split_seconds']<=10,'Voice would be truncated')
    profile=read(ROOT/cfg['profile']);req=read(folder/'request.json')
    for key,value in profile['generation'].items():need(req.get(key)==value,'Voice parameter changed: '+key)
    need(req['text']==cfg['voice_text'] and req['prompt_text']==profile['reference_text'],'Voice text/reference changed')
    need(pathlib.Path(req['ref_audio_path']).resolve()==(ROOT/profile['reference_audio']).resolve(),'Voice reference file changed')
    for field,hashfield in [('gpt_weights','gpt_sha256'),('sovits_weights','sovits_sha256')]:
        need(sha(ROOT/profile[field])==profile[hashfield],'Voice weights mismatch')
    for value in ('dialogue_raw.wav','dialogue.wav'):command([FF,'-v','error','-xerror','-i',folder/value,'-f','null','-'])
    if (folder/'asr.json').exists():need(norm(read(folder/'asr.json')['asr'])==norm(cfg['voice_text']),'ASR differs: inspect pronunciation, do not silently approve')
    return {'seconds':len(a)/32000,'asr_is_not_human_listening':True}

def media(path,frames,width=960,height=544,audio=False):
    m=json.loads(command([PROBE,'-v','error','-show_format','-show_streams','-of','json',path]).stdout)
    streams=m['streams'];v=next(x for x in streams if x['codec_type']=='video')
    need((v['width'],v['height'],v['codec_name'])==(width,height,'h264'),'Video dimensions/codec wrong')
    need(Fraction(v['avg_frame_rate'])==24 and int(v['nb_frames'])==frames,'Video FPS/frame count wrong')
    need(abs(float(m['format']['duration'])-frames/24)<.08,'Video duration wrong')
    if audio:
        a=next(x for x in streams if x['codec_type']=='audio');need(a['codec_name']=='aac','Expected AAC audio')
    command([FF,'-v','error','-xerror','-i',path,'-f','null','-'])
    b=command([FF,'-v','error','-i',path,'-vf','fps=2,scale=96:54','-f','rawvideo','-pix_fmt','gray','-']).stdout
    a=np.frombuffer(b,dtype=np.uint8).reshape(-1,54,96).astype(float)
    need(len(a)>1 and float(a.std())>3,'Blank or uniform video')
    motion=float(np.abs(np.diff(a,axis=0)).mean());need(motion>.1,'Sampled video appears static')
    return {'frames':frames,'seconds':float(m['format']['duration']),'sampled_motion':motion,'semantic_action_not_automatically_verified':True}

def shot_file(p,shot):
    folder=p/'renders'/shot['run'];metrics=read(folder/'metrics.json')
    files=[folder/pathlib.Path(x).name for x in metrics['files'] if str(x).endswith('.mp4')]
    need(len(files)==1,'Expected one video per shot');return files[0]

def shot_check(p,shot):
    cfg,pr=configs(p);folder=p/'renders'/shot['run']
    g=read(folder/'workflow_api.json');h=read(folder/'history.json');req=read(folder/'request.json')['inputs']
    need(h['status']['completed'] and h['status']['status_str']=='success','Render did not succeed')
    need(h['prompt'][2]==g,'Executed graph differs from saved graph')
    need(read(folder/'submission.json')['prompt_id']==h['prompt'][1]==read(folder/'metrics.json')['prompt_id'],'Prompt IDs differ')
    expected=read(WORKER/'templates/wan5b_api.json')
    expected['6']['inputs']['text']=local(p,shot['prompt']).read_text(encoding='utf-8')
    expected['3']['inputs']['seed']=shot['seed']
    expected['60']['inputs']['image']=g['60']['inputs']['image']
    expected['58']['inputs']['filename_prefix']=g['58']['inputs']['filename_prefix']
    need(g==expected,'Graph differs from approved recipe beyond prompt/seed/input/output name')
    need(req['prompt']==expected['6']['inputs']['text'],'Request prompt changed')
    ref=local(p,shot['reference']);refhash=sha(ref)
    need(list(req['references'].values())==[refhash],'Input reference hash changed')
    need(refhash[:12] in g['60']['inputs']['image'],'Uploaded reference name does not match content hash')
    for k,v in {'width':960,'height':544,'steps':24,'frames':121,'seed':shot['seed']}.items():need(req[k]==v,'Request differs: '+k)
    need(not list(folder.glob('*.part')),'Unfinished download exists')
    return media(shot_file(p,shot),121)

def final_check(p):
    cfg,pr=configs(p);final=local(p,pr['final']);out=final.parent
    result=media(final,240,audio=True);v=read(out/'verification.json')
    need(sha(final)==v['sha256'],'Final SHA mismatch')
    need(v['dialogue']==cfg['voice_text'],'Final dialogue metadata changed')
    need([pathlib.Path(x).name for x in v['source_shots']]==[shot_file(p,x).name for x in pr['shots']],'Composition uses different shots')
    raw=pcm(p/'output/voice/dialogue.wav');aligned=pcm(out/'voice_timeline.wav');expected=bytearray(10*32000*2)
    cut=round(cfg['voice_split_seconds']*32000)*2
    for offset,chunk in zip(cfg['voice_offsets'],(raw[:cut],raw[cut:])):
        start=round(offset*32000)*2;need(start+len(chunk)<=len(expected),'Audio overflows timeline');expected[start:start+len(chunk)]=chunk
    need(bytes(expected)==aligned,'Voice changed, overlapped, truncated, or placed at wrong time')
    decoded=command([FF,'-v','error','-i',final,'-vn','-ar','32000','-ac','1','-f','s16le','-']).stdout
    a=np.frombuffer(aligned,dtype='<i2').astype(float);b=np.frombuffer(decoded,dtype='<i2').astype(float)[:len(a)]
    need(len(a)==len(b),'Final audio too short');corr=float(np.corrcoef(a,b)[0,1]);need(corr>.98,'Final audio does not match approved timeline')
    subtitles=(out/'dialogue.srt').read_text(encoding='utf-8')
    for x in pr['subtitles']:need(x['text'] in subtitles,'Missing subtitle text')
    result['audio_correlation']=corr
    # 字幕/角标以外的画面应来自指定原始镜头，避免只验证了音轨和容器。
    def pixels(path,start):
        b=command([FF,'-v','error','-ss',start,'-i',path,'-frames:v','1','-vf','crop=iw:ih*0.7:0:ih*0.1,scale=160:64','-pix_fmt','gray','-f','rawvideo','-']).stdout
        return np.frombuffer(b,dtype=np.uint8).astype(float)
    correlations=[]
    for i,x in enumerate(pr['shots']):
        for t in (1,3):
            a=pixels(shot_file(p,x),t);b=pixels(final,i*5+t)
            c=float(np.corrcoef(a,b)[0,1]);need(c>.98,'Final frames do not match selected shots/order');correlations.append(c)
    result['source_frame_correlations']=correlations
    return result

def environment(base):
    s=requests.Session();s.trust_env=False
    r=s.get(base.rstrip('/')+'/system_stats',timeout=15);r.raise_for_status();current=r.json()
    expected=read(WORKER/'evidence/system_stats.json')
    for key in ('comfyui_version','pytorch_version'):
        if key in expected['system']:need(current['system'].get(key)==expected['system'][key],'Environment version drift: '+key)
    for arg in ('--reserve-vram','--disable-cuda-malloc','--disable-async-offload','--disable-pinned-memory'):
        need(arg in current['system']['argv'],'Missing launch option '+arg)
    q=s.get(base.rstrip('/')+'/queue',timeout=15);q.raise_for_status()
    if any(q.json().get(k) for k in ('queue_running','queue_pending')):raise Blocked('ComfyUI queue occupied')
    return {'version':current['system']['comfyui_version'],'queue_empty':True}

def check(p,stage='all',dependencies=False):
    results={};error=None
    steps=[('recipe',lambda:lock_check(dependencies)),('project',lambda:project_check(p) and 'valid')]
    if stage in ('assets','renders','final','all'):steps.append(('assets',lambda:assets_check(p)))
    if stage in ('voice','final','all'):steps.append(('voice',lambda:voice_check(p)))
    if stage in ('renders','final','all'):steps.append(('renders',lambda:{x['id']:shot_check(p,x) for x in configs(p)[1]['shots']}))
    if stage in ('final','all'):steps.append(('final',lambda:final_check(p)))
    if stage=='all':steps.append(('user_acceptance',lambda:review_check(p,'final')))
    status='PASS'
    for key,fn in steps:
        try:results[key]=fn()
        except Exception as e:
            status='BLOCKED' if isinstance(e,Blocked) else 'FAIL';error=f'{key}: {e}';break
    report={'status':status,'stage':stage,'checks':results,'error':error,'time':datetime.datetime.now().astimezone().isoformat()}
    target=p/'checks'/('check_'+datetime.datetime.now().strftime('%Y%m%d_%H%M%S_%f')+'.json');save(target,report)
    print(status,str(target),error or '',flush=True)
    return report

def run_stage(a,p):
    cfg,pr=project_check(p)
    need(p!=WORKER,'Accepted sample is read-only for execution; create a new project')
    lock_check(True)
    lock=RECIPE/'execution.lock';lock.parent.mkdir(parents=True,exist_ok=True)
    try:fd=os.open(lock,os.O_CREAT|os.O_EXCL|os.O_WRONLY)
    except FileExistsError:raise Blocked('Execution lock exists; inspect owner/job before any cleanup')
    os.write(fd,str(os.getpid()).encode());os.close(fd)
    try:
        if a.stage=='voice':
            spec=importlib.util.spec_from_file_location('voice_worker',ROOT/'scripts/hanli_reuse_pipeline.py');w=importlib.util.module_from_spec(spec);spec.loader.exec_module(w)
            profile=read(ROOT/cfg['profile']);w.verify_profile(profile);w.voice(p,{**cfg,'voice_offset':0},profile)
        elif a.stage=='render':
            assets_check(p)
            environment(a.base_url)
            shot=next(x for x in pr['shots'] if x['id']==a.shot)
            args=[sys.executable,WORKER/'pipeline.py','resume' if a.resume else 'video','--project',p,'--name',shot['run'],'--base-url',a.base_url,'--timeout',a.timeout]
            if not a.resume:args+=['--ref',local(p,shot['reference']),'--prompt-file',local(p,shot['prompt']),'--seed',shot['seed']]
            subprocess.run(list(map(str,args)),check=True)
            shot_check(p,shot)
        elif a.stage=='compose':
            r=check(p,'final' if local(p,pr['final']).exists() else 'renders')
            need(r['status']=='PASS','Render checks must pass before composition');voice_check(p);review_check(p,'voice')
            out=local(p,pr['final']);need(out.stem==out.parent.name,'Final name must match output folder')
            subprocess.run(list(map(str,[sys.executable,WORKER/'compose.py','--project',p,'--tea',shot_file(p,pr['shots'][0]),'--dog',shot_file(p,pr['shots'][1]),'--name',out.stem])),check=True,timeout=180)
        r=check(p,{'voice':'voice','render':'project','compose':'final'}[a.stage]);need(r['status']=='PASS','Post-stage checker failed')
    finally:lock.unlink()

def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('command',choices=['check','plan','new','review','run'])
    ap.add_argument('--project',type=pathlib.Path,required=True)
    ap.add_argument('--stage',default='all');ap.add_argument('--dependencies',action='store_true')
    ap.add_argument('--kind',choices=['assets','voice','final']);ap.add_argument('--reviewer');ap.add_argument('--evidence');ap.add_argument('--known-issue',default='')
    ap.add_argument('--shot');ap.add_argument('--resume',action='store_true');ap.add_argument('--base-url',default='http://127.0.0.1:8188');ap.add_argument('--timeout',type=int,default=900)
    a=ap.parse_args();p=a.project.resolve()
    try:
        if a.command=='new':
            need(p.is_relative_to(ROOT/'projects') and p!=ROOT/'projects','New project must be inside workspace projects');need(not p.exists(),'Project already exists')
            p.mkdir(parents=True)
            for f in ['project.json','production.json']:shutil.copy2(WORKER/f,p/f)
            for folder in ('assets','prompts'):shutil.copytree(WORKER/folder,p/folder)
            cfg,pr=configs(p);cfg['id']=p.name;save(p/'project.json',cfg)
            for x in pr['assets']:
                dest=local(p,x)
                if not dest.exists():dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(WORKER/x,dest)
            for d in ('renders','workflows','evidence','logs','output'):(p/d).mkdir(exist_ok=True)
            print('Created draft; edit project.json, production.json and references; no outputs/reviews copied:',p)
        elif a.command=='plan':
            cfg,pr=project_check(p);print(json.dumps({'project':str(p),'dialogue':cfg['voice_text'],'shots':pr['shots'],'final':pr['final'],'order':['assets/review','voice/review','render per shot','compose','final check','user review','all check']},ensure_ascii=False,indent=2))
        elif a.command=='review':
            need(a.kind and a.reviewer and a.evidence,'kind/reviewer/evidence required')
            if a.kind=='final':need(a.reviewer=='user','Only actual user acceptance can authorize final review')
            target=p/'checks/reviews'/f'{a.kind}.json';need(not target.exists(),'Review already exists; do not overwrite history')
            save(target,dict(kind=a.kind,reviewer=a.reviewer,evidence=a.evidence,known_issue=a.known_issue,artifacts=review_files(p,a.kind),recipe_lock_sha256=sha(RECIPE/'lock.json'),time=datetime.datetime.now().astimezone().isoformat()))
            print(target)
        elif a.command=='run':
            need(a.stage in ('voice','render','compose'),'run stage must be voice/render/compose');need(a.timeout>0,'Positive timeout required');run_stage(a,p)
        else:
            need(a.stage in ('project','assets','voice','renders','final','all'),'Unknown check stage')
            r=check(p,a.stage,a.dependencies);return {'PASS':0,'FAIL':1,'BLOCKED':2}[r['status']]
    except Exception as e:
        print(('BLOCKED' if isinstance(e,Blocked) else 'FAIL')+': '+str(e));return 2 if isinstance(e,Blocked) else 1
    return 0
if __name__=='__main__':sys.exit(main())
