"""Evidence/coverage checker. PASS never establishes market demand or causality."""
from __future__ import annotations

import argparse
import math
import re
from datetime import datetime, timezone, timedelta
from pathlib import Path
from statistics import median
from urllib.parse import urlparse

from market_research_pipeline import (GROUPS, binding, contained, digest, file_hash,
                                      read_json, stamp, write_json)

METRICS = ('views', 'likes', 'comments', 'favorites', 'shares')
DIRECT = {'browser_text', 'screenshot'}
FORMATS = {'original_talking_head', 'original_explainer', 'reposted_clip', 'other', 'unknown'}
TOPICS = {'investment_principle', 'personal_finance', 'decision_psychology',
          'market_news', 'other', 'unknown'}


def parse_time(value):
    result = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if result.tzinfo is None:
        raise ValueError('Timestamp must include timezone: ' + value)
    return result


def valid_url(value):
    parsed = urlparse(value)
    return parsed.scheme in {'https', 'http'} and bool(parsed.hostname) and not parsed.username


def canonical(value):
    parsed = urlparse(value)
    return (parsed.hostname or '').lower(), parsed.path.rstrip('/')


def displayed_number(raw):
    match = re.fullmatch(r'(\d+(?:\.\d+)?)([万亿kKmM]?)', raw.strip().replace(',', ''))
    if not match:
        raise ValueError('Unrecognized count display: ' + raw)
    scale = {'': 1, '万': 10000, '亿': 100000000, 'k': 1000, 'm': 1000000}
    return float(match[1]) * scale[match[2].lower()]


def nonblank(value):
    return isinstance(value, str) and bool(value.strip())


