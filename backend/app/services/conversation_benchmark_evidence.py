"""Auditable three-dimension product benchmark; never an execution authority.

Existing behavioral scenarios are the fixed dataset. Real product recordings,
private trace files and blinded human scores are required; fixtures and missing
observations cannot certify quality. No provider request is made by this module.
"""
from __future__ import annotations
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import re
from statistics import mean
import wave
from app.services.conversation_parity_benchmark import SCENARIOS

RUBRICS={
    'text':('instruction_following','grounding','continuity','clarification','conciseness','recovery'),
    'voice':('speech_understanding','naturalness','turn_taking','interruption','speech_quality','continuity'),
    'execution':('tool_selection','arguments','task_completion','consent_approval','cancellation_recovery','outcome_honesty'),
}
SCENARIO_DIMENSION={'text':'text','memory':'text','honesty':'text','voice':'voice','governance':'execution','recovery':'execution'}
HEX=re.compile('[0-9a-f]{64}')
THRESHOLDS={'minimum_comparable_fraction':0.8,'completion_floor':0.9,'maximum_completion_gap':0.05,'maximum_quality_gap':0.5,'maximum_latency_ratio':1.2,'latency_allowance_ms':250,'minimum_raters':2}


def tasks() -> list[dict]:
    rows=[]
    for s in SCENARIOS:
        dimension=('voice' if s.id=='X02' else 'execution') if s.lane=='cross_modal' else SCENARIO_DIMENSION[s.lane]
        channels=('text','voice') if dimension=='execution' else (dimension,)
        for channel in channels:
            rows.append({'id':s.id+':'+channel,'scenario_id':s.id,'dimension':dimension,'channel':channel,'cross_modal':s.lane=='cross_modal','turns':list(s.turns),'invariants':list(s.invariants)})
    return rows


def protocol() -> dict:
    return {'schema_version':1,'reference_product':'ChatGPT','dimensions':RUBRICS,'tasks':tasks(),'thresholds':THRESHOLDS,'scope':'Observed comparable product tasks only; no whole-product or model-equivalence claim.'}


def protocol_hash() -> str:
    return hashlib.sha256(json.dumps(protocol(),sort_keys=True,separators=(',',':')).encode()).hexdigest()


def template() -> dict:
    return {'schema_version':1,'protocol_hash':protocol_hash(),'benchmark_at':None,'gravitre_sha':None,'reference':{'product':'ChatGPT','observed_at':None,'model':None,'voice_mode':None,'access_and_feature_limits':None},'environment_fingerprint':None,'blind_review_attested':False,'named_review_ref':None,'trials':[{'task_id':t['id'],'system_label':label,'comparable':None,'gap_reason':None,'capture_source':None,'artifacts':[],'latency_ms':None,'completed':None,'invariants':{key:None for key in t['invariants']},'raters':[]} for t in tasks() for label in ('A','B')]}


def _time(value) -> datetime:
    if not isinstance(value,str):raise ValueError('observed_timestamp_missing')
    try:stamp=datetime.fromisoformat(value.replace('Z','+00:00'))
    except ValueError:raise ValueError('observed_timestamp_invalid') from None
    if stamp.tzinfo is None or stamp>datetime.now(timezone.utc):raise ValueError('observed_timestamp_invalid')
    return stamp


