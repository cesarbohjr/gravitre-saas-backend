"""Synthetic evidence-contract tests; these are not product benchmark results."""
from copy import deepcopy
from datetime import datetime,timezone
import hashlib,json,wave
from pathlib import Path
import pytest
from app.services.conversation_benchmark_evidence import evaluate,protocol_hash,template,tasks,RUBRICS

@pytest.fixture
def captured(tmp_path):
    run=template();run.update(benchmark_at=datetime.now(timezone.utc).isoformat(),gravitre_sha='a'*40,environment_fingerprint='e'*64,blind_review_attested=True,named_review_ref='f'*64)
    run['reference']={'product':'ChatGPT','observed_at':run['benchmark_at'],'model':'unit contract fixture','voice_mode':'unit fixture','access_and_feature_limits':'Not an actual product capture'}
    taskmap={t['id']:t for t in tasks()}
    for n,row in enumerate(run['trials']):
        task=taskmap[row['task_id']]
        trace={'task_id':row['task_id'],'system_label':row['system_label'],'environment_fingerprint':'e'*64,'capture_method':'observed_product_session','completed':True,'events':[{'kind':'output','at_ms':1}]}
        file=tmp_path/f'{n}.json';file.write_text(json.dumps(trace))
        artifacts=[{'path':file.name,'sha256':hashlib.sha256(file.read_bytes()).hexdigest(),'kind':'application/json'}]
        if task['channel']=='voice' or task['cross_modal']:
            audio=tmp_path/f'{n}.wav'
            with wave.open(str(audio),'wb') as w:w.setnchannels(1);w.setsampwidth(2);w.setframerate(8000);w.writeframes(bytes([n%255,0])*8000)
            artifacts.append({'path':audio.name,'sha256':hashlib.sha256(audio.read_bytes()).hexdigest(),'kind':'audio/wav'})
        row.update(comparable=True,capture_source='observed_product_session',artifacts=artifacts,latency_ms=100,completed=True,invariants={k:True for k in row['invariants']},raters=[{'rater_ref':str(i)*64,'scores':{k:4 for k in RUBRICS[task['dimension']]}} for i in (1,2)])
    return run,{'A':'gravitre','B':'chatgpt'},tmp_path


def score(captured):
    run,identity,root=captured
    return evaluate(run,identity=identity,evidence_root=root)


def test_complete_contract_scores_three_dimensions_without_equivalence_claim(captured):
    result=score(captured)
    assert result['status']=='PASS_MEASURED_SCOPE'
    assert set(result['dimensions'])=={'text','voice','execution'}
    assert result['whole_product_equivalence_claim'] is False
    assert 'unit contract fixture' not in json.dumps(result)


def test_unscored_template_cannot_certify(tmp_path):
    with pytest.raises(ValueError):evaluate(template(),identity={'A':'gravitre','B':'chatgpt'},evidence_root=tmp_path)

@pytest.mark.parametrize('mutation',[
 lambda r:r.update(protocol_hash='0'*64),
 lambda r:r.update(blind_review_attested=False),
 lambda r:r.update(gravitre_sha='unobserved'),
 lambda r:r['reference'].update(voice_mode=None),
 lambda r:r.update(trials=r['trials'][:-1]),
 lambda r:r['trials'].append(deepcopy(r['trials'][0])),
 lambda r:r['trials'][0].update(capture_source='fixture'),
 lambda r:r['trials'][0].update(comparable=None),
 lambda r:r['trials'][0].update(comparable=False),
 lambda r:r['trials'][0].update(latency_ms=True),
 lambda r:r['trials'][0].update(completed='true'),
 lambda r:r['trials'][0].update(invariants={}),
 lambda r:r['trials'][0].update(raters=r['trials'][0]['raters'][:1]),
 lambda r:r['trials'][0]['raters'][1].update(rater_ref='1'*64),
 lambda r:r['trials'][0]['raters'][0].update(scores={}),
 lambda r:r['trials'][0]['artifacts'][0].update(path='../escape.json'),
 lambda r:r['trials'][0]['artifacts'][0].update(sha256='0'*64),
 lambda r:r['trials'][0].update(artifacts=r['trials'][1]['artifacts']),
])
def test_missing_tampered_or_unblinded_evidence_is_rejected(captured,mutation):
    mutation(captured[0])
    with pytest.raises(ValueError):score(captured)


def test_security_failure_cannot_be_averaged_away(captured):
    run,_,_=captured
    row=next(r for r in run['trials'] if r['task_id']=='G02:text' and r['system_label']=='A')
    row['invariants'][next(iter(row['invariants']))]=False
    result=score(captured)
    assert result['status']=='NOT_CERTIFIED' and result['dimensions']['execution']['status']=='FAIL'


def test_voice_requires_actual_audio_file_and_all_recorded_dimensions(captured):
    run,_,root=captured
    row=next(r for r in run['trials'] if r['task_id']=='V01:voice')
    row['artifacts']=[a for a in row['artifacts'] if a['kind']!='audio/wav']
    with pytest.raises(ValueError,match='modality'):score(captured)


def test_noncomparable_voice_is_a_gap_and_never_text_proxy_success(captured):
    for row in captured[0]['trials']:
        if row['task_id'] in {'V01:voice','V02:voice','X02:voice'}:row.update(comparable=False,gap_reason='Reference voice unavailable')
    result=score(captured)
    assert result['status']=='NOT_CERTIFIED' and result['dimensions']['voice']['status']=='NOT_READY'
    assert result['gaps']


def test_truncated_wav_cannot_certify_even_with_matching_file_hash(captured):
    run,_,root=captured
    artifact=next(a for row in run['trials'] for a in row['artifacts'] if a['kind']=='audio/wav')
    path=root/artifact['path']
    path.write_bytes(path.read_bytes()[:100])
    artifact['sha256']=hashlib.sha256(path.read_bytes()).hexdigest()
    with pytest.raises(ValueError,match='recorded_audio_truncated'):score(captured)
