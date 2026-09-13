"""Download only the three image-edit dependencies from official tutorial sources."""
import concurrent.futures, hashlib, json, pathlib, subprocess, sys
import requests
P = pathlib.Path(__file__).resolve().parent
ROOT = P.parents[1]
MODELS = pathlib.Path('D:/work/software/pinokio/api/comfyui.pinokio/ComfyUI/models')
S = requests.Session()
items = [
 ('black-forest-labs/FLUX.2-klein-4b-fp8', 'flux-2-klein-4b-fp8.safetensors', 'diffusion_models'),
 ('Comfy-Org/z_image_turbo', 'split_files/text_encoders/qwen_3_4b.safetensors', 'text_encoders'),
 ('Comfy-Org/flux2-dev', 'split_files/vae/flux2-vae.safetensors', 'vae'),
]
manifest=[]
cached=P/'evidence/model_manifest.json'
if cached.exists(): manifest=json.loads(cached.read_text())
for repo, file, category in ([] if manifest else items):
    r=S.get(f'https://huggingface.co/api/models/{repo}/tree/main/' + '/'.join(file.split('/')[:-1]),params={'recursive':'false'},timeout=60)
    r.raise_for_status()
    item=next(x for x in r.json() if x['path']==file)
    manifest.append(dict(repo=repo,file=file,bytes=item['size'],sha256=item['lfs']['oid'],
       url=f'https://huggingface.co/{repo}/resolve/main/{file}',target=str(MODELS/category/'007_tea_dog'/file.split('/')[-1])))
(P/'evidence').mkdir(exist_ok=True)
(P/'logs').mkdir(exist_ok=True)
(P/'evidence/model_manifest.json').write_text(json.dumps(manifest,indent=2))
print(json.dumps(manifest,indent=2),flush=True)
def download(item):
    url=item['url'].replace('https://huggingface.co/','https://hf-mirror.com/')+'?download=true' if '--mirror' in sys.argv else item['url']
    with (P/'logs'/('download_'+('mirror_' if '--mirror' in sys.argv else '')+pathlib.Path(item['target']).name+'.log')).open('w') as log:
        workers='48' if 'text_encoders' in item['target'] else '24'
        cmd=[sys.executable,str(P/'download_https.py'),'--url',url,'--target',item['target'],'--bytes',str(item['bytes']),'--sha256',item['sha256'],'--workers',workers]
        subprocess.run(cmd,stdout=log,stderr=subprocess.STDOUT,check=True)
    print('READY',item['target'],flush=True)
with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
    list(pool.map(download,manifest))
