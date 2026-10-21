"""Append-only experiment records, independent of Streamlit."""
import hashlib
import json
import platform
import uuid
from datetime import datetime, timezone
from pathlib import Path

def digest(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
    return h.hexdigest()

class RunLog:
    def __init__(self, root, config):
        self.path=Path(root)/'runs'/uuid.uuid4().hex
        self.path.mkdir(parents=True,exist_ok=False)
        config=dict(config,created_at=datetime.now(timezone.utc).isoformat(),python=platform.python_version())
        self.save('config.json',config)
        self.save('result.json',{'status':'running','note':'若一直为running，请核查任务中断'})
    def save(self,name,data):
        target=self.path/name; tmp=self.path/(name+'.tmp')
        tmp.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8');tmp.replace(target)
    def frame(self, data):
        with (self.path/'predictions.jsonl').open('a',encoding='utf-8') as f:
            f.write(json.dumps(data,ensure_ascii=False)+'\n')
