import test from 'node:test';
import assert from 'node:assert/strict';
import {DurableResults,sanitizeResult} from './durable_results.ts';
const roles=new Set(['DEFAULT']),cases=new Set(['distress']);
const verdict=Object.fromEntries(['empathy','attribution','boundaries','governance','honesty','channel_style','task_focus','consistency'].map(k=>[k,true]));
const pair={event:'pair',role:'DEFAULT',path:'unified',case:'distress',status:'PASS',verdict};
const summary={event:'summary',status:'PASS',completed_pairs:1,expected_pairs:1,passed:1,failed:0,errors:0};
function fixture(){const objects=new Map<string,string>();const store={put:async(k:string,v:string)=>{objects.set(k,v)},get:async(k:string)=>objects.get(k)!};return {objects,store,sink:new DurableResults(store,'11111111-1111-4111-8111-111111111111','a'.repeat(40),roles,cases,1)};}
test('only fixed result fields survive; credentials, replies and exception text are omitted',()=>{
 const safe=sanitizeResult({...pair,text:'private generated reply',voice:'private voice',headers:{authorization:'secret'},api_key:'secret',verdict:{...verdict,extra:'secret'}},roles,cases);
 assert.ok(!JSON.stringify(safe).includes('private'));assert.ok(!JSON.stringify(safe).includes('secret'));
 assert.equal(sanitizeResult({event:'authentication',provider:'openai',reason:'secret error body'},roles,cases).reason,'unclassified');
});
test('writes each event before final manifest and verifies readback',async()=>{
 const {objects,sink}=fixture();await sink.initialize();sink.enqueue(pair);sink.enqueue(summary);const final=await sink.finish(summary);
 assert.equal(final.status,'PASS');assert.equal(final.production_certified,false);assert.equal(objects.size,3);
 assert.equal(JSON.parse(objects.get(sink.prefix+'/manifest.json')!).completed_pairs,1);
});
test('write failures never produce a passing completion manifest',async()=>{
 const {store,sink,objects}=fixture();await sink.initialize();store.put=async()=>{throw new Error('secret upstream failure')};sink.enqueue(pair);
 await assert.rejects(sink.finish(summary),/evidence_write_failed/);
 assert.equal(JSON.parse(objects.get(sink.prefix+'/manifest.json')!).status,'RUNNING');
});
test('readback corruption, incomplete summaries, duplicate and foreign pairs fail closed',async()=>{
 const a=fixture();a.store.get=async()=>'{corrupt}';await assert.rejects(a.sink.initialize(),/readback_mismatch/);
 const b=fixture();await b.sink.initialize();await assert.rejects(b.sink.finish(summary),/summary_mismatch/);
 b.sink.enqueue(pair);assert.throws(()=>b.sink.enqueue(pair),/duplicate/);
 assert.throws(()=>sanitizeResult({...pair,role:'FOREIGN'},roles,cases),/identity/);
 assert.throws(()=>sanitizeResult({...pair,verdict:{...verdict,governance:false}},roles,cases),/pair_pass/);
 await b.sink.flush();
});
test('aborted runs retain a durable error manifest and completed prefix',async()=>{
 const {sink,objects}=fixture();await sink.initialize();sink.enqueue(pair);await sink.abort();
 const final=JSON.parse(objects.get(sink.prefix+'/manifest.json')!);
 assert.equal(final.status,'ERROR');assert.equal(final.completed_pairs,1);assert.equal(final.production_certified,false);
 assert.equal(objects.size,2);
});
