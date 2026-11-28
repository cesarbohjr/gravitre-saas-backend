import assert from "node:assert/strict"
import { stretchCandidate } from "./rate-prototype.mjs"
for(const sr of [44100,48000]){
 const x=Float32Array.from({length:sr*2},(_,i)=>.5*Math.sin(2*Math.PI*210*i/sr))
 for(const rate of [.95,.97,.99,1]){
  const y=stretchCandidate(x,sr,rate)
  assert(y.every(Number.isFinite))
  assert(Math.abs(y.length-x.length/rate)<=sr*.05)
  let crossings=0
  for(let i=1;i<y.length;i++)if(y[i-1]<=0&&y[i]>0)crossings++
  const pitch=crossings*sr/y.length
  assert(Math.abs(pitch-210)<10, "local pitch sanity bound")
  console.log(JSON.stringify({sr,rate,sourceFrames:x.length,outputFrames:y.length,pitch}))
 }
}
assert.throws(()=>stretchCandidate(new Float32Array(100),48000,.9))
