#!/usr/bin/env node
/** Fail CI if a new Next.js route root was not reviewed as public or private. */
import fs from "node:fs"
const source = fs.readFileSync("apps/web/lib/route-root-access.ts", "utf8")
function declared(name) {
  const block = source.match(new RegExp(`export const ${name} = \\[([\\s\\S]*?)\\] as const`))
  if (!block) throw new Error(`Missing route classification registry ${name}`)
  return new Set([...block[1].matchAll(/"([^"]+)"/g)].map(match => match[1]))
}
function directories(path) {
  return new Set(fs.readdirSync(path, {withFileTypes:true}).filter(e=>e.isDirectory()).map(e=>e.name))
}
let failures = 0
for (const [group,registry] of [["(app)","PRIVATE_ROUTE_ROOTS"],["(marketing)","PUBLIC_MARKETING_ROUTE_ROOTS"]]) {
  const live = directories(`apps/web/app/${group}`)
  const expected = declared(registry)
  for(const name of live) if(!expected.has(name)){console.error(`Route classification missing: ${group}/${name}`);failures++}
  for(const name of expected) if(!live.has(name)){console.error(`Stale route classification: ${registry}/${name}`);failures++}
}
if(failures)process.exit(1)
console.log("Route-group access registry matches current app routes.")
