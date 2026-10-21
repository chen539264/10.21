"""Persistent demo event workflow. No SMS network calls are made."""
import json
import sqlite3
import uuid
from contextlib import contextmanager, closing
from datetime import datetime, timezone
from pathlib import Path

def now():
    return datetime.now(timezone.utc).isoformat()

class Gate:
    def __init__(self, required=3, clear=5):
        self.required, self.clear = required, clear
        self.hits = self.misses = 0
        self.active = False
        self.first = None

    def step(self, positive, video_time):
        if positive:
            self.misses = 0
            if self.hits == 0:
                self.first = video_time
            self.hits += 1
            if not self.active and self.hits >= self.required:
                self.active = True
                return self.first
        else:
            self.hits = 0
            self.misses += 1
            if self.misses >= self.clear:
                self.active = False
        return None

class Store:
    def __init__(self, root):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.db = self.root/'events.sqlite3'
        with self.connect() as c:
            c.execute('CREATE TABLE IF NOT EXISTS events (id TEXT PRIMARY KEY, data TEXT NOT NULL)')
            c.execute('CREATE TABLE IF NOT EXISTS event_keys (key TEXT PRIMARY KEY, event_id TEXT NOT NULL)')

    @contextmanager
    def connect(self):
        connection=sqlite3.connect(self.db, timeout=20)
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def create(self, **data):
        event_key = data.pop('event_key', None)
        eid = uuid.uuid4().hex
        data.update(id=eid, created_at=now(), status='待接警', history=[])
        data['sms'] = {'mode':'模拟发送', 'status':'已生成模拟短信，未发送至运营商', 'created_at':now(),
                       'body':f"【模拟短信·车棚火情预警】{data['site']}发现疑似火情，请核查。事件编号：{eid[:8]}。"}
        with self.connect() as c:
            c.execute('BEGIN IMMEDIATE')
            if event_key:
                existing = c.execute('SELECT event_id FROM event_keys WHERE key=?',(event_key,)).fetchone()
                if existing:
                    return existing[0]
            c.execute('INSERT INTO events VALUES (?,?)', (eid,json.dumps(data,ensure_ascii=False)))
            if event_key:
                c.execute('INSERT INTO event_keys VALUES (?,?)',(event_key,eid))
        return eid

    def all(self):
        with self.connect() as c:
            rows = c.execute('SELECT data FROM events ORDER BY rowid DESC').fetchall()
        return [json.loads(r[0]) for r in rows]

    def export_backup(self):
        """SQLite consistent snapshot plus immutable evidence and existing run files."""
        import io
        import tempfile
        import zipfile
        with tempfile.TemporaryDirectory() as td:
            snapshot=Path(td)/'events.sqlite3'
            with self.connect() as source, closing(sqlite3.connect(snapshot)) as target:
                source.backup(target)
            buffer=io.BytesIO()
            with zipfile.ZipFile(buffer,'w',zipfile.ZIP_DEFLATED) as archive:
                archive.write(snapshot,'events.sqlite3')
                for p in self.root.rglob('*'):
                    if p.is_file() and p.name not in ('events.sqlite3','events.sqlite3-wal','events.sqlite3-shm','events.sqlite3-journal'):
                        archive.write(p,p.relative_to(self.root).as_posix())
                archive.writestr('RESTORE.txt','停止应用后解压至新的空目录，设置SHED_DATA_DIR指向该目录。运行中导出时实验日志可能仍在增长，应在分析完成后备份。')
            return buffer.getvalue()

    def transition(self, eid, action, operator, note='', verdict=''):
        if not operator.strip():
            raise ValueError('请填写处置人员姓名')
        with self.connect() as c:
            c.execute('BEGIN IMMEDIATE')
            row=c.execute('SELECT data FROM events WHERE id=?',(eid,)).fetchone()
            if not row:
                raise ValueError('事件不存在')
            data=json.loads(row[0])
            if action=='接警' and data['status']=='待接警':
                data['status']='处理中'; data['ack_at']=now()
            elif action=='结案' and data['status']=='处理中' and verdict in ('确认火情','误报','无法确认') and note.strip():
                data.update(status='已结案', verdict=verdict, closed_at=now())
            else:
                raise ValueError('状态已变更，或尚未填写完整处置记录')
            data['history'].append(dict(action=action,operator=operator.strip(),note=note,at=now()))
            c.execute('UPDATE events SET data=? WHERE id=?',(json.dumps(data,ensure_ascii=False),eid))
