"""Generate staging-only schema reconciliation; never execute against production."""
import json
from pathlib import Path
import sys


def q(s):
    return '"'+s.replace('"','""')+'"'


def keyed(rows, *keys):
    return {tuple(r[k] for k in keys):r for r in rows}


def render(p,c,cols,local_cols):
    out=['SET check_function_bodies=off;']
    existing=keyed(local_cols,'relname','attname')
    for r in cols:
        key=(r['relname'],r['attname'])
        if key in existing:
            if r!=existing[key]: raise ValueError(f'Incompatible column {key}')
            continue
        sql=f'ALTER TABLE public.{q(key[0])} ADD COLUMN {q(key[1])} {r["data_type"]}'
        if r['default_expression'] is not None: sql+=' DEFAULT '+r['default_expression']
        if r['attnotnull']: sql+=' NOT NULL'
        out.append(sql+';')
    for kind in ['constraints','indexes']:
        old=keyed(c[kind],'table','name')
        for r in p[kind]:
            key=(r['table'],r['name'])
            if old.get(key)==r: continue
            if kind=='constraints':
                if key in old: out.append(f'ALTER TABLE public.{q(r["table"])} DROP CONSTRAINT {q(r["name"])};')
                out.append(f'ALTER TABLE public.{q(r["table"])} ADD CONSTRAINT {q(r["name"])} {r["definition"]};')
            else:
                if key in old: out.append(f'DROP INDEX public.{q(r["name"])};')
                out.append(r['definition']+';')
    want,have=keyed(p['functions'],'name','identity'),keyed(c['functions'],'name','identity')
    for name,args in have.keys()-want.keys(): out.append(f'DROP FUNCTION public.{q(name)}({args});')
    for key,r in want.items():
        old=have.get(key)
        if old and old['definition'].replace('\r\n','\n')==r['definition'].replace('\r\n','\n'): continue
        if old and r['name']=='domain_event_outbox_stats': out.append(f'DROP FUNCTION public.{q(r["name"])}({r["identity"]});')
        out.append(r['definition'].rstrip().rstrip(';')+';')
    want,have=keyed(p['policies'],'tablename','policyname'),keyed(c['policies'],'tablename','policyname')
    for key,r in have.items():
        if want.get(key)!=r: out.append(f'DROP POLICY {q(r["policyname"])} ON public.{q(r["tablename"])};')
    for key,r in want.items():
        if have.get(key)==r: continue
        sql=f'CREATE POLICY {q(r["policyname"])} ON public.{q(r["tablename"])} AS {r["permissive"]} FOR {r["cmd"]}'
        sql+=' TO '+','.join('PUBLIC' if role=='public' else q(role) for role in r['roles'])
        if r['qual'] is not None: sql+=' USING ('+r['qual']+')'
        if r['with_check'] is not None: sql+=' WITH CHECK ('+r['with_check']+')'
        out.append(sql+';')
    for r in p['triggers']:
        if r not in c['triggers']:
            out.append(f'DROP TRIGGER IF EXISTS {q(r["name"])} ON {q(r.get('schema','public'))}.{q(r["table"])};')
            out.append(r['definition']+';')
    privileges=dict(U='USAGE',a='INSERT',r='SELECT',w='UPDATE',d='DELETE',D='TRUNCATE',x='REFERENCES',t='TRIGGER',m='MAINTAIN',X='EXECUTE')
    for r in p.get('views') or []:
        out.append(f'CREATE OR REPLACE VIEW public.{q(r["name"])} AS '+r['definition'].rstrip().rstrip(';')+';')
        if r.get('options'): out.append(f'ALTER VIEW public.{q(r["name"])} SET ('+','.join(r['options'])+');')
    for kind in ['tables','functions','views','sequences']:
        for r in p.get(kind) or []:
            if kind=='tables':
                target='TABLE public.'+q(r['name'])
                out.append(f'ALTER TABLE public.{q(r["name"])} '+('ENABLE' if r['rls'] else 'DISABLE')+' ROW LEVEL SECURITY;')
                out.append(f'ALTER TABLE public.{q(r["name"])} '+('FORCE' if r['force_rls'] else 'NO FORCE')+' ROW LEVEL SECURITY;')
            elif kind=='views': target='TABLE public.'+q(r['name'])
            elif kind=='sequences': target='SEQUENCE public.'+q(r['name'])
            else: target=f'FUNCTION public.{q(r["name"])}({r["identity"]})'
            out.append(f'REVOKE ALL ON {target} FROM PUBLIC,anon,authenticated,service_role;')
            for entry in r.get('acl') or []:
                role,tail=entry.split('=',1); rights=tail.split('/',1)[0]
                for i,char in enumerate(rights):
                    if char=='*': continue
                    option=' WITH GRANT OPTION' if rights[i+1:i+2]=='*' else ''
                    out.append(f'GRANT {privileges[char]} ON {target} TO '+(q(role) if role else 'PUBLIC')+option+';')
            if kind=='functions' and r.get('acl') is None: out.append(f'GRANT EXECUTE ON {target} TO PUBLIC;')
    kinds={'r':'TABLES','S':'SEQUENCES','f':'FUNCTIONS'}
    for r in p.get('defaults') or []:
        target=f'ALTER DEFAULT PRIVILEGES FOR ROLE {q(r["role"])} IN SCHEMA {q(r["schema"])}'
        out.append(target+f' REVOKE ALL ON {kinds[r["type"]]} FROM PUBLIC,anon,authenticated,service_role,postgres;')
        for entry in r['acl']:
            role,tail=entry.split('=',1); rights=tail.split('/',1)[0]
            for i,char in enumerate(rights):
                if char=='*': continue
                option=' WITH GRANT OPTION' if rights[i+1:i+2]=='*' else ''
                out.append(target+f' GRANT {privileges[char]} ON {kinds[r["type"]]} TO '+(q(role) if role else 'PUBLIC')+option+';')
    out.append('SET check_function_bodies=on;')
    return out


if __name__=='__main__':
    *sources,dest=map(Path,sys.argv[1:])
    dest.write_text('\n'.join(render(*(json.loads(p.read_text()) for p in sources)))+'\n')
