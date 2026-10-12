"""Phase 6: Background ingestion worker runner."""
from __future__ import annotations

import argparse
import os
import socket
import time
import uuid

from supabase import create_client

from app.config import get_settings
from app.rag.worker import run_worker_once


def main() -> None:
    parser = argparse.ArgumentParser(description="Process queued RAG ingest jobs")
    parser.add_argument("--once", action="store_true", help="Process at most one job and exit")
    parser.add_argument("--poll-interval", type=int, default=5, help="Poll interval in seconds")
    parser.add_argument("--visibility-timeout", type=int, default=300, help="Visibility timeout in seconds")
    parser.add_argument("--worker-id", type=str, default="", help="Worker id (optional)")
    args = parser.parse_args()

    settings = get_settings()
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    worker_id = args.worker_id.strip()
    if not worker_id:
        worker_id = f"{socket.gethostname()}-{os.getpid()}-{uuid.uuid4().hex[:8]}"

    while True:
        # Same gates as ``python -m app.rag.worker``: DISABLE_INGESTION, the owner's
        # EXISTING_INGESTION_REQUIRES_LIFECYCLE switch, and the pilot interlock for
        # jobs of RAG_WORKER_PILOT_ORG_IDS orgs.
        outcome = run_worker_once(settings, client, worker_id, args.visibility_timeout)
        if args.once:
            return
        if outcome != "processed":
            time.sleep(args.poll_interval)


if __name__ == "__main__":
    main()
