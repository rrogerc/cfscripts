from datetime import datetime
from urllib.parse import quote_plus

from .api import get_results, CACHE_SHORT

def get_submissions(handle):
    url = "https://codeforces.com/api/user.status?handle={}&from=1&count=1000000".format(
        quote_plus(str(handle))
    )
    return get_results(url, CACHE_SHORT)

def get_solved_set(handle):
    """Return set of (contestId, index) tuples for all AC'd problems."""
    subs = get_submissions(handle)
    solved = set()
    for s in subs:
        if s.get("verdict") == "OK" and "contestId" in s.get("problem", {}):
            solved.add((s["problem"]["contestId"], s["problem"]["index"]))
    return solved

def get_solved_problems_by_day(handle):
    """Fetch submissions, deduplicate by problem, and group by calendar day.

    Returns a dict mapping day_timestamp -> list of problem dicts (each with a "key" and "time" field).
    """
    subs = get_submissions(handle)[::-1]
    problems = {}
    for sub in subs:
        if "contestId" not in sub["problem"]:
            key = sub["problem"]["name"]
        else:
            key = sub["problem"]["name"] + " (" + str(sub["problem"]["contestId"]) + sub["problem"]["index"] + ")"
        if "verdict" in sub and sub["verdict"] == "OK" and key not in problems:
            problems[key] = dict(sub["problem"])
            problems[key]["time"] = int(sub["creationTimeSeconds"])
            problems[key]["key"] = key
    days = {}
    for problem in problems.values():
        date = datetime.fromtimestamp(problem["time"])
        day_ts = problem["time"] - date.hour * 3600 - date.minute * 60 - date.second
        if day_ts not in days:
            days[day_ts] = []
        days[day_ts].append(problem)
    return days

def get_submissions_for_contest(contest_id, handle=None):
    if handle is None:
        url = "https://codeforces.com/api/contest.status?contestId={}".format(
            quote_plus(str(contest_id)),
        )
    else:
        url = "https://codeforces.com/api/contest.status?contestId={}&handle={}".format(
            quote_plus(str(contest_id)),
            quote_plus(str(handle))
        )
    return get_results(url, CACHE_SHORT)
