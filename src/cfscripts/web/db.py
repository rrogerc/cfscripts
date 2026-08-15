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
CREATE TABLE IF NOT EXISTS problem_solutions (
    contest_id INTEGER NOT NULL,
    problem_index TEXT NOT NULL,
    status TEXT NOT NULL,
    content_md TEXT,
    model TEXT,
    source_url TEXT,
    updated_ts BIGINT NOT NULL,
    PRIMARY KEY (contest_id, problem_index)
);
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


def fetch_match(conn, handle, match_id):
    return conn.execute(
        "SELECT * FROM ranked_matches WHERE id = %s AND handle = %s",
        (match_id, handle),
    ).fetchone()


def get_solution(conn, contest_id, problem_index):
    return conn.execute(
        """
        SELECT * FROM problem_solutions
        WHERE contest_id = %s AND problem_index = %s
        """,
        (contest_id, problem_index),
    ).fetchone()


def claim_solution(conn, contest_id, problem_index, now, stale_before):
    """Take the generation lock: insert a 'pending' row, or adopt one that a
    crashed generator left behind. Returns the row if we hold the lock, None
    if another request holds it (or the solution is already done)."""
    row = conn.execute(
        """
        INSERT INTO problem_solutions (contest_id, problem_index, status, updated_ts)
        VALUES (%s, %s, 'pending', %s)
        ON CONFLICT (contest_id, problem_index) DO UPDATE
            SET status = 'pending', updated_ts = EXCLUDED.updated_ts
            WHERE problem_solutions.status = 'pending'
              AND problem_solutions.updated_ts < %s
        RETURNING *
        """,
        (contest_id, problem_index, now, stale_before),
    ).fetchone()
    conn.commit()
    return row


def finish_solution(conn, contest_id, problem_index, content_md, model,
                    source_url, now):
    row = conn.execute(
        """
        UPDATE problem_solutions
        SET status = 'done', content_md = %s, model = %s,
            source_url = %s, updated_ts = %s
        WHERE contest_id = %s AND problem_index = %s
        RETURNING *
        """,
        (content_md, model, source_url, now, contest_id, problem_index),
    ).fetchone()
    conn.commit()
    return row


def release_solution(conn, contest_id, problem_index):
    """Drop a failed generation's pending row so a retry can claim fresh."""
    conn.execute(
        """
        DELETE FROM problem_solutions
        WHERE contest_id = %s AND problem_index = %s AND status = 'pending'
        """,
        (contest_id, problem_index),
    )
    conn.commit()


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
