import { execSync } from "node:child_process"
import fs from "node:fs"
import path from "node:path"

const repoRoot = path.resolve(__dirname, "..")
const fixturesPath = path.join(repoRoot, "e2e", ".fixtures", "billing-users.json")

export default async function globalSetup() {
  if (process.env.E2E_SKIP_FIXTURE_SEED === "1" && fs.existsSync(fixturesPath)) {
    console.log("[e2e] Skipping fixture seed (E2E_SKIP_FIXTURE_SEED=1)")
    return
  }

  const python = process.env.PYTHON ?? "python"
  execSync(`${python} scripts/billing-e2e-fixtures.py`, {
    cwd: repoRoot,
    stdio: "inherit",
    env: process.env,
  })

  if (!fs.existsSync(fixturesPath)) {
    throw new Error(`Fixture seed did not produce ${fixturesPath}`)
  }
}
