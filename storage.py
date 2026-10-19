"""Transactional local document store; logical JSON exports stay portable."""
import json
import sqlite3
import threading
from contextlib import contextmanager, closing

NAMES = {'profile.json': {}, 'records.json': [], 'conversations.json': [],
         'media.json': [], 'metadata.json': {}, 'workspace.json': {}}
LOCAL = threading.local()

def db_path(folder):
    return folder / 'health.sqlite3'

def initialize(folder):
    folder.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(db_path(folder))) as conn, conn:
        conn.execute('CREATE TABLE IF NOT EXISTS documents (name TEXT PRIMARY KEY, body TEXT NOT NULL)')
        conn.execute('CREATE TABLE IF NOT EXISTS revisions (id INTEGER PRIMARY KEY CHECK(id=1), value INTEGER NOT NULL)')
        conn.execute('INSERT OR IGNORE INTO revisions VALUES (1,0)')
        for name, default in NAMES.items():
            if conn.execute('SELECT 1 FROM documents WHERE name=?', (name,)).fetchone():
                continue
            path = folder / name
            value = json.loads(path.read_text(encoding='utf-8')) if path.exists() else default
            if not isinstance(value, type(default)):
                raise ValueError('invalid_legacy_data')
            conn.execute('INSERT INTO documents VALUES (?,?)', (name, json.dumps(value, ensure_ascii=False)))
        if conn.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
            raise ValueError('database_integrity_failed')

@contextmanager
def connection(folder):
    active = getattr(LOCAL, 'active', None)
    if active and active[0] == str(folder):
        yield active[1]
        return
    conn = sqlite3.connect(db_path(folder), timeout=10)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

@contextmanager
def transaction(folder):
    with connection(folder) as conn:
        if getattr(LOCAL, 'active', None):
            yield
            return
        conn.execute('BEGIN IMMEDIATE')
        LOCAL.active = (str(folder), conn)
        try:
            yield
        finally:
            LOCAL.active = None

def read(folder, name, default):
    with connection(folder) as conn:
        row = conn.execute('SELECT body FROM documents WHERE name=?', (name,)).fetchone()
        return json.loads(row[0]) if row else default

def write(folder, name, value):
    with connection(folder) as conn:
        conn.execute('INSERT OR REPLACE INTO documents VALUES (?,?)', (name, json.dumps(value, ensure_ascii=False)))
        conn.execute('UPDATE revisions SET value=value+1 WHERE id=1')

def revision(folder):
    with connection(folder) as conn:
        return conn.execute('SELECT value FROM revisions WHERE id=1').fetchone()[0]

def snapshot(folder):
    with connection(folder) as conn:
        return {name: json.loads(body) for name, body in conn.execute('SELECT name,body FROM documents')}
