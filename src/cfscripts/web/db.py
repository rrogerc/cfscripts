"""Neon Postgres access for the ranked queue.

One table holds the whole game: a match row is created when the player
queues and finalized (result + elo_after) when it resolves. Current elo is
derived from the newest resolved row, so history is the single source of
truth and there is no state table to drift out of sync.

Connections are opened per request — Neon's pooled DATABASE_URL makes that
cheap on serverless.
"""

import os
import threading

import psycopg
from psycopg.rows import dict_row

_SCHEMA = """
CREATE TABLE IF NOT EXISTS ranked_matches (
    id BIGSERIAL PRIMARY KEY,
    handle TEXT NOT NULL,
    contest_id INTEGER NOT NULL,
    problem_index TEXT NOT NULL,
    problem_name TEXT NOT NULL,
    problem_rating INTEGER NOT NULL,
    start_ts BIGINT NOT NULL,
    deadline_ts BIGINT NOT NULL,
    elo_before DOUBLE PRECISION NOT NULL,
    elo_after DOUBLE PRECISION,
    result TEXT,
    solved_ts BIGINT
);
CREATE INDEX IF NOT EXISTS ranked_matches_handle_id_idx
    ON ranked_matches (handle, id);
"""

_schema_ready = False
_schema_lock = threading.Lock()


class DatabaseNotConfigured(Exception):
    pass


def connect():
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise DatabaseNotConfigured(
            "DATABASE_URL is not set — provision the Neon integration first"
        )
    conn = psycopg.connect(url, row_factory=dict_row)
    global _schema_ready
    if not _schema_ready:
        with _schema_lock:
            if not _schema_ready:
                conn.execute(_SCHEMA)
                conn.commit()
                _schema_ready = True
    return conn


def fetch_matches(conn, handle):
    """All match rows for handle, oldest first."""
    return conn.execute(
        "SELECT * FROM ranked_matches WHERE handle = %s ORDER BY id",
        (handle,),
    ).fetchall()


def insert_match(conn, handle, problem, start_ts, deadline_ts, elo_before):
    row = conn.execute(
        """
        INSERT INTO ranked_matches
            (handle, contest_id, problem_index, problem_name, problem_rating,
             start_ts, deadline_ts, elo_before)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING *
        """,
        (
            handle,
            problem["contestId"],
            problem["index"],
            problem["name"],
            problem["rating"],
            start_ts,
            deadline_ts,
            elo_before,
        ),
    ).fetchone()
    conn.commit()
    return row


def finalize_match(conn, match_id, result, elo_after, solved_ts):
    """Set the outcome on an unresolved row; returns the updated row or None.

    The `result IS NULL` guard makes concurrent resolution attempts (two
    clients polling at once) idempotent — only one write wins.
    """
    row = conn.execute(
        """
        UPDATE ranked_matches
        SET result = %s, elo_after = %s, solved_ts = %s
        WHERE id = %s AND result IS NULL
        RETURNING *
        """,
        (result, elo_after, solved_ts, match_id),
    ).fetchone()
    conn.commit()
    return row
