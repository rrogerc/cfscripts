from time import time
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from cfscripts.core import ranked
from cfscripts.core.picker import get_problem_by_level
from cfscripts.core.scraper import get_problem_html
from cfscripts.lib.api import CACHE_NONE, ApiError
from cfscripts.lib.contests import get_participations
from cfscripts.lib.performance import UserPerformanceCalculator
from cfscripts.lib.rating import get_rating_changes_for_user
from cfscripts.lib.submissions import get_submissions
from cfscripts.web import db, solutions

app = FastAPI()


@app.exception_handler(ApiError)
def _api_error(request, exc):
    return JSONResponse(status_code=502, content={"detail": str(exc)})


@app.exception_handler(solutions.SolutionUnavailable)
def _solution_unavailable(request, exc):
    return JSONResponse(status_code=502, content={"detail": str(exc)})


@app.exception_handler(db.DatabaseNotConfigured)
def _db_not_configured(request, exc):
    return JSONResponse(status_code=503, content={"detail": str(exc)})

# Allow CORS for frontend integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/api/pick")
def pick_problem(handle: str, level: int):
    try:
        # Filter out problems the user has already solved. Fetch submissions
        # fresh (CACHE_NONE) so a problem just AC'd is excluded on the next pick
        # instead of lingering until the short cache expires.
        best = get_problem_by_level(handle, level, use_solved=True, solved_cache=CACHE_NONE)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    if best is None:
        raise HTTPException(status_code=404, detail=f"No problem found for level {level}")

    html_content = get_problem_html(best["contestId"], best["index"])

    return {
        "problem": best,
        "html": html_content
    }

@app.get("/api/participations")
def participations(handle: str):
    """List contests the user participated in (contestant/virtual/out-of-comp), newest first.

    Also returns the user's current official rating (last rating change),
    so the client can contrast it with the simulated rating.
    """
    try:
        parts = get_participations(handle)
        changes = get_rating_changes_for_user(handle)
        official = changes[-1]["newRating"] if changes else None
        return {"participations": parts, "official_rating": official}
    except ApiError as e:
        raise HTTPException(status_code=502, detail=str(e))

