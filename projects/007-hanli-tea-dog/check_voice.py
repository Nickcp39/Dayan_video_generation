"""本地 ASR 辅助核查台词并保留逐词时间；不替代试听。"""
import json, pathlib, sys
from faster_whisper import WhisperModel
sys.stdout.reconfigure(encoding='utf-8')
P=pathlib.Path(__file__).resolve().parent
ROOT=P.parents[1]
model=WhisperModel(str(ROOT/'tools/models/faster-whisper-medium'),device='cpu',compute_type='int8',cpu_threads=4)
segments,info=model.transcribe(str(P/'output/voice/dialogue.wav'),language='zh',beam_size=5,word_timestamps=True,vad_filter=False)
data=[dict(start=s.start,end=s.end,text=s.text,words=[dict(start=w.start,end=w.end,text=w.word) for w in s.words]) for s in segments]
report=dict(expected='今天的茶水有股怪味啊，狗狗怎么也没精打采的。',segments=data,asr=''.join(s['text'] for s in data),note='ASR only; user listening needed for subtle pronunciation issues')
(P/'output/voice/asr.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(report,ensure_ascii=False),flush=True)
