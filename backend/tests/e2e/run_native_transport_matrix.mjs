import { chromium } from "playwright"
import { writeFileSync } from "node:fs"
const browser=await chromium.launch({args:["--autoplay-policy=no-user-gesture-required"]})
try{
 const page=await browser.newPage()
 await page.goto("http://127.0.0.1:8797/")
 await page.waitForFunction(()=>typeof window.runReference==="function")
 const trials=[]
 const chunkMs=Number(process.env.REFERENCE_CHUNK_MS), target=process.env.REFERENCE_JITTER_TARGET
 if(![10,20,40].includes(chunkMs)||!['default','0','40'].includes(target))throw Error('invalid matrix configuration')
 const config={chunkMs,targetMs:target==='default'?null:Number(target)}
 for(let i=0;i<20;i++){try{trials.push({...await page.evaluate(c=>window.runReference(c),config),workloadId:'interrupt-recover-v1',repeat:i+1})}catch(e){trials.push({workloadId:'interrupt-recover-v1',repeat:i+1,error:String(e),localSamples:[],stats:[],server:[],inbound:[]})}}
 const failures=trials.flatMap((t,i)=>[
 ...(t.error?[t.error]:[]),
 ...(!t.server.some(s=>s.boundary==='configuration'&&s.chunkMs===chunkMs)?['missing applied server chunk']:[]),
 ...(config.targetMs!==null&&t.config?.appliedTargetMs!==config.targetMs?['missing applied receiver target']:[]),
 ...(!t.inbound.some(s=>Number.isFinite(s.jitterBufferDelay)&&s.jitterBufferEmittedCount>0)?['missing native jitter buffer statistics']:[]),
 ...(!t.server.some(s=>s.boundary==='native_write_enter')||!t.server.some(s=>s.boundary==='output_interrupt_exit')?['missing native output trace']:[]),
 ...(!t.localSamples.some(s=>s.rms>.015)?["missing local input"]:[]),
 ...(!t.stats.some(s=>s.type==="outbound-rtp"&&s.packetsSent>0)?["missing outbound RTP"]:[]),
 ...(!t.server.some(s=>s.boundary==="server_input")?["missing server input"]:[]),
 ...(!t.server.some(s=>s.boundary==="server_output")?["missing server output"]:[]),
 ...(!t.inbound.some(s=>s.packetsReceived>0)?["missing RTP"]:[]),
 ...(!(Number.isFinite(t.firstAudioMs)&&Number.isFinite(t.secondAudioMs)&&t.firstAudioMs>=0&&t.firstAudioMs<=2000&&t.secondAudioMs>=0&&t.secondAudioMs<=2000)?["missing or invalid onset"]:[]),
 ...(!(t.clockSync?.rttMs>0)||!Number.isFinite(t.interruptPerfMs)||!t.server.some(s=>s.boundary==='producer_cancelled')||!t.server.some(s=>s.boundary==='interrupt_forwarded')?["missing cancellation trace"]:[]),
 ...(t.oldToneAfterSecond?["cross-reply audio"]:[]),
 ...(!Number.isFinite(t.interruptResidualMs)||t.interruptResidualMs>=300?["synthetic interruption exceeds 300 ms screening bound"]:[]),
 ...(t.secondToneSpanMs<1500?["incomplete second tone"]:[]),
 ...(t.secondGapMs>100?["synthetic tone gap exceeds 100 ms screening bound"]:[])
 ].map(reason=>({trial:i+1,reason})))
 writeFileSync("native-matrix-evidence.json",JSON.stringify({sourceSha:process.env.GITHUB_SHA,synthetic:true,config,fixture:'interrupt-recover-v1',clock:"browser callback clock; server monotonic offset estimate with RTT uncertainty",scope:"transport screening, not naturalness or final QA",trials,failures},null,2))
 if(failures.length)throw Error(JSON.stringify(failures))
}finally{await browser.close()}
