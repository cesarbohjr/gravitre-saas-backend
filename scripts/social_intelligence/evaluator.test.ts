import test from 'node:test';
import assert from 'node:assert/strict';
import {CRITERIA,parseVerdict,verdictPasses,validateBundle,runEvaluation,classifyEvaluationError} from './evaluator.ts';
const good=Object.fromEntries(CRITERIA.map(k=>[k,true]));
const bundle:any={schema:1,source_sha:'a'.repeat(40),source_dirty:false,source_hashes:{},data_scope:'fixed_synthetic_only',scope:'synthetic',profiles:[{role:'DEFAULT',channel:'text',path:'unified',system:'s'},{role:'DEFAULT',channel:'voice',path:'unified',system:'s'}],cases:[{id:'c',messages:[{role:'user',content:'synthetic'}],expect:'help',dialogue:'d'}]};
test('verdict requires every exact boolean criterion',()=>{
 assert.ok(verdictPasses(parseVerdict(JSON.stringify(good))));
 for(const key of CRITERIA){const v={...good,[key]:false};assert.equal(verdictPasses(parseVerdict(JSON.stringify(v))),false);}
 for(const value of [{},{...good,extra:true},{...good,empathy:'true'},null,[]])assert.throws(()=>parseVerdict(JSON.stringify(value)));
});
test('unpaired, duplicate and dirty bundles cannot be evaluated',()=>{
 validateBundle(bundle);
 assert.throws(()=>validateBundle({...bundle,source_dirty:true}));
 assert.throws(()=>validateBundle({...bundle,profiles:bundle.profiles.slice(0,1)}));
 assert.throws(()=>validateBundle({...bundle,profiles:[...bundle.profiles,bundle.profiles[0]]}));
});
test('missing credential reports NOT RUN, with no network',async()=>{
 const rows:any[]=[];await runEvaluation(bundle,{},r=>rows.push(r));
 assert.equal(rows[0].status,'NOT RUN');
});
test('provider authorization failure stops workload and never logs provider bodies or keys',async()=>{
 const original=globalThis.fetch;const rows:any[]=[];
 globalThis.fetch=async()=>new Response('sensitive provider response', {status:401});
 try {const result=await runEvaluation(bundle,{ANTHROPIC_API_KEY:'test-secret'},r=>rows.push(r));assert.equal(result?.status,'FAIL');assert.equal(result?.errors,1);assert.ok(!JSON.stringify(rows).includes('sensitive'));assert.ok(!JSON.stringify(rows).includes('test-secret'));} finally{globalThis.fetch=original;}
});
test('real runner pairs text/voice, parses judge and fails any criterion',async()=>{
 const original=globalThis.fetch;const rows:any[]=[];
 globalThis.fetch=async(_url,options)=>{
  const req=JSON.parse(String(options?.body));
  const isJudge=typeof req.system==='string';
  return Response.json({stop_reason:'end_turn',content:[{type:'text',text:isJudge?JSON.stringify({...good,governance:false}):'Synthetic response.'}],usage:{input_tokens:1,output_tokens:2}});
 };
 try{const result=await runEvaluation(bundle,{ANTHROPIC_API_KEY:'test'},r=>rows.push(r));assert.equal(result?.status,'FAIL');assert.equal(result?.failed,1);assert.equal(result?.requests,3);assert.equal(rows[1].text,'Synthetic response.');assert.equal(rows[1].voice,'Synthetic response.');} finally{globalThis.fetch=original;}
});
test('dialogue guidance retains each runtime paths actual message priority',async()=>{
 const original=globalThis.fetch;const seen:any[]=[];
 const profiles=['unified','classical'].flatMap(path=>['text','voice'].map(channel=>({role:'DEFAULT',path,channel,system:path})));
 globalThis.fetch=async(_url,options)=>{
  const req=JSON.parse(String(options?.body));seen.push(req);
  return Response.json({stop_reason:'end_turn',content:[{type:'text',text:typeof req.system==='string'?JSON.stringify(good):'Reply.'}]});
 };
 try{await runEvaluation({...bundle,profiles},{ANTHROPIC_API_KEY:'test'},()=>{});
  for(const req of seen.filter(r=>Array.isArray(r.system))){
   const classical=req.system[0].text==='classical';
   assert.equal(req.system.some((s:any)=>s.text==='d'),classical);
   assert.equal(req.messages.at(-1).content.includes('\n\nd'),!classical);
  }
 }finally{globalThis.fetch=original;}
});

test('sanitized categories exclude sensitive provider exception messages',()=>{
 assert.equal(classifyEvaluationError(new Error('provider_http_503')),'provider_http_503');
 assert.equal(classifyEvaluationError(new Error('invalid_judge')),'invalid_judge');
 assert.equal(classifyEvaluationError(new Error('truncated_response')),'truncated_response');
 assert.equal(classifyEvaluationError(new DOMException('secret timeout','TimeoutError')),'provider_timeout');
 assert.equal(classifyEvaluationError(new TypeError('secret endpoint and token')),'provider_network_error');
 assert.equal(classifyEvaluationError(new Error('secret raw provider body')),'evaluation_error');
});
test('transient HTTP 503 retries within three attempts and succeeds',async()=>{
 const original=globalThis.fetch;let calls=0;const rows:any[]=[];
 globalThis.fetch=async(_url,options)=>{
  calls++;
  if(calls===1)return new Response('sensitive provider response',{status:503});
  const req=JSON.parse(String(options?.body));
  return Response.json({stop_reason:'end_turn',content:[{type:'text',text:typeof req.system==='string'?JSON.stringify(good):'Synthetic reply.'}]});
 };
 try {
  const result=await runEvaluation(bundle,{ANTHROPIC_API_KEY:'test'},r=>rows.push(r));
  assert.equal(result?.status,'PASS');assert.equal(result?.requests,4);assert.equal(calls,4);
  assert.ok(!JSON.stringify(rows).includes('sensitive provider response'));
 } finally {globalThis.fetch=original;}
});
