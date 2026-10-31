import importlib.util
from pathlib import Path
import unittest


path = Path(__file__).resolve().parents[1] / "scripts/bootstrap_voice_acceptance.py"
spec = importlib.util.spec_from_file_location("voice_acceptance_bootstrap", path)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class AcceptanceTargetTests(unittest.TestCase):
    def configuration(self):
        return {"SUPABASE_URL": module.TARGET, "E2E_SUPABASE_ALLOWED_URL": module.TARGET,
                "SUPABASE_SERVICE_ROLE_KEY": "test-only-placeholder"}

    def test_refuses_production_before_loading_or_using_client(self):
        env = self.configuration()
        env["SUPABASE_URL"] = "https://smyeexlrqdpymwjmgzqu.supabase.co"
        with self.assertRaises(ValueError):
            module.provision(env, None)

    def test_refuses_missing_explicit_allowlist(self):
        env = self.configuration()
        env.pop("E2E_SUPABASE_ALLOWED_URL")
        with self.assertRaises(ValueError):
            module.provision(env, None)

    def test_refuses_missing_acceptance_credential(self):
        env = self.configuration()
        env.pop("SUPABASE_SERVICE_ROLE_KEY")
        with self.assertRaises(ValueError):
            module.provision(env, None)

    def test_exact_test_target_is_accepted(self):
        module.assert_target(self.configuration())


if __name__ == "__main__":
    unittest.main()
