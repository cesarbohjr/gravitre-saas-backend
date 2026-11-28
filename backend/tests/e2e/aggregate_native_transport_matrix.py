"""Report native configurations without claiming acoustic or production certification."""
import json,math,sys
from pathlib import Path
root,sha=sys.argv[1:]
expected={(c,t) for c in (10,20,40) for t in (None,0,40)}
results={}
def stats(values):
    v=sorted(x for x in values if type(x) in (float,int) and math.isfinite(x) and x>=0)
    return dict(n=len(v),p50=v[math.ceil(len(v)*.5)-1] if v else None,p95=v[math.ceil(len(v)*.95)-1] if v else None)
for path in Path(root).rglob('native-matrix-evidence.json'):
    d=json.loads(path.read_text())
    assert d['sourceSha']==sha and d['synthetic'] is True and d['fixture']=='interrupt-recover-v1'
    cfg=d['config']; key=(cfg['chunkMs'],cfg['targetMs'])
    assert key in expected and key not in results
    rows=d['trials']
    assert len(rows)==20 and {r['repeat'] for r in rows}==set(range(1,21))
    failed={f['trial'] for f in d['failures']}
    for row in rows:
        if row.get('error') or not all(type(row.get(m)) in (int,float) and math.isfinite(row[m]) for m in ('interruptResidualMs','firstAudioMs','secondAudioMs','secondGapMs','secondToneSpanMs')) or row.get('interruptResidualMs',999)>=300 or row.get('secondGapMs',999)>100 or row.get('secondToneSpanMs',0)<1500 or row.get('oldToneAfterSecond') is not False:
            failed.add(row['repeat'])
    results[key]={'config':cfg,'passed':20-len(failed),'failedRepeats':sorted(failed),'metrics':{m:stats(r.get(m) for r in rows) for m in ('firstAudioMs','interruptResidualMs','secondAudioMs','secondGapMs')},'jitterResidenceMs':stats(1000*s['jitterBufferDelay']/s['jitterBufferEmittedCount'] for r in rows for s in r.get('inbound',[]) if s.get('jitterBufferEmittedCount',0)>0 and isinstance(s.get('jitterBufferDelay'),(int,float))),'exactFrameResidenceMs':stats(s.get('residenceMs') for r in rows for s in r.get('server',[]) if s.get('boundary')=='native_write_enter')}
missing=expected-set(results)
report={'sourceSha':sha,'expectedTrials':180,'observedTrials':20*len(results),'missingConfigurations':[list(x) for x in sorted(missing,key=str)],'configurations':list(results.values()),'syntheticScreeningCandidates':[v['config'] for v in results.values() if v['passed']==20],'promotionEligible':False,'scope':'loopback synthetic only; matched frame residence is not internal queue depth or proof of clearing'}
print(json.dumps(report,indent=2))
if missing or not report['syntheticScreeningCandidates']:sys.exit(1)
