from cfscripts.lib.contests import get_div2_contest_ids, get_problems
from cfscripts.lib.submissions import get_solved_set

def get_rated_problems():
    """Return list of problems that have a rating."""
    return [p for p in get_problems() if "rating" in p and p["rating"] is not None]

def get_problem_by_level(handle, level):
    """Return the latest unsolved Div. 2 problem at the given rating level, or None."""
    if level < 8 or level > 32:
        raise ValueError("Level must be an integer between 8 and 32 inclusive.")

    target_rating = level * 100
    rated_problems = get_rated_problems()
    div2_contests = get_div2_contest_ids()
    solved = get_solved_set(handle)

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

def get_problem_by_index(handle, index_letter):
    """Return the latest unsolved Div. 2 problem matching the index letter, or None."""
    letter = index_letter.strip().upper()
    if len(letter) != 1 or not letter.isalpha():
        raise ValueError("Problem index must be a single letter (e.g., A, B, C).")

    rated_problems = get_rated_problems()
    div2_contests = get_div2_contest_ids()
    solved = get_solved_set(handle)

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
