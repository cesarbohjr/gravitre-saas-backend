/** Private synthetic evaluation evidence. Never persist provider bodies or replies. */
export type Store = {put(key:string, value:string):Promise<void>; get(key:string):Promise<string>};
const statuses = new Set(['PASS','FAIL','ERROR','NOT_RUN','NOT RUN','RUNNING']);
const counts = ['http_status','pairs','expected_pairs','completed_pairs','passed','failed','errors','requests','input_tokens','output_tokens','cache_read_tokens'] as const;
const criteria = ['empathy','attribution','boundaries','governance','honesty','channel_style','task_focus','consistency'];

export function sanitizeResult(row:any, roles:Set<string>, cases:Set<string>):Record<string,unknown> {
  if (!row || !['authentication','start','pair','summary'].includes(row.event)) throw new Error('invalid_evidence_event');
  const out:Record<string,unknown> = {event:row.event};
  if (statuses.has(row.status)) out.status=row.status;
  if (['anthropic','openai'].includes(row.provider)) out.provider=row.provider;
  if (['claude-sonnet-4-6','claude-haiku-4-5-20251001','gpt-4.1-mini'].includes(row.model)) out.model=row.model;
  if (roles.has(row.role)) out.role=row.role;
  if (cases.has(row.case)) out.case=row.case;
  if (['unified','classical'].includes(row.path)) out.path=row.path;
  if (typeof row.nonempty_reply==='boolean') out.nonempty_reply=row.nonempty_reply;
  for(const k of counts) if(Number.isSafeInteger(row[k]) && row[k]>=0) out[k]=row[k];
  if(row.reason) out.reason=/^provider_http_[1-5][0-9]{2}$/.test(row.reason) || ['missing_key','request_failed','invalid_judge','truncated_response','empty_response','rate_limited','evaluation_error'].includes(row.reason) ? row.reason : 'unclassified';
  if(row.event==='pair') {
    if(!out.role || !out.case || !out.path || !['PASS','FAIL','ERROR'].includes(String(out.status))) throw new Error('invalid_pair_identity');
    if(row.verdict) {
      if(criteria.some(k=>typeof row.verdict[k]!=='boolean')) throw new Error('invalid_verdict');
      out.verdict=Object.fromEntries(criteria.map(k=>[k,row.verdict[k]]));
      if(out.status==='PASS' && criteria.some(k=>!row.verdict[k])) throw new Error('invalid_pair_pass');
    } else if(out.status!=='ERROR') throw new Error('missing_verdict');
  }
  return out;
}

export class DurableResults {
  private queue:Promise<void>=Promise.resolve();
  private error:Error|undefined;
  private sequence=0;
  private seen=new Set<string>();
  private pairCounts={passed:0,failed:0,errors:0};
  readonly prefix:string;
  private store:Store;
  readonly runId:string;
  readonly sourceSha:string;
  private roles:Set<string>;
  private cases:Set<string>;
  readonly expectedPairs:number;
  constructor(store:Store, runId:string, sourceSha:string, roles:Set<string>, cases:Set<string>, expectedPairs:number) {
    if(!/^[a-f0-9-]{36}$/.test(runId)||!/^[a-f0-9]{40}$/.test(sourceSha)||!Number.isSafeInteger(expectedPairs)||expectedPairs<1) throw new Error('invalid_evidence_identity');
    this.prefix=`runs/${sourceSha}/${runId}`;
    this.store=store;this.runId=runId;this.sourceSha=sourceSha;this.roles=roles;this.cases=cases;this.expectedPairs=expectedPairs;
  }
  private async verifiedPut(key:string, data:unknown) {
    const text=JSON.stringify(data);
    await this.store.put(key,text);
    if(await this.store.get(key)!==text) throw new Error('evidence_readback_mismatch');
  }
  async initialize() {
    await this.verifiedPut(`${this.prefix}/manifest.json`,{schema:1,run_id:this.runId,source_sha:this.sourceSha,status:'RUNNING',expected_pairs:this.expectedPairs,production_certified:false,scope:'synthetic_prompt_builders_only',replies_retained:false});
  }
  enqueue(row:unknown) {
    if(this.error) throw this.error;
    const safe=sanitizeResult(row,this.roles,this.cases);
    if(safe.event==='pair') {
      const id=`${safe.role}/${safe.path}/${safe.case}`;
      if(this.seen.has(id)) throw new Error('duplicate_pair_evidence');
      this.seen.add(id);
      this.pairCounts[safe.status==='PASS'?'passed':safe.status==='FAIL'?'failed':'errors']++;
    }
    const sequence=this.sequence++;
    this.queue=this.queue.then(async()=>{
      if(this.error) return;
      try {await this.verifiedPut(`${this.prefix}/events/${String(sequence).padStart(6,'0')}.json`,{schema:1,run_id:this.runId,source_sha:this.sourceSha,sequence,...safe});}
      catch {this.error=new Error('evidence_write_failed');}
    });
  }
  async flush() {await this.queue;if(this.error)throw this.error;}
  async abort() {
    await this.queue;
    await this.verifiedPut(`${this.prefix}/manifest.json`,{schema:1,run_id:this.runId,source_sha:this.sourceSha,status:'ERROR',reason:'evaluation_or_evidence_failure',expected_pairs:this.expectedPairs,completed_pairs:this.seen.size,...this.pairCounts,events:this.sequence,production_certified:false,scope:'synthetic_prompt_builders_only',replies_retained:false});
  }
  async finish(summary:any) {
    await this.flush();
    const completed=this.seen.size;
    if(!summary || summary.completed_pairs!==completed || summary.expected_pairs!==this.expectedPairs || Object.entries(this.pairCounts).some(([k,v])=>summary[k]!==v)) throw new Error('evidence_summary_mismatch');
    const passes=completed===this.expectedPairs && this.pairCounts.passed===this.expectedPairs;
    if((summary.status==='PASS')!==passes) throw new Error('evidence_summary_mismatch');
    const result={schema:1,run_id:this.runId,source_sha:this.sourceSha,status:summary.status,expected_pairs:this.expectedPairs,completed_pairs:completed,...this.pairCounts,events:this.sequence,production_certified:false,scope:'synthetic_prompt_builders_only',replies_retained:false};
    await this.verifiedPut(`${this.prefix}/manifest.json`,result);
    return result;
  }
}
