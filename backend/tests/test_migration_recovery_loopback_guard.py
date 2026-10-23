"""Recovery tools must not disguise a remote connection behind a loopback URL."""
import importlib.util
from pathlib import Path
import pytest

spec = importlib.util.spec_from_file_location("_recovery_url_guard", Path(__file__).resolve().parents[2] / "scripts/migration_recovery/replay.py")
replay = importlib.util.module_from_spec(spec)
spec.loader.exec_module(replay)

@pytest.mark.parametrize("url", [
    "postgresql://postgres:password@remote.example/postgres",
    "postgresql://postgres@localhost/postgres?host=remote.example",
    "postgresql://postgres@127.0.0.1/postgres?hostaddr=192.0.2.1",
    "postgresql://postgres@127.0.0.1/postgres?service=production",
])
def test_remote_or_override_connection_is_refused(url):
    with pytest.raises(ValueError, match="loopback"):
        replay.local_url(url)


def test_explicit_disposable_loopback_connection_is_accepted():
    url = "postgresql://postgres:postgres@127.0.0.1:54322/postgres"
    assert replay.local_url(url) == url
