"""Reconstruct and strictly compare a production-equivalent schema on loopback only."""
import json
from pathlib import Path
import sys
import psycopg
from psycopg.rows import dict_row
from replay import local_url
from reconcile import render, keyed

ROOT=Path(__file__).parent


def snapshot(conn):
    inventory=conn.execute((ROOT/'inventory.sql').read_text()).fetchone()['inventory']
    columns=conn.execute((ROOT/'columns.sql').read_text()).fetchall()
    return inventory,columns


def normalize(value):
    if isinstance(value,str): return value.replace('\r\n','\n')
    if isinstance(value,list): return sorted((normalize(x) for x in value),key=lambda x:json.dumps(x,sort_keys=True))
    if isinstance(value,dict): return {k:normalize(v) for k,v in value.items()}
    return value


def main():
    url=local_url(sys.argv[1]); folder=Path(sys.argv[2]); report=Path(sys.argv[3])
    prod=json.loads((folder/'production-inventory.json').read_text())
    prod_columns=json.loads((folder/'production-columns.json').read_text())
    with psycopg.connect(url,autocommit=True,row_factory=dict_row) as conn:
        before,cols=snapshot(conn)
        sql=[] if '--verify-only' in sys.argv[4:] else render(prod,before,prod_columns,cols)
        with conn.transaction():
            for statement in sql: conn.execute(statement,prepare=False)
        after,cols=snapshot(conn)
        differences={}
        for category in prod:
            if normalize(prod[category])!=normalize(after[category]): differences[category]='mismatch'
        if normalize(prod_columns)!=normalize(cols): differences['columns']='mismatch'
        result={'passed':not differences,'differences':differences,
                'columns':len(cols),'objects':{kind:len(rows or []) for kind,rows in after.items()},
                'reconciliation_statement_count':len(sql),'production_mutated':False}
        report.parent.mkdir(parents=True,exist_ok=True)
        report.write_text(json.dumps(result,indent=2)+'\n')
        print(json.dumps(result,indent=2))
        if differences: raise SystemExit('Schema parity failed')


if __name__=='__main__': main()
