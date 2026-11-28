import { chromium } from 'playwright'
import { writeFileSync } from 'node:fs'
const browser=await chromium.launch({args:['--autoplay-policy=no-user-gesture-required']})
const trials=[]
try {
 for(let repeat=1;repeat<=20;repeat++){
  for(const senderClear of repeat%2?[false,true]:[true,false]){
   const page=await browser.newPage()
   try{
    await page.goto('http://127.0.0.1:8797/')
    await page.waitForFunction(()=>typeof window.runReference==='function')
    const result=await page.evaluate(c=>window.runReference(c),{chunkMs:10,targetMs:0,senderClear})
    trials.push({repeat,senderClear,...result})
   }catch(e){trials.push({repeat,senderClear,error:String(e)})}
   finally{await page.close()}
  }
 }
 const failures=[]
 for(const t of trials){
  const problems=[]
  if(t.error)problems.push(t.error)
  if(!Number.isFinite(t.interruptResidualMs)||t.interruptResidualMs>=300)problems.push('residual')
  if(!Number.isFinite(t.firstAudioMs)||t.firstAudioMs<0||t.firstAudioMs>2000||!Number.isFinite(t.secondAudioMs)||t.secondAudioMs<0||t.secondAudioMs>2000)problems.push('onset')
  if(!Number.isFinite(t.secondGapMs)||t.secondGapMs>100||!Number.isFinite(t.secondToneSpanMs)||t.secondToneSpanMs<1500||t.oldToneAfterSecond!==false)problems.push('continuity')
  if(!t.server?.some(s=>s.boundary==='track_dequeue'&&s.frequency>0)||!t.server?.some(s=>s.boundary==='track_interrupt_after_native'))problems.push('missing native trace')
  if(t.senderClear&&!t.server?.some(s=>s.boundary==='track_clear'&&s.depth===0))problems.push('missing clear')
  if(problems.length)failures.push({repeat:t.repeat,senderClear:t.senderClear,problems})
 }
 const stats=(key,mode,q)=>{const a=trials.filter(t=>t.senderClear===mode).map(t=>t[key]).filter(Number.isFinite).sort((a,b)=>a-b);return a.length===20?a[Math.ceil(q*20)-1]:null}
 const candidatePassed=trials.length===40&&!failures.some(f=>f.senderClear)
 const metrics=['firstAudioMs','secondAudioMs','secondGapMs','interruptResidualMs']
 const summaries=Object.fromEntries([false,true].map(m=>[String(m),Object.fromEntries(metrics.map(k=>[k,{p50:stats(k,m,.5),p95:stats(k,m,.95)}]))]))
 const nonRegression=metrics.slice(0,3).every(k=>[.5,.95].every(q=>stats(k,true,q)!==null&&stats(k,false,q)!==null&&stats(k,true,q)<=stats(k,false,q)))
 writeFileSync('native-sender-paired.json',JSON.stringify({sourceSha:process.env.GITHUB_SHA,synthetic:true,trials,failures,summaries,candidatePassed,nonRegression,promotionEligible:false},null,2))
 if(!candidatePassed||!nonRegression)throw Error('candidate screening or non-regression failed')
}finally{await browser.close()}
