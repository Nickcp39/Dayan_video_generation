"""Fail-closed handoff controls around the unchanged, approved Han Li worker."""
import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
from fractions import Fraction
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time
import uuid

import requests

ROOT = Path(__file__).resolve().parents[1]
CONTROL = ROOT / 'workflows/hanli-v1'
FFMPEG = ROOT / 'tools/ffmpeg-8.1.2-essentials_build/bin/ffmpeg.exe'
FFPROBE = FFMPEG.with_name('ffprobe.exe')
STAGES = ('lock', 'project', 'voice', 'prepared', 'preprocess', 'render', 'compose', 'delivery')


class Blocked(RuntimeError):
    pass


def require(condition, message):
    if not condition:
        raise ValueError(message)


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def canonical(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def atomic(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + '.' + uuid.uuid4().hex + '.tmp')
    try:
        temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def now():
    return datetime.now(timezone.utc).isoformat()


def bounded(command, timeout=120):
    return subprocess.check_output(list(map(str, command)), timeout=timeout, stderr=subprocess.PIPE)


def runtime_info(executable):
    code = ('import json,sys,importlib.metadata as m; '
            'print(json.dumps({"python":sys.version,"packages":'
            '{p:m.version(p) for p in ("torch","numpy","requests","transformers")}}))')
    return json.loads(bounded([executable, '-c', code], 60))


def probe(path):
    return json.loads(bounded([FFPROBE, '-v', 'error', '-show_streams', '-show_format', '-of', 'json', path]))


def decode(path):
    bounded([FFMPEG, '-v', 'error', '-xerror', '-i', path, '-f', 'null', '-'])


def video(path, width, height, fps, frames):
    meta = probe(path)
    streams = [s for s in meta['streams'] if s['codec_type'] == 'video']
    require(len(streams) == 1, 'Expected one video stream: ' + str(path))
    stream = streams[0]
    require((stream['width'], stream['height']) == (width, height), 'Video dimensions changed')
    require(abs(float(Fraction(stream['avg_frame_rate'])) - fps) < .001, 'Wrong FPS')
    require(int(stream.get('nb_frames', -1)) == frames, 'Wrong video frame count')
    require(abs(float(stream['duration']) - frames / fps) < .1, 'Wrong video duration')
    decode(path)
    return meta


def audio(path, rate, seconds=None):
    meta = probe(path)
    streams = [s for s in meta['streams'] if s['codec_type'] == 'audio']
    require(len(streams) == 1, 'Expected one audio stream')
    stream = streams[0]
    require(int(stream['sample_rate']) == rate and stream['channels'] == 1, 'Wrong audio format')
    duration = float(stream['duration'])
    require(duration > .1, 'Empty audio')
    if seconds is not None:
        require(abs(duration - seconds) < .1, 'Audio duration mismatch')
    decode(path)
    return duration


@contextmanager
def exclusive(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        handle = path.open('x', encoding='utf-8')
    except FileExistsError:
        raise Blocked('Execution lock exists. Inspect PID/job state; do not automatically remove: ' + str(path))
    with handle:
        handle.write(json.dumps({'pid': os.getpid(), 'created': now()}))
    try:
        yield
    finally:
        path.unlink()


class Checker:
    def __init__(self, project, base='http://127.0.0.1:8188'):
        self.project = Path(project).resolve()
        self.cfg = read(self.project / 'project.json')
        self.lock = read(CONTROL / 'lock.json')
        self.profile = read(ROOT / self.lock['profile'])
        self.base = base.rstrip('/')
        require(self.base == 'http://127.0.0.1:8188', 'V1 only permits the local, approved ComfyUI endpoint')
        self.session = requests.Session()
        self.session.trust_env = False
        self.work = self.project / 'work'
        self.out = self.project / 'output'
        self.checked_lock = False

    def lock_check(self):
        if self.checked_lock:
            return
        for name, expected in self.lock['files'].items():
            path = ROOT / name
            require(path.is_file() and path.stat().st_size == expected['bytes'], 'Missing/changed locked file: ' + name)
            require(digest(path) == expected['sha256'], 'SHA256 mismatch: ' + name)
        for name, expected in self.lock['runtimes'].items():
            require(runtime_info(ROOT / name) == expected, 'Runtime versions changed: ' + name)
        self.checked_lock = True

    def environment(self):
        self.lock_check()
        r = self.session.get(self.base + '/system_stats', timeout=10)
        r.raise_for_status()
        actual = r.json()['system']
        for key, expected in self.lock['comfy_system'].items():
            require(actual.get(key) == expected, 'ComfyUI runtime drift: ' + key)
        r = self.session.get(self.base + '/object_info', timeout=30)
        r.raise_for_status()
        objects = r.json()
        classes = {n['class_type'] for n in read(CONTROL / 'render_baseline.json').values()}
        require(classes <= objects.keys(), 'Missing ComfyUI nodes: ' + repr(classes - objects.keys()))
        require(shutil.disk_usage(self.project).free >= 10 * 1024**3, 'Less than 10 GiB project disk space')
        require(shutil.disk_usage(self.lock['comfy_root']).free >= 10 * 1024**3, 'Less than 10 GiB ComfyUI disk space')

    def project_check(self):
        cfg = self.cfg
        baseline = read(CONTROL / 'project.example.json')
        require(set(cfg) == set(baseline), 'Config fields missing/unknown; use project.example.json')
        for key in self.lock['fixed_project_fields']:
            require(cfg[key] == baseline[key], 'Locked project parameter changed: ' + key)
        require(re.fullmatch(r'[A-Za-z0-9_-]{1,90}', cfg['id']) is not None, 'Unsafe project id')
        for key in ('source_start', 'voice_offset'):
            require(isinstance(cfg[key], (int, float)) and math.isfinite(cfg[key]) and cfg[key] >= 0,
                    'Invalid time: ' + key)
        require(cfg['voice_offset'] < 10, 'Voice offset outside shot')
        require(re.fullmatch(r'crop=\d+:\d+:\d+:\d+,scale=640:352,setsar=1', cfg['source_filter']) is not None,
                'Only approved crop/scale/setsar filter structure is allowed')
        for kind in ('positive_points', 'negative_points'):
            require(isinstance(cfg[kind], list) and cfg[kind], 'Segmentation points missing')
            for point in cfg[kind]:
                require(set(point) == {'x', 'y'} and 0 <= point['x'] < 640 and 0 <= point['y'] < 352,
                        'Segmentation point outside resized image')
        require(cfg['voice_text'].strip() and cfg['visual_prompt'].strip(), 'Empty dialogue/prompt')
        source = (self.project / cfg['source']).resolve()
        require(source.is_file(), 'Source file missing')
        meta = probe(source)
        require(float(meta['format']['duration']) >= cfg['source_start'] + 10, 'Source segment exceeds duration')
        require(any(s['codec_type'] == 'video' for s in meta['streams']), 'Source has no video')

    def expected_graph(self, actual):
        graph = read(CONTROL / 'render_baseline.json')
        cfg = self.cfg
        for node, field, suffix in (('1', 'file', '.mp4'), ('3', 'image', '.jpg')):
            uploaded = actual[node]['inputs'][field]
            require('..' not in uploaded and '\\' not in uploaded and
                    uploaded.startswith(cfg['id'] + '_') and uploaded.endswith(suffix), 'Unexpected uploaded input name')
            graph[node]['inputs'][field] = uploaded
        graph['6']['inputs'].update(coordinates_positive=json.dumps(cfg['positive_points']),
                                    coordinates_negative=json.dumps(cfg['negative_points']))
        graph['35']['inputs']['text'] = cfg['visual_prompt']
        for node, suffix in (('16', 'mask'), ('18', 'person'), ('20', 'pose'), ('46', 'generated')):
            graph[node]['inputs']['filename_prefix'] = cfg['id'] + '/' + suffix
        return graph

    def prepared_check(self):
        graph = read(self.work / 'render.json')
        require(graph == self.expected_graph(graph), 'Workflow graph drift (model/seed/steps/links/parameters)')
        require(read(self.work / 'preprocess.json') == {k: v for k, v in graph.items() if int(k) < 30},
                'Preprocess graph differs from render graph')
        require(read(self.work / 'project_snapshot.json') == self.cfg, 'Prepared config snapshot is stale')
        require(read(self.work / 'profile_snapshot.json') == self.profile, 'Prepared voice profile is stale')
        manifest = read(self.work / 'input_manifest.json')
        actual = {(ROOT / name).resolve(): value for name, value in manifest.items()}
        expected = {(self.project / self.cfg['source']).resolve(), (ROOT / self.profile['character_image']).resolve(),
                    (ROOT / self.profile['reference_audio']).resolve()}
        require(set(actual) == expected, 'Input manifest does not cover the exact source and references')
        for path, sha in actual.items():
            require(digest(path) == sha, 'Source/reference changed after preparation: ' + str(path))
        video(self.work / 'original_10s.mp4', 640, 352, 25, 250)
        video(self.work / 'render_input.mp4', 640, 352, 10, 101)

    def aligned(self):
        source = self.out / 'voice/dialogue.wav'
        # Preserve the worker's exact JSON number representation (10 vs 10.0).
        signature = hashlib.sha256(source.read_bytes() + json.dumps([self.cfg['voice_offset'], self.cfg['seconds']]).encode()).hexdigest()
        path = source.with_name('aligned_' + signature[:12] + '.wav')
        meta = read(path.with_suffix('.json'))
        require(meta['signature'] == signature and meta['speed'] == 1 and meta['offset'] == self.cfg['voice_offset']
                and meta['target_seconds'] == 10, 'Alignment metadata mismatch')
        audio(path, 48000, 10)
        filters = 'adelay=' + str(round(self.cfg['voice_offset'] * 1000)) + ':all=1,apad,atrim=duration=10'
        expected = bounded([FFMPEG, '-v', 'error', '-i', source, '-af', filters, '-ar', '48000', '-ac', '1', '-f', 's16le', '-'])
        actual = bounded([FFMPEG, '-v', 'error', '-i', path, '-f', 's16le', '-'])
        require(actual == expected, 'Aligned audio bytes do not match delay/padding of the approved dialogue')
        return path

    def voice_check(self):
        folder = self.out / 'voice'
        expected = dict(self.profile['generation'], text=self.cfg['voice_text'],
                        ref_audio_path=str(ROOT / self.profile['reference_audio']), prompt_text=self.profile['reference_text'])
        request = read(folder / 'request.json')
        require(request == expected, 'TTS request differs from locked profile/current dialogue')
        report = read(folder / 'verification.json')
        require(report['status'] == 'complete' and report['retrained'] is False and report['speed'] == 1,
                'Voice synthesis was not completed with the approved recipe')
        require(report['payload'] == expected and report['profile'] == self.profile['profile_id'], 'Wrong synthesis provenance')
        script = 'import json,sys,yaml; print(json.dumps(yaml.safe_load(open(sys.argv[1],encoding="utf-8"))["custom"]))'
        config = json.loads(bounded([ROOT / self.profile['engine_root'] / 'runtime/python.exe', '-c', script,
                                     folder / 'inference.yaml'], 30))
        for key, value in {'version': 'v2', 'device': 'cuda', 'is_half': True,
                           't2s_weights_path': str(ROOT / self.profile['gpt_weights']),
                           'vits_weights_path': str(ROOT / self.profile['sovits_weights'])}.items():
            require(config[key] == value, 'Inference configuration differs from approved model: ' + key)
        seconds = audio(folder / 'dialogue.wav', 32000)
        require(seconds + self.cfg['voice_offset'] <= 10, 'Dialogue would be truncated')
        require(abs(float(report['seconds']) - seconds) < .02, 'Voice duration differs from synthesis report')
        decode(folder / 'dialogue_raw.wav')
        pcm = bounded([FFMPEG, '-v', 'error', '-i', folder / 'dialogue.wav', '-f', 's16le', '-ac', '1', '-'])
        import numpy as np
        values = np.frombuffer(pcm, dtype='<i2').astype(float) / 32768
        require(float(np.sqrt(np.mean(values**2))) > .001, 'Silent/near-silent voice')
        require(float(np.mean(np.abs(values) > .999)) < .001, 'Clipped voice')

    def job_check(self, stage):
        folder = self.out / stage
        graph = read(self.work / ('preprocess.json' if stage == 'preprocess' else 'render.json'))
        require(read(folder / 'workflow_api.json') == graph, 'Submitted graph differs from prepared graph')
        submission = read(folder / 'submission.json')
        require(not submission.get('node_errors'), 'ComfyUI rejected node inputs')
        history = read(folder / 'history.json')
        require(history['prompt'][1] == submission['prompt_id'] and history['prompt'][2] == graph,
                'History belongs to a different job or graph')
        status = history['status']
        require(status['completed'] and status['status_str'] == 'success', 'ComfyUI job not successful')
        require(not any(m[0] in ('execution_error', 'execution_interrupted') for m in status['messages']),
                'ComfyUI execution failed/interrupted')
        metrics = read(folder / 'metrics.json')
        require(metrics['prompt_id'] == submission['prompt_id'], 'Wrong metrics prompt id')
        nodes = ('16', '18', '20', '46') if stage == 'render' else ('16', '18', '20')
        for node in nodes:
            files = list(folder.glob(node + '_*.mp4'))
            require(len(files) == 1, 'Missing/ambiguous job output: ' + node)
            filenames = [item['filename'] for value in history['outputs'][node].values() if isinstance(value, list)
                         for item in value if isinstance(item, dict) and 'filename' in item]
            require(files[0].name in [node + '_' + Path(name).name for name in filenames], 'Output filename not in job history')
            # DWPose resizes its shorter edge to 384; it is not a final-frame raster.
            width, height = (698, 384) if node == '20' else (640, 352)
            video(files[0], width, height, 10, 101)
        require(not list(folder.glob('*.part')), 'Incomplete job downloads remain')

    def compose_check(self):
        require(read(self.work / 'composition_snapshot.json') == self.cfg, 'Composition config is stale')
        aligned = self.aligned()
        final = self.out / 'hanli_reuse_10s.mp4'
        video(final, 640, 384, 25, 250)
        audio(final, 48000, 10)
        video(self.out / 'before_after_10s.mp4', 1280, 384, 25, 250)
        meta = read(self.out / 'verification.json')
        require(meta['voice_offset'] == self.cfg['voice_offset'] and Path(meta['aligned_voice']).resolve() == aligned,
                'Composition used a different aligned voice')
        import numpy as np
        pcm_args = ['-f', 'f32le', '-ac', '1', '-ar', '48000', '-']
        a = np.frombuffer(bounded([FFMPEG, '-v', 'error', '-i', aligned, *pcm_args]), dtype='<f4')
        b = np.frombuffer(bounded([FFMPEG, '-v', 'error', '-i', final, '-vn', *pcm_args]), dtype='<f4')
        length = min(len(a), len(b))
        require(abs(len(a) - len(b)) <= 2048 and float(np.corrcoef(a[:length], b[:length])[0, 1]) > .98,
                'Final audio is not the aligned synthetic voice')
        raw = bounded([FFMPEG, '-v', 'error', '-i', final, '-vf', 'fps=1,scale=64:38', '-pix_fmt', 'rgb24', '-f', 'rawvideo', '-'])
        frames = np.frombuffer(raw, dtype=np.uint8).reshape(-1, 38, 64, 3).astype(float)
        require(len(frames) == 10 and min(f.std() for f in frames) > 5, 'Blank/near-blank sampled output')
        require(float(np.mean(np.abs(np.diff(frames, axis=0)))) > .5, 'Sampled output appears frozen')
        require((self.out / 'review_contact.jpg').is_file(), 'Contact sheet missing')

    def review_files(self, kind):
        if kind == 'voice':
            paths = [self.out / 'voice/dialogue.wav', self.out / 'voice/request.json']
        elif kind == 'mask':
            paths = [self.work / 'preprocess.json', self.work / 'render_input.mp4']
            paths += sorted((self.out / 'preprocess').glob('*.mp4'))
        else:
            paths = [self.out / 'hanli_reuse_10s.mp4', self.out / 'before_after_10s.mp4', self.aligned()]
        require(paths and all(p.is_file() for p in paths), 'Review artifacts missing')
        return {str(p.relative_to(self.project)): digest(p) for p in paths}

    def binding(self, kind):
        return {'config': canonical(self.cfg), 'recipe': digest(CONTROL / 'lock.json'), 'files': self.review_files(kind)}

    def review_check(self, kind):
        path = self.project / 'checks/reviews' / (kind + '.json')
        if not path.exists():
            raise Blocked('Human review required: ' + kind)
        record = read(path)
        require(record['binding'] == self.binding(kind), 'Review is stale: ' + kind)
        require(record['decision'] in ('accepted', 'accepted_with_issue'), 'Review not accepted')
        require(record['reviewer'].strip() and record['evidence'].strip(), 'Review evidence missing')
        if kind == 'final':
            require(record['reviewer'] == 'user', 'Final acceptance must come from the user')

    def check(self, stage):
        if stage == 'lock':
            self.lock_check()
        elif stage == 'project':
            self.project_check()
        elif stage == 'voice':
            self.voice_check()
        elif stage == 'prepared':
            self.prepared_check()
        elif stage in ('preprocess', 'render'):
            self.job_check(stage)
        elif stage == 'compose':
            self.compose_check()
        else:
            self.review_check('final')


def job(folder, graph, session, base, timeout, allow_submit):
    """Write intent before POST; uncertain submissions must never be automatically retried."""
    folder.mkdir(parents=True, exist_ok=True)
    statepath = folder / 'job_state.json'
    graph_hash = canonical(graph)
    if statepath.exists():
        state = read(statepath)
        require(state['graph_hash'] == graph_hash and state['base'] == base, 'Cannot resume a changed graph/endpoint')
        if not state.get('prompt_id'):
            raise Blocked('Submission outcome unknown. Reconcile queue/history manually; do not resubmit.')
        prompt_id = state['prompt_id']
    else:
        require(allow_submit, 'No saved job to resume; run without --resume only for a new job')
        require(not list(folder.iterdir()), 'Existing legacy/partial job; inspect it instead of resubmitting')
        response = session.get(base + '/queue', timeout=15)
        response.raise_for_status()
        queue = response.json()
        if queue.get('queue_running') or queue.get('queue_pending'):
            raise Blocked('ComfyUI queue is busy; leaving other jobs alone')
        atomic(folder / 'workflow_api.json', graph)
        state = dict(graph_hash=graph_hash, base=base, status='submission_intent', created=now(),
                     client_id=str(uuid.uuid4()))
        atomic(statepath, state)
        response = session.post(base + '/prompt', json={'prompt': graph, 'client_id': state['client_id']}, timeout=60)
        response.raise_for_status()
        submission = response.json()
        atomic(folder / 'submission.json', submission)
        require(not submission.get('node_errors') and submission.get('prompt_id'), 'Submission rejected; inspect saved response')
        prompt_id = submission['prompt_id']
        state.update(prompt_id=prompt_id, status='submitted')
        atomic(statepath, state)
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        response = session.get(base + '/history/' + prompt_id, timeout=30)
        response.raise_for_status()
        history = response.json().get(prompt_id)
        if history:
            atomic(folder / 'history.json', history)
            status = history['status']
            if status['status_str'] == 'error' or any(m[0] in ('execution_error', 'execution_interrupted') for m in status['messages']):
                state.update(status='failed', updated=now())
                atomic(statepath, state)
                raise ValueError('ComfyUI job failed; preserve history and use an explicitly approved new attempt')
            if status['completed']:
                require(status['status_str'] == 'success', 'Unexpected completed job status')
                files = []
                for node, output in history['outputs'].items():
                    for values in output.values():
                        if not isinstance(values, list):
                            continue
                        for entry in values:
                            if not isinstance(entry, dict) or 'filename' not in entry:
                                continue
                            require(re.fullmatch(r'\d+', node) is not None, 'Unsafe output node id')
                            filename = str(entry['filename']).replace('\\', '/').split('/')[-1]
                            require(filename not in ('', '.', '..') and ':' not in filename, 'Unsafe output filename')
                            target = folder / (node + '_' + filename)
                            if not target.exists():
                                response = session.get(base + '/view', params={k: entry[k] for k in ('filename', 'subfolder', 'type')}, timeout=180)
                                response.raise_for_status()
                                partial = target.with_suffix(target.suffix + '.part')
                                partial.write_bytes(response.content)
                                os.replace(partial, target)
                            files.append(str(target))
                atomic(folder / 'metrics.json', dict(prompt_id=prompt_id, files=files, resumed=True))
                state.update(status='complete', updated=now())
                atomic(statepath, state)
                return
        time.sleep(min(5, max(0, deadline - time.monotonic())))
    state.update(status='wait_timeout', updated=now())
    atomic(statepath, state)
    raise Blocked('Wait limit reached; server may still be running. Resume this prompt_id, never submit a duplicate.')


def check_report(checker, stages):
    report = dict(created=now(), project=str(checker.project), recipe=digest(CONTROL / 'lock.json'), stages={})
    for stage in stages:
        try:
            checker.check(stage)
            report['stages'][stage] = {'status': 'PASS'}
        except Exception as exc:
            report['stages'][stage] = {'status': 'BLOCKED' if isinstance(exc, Blocked) else 'FAIL', 'reason': str(exc)}
    failures = [v['status'] for v in report['stages'].values() if v['status'] != 'PASS']
    report['status'] = 'FAIL' if 'FAIL' in failures else ('BLOCKED' if failures else 'PASS')
    report['scope'] = 'Selected checks only; PASS is not a claim of subjective quality or bitwise reproducibility.'
    atomic(checker.project / 'checks' / ('check_' + str(time.time_ns()) + '.json'), report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 1 if report['status'] == 'FAIL' else (2 if report['status'] == 'BLOCKED' else 0)


def run_stage(c, stage, resume, timeout):
    with exclusive(CONTROL / 'execution.lock'):
        c.lock_check()
        c.project_check()
        if stage in ('prepare', 'preprocess', 'render'):
            c.environment()
        prerequisites = {'voice': [], 'prepare': ['voice'], 'preprocess': ['voice', 'prepared'],
                         'render': ['voice', 'prepared', 'preprocess'], 'compose': ['voice', 'prepared', 'render']}[stage]
        for prerequisite in prerequisites:
            c.check(prerequisite)
        if stage != 'voice':
            c.review_check('voice')
        if stage in ('render', 'compose'):
            c.review_check('mask')
        if stage in ('preprocess', 'render'):
            graph = read(c.work / (stage + '.json'))
            # Verify server-side uploads still contain the bytes prepared locally.
            for node, field, path in (('1', 'file', c.work / 'render_input.mp4'),
                                       ('3', 'image', ROOT / c.profile['character_image'])):
                response = c.session.get(c.base + '/view', params={'filename': graph[node]['inputs'][field], 'type': 'input'}, timeout=120)
                response.raise_for_status()
                require(hashlib.sha256(response.content).hexdigest() == digest(path), 'Server upload changed')
            job(c.out / stage, graph, c.session, c.base, timeout, not resume)
        else:
            require(not resume, '--resume is only for preprocess/render jobs')
            destination = {'voice': c.out / 'voice', 'prepare': c.work / 'original_10s.mp4',
                           'compose': c.out / 'hanli_reuse_10s.mp4'}[stage]
            require(not destination.exists(), 'Output already exists; preserve it and inspect, do not overwrite')
            python = ROOT / c.profile['engine_root'] / 'runtime/python.exe' if stage == 'voice' else Path(sys.executable)
            # The voice worker owns and cleans up its child API; do not kill its parent on an external timer.
            result = subprocess.run([str(python), '-u', str(ROOT / 'scripts/hanli_reuse_pipeline.py'), stage,
                                     '--project', str(c.project), '--base-url', c.base], cwd=ROOT)
            require(result.returncode == 0, 'Worker failed; preserve partial artifacts, inspect logs before another attempt')
        c.check('prepared' if stage == 'prepare' else stage)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('command', choices=['check', 'run', 'review', 'environment'])
    p.add_argument('--project', type=Path, required=True)
    p.add_argument('--stage', choices=STAGES + ('all', 'prepare'), default='all')
    p.add_argument('--kind', choices=['voice', 'mask', 'final'])
    p.add_argument('--reviewer')
    p.add_argument('--evidence')
    p.add_argument('--known-issue', default='')
    p.add_argument('--resume', action='store_true')
    p.add_argument('--timeout', type=int, default=900)
    args = p.parse_args()
    c = None
    try:
        c = Checker(args.project)
        if args.command == 'check':
            require(args.stage != 'prepare', 'Use --stage prepared for check')
            return check_report(c, STAGES if args.stage == 'all' else STAGES[:STAGES.index(args.stage) + 1])
        if args.command == 'environment':
            c.environment()
            print('PASS: locked files, runtimes, live ComfyUI, required nodes and disk space')
        elif args.command == 'run':
            require(args.stage in ('voice', 'prepare', 'preprocess', 'render', 'compose'), 'Choose one generation stage')
            require(1 <= args.timeout <= 3600, 'Timeout must be 1..3600 seconds')
            run_stage(c, args.stage, args.resume, args.timeout)
            print('PASS: ' + args.stage + '; next stage is not started automatically')
        else:
            require(args.kind and args.reviewer and args.evidence, 'Review needs kind, reviewer and actual evidence')
            if args.kind == 'final':
                require(args.reviewer == 'user', 'Final review must quote actual user acceptance')
            c.lock_check()
            c.project_check()
            c.check({'voice': 'voice', 'mask': 'preprocess', 'final': 'compose'}[args.kind])
            record = dict(created=now(), reviewer=args.reviewer, evidence=args.evidence,
                          decision='accepted_with_issue' if args.known_issue else 'accepted', known_issue=args.known_issue,
                          binding=c.binding(args.kind))
            path = c.project / 'checks/reviews' / (args.kind + '.json')
            require(not path.exists(), 'Review already exists; preserve it. A changed attempt belongs in a new project directory.')
            atomic(path, record)
            print('Recorded review assertion; the checker cannot authenticate a human statement: ' + str(path))
        return 0
    except Exception as exc:
        status = 'BLOCKED' if isinstance(exc, Blocked) else 'FAIL'
        if c:
            atomic(c.project / 'checks' / ('error_' + str(time.time_ns()) + '.json'),
                   dict(created=now(), command=args.command, stage=args.stage, status=status, reason=str(exc)))
        print(status + ': ' + str(exc), file=sys.stderr)
        return 2 if isinstance(exc, Blocked) else 1
    finally:
        if c:
            c.session.close()


if __name__ == '__main__':
    sys.exit(main())
