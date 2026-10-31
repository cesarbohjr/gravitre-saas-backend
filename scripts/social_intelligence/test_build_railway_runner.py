import importlib.util
import json
from pathlib import Path
import re
import subprocess
import unittest

spec = importlib.util.spec_from_file_location("runner_build", Path(__file__).with_name("build_railway_runner.py"))
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class RunnerBuildTests(unittest.TestCase):
    def bundle(self):
        return {"source_dirty": False, "data_scope": "fixed_synthetic_only", "profiles": [{"system": "Español"} for _ in range(40)], "cases": [{"id": str(i)} for i in range(26)]}

    def test_embedded_payload_is_exact_and_bundle_has_no_local_imports(self):
        bundle = self.bundle()
        code = module.build(bundle)
        payload = re.search(r"brotliDecompressSync\(Buffer.from\('([A-Za-z0-9+/=]+)'", code).group(1)
        decoded = subprocess.check_output(["node", "--input-type=module", "-e", "import {brotliDecompressSync} from 'node:zlib'; import {readFileSync} from 'node:fs'; process.stdout.write(brotliDecompressSync(Buffer.from(readFileSync(0,'utf8'),'base64')));"], input=payload.encode(), timeout=60)
        self.assertEqual(json.loads(decoded), bundle)
        self.assertNotIn("from './", code)
        self.assertNotIn("Bun.file(process.argv[2])", code)
        self.assertIn("Tested runner source SHA256", code)

    def test_dirty_or_incomplete_inputs_are_rejected(self):
        for changed in ({"source_dirty": True}, {"data_scope": "customer"}, {"cases": []}):
            with self.assertRaises(ValueError):
                module.build({**self.bundle(), **changed})


if __name__ == "__main__":
    unittest.main()
