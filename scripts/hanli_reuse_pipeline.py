"""Reuse approved Han Li assets on a configured single-shot video, without training."""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import socket
import subprocess
import time

import requests


ROOT = Path(__file__).resolve().parents[1]
FFMPEG = ROOT / 'tools/ffmpeg-8.1.2-essentials_build/bin/ffmpeg.exe'
FFPROBE = FFMPEG.with_name('ffprobe.exe')


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')


def ff(*args):
    subprocess.run([str(FFMPEG), '-hide_banner', '-loglevel', 'error', '-n', *map(str, args)], check=True)


def duration(path):
    return float(subprocess.check_output([str(FFPROBE), '-v', 'error', '-show_entries', 'format=duration',
                                         '-of', 'default=nw=1:nk=1', str(path)], text=True))


def verify_profile(profile):
    for key in ('gpt', 'sovits'):
        path = ROOT / profile[key + '_weights']
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        if actual != profile[key + '_sha256']:
            raise RuntimeError('Approved weights changed: ' + str(path))


def align_voice(project, cfg):
    out = project / 'output/voice'
    normalized = out / 'dialogue.wav'
    seconds = duration(normalized)
    offset = cfg['voice_offset']
    if offset < 0 or seconds + offset > cfg['seconds']:
        raise RuntimeError('Dialogue does not fit; revise text or timing without truncating')
    signature = hashlib.sha256(normalized.read_bytes() + json.dumps([offset, cfg['seconds']]).encode()).hexdigest()
    target = out / ('aligned_' + signature[:12] + '.wav')
    metadata = target.with_suffix('.json')
    if target.exists():
        if not metadata.exists() or json.loads(metadata.read_text(encoding='utf-8'))['signature'] != signature:
            raise RuntimeError('Incomplete alignment cache; preserve it and use another output directory')
    else:
        ff('-i', normalized, '-af', f"adelay={round(offset*1000)}:all=1,apad,atrim=duration={cfg['seconds']}",
           '-ar', 48000, '-ac', 1, target)
        write_json(metadata, dict(signature=signature, source=str(normalized), source_seconds=seconds,
                                  offset=offset, target_seconds=cfg['seconds'], speed=1.0))
    return target


def prepare(project, cfg, profile, base):
    session = requests.Session()
    session.trust_env = False
    session.get(base + '/system_stats', timeout=10).raise_for_status()
    response = session.get(base + '/object_info', timeout=30)
    response.raise_for_status()
    objects = response.json()
    graph = json.loads((ROOT / cfg['template']).read_text(encoding='utf-8'))
    missing = sorted({n['class_type'] for n in graph.values()} - set(objects))
    if missing:
        raise RuntimeError('Missing ComfyUI nodes: ' + repr(missing))
    work = project / 'work'
    original = work / 'original_10s.mp4'
    frames = 4 * math.ceil(cfg['seconds'] * cfg['render_fps'] / 4) + 1
    ff('-ss', cfg['source_start'], '-i', project / cfg['source'], '-t', cfg['seconds'],
       '-vf', cfg['source_filter'] + ',fps=' + str(cfg['output_fps']), '-c:v', 'libx264',
       '-crf', 16, '-c:a', 'aac', original)
    input_video = work / 'render_input.mp4'
    ff('-i', original, '-an', '-vf', 'fps=' + str(cfg['render_fps']) + ',tpad=stop_mode=clone:stop_duration=0.25',
       '-frames:v', frames, '-c:v', 'libx264', '-crf', 15, input_video)

    def upload(path):
        with path.open('rb') as handle:
            result = session.post(base + '/upload/image', files={'image': (cfg['id'] + '_' + path.name, handle)}, timeout=120)
        result.raise_for_status()
        value = result.json()
        return (value.get('subfolder', '') + '/' + value['name']).lstrip('/')

    graph['1']['inputs']['file'] = upload(input_video)
    graph['3']['inputs']['image'] = upload(ROOT / profile['character_image'])
    graph['4']['inputs'].update(width=cfg['width'], height=cfg['height'])
    graph['6']['inputs'].update(coordinates_positive=json.dumps(cfg['positive_points']),
                               coordinates_negative=json.dumps(cfg['negative_points']))
    graph['35']['inputs']['text'] = cfg['visual_prompt']
    graph['36']['inputs']['text'] = 'flicker, distorted face, old man, beard, short hair, duplicate person, blur, deformed hands, subtitles'
    graph['40']['inputs'].update(width=cfg['width'], height=cfg['height'], length=frames)
    graph['44']['inputs']['length'] = frames
    for key in ('15', '17', '19', '45'):
        graph[key]['inputs']['fps'] = cfg['render_fps']
    for key, suffix in (('16', 'mask'), ('18', 'person'), ('20', 'pose'), ('46', 'generated')):
        graph[key]['inputs']['filename_prefix'] = cfg['id'] + '/' + suffix
    write_json(work / 'render.json', graph)
    write_json(work / 'preprocess.json', {k: v for k, v in graph.items() if int(k) < 30})
    write_json(work / 'profile_snapshot.json', profile)
    write_json(work / 'project_snapshot.json', cfg)
    write_json(work / 'input_manifest.json', {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
               for p in (project / cfg['source'], ROOT / profile['character_image'], ROOT / profile['reference_audio'])})
    print('Prepared', frames, 'frames;', work / 'render.json', flush=True)
    session.close()


