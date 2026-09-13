"""用户要求保存时使用：创建不可覆盖的直接生成 v1 快照并逐文件核对。"""
import datetime, pathlib, shutil, subprocess, sys
import direct_animation as d

root=d.ROOT;source=d.WORKER;target=root/'releases/direct-animation-v1-20260913'
if target.exists():raise RuntimeError('Release already exists; preserve it and use a new release version')
checks=sorted((source/'checks').glob('check_*.json'))
passed=[p for p in checks if (r:=d.read(p)).get('stage')=='all' and r.get('status')=='PASS' and r['checks']['recipe']['dependency_hashes_checked']]
if not passed:raise RuntimeError('A real all + dependencies PASS report is required before archiving')
d.lock_check()
test=subprocess.run([sys.executable,str(root/'scripts/test_direct_animation.py')],capture_output=True,text=True,encoding='utf-8')
if test.returncode:raise RuntimeError(test.stdout+test.stderr)
d.save(source/'evidence/control_validation.json',dict(time=datetime.datetime.now().astimezone().isoformat(),checker_report=str(passed[-1]),
    regression_exit_code=test.returncode,regression_output=test.stdout+test.stderr,
    gpu_jobs_submitted_during_controls_validation=0,
    new_project_smoke='projects/_checks/direct-animation-v1-smoke: project PASS; assets BLOCKED due to missing review, as intended',
    boundaries='Checker does not infer character likeness, exact petting semantics or pronunciation quality. User acceptance quotes are declarations, not identity authentication.'))
extras=[root/x for x in ['AGENTS.md','docs/VIDEO_MODES.md','docs/DIRECT_ANIMATION_HANDOFF.md','docs/DIRECT_ANIMATION_CHECK_RESULTS.md','scripts/direct_animation.py','scripts/test_direct_animation.py','scripts/archive_direct_animation.py','scripts/hanli_reuse_pipeline.py','projects/004-hanli-voice-finetune/approved_profile_v1.json','workflows/direct-animation-v1/lock.json']]
files=[];excluded=[]
for p in source.rglob('*'):
    if not p.is_file():continue
    rel=p.relative_to(source)
    if '__pycache__' in rel.parts or p.suffix=='.bin' or p.stat().st_size>25*1024*1024:
        excluded.append(dict(path=str(p.relative_to(root)),bytes=p.stat().st_size,reason='Cache/network probe or oversized failed intermediate; original retained, not part of accepted delivery'))
    else:files.append(p)
target.mkdir(parents=True,exist_ok=False);manifest={}
for p in sorted(set(files+extras)):
    rel=p.relative_to(root);dest=target/rel;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,dest)
    a=d.sha(p);b=d.sha(dest)
    if a!=b:raise RuntimeError('Copy hash mismatch: '+str(rel))
    manifest[str(rel)]={'bytes':dest.stat().st_size,'sha256':b}
d.save(target/'manifest.json',dict(status='complete',created_at=datetime.datetime.now().astimezone().isoformat(),files=manifest,excluded=excluded,
    dependencies='Large inference models and runtimes are referenced by the frozen lock, not bundled. Restore files relative to workspace root; this is not a standalone installation.'))
(target/'README.md').write_text('# 直接生成模式 v1 保存快照\n\n已逐文件核对 SHA256。manifest.json 为文件清单；原始目录结构保留。\n\n先读 docs/VIDEO_MODES.md 和 docs/DIRECT_ANIMATION_HANDOFF.md。大型模型和运行环境不在快照内，见 workflows/direct-animation-v1/lock.json。不要在归档内训练或覆盖输出。\n',encoding='utf-8')
print('ARCHIVED',len(manifest),'files',sum(x['bytes'] for x in manifest.values()),'bytes',target)
