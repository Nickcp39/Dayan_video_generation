"""Wait for verified local dependencies, then generate independent character/dog assets."""
import json,pathlib,subprocess,sys,time
P=pathlib.Path(__file__).resolve().parent;ROOT=P.parents[1]
manifest=json.loads((P/'evidence/model_manifest.json').read_text())
for i in range(360):
    if all(pathlib.Path(x['target']).exists() and pathlib.Path(x['target']).with_suffix('.verified.json').exists() for x in manifest):break
    if i%12==0:print('WAITING for verified image dependencies',flush=True)
    time.sleep(5)
else:raise TimeoutError('Image dependencies incomplete; inspect download logs')
for args in [
 ['image','--name','character_v1','--prompt-file',str(P/'prompts/character.txt'),'--ref',str(ROOT/'assets/faces/hanli_01.jpg'),'--width','1536','--height','768'],
 ['image','--name','dog_reference_v1','--prompt-file',str(P/'prompts/dog_asset.txt'),'--width','1024','--height','576','--seed','2026091310'],
]:
    subprocess.run([sys.executable,str(P/'pipeline.py'),*args],check=True,cwd=ROOT)