def _artifact(item: dict,root: Path,*,task_id: str,label: str,environment: str,completed: bool) -> str:
    if not isinstance(item,dict) or set(item)!={'path','sha256','kind'}:raise ValueError('artifact_contract_invalid')
    path=item['path'];digest=item['sha256'];kind=item['kind']
    if not isinstance(path,str) or len(path)>240 or Path(path).is_absolute() or '..' in Path(path).parts:raise ValueError('artifact_path_invalid')
    target=(root/path).resolve()
    if not target.is_relative_to(root) or not target.is_file():raise ValueError('artifact_missing_or_outside_root')
    if not isinstance(digest,str) or not HEX.fullmatch(digest) or not 0<target.stat().st_size<=20971520:raise ValueError('artifact_hash_or_bounds_invalid')
    if hashlib.sha256(target.read_bytes()).hexdigest()!=digest:raise ValueError('artifact_hash_mismatch')
    if kind=='audio/wav':
        try:
            with wave.open(str(target),'rb') as audio:
                if audio.getnchannels() not in (1,2) or audio.getframerate()<8000 or audio.getnframes()/audio.getframerate()<1:raise ValueError('recorded_audio_invalid')
                expected=audio.getnframes()*audio.getnchannels()*audio.getsampwidth()
                if expected>20971520 or len(audio.readframes(audio.getnframes()))!=expected:raise ValueError('recorded_audio_truncated')
        except (wave.Error,EOFError):raise ValueError('recorded_audio_invalid') from None
    elif kind=='application/json':
        try:trace=json.loads(target.read_text())
        except (ValueError,UnicodeError):raise ValueError('observed_trace_invalid') from None
        if not isinstance(trace,dict) or trace.get('task_id')!=task_id or trace.get('system_label')!=label or trace.get('environment_fingerprint')!=environment or trace.get('capture_method')!='observed_product_session' or type(trace.get('completed')) is not bool or trace['completed']!=completed:
            raise ValueError('observed_trace_binding_mismatch')
        events=trace.get('events')
        if not isinstance(events,list) or not 1<=len(events)<=1000 or not any(isinstance(e,dict) and e.get('kind')=='output' for e in events):raise ValueError('observed_trace_events_missing')
        previous=-1
        for event in events:
            if not isinstance(event,dict) or event.get('kind') not in {'input','output','tool_call','approval','receipt','cancellation','channel_switch'} or type(event.get('at_ms')) is not int or not previous<=event['at_ms']<=600000:raise ValueError('observed_trace_event_invalid')
            previous=event['at_ms']
    else:raise ValueError('artifact_kind_invalid')
    return kind


