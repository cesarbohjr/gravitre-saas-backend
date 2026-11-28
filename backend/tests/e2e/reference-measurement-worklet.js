// Passive analysis only. Outputs remain silent; native HTML audio owns playout.
class ReferenceMeasurement extends AudioWorkletProcessor {
  constructor(){super();this.buf=new Float32Array(480);this.i=0;this.start=0}
  process(inputs){
    const x=inputs[0]?.[0];if(!x)return true
    for(let k=0;k<x.length;k++){
      if(!this.i)this.start=currentFrame+k
      this.buf[this.i++]=x[k]
      if(this.i===this.buf.length){
        const energy=hz=>{let re=0,im=0,n=0;for(let i=0;i<this.buf.length;i++){const w=.5-.5*Math.cos(2*Math.PI*i/(this.buf.length-1));const a=2*Math.PI*hz*i/sampleRate;re+=this.buf[i]*w*Math.cos(a);im+=this.buf[i]*w*Math.sin(a);n+=w}return 2*Math.hypot(re,im)/n}
        this.port.postMessage({startMs:1000*this.start/sampleRate,endMs:1000*(this.start+this.buf.length)/sampleRate,oldEnergy:energy(1100),newEnergy:energy(1700)})
        this.i=0
      }
    }
    return true
  }
}
registerProcessor('reference-measurement',ReferenceMeasurement)
