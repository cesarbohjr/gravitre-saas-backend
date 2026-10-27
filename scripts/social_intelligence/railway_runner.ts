/** One-shot private runner; no HTTP listener, tools, customer data or restart loop. */
import {S3Client} from 'bun';
import {DurableResults,sanitizeResult} from './durable_results.ts';
import {runEvaluation,validateBundle} from './evaluator.ts';

const bundle=JSON.parse(await Bun.file(process.argv[2]).text());
validateBundle(bundle);
const expected=bundle.profiles.filter((p:any)=>p.channel==='text').length*bundle.cases.length;
if(expected!==520) throw new Error('unexpected_evaluation_size');
const roles=new Set<string>(bundle.profiles.map((p:any)=>p.role));
const cases=new Set<string>(bundle.cases.map((c:any)=>c.id));
for(const k of ['EVAL_S3_ENDPOINT','EVAL_S3_BUCKET','EVAL_S3_REGION','EVAL_S3_ACCESS_KEY_ID','EVAL_S3_SECRET_ACCESS_KEY']) {
  if(!process.env[k] || process.env[k]!.includes('$'+'{{')) throw new Error('missing_evidence_storage');
}
const endpoint=new URL(process.env.EVAL_S3_ENDPOINT!);
endpoint.hostname=process.env.EVAL_S3_BUCKET+'.'+endpoint.hostname;
const storage=new S3Client({endpoint:endpoint.toString(),virtualHostedStyle:true,region:process.env.EVAL_S3_REGION,accessKeyId:process.env.EVAL_S3_ACCESS_KEY_ID,secretAccessKey:process.env.EVAL_S3_SECRET_ACCESS_KEY});
const store={put:async(key:string,value:string)=>{await storage.file(key).write(value,{type:'application/json'});},get:async(key:string)=>await storage.file(key).text()};
const sink=new DurableResults(store,crypto.randomUUID(),bundle.source_sha,roles,cases,expected);
let completed=0;
const emit=(row:any)=>{
  sink.enqueue(row);
  if(row.event==='pair') completed++;
  if(row.event!=='pair' || completed%20===0) console.log('EVAL_RESULT '+JSON.stringify({...sanitizeResult(row,roles,cases),completed,source_sha:bundle.source_sha,run_id:sink.runId}));
};

async function authenticate(provider:'anthropic'|'openai') {
  const anth=provider==='anthropic',model=anth?'claude-sonnet-4-6':'gpt-4.1-mini';
  const key=(process.env[anth?'ANTHROPIC_API_KEY':'OPENAI_API_KEY']||'').trim();
  if(!key || key.includes('$'+'{{')) return {event:'authentication',provider,model,status:'NOT_RUN',reason:'missing_key'};
  try {
    const r=await fetch(anth?'https://api.anthropic.com/v1/messages':'https://api.openai.com/v1/chat/completions',{
      method:'POST',signal:AbortSignal.timeout(60000),headers:anth?{'x-api-key':key,'anthropic-version':'2023-06-01','content-type':'application/json'}:{Authorization:'Bearer '+key,'content-type':'application/json'},
      body:JSON.stringify({model,max_tokens:32,messages:[{role:'user',content:'Reply with only OK.'}]})});
    let reply=false;
    if(r.ok) {const d=await r.json() as any;reply=anth?!!d.content?.some((x:any)=>x.type==='text'&&x.text?.trim()):!!d.choices?.[0]?.message?.content?.trim();}
    return {event:'authentication',provider,model,status:r.ok&&reply?'PASS':'FAIL',http_status:r.status,nonempty_reply:reply};
  } catch {return {event:'authentication',provider,model,status:'ERROR',reason:'request_failed'};}
}

try {
  await sink.initialize();
  console.log('EVAL_EVIDENCE_READY '+JSON.stringify({run_id:sink.runId,source_sha:bundle.source_sha,prefix:sink.prefix,expected_pairs:expected}));
  const auth=await authenticate('anthropic');emit(auth);
  emit(await authenticate('openai'));
  await sink.flush();
  let summary:any;
  if(auth.status==='PASS') summary=await runEvaluation(bundle,process.env,emit);
  else {summary={event:'summary',status:'NOT_RUN',expected_pairs:expected,completed_pairs:0,passed:0,failed:0,errors:0};emit(summary);}
  const final=await sink.finish(summary);
  console.log('EVAL_DURABLE_COMPLETE '+JSON.stringify({...final,prefix:sink.prefix,readback_verified:true}));
  if(final.status!=='PASS')process.exitCode=1;
} catch {
  try {await sink.abort();} catch {console.error('EVAL_STORAGE_FAILURE '+JSON.stringify({run_id:sink.runId,status:'ERROR'}));}
  // Never print exception text, headers, provider bodies or signed URLs.
  console.error('EVAL_RUN_ERROR '+JSON.stringify({run_id:sink.runId,source_sha:bundle.source_sha,status:'ERROR',reason:'evaluation_or_evidence_failure',completed}));
  process.exitCode=1;
}
