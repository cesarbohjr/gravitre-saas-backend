import { chromium } from "playwright"
import { writeFileSync } from "node:fs"
const browser=await chromium.launch({args:["--autoplay-policy=no-user-gesture-required"]})
try{
 const page=await browser.newPage()
 await page.goto("http://127.0.0.1:8797/")
 await page.waitForFunction(()=>typeof window.runReference==="function")
 const trials=[]
 for(let i=0;i<20;i++){try{trials.push({...await page.evaluate(()=>window.runReference()),workloadId:'interrupt-recover-v1',repeat:i+1})}catch(e){trials.push({workloadId:'interrupt-recover-v1',repeat:i+1,error:String(e),localSamples:[],stats:[],server:[],inbound:[]})}}
 const failures=trials.flatMap((t,i)=>[
 ...(t.error?[t.error]:[]),
 ...(!t.localSamples.some(s=>s.rms>.015)?["missing local input"]:[]),
 ...(!t.stats.some(s=>s.type==="outbound-rtp"&&s.packetsSent>0)?["missing outbound RTP"]:[]),
 ...(!t.server.some(s=>s.boundary==="server_input")?["missing server input"]:[]),
 ...(!t.server.some(s=>s.boundary==="server_output")?["missing server output"]:[]),
 ...(!t.inbound.some(s=>s.packetsReceived>0)?["missing RTP"]:[]),
 ...(!(Number.isFinite(t.firstAudioMs)&&Number.isFinite(t.secondAudioMs)&&t.firstAudioMs>=0&&t.firstAudioMs<=2000&&t.secondAudioMs>=0&&t.secondAudioMs<=2000)?["missing or invalid onset"]:[]),
 ...(!(t.clockSync?.rttMs>0)||!Number.isFinite(t.interruptPerfMs)||!t.server.some(s=>s.boundary==='producer_cancelled')||!t.server.some(s=>s.boundary==='interrupt_forwarded')?["missing cancellation trace"]:[]),
 ...(t.oldToneAfterSecond?["cross-reply audio"]:[]),
 ...(t.interruptResidualMs>300?["synthetic interruption exceeds 300 ms screening bound"]:[]),
 ...(t.secondToneSpanMs<1500?["incomplete second tone"]:[]),
 ...(t.secondGapMs>100?["synthetic tone gap exceeds 100 ms screening bound"]:[])
 ].map(reason=>({trial:i+1,reason})))
 writeFileSync("native-reference-evidence.json",JSON.stringify({sourceSha:process.env.GITHUB_SHA,synthetic:true,fixture:'interrupt-recover-v1',clock:"browser callback clock; server monotonic offset estimate with RTT uncertainty",scope:"transport screening, not naturalness or final QA",trials,failures},null,2))
 if(failures.length)throw Error(JSON.stringify(failures))
}finally{await browser.close()}
