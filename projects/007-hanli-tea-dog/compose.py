"""两段原生动画剪为10秒；原速台词按自然停顿分开排布，保存验证。"""
import argparse, hashlib, json, pathlib, subprocess, sys, wave
P=pathlib.Path(__file__).resolve().parent; ROOT=P.parents[1]
FF=ROOT/'tools/ffmpeg-8.1.2-essentials_build/bin/ffmpeg.exe'; PROBE=FF.with_name('ffprobe.exe')
sys.stdout.reconfigure(encoding='utf-8')

def run(*args): subprocess.run([str(FF),'-hide_banner','-loglevel','error','-n',*map(str,args)],cwd=P,check=True)
def probe(path): return json.loads(subprocess.check_output([str(PROBE),'-v','error','-show_streams','-show_format','-of','json',str(path)],text=True))
parser=argparse.ArgumentParser(); parser.add_argument('--tea',type=pathlib.Path,required=True);parser.add_argument('--dog',type=pathlib.Path,required=True);parser.add_argument('--name',default='hanli_tea_dog_10s_v1');parser.add_argument('--project',type=pathlib.Path,default=P);a=parser.parse_args()
P=a.project.resolve()
if not a.name or any(c in a.name for c in '/\\:') or a.name in ('.','..'):parser.error('Invalid output name')
cfg=json.loads((P/'project.json').read_text(encoding='utf-8'))
production=json.loads((P/'production.json').read_text(encoding='utf-8'))
assert cfg['seconds']==10 and cfg['fps']==24, 'v1 supports two five-second shots at 24 fps'
split=cfg['voice_split_seconds'];offsets=cfg['voice_offsets']
out=P/'output'/a.name;out.mkdir(exist_ok=False)
voice=P/'output/voice/dialogue.wav'
# ASR将第一句末尾定在1.94秒，第二句从2.96秒开始；2.4秒是中间静音处。
# 保留原始音频，不做变速、变调；二句分别放在喝完茶后和抚摸狗时。
# 直接按 PCM 样本放置两句，避免 FFmpeg asplit/amix 时间戳同步卡住。
with wave.open(str(voice),'rb') as wav:
    channels, sample_width, sample_rate, frames, compression, _ = wav.getparams()
    assert compression == 'NONE'
    raw=wav.readframes(frames)
stride=channels*sample_width
timeline=bytearray(10*sample_rate*stride)
cut=round(split*sample_rate)*stride
assert 0<cut<len(raw) and len(offsets)==2 and offsets[0]>=0
assert offsets[0]+split<=offsets[1], 'Voice segments must not overlap'
for offset, chunk in zip(offsets,(raw[:cut],raw[cut:])):
    start=round(offset*sample_rate)*stride
    assert start+len(chunk)<=len(timeline)
    timeline[start:start+len(chunk)]=chunk
with wave.open(str(out/'voice_timeline.wav'),'wb') as wav:
    wav.setparams((channels,sample_width,sample_rate,0,'NONE','not compressed'))
    wav.writeframes(timeline)
def timestamp(t):
    ms=round(t*1000);return f'{ms//3600000:02}:{ms//60000%60:02}:{ms//1000%60:02},{ms%1000:03}'
srt='\n'.join(f"{i}\n{timestamp(x['start'])} --> {timestamp(x['end'])}\n{x['text']}\n" for i,x in enumerate(production['subtitles'],1))
(out/'dialogue.srt').write_text(srt,encoding='utf-8')
tea,dog=a.tea.resolve(),a.dog.resolve()
metadata=[probe(tea),probe(dog)]
width=metadata[0]['streams'][0]['width'];height=metadata[0]['streams'][0]['height']
assert all(float(m['format']['duration'])>=5 for m in metadata),'Both generated shots must cover five seconds'
sub=f"output/{a.name}/dialogue.srt"
vf=f"[0:v]trim=duration=5,setpts=PTS-STARTPTS,fps=24,setsar=1[a];[1:v]trim=duration=5,setpts=PTS-STARTPTS,fps=24,scale={width}:{height},setsar=1[b];[a][b]concat=n=2:v=1:a=0,subtitles='{sub}':force_style='FontName=Microsoft YaHei,FontSize=20,Outline=1.2,Shadow=0.5,MarginV=18',drawtext=text='AI ANIMATION':fontcolor=white@0.6:fontsize=12:x=16:y=14[v]"
final=out/(a.name+'.mp4')
run('-i',tea,'-i',dog,'-i',out/'voice_timeline.wav','-filter_complex',vf,'-map','[v]','-map','2:a','-t','10','-c:v','libx264','-crf','17','-pix_fmt','yuv420p','-c:a','aac','-b:a','192k','-movflags','+faststart',final)
run('-i',final,'-vf','fps=1,scale=384:-2,tile=5x2','-frames:v','1',out/'contact.jpg')
run('-i',final,'-f','null','-')
m=probe(final); assert abs(float(m['format']['duration'])-10)<0.05
report=dict(final=str(final),sha256=hashlib.sha256(final.read_bytes()).hexdigest(),full_decode='passed',ffprobe=m,source_shots=[str(tea),str(dog)],native_fps=24,upscale=False,audio_speed=1,voice_split_seconds=split,voice_offsets=offsets,dialogue=cfg['voice_text'],lip_sync='No phoneme-level lip sync; dialogue is inner monologue',visual_review='pending')
(out/'verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print(final,flush=True)