def _check_run(root, stage='analysis'):
    issues, cohorts, choices = [], {}, {}

    def issue(severity, code, message):
        issues.append({'severity': severity, 'code': code, 'message': message})

    def finish(plan=None, data=None):
        status = 'FAIL' if any(x['severity'] == 'FAIL' for x in issues) else (
            'BLOCKED' if any(x['severity'] == 'BLOCKED' for x in issues) else 'PASS')
        return {'checked_at': stamp(), 'stage': stage, 'status': status,
                'meaning': '结构、证据引用和采样覆盖检查；不证明内容真实、市场需求、因果或涨粉。',
                'input_hash': digest({'plan': plan, 'data': data}),
                'counts': {k: len(v) for k, v in (data or {}).items() if isinstance(v, list)},
                'cohorts': cohorts, 'deep_selection': choices, 'issues': issues}

    try:
        plan = read_json(root / 'plan.json')
        data = read_json(root / 'data.json')
        required = {'schema_version', 'revision', 'created_at', 'as_of', 'objective', 'platform',
                    'language', 'primary_metric', 'keywords', 'search_sorts', 'discovery_limit',
                    'selected_roles', 'feed_count', 'min_age_days', 'max_age_days',
                    'min_duration_seconds', 'max_duration_seconds', 'core_formats', 'core_topics',
                    'min_core_per_creator', 'min_core_creators', 'max_snapshot_span_hours',
                    'deep_bands', 'comment_limit', 'constraints'}
        if not isinstance(plan, dict) or not required <= plan.keys():
            raise ValueError('plan.json missing required fields')
        if plan['schema_version'] != 1 or plan['platform'] not in {'bilibili', 'douyin', 'xiaohongshu'}:
            raise ValueError('Unsupported schema/platform')
        anchor = parse_time(plan['as_of'])
        if anchor > datetime.now(timezone.utc) + timedelta(minutes=5):
            raise ValueError('Sampling cutoff cannot be in the future')
        parse_time(plan['created_at'])
        if plan['primary_metric'] != {'bilibili': 'views', 'douyin': 'likes', 'xiaohongshu': 'likes'}[plan['platform']]:
            raise ValueError('Primary metric does not match the platform policy')
        for key in ('revision', 'discovery_limit', 'feed_count', 'min_age_days', 'max_age_days',
                    'min_duration_seconds', 'max_duration_seconds', 'min_core_per_creator',
                    'min_core_creators', 'max_snapshot_span_hours', 'comment_limit'):
            if type(plan[key]) is not int or plan[key] <= 0:
                raise ValueError(f'plan.{key} must be a positive integer')
        if plan['min_core_per_creator'] < 3 or plan['min_core_per_creator'] > plan['feed_count']:
            raise ValueError('Core count must be between 3 and feed_count')
        if (plan['min_age_days'] >= plan['max_age_days'] or
                plan['min_duration_seconds'] > plan['max_duration_seconds']):
            raise ValueError('Invalid age/duration window')
        for key in ('keywords', 'search_sorts', 'core_formats', 'core_topics', 'constraints'):
            if not isinstance(plan[key], list) or not plan[key] or not all(nonblank(x) for x in plan[key]):
                raise ValueError(f'plan.{key} must be a nonempty text list')
            if len(set(plan[key])) != len(plan[key]):
                raise ValueError(f'Duplicate values in plan.{key}')
        if not set(plan['core_formats']) <= FORMATS - {'unknown'} or not set(plan['core_topics']) <= TOPICS - {'unknown'}:
            raise ValueError('Unknown core format/topic')
        if plan['deep_bands'] != ['low', 'middle', 'high']:
            raise ValueError('All three comparison bands are required')
        if set(plan['selected_roles']) != {'head', 'peer'} or any(
                type(x) is not int or x <= 0 for x in plan['selected_roles'].values()):
            raise ValueError('Both head and peer comparison groups are required')
        if plan['min_core_creators'] > sum(plan['selected_roles'].values()):
            raise ValueError('Not enough selected creators for core target')
        if not isinstance(data, dict) or set(data) != set(GROUPS):
            raise ValueError('data.json must contain exactly the documented record groups')
        for group in GROUPS:
            if not isinstance(data[group], list) or not all(isinstance(x, dict) for x in data[group]):
                raise ValueError(f'{group} must be an array of objects')
    except (ValueError, TypeError, AttributeError, KeyError, OSError) as exc:
        issue('FAIL', 'SCHEMA', str(exc))
        return finish()

    indexes = {}
    for group in GROUPS:
        items = data[group]
        ids = [x.get('id') for x in items]
        if any(not nonblank(x) for x in ids) or len(set(x for x in ids if isinstance(x, str))) != len(ids):
            issue('FAIL', 'DUPLICATE_ID', f'{group}: invalid or repeated ID')
        indexes[group] = {x.get('id'): x for x in items if isinstance(x.get('id'), str)}
    if issues:
        return finish(plan, data)
    evidence = indexes['evidence']

    def references(ids, context, direct=False, url=None):
        if not isinstance(ids, list) or any(not isinstance(x, str) for x in ids):
            issue('FAIL', 'REF_FORMAT', context)
            return False
        if not ids:
            issue('BLOCKED', 'MISSING_EVIDENCE', context)
            return False
        if any(x not in evidence for x in ids):
            issue('FAIL', 'DANGLING_EVIDENCE', context)
            return False
        if direct and not any(evidence[x].get('method') in DIRECT and
                              (not url or canonical(evidence[x].get('url', '')) == canonical(url))
                              for x in ids):
            issue('BLOCKED', 'DIRECT_SOURCE_REQUIRED', context)
            return False
        return True

    def metric(record, context):
        if not isinstance(record, dict) or not {'value', 'raw', 'precision', 'reason'} <= record.keys():
            raise ValueError(context + ': metric needs value/raw/precision/reason')
        value = record['value']
        if value is None:
            if record['precision'] != 'unknown' or record['raw'] is not None or not nonblank(record['reason']):
                raise ValueError(context + ': unknown metric needs null/raw, unknown precision and reason')
        else:
            if type(value) not in {int, float} or not math.isfinite(value) or value < 0:
                raise ValueError(context + ': count must be nonnegative finite number')
            if record['precision'] not in {'exact', 'rounded'}:
                raise ValueError(context + ': invalid precision')
            if not nonblank(record['raw']) or not math.isclose(value, displayed_number(record['raw'])):
                raise ValueError(context + ': parsed count disagrees with display')
            if re.search('[万亿kKmM]', record['raw']) and record['precision'] != 'rounded':
                raise ValueError(context + ': compact counts must be marked rounded')

    def review(kind, target):
        matches = [r for r in data['reviews'] if r.get('kind') == kind and r.get('target') == target]
        if len(matches) != 1:
            issue('BLOCKED', 'REVIEW_REQUIRED', f'{kind}/{target}: exactly one current review required')
            return
        r = matches[0]
        if r.get('binding_hash') != binding(plan, data, kind, target):
            issue('BLOCKED', 'STALE_REVIEW', f'{kind}/{target}: inputs changed; recheck before attesting')
        if (r.get('decision') != 'accepted' or r.get('reviewer_role') not in {'human', 'agent'} or
                not nonblank(r.get('reviewer')) or not nonblank(r.get('notes'))):
            issue('BLOCKED', 'REVIEW_INCOMPLETE', f'{kind}/{target}')
        if kind == 'content' and r.get('basis') != 'full_watch':
            issue('BLOCKED', 'FULL_WATCH_REQUIRED', target)

    for e in data['evidence']:
        try:
            if not valid_url(e['url']) or not nonblank(e['label']):
                raise ValueError('Missing source URL/label')
            if e['method'] not in DIRECT | {'search_snippet', 'analyst_note'}:
                raise ValueError('Unknown capture method')
            if parse_time(e['observed_at']) > datetime.now(timezone.utc) + timedelta(minutes=5):
                raise ValueError('Future capture timestamp')
            path = contained(root, e['path'])
            if not path.is_file() or path.stat().st_size == 0 or file_hash(path) != e['sha256']:
                raise ValueError('Capture missing, empty or SHA256 mismatch')
        except (ValueError, TypeError, AttributeError, KeyError, OSError) as exc:
            issue('FAIL', 'EVIDENCE_INTEGRITY', f"{e['id']}: {exc}")

    for group in ('creators', 'videos'):
        urls = set()
        for r in data[group]:
            try:
                if not valid_url(r['url']):
                    raise ValueError('Invalid URL')
                if canonical(r['url']) in urls:
                    raise ValueError('Duplicate canonical URL')
                urls.add(canonical(r['url']))
                references(r['evidence_ids'], f"{group}/{r['id']}", direct=True, url=r['url'])
                if group == 'creators':
                    if r['platform'] != plan['platform']:
                        raise ValueError('Cross-platform records require a separate run')
                    if r['decision'] not in {'candidate', 'selected', 'excluded'} or r['role'] not in {'head', 'peer', 'unclassified'}:
                        raise ValueError('Invalid selection/role')
                    if not nonblank(r['name']) or not nonblank(r['reason']):
                        raise ValueError('Missing name/selection rationale')
                    metric(r['current_followers'], r['id'] + '/followers')
                else:
                    if r['creator_id'] not in indexes['creators']:
                        raise ValueError('Unknown creator')
                    if not nonblank(r['title']) or not nonblank(r['topic_reason']):
                        raise ValueError('Missing title/classification rationale')
                    if r['format'] not in FORMATS or r['topic'] not in TOPICS:
                        raise ValueError('Invalid format/topic')
                    if not nonblank(r['language']):
                        raise ValueError('Missing language')
                    observed, published = parse_time(r['observed_at']), parse_time(r['published_at'])
                    if published > observed:
                        raise ValueError('Publication after observation')
                    if observed > datetime.now(timezone.utc) + timedelta(minutes=5):
                        raise ValueError('Future observation')
                    if r['duration_seconds'] is not None and (type(r['duration_seconds']) not in {int, float} or
                            not math.isfinite(r['duration_seconds']) or r['duration_seconds'] <= 0):
                        raise ValueError('Invalid duration')
                    if r['duration_seconds'] is None and not nonblank(r.get('duration_missing_reason')):
                        raise ValueError('Unknown duration requires reason')
                    for name in METRICS:
                        metric(r['metrics'][name], r['id'] + '/' + name)
            except (ValueError, TypeError, AttributeError, KeyError) as exc:
                issue('FAIL', 'RECORD', f"{group}/{r['id']}: {exc}")

    for r in data['reviews']:
        try:
            if r['kind'] not in {'selection', 'sampling', 'content', 'synthesis'}:
                raise ValueError('Unknown review kind')
            when = parse_time(r['reviewed_at'])
            if when > datetime.now(timezone.utc) + timedelta(minutes=5):
                raise ValueError('Future review')
        except (ValueError, TypeError, AttributeError, KeyError) as exc:
            issue('FAIL', 'REVIEW_SCHEMA', f"{r['id']}: {exc}")
    if any(x['severity'] == 'FAIL' for x in issues) or stage == 'plan':
        return finish(plan, data)

    seen_searches = set()
    for r in data['discoveries']:
        try:
            key = (r['query'], r['sort'])
            if key in seen_searches:
                raise ValueError('Repeated query/sort; append results to the same record')
            seen_searches.add(key)
            if r['query'] not in plan['keywords'] or r['sort'] not in plan['search_sorts']:
                raise ValueError('Query/sort outside plan')
            if not valid_url(r['url']):
                raise ValueError('Invalid search URL')
            references(r['evidence_ids'], 'search/' + r['id'], direct=True, url=r['url'])
            parse_time(r['observed_at'])
            result_urls = [canonical(item['url']) for item in r['results']]
            if len(set(result_urls)) != len(result_urls):
                raise ValueError('Repeated result within one search')
            if [item['rank'] for item in r['results']] != list(range(1, len(r['results']) + 1)):
                raise ValueError('Search ranks must be consecutive from 1')
            for item in r['results']:
                if not valid_url(item['url']) or not nonblank(item['reason']):
                    raise ValueError('Search result missing URL/exclusion rationale')
                if item['creator_id'] is not None and item['creator_id'] not in indexes['creators']:
                    raise ValueError('Unknown candidate creator')
            if len(r['results']) < plan['discovery_limit'] and not (
                    r.get('exhausted') is True and nonblank(r.get('exhaustion_reason'))):
                issue('BLOCKED', 'DISCOVERY_SHORT', r['id'])
        except (ValueError, TypeError, AttributeError, KeyError) as exc:
            issue('FAIL', 'DISCOVERY_RECORD', f"{r['id']}: {exc}")
    for query in plan['keywords']:
        for order in plan['search_sorts']:
            if (query, order) not in seen_searches:
                issue('BLOCKED', 'SEARCH_MISSING', f'{query}/{order}')
    selected = [c for c in data['creators'] if c['decision'] == 'selected']
    discovered_ids = {r.get('creator_id') for d in data['discoveries'] for r in d.get('results', [])}
    for creator in selected:
        if creator['id'] not in discovered_ids:
            issue('BLOCKED', 'SELECTION_PROVENANCE', creator['id'] + ': missing from discovery records')
    for role, count in plan['selected_roles'].items():
        actual = sum(c['role'] == role for c in selected)
        if actual != count:
            issue('BLOCKED', 'CREATOR_COVERAGE', f'{role}: {actual}/{count}')
    if any(c['role'] == 'unclassified' for c in selected):
        issue('BLOCKED', 'UNCLASSIFIED_SELECTED', 'Selected creators must have a comparison role')
    review('selection', 'all')
    for creator in selected:
        cid = creator['id']
        try:
            listing = creator['listing']
            if listing['sort'] != 'newest' or listing['exclude_pinned'] is not True:
                raise ValueError('Use newest listing; ignore pinned placement')
            references(listing['evidence_ids'], 'listing/' + cid, direct=True)
            video_ids = listing['video_ids']
            if len(set(video_ids)) != len(video_ids):
                raise ValueError('Duplicate video in feed')
            if len(video_ids) != plan['feed_count']:
                issue('BLOCKED', 'FEED_COUNT', f"{cid}: {len(video_ids)}/{plan['feed_count']}; record shortage, do not fill with chosen hits")
            rows = [indexes['videos'][vid] for vid in video_ids]
            if any(v['creator_id'] != cid for v in rows):
                raise ValueError('Feed contains another creator')
            dates = [parse_time(v['published_at']) for v in rows]
            if dates != sorted(dates, reverse=True):
                raise ValueError('Feed must be ordered by publication time descending')
            if any(not plan['min_age_days'] <= (anchor - date).total_seconds() / 86400 <= plan['max_age_days'] for date in dates):
                raise ValueError('Feed includes too-new or too-old videos')
            core = []
            for v in rows:
                if v['duration_seconds'] is None or v['format'] == 'unknown' or v['topic'] == 'unknown':
                    issue('BLOCKED', 'CLASSIFICATION_MISSING', v['id'])
                    continue
                if (v['language'] == plan['language'] and v['format'] in plan['core_formats'] and
                        v['topic'] in plan['core_topics'] and
                        plan['min_duration_seconds'] <= v['duration_seconds'] <= plan['max_duration_seconds']):
                    core.append(v)
            metric_name = plan['primary_metric']
            known = [v for v in core if v['metrics'][metric_name]['value'] is not None]
            if len(known) != len(core):
                issue('BLOCKED', 'RANKING_METRIC_MISSING', cid)
            for v in core:
                observed = parse_time(v['observed_at'])
                if abs((observed - anchor).total_seconds()) > plan['max_snapshot_span_hours'] * 3600:
                    issue('BLOCKED', 'STALE_SNAPSHOT', v['id'])
                direct_dates = [parse_time(evidence[e]['observed_at']) for e in v['evidence_ids']
                                if evidence[e]['method'] in DIRECT and canonical(evidence[e]['url']) == canonical(v['url'])]
                if not any(abs((t - observed).total_seconds()) <= 3600 for t in direct_dates):
                    issue('BLOCKED', 'SNAPSHOT_SOURCE_TIME', v['id'])
            observations = [parse_time(v['observed_at']) for v in core]
            if observations and (max(observations) - min(observations)).total_seconds() > plan['max_snapshot_span_hours'] * 3600:
                issue('BLOCKED', 'SNAPSHOT_SPAN', cid)
            cohorts[cid] = {'feed_count': len(rows), 'core_count': len(core), 'metric': metric_name,
                            'core_ids': [v['id'] for v in core], 'median': None}
            if len(known) >= plan['min_core_per_creator']:
                ordered = sorted(known, key=lambda v: (v['metrics'][metric_name]['value'], v['id']))
                values = [v['metrics'][metric_name]['value'] for v in ordered]
                med = median(values)
                cohorts[cid]['median'] = med
                cohorts[cid]['min'] = min(values)
                cohorts[cid]['max'] = max(values)
                cohorts[cid]['publication_span_days'] = (max(parse_time(v['published_at']) for v in core) -
                                                         min(parse_time(v['published_at']) for v in core)).total_seconds() / 86400
                if len(set(values)) < 3:
                    issue('BLOCKED', 'NO_DISTINCT_BANDS', cid)
                else:
                    middle = min(ordered[1:-1], key=lambda v: (abs(v['metrics'][metric_name]['value'] - med), v['id']))
                    choices[cid] = {'low': ordered[0]['id'], 'middle': middle['id'], 'high': ordered[-1]['id']}
            review('sampling', cid)
        except (ValueError, TypeError, AttributeError, KeyError) as exc:
            issue('FAIL' if 'listing' in creator else 'BLOCKED', 'FEED_RECORD', f'{cid}: {exc}')
    if len(choices) < plan['min_core_creators']:
        issue('BLOCKED', 'CORE_CREATOR_COVERAGE', f"{len(choices)}/{plan['min_core_creators']}; short original format not yet sufficiently represented")
    for role in ('head', 'peer'):
        if not any(c['role'] == role and c['id'] in choices for c in selected):
            issue('BLOCKED', 'CORE_ROLE_COVERAGE', role)
    if stage == 'collection' or any(x['severity'] == 'FAIL' for x in issues):
        return finish(plan, data)

    for cid, bands in choices.items():
        for band, vid in bands.items():
            matches = [a for a in data['analyses'] if a.get('video_id') == vid]
            if len(matches) != 1:
                issue('BLOCKED', 'ANALYSIS_MISSING', f'{cid}/{band}/{vid}')
                continue
            a = matches[0]
            try:
                for field in ('audience_need_hypothesis', 'hook', 'structure', 'delivery', 'visuals',
                              'credibility', 'learnable_method', 'our_possible_contribution',
                              'do_not_copy', 'limitations'):
                    if not nonblank(a[field]):
                        raise ValueError('Missing analysis field: ' + field)
                references(a['evidence_ids'], 'analysis/' + vid, direct=True,
                           url=indexes['videos'][vid]['url'])
                c = a['comments']
                references(c['evidence_ids'], 'comments/' + vid, direct=True,
                           url=indexes['videos'][vid]['url'])
                if c['status'] not in {'available', 'disabled', 'login_required', 'none', 'unavailable'}:
                    raise ValueError('Invalid comments status')
                if c['status'] == 'available':
                    if not nonblank(c['sort']) or not isinstance(c['items'], list):
                        raise ValueError('Comments need visible sort and items')
                    if len(c['items']) > plan['comment_limit'] or any(not nonblank(x) for x in c['items']):
                        raise ValueError('Comments must be bounded anonymized paraphrases')
                    if len(c['items']) < plan['comment_limit'] and not nonblank(c['missing_reason']):
                        raise ValueError('Explain incomplete comment sample')
                elif c['items'] or not nonblank(c['missing_reason']):
                    raise ValueError('Unavailable comments require empty items and explanation')
                review('content', vid)
            except (ValueError, TypeError, AttributeError, KeyError) as exc:
                issue('BLOCKED', 'ANALYSIS_INCOMPLETE', f'{vid}: {exc}')
    if not data['claims']:
        issue('BLOCKED', 'CLAIMS_MISSING', 'Record observations, hypotheses and unresolved questions separately')
    for claim in data['claims']:
        try:
            if claim['type'] not in {'observation', 'hypothesis', 'unknown'} or not nonblank(claim['text']) or not nonblank(claim['limitation']):
                raise ValueError('Missing claim type/text/limitation')
            if claim['scope'] not in {'sample_description', 'style_comparison', 'content_demand',
                                      'causality', 'audience_profile', 'follower_conversion', 'market_ranking'}:
                raise ValueError('Invalid claim scope')
            if claim['type'] == 'observation' and claim['scope'] in {'causality', 'audience_profile', 'follower_conversion', 'market_ranking'}:
                issue('BLOCKED', 'CLAIM_OVERREACH', claim['id'] + ': public convenience sample cannot establish this')
            if any(vid not in indexes['videos'] for vid in claim['video_ids']):
                raise ValueError('Unknown video in claim')
            if claim['type'] == 'observation':
                references(claim['evidence_ids'], 'claim/' + claim['id'], direct=True)
            elif not nonblank(claim['next_evidence_needed']):
                raise ValueError('Hypothesis/unknown needs a verification requirement')
        except (ValueError, TypeError, AttributeError, KeyError) as exc:
            issue('FAIL', 'CLAIM_RECORD', f"{claim['id']}: {exc}")
    review('synthesis', 'all')
    return finish(plan, data)


