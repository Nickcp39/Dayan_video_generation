"""Offline, resumable market-research records. No scraping or publishing."""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

GROUPS = ('discoveries', 'creators', 'videos', 'analyses', 'claims', 'reviews', 'evidence')


def stamp():
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                     separators=(',', ':')).encode('utf-8')).hexdigest()


def file_hash(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def write_json(path, value):
    path = Path(path)
    temp = path.with_suffix(path.suffix + '.tmp')
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    temp.replace(path)


def contained(root, relative):
    root = Path(root).resolve()
    candidate = (root / relative).resolve()
    if not candidate.is_relative_to(root) or Path(relative).is_absolute():
        raise ValueError('Evidence path must stay inside the research run')
    return candidate


def binding(plan, data, kind, target):
    """Bind an attestation to current inputs; never create an attestation."""
    if kind == 'selection':
        payload = {k: data[k] for k in ('discoveries', 'creators', 'evidence')}
    elif kind == 'sampling':
        payload = {
            'creators': [x for x in data['creators'] if x['id'] == target],
            'videos': [x for x in data['videos'] if x['creator_id'] == target],
            'evidence': data['evidence'],
        }
    elif kind == 'content':
        payload = {
            'videos': [x for x in data['videos'] if x['id'] == target],
            'analyses': [x for x in data['analyses'] if x['video_id'] == target],
            'evidence': data['evidence'],
        }
    elif kind == 'synthesis':
        payload = {k: data[k] for k in GROUPS if k != 'reviews'}
        payload['reviews'] = [r for r in data['reviews'] if r['kind'] != 'synthesis']
    else:
        raise ValueError('Unknown review kind')
    return digest({'plan': plan, 'kind': kind, 'target': target, 'inputs': payload})


def default_plan(as_of, platform):
    return {
        'schema_version': 1, 'revision': 1, 'created_at': stamp(), 'as_of': as_of,
        'objective': '比较投资内容的热门、普通、低表现作品，研究可借鉴表达及原创增量；不开始制作。',
        'platform': platform, 'language': 'zh',
        'primary_metric': 'views' if platform == 'bilibili' else 'likes',
        'keywords': ['投资', '理财', '价值投资', '巴菲特', '芒格', '决策思维'],
        'search_sorts': ['relevance', 'popular'], 'discovery_limit': 10,
        'selected_roles': {'head': 3, 'peer': 2},
        'feed_count': 20, 'min_age_days': 14, 'max_age_days': 365,
        'min_duration_seconds': 15, 'max_duration_seconds': 90,
        'core_formats': ['original_talking_head', 'original_explainer'],
        'core_topics': ['investment_principle', 'personal_finance', 'decision_psychology'],
        'min_core_per_creator': 6, 'min_core_creators': 3,
        'max_snapshot_span_hours': 48, 'deep_bands': ['low', 'middle', 'high'],
        'comment_limit': 10,
        'constraints': ['不把搜索排名称为全市场排名', '不把累计互动称为涨粉或完播',
                        '不从标题直接推断流量原因', '不将缺失值填0',
                        '不自动写脚本、生成或发布视频'],
    }


def init_run(root, as_of, platform):
    root = Path(root)
    if root.exists() and any(root.iterdir()):
        raise ValueError('Run directory is not empty; use a new run directory')
    root.mkdir(parents=True, exist_ok=True)
    for folder in ('evidence', 'reports'):
        (root / folder).mkdir(exist_ok=True)
    write_json(root / 'plan.json', default_plan(as_of, platform))
    write_json(root / 'data.json', {key: [] for key in GROUPS})
    return root


def add_evidence(root, source, url, observed_at, method, label):
    root = Path(root)
    data = read_json(root / 'data.json')
    src = Path(source).resolve()
    if not src.is_file() or src.stat().st_size == 0:
        raise ValueError('Capture must be a nonempty local file')
    sha = file_hash(src)
    evidence_id = 'e-' + digest([sha, url, observed_at, method])[:16]
    if any(e['id'] == evidence_id for e in data['evidence']):
        return evidence_id
    relative = 'evidence/' + evidence_id + src.suffix.lower()
    dest = contained(root, relative)
    if dest.exists():
        raise ValueError('Refusing to overwrite an existing capture')
    shutil.copyfile(src, dest)
    data['evidence'].append({
        'id': evidence_id, 'url': url, 'observed_at': observed_at,
        'method': method, 'label': label, 'path': relative, 'sha256': sha,
    })
    # Only one writer per run. Failure before this save leaves an unreferenced capture.
    write_json(root / 'data.json', data)
    return evidence_id


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    init = sub.add_parser('init')
    init.add_argument('--run', required=True)
    init.add_argument('--as-of', required=True, help='Timezone-aware fixed sampling cutoff')
    init.add_argument('--platform', choices=['bilibili', 'douyin', 'xiaohongshu'], default='bilibili')
    evidence = sub.add_parser('evidence')
    evidence.add_argument('--run', required=True)
    evidence.add_argument('--capture', required=True)
    evidence.add_argument('--url', required=True)
    evidence.add_argument('--observed-at', required=True)
    evidence.add_argument('--method', required=True, choices=[
        'browser_text', 'screenshot', 'search_snippet', 'analyst_note'])
    evidence.add_argument('--label', required=True)
    bind = sub.add_parser('binding')
    bind.add_argument('--run', required=True)
    bind.add_argument('--kind', choices=['selection', 'sampling', 'content', 'synthesis'], required=True)
    bind.add_argument('--target', required=True)
    for command in ('check', 'queue'):
        item = sub.add_parser(command)
        item.add_argument('--run', required=True)
        item.add_argument('--stage', choices=['plan', 'collection', 'analysis'], default='analysis')
    args = parser.parse_args()
    try:
        if args.command == 'init':
            from check_market_research import parse_time
            parse_time(args.as_of)
            print(init_run(args.run, args.as_of, args.platform))
        elif args.command == 'evidence':
            from check_market_research import parse_time, valid_url
            parse_time(args.observed_at)
            if not valid_url(args.url):
                raise ValueError('Expected a public http(s) source URL')
            print(add_evidence(args.run, args.capture, args.url, args.observed_at, args.method, args.label))
        elif args.command == 'binding':
            print(binding(read_json(Path(args.run) / 'plan.json'),
                          read_json(Path(args.run) / 'data.json'), args.kind, args.target))
        else:
            from check_market_research import check_run, save_report
            report = check_run(Path(args.run), args.stage)
            path = save_report(Path(args.run), report)
            if args.command == 'queue':
                for item in report['issues']:
                    print(f"[{item['severity']}] {item['code']}: {item['message']}")
            print(f"{report['status']} ({report['stage']}): {path}")
            return {'PASS': 0, 'BLOCKED': 2, 'FAIL': 1}[report['status']]
    except (ValueError, OSError, KeyError, TypeError) as exc:
        print(f'FAIL: {exc}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
