"""Seed disposable MSP database fixtures. Refuses non-local database targets."""
import os
from urllib.parse import urlparse
import uuid
import psycopg

dsn = os.environ["MSP_TEST_DATABASE_URL"]
url = urlparse(dsn)
if (url.hostname, url.port, url.path) != ("127.0.0.1", 54322, "/postgres"):
    raise SystemExit("Refusing to seed: MSP integration tests require local Supabase at 127.0.0.1:54322/postgres")

with psycopg.connect(dsn) as conn:
    with conn.cursor() as cur:
        for label in ("customer-a", "customer-b"):
            slug = "msp-isolation-ci-" + label
            cur.execute(
                "INSERT INTO public.organizations (id, name, slug, status) "
                "VALUES (%s, %s, %s, 'active') ON CONFLICT (slug) DO NOTHING",
                (uuid.uuid4(), "MSP isolated fixture " + label, slug),
            )
        cur.execute(
            "SELECT count(*) FROM public.organizations WHERE slug IN (%s, %s)",
            ("msp-isolation-ci-customer-a", "msp-isolation-ci-customer-b"),
        )
        if cur.fetchone()[0] != 2:
            raise RuntimeError("Failed to seed two isolated customer organizations")
print("Seeded two disposable customer organizations for MSP database tests.")
