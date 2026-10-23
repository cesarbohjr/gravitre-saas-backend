"""Real PostgreSQL acceptance of the shipped recommendation claim/confirmation code.

No vendor is called. A durable local write probe represents dispatch. Source AST
loading avoids booting unrelated application integrations; tested function bodies
are compiled unchanged from backend/app/operators/governed_recommendations.py.
"""
import ast
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
from types import SimpleNamespace
from threading import Barrier
from uuid import UUID, uuid4

from fastapi import HTTPException
import psycopg
from psycopg import sql
from psycopg.rows import dict_row
from replay import local_url


class Query:
    def __init__(self,url,table): self.url,self.table,self.filters=url,table,[]
    def update(self,values): self.values=values; return self
    def eq(self,key,value): self.filters.append((key,'=',value)); return self
    def gt(self,key,value): self.filters.append((key,'>',value)); return self
    def execute(self):
        query=sql.SQL('UPDATE public.{} SET {} WHERE {} RETURNING *').format(
            sql.Identifier(self.table),
            sql.SQL(',').join(sql.SQL('{}=%s').format(sql.Identifier(k)) for k in self.values),
            sql.SQL(' AND ').join(sql.SQL('{} {} %s').format(sql.Identifier(k),sql.SQL(op)) for k,op,v in self.filters))
        with psycopg.connect(self.url,row_factory=dict_row) as conn:
            conn.execute('SET LOCAL ROLE service_role')
            rows=conn.execute(query,[*self.values.values(),*(v for k,op,v in self.filters)]).fetchall()
        return SimpleNamespace(data=rows)


class Client:
    def __init__(self,url): self.url=url
    def table(self,name):
        if name!='operator_recommendations': raise AssertionError(name)
        return Query(self.url,name)


def load_code(client,dispatcher):
    source=Path('backend/app/operators/governed_recommendations.py').read_text()
    tree=ast.parse(source)
    functions=[]
    for node in tree.body:
        if isinstance(node,ast.FunctionDef) and node.name in {'_require_org','_single_claim','confirm'}:
            node.decorator_list=[]; node.returns=None
            for arg in node.args.args: arg.annotation=None
            functions.append(node)
    assert len(functions)==3
    scope={'HTTPException':HTTPException,'datetime':datetime,'timezone':timezone,'UUID':UUID,
           '_ALLOWED_TYPES':{'workflow-param-suggester'},'shared_service_client':lambda *a:client,
           'create_client':None,'_execute_workflow_with_context':dispatcher}
    exec(compile(ast.fix_missing_locations(ast.Module(body=functions,type_ignores=[])),'shipped-confirmation-code','exec'),scope)
    return scope


