// Offline candidate only. No AudioWorklet integration or live promotion.
 // Similarity-aligned overlap-add (WSOLA-style), bounded slowdown.
export function stretchCandidate(input, sampleRate, rate) {
  if (!(rate >= .95 && rate <= 1) || !Number.isFinite(sampleRate) || sampleRate < 8000 || !(input instanceof Float32Array)) throw Error("Invalid candidate parameters")
  if (rate === 1 || input.length < Math.round(sampleRate*.06)) return input.slice()
  const hop=Math.round(sampleRate*.02), search=Math.round(sampleRate*.008)
  const target=Math.ceil(input.length/rate)
  const output=new Float32Array(target)
  output.set(input.subarray(0,Math.min(hop,target)))
  let pos=hop
  while (pos<target) {
    const expected=Math.round(pos*rate), lo=Math.max(0,expected-search), hi=Math.min(input.length-hop,expected+search)
    if (hi<lo) break
    let best=lo, bestScore=-Infinity
    const overlap=Math.min(hop,pos,target-pos)
    // Select a waveform match to the previous source continuation, not
    // a resampled waveform. Keep a bounded search and unity local pitch.
    for(let k=lo;k<=hi;k+=Math.max(1,Math.round(sampleRate/12000))) {
      let dot=0,a2=1e-12,b2=1e-12
      for(let i=0;i<overlap;i+=4) {
        const a=output[pos-hop+i], b=input[k-hop>=0?k-hop+i:k+i]
        dot+=a*b;a2+=a*a;b2+=b*b
      }
      const score=dot/Math.sqrt(a2*b2)-.02*Math.abs(k-expected)/Math.max(1,search)
      if(score>bestScore){bestScore=score;best=k}
    }
    // Crossfade the overlap against the previous source continuation.
    // Use only existing source samples, never arbitrary silence padding.
    for(let i=0;i<overlap;i++){
      const u=(i+1)/(overlap+1), oldIndex=Math.min(input.length-1,Math.round((pos-hop)*rate)+hop+i)
      output[pos+i]=(1-u)*input[oldIndex]+u*input[Math.min(input.length-1,best+i)]
    }
    pos+=overlap
  }
  return output.subarray(0,pos)
}