def voice(project, cfg, profile):
    import yaml

    engine = ROOT / profile['engine_root']
    out = project / 'output/voice'
    out.mkdir(exist_ok=False)
    with socket.socket() as probe:
        probe.settimeout(2)
        if probe.connect_ex(('127.0.0.1', 9881)) == 0:
            raise RuntimeError('Port 9881 in use; leaving that service alone')
    config = yaml.safe_load((engine / 'GPT_SoVITS/configs/tts_infer.yaml').read_text(encoding='utf-8'))
    config['custom'].update(device='cuda', is_half=True, version=profile['version'],
        t2s_weights_path=str(ROOT / profile['gpt_weights']), vits_weights_path=str(ROOT / profile['sovits_weights']))
    configpath = out / 'inference.yaml'
    configpath.write_text(yaml.safe_dump(config), encoding='utf-8')
    payload = dict(profile['generation'], text=cfg['voice_text'],
                   ref_audio_path=str(ROOT / profile['reference_audio']), prompt_text=profile['reference_text'])
    write_json(out / 'request.json', payload)
    session = requests.Session()
    session.trust_env = False
    url = 'http://127.0.0.1:9881'
    env = os.environ.copy()
    env.update(PYTHONIOENCODING='utf-8', OMP_NUM_THREADS='4', MKL_NUM_THREADS='4')
    report = dict(status='running', profile=profile['profile_id'], retrained=False, payload=payload)
    with (out / 'api.log').open('w', encoding='utf-8') as log:
        process = subprocess.Popen([str(engine / 'runtime/python.exe'), '-u', 'api_v2.py', '-a', '127.0.0.1',
                                    '-p', '9881', '-c', str(configpath)], cwd=engine, env=env,
                                   stdout=log, stderr=subprocess.STDOUT, creationflags=subprocess.CREATE_NO_WINDOW)
        try:
            for _ in range(120):
                if process.poll() is not None:
                    raise RuntimeError('Voice API exited; inspect api.log')
                try:
                    if session.get(url + '/openapi.json', timeout=2).ok:
                        break
                except requests.RequestException:
                    pass
                time.sleep(2)
            else:
                raise TimeoutError('Voice API startup timeout')
            response = session.post(url + '/tts', json=payload, timeout=240)
            if not response.ok or not response.content.startswith(b'RIFF'):
                raise RuntimeError(response.text[:2000])
            raw = out / 'dialogue_raw.wav'
            raw.write_bytes(response.content)
            normalized = out / 'dialogue.wav'
            ff('-i', raw, '-af', 'loudnorm=I=-20:TP=-3:LRA=9', '-ar', 32000, '-ac', 1, normalized)
            seconds = duration(normalized)
            if seconds + cfg['voice_offset'] > cfg['seconds']:
                raise RuntimeError('Dialogue exceeds shot; shorten script instead of silently accelerating or truncating')
            aligned = align_voice(project, cfg)
            report.update(status='complete', seconds=seconds, output=str(normalized),
                          aligned_output=str(aligned),
                          offset=cfg['voice_offset'], speed=1.0, postprocessing='loudness, delay, silence pad only')
        except Exception as exc:
            report.update(status='failed', error=repr(exc))
            raise
        finally:
            if process.poll() is None:
                try:
                    session.get(url + '/control', params={'command': 'exit'}, timeout=5)
                except requests.RequestException:
                    pass
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.terminate()
                    process.wait(timeout=10)
            report['api_exit_code'] = process.returncode
            write_json(out / 'verification.json', report)
            session.close()
    verify_profile(profile)
    print(json.dumps(report, ensure_ascii=False), flush=True)


