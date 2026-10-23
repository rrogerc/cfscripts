from concurrent.futures import ThreadPoolExecutor

from cfscripts.lib.api import CACHE_SHORT
from cfscripts.lib.atcoder import (
    get_abc_contest_ids,
    get_problems as get_atcoder_problems,
    get_user_accepted_problems,
)
from cfscripts.lib.contests import get_div2_contest_ids, get_problems
from cfscripts.lib.submissions import get_solved_set

def get_rated_problems():
    """Return list of problems that have a rating."""
    return [p for p in get_problems() if "rating" in p and p["rating"] is not None]

def _fetch_inputs(handle, use_solved=True, solved_cache=CACHE_SHORT):
    """Fetch the independent picker inputs concurrently.

    Returns (rated_problems, div2_contests, solved). These hit three distinct
    Codeforces endpoints, so running them in parallel turns the latency from
    their sum into their max. When use_solved is False the expensive
    user.status fetch is skipped and solved is an empty set. solved_cache
    controls the freshness of the user.status fetch (e.g. CACHE_NONE so a
    problem you just solved is excluded on the next pick).
    """
    with ThreadPoolExecutor(max_workers=3) as executor:
        problems_future = executor.submit(get_rated_problems)
        div2_future = executor.submit(get_div2_contest_ids)
        solved_future = executor.submit(get_solved_set, handle, solved_cache) if use_solved else None
        rated_problems = problems_future.result()
        div2_contests = div2_future.result()
        solved = solved_future.result() if solved_future is not None else set()
    return rated_problems, div2_contests, solved

def get_problem_by_level(handle, level, use_solved=True, solved_cache=CACHE_SHORT):
    """Return the latest unsolved Div. 2 problem at the given rating level, or None."""
    if level < 8 or level > 32:
        raise ValueError("Level must be an integer between 8 and 32 inclusive.")

    target_rating = level * 100
    rated_problems, div2_contests, solved = _fetch_inputs(handle, use_solved, solved_cache)

    best = None
    for p in rated_problems:
        if p.get("rating") != target_rating:
            continue
        cid = p.get("contestId")
        if cid not in div2_contests:
            continue
        if (cid, p["index"]) in solved:
            continue
        if best is None or cid > best.get("contestId", 0):
            best = p

    return best

def get_problem_by_index(handle, index_letter, use_solved=True, solved_cache=CACHE_SHORT):
    """Return the latest unsolved Div. 2 problem matching the index letter, or None."""
    letter = index_letter.strip().upper()
    if len(letter) != 1 or not letter.isalpha():
        raise ValueError("Problem index must be a single letter (e.g., A, B, C).")

    rated_problems, div2_contests, solved = _fetch_inputs(handle, use_solved, solved_cache)

    best = None
    for p in rated_problems:
        cid = p.get("contestId")
        if cid not in div2_contests:
            continue
        idx = p.get("index", "")
        if not idx or idx[0].upper() != letter:
            continue
        if (cid, p["index"]) in solved:
            continue
        if best is None or cid > best.get("contestId", 0):
            best = p

    return best


def _abc_problem_index(problem):
    """Extract the lowercase task letter from an AtCoder problem entry."""
    idx = problem.get("problem_index")
    if isinstance(idx, str) and idx.strip():
        return idx.strip().lower()
    parts = str(problem.get("id", "")).split("_")
    return parts[-1].lower() if parts else ""


def _abc_contest_number(contest_id):
    """Extract numeric suffix from contest ID (e.g., 'abc300' -> 300)."""
    digits = str(contest_id).lstrip("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ")
    return int(digits) if digits.isdigit() else 0


def _fetch_abc_inputs(handle, use_solved=True, solved_cache=CACHE_SHORT):
    """Fetch the AtCoder ABC picker inputs concurrently."""
    with ThreadPoolExecutor(max_workers=3) as executor:
        problems_future = executor.submit(get_atcoder_problems)
        abc_future = executor.submit(get_abc_contest_ids)
        solved_future = (
            executor.submit(get_user_accepted_problems, handle, solved_cache)
            if use_solved else None
        )
        problems = problems_future.result()
        abc_contests = abc_future.result()
        solved = solved_future.result() if solved_future is not None else set()
    return problems, abc_contests, solved


def get_abc_problem_by_index(handle, index_letter, use_solved=True, solved_cache=CACHE_SHORT):
    """Return the latest unsolved AtCoder ABC problem matching the task letter, or None."""
    letter = index_letter.strip().lower()
    if len(letter) != 1 or not letter.isalpha():
        raise ValueError("Problem index must be a single letter (e.g., A, B, C).")

    problems, abc_contests, solved = _fetch_abc_inputs(handle, use_solved, solved_cache)

    candidates = [
        p for p in problems
        if p.get("contest_id") in abc_contests
        and _abc_problem_index(p) == letter
        and p.get("id") not in solved
    ]
    if not candidates:
        return None

    candidates.sort(key=lambda p: (-_abc_contest_number(p["contest_id"]), p["id"]))
    best = candidates[0]
    upper = letter.upper()
    return {
        "id": best["id"],
        "contest_id": best["contest_id"],
        "contestId": best["contest_id"],
        "index": upper,
        "problem_index": best.get("problem_index", upper),
        "name": best.get("name") or best.get("title") or best["id"],
        "title": best.get("title", ""),
    }
