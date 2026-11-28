import { PipecatClient } from "@pipecat-ai/client-js"
import { SmallWebRTCTransport } from "@pipecat-ai/small-webrtc-transport"
window.runReference=async(config={})=>{
 const ctx=new AudioContext({sampleRate:48000});await ctx.resume()
 const dst=ctx.createMediaStreamDestination(),osc=ctx.createOscillator(),gain=ctx.createGain()
 osc.frequency.value=440;gain.gain.value=0;osc.connect(gain).connect(dst);osc.start()
 const original=navigator.mediaDevices.getUserMedia.bind(navigator.mediaDevices)
 navigator.mediaDevices.getUserMedia=async constraints=>constraints.audio&&!constraints.video?dst.stream:original(constraints)
 const samples=[],localSamples=[],pcs=[]
 const Original=window.RTCPeerConnection
 window.RTCPeerConnection=class extends Original{constructor(...args){super(...args);pcs.push(this)}}
 const energy=(x,hz)=>{let re=0,im=0,norm=0;for(let i=0;i<x.length;i++){const w=.5-.5*Math.cos(2*Math.PI*i/(x.length-1)),v=x[i]*w,a=2*Math.PI*hz*i/ctx.sampleRate;re+=v*Math.cos(a);im+=v*Math.sin(a);norm+=w}return 2*Math.hypot(re,im)/norm}
 const tap=(src,rows)=>{const node=ctx.createScriptProcessor(1024,1,1),silent=ctx.createGain();silent.gain.value=0;src.connect(node).connect(silent).connect(ctx.destination);node.onaudioprocess=e=>{const x=e.inputBuffer.getChannelData(0);let sum=0,c=0;for(let i=1;i<x.length;i++){sum+=x[i]*x[i];if(x[i-1]<=0&&x[i]>0)c++}rows.push({t:ctx.currentTime*1000,callbackPerfMs:performance.now(),playbackTime:e.playbackTime*1000,oldEnergy:energy(x,1100),newEnergy:energy(x,1700),rms:Math.sqrt(sum/x.length),hz:c*ctx.sampleRate/x.length})}}
 tap(ctx.createMediaStreamSource(dst.stream),localSamples)
 const workletSamples=[],receiverSnapshots=[];let statsTimer=null,workletNode=null,statsBusy=false,statsError=null
 let remote=false, remoteTrack=null, remoteElement=null; const trackEvents=[]
 const client=new PipecatClient({transport:new SmallWebRTCTransport(),enableMic:true,enableCam:false,callbacks:{onTrackStarted:(track,participant)=>{trackEvents.push({kind:track.kind,id:track.id,local:participant?.local??null});}}})
 const wait=ms=>new Promise(r=>setTimeout(r,ms)),now=()=>ctx.currentTime*1000
 let first=null,interrupt=null,error=null,clockSync=null,firstPerfMs=null,interruptPerfMs=null
 try{
  await Promise.race([client.connect({connection_url:location.origin+"/offer?"+new URLSearchParams({...config.chunkMs?{chunk_ms:String(config.chunkMs)}:{},sender_clear:String(config.senderClear===true),confirmation_frames:String(config.confirmationFrames??3)})}),wait(15000).then(()=>{throw Error("SDK connection timeout")})])
  await wait(400)
  const receiver=pcs.flatMap(pc=>pc.getReceivers()).find(r=>r.track?.kind==="audio"&&r.track.readyState==="live")
  if(!receiver)throw Error("missing native remote receiver")
  remoteTrack=receiver.track;remote=true
  if(config.targetMs!=null){if(!('jitterBufferTarget' in receiver))throw Error('native jitterBufferTarget unsupported');receiver.jitterBufferTarget=config.targetMs;if(receiver.jitterBufferTarget!==config.targetMs)throw Error('native jitterBufferTarget not applied')}
  config={...config,appliedTargetMs:receiver.jitterBufferTarget??null}
  const stream=new MediaStream([remoteTrack]);remoteElement=document.createElement("audio");remoteElement.srcObject=stream;remoteElement.autoplay=true;document.body.append(remoteElement);await remoteElement.play()
  tap(ctx.createMediaStreamSource(stream),samples)
  if(config.worklet){
   await ctx.audioWorklet.addModule('/reference-worklet.js');workletNode=new AudioWorkletNode(ctx,'reference-measurement');const silent=ctx.createGain();silent.gain.value=0;ctx.createMediaStreamSource(stream).connect(workletNode).connect(silent).connect(ctx.destination);workletNode.port.onmessage=e=>workletSamples.push({...e.data,receivedPerfMs:performance.now()});
   const snapshot=async()=>{if(statsBusy)return;statsBusy=true;try{for(const s of (await receiver.getStats()).values())if(s.type==='inbound-rtp'&&s.kind==='audio')receiverSnapshots.push({perfMs:performance.now(),timestamp:s.timestamp,id:s.id,delay:s.jitterBufferDelay,emitted:s.jitterBufferEmittedCount,target:s.jitterBufferTargetDelay,minimum:s.jitterBufferMinimumDelay,concealed:s.concealedSamples,packetsLost:s.packetsLost})}catch(e){statsError=String(e)}finally{statsBusy=false}};await snapshot();statsTimer=setInterval(snapshot,50)
  }
  const sync=[];for(let i=0;i<5;i++){const before=performance.now();const v=await(await fetch('/clock',{cache:'no-store'})).json();const after=performance.now();sync.push({offsetMs:v.monotonicMs-(before+after)/2,rttMs:after-before,uncertaintyMs:(after-before)/2})}clockSync=sync.sort((a,b)=>a.rttMs-b.rttMs)[0];
  firstPerfMs=performance.now();first=now();gain.gain.value=.3;await wait(180);gain.gain.value=0
  for(let i=0;!samples.some(s=>s.t>=first&&s.oldEnergy>.015&&s.oldEnergy>2*s.newEnergy)&&i<100;i++)await wait(20)
  if(!samples.some(s=>s.t>=first&&s.oldEnergy>.015&&s.oldEnergy>2*s.newEnergy))throw Error("first tone not received")
  if(config.negativeProbe){osc.frequency.value=1200;gain.gain.value=.3;await wait(100);gain.gain.value=0;await wait(100)}
  interruptPerfMs=performance.now();interrupt=now();osc.frequency.value=800;gain.gain.value=.3;await wait(180);gain.gain.value=0;await wait(2600)
 }catch(e){error=String(e)}
 try{
 if(statsTimer!==null)clearInterval(statsTimer)
 const stats=[];for(const pc of pcs)for(const s of (await pc.getStats()).values())if(["inbound-rtp","outbound-rtp"].includes(s.type)&&s.kind==="audio")stats.push({type:s.type,packetsReceived:s.packetsReceived,packetsSent:s.packetsSent,packetsLost:s.packetsLost,jitter:s.jitter,totalAudioEnergy:s.totalAudioEnergy,totalSamplesDuration:s.totalSamplesDuration,audioLevel:s.audioLevel,jitterBufferDelay:s.jitterBufferDelay,jitterBufferTargetDelay:s.jitterBufferTargetDelay,jitterBufferMinimumDelay:s.jitterBufferMinimumDelay,jitterBufferEmittedCount:s.jitterBufferEmittedCount,concealedSamples:s.concealedSamples,totalSamplesReceived:s.totalSamplesReceived})
 const server=await (await fetch("/observations")).json()
 const a=samples.filter(s=>first!==null&&s.t>=first&&s.oldEnergy>.015&&s.oldEnergy>2*s.newEnergy),b=samples.filter(s=>interrupt!==null&&s.t>=interrupt&&s.newEnergy>.015&&s.newEnergy>2*s.oldEnergy)
 const wa=workletSamples.filter(s=>first!==null&&s.startMs>=first&&s.oldEnergy>.015&&s.oldEnergy>2*s.newEnergy),wb=workletSamples.filter(s=>interrupt!==null&&s.startMs>=interrupt&&s.newEnergy>.015&&s.newEnergy>2*s.oldEnergy)
 const workletMetrics={firstAudioMs:wa.length?wa[0].startMs-first:null,interruptResidualMs:wa.length&&interrupt!==null?Math.max(0,wa.at(-1).endMs-interrupt):null,secondAudioMs:wb.length?wb[0].startMs-interrupt:null,secondGapMs:wb.length?Math.max(0,...wb.slice(1).map((s,i)=>s.startMs-wb[i].endMs)):null,secondToneSpanMs:wb.length?wb.at(-1).endMs-wb[0].startMs:null,oldToneAfterSecond:wb.length?wa.some(s=>s.startMs>=wb[0].startMs):null}
 return {workletSamples,workletMetrics,receiverSnapshots,statsError,config,error,first,interrupt,firstPerfMs,interruptPerfMs,clockSync,firstAudioMs:a.length?a[0].t-first:null,interruptResidualMs:a.length&&interrupt!==null?Math.max(0,a.at(-1).t-interrupt):null,secondAudioMs:b.length?b[0].t-interrupt:null,secondToneSpanMs:b.length?b.at(-1).t-b[0].t:null,oldToneAfterSecond:b.length?a.some(s=>s.t>b[0].t):null,secondGapMs:b.length?Math.max(0,...b.slice(1).map((s,i)=>s.t-b[i].t-1024/ctx.sampleRate*1000)):null,inbound:stats.filter(s=>s.type==="inbound-rtp"),stats,server,samples,localSamples,trackEvents,remoteTrack:remoteTrack?{id:remoteTrack.id,enabled:remoteTrack.enabled,muted:remoteTrack.muted,readyState:remoteTrack.readyState}:null}
 }finally{if(statsTimer!==null)clearInterval(statsTimer);workletNode?.disconnect();remoteElement?.remove();await client.disconnect().catch(()=>{});navigator.mediaDevices.getUserMedia=original;window.RTCPeerConnection=Original;await ctx.close()}
}
