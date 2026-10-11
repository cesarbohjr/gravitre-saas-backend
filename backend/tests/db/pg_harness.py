"""Throwaway PostgreSQL cluster for migration tests (initdb + pg_ctl on a unix socket).

Shared by the tests in this package. Skips when no PostgreSQL server binaries are
installed; GRAVITRE_PG_BIN points at a specific bin directory.
"""
from __future__ import annotations

import contextlib
import glob
import os
import shutil
import subprocess
import tempfile
from collections.abc import Iterator
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
MIGRATIONS = REPO_ROOT / "supabase" / "migrations"


def _pg_bin() -> Path | None:
    env = os.environ.get("GRAVITRE_PG_BIN")
    candidates = [env] if env else []
    candidates += sorted(glob.glob("/usr/lib/postgresql/*/bin"), reverse=True)
    for c in candidates:
        if c and (Path(c) / "initdb").exists() and (Path(c) / "pg_ctl").exists():
            return Path(c)
    return None


PG_BIN = _pg_bin()
requires_pg = pytest.mark.skipif(PG_BIN is None, reason="PostgreSQL server binaries not installed")


class Pg:
    def __init__(self, root: Path, run_as: list[str]) -> None:
        self.root = root
        self.data = root / "data"
        self.sock = root / "sock"
        self.run_as = run_as
        self.port = "54329"

    def _cmd(self, binary: str, *args: str) -> list[str]:
        return [*self.run_as, str(PG_BIN / binary), *args]

    def start(self) -> None:
        self.sock.mkdir()
        if self.run_as:
            shutil.chown(self.sock, "postgres", "postgres")
        subprocess.run(
            self._cmd("initdb", "-D", str(self.data), "-A", "trust", "-U", "postgres", "--no-sync"),
            check=True,
            capture_output=True,
        )
        opts = f"-k {self.sock} -p {self.port} -c listen_addresses='' -c fsync=off"
        subprocess.run(
            self._cmd("pg_ctl", "-D", str(self.data), "-o", opts, "-w", "-l", str(self.root / "log"), "start"),
            check=True,
            capture_output=True,
        )

    def stop(self) -> None:
        subprocess.run(
            self._cmd("pg_ctl", "-D", str(self.data), "-m", "immediate", "stop"),
            capture_output=True,
            check=False,
        )

    def psql(self, sql: str, *, check: bool = True) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [
                str(PG_BIN / "psql"),
                "-h", str(self.sock), "-p", self.port, "-U", "postgres", "-d", "postgres",
                "-X", "-q", "-At", "-v", "ON_ERROR_STOP=1",
            ],
            input=sql,
            text=True,
            capture_output=True,
            check=check,
        )

    def value(self, sql: str) -> str:
        return self.psql(sql).stdout.strip()


@contextlib.contextmanager
def pg_cluster(*scripts: str) -> Iterator[Pg]:
    """Start a private cluster, run ``scripts`` in order, yield it, then remove it."""
    assert PG_BIN is not None
    root = Path(tempfile.mkdtemp(prefix="gravitre-pg-"))
    run_as: list[str] = []
    if os.geteuid() == 0:
        if shutil.which("runuser") is None:
            pytest.skip("running as root without runuser")
        shutil.chown(root, "postgres", "postgres")
        os.chmod(root, 0o777)
        run_as = ["runuser", "-u", "postgres", "--"]
    server = Pg(root, run_as)
    server.start()
    try:
        for sql in scripts:
            server.psql(sql)
        yield server
    finally:
        server.stop()
        shutil.rmtree(root, ignore_errors=True)
