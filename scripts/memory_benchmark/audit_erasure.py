"""Pinned-source and real SQLite history probe; never a complete SDK/quality pass.

Uses only synthetic records in a temporary directory. It imports the verified
upstream storage module directly, avoiding SDK initialization, telemetry and
provider clients. A successful investigation may (and currently does) report
complete_erasure_gate=FAIL. Exit zero means the investigation reproduced its
assertions, not that Mem0 passed the adoption gate.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
from pathlib import Path
import runpy
import sqlite3
import tempfile

HERE = Path(__file__).resolve().parent


def investigate(package_root: Path) -> dict:
    manifest = json.loads((HERE / "engine_source.json").read_text())
    paths = ("mem0/memory/main.py", "mem0/memory/storage.py")
    sources = {}
    hashes = {}
    for path in paths:
        raw = (package_root / path).read_bytes()
        digest = hashlib.sha256(raw).hexdigest()
        if digest != manifest["files"][path]:
            raise ValueError("Pinned upstream source mismatch")
        hashes[path] = digest
        sources[path] = raw.decode()

    # Verify the actual call chain and record its locations. These checks are
    # tied to exact upstream hashes; no heuristic classification of a new SDK.
    tree = ast.parse(sources[paths[0]])
    memory = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "Memory")
    methods = {n.name: n for n in memory.body if isinstance(n, ast.FunctionDef)}

    def calls(name):
        return {ast.unparse(n.func) for n in ast.walk(methods[name]) if isinstance(n, ast.Call)}

    assert "self._delete_memory" in calls("delete")
    assert "self._delete_memory" in calls("delete_all")
    assert {"self.vector_store.delete", "self.db.add_history"} <= calls("_delete_memory")
    assert "self.db.get_history" in calls("history")
    assert "self.db.reset" in calls("reset")
    history_call = next(n for n in ast.walk(methods["_delete_memory"])
                        if isinstance(n, ast.Call) and ast.unparse(n.func) == "self.db.add_history")
    assert ast.unparse(history_call.args[1]) == "prev_value"
    assert ast.literal_eval(history_call.args[2]) is None
    assert ast.literal_eval(history_call.args[3]) == "DELETE"
    assert any(k.arg == "is_deleted" and ast.literal_eval(k.value) == 1 for k in history_call.keywords)

    storage = runpy.run_path(str(package_root / paths[1]))["SQLiteManager"]
    # Reproduce the history writes made by upstream add/update/delete. This is
    # the real storage implementation, not an execution of vector/model APIs.
    with tempfile.TemporaryDirectory(prefix="mem0-erasure-audit-") as temporary:
        root = Path(temporary)
        database = root / "history.sqlite"
        db = storage(str(database))
        try:
            db.add_history("synthetic-a", None, "synthetic original", "ADD")
            db.add_history("synthetic-a", "synthetic original", "synthetic correction", "UPDATE")
            db.add_history("synthetic-a", "synthetic correction", None, "DELETE", is_deleted=1)
            db.add_history("synthetic-b", None, "synthetic separate scope", "ADD")
            rows = db.get_history("synthetic-a")
            assert len(rows) == 3 and rows[-1]["is_deleted"] == 1
            assert any(r["old_memory"] or r["new_memory"] for r in rows)
            # Use SQLite's supported backup API, never copy an open database.
            with sqlite3.connect(root / "snapshot.sqlite") as snapshot:
                db.connection.backup(snapshot)
        finally:
            db.close()
        db = storage(str(database))
        try:
            assert len(db.get_history("synthetic-a")) == 3
            assert len(db.get_history("synthetic-b")) == 1
            db.reset()
        finally:
            db.close()
        db = storage(str(database))
        try:
            assert not db.get_history("synthetic-a") and not db.get_history("synthetic-b")
        finally:
            db.close()
        snapshot = storage(str(root / "snapshot.sqlite"))
        try:
            assert len(snapshot.get_history("synthetic-a")) == 3
        finally:
            snapshot.close()

    return {
        "schema_version": 1,
        "version": manifest["version"],
        "source_revision": manifest["revision"],
        "source_hashes": hashes,
        "source_locations": {name: {"start": methods[name].lineno, "end": methods[name].end_lineno}
                             for name in ("delete", "delete_all", "_delete_memory", "history", "reset")},
        "probe": "upstream_sqlite_storage_only",
        "history_rows_after_delete_event": 3,
        "history_retained_after_restart": True,
        "delete_event_retains_previous_text": True,
        "global_reset_removes_other_scope_history": True,
        "pre_reset_snapshot_retains_history": True,
        "complete_erasure_gate": "FAIL",
        "scoped_supported_erasure_remedy": "NOT_IDENTIFIED_IN_PINNED_SOURCE",
        "physical_disk_backup_erasure": "NOT_CERTIFIED",
        "sdk_vector_lifecycle": "NOT_RUN_BY_THIS_PROBE",
        "semantic_quality_comparison": "NOT_RUN",
        "production_certified": False,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package-root", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    report = investigate(args.package_root.resolve())
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"investigation": "PASS", "complete_erasure_gate": report["complete_erasure_gate"]}))


if __name__ == "__main__":
    main()
