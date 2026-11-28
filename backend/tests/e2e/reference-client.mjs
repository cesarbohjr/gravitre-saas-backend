import { PipecatClient } from "@pipecat-ai/client-js"
import { SmallWebRTCTransport } from "@pipecat-ai/small-webrtc-transport"
window.runReference=async()=>{
 const ctx=new AudioContext({sampleRate:48000});await ctx.resume()
 const dst=ctx.createMediaStreamDestination(),osc=ctx.createOscillator(),gain=ctx.createGain()
 osc.frequency.value=440;gain.gain.value=0;osc.connect(gain).connect(dst);osc.start()
 const original=navigator.mediaDevices.getUserMedia.bind(navigator.mediaDevices)
 navigator.mediaDevices.getUserMedia=async constraints=>constraints.audio&&!constraints.video?dst.stream:original(constraints)
 const samples=[],localSamples=[],pcs=[]
 const Original=window.RTCPeerConnection
 window.RTCPeerConnection=class extends Original{constructor(...args){super(...args);pcs.push(this)}}
 const tap=(src,rows)=>{const node=ctx.createScriptProcessor(1024,1,1),silent=ctx.createGain();silent.gain.value=0;src.connect(node).connect(silent).connect(ctx.destination);node.onaudioprocess=e=>{const x=e.inputBuffer.getChannelData(0);let sum=0,c=0;for(let i=1;i<x.length;i++){sum+=x[i]*x[i];if(x[i-1]<=0&&x[i]>0)c++}rows.push({t:e.playbackTime*1000,rms:Math.sqrt(sum/x.length),hz:c*ctx.sampleRate/x.length})}}
 tap(ctx.createMediaStreamSource(dst.stream),localSamples)
 let remote=false
 const client=new PipecatClient({transport:new SmallWebRTCTransport(),enableMic:true,enableCam:false,callbacks:{onTrackStarted:(track,participant)=>{if(track.kind==="audio"&&!participant?.local&&!remote){remote=true;tap(ctx.createMediaStreamSource(new MediaStream([track])),samples)}}}})
 const wait=ms=>new Promise(r=>setTimeout(r,ms)),now=()=>ctx.currentTime*1000
 let first=null,interrupt=null,error=null
 try{
  await Promise.race([client.connect({connection_url:location.origin+"/offer"}),wait(15000).then(()=>{throw Error("SDK connection timeout")})])
  await wait(400)
  first=now();gain.gain.value=.3;await wait(180);gain.gain.value=0
  for(let i=0;!samples.some(s=>s.t>=first&&s.rms>.015&&s.hz>950&&s.hz<1300)&&i<100;i++)await wait(20)
  if(!samples.some(s=>s.t>=first&&s.rms>.015&&s.hz>950&&s.hz<1300))throw Error("first tone not received")
  interrupt=now();osc.frequency.value=800;gain.gain.value=.3;await wait(180);gain.gain.value=0;await wait(2600)
 }catch(e){error=String(e)}
 try{
 const stats=[];for(const pc of pcs)for(const s of (await pc.getStats()).values())if(["inbound-rtp","outbound-rtp"].includes(s.type)&&s.kind==="audio")stats.push({type:s.type,packetsReceived:s.packetsReceived,packetsSent:s.packetsSent,packetsLost:s.packetsLost,jitter:s.jitter})
 const server=await (await fetch("/observations")).json()
 const a=samples.filter(s=>first!==null&&s.t>=first&&s.rms>.015&&s.hz>950&&s.hz<1300),b=samples.filter(s=>interrupt!==null&&s.t>=interrupt&&s.rms>.015&&s.hz>1500&&s.hz<1900)
 return {error,first,interrupt,firstAudioMs:a.length?a[0].t-first:null,interruptResidualMs:a.length&&interrupt!==null?Math.max(0,a.at(-1).t-interrupt):null,secondAudioMs:b.length?b[0].t-interrupt:null,secondToneSpanMs:b.length?b.at(-1).t-b[0].t:null,oldToneAfterSecond:b.length?a.some(s=>s.t>b[0].t):null,secondGapMs:b.length?Math.max(0,...b.slice(1).map((s,i)=>s.t-b[i].t-1024/ctx.sampleRate*1000)):null,inbound:stats.filter(s=>s.type==="inbound-rtp"),stats,server,samples,localSamples}
 }finally{await client.disconnect().catch(()=>{});navigator.mediaDevices.getUserMedia=original;window.RTCPeerConnection=Original;await ctx.close()}
}
