import unittest,tempfile
from pathlib import Path
from lib.models import Inventory,Repository,Project,PolicyError
from scripts.security_remediation import select_candidate,validate_patch

class RepairTests(unittest.TestCase):
    def candidate(self,pulls=None,enabled=True):
        inventory=Inventory(1,(Repository('app','main',(Project('root','npm','.',runtime_version='20',manifest='package.json'),),auto_merge_enabled=enabled),))
        return select_candidate([{'name':'app','nameWithOwner':'example/app','defaultBranchRef':{'name':'main'}}],{'app':[{'number':1,'security_advisory':{'severity':'high'}}]},{'app':pulls or []},inventory)
    def test_manual_policy_and_duplicate_open_attempt_block(self):
        self.assertIsNone(self.candidate(enabled=False))
        c=self.candidate();self.assertIsNotNone(c)
        self.assertIsNone(self.candidate([{'head':{'ref':c['branch']},'state':'open'}]))
    def test_attempts_stop_after_three(self):
        c=self.candidate();prefix=c['branch'][:-1]
        pulls=[{'head':{'ref':prefix+str(n)},'state':'closed'} for n in range(1,4)]
        self.assertIsNone(self.candidate(pulls))
    def test_protected_paths_cannot_publish(self):
        with tempfile.TemporaryDirectory() as d:
            for path in ['.github/workflows/ci.yml','tests/test_app.py','.env','AGENTS.md','render.yaml','../escape','.agent/CURRENT.md']:
                with self.subTest(path=path),self.assertRaises(PolicyError):validate_patch(Path(d),[path])
    def test_empty_patch_is_not_success(self):
        with tempfile.TemporaryDirectory() as d,self.assertRaises(PolicyError):validate_patch(Path(d),[])

if __name__=='__main__':unittest.main()
