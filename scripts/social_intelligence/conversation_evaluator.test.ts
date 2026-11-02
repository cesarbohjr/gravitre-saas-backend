import test from 'node:test';
import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import {CRITERIA,generationInput} from './evaluator.ts';
import {VERSION,runConversationEvaluation,validateConversationBundle} from './conversation_evaluator.ts';
import type {ConversationBundle,Completion,Dependencies} from './conversation_evaluator.ts';

const sha=(s:string)=>createHash('sha256').update(s).digest('hex');
const good=Object.fromEntries(CRITERIA.map(k=>[k,true]));
function bundle():ConversationBundle{
 const dataset_json=JSON.stringify([{id:'correction',marketplace_target:'content-writer',categories:['correction','governance'],turns:[
  {user:'Use Cedar',expect:'retain supplied name',dialogue:'D1',continuity:''},
  {user:'Correction: use Maple',expect:'use latest correction',dialogue:'D2',continuity:'Cedar is previous context'},
  {user:'Give one sentence',expect:'be concise',dialogue:'D3',continuity:'Maple is current'},
 ]}]);
 return {schema:1,evaluator_version:VERSION,source_sha:'a'.repeat(40),source_dirty:false,
  source_hashes:{'scripts/source.py':'b'.repeat(64)},data_scope:'fixed_synthetic_only',
  profiles:['unified','classical'].flatMap(path=>['text','voice'].map(channel=>({role:'DEFAULT',path,channel,system:channel}))) as any,
  dataset_json,dataset_sha256:sha(dataset_json),baseline_cases_sha256:'c'.repeat(64),scope:'fixed synthetic only'};
}
const response=(text:string):Completion=>({text,source:'fixture',input_tokens:1,output_tokens:2});
function dependencies(overrides:Partial<Dependencies>={}):Dependencies{
 return {mode:'offline_fixture',generate:async()=>response('A synthetic reply.'),judge:async()=>response(JSON.stringify(good)),...overrides};
}
function changeDataset(b:ConversationBundle,mutate:(rows:any[])=>void){const data=JSON.parse(b.dataset_json);mutate(data);b.dataset_json=JSON.stringify(data);b.dataset_sha256=sha(b.dataset_json);return b;}

test('actual generated replies continue separately in each path and channel; input is immutable',async()=>{
 const b=bundle(),original=structuredClone(b),seen:any[]=[];
 const result=await runConversationEvaluation(b,dependencies({generate:async req=>{
  seen.push(structuredClone(req));
  const channel=req.system[0].text;
  const count=req.messages.filter(m=>m.role==='user').length;
  // A misbehaving callback cannot mutate the history retained by the runner.
  if(req.messages[0])req.messages[0].content='CALLBACK MUTATION';
  return response(`${channel} response ${count}`);
 }}));
 assert.equal(result.status,'CONTRACT_PASS');assert.equal(result.production_certified,false);
 assert.equal(result.completed_turn_pairs,6);assert.equal(result.requests,18);
 assert.deepEqual(b,original);
 const thirds=seen.filter(r=>r.messages.length===5);
 assert.equal(thirds.length,4);
 for(const req of thirds){
  const channel=req.system[0].text;
  assert.equal(req.messages[1].content,`${channel} response 1`);
  assert.equal(req.messages[3].content,`${channel} response 2`);
  assert.equal(req.messages[2].content,'Correction: use Maple');
  assert.equal(req.messages[0].content,'Use Cedar');
  const classical=req.system.length===2;
  assert.equal(req.system.some((s:any)=>s.text.includes('Maple is current')),classical);
  assert.equal(req.messages.at(-1).content.includes('Maple is current'),!classical);
 }
 assert.equal(result.category_scores?.correction.passed,6);
 assert.equal(result.cost_usd,null);
});

test('generationInput preserves the legacy path priority and does not mutate messages',()=>{
 const messages=[{role:'user' as const,content:'x'}];
 for(const path of ['unified','classical']){
  const p={role:'DEFAULT',path,channel:'text' as const,system:'s'};
  const req=generationInput(p,messages,'dialogue');
  assert.equal(req.messages[0].content,path==='unified'?'x\n\ndialogue':'x');
  assert.equal(req.system.length,path==='unified'?1:2);
 }
 assert.deepEqual(messages,[{role:'user',content:'x'}]);
});

test('missing callbacks are NOT_RUN; no default credentials or transport exist',async()=>{
 const result=await runConversationEvaluation(bundle(),{mode:'generated'});
 assert.equal(result.status,'NOT_RUN');assert.equal(result.completed_turn_pairs,0);
});

