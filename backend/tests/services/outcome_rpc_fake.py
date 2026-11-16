"""Sequential unit transport only; PostgreSQL tests prove transaction semantics."""
from copy import deepcopy
from types import SimpleNamespace


def outcome_rpc(row, name, args):
    def execute():
        if name == "persist_workflow_run_outcome":
            status = args["p_status"]
            if row["status"] in {"completed", "failed", "cancelled", "partial_success"} and row["status"] != status:
                return SimpleNamespace(data={"accepted": False, "status": row["status"]})
            if row["status"] != status or row["parameters"].get("terminal_outcome_version") != 2:
                row["parameters"].update(deepcopy(args["p_patch"]))
                row["parameters"].update(terminal_outcome_version=2, outcome_actor_id=args["p_actor_id"],
                    outcome_actor_required=bool(args["p_actor_id"]), outcome_fanout_version=1)
                row.update(status=status, error_message=args["p_error_message"])
            return SimpleNamespace(data={"accepted": True, "status": status,
                "parameters": deepcopy(row["parameters"]), "error_message": row.get("error_message")})
        assert name == "checkpoint_workflow_run_outcome"
        if row["status"] != args["p_status"]:
            return SimpleNamespace(data={"accepted": False, "status": row["status"]})
        old = row["parameters"].get("outcome_fanout", {})
        receipt = {key: old.get(key) is True or args["p_receipt"].get(key) is True
                   for key in ("run_persisted", "audit_written", "notification_emitted", "learning_recorded")}
        required = ["run_persisted", "learning_recorded"]
        if row["parameters"].get("outcome_actor_required") or args["p_actor_required"]:
            required += ["audit_written", "notification_emitted"]
        requested = bool(args["p_finalize"] or old.get("finalize_requested"))
        receipt.update(status=args["p_status"], finalize_requested=requested,
                       complete=requested and all(receipt[key] for key in required))
        row["parameters"].update(outcome_fanout_version=1, outcome_fanout=deepcopy(receipt),
            outcome_finalized=receipt["complete"], notification_emitted=receipt["notification_emitted"])
        return SimpleNamespace(data={"accepted": True, "status": row["status"], "receipt": receipt})
    return SimpleNamespace(execute=execute)