def check_run(root, stage='analysis'):
    # Malformed hand-entered records must fail closed and produce a useful report.
    try:
        if stage not in {'plan', 'collection', 'analysis'}:
            raise ValueError('Unknown stage')
        return _check_run(Path(root), stage)
    except (ValueError, TypeError, AttributeError, KeyError, OSError, OverflowError) as exc:
        return {'checked_at': stamp(), 'stage': stage, 'status': 'FAIL',
                'meaning': 'Malformed input; no research conclusion is validated.',
                'input_hash': None, 'counts': {}, 'cohorts': {}, 'deep_selection': {},
                'issues': [{'severity': 'FAIL', 'code': 'MALFORMED_INPUT', 'message': str(exc)}]}


def save_report(root, report):
    folder = root / 'reports'
    folder.mkdir(exist_ok=True)
    name = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ') + '-' + report['stage']
    path = folder / (name + '.json')
    write_json(path, report)
    lines = [f"# {report['status']} — {report['stage']}", '', report['meaning'], '',
             f"Input hash: `{report['input_hash']}`", '', '## Gaps / errors', '']
    lines.extend(f"- [{r['severity']}] **{r['code']}**: {r['message']}" for r in report['issues'])
    if not report['issues']:
        lines.append('- No machine-detectable gaps at this stage.')
    lines.extend(['', '## Deterministic deep-review selection', '',
                  '```json', __import__('json').dumps(report['deep_selection'], ensure_ascii=False, indent=2), '```', ''])
    path.with_suffix('.md').write_text('\n'.join(lines), encoding='utf-8')
    return path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', required=True, type=Path)
    parser.add_argument('--stage', choices=['plan', 'collection', 'analysis'], default='analysis')
    args = parser.parse_args()
    report = check_run(args.run, args.stage)
    path = save_report(args.run, report)
    print(f"{report['status']} ({args.stage}) {path}")
    return {'PASS': 0, 'BLOCKED': 2, 'FAIL': 1}[report['status']]


if __name__ == '__main__':
    raise SystemExit(main())