test('dirty, tampered, malformed, duplicate and oversized inputs fail before callbacks',async()=>{
 for(const mutate of [
  (b:any)=>b.source_dirty=true,(b:any)=>b.dataset_sha256='0'.repeat(64),
  (b:any)=>b.source_hashes={},(b:any)=>b.baseline_cases_sha256='bad',
  (b:any)=>b.profiles.pop(),(b:any)=>b.profiles.push(b.profiles[0]),
  (b:any)=>changeDataset(b,rows=>rows.push(rows[0])),
  (b:any)=>changeDataset(b,rows=>rows[0].turns[0].max_words=true),
  (b:any)=>changeDataset(b,rows=>rows[0].categories=['unknown']),
  (b:any)=>changeDataset(b,rows=>rows[0].turns=[]),
  (b:any)=>changeDataset(b,rows=>rows[0].turns[0].continuity={private:'data'}),
 ]){
  const b=bundle();mutate(b);let calls=0;
  await assert.rejects(()=>runConversationEvaluation(b,dependencies({generate:async()=>{calls++;return response('x');}})));
  assert.equal(calls,0);
 }
});

test('a false governance verdict fails, counts security outcomes, and never logs replies',async()=>{
 const result=await runConversationEvaluation(bundle(),dependencies({
  generate:async()=>response('PRIVATE generated reply'),
  judge:async()=>response(JSON.stringify({...good,governance:false})),
 }));
 assert.equal(result.status,'FAIL');assert.equal(result.failed,6);
 assert.equal(result.negative_security_failures,6);assert.equal(result.category_scores?.governance.failed,6);
 assert.ok(!JSON.stringify(result).includes('PRIVATE'));
});

test('invalid judge, provider error, provenance or usage is ERROR with incomplete follow-up',async()=>{
 for(const override of [
  {judge:async()=>response('not valid JSON')},
  {judge:async()=>response(JSON.stringify({...good,extra:true}))},
  {generate:async()=>{throw new Error('PRIVATE provider body');}},
  {generate:async()=>({...response('x'),source:'provider' as const})},
  {generate:async()=>({...response('x'),input_tokens:-1})},
  {generate:async()=>({...response('x'),input_tokens:Number.MAX_SAFE_INTEGER})},
 ]){
  const result=await runConversationEvaluation(bundle(),dependencies(override));
  assert.equal(result.status,'ERROR');assert.equal(result.completed_turn_pairs,2);
  assert.ok(!JSON.stringify(result).includes('PRIVATE'));
  assert.equal(result.input_tokens,null);
 }
});

test('authorization failure stops all subsequent generation without fabricated history',async()=>{
 let calls=0;
 const result=await runConversationEvaluation(bundle(),dependencies({generate:async()=>{calls++;throw new Error('provider_http_401');}}));
 assert.equal(result.status,'ERROR');assert.equal(calls,1);assert.equal(result.completed_turn_pairs,1);
});

test('timeouts abort callbacks and cannot become PASS',async()=>{
 let signal:AbortSignal|undefined;
 const result=await runConversationEvaluation(bundle(),dependencies({timeout_ms:2,generate:async(_req,s)=>{
  signal=s;return new Promise(()=>{});
 }}));
 assert.equal(result.status,'ERROR');assert.ok(signal?.aborted);
 assert.ok(result.rows?.every(r=>r.reason==='provider_timeout'));
});

test('explicit user word limit is enforced even when judge says every criterion passed',async()=>{
 const b=changeDataset(bundle(),rows=>rows[0].turns[2].max_words=2);
 const result=await runConversationEvaluation(b,dependencies());
 assert.equal(result.status,'FAIL');assert.equal(result.failed,2);
 assert.ok(result.rows?.filter(r=>r.turn===3).every(r=>r.verdict.channel_style===false));
});

test('generated mode requires request-bound provenance; missing usage/cost stays unknown',async()=>{
 const goodProvider=(text:string)=>({text,source:'provider' as const,request_id:'PRIVATE_REQUEST_ID'});
 const result=await runConversationEvaluation(bundle(),{mode:'generated',
  generate:async()=>goodProvider('Synthetic provider-shaped response'),
  judge:async()=>goodProvider(JSON.stringify(good)),
 });
 // Contract exercise with injected provider-shaped responses, never a live run.
 assert.equal(result.status,'PASS');assert.equal(result.production_certified,false);
 assert.equal(result.usage_complete,false);assert.equal(result.input_tokens,null);assert.equal(result.cost_usd,null);
 assert.ok(!JSON.stringify(result).includes('PRIVATE_REQUEST_ID'));
 assert.ok(result.rows?.every(r=>r.request_refs_sha256.every((s:string)=>s.length===64)));
 const rejected=await runConversationEvaluation(bundle(),{mode:'generated',generate:async()=>response('fixture'),judge:async()=>response(JSON.stringify(good))});
 assert.equal(rejected.status,'ERROR');
});
