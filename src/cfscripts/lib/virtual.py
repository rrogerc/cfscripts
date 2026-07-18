"""Reconstruct a user's contest result from their own submissions.

Codeforces removed API access to unofficial standings rows (contest.standings
now only returns official CONTESTANT rows), so virtual and out-of-competition
results must be rebuilt from user.status data: per-problem solve time and
wrong-attempt counts, scored with the contest's own rules.

Scoring rules (https://codeforces.com/blog/entry/133094):
- Standard ("CF" type): score per solved problem =
      max(0.3*x, x - floor(120*x*t / (250*d)) - 50*w)
  where x = initial problem score, t = solve minute, d = contest duration in
  minutes, w = wrong attempts before the first OK. Compilation errors and
  submissions failing on the first test do not count toward w.
- Extended ICPC ("ICPC" type: educational, Div. 3/4): points = solved count,
  penalty = sum over solved problems of (t + 10*w).
"""

from .submissions import get_submissions

_TRACKED_TYPES = ("CONTESTANT", "VIRTUAL", "OUT_OF_COMPETITION")

# Verdicts that never count as wrong attempts regardless of tests passed.
_NON_ATTEMPT_VERDICTS = ("COMPILATION_ERROR", "TESTING", "SUBMITTED")


def get_contest_runs(handle, contest_id, submissions=None):
    """Group the user's submissions for a contest into runs.

    Returns dict mapping (participant_type, start_time) -> [submissions],
    one entry per distinct participation (a contest can have an official run
    and later virtual runs).
    """
    if submissions is None:
        submissions = get_submissions(handle)
    runs = {}
    for sub in submissions:
        if sub.get("contestId") != contest_id:
            continue
        author = sub["author"]
        part_type = author["participantType"]
        if part_type not in _TRACKED_TYPES:
            continue
        if len(author["members"]) != 1:
            continue
        key = (part_type, author["startTimeSeconds"])
        runs.setdefault(key, []).append(sub)
    return runs


def pick_run(runs, start_time=None):
    """Pick one run: exact start_time match if given, otherwise the latest."""
    if not runs:
        return None
    if start_time is not None:
        for key in runs:
            if key[1] == start_time:
                return key
        return None
    return max(runs, key=lambda k: k[1])


def _problem_outcomes(run_submissions):
    """Per problem index: (solve_minute or None, wrong_attempts_before_ok)."""
    by_problem = {}
    for sub in run_submissions:
        idx = sub["problem"]["index"]
        by_problem.setdefault(idx, []).append(sub)

    outcomes = {}
    for idx, subs in by_problem.items():
        subs.sort(key=lambda s: s["relativeTimeSeconds"])
        wrongs = 0
        solve_minute = None
        for sub in subs:
            verdict = sub.get("verdict")
            if verdict == "OK":
                solve_minute = sub["relativeTimeSeconds"] // 60
                break
            if verdict in _NON_ATTEMPT_VERDICTS:
                continue
            if sub.get("passedTestCount", 0) == 0:
                continue  # failed on the first test — not counted
            wrongs += 1
        outcomes[idx] = (solve_minute, wrongs)
    return outcomes


def score_run(contest, problems, run_submissions):
    """Return (points, penalty) for a run under the contest's scoring rules."""
    contest_type = contest.get("type")
    outcomes = _problem_outcomes(run_submissions)
    duration_minutes = contest["durationSeconds"] // 60

    if contest_type == "CF":
        initial_scores = {p["index"]: p.get("points") for p in problems}
        total = 0.0
        for idx, (solve_minute, wrongs) in outcomes.items():
            if solve_minute is None:
                continue
            x = initial_scores.get(idx)
            if x is None:
                continue
            decay = (120 * x * solve_minute) // (250 * duration_minutes)
            total += max(0.3 * x, x - decay - 50 * wrongs)
        return total, 0

    if contest_type == "ICPC":
        solved = 0
        penalty = 0
        for solve_minute, wrongs in outcomes.values():
            if solve_minute is None:
                continue
            solved += 1
            penalty += solve_minute + 10 * wrongs
        return float(solved), penalty

    raise ValueError(
        "Unsupported contest type {!r} for result reconstruction".format(contest_type)
    )


def insertion_rank(points, penalty, results):
    """Rank the reconstructed result would take among official results.

    results: iterable of (points, penalty) pairs for official contestants.
    """
    better = 0
    for other_points, other_penalty in results:
        if (-other_points, other_penalty) < (-points, penalty):
            better += 1
    return better + 1
