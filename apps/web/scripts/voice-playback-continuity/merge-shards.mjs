import { readFileSync, writeFileSync, readdirSync } from "node:fs"
import { join } from "node:path"
const [dir, output] = process.argv.slice(2)
const sha = process.env.VOICE_DUPLEX_SOURCE_SHA
if (!/^[a-f0-9]{40}$/.test(sha ?? "")) throw Error("Missing exact source SHA")
const files = readdirSync(dir).sort()
if (JSON.stringify(files) !== JSON.stringify([1,2,3].map(s=>`buffer-shard-${s}.json`))) throw Error("Missing or unexpected shard files")
const results = [], violations = [], seen = new Set()
for (const seed of [1,2,3]) {
  const x=JSON.parse(readFileSync(join(dir,`buffer-shard-${seed}.json`),"utf8"))
  if (x.sourceSha!==sha || x.synthetic!==true || x.shardSeed!==seed || x.results.length!==72 || !Array.isArray(x.violations)) throw Error("Invalid shard "+seed)
  const expected=new Set()
  for(const policy of ["baseline","fixed","adaptive"]) for(const jitter of ["clean","uniform","burst"]) for(const rate of [44100,48000]) for(const odd of [false,true]) for(const pace of [1,2]) expected.add(JSON.stringify([policy,jitter,seed,rate,odd,pace]))
  for(const row of x.results) {
    const s=row.scenario,k=JSON.stringify([s.policy,s.jitterProfile,s.seed,s.ctxRate,s.oddSplit,s.pacing])
    if(!expected.delete(k)||seen.has(k)||s.impl!=="after"||s.replyS!==6||s.flushAtS!==3.2||s.secondReplyDelayS!==0.4||s.secondReplyS!==2.5||s.jitterMaxMs!==300) throw Error("Invalid paired scenario "+k)
    seen.add(k);results.push(row)
  }
  if(expected.size) throw Error("Incomplete shard "+seed)
  violations.push(...x.violations)
}
writeFileSync(output,JSON.stringify({synthetic:true,sourceSha:sha,results,violations,shards:files},null,2)+"\n")
console.log("Validated "+results.length+" distinct paired scenarios")
