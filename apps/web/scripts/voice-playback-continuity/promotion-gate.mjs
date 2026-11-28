import { readFileSync, writeFileSync } from "node:fs"
const [input, output] = process.argv.slice(2)
const x = JSON.parse(readFileSync(input, "utf8"))
const policies = ["baseline","fixed","adaptive"]
const expected = new Set()
for (const policy of policies) for (const jitter of ["clean","uniform","burst"]) for (const seed of [1,2,3]) for (const rate of [44100,48000]) for (const odd of [false,true]) for (const pace of [1,2]) expected.add(JSON.stringify([policy,jitter,seed,rate,odd,pace]))
const id = s => JSON.stringify([s.policy,s.jitterProfile,s.seed,s.ctxRate,s.oddSplit,s.pacing])
const issues = []
const seen = new Set()
const summaries = {}
if (x.sourceSha !== process.env.VOICE_DUPLEX_SOURCE_SHA || x.synthetic !== true || x.results.length !== expected.size) issues.push("invalid evidence identity or count")
for (const row of x.results) {
  const key = id(row.scenario)
  if (!expected.has(key) || seen.has(key)) issues.push("invalid or duplicate scenario "+key)
  seen.add(key)
}
for (const policy of policies) {
  const rows = x.results.filter(r=>r.scenario.policy===policy)
  const starts = []
  let failures = 0, gap = 0, maxResidual = 0
  for (const row of rows) {
    const m = row.metrics
    const values = [m.firstStartupMs,m.secondStartupMs,m.residualMs,m.secondReplySpanMs,m.totals.gapMs,m.totals.jumps,m.totals.hardGapEdges,m.flush.jumps]
    const valid = values.every(v=>Number.isFinite(v)&&v>=0)
    if (!valid) issues.push("invalid measurement "+id(row.scenario))
    const feasibility = m.rateFeasibility
    if (!Array.isArray(row.arrivals) || !row.arrivals.length || !Array.isArray(feasibility) || feasibility.length !== 2 || feasibility.some((f,i)=>f.reply!==i || !Number.isSafeInteger(f.packetCount) || f.packetCount<=0 || !Array.isArray(f.bounds) || f.bounds.length!==4 || f.bounds.some((b,j)=>b.rate!==[1,.99,.97,.95][j] || !Number.isFinite(b.maxSupplyDeficitMs) || b.maxSupplyDeficitMs<0))) issues.push("missing or invalid rate feasibility evidence "+id(row.scenario))
    starts.push(m.firstStartupMs,m.secondStartupMs)
    gap += m.totals.gapMs
    maxResidual = Math.max(maxResidual,m.residualMs)
    if (!valid || row.playerKind!=="worklet" || m.reply1.missing || m.reply2.missing || m.totals.jumps!==0 || m.totals.hardGapEdges!==0 || m.flush.jumps!==0 || m.totals.gapMs>20 || m.residualMs>50 || m.secondReplySpanMs<row.scenario.secondReplyS*1000-50) failures++
  }
  starts.sort((a,b)=>a-b)
  const q = p=>starts[Math.ceil(starts.length*p)-1]
  summaries[policy]={scenarios:rows.length,observations:starts.length,p50:q(.5),p95:q(.95),failures,gap,maxResidual}
}
const a=summaries.adaptive,f=summaries.fixed
if (!(a.p50<f.p50)) issues.push("adaptive p50 not superior")
if (!(a.p95<f.p95)) issues.push("adaptive p95 not superior")
if (a.failures!==0) issues.push("adaptive acoustic acceptance failures")
if (!(a.gap<=f.gap)) issues.push("adaptive accumulated silence regression")
if (!(a.maxResidual<=50)) issues.push("adaptive interruption residual exceeds bound")
const report={sourceSha:x.sourceSha,syntheticOnly:true,promotionEligible:issues.length===0,issues,summaries,liveCertification:"NOT RUN"}
writeFileSync(output,JSON.stringify(report,null,2)+"\n")
console.log(JSON.stringify(report,null,2))
if (!report.promotionEligible) process.exitCode=1
