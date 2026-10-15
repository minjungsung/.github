"""Publish validated repair via GitHub Git APIs without executing target code."""
import argparse
import base64
import json
import re
import subprocess
import tempfile
from pathlib import Path

from lib.models import PolicyError, load_inventory
from scripts.maintain_dependencies import MaintenanceClient
from scripts.security_remediation import validate_patch


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--evidence',type=Path,required=True);p.add_argument('--owner',required=True);p.add_argument('--inventory',type=Path,required=True);a=p.parse_args()
    c=json.loads((a.evidence/'candidate.json').read_text())['candidate']
    repo=load_inventory(a.inventory).repository(c['name'])
    if c['repository']!=f"{a.owner}/{repo.name}" or not re.fullmatch(r'automation/security-repair-[0-9a-f]{12}-[1-3]',c['branch']):raise PolicyError('invalid repair provenance')
    base=(a.evidence/'base-sha.txt').read_text().strip()
    if not re.fullmatch('[0-9a-f]{40}',base):raise PolicyError('invalid base SHA')
    client=MaintenanceClient();full=c['repository']
    current=client._json(['gh','api',f'repos/{full}/git/ref/heads/{repo.default_branch}'])['object']['sha']
    if current!=base:raise PolicyError('default branch advanced; regenerate repair')
    # Fetch public source in a disposable repo with hooks disabled and no target execution.
    with tempfile.TemporaryDirectory() as d:
        root=Path(d)
        subprocess.run(['git','init','-q',str(root)],check=True)
        subprocess.run(['git','-c','core.hooksPath=/dev/null','fetch','--depth=1',f'https://github.com/{full}.git',base],cwd=root,check=True,capture_output=True)
        subprocess.run(['git','-c','core.hooksPath=/dev/null','checkout','-q','FETCH_HEAD'],cwd=root,check=True)
        subprocess.run(['git','apply','--index',str((a.evidence/'repair.patch').resolve())],cwd=root,check=True)
        paths=subprocess.check_output(['git','diff','--cached','--name-only','-z'],cwd=root).decode().strip('\0').split('\0')
        validate_patch(root,paths)
        tree=[]
        for path in paths:
            target=root/path
            if target.is_file():
                raw=subprocess.run(['gh','api','--method','POST',f'repos/{full}/git/blobs','--input','-'],input=json.dumps({'content':base64.b64encode(target.read_bytes()).decode(),'encoding':'base64'}),text=True,capture_output=True,check=True)
                sha=json.loads(raw.stdout)['sha']
            else:sha=None
            tree.append({'path':path,'mode':'100644','type':'blob','sha':sha})
        def post(endpoint,payload):
            r=subprocess.run(['gh','api','--method','POST',endpoint,'--input','-'],input=json.dumps(payload),text=True,capture_output=True,check=True);return json.loads(r.stdout)
        original=client._json(['gh','api',f'repos/{full}/git/commits/{base}'])
        tree_sha=post(f'repos/{full}/git/trees',{'base_tree':original['tree']['sha'],'tree':tree})['sha']
        commit=post(f'repos/{full}/git/commits',{'message':'fix: remediate dependency security alerts','tree':tree_sha,'parents':[base]})['sha']
        client.mutate(f"repos/{full}/git/refs/heads/{c['branch']}",'PATCH',{'sha':commit,'force':False})
        body='Automated security repair after local project validation. Alerts: '+', '.join(map(str,c['alert-ids']))+'. Independent hosted CI and review remain required; no alert is dismissed. This PR is held for review because application compatibility changed.'
        result=post(f'repos/{full}/pulls',{'title':'fix: remediate dependency security alerts','head':c['branch'],'base':repo.default_branch,'body':body,'draft':True})
        post(f"repos/{full}/issues/{result['number']}/labels",{'labels':['human-only','security-remediation']})
        subprocess.run(['gh','pr','ready',str(result['number']),'--repo',full],check=True,capture_output=True)
        print('Repair PR published:',result['html_url'])

if __name__=='__main__':main()
