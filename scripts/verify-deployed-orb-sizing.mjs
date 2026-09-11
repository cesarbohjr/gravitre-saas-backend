const BASE = "https://gravitre.app";
const NEEDLES = [["data-voice-orb-sizing","orb sizing source marker"],["--gv-orb-bloom","proportional bloom variable"]];
const found = new Set();
for (const page of ["/login","/dashboard"]) {
  const html = await (await fetch(BASE+page,{redirect:"follow"})).text();
  for (const m of html.matchAll(/\/?_next\/static\/[^"'\s)]+?\.js/g)) found.add(new URL(m[0].startsWith("/")?m[0]:"/"+m[0], BASE).toString());
}
console.log("chunks="+found.size);
const hits = new Map(NEEDLES.map(([n])=>[n,[]]));
for (const url of found) { const r = await fetch(url); if(!r.ok) continue; const b = await r.text(); for (const [n] of NEEDLES) if (b.includes(n)) hits.get(n).push(url.split("/").pop()); }
let fail=0;
for (const [n,d] of NEEDLES) { const w=hits.get(n); if(w.length) console.log(`PASS  ${d}: "${n}" in ${w.join(", ")}`); else { console.log(`FAIL  ${d}: "${n}" not found`); fail++; } }
console.log(fail? "RESULT: FAIL":"RESULT: PASS");
