"""Ranked queue game logic: elo math, problem selection, match resolution.

A "match" is 30 minutes against one unsolved problem picked near the player's
queue elo. The problem is treated as an opponent whose rating is its CF
problem rating; standard elo updates give the asymmetric win/loss deltas.

Everything here is a pure function over plain dicts — no database access —
so the whole game can be tested without provisioning anything. Win detection
uses wall-clock creationTimeSeconds from the player's own submissions, which
means matches resolve correctly even if the app was closed the entire time,
and the clock can't be cheated by not opening the app.
"""

import random

from cfscripts.core.picker import _fetch_inputs
from cfscripts.lib.api import CACHE_NONE

K_FACTOR = 32
MATCH_SECONDS = 30 * 60
DEFAULT_SEED_ELO = 1500

# Target rating is sampled from elo + one of these offsets (CF ratings come in
# 100-point steps), then the problem is chosen randomly among the newest
# unsolved Div. 2 problems at that rating so picks stay fresh but unpredictable.
RATING_OFFSETS = (-200, -100, 0, 100, 200)
CANDIDATE_POOL = 30
MIN_RATING = 800
MAX_RATING = 3500


def expected_score(elo, problem_rating):
    """Probability of beating the problem under the elo model."""
    return 1.0 / (1.0 + 10.0 ** ((problem_rating - elo) / 400.0))


def elo_after(elo, problem_rating, won):
    score = 1.0 if won else 0.0
    return elo + K_FACTOR * (score - expected_score(elo, problem_rating))


def pick_ranked_problem(handle, elo, exclude):
    """Pick an unsolved Div. 2 problem near elo, or None if none qualify.

    exclude is a set of (contestId, index) that already appeared in past
    matches — a surrendered problem must never be re-served, or surrendering
    would be a free re-roll.
    """
    rated_problems, div2_contests, solved = _fetch_inputs(
        handle, use_solved=True, solved_cache=CACHE_NONE
    )

    buckets = {}
    for p in rated_problems:
        cid = p.get("contestId")
        if cid not in div2_contests:
            continue
        key = (cid, p["index"])
        if key in solved or key in exclude:
            continue
        buckets.setdefault(p["rating"], []).append(p)
    if not buckets:
        return None

    base = round(elo / 100) * 100
    target = min(MAX_RATING, max(MIN_RATING, base + random.choice(RATING_OFFSETS)))
    rating = min(buckets, key=lambda r: (abs(r - target), r))
    pool = sorted(buckets[rating], key=lambda p: p["contestId"], reverse=True)
    return random.choice(pool[:CANDIDATE_POOL])


def resolve_match(match, submissions, now):
    """Return (result, solved_ts): ("win", ts), ("loss", None), or (None, None).

    match needs contest_id, problem_index, start_ts, deadline_ts. A win is an
    OK submission on the match problem whose creationTimeSeconds falls inside
    the window; being past the deadline without one is a loss; otherwise the
    match is still live.
    """
    best = None
    for s in submissions:
        p = s.get("problem", {})
        if p.get("contestId") != match["contest_id"]:
            continue
        if p.get("index") != match["problem_index"]:
            continue
        if s.get("verdict") != "OK":
            continue
        ts = s.get("creationTimeSeconds")
        if ts is None or not (match["start_ts"] <= ts <= match["deadline_ts"]):
            continue
        if best is None or ts < best:
            best = ts
    if best is not None:
        return "win", best
    if now > match["deadline_ts"]:
        return "loss", None
    return None, None