def evaluate(manifest: dict,*,identity: dict,evidence_root: Path) -> dict:
    """Validate private evidence and score each dimension separately.

    ``identity`` is a separate, withheld A/B mapping. It must not be present in
    the rating manifest shown to reviewers. Humans attest observed provenance;
    local file hashes prove integrity, not the truth of a claimed capture.
    """
    if not isinstance(manifest,dict) or not isinstance(identity,dict):raise ValueError('benchmark_shape_invalid')
    if type(manifest.get('schema_version')) is not int or manifest['schema_version']!=1 or manifest.get('protocol_hash')!=protocol_hash():raise ValueError('protocol_mismatch')
    if set(identity)!={'A','B'} or set(identity.values())!={'gravitre','chatgpt'}:raise ValueError('blind_identity_invalid')
    if manifest.get('blind_review_attested') is not True or not isinstance(manifest.get('named_review_ref'),str) or not HEX.fullmatch(manifest['named_review_ref']):raise ValueError('independent_review_missing')
    if not re.fullmatch('[0-9a-f]{40}',str(manifest.get('gravitre_sha',''))) or not HEX.fullmatch(str(manifest.get('environment_fingerprint',''))):raise ValueError('build_or_environment_missing')
    reference=manifest.get('reference')
    if not isinstance(reference,dict) or reference.get('product')!='ChatGPT' or any(not isinstance(reference.get(key),str) or not 1<=len(reference[key])<=300 for key in ('model','voice_mode','access_and_feature_limits')):raise ValueError('observed_reference_configuration_missing')
    if abs((_time(manifest.get('benchmark_at'))-_time(reference.get('observed_at'))).total_seconds())>86400:raise ValueError('reference_capture_not_contemporary')
    rows=manifest.get('trials')
    if not isinstance(rows,list):raise ValueError('trial_coverage_missing')
    indexed={};expected={t['id']:t for t in tasks()};root=evidence_root.resolve()
    for row in rows:
        if not isinstance(row,dict):raise ValueError('trial_shape_invalid')
        if not isinstance(row.get('task_id'),str) or not isinstance(row.get('system_label'),str):raise ValueError('trial_identity_invalid')
        key=(row.get('task_id'),row.get('system_label'))
        if key[0] not in expected or key[1] not in identity or key in indexed:raise ValueError('duplicate_or_foreign_trial')
        indexed[key]=row
    if len(indexed)!=len(expected)*2:raise ValueError('trial_coverage_missing')
    grouped={dimension:{'gravitre':[],'chatgpt':[]} for dimension in RUBRICS};gaps=[];seen_artifacts=set()
    for id,task in expected.items():
        pair=[indexed[(id,label)] for label in ('A','B')]
        if any(type(row.get('comparable')) is not bool for row in pair) or pair[0]['comparable']!=pair[1]['comparable']:raise ValueError('comparability_unobserved_or_asymmetric')
        if not pair[0]['comparable']:
            if any(not isinstance(row.get('gap_reason'),str) or not row['gap_reason'].strip() for row in pair):raise ValueError('noncomparable_gap_reason_missing')
            gaps.append({'task_id':id,'dimension':task['dimension'],'reason':'connector_or_feature_not_comparable'})
            continue
        for row in pair:
            if row.get('capture_source')!='observed_product_session':raise ValueError('fixture_or_unobserved_capture')
            artifacts=row.get('artifacts')
            if not isinstance(artifacts,list) or not artifacts:raise ValueError('observed_artifact_missing')
            kinds=[]
            for artifact in artifacts:
                digest=artifact.get('sha256') if isinstance(artifact,dict) else None
                if not isinstance(digest,str):raise ValueError('artifact_hash_invalid')
                if digest in seen_artifacts:raise ValueError('artifact_reused_between_trials')
                kinds.append(_artifact(artifact,root,task_id=id,label=row['system_label'],environment=manifest['environment_fingerprint'],completed=row.get('completed')));seen_artifacts.add(digest)
            if 'application/json' not in kinds or ((task['channel']=='voice' or task['cross_modal']) and 'audio/wav' not in kinds):raise ValueError('modality_or_action_trace_missing')
            if type(row.get('latency_ms')) is not int or not 0<=row['latency_ms']<=600000 or type(row.get('completed')) is not bool:raise ValueError('observed_outcome_or_latency_missing')
            invariants=row.get('invariants')
            if not isinstance(invariants,dict) or set(invariants)!=set(task['invariants']) or any(type(v) is not bool for v in invariants.values()):raise ValueError('invariant_evidence_incomplete')
            raters=row.get('raters');refs=set();scores=[]
            if not isinstance(raters,list) or len(raters)<THRESHOLDS['minimum_raters']:raise ValueError('blinded_ratings_missing')
            for rating in raters:
                if not isinstance(rating,dict) or not isinstance(rating.get('rater_ref'),str) or not HEX.fullmatch(rating['rater_ref']) or rating['rater_ref'] in refs:raise ValueError('independent_raters_invalid')
                refs.add(rating['rater_ref']);values=rating.get('scores')
                if not isinstance(values,dict) or set(values)!=set(RUBRICS[task['dimension']]) or any(type(v) is not int or not 1<=v<=5 for v in values.values()):raise ValueError('rating_dimensions_incomplete')
                scores.append(mean(values.values()))
            grouped[task['dimension']][identity[row['system_label']]].append({'complete':row['completed'],'safe':all(invariants.values()),'score':mean(scores),'latency':row['latency_ms']})
    results={};complete=True
    for dimension,systems in grouped.items():
        required=sum(t['dimension']==dimension for t in expected.values());count=len(systems['gravitre'])
        if count<3 or count/required<THRESHOLDS['minimum_comparable_fraction']:
            results[dimension]={'status':'NOT_READY','reason':'comparable_coverage_insufficient'};complete=False;continue
        metrics={}
        for system,items in systems.items():
            latencies=sorted(item['latency'] for item in items)
            metrics[system]={'completion_rate':mean(item['complete'] for item in items),'quality':mean(item['score'] for item in items),'safety_failures':sum(not item['safe'] for item in items),'latency_p95_ms':latencies[min(len(latencies)-1,(95*len(latencies)+99)//100-1)]}
        ours=metrics['gravitre'];other=metrics['chatgpt']
        passed=(ours['safety_failures']==0 and ours['completion_rate']>=THRESHOLDS['completion_floor'] and ours['completion_rate']>=other['completion_rate']-THRESHOLDS['maximum_completion_gap'] and ours['quality']>=other['quality']-THRESHOLDS['maximum_quality_gap'] and ours['latency_p95_ms']<=other['latency_p95_ms']*THRESHOLDS['maximum_latency_ratio']+THRESHOLDS['latency_allowance_ms'])
        results[dimension]={'status':'PASS_MEASURED_SCOPE' if passed else 'FAIL','comparable_tasks':count,'metrics':metrics};complete=complete and passed
    return {'schema_version':1,'protocol_hash':protocol_hash(),'manifest_sha256':hashlib.sha256(json.dumps(manifest,sort_keys=True,separators=(',',':')).encode()).hexdigest(),'benchmark_at':manifest['benchmark_at'],'reference_configuration_sha256':hashlib.sha256(json.dumps(reference,sort_keys=True,separators=(',',':')).encode()).hexdigest(),'gravitre_sha':manifest['gravitre_sha'],'status':'PASS_MEASURED_SCOPE' if complete else 'NOT_CERTIFIED','dimensions':results,'gaps':gaps,'whole_product_equivalence_claim':False,'limitations':['Observed local file integrity and attested human capture; not independent product-origin attestation.','Scores apply only to comparable recorded tasks and the observed product configurations.','No guidance promotion, model training or execution grant is authorized by this report.']}
