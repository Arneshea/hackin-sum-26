"""
Postgres access layer.

Section 6.1: PostgreSQL is the source of truth. This module is the
only place backend code should open a database connection — routes,
the referral engine, and the triage service must go through here
rather than embedding psycopg2 calls directly (section 41R).

Uses the Supabase service-role connection string, which bypasses RLS.
Application-level authorization (which role can call which endpoint)
is enforced in the route layer; RLS in 003_rls_policies.sql governs
what the frontend can read/write directly via the Supabase client.
"""

import json
import psycopg2
import psycopg2.extras
from contextlib import contextmanager

from app.config import get_config

_pool_conn = None


def _connect():
    cfg = get_config()
    if not cfg.SUPABASE_DB_URL:
        raise RuntimeError(
            "SUPABASE_DB_URL is not configured. Set it in your .env — "
            "see .env.example and docs/PROTOTYPE_LIMITATIONS.md."
        )
    return psycopg2.connect(cfg.SUPABASE_DB_URL)


@contextmanager
def get_cursor(commit: bool = False):
    """Yield a RealDictCursor; commits on success if commit=True."""
    global _pool_conn
    if _pool_conn is None or _pool_conn.closed:
        _pool_conn = _connect()
    cur = _pool_conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    try:
        yield cur
        if commit:
            _pool_conn.commit()
    except Exception:
        _pool_conn.rollback()
        raise
    finally:
        cur.close()


def db_reachable() -> bool:
    try:
        with get_cursor() as cur:
            cur.execute("select 1")
            cur.fetchone()
        return True
    except Exception:
        return False


def get_prototype_config(key: str, default=None):
    """
    Read a tunable prototype-assumption value from `prototype_config`
    (section 0.10). Returns the parsed JSON value.

    Falls back to `default` if the database is unreachable (e.g. pure
    unit tests running without SUPABASE_DB_URL configured, per step
    22.1 — referral-engine logic tests should not require a live DB).
    This fallback is app configuration, not a clinical value, so it is
    an acceptable degradation; it does not fabricate patient/hospital
    data.
    """
    try:
        with get_cursor() as cur:
            cur.execute("select value from prototype_config where key = %s", (key,))
            row = cur.fetchone()
            if row is None:
                return default
            return row["value"]
    except Exception:
        return default


def record_audit_event(actor_id, actor_role, action, entity_type, entity_id, metadata=None):
    """Append-only audit log write (section 20)."""
    with get_cursor(commit=True) as cur:
        cur.execute(
            """
            insert into audit_events (actor_id, actor_role, action, entity_type, entity_id, metadata)
            values (%s, %s, %s, %s, %s, %s)
            """,
            (actor_id, actor_role, action, entity_type, entity_id, json.dumps(metadata or {})),
        )
