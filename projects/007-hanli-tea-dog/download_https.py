"""Resume bounded model ranges using persistent verified-TLS requests sessions."""
import argparse, concurrent.futures, hashlib, json, pathlib, re, threading, time
import requests
p=argparse.ArgumentParser()
for name in ('url','target','sha256'):p.add_argument('--'+name,required=True)
p.add_argument('--bytes',type=int,required=True);p.add_argument('--workers',type=int,default=12)
a=p.parse_args();target=pathlib.Path(a.target);target.parent.mkdir(parents=True,exist_ok=True)
def digest(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for b in iter(lambda:f.read(8*1024*1024),b''):h.update(b)
    return h.hexdigest()
if target.exists():
    assert target.stat().st_size==a.bytes and digest(target)==a.sha256
    print('ALREADY VERIFIED',target,flush=True);raise SystemExit(0)
parts=target.with_name(target.name+'.chunks');parts.mkdir(exist_ok=True)
pieces=[]
for path in list(parts.glob('*.bin'))+list(parts.glob('*.tmp')):
    start,end=map(int,path.stem.split('-'));size=path.stat().st_size
    if path.suffix=='.tmp' and path.with_suffix('.bin').exists():continue
    assert size<=end-start
    if size:pieces.append((start,start+size,path))
pieces.sort();cursor=0;gaps=[]
for start,end,path in pieces:
    assert start>=cursor
    if start>cursor:gaps.append((cursor,start))
    cursor=end
if cursor<a.bytes:gaps.append((cursor,a.bytes))
jobs=[(x,min(end,x+8*1024*1024)) for start,end in gaps for x in range(start,end,8*1024*1024)]
local=threading.local();started=time.monotonic();initial=sum(e-s for s,e,_ in pieces);done=initial
print('RESUME',initial,'bytes, requests',len(jobs),flush=True)
def fetch(bounds):
    start,end=bounds; dest=parts/f'{start}-{end}.bin';tmp=dest.with_suffix('.tmp')
    if not hasattr(local,'session'):
        local.session=requests.Session();local.session.trust_env=False
    for attempt in range(10):
        try:
            with local.session.get(a.url,headers={'Range':f'bytes={start}-{end-1}'},stream=True,timeout=(20,90)) as r:
                r.raise_for_status()
                assert r.status_code==206 and r.headers.get('Content-Range')==f'bytes {start}-{end-1}/{a.bytes}'
                with tmp.open('wb') as f:
                    for block in r.iter_content(256*1024):f.write(block)
                assert tmp.stat().st_size==end-start
                tmp.replace(dest)
                return start,end,dest
        except Exception as e:
            print('RETRY',start,attempt+1,type(e).__name__,flush=True);time.sleep(min(2**attempt,15))
    raise RuntimeError('Range failed: '+str(bounds))
last=0
with concurrent.futures.ThreadPoolExecutor(max_workers=a.workers) as pool:
    for f in concurrent.futures.as_completed([pool.submit(fetch,j) for j in jobs]):
        item=f.result();pieces.append(item);done+=item[1]-item[0];elapsed=time.monotonic()-started
        if elapsed-last>15:
            print(f'{done/1e9:.3f}/{a.bytes/1e9:.3f} GB; {(done-initial)/1e6/elapsed:.2f} MB/s',flush=True);last=elapsed
assembled=target.with_name(target.name+'.assembled');h=hashlib.sha256();cursor=0
with assembled.open('wb') as dst:
    for start,end,path in sorted(pieces):
        assert cursor==start
        with path.open('rb') as src:
            for b in iter(lambda:src.read(8*1024*1024),b''):dst.write(b);h.update(b)
        cursor=end
assert cursor==a.bytes and h.hexdigest()==a.sha256,'SHA256 mismatch'
assembled.replace(target)
target.with_suffix('.verified.json').write_text(json.dumps(dict(sha256=h.hexdigest(),bytes=a.bytes,seconds=time.monotonic()-started,transport=a.url.split('/')[2])))
print('VERIFIED',target,flush=True)
