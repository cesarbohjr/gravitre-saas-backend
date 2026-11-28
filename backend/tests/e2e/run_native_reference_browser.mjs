import { chromium } from "playwright"
import { writeFileSync } from "node:fs"
const browser=await chromium.launch({args:["--autoplay-policy=no-user-gesture-required"]})
try{
 const page=await browser.newPage()
 await page.goto("http://127.0.0.1:8797/")
 const trials=[]
 for(let i=0;i<3;i++)trials.push(await page.evaluate(()=>window.runReference()))
 const failures=trials.flatMap((t,i)=>[
 ...(!t.inbound.some(s=>s.packetsReceived>0)?["missing RTP"]:[]),
 ...(!(t.firstAudioMs>=0&&t.firstAudioMs<=2000&&t.secondAudioMs>=0&&t.secondAudioMs<=2000)?["missing or invalid onset"]:[]),
 ...(t.oldToneAfterSecond?["cross-reply audio"]:[]),
 ...(t.interruptResidualMs>300?["synthetic interruption exceeds 300 ms screening bound"]:[]),
 ...(t.secondToneSpanMs<1500?["incomplete second tone"]:[]),
 ...(t.secondGapMs>100?["synthetic tone gap exceeds 100 ms screening bound"]:[])
 ].map(reason=>({trial:i+1,reason})))
 writeFileSync("native-reference-evidence.json",JSON.stringify({sourceSha:process.env.GITHUB_SHA,synthetic:true,clock:"browser AudioContext; analysis block resolution",scope:"transport screening, not naturalness or final QA",trials,failures},null,2))
 if(failures.length)throw Error(JSON.stringify(failures))
}finally{await browser.close()}
