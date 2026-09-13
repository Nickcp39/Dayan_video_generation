"""汇总已完成运行的时间、采样审查与音频时间轴校验，不重新推理。"""
import datetime, json, pathlib, wave
import requests

P=pathlib.Path(__file__).resolve().parent
def read(p): return json.loads(p.read_text(encoding='utf-8'))
def save(p,data): p.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
s=requests.Session();s.trust_env=False
results={}
reviews={
    'tea_v1': 'Sampled every 0.5 seconds: cup rises to lips, is held for a sip, and lowers near the end; character and dog remain coherent. Fine face detail softens during motion.',
    'dog_v1': 'Sampled every 0.5 seconds: hand moves from forehead toward ear/side of head; dog stays sleepy. A gentle stroke is visible, but not two distinct complete back-and-forth strokes.'
}
for name in reviews:
    folder=P/'renders'/name; metrics=read(folder/'metrics.json')
    j=s.get('http://127.0.0.1:8188/api/jobs/'+metrics['prompt_id'],timeout=15).json()
    times={k:j[k] for k in ['status','create_time','execution_start_time','execution_end_time']}
    samples=[json.loads(line) for line in (folder/'gpu.jsonl').read_text().splitlines()]
    memory=[]
    for row in samples:
        try: memory.append(int(row['total_gpu_memory_and_utilization'].split(',')[0]))
        except (KeyError,ValueError): pass
    results[name]=dict(prompt_id=metrics['prompt_id'], **times,
        execution_seconds=(j['execution_end_time']-j['execution_start_time'])/1000,
        queue_seconds=(j['execution_start_time']-j['create_time'])/1000,
        client_wait_seconds=metrics['seconds'],
        sampled_peak_total_device_memory_mib=max(memory) if memory else None,
        memory_note='Total device use sampled every 3 seconds; includes other processes and queue time, not isolated model allocation.',
        visual_review=reviews[name])
save(P/'evidence/render_summary.json',results)
visual=read(P/'evidence/visual_review.json')
for name,reason in reviews.items(): visual[name]=dict(decision='accept_for_this_clip',reason=reason)
visual['final_v2']=dict(decision='ready_for_user_review',method='Raw clips sampled at 2 fps, final sampled at 1 fps; complete FFmpeg decode and metadata checks.',
    findings='Readable Chinese subtitles, both requested actions visible, coherent setting. Cut at 5 seconds omits cup placement; no phoneme lip sync. Subject likeness remains a generated interpretation.')
save(P/'evidence/visual_review.json',visual)
out=P/'output/hanli_tea_dog_10s_v2'; v=read(out/'verification.json')
with wave.open(str(P/'output/voice/dialogue.wav'),'rb') as f:
    sr=f.getframerate(); stride=f.getnchannels()*f.getsampwidth(); raw=f.readframes(f.getnframes())
with wave.open(str(out/'voice_timeline.wav'),'rb') as f: aligned=f.readframes(f.getnframes())
cut=round(2.4*sr)*stride
for offset,chunk in ((2.1,raw[:cut]),(5.9,raw[cut:])):
    start=round(offset*sr)*stride
    assert aligned[start:start+len(chunk)]==chunk, 'Voice samples must remain unchanged'
assert len(aligned)==10*sr*stride
v['visual_review']=visual['final_v2'];v['pcm_timeline_validation']='passed: both source chunks preserved byte for byte at requested offsets; 10 seconds total'
save(out/'verification.json',v)
status=read(P/'evidence/status.json')
status.update(updated_at=datetime.datetime.now().astimezone().isoformat(),phase='ready_for_user_review',video_completed=True,
    final_video=str(out/'hanli_tea_dog_10s_v2.mp4'),batch_stability_proven=False,
    composition_retry='v1 FFmpeg split/mix graph stalled; terminated only its own process. v2 uses deterministic PCM placement and passed complete decode.')
save(P/'evidence/status.json',status)
print(json.dumps(results,ensure_ascii=False,indent=2))
