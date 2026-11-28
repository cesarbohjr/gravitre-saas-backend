"""Exact-SHA cohort aggregation. Matching labels do not equate acoustic and protocol measurements."""
import json,sys,math,statistics
from pathlib import Path

EXPECTED={('interrupt-recover-v1',i) for i in range(1,21)}
def compare(a,b):
    if a.get('sourceSha')!=b.get('sourceSha') or not a.get('sourceSha'):
        raise ValueError('source mismatch')
    if any(d.get('synthetic') is not True or d.get('fixture')!='interrupt-recover-v1' for d in (a,b)):
        raise ValueError('fixture or evidence scope mismatch')
    def index(doc):
        rows=doc['trials']; result={(r['workloadId'],r['repeat']):r for r in rows}
        if len(result)!=len(rows): raise ValueError('duplicate workload')
        if set(result)!=EXPECTED: raise ValueError('incomplete or unexpected cohort')
        return result
    x,y=index(a),index(b)
    native_fail={f['trial'] for f in a.get('failures',[])}
    pairs=[]
    for k in sorted(EXPECTED):
        row={'workloadId':k[0],'repeat':k[1],'nativePassed':not x[k].get('error') and k[1] not in native_fail,'speechEnginePassed':y[k].get('completed') is True and y[k].get('cancelled') is True,'metrics':{}}
        for m in ('firstAudioMs','interruptResidualMs','secondAudioMs','firstTextMs','secondTextMs'):
            u,v=x[k].get(m),y[k].get(m)
            ok=all(type(z) in (int,float) and math.isfinite(z) and z>=0 for z in (u,v))
            row['metrics'][m]={'native':u,'speechEngine':v,'comparable':False,'reason':'different evidence scopes' if ok else 'missing measurement'}
        pairs.append(row)
    def stats(rows,key):
        values=sorted(r.get(key) for r in rows if type(r.get(key)) in (int,float) and math.isfinite(r[key]) and r[key]>=0)
        return {'n':len(values),'p50':values[math.ceil(len(values)*.5)-1] if values else None,'p95':values[math.ceil(len(values)*.95)-1] if values else None}
    return {'sourceSha':a['sourceSha'],'pairs':pairs,'cohortSize':len(pairs),'nativePassed':sum(r['nativePassed'] for r in pairs),'speechEnginePassed':sum(r['speechEnginePassed'] for r in pairs),'nativeAcoustic':{m:stats(x.values(),m) for m in ('firstAudioMs','interruptResidualMs','secondAudioMs')},'speechProtocol':{m:stats(y.values(),m) for m in ('firstTextMs','secondTextMs')},'promotionEligible':False,'status':'BLOCKED_PROTOCOL_VS_ACOUSTIC'}
if __name__=='__main__':
    print(json.dumps(compare(*(json.loads(Path(p).read_text()) for p in sys.argv[1:3])),indent=2))
