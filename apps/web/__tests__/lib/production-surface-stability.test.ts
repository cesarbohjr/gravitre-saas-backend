import { describe, expect, it } from "vitest"
import fs from "node:fs"
import path from "node:path"
const read=(p:string)=>fs.readFileSync(path.join(process.cwd(),p),"utf8")

describe("production surface stability",()=>{
  it("distinguishes failed actions from browser transport failures",()=>{
    const c=read("components/gravitre/ai-runtime-details.tsx")
    expect(c).toMatch(/executionResult\?\.success === false/)
    expect(c).toMatch(/requested action did not complete/)
    expect(c).toMatch(/reply connection ended before completion was confirmed/)
    expect(c).toMatch(/label: "Reason"/)
  })
  it("keeps the Ask Gravitre dock movable",()=>{
    const c=read("components/gravitre/ai-helper.tsx")
    expect(c).toMatch(/motion\.button/)
    expect(c).toMatch(/dragMomentum=\{false\}/)
    expect(c).toMatch(/cursor-grab/)
  })
  it("keeps the settings rail on one continuous surface",()=>{
    const c=read("components/settings/settings-shell.tsx")
    expect(c).toMatch(/min-h-full/)
    expect(c).toMatch(/self-stretch/)
    expect(c).not.toMatch(/bg-\[color:var\(--g-surface-1\)\]\/95 p-4/)
  })
})
