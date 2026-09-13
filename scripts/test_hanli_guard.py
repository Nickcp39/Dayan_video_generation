"""Offline regression tests: never submit a real GPU job."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

import hanli_guard as g


EXAMPLE = g.ROOT / 'projects/006-hanli-reuse-10s/retry_10fps'


class GuardTests(unittest.TestCase):
    def test_atomic_roundtrip(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'report.json'
            g.atomic(path, {'status': 'PASS'})
            self.assertEqual(g.read(path), {'status': 'PASS'})
            self.assertEqual(len(list(Path(directory).iterdir())), 1)

    def test_concurrent_lock_blocked(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'lock'
            with g.exclusive(path):
                with self.assertRaises(g.Blocked):
                    with g.exclusive(path):
                        pass
            self.assertFalse(path.exists())

    def checker(self):
        c = g.Checker(EXAMPLE)
        self.addCleanup(c.session.close)
        return c

    def test_approved_graph_matches(self):
        c = self.checker()
        actual = g.read(c.work / 'render.json')
        self.assertEqual(actual, c.expected_graph(actual))

    def test_actual_preprocess_and_render_artifacts(self):
        c = self.checker()
        c.job_check('preprocess')
        c.job_check('render')

    def test_voice_request_drift_rejected(self):
        c = self.checker()
        request = g.read(c.out / 'voice/request.json')
        request['seed'] = 3
        with patch.object(g, 'read', return_value=request):
            with self.assertRaisesRegex(ValueError, 'TTS request'):
                c.voice_check()

    def test_graph_model_seed_and_link_drift(self):
        c = self.checker()
        for node, key, value in [('41', 'seed', 7), ('41', 'steps', 4), ('30', 'unet_name', 'other'),
                                 ('40', 'pose_video', ['11', 0])]:
            graph = g.read(c.work / 'render.json')
            graph[node]['inputs'][key] = value
            self.assertNotEqual(graph, c.expected_graph(graph))

    def test_project_rejects_16fps(self):
        c = self.checker()
        c.cfg['render_fps'] = 16
        with self.assertRaisesRegex(ValueError, 'Locked project'):
            c.project_check()

    def test_project_rejects_negative_offset(self):
        c = self.checker()
        c.cfg['voice_offset'] = -1
        with self.assertRaisesRegex(ValueError, 'Invalid time'):
            c.project_check()

    def test_project_rejects_filter_injection(self):
        c = self.checker()
        c.cfg['source_filter'] += ',movie=other.mp4'
        with self.assertRaisesRegex(ValueError, 'filter'):
            c.project_check()

    def test_missing_review_blocked(self):
        c = self.checker()
        with patch.object(g.Path, 'exists', return_value=False):
            with self.assertRaises(g.Blocked):
                c.review_check('voice')

    def test_stale_review_rejected(self):
        c = self.checker()
        with patch.object(g.Path, 'exists', return_value=True), patch.object(g, 'read', return_value={'binding': {}}):
            with self.assertRaisesRegex(ValueError, 'stale'):
                c.review_check('voice')

    def test_corrupt_video_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'bad.mp4'
            path.write_bytes(b'not a video')
            with self.assertRaises(Exception):
                g.video(path, 640, 352, 10, 101)

    def test_unknown_submission_never_reposts(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            graph = {'1': {}}
            g.atomic(folder / 'job_state.json', dict(graph_hash=g.canonical(graph), base='local', status='submission_intent'))
            session = Mock()
            with self.assertRaises(g.Blocked):
                g.job(folder, graph, session, 'local', 1, True)
            session.post.assert_not_called()

    def test_post_timeout_persists_intent_no_retry(self):
        with tempfile.TemporaryDirectory() as directory:
            session = Mock()
            session.get.return_value.json.return_value = {'queue_running': [], 'queue_pending': []}
            session.post.side_effect = TimeoutError('ambiguous response')
            folder = Path(directory)
            with self.assertRaises(TimeoutError):
                g.job(folder, {}, session, 'local', 1, True)
            self.assertEqual(g.read(folder / 'job_state.json')['status'], 'submission_intent')
            with self.assertRaises(g.Blocked):
                g.job(folder, {}, session, 'local', 1, True)
            self.assertEqual(session.post.call_count, 1)

    def test_saved_job_resume_without_submission(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            g.atomic(folder / 'job_state.json', dict(graph_hash=g.canonical({}), base='local', prompt_id='saved'))
            session = Mock()
            session.get.return_value.json.return_value = {'saved': {'status': {'completed': True, 'status_str': 'success',
                                                                             'messages': []}, 'outputs': {}}}
            g.job(folder, {}, session, 'local', 1, False)
            session.post.assert_not_called()
            self.assertEqual(g.read(folder / 'job_state.json')['status'], 'complete')

    def test_timeout_keeps_job_resumable(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            g.atomic(folder / 'job_state.json', dict(graph_hash=g.canonical({}), base='local', prompt_id='saved'))
            with self.assertRaises(g.Blocked):
                g.job(folder, {}, Mock(), 'local', 0, False)
            self.assertEqual(g.read(folder / 'job_state.json')['prompt_id'], 'saved')

    def test_changed_graph_resume_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            g.atomic(folder / 'job_state.json', dict(graph_hash='old', base='local', prompt_id='saved'))
            session = Mock()
            with self.assertRaisesRegex(ValueError, 'changed graph'):
                g.job(folder, {}, session, 'local', 1, False)
            session.post.assert_not_called()

    def test_busy_queue_no_submission(self):
        with tempfile.TemporaryDirectory() as directory:
            session = Mock()
            session.get.return_value.json.return_value = {'queue_running': [1], 'queue_pending': []}
            with self.assertRaises(g.Blocked):
                g.job(Path(directory), {}, session, 'local', 1, True)
            session.post.assert_not_called()


if __name__ == '__main__':
    unittest.main(verbosity=2)
