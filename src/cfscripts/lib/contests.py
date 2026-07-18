from urllib.parse import quote_plus
import re

from .api import get_results, CACHE_SHORT, CACHE_LONG
from .submissions import get_submissions

def get_contests():
    url="https://codeforces.com/api/contest.list?gym=false"
    return get_results(url, CACHE_SHORT)

def get_contest_map():
    contests = get_contests()
    mp = {}
    for contest in contests:
        mp[contest["id"]] = contest
    return mp

def get_contest_and_standings(contest_id, cache_type=CACHE_LONG):
    """Return (contest, problems, rows) for a contest.

    Codeforces restricted contest.standings in 2026: non-admin calls must be
    anonymous GETs with contestId only (no from/count/showUnofficial), so the
    rows contain official CONTESTANT results exclusively. Virtual and
    out-of-competition rows are no longer available from the API — see
    lib/virtual.py for how those results are reconstructed from submissions.
    """
    url = "https://codeforces.com/api/contest.standings?contestId={}".format(
        quote_plus(str(contest_id))
    )
    results = get_results(url, cache_type)
    return results["contest"], results["problems"], results["rows"]

def get_participated_contest_ids(handle, contest_map=None):
    if contest_map is None:
        contest_map = get_contest_map()
    submissions = get_submissions(handle)
    contest_ids = {}
    for submission in submissions:
        if "contestId" not in submission: continue;
        contest_id = submission["contestId"]
        part_type = submission["author"]["participantType"]
        if (part_type == "CONTESTANT" or part_type == "VIRTUAL" or part_type == "OUT_OF_COMPETITION") and contest_id in contest_map and len(submission["author"]["members"]) == 1:
            start_time = submission["author"]["startTimeSeconds"]# if "startTimeSeconds" in submission["author"] else 0
            contest_ids[contest_id] = start_time
    l = [(id, contest_ids[id]) for id in contest_ids]
    l.sort(key=lambda t: t[1])
    return l

_PARTICIPATION_PRIORITY = {"CONTESTANT": 2, "OUT_OF_COMPETITION": 1, "VIRTUAL": 0}

def get_participations(handle, contest_map=None):
    """Return participation entries with contest name and type, newest first.

    participation_type is lowercased ("contestant", "virtual",
    "out_of_competition"). If a contest has submissions under multiple
    participation types, the highest-priority one wins.
    """
    if contest_map is None:
        contest_map = get_contest_map()
    submissions = get_submissions(handle)
    entries = {}
    for submission in submissions:
        if "contestId" not in submission: continue
        contest_id = submission["contestId"]
        if contest_id not in contest_map: continue
        author = submission["author"]
        part_type = author["participantType"]
        if part_type not in _PARTICIPATION_PRIORITY: continue
        if len(author["members"]) != 1: continue
        prev = entries.get(contest_id)
        if prev is None or _PARTICIPATION_PRIORITY[part_type] > _PARTICIPATION_PRIORITY[prev["_priority_type"]]:
            entries[contest_id] = {
                "contest_id": contest_id,
                "contest_name": contest_map[contest_id]["name"],
                "participation_type": part_type.lower(),
                "start_time": author["startTimeSeconds"],
                "_priority_type": part_type,
            }
    result = sorted(entries.values(), key=lambda e: e["start_time"], reverse=True)
    for entry in result:
        del entry["_priority_type"]
    return result

def get_div2_contest_ids():
    """Return set of contest IDs for Div. 2 only contests (not Div. 1 + Div. 2)."""
    contests = get_contests()
    return {
        c["id"] for c in contests
        if "Div. 2" in c["name"] and "Div. 1" not in c["name"]
    }

def get_contest_number(contest_name):
    res = re.findall(r'#(\d+)', contest_name)
    if len(res) != 1: return None
    return int(res[0])

def get_problems():
    url="https://codeforces.com/api/problemset.problems"
    result = get_results(url, CACHE_LONG)
    return result["problems"]
