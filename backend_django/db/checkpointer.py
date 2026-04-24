"""
Process-scoped PostgresSaver singleton for LangGraph checkpoint storage.

Uses the same DATABASE_URL as the SQLAlchemy engine but via a psycopg3
connection. The singleton is initialised lazily on first call and reused
for the lifetime of the process, so setup() is called at most once.

Note: PostgresSaver.from_conn_string() is a context manager — it cannot
be used for a long-lived singleton. Instead we open a psycopg connection
directly (with autocommit=True, which PostgresSaver requires) and pass
it to the constructor.
"""
from __future__ import annotations

import os
import threading

_lock = threading.Lock()
_saver = None


def get_checkpointer():
    """
    Return the process-scoped PostgresSaver instance.

    Thread-safe: double-checked locking ensures setup() runs exactly once.
    """
    global _saver
    if _saver is not None:
        return _saver

    with _lock:
        if _saver is not None:
            return _saver

        import psycopg
        from langgraph.checkpoint.postgres import PostgresSaver

        db_url = os.getenv(
            "DATABASE_URL",
            "postgresql://langgraph:langgraph_secret@localhost:5733/lbdnew",
        )
        # autocommit=True is required by PostgresSaver
        conn = psycopg.connect(db_url, autocommit=True)
        saver = PostgresSaver(conn)
        # idempotent: creates checkpoints / checkpoint_blobs / checkpoint_writes
        # tables if they don't already exist
        saver.setup()
        _saver = saver

    return _saver