def main():
    url=local_url(sys.argv[1]); report=Path(sys.argv[2]); checks=[]
    user,other,org,other_org=map(str,[uuid4(),uuid4(),uuid4(),uuid4()])
    def dispatch(**kwargs):
        with psycopg.connect(url) as conn:
            conn.execute('insert into recovery_acceptance.write_probe(actor_id) values (%s)',(kwargs['actor_id'],))
        return {'run_id':str(uuid4()),'status':'completed'}
    client=Client(url); scope=load_code(client,dispatch)
    with psycopg.connect(url,autocommit=True) as conn:
        conn.execute('CREATE SCHEMA recovery_acceptance')
        conn.execute('CREATE TABLE recovery_acceptance.write_probe(actor_id uuid)')
        # Isolated fixture IDs only; do not invoke unrelated onboarding triggers.
        with conn.transaction():
            conn.execute('SET LOCAL session_replication_role=replica')
            conn.execute('insert into auth.users(id) values (%s),(%s)',(user,other))
            conn.execute('insert into public.organizations(id,name,slug) values (%s,%s,%s),(%s,%s,%s)',(org,'recovery test',org,other_org,'recovery other',other_org))
    def seed(status='pending',expired=False,environment='production'):
        rec=str(uuid4())
        with psycopg.connect(url) as conn:
            conn.execute("""insert into public.operator_recommendations(id,org_id,operator_type,recommendation,status,created_by,expires_at)
            values (%s,%s,'workflow-param-suggester',%s::jsonb,%s,%s,now()+(%s::interval))""",
            (rec,org,json.dumps({'workflow_id':str(uuid4()),'parameters':{},'environment':environment}),status,user,'-1 hour' if expired else '1 hour'))
        return rec
    def confirm(rec,actor=user,tenant=org,yes=True):
        return scope['confirm']('workflow-param-suggester',SimpleNamespace(recommendation_id=rec,confirmed=yes),{'user_id':actor},tenant,'production',None)
    def blocked(fn,code=409):
        try: fn()
        except HTTPException as exc: assert exc.status_code==code,exc
        else: raise AssertionError('Expected fail-closed rejection')
    def probes():
        with psycopg.connect(url) as conn: return conn.execute('select count(*) from recovery_acceptance.write_probe').fetchone()[0]
    try:
        rec=seed()
        barrier=Barrier(12)
        def claim(_):
            barrier.wait(timeout=20)
            try:
                scope['_single_claim'](client,rec_id=rec,org_id=org,operator_type='workflow-param-suggester',status='claimed',user_id=user)
                return 1
            except HTTPException as exc: assert exc.status_code==409; return 0
        with ThreadPoolExecutor(max_workers=12) as pool: assert sum(pool.map(claim,range(12)))==1
        checks.append('12 independent PostgreSQL sessions: exactly one successful claimant')
        rec=seed(); blocked(lambda:confirm(rec,tenant=other_org)); blocked(lambda:confirm(rec,actor=other)); assert probes()==0
        checks.append('cross-tenant and wrong-user confirmation cannot dispatch')
        for role in ['anon','authenticated']:
            with psycopg.connect(url) as conn:
                try:
                    for privilege in ['SELECT','INSERT','UPDATE','DELETE']:
                        assert not conn.execute('select has_table_privilege(%s,%s,%s)',(role,'public.operator_recommendations',privilege)).fetchone()[0]
                    conn.execute(sql.SQL('SET LOCAL ROLE {}').format(sql.Identifier(role)))
                    conn.execute('select * from public.operator_recommendations')
                except psycopg.errors.InsufficientPrivilege: pass
                else: raise AssertionError('Client accessed service-only approval table')
        checks.append('anon/authenticated cannot access or forge service-only recommendations')
        confirm(seed(),yes=False); blocked(lambda:confirm(seed(expired=True))); blocked(lambda:confirm(seed(environment='staging'))); assert probes()==0
        checks.append('rejected, expired and environment-mismatched confirmations produce zero writes')
        interrupted=seed()
        def interrupt(**kwargs): raise TimeoutError('interrupted before dispatch')
        scope['_execute_workflow_with_context']=interrupt
        blocked(lambda:confirm(interrupted),503); blocked(lambda:confirm(interrupted)); assert probes()==0
        checks.append('interruption preserves consumed claim and blocks retry without writes')
        scope['_execute_workflow_with_context']=dispatch
        result=confirm(seed()); assert result['verified'] is False and result['status']=='running' and probes()==1
        checks.append('provider completion without independent verification stays nonterminal and unverified')
        uncertain=seed()
        def uncertain_dispatch(**kwargs): dispatch(**kwargs); raise TimeoutError('response lost after write')
        scope['_execute_workflow_with_context']=uncertain_dispatch
        blocked(lambda:confirm(uncertain),503); before=probes();blocked(lambda:confirm(uncertain));assert probes()==before
        checks.append('ambiguous write response cannot cause duplicate dispatch on retry')
        report.parent.mkdir(parents=True,exist_ok=True)
        report.write_text(json.dumps({'passed':True,'checks':checks,'live_provider_writes':0,'scope':'shipped confirmation code with real PostgreSQL and isolated dispatch probe'},indent=2)+'\n')
        print(report.read_text())
    finally:
        with psycopg.connect(url,autocommit=True) as conn:
            with conn.transaction():
                conn.execute('SET LOCAL session_replication_role=replica')
                conn.execute('delete from public.operator_recommendations where org_id in (%s,%s)',(org,other_org))
                conn.execute('delete from public.organizations where id in (%s,%s)',(org,other_org))
                conn.execute('delete from auth.users where id in (%s,%s)',(user,other))
            conn.execute('DROP SCHEMA recovery_acceptance CASCADE')


if __name__=='__main__': main()
