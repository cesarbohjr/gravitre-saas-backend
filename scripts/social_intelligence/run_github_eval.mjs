/** Manual GitHub Actions entrypoint for the synthetic generated-response gate. */
import {readFileSync,writeFileSync} from "node:fs";
import {runEvaluation} from "./evaluator.ts";
const bundle=JSON.parse(readFileSync(process.argv[2],"utf8"));
const rows=[];
let summary;
try {
  summary=await runEvaluation(bundle,process.env,row=>{rows.push(row);console.log(JSON.stringify(row));});
} catch(e) {
  summary={event:"summary",status:"ERROR",source_sha:bundle.source_sha,reason:e instanceof Error?e.message:"unknown"};
  rows.push(summary);
  console.error(JSON.stringify(summary));
}
writeFileSync(process.argv[3],JSON.stringify({summary,rows},null,2));
if(summary?.status!=="PASS")process.exitCode=1;
