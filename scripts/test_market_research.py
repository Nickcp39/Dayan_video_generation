"""Synthetic checker regression cases; no market observations are generated."""
import copy
import tempfile
import unittest
from datetime import datetime, timezone, timedelta
from pathlib import Path

from market_research_pipeline import (GROUPS, default_plan, binding, file_hash,
                                     init_run, write_json)
from check_market_research import check_run


def metric(value):
    return {'value': value, 'raw': str(value) if value is not None else None,
            'precision': 'exact' if value is not None else 'unknown',
            'reason': '' if value is not None else 'Not publicly visible'}


class CheckerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.anchor = datetime.now(timezone.utc) - timedelta(hours=1)
        self.plan = default_plan(self.anchor.isoformat(), 'bilibili')
        self.plan.update(feed_count=6, keywords=['投资'], search_sorts=['popular'], discovery_limit=5)
        self.data = {k: [] for k in GROUPS}
        (self.root / 'evidence').mkdir()
        self.capture = self.root / 'evidence' / 'synthetic.txt'
        self.capture.write_text('SYNTHETIC TEST ONLY - not real audience evidence', encoding='utf-8')
        self.ev('search', 'https://search.bilibili.com/all?keyword=test')
        results = []
        for n in range(5):
            cid = f'c{n}'
            url = f'https://space.bilibili.com/{n+1}'
            self.ev(cid, url)
            self.data['creators'].append({
                'id': cid, 'platform': 'bilibili', 'name': 'SYNTHETIC ' + cid, 'url': url,
                'role': 'head' if n < 3 else 'peer', 'decision': 'selected', 'reason': 'Synthetic selection',
                'current_followers': metric(1000), 'evidence_ids': [cid],
                'listing': {'sort': 'newest', 'exclude_pinned': True, 'evidence_ids': [cid],
                            'video_ids': [f'{cid}v{i}' for i in range(6)]}})
            results.append({'rank': n+1, 'url': url, 'creator_id': cid, 'reason': 'Synthetic candidate'})
            for i in range(6):
                vid = f'{cid}v{i}'
                vurl = f'https://www.bilibili.com/video/{vid}'
                self.ev(vid, vurl)
                self.data['videos'].append({
                    'id': vid, 'creator_id': cid, 'url': vurl, 'title': 'SYNTHETIC ' + vid,
                    'published_at': (self.anchor-timedelta(days=20+i)).isoformat(),
                    'observed_at': self.anchor.isoformat(), 'duration_seconds': 30,
                    'language': 'zh', 'format': 'original_talking_head', 'topic': 'investment_principle',
                    'topic_reason': 'Synthetic fixture', 'metrics': {k: metric((i+1)*100) for k in
                                    ('views', 'likes', 'comments', 'favorites', 'shares')},
                    'evidence_ids': [vid]})
        self.data['discoveries'].append({'id': 'd1', 'query': '投资', 'sort': 'popular',
            'url': 'https://search.bilibili.com/all?keyword=test', 'observed_at': self.anchor.isoformat(),
            'evidence_ids': ['search'], 'results': results})
        self.save()
        for bands in check_run(self.root, 'collection')['deep_selection'].values():
            for vid in bands.values():
                a = {'id': 'a'+vid, 'video_id': vid, 'evidence_ids': [vid], 'comments': {
                    'status': 'none', 'sort': 'visible', 'items': [], 'missing_reason': 'Synthetic empty comments',
                    'evidence_ids': [vid]}}
                for field in ('audience_need_hypothesis', 'hook', 'structure', 'delivery', 'visuals',
                              'credibility', 'learnable_method', 'our_possible_contribution', 'do_not_copy', 'limitations'):
                    a[field] = 'Synthetic test explanation'
                self.data['analyses'].append(a)
        self.data['claims'] = [{'id': 'claim1', 'type': 'observation', 'scope': 'sample_description',
                              'text': 'Synthetic record exists', 'limitation': 'Not market evidence',
                              'video_ids': ['c0v0'], 'evidence_ids': ['c0v0']}]
        self.attest()

    def ev(self, eid, url):
        self.data['evidence'].append({'id': eid, 'url': url, 'method': 'browser_text',
            'label': 'Synthetic fixture', 'observed_at': self.anchor.isoformat(),
            'path': 'evidence/synthetic.txt', 'sha256': file_hash(self.capture)})

    def attest(self):
        self.data['reviews'] = []
        pairs = [('selection', 'all')]
        pairs += [('sampling', c['id']) for c in self.data['creators']]
        pairs += [('content', a['video_id']) for a in self.data['analyses']]
        pairs += [('synthesis', 'all')]
        for kind, target in pairs:
            self.data['reviews'].append({'id': kind+target, 'kind': kind, 'target': target,
                'binding_hash': binding(self.plan, self.data, kind, target), 'decision': 'accepted',
                'reviewer_role': 'agent', 'reviewer': 'SYNTHETIC TEST', 'notes': 'Fixture only',
                'reviewed_at': self.anchor.isoformat(), 'basis': 'full_watch'})
        self.save()

    def save(self):
        write_json(self.root/'plan.json', self.plan)
        write_json(self.root/'data.json', self.data)

    def check_code(self, code):
        self.save()
        result = check_run(self.root)
        self.assertNotEqual(result['status'], 'PASS')
        self.assertIn(code, [r['code'] for r in result['issues']], result)

    def tearDown(self):
        self.temp.cleanup()

    def test_complete_synthetic_fixture_passes(self):
        report = check_run(self.root)
        self.assertEqual(report['status'], 'PASS', report)
        self.assertEqual(report['cohorts']['c0']['median'], 350)
        self.assertEqual(len(report['deep_selection']), 5)

    def test_empty_run_is_not_research_pass(self):
        self.data = {k: [] for k in GROUPS}
        self.check_code('CREATOR_COVERAGE')
        self.assertEqual(check_run(self.root, 'plan')['status'], 'PASS')

    def test_missing_metric_not_zero(self):
        self.data['videos'][0]['metrics']['views'] = metric(None)
        self.check_code('RANKING_METRIC_MISSING')

    def test_unknown_zero_rejected(self):
        self.data['videos'][0]['metrics']['views'] = {'value': 0, 'raw': None, 'precision': 'unknown', 'reason': 'missing'}
        self.check_code('RECORD')

    def test_rounded_display_and_conversion(self):
        self.data['videos'][0]['metrics']['views'] = {'value': 156000, 'raw': '15.6万', 'precision': 'exact', 'reason': ''}
        self.check_code('RECORD')

    def test_recent_video_not_failure(self):
        self.data['videos'][0]['published_at'] = (self.anchor-timedelta(minutes=15)).isoformat()
        self.check_code('FEED_RECORD')

    def test_duplicate_video_url_rejected(self):
        self.data['videos'][1]['url'] = self.data['videos'][0]['url'] + '?tracking=1'
        self.check_code('RECORD')

    def test_tampered_evidence_fails(self):
        self.capture.write_text('changed', encoding='utf-8')
        self.check_code('EVIDENCE_INTEGRITY')

    def test_escape_path_fails(self):
        self.data['evidence'][0]['path'] = '../outside.txt'
        self.check_code('EVIDENCE_INTEGRITY')

    def test_review_cannot_survive_changed_input(self):
        self.data['videos'][0]['title'] += ' changed'
        self.check_code('STALE_REVIEW')

    def test_cross_platform_metric_rejected(self):
        self.plan['primary_metric'] = 'likes'
        self.check_code('SCHEMA')

    def test_snippet_not_primary_evidence(self):
        self.data['evidence'][-1]['method'] = 'search_snippet'
        self.check_code('DIRECT_SOURCE_REQUIRED')

    def test_causality_not_proven_by_counts(self):
        self.data['claims'][0]['scope'] = 'causality'
        self.attest()
        self.check_code('CLAIM_OVERREACH')

    def test_text_only_not_full_watch(self):
        for review in self.data['reviews']:
            if review['kind'] == 'content':
                review['basis'] = 'title_only'
                break
        self.check_code('FULL_WATCH_REQUIRED')

    def test_malformed_record_fails_without_crash(self):
        self.data['videos'][0]['id'] = []
        self.check_code('DUPLICATE_ID')

    def test_init_never_overwrites(self):
        with self.assertRaises(ValueError):
            init_run(self.root, self.anchor.isoformat(), 'bilibili')


if __name__ == '__main__':
    unittest.main(verbosity=2)
