"""不提交 GPU 作业：检查真实样片关联与故障拦截；临时目录由测试自行清理。"""
import copy, importlib.util, json, pathlib, shutil, sys, tempfile, unittest
from unittest.mock import patch, Mock
import requests
import direct_animation as d

sys.path.insert(0,str(d.WORKER))
import safe_runner

class CheckerTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='direct-check-');self.p=pathlib.Path(self.temp.name)
        for f in ('project.json','production.json'):shutil.copy2(d.WORKER/f,self.p/f)
    def tearDown(self):self.temp.cleanup()
    def edit(self,file,key,value):
        x=d.read(self.p/file);x[key]=value;d.save(self.p/file,x)
    def test_wrong_recipe_dimensions(self):
        self.edit('project.json','width',640)
        with self.assertRaises(ValueError):d.project_check(self.p)
    def test_path_escape(self):
        with self.assertRaises(ValueError):d.local(self.p,'../outside.png')
    def test_wrong_subtitle(self):
        x=d.read(self.p/'production.json');x['subtitles'][0]['text']='错误台词';d.save(self.p/'production.json',x)
        with self.assertRaises(ValueError):d.project_check(self.p)
    def test_overlapping_audio(self):
        self.edit('project.json','voice_offsets',[3,4])
        with self.assertRaises(ValueError):d.project_check(self.p)
    def test_missing_review(self):
        with self.assertRaises(d.Blocked):d.review_check(self.p,'assets')
    def test_stale_final_approval(self):
        f=d.configs(self.p)[1]['final'];dst=self.p/f;dst.parent.mkdir(parents=True);shutil.copy2(d.WORKER/f,dst)
        dst=self.p/'checks/reviews/final.json';dst.parent.mkdir(parents=True);shutil.copy2(d.WORKER/'checks/reviews/final.json',dst)
        self.edit('project.json','voice_text','换了台词')
        with self.assertRaises(ValueError):d.review_check(self.p,'final')
    def test_changed_render_graph(self):
        shutil.copytree(d.WORKER/'renders/tea_v1',self.p/'renders/tea_v1')
        path=self.p/'renders/tea_v1/workflow_api.json';g=d.read(path);g['3']['inputs']['steps']=6;d.save(path,g)
        with self.assertRaises(ValueError):d.shot_check(self.p,d.configs(self.p)[1]['shots'][0])
    def test_bad_video_rejected(self):
        p=self.p/'bad.mp4';p.write_bytes(b'not a video')
        with self.assertRaises(Exception):d.media(p,240)

class SubmissionTests(unittest.TestCase):
    def setUp(self):self.temp=tempfile.TemporaryDirectory(prefix='direct-submit-');self.p=pathlib.Path(self.temp.name);self.g={'1':{'class_type':'SaveImage','inputs':{}}}
    def tearDown(self):self.temp.cleanup()
    def session(self,queue=None):
        s=Mock();r=Mock();r.json.return_value=queue or {'queue_running':[],'queue_pending':[]};s.get.return_value=r;return s
    def test_busy_queue_never_posts(self):
        s=self.session({'queue_running':[1]})
        with patch.object(safe_runner.requests,'Session',return_value=s),self.assertRaises(RuntimeError):safe_runner.run('http://localhost',self.g,self.p)
        s.post.assert_not_called()
    def test_ambiguous_post_cannot_repeat(self):
        s=self.session();s.post.side_effect=requests.Timeout('lost response')
        with patch.object(safe_runner.requests,'Session',return_value=s):
            with self.assertRaises(requests.Timeout):safe_runner.run('http://localhost',self.g,self.p)
            with self.assertRaises(RuntimeError):safe_runner.run('http://localhost',self.g,self.p)
            with self.assertRaises(RuntimeError):safe_runner.run('http://localhost',self.g,self.p,resume=True)
        self.assertEqual(s.post.call_count,1)
        self.assertEqual(d.read(self.p/'job_state.json')['status'],'submission_intent')
    def test_known_resume_never_posts(self):
        s=self.session();h={'status':{'completed':True,'status_str':'success'},'outputs':{'1':{'images':[{'filename':'sample.png','type':'output'}]}}}
        history=Mock();history.json.return_value={'known':h};image=Mock();image.content=b'example image bytes';s.get.side_effect=[history,image]
        d.save(self.p/'job_state.json',{'prompt_id':'known','graph_sha256':safe_runner.digest(self.g)})
        with patch.object(safe_runner.requests,'Session',return_value=s):safe_runner.run('http://localhost',self.g,self.p,resume=True)
        s.post.assert_not_called();self.assertTrue((self.p/'metrics.json').exists())

if __name__=='__main__':unittest.main(verbosity=2)
