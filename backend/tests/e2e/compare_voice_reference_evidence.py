"""Fail-closed evidence comparison; protocol and acoustic are not equivalent."""
import json,sys,math
from pathlib import Path
def compare(a,b):
    if a.get('sourceSha')!=b.get('sourceSha') or not a.get('sourceSha'):
        raise ValueError('source mismatch')
    def index(doc):
        rows=doc['trials']; result={(r['workloadId'],r['repeat']):r for r in rows}
        if len(result)!=len(rows): raise ValueError('duplicate workload')
        return result
    x,y=index(a),index(b)
    pairs=[]
    for k in sorted(x.keys() & y.keys()):
        row={'workloadId':k[0],'repeat':k[1],'metrics':{}}
        for m in ('firstAudioMs','interruptResidualMs','secondAudioMs','firstTextMs','secondTextMs'):
            u,v=x[k].get(m),y[k].get(m)
            ok=all(type(z) in (int,float) and math.isfinite(z) and z>=0 for z in (u,v))
            row['metrics'][m]={'native':u,'speechEngine':v,'comparable':False,'reason':'different evidence scopes' if ok else 'missing measurement'}
        pairs.append(row)
    return {'sourceSha':a['sourceSha'],'pairs':pairs,'unmatchedNative':len(x.keys()-y.keys()),'unmatchedSpeechEngine':len(y.keys()-x.keys()),'promotionEligible':False,'status':'BLOCKED_PROTOCOL_VS_ACOUSTIC'}
if __name__=='__main__':
    print(json.dumps(compare(*(json.loads(Path(p).read_text()) for p in sys.argv[1:3])),indent=2))
