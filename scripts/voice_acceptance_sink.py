"""Loopback-only, durable side-effect witness for isolated voice governance.

Every effect-endpoint attempt is recorded separately from deduplicated effects, so sink
idempotency cannot hide a duplicate application request. No messages are sent.
"""
import argparse
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
import secrets
import sqlite3
import time
import uuid


def connect(path):
    db = sqlite3.connect(str(path), timeout=10)
    db.execute('PRAGMA journal_mode=WAL')
    db.execute('CREATE TABLE IF NOT EXISTS attempts (id TEXT PRIMARY KEY, org_id TEXT, actor_id TEXT, logical_id TEXT, status INTEGER NOT NULL, created REAL NOT NULL)')
    db.execute('CREATE TABLE IF NOT EXISTS effects (id TEXT PRIMARY KEY, org_id TEXT NOT NULL, actor_id TEXT NOT NULL, logical_id TEXT NOT NULL UNIQUE, action TEXT NOT NULL, payload_sha256 TEXT NOT NULL, created REAL NOT NULL)')
    db.commit()
    return db


def audit(path):
    with connect(path) as db:
        return {
            'attempts': [dict(zip(('id', 'org_id', 'actor_id', 'logical_id', 'status'), row))
                         for row in db.execute('SELECT id,org_id,actor_id,logical_id,status FROM attempts ORDER BY created,id')],
            'effects': [dict(zip(('id', 'org_id', 'actor_id', 'logical_id', 'action', 'payload_sha256'), row))
                        for row in db.execute('SELECT id,org_id,actor_id,logical_id,action,payload_sha256 FROM effects ORDER BY created,id')],
            'scope': 'independent fixture HTTP attempts and durable effects; not a vendor account',
        }


def server(path, *, org, actor, token, port=0):
    if not all(isinstance(v, str) and v for v in (org, actor, token)):
        raise ValueError('explicit fixture scope and authentication required')
    connect(path).close()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_args):
            pass

        def respond(self, status, payload):
            body = json.dumps(payload).encode()
            self.send_response(status)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_POST(self):
            if self.path != '/effects':
                self.respond(404, {'error': 'route'})
                return
            if not secrets.compare_digest(self.headers.get('Authorization', ''), 'Bearer ' + token):
                with connect(path) as db:
                    db.execute('INSERT INTO attempts VALUES (?,?,?,?,?,?)', (str(uuid.uuid4()), None, None, None, 401, time.time()))
                self.respond(401, {'error': 'authentication'})
                return
            try:
                size = int(self.headers.get('Content-Length', '0'))
                if not 0 < size <= 16384:
                    raise ValueError()
                body = json.loads(self.rfile.read(size))
                if not isinstance(body, dict) or set(body) != {'org_id', 'actor_id', 'logical_id', 'action', 'payload'}:
                    raise ValueError()
                if not isinstance(body['logical_id'], str) or not 1 <= len(body['logical_id']) <= 160:
                    raise ValueError()
                if body['action'] != 'acceptance.note.create' or not isinstance(body['payload'], dict):
                    raise ValueError()
            except (ValueError, TypeError):
                with connect(path) as db:
                    db.execute('INSERT INTO attempts VALUES (?,?,?,?,?,?)', (str(uuid.uuid4()), None, None, None, 400, time.time()))
                self.respond(400, {'error': 'request'})
                return
            allowed = body['org_id'] == org and body['actor_id'] == actor
            with connect(path) as db:
                db.execute('BEGIN IMMEDIATE')
                db.execute('INSERT INTO attempts VALUES (?,?,?,?,?,?)',
                    (str(uuid.uuid4()), str(body['org_id']), str(body['actor_id']), body['logical_id'], 200 if allowed else 403, time.time()))
                if not allowed:
                    db.commit()
                    self.respond(403, {'error': 'scope'})
                    return
                existing = db.execute('SELECT id,payload_sha256 FROM effects WHERE logical_id=?', (body['logical_id'],)).fetchone()
                digest = hashlib.sha256(json.dumps(body['payload'], sort_keys=True, separators=(',', ':')).encode()).hexdigest()
                if existing and existing[1] != digest:
                    db.commit()
                    self.respond(409, {'error': 'idempotency_payload_changed'})
                    return
                effect_id = existing[0] if existing else str(uuid.uuid4())
                if not existing:
                    db.execute('INSERT INTO effects VALUES (?,?,?,?,?,?,?)',
                        (effect_id, org, actor, body['logical_id'], body['action'], digest, time.time()))
                db.commit()
            self.respond(200, {'effect_id': effect_id, 'replay': bool(existing)})

    return ThreadingHTTPServer(('127.0.0.1', port), Handler)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--db', required=True)
    parser.add_argument('--audit', action='store_true')
    parser.add_argument('--org')
    parser.add_argument('--actor')
    parser.add_argument('--port', type=int, default=8771)
    args = parser.parse_args()
    if args.audit:
        print(json.dumps(audit(args.db), indent=2))
    else:
        if os.environ.get('GRAVITRE_VOICE_ISOLATED') != '1':
            raise SystemExit('explicit isolation required')
        server(args.db, org=args.org, actor=args.actor,
            token=os.environ.get('ACCEPTANCE_SINK_TOKEN', ''), port=args.port).serve_forever()