def compose(project, cfg):
    out, work = project / 'output', project / 'work'
    renders = list((out / 'render').glob('46_*.mp4'))
    masks = list((out / 'render').glob('16_*.mp4'))
    if len(renders) != 1 or len(masks) != 1:
        raise RuntimeError('Expected one successful render and one mask in output/render')
    fps = cfg['output_fps']
    h, w = cfg['height'], cfg['width']
    filters = ';'.join([
        f'[0:v]fps={fps},setpts=PTS-STARTPTS,format=gbrp[o]',
        f'[1:v]fps={fps},setpts=PTS-STARTPTS,format=gbrp[g]',
        f'[2:v]fps={fps},setpts=PTS-STARTPTS,format=gray,gblur=sigma=2,format=gbrp[m]',
        f"[o][g][m]maskedmerge,format=yuv420p,pad={w}:{h+32}:0:0:black,setsar=1,drawtext=text='{cfg['label']}':fontcolor=white:fontsize=13:x=12:y={h+9}[v]",
    ])
    final = out / 'hanli_reuse_10s.mp4'
    aligned = align_voice(project, cfg)
    write_json(work / 'composition_snapshot.json', cfg)
    ff('-i', work / 'original_10s.mp4', '-i', renders[0], '-i', masks[0], '-i', aligned,
       '-filter_complex', filters, '-map', '[v]', '-map', '3:a', '-t', cfg['seconds'],
       '-c:v', 'libx264', '-crf', 16, '-c:a', 'aac', '-movflags', '+faststart', final)
    comparison = out / 'before_after_10s.mp4'
    ff('-i', work / 'original_10s.mp4', '-i', final, '-filter_complex',
       f"[0:v]pad={w}:{h+32}:0:0:black,setsar=1,drawtext=text=ORIGINAL:fontcolor=white:fontsize=13:x=12:y={h+9}[l];[l][1:v]hstack=inputs=2[v]",
       '-map', '[v]', '-map', '1:a', '-t', cfg['seconds'], '-c:v', 'libx264', '-crf', 18,
       '-c:a', 'aac', '-movflags', '+faststart', comparison)
    ff('-i', final, '-vf', 'fps=1,scale=320:192,tile=5x2', '-frames:v', 1, out / 'review_contact.jpg')
    ff('-i', final, '-f', 'null', '-')
    meta = json.loads(subprocess.check_output([str(FFPROBE), '-v', 'error', '-show_format', '-show_streams',
                                             '-of', 'json', str(final)], text=True))
    assert abs(float(meta['format']['duration']) - cfg['seconds']) < 0.1
    write_json(out / 'verification.json', dict(full_decode='passed', ffprobe=meta, lip_sync=cfg['lip_sync'],
               aligned_voice=str(aligned), voice_offset=cfg['voice_offset'],
               audio_policy=cfg['audio_policy'], original_pixels_restored='outside feathered segmentation mask',
               final=str(final), comparison=str(comparison), visual_review='pending'))
    print(final, flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('stage', choices=['prepare', 'voice', 'compose'])
    parser.add_argument('--project', type=Path, required=True)
    parser.add_argument('--base-url', default='http://127.0.0.1:8188')
    args = parser.parse_args()
    project = args.project.resolve()
    cfg = json.loads((project / 'project.json').read_text(encoding='utf-8'))
    profile = json.loads((ROOT / cfg['profile']).read_text(encoding='utf-8'))
    verify_profile(profile)
    for name in ('work', 'output'):
        (project / name).mkdir(exist_ok=True)
    if args.stage == 'prepare':
        prepare(project, cfg, profile, args.base_url.rstrip('/'))
    elif args.stage == 'voice':
        voice(project, cfg, profile)
    else:
        compose(project, cfg)


if __name__ == '__main__':
    main()
