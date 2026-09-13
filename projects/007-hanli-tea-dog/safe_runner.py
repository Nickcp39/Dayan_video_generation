"""ComfyUI 有界等待与断点恢复。提交不明时保留现场，绝不自动再次 POST。"""
import hashlib, json, pathlib, time, uuid
import requests

def save(p,d): p.write_text(json.dumps(d,ensure_ascii=False,indent=2),encoding='utf-8')
def digest(g): return hashlib.sha256(json.dumps(g,sort_keys=True).encode()).hexdigest()

def run(base,graph,out,timeout=900,resume=False):
    out=pathlib.Path(out);out.mkdir(parents=True,exist_ok=True)
    s=requests.Session();s.trust_env=False
    statefile=out/'job_state.json'; started=time.monotonic()
    if resume:
        if statefile.exists(): state=json.loads(statefile.read_text())
        elif (out/'submission.json').exists():
            state={'prompt_id':json.loads((out/'submission.json').read_text()).get('prompt_id'),'graph_sha256':digest(graph)}
        else: raise RuntimeError('No known submission: inspect queue/history, do not resubmit')
        if state.get('graph_sha256')!=digest(graph) or not state.get('prompt_id'):
            raise RuntimeError('Changed graph or unknown submission; manual reconciliation required')
    else:
        if statefile.exists() or (out/'submission.json').exists():
            raise RuntimeError('Existing submission; use resume for a known prompt ID')
        queue=s.get(base+'/queue',timeout=15);queue.raise_for_status()
        if any(queue.json().get(k) for k in ('queue_running','queue_pending')):
            raise RuntimeError('ComfyUI queue occupied; leave other jobs alone')
        state={'status':'submission_intent','client_id':str(uuid.uuid4()),'graph_sha256':digest(graph),'created_at':time.time()}
        save(out/'workflow_api.json',graph);save(statefile,state)
        r=s.post(base+'/prompt',json={'prompt':graph,'client_id':state['client_id']},timeout=60)
        (out/'submission.json').write_text(r.text,encoding='utf-8');r.raise_for_status()
        state.update(prompt_id=r.json()['prompt_id'],status='submitted');save(statefile,state)
    prompt_id=state['prompt_id'];print('WAIT',prompt_id,flush=True)
    while time.monotonic()-started<timeout:
        r=s.get(base+'/history/'+prompt_id,timeout=30);r.raise_for_status();h=r.json().get(prompt_id)
        if h:
            save(out/'history.json',h)
            if h.get('status',{}).get('status_str')=='error':
                state['status']='failed';save(statefile,state);raise RuntimeError('Comfy execution failed; inspect history')
            if h.get('status',{}).get('completed'):
                files=[]
                for nid,node in h.get('outputs',{}).items():
                    for values in node.values():
                        if not isinstance(values,list):continue
                        for item in values:
                            if not isinstance(item,dict) or 'filename' not in item:continue
                            params={k:item[k] for k in ('filename','subfolder','type') if k in item}
                            r=s.get(base+'/view',params=params,timeout=180);r.raise_for_status()
                            target=out/(nid+'_'+pathlib.Path(item['filename']).name)
                            if target.exists():
                                if target.read_bytes()!=r.content:raise RuntimeError('Existing downloaded artifact differs')
                            else:
                                part=target.with_suffix(target.suffix+'.part');part.write_bytes(r.content);part.replace(target)
                            files.append(str(target))
                if not files:raise RuntimeError('Completed job has no downloadable outputs')
                save(out/'metrics.json',{'prompt_id':prompt_id,'seconds':time.monotonic()-started,'files':files,'resumed':resume})
                state['status']='completed';save(statefile,state);return
        time.sleep(min(5,max(0,timeout-(time.monotonic()-started))))
    state['status']='wait_timeout_server_may_still_run';save(statefile,state)
    raise TimeoutError('Server job not cancelled; resume this same prompt ID')
