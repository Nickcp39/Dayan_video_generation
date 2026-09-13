"""Validate the Git index only; no model, media, service or third-party package needed."""
import ast
import hashlib
import json
import pathlib
import subprocess
import sys

ROOT=pathlib.Path(__file__).resolve().parents[1]
def git(*args):return subprocess.check_output(['git',*args],cwd=ROOT)
def main():
    files=[x.decode('utf-8') for x in git('ls-files','-z').split(b'\0') if x]
    allowed={'.py','.ps1','.json','.md','.txt','.yaml','.yml','.srt','.toml'}
    special={'.gitignore','.gitattributes','.gitkeep'}
    contents={};errors=[]
    for name in files:
        p=pathlib.PurePosixPath(name);data=git('show',':'+name);contents[name]=data
        if p.suffix.lower() not in allowed and p.name not in special:errors.append('Non-source artifact: '+name)
        if len(data)>1024*1024:errors.append('File exceeds 1 MiB: '+name)
        if any(part in {'releases','node_modules','__pycache__','.venv','tools','dist','build'} for part in p.parts):errors.append('Local dependency/output directory: '+name)
        try:
            text=data.decode('utf-8-sig')
            if p.suffix=='.py':ast.parse(text,filename=name)
            if p.suffix=='.json':json.loads(text)
        except (ValueError,SyntaxError,UnicodeDecodeError) as e:errors.append(f'{name}: {e}')
    # Hash the staged bytes, not just the working copy: checkout normalization must not break locks.
    direct=json.loads(contents['workflows/direct-animation-v1/lock.json'])
    for name,expected in direct['code'].items():
        name=name.replace('\\','/')
        if name not in contents:errors.append('Missing locked workflow source: '+name)
        elif hashlib.sha256(contents[name]).hexdigest()!=expected:errors.append('Locked source changed: '+name)
    reuse=json.loads(contents['workflows/hanli-v1/lock.json'])
    for name,record in reuse['files'].items():
        name=name.replace('\\','/')
        if name in contents and hashlib.sha256(contents[name]).hexdigest()!=record['sha256']:errors.append('Reuse lock mismatch: '+name)
    if errors:
        print('\n'.join(errors));return 1
    print(f'PASS: {len(files)} source/design files; {sum(map(len,contents.values())):,} bytes; no models/media; staged workflow hashes match.')
    return 0
if __name__=='__main__':sys.exit(main())
