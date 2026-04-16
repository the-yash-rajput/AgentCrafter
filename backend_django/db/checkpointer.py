"""
Process-scoped PostgresSaver singleton for LangGraph checkpoint storage.

Uses the same DATABASE_URL as the SQLAlchemy engine but via a psycopg3
connection string. The singleton is initialised lazily on first call and
reused for the lifetime of the process, so setup() (which creates the
checkpoint tables) is called at most once per process.
"""
from __future__ import annotations

import os
import threading

_lock = threading.Lock()
_saver = None


def get_checkpointer():
    """
    Return the process-scoped PostgresSaver instance.

    Thread-safe: uses double-checked locking so only one thread ever calls
    setup() even under concurrent request startup.
    """
    global _saver
    if _saver is not None:
        return _saver

    with _lock:
        if _saver is not None:  # re-check inside the lock
            return _saver

        from langgraph.checkpoint.postgres import PostgresSaver

        db_url = os.getenv(
            "DATABASE_URL",
            "postgresql://langgraph:langgraph_secret@localhost:5733/ldb",
        )
        saver = PostgresSaver.from_conn_string(db_url)
        # idempotent: creates checkpoints / checkpoint_blobs / checkpoint_writes
        # tables if they don't already exist
        saver.setup()
        _saver = saver

    return _saver