@app.get("/api/perf")
def perf(
    handle: str,
    contest_id: int,
    rating: Optional[int] = None,
    start_time: Optional[int] = None,
):
    """Rank/delta/performance for one contest.

    Optional `rating` overrides the user's rating at contest time — used by the
    client-side whatif simulation to chain contests with a simulated rating.
    Optional `start_time` (from /api/participations) picks the specific run
    when the user has several for one contest. Skips the ratedList fallback for
    just-ended contests (payload too large for serverless); those return
    delta/performance as "unknown".
    """
    try:
        calculator = UserPerformanceCalculator(handle)
        data = calculator.get_performance(
            contest_id,
            current_rating=rating,
            ratedlist_fallback=False,
            start_time=start_time,
        )
    except ApiError as e:
        raise HTTPException(status_code=502, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except (KeyError, TypeError, AssertionError):
        raise HTTPException(
            status_code=404,
            detail=f"No ranked result for {handle} in contest {contest_id}",
        )
    return data


def _active_payload(row):
    """Public view of a live match — problem_rating stays hidden until it ends."""
    if row is None:
        return None
    return {
        "id": row["id"],
        "contest_id": row["contest_id"],
        "problem_index": row["problem_index"],
        "problem_name": row["problem_name"],
        "start_ts": row["start_ts"],
        "deadline_ts": row["deadline_ts"],
    }


def _history_payload(row):
    return {
        "id": row["id"],
        "contest_id": row["contest_id"],
        "problem_index": row["problem_index"],
        "problem_name": row["problem_name"],
        "problem_rating": row["problem_rating"],
        "result": row["result"],
        "elo_before": row["elo_before"],
        "elo_after": row["elo_after"],
        "start_ts": row["start_ts"],
        "solved_ts": row["solved_ts"],
    }


def _ranked_snapshot(conn, handle):
    """Lazily resolve any live match, then return the full game state.

    Resolution needs no background process: an AC inside the window (from the
    user's own submission timestamps) is a win, being past the deadline
    without one is a loss — both are decided whenever any client checks in.
    """
    rows = db.fetch_matches(conn, handle)
    active = next((r for r in rows if r["result"] is None), None)
    now = int(time())
    if active is not None:
        subs = get_submissions(handle, CACHE_NONE)
        result, solved_ts = ranked.resolve_match(active, subs, now)
        if result is not None:
            after = ranked.elo_after(
                active["elo_before"], active["problem_rating"], result == "win"
            )
            db.finalize_match(conn, active["id"], result, after, solved_ts)
            rows = db.fetch_matches(conn, handle)
            active = None

    resolved = [r for r in rows if r["result"] is not None]
    if resolved:
        elo = resolved[-1]["elo_after"]
        seeded = False
    else:
        changes = get_rating_changes_for_user(handle)
        elo = changes[-1]["newRating"] if changes else ranked.DEFAULT_SEED_ELO
        seeded = True
    wins = sum(1 for r in resolved if r["result"] == "win")

    return {
        "elo": elo,
        "seeded": seeded,
        "wins": wins,
        "losses": len(resolved) - wins,
        "server_now": now,
        "active": _active_payload(active),
        "history": [_history_payload(r) for r in reversed(resolved)],
    }


@app.get("/api/ranked/state")
def ranked_state(handle: str):
    """Current elo, W/L record, live match (if any), and match history."""
    with db.connect() as conn:
        return _ranked_snapshot(conn, handle)


@app.post("/api/ranked/queue")
def ranked_queue(handle: str):
    """Start a match: pick a problem near elo, 30-minute clock starts now.

    The problem statement is returned in the same response — the match is
    live the moment the player sees it, so there is no free re-rolling.
    """
    with db.connect() as conn:
        snap = _ranked_snapshot(conn, handle)
        if snap["active"] is not None:
            raise HTTPException(status_code=409, detail="A match is already in progress")

        exclude = {
            (r["contest_id"], r["problem_index"])
            for r in db.fetch_matches(conn, handle)
        }
        problem = ranked.pick_ranked_problem(handle, snap["elo"], exclude)
        if problem is None:
            raise HTTPException(
                status_code=404, detail="No eligible problem found near your elo"
            )

        # Fetch the statement before creating the match so a scrape failure
        # doesn't leave a running clock on a problem the player never saw.
        html = get_problem_html(problem["contestId"], problem["index"])
        now = int(time())
        row = db.insert_match(
            conn, handle, problem, now, now + ranked.MATCH_SECONDS, snap["elo"]
        )
        snap["active"] = _active_payload(row)
        snap["server_now"] = now
        return {**snap, "html": html}


@app.get("/api/ranked/problem")
def ranked_problem(handle: str):
    """Statement HTML for the live match (for clients that reopen mid-match)."""
    with db.connect() as conn:
        rows = db.fetch_matches(conn, handle)
    active = next((r for r in rows if r["result"] is None), None)
    if active is None:
        raise HTTPException(status_code=404, detail="No active match")
    return {
        "match_id": active["id"],
        "html": get_problem_html(active["contest_id"], active["problem_index"]),
    }


# A generation that has held the lock this long is presumed dead (crashed
# instance, dropped request) and the next poll takes it over.
SOLUTION_STALE_SECONDS = 180


def _solution_payload(row):
    if row is None:
        return None
    return {
        "status": row["status"],
        "content_md": row["content_md"],
        "model": row["model"],
    }


def _finished_match(conn, handle, match_id):
    """The handle's own resolved match row — the auth gate for review and
    solution generation, so strangers can't burn tokens on arbitrary problems."""
    row = db.fetch_match(conn, handle, match_id)
    if row is None or row["result"] is None:
        raise HTTPException(
            status_code=404, detail=f"No finished match {match_id} for {handle}"
        )
    return row


@app.get("/api/ranked/review")
def ranked_review(handle: str, match_id: int):
    """Statement + any cached editorial for a finished match."""
    with db.connect() as conn:
        row = _finished_match(conn, handle, match_id)
        sol = db.get_solution(conn, row["contest_id"], row["problem_index"])
    return {
        "match": _history_payload(row),
        "html": get_problem_html(row["contest_id"], row["problem_index"]),
        "solution": _solution_payload(sol),
    }


@app.post("/api/ranked/solution")
def ranked_solution(handle: str, match_id: int):
    """Return the editorial for a finished match, generating it on first ask.

    Editorials are cached per problem (not per user), so each problem costs
    one model call ever. While another request is generating, this returns
    the pending row — the client polls until it flips to done.
    """
    with db.connect() as conn:
        row = _finished_match(conn, handle, match_id)
        contest_id, index = row["contest_id"], row["problem_index"]
        now = int(time())
        claimed = db.claim_solution(
            conn, contest_id, index, now, now - SOLUTION_STALE_SECONDS
        )
        if claimed is None:
            return {"solution": _solution_payload(
                db.get_solution(conn, contest_id, index)
            )}

    # We hold the lock. Generate with no connection open — a model call can
    # take a minute, longer than a pooled connection should sit idle.
    try:
        content, source_url, model = solutions.generate(
            contest_id, index, row["problem_name"]
        )
    except Exception:
        with db.connect() as conn:
            db.release_solution(conn, contest_id, index)
        raise

    with db.connect() as conn:
        sol = db.finish_solution(
            conn, contest_id, index, content, model,
            source_url, int(time()),
        )
    return {"solution": _solution_payload(sol)}


@app.post("/api/ranked/surrender")
def ranked_surrender(handle: str):
    """Concede the live match. If it turns out already won/lost, that stands."""
    with db.connect() as conn:
        snap = _ranked_snapshot(conn, handle)
        if snap["active"] is None:
            # Nothing live — either no match or it just resolved on its own
            # (e.g. the player AC'd and then hit surrender). Return the state.
            return snap
        active = next(
            r for r in db.fetch_matches(conn, handle) if r["result"] is None
        )
        after = ranked.elo_after(
            active["elo_before"], active["problem_rating"], False
        )
        db.finalize_match(conn, active["id"], "surrender", after, None)
        return _ranked_snapshot(conn, handle)
