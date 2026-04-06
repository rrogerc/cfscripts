import webbrowser

from cfscripts.lib.atcoder import (
    get_abc_contest_ids,
    get_problems,
    get_user_accepted_problems,
)


def _problem_index(problem_id):
    """Extract the task letter from an AtCoder problem ID (e.g., 'abc300_a' -> 'a')."""
    parts = problem_id.split("_")
    return parts[-1].lower() if parts else None


def _contest_number(contest_id):
    """Extract numeric suffix from contest ID (e.g., 'abc300' -> 300)."""
    digits = contest_id.lstrip("abcdefghijklmnopqrstuvwxyz")
    return int(digits) if digits.isdigit() else 0


def run(handle, index_letter, open_browser=True):
    """Pick the latest unsolved AtCoder ABC problem matching the index letter."""
    letter = index_letter.strip().lower()
    if len(letter) != 1 or not letter.isalpha():
        print("Error: Problem index must be a single letter (e.g., a, b, c).")
        return

    abc_contests = get_abc_contest_ids()
    problems = get_problems()
    solved = get_user_accepted_problems(handle)

    candidates = [
        p for p in problems
        if p["contest_id"] in abc_contests
        and _problem_index(p["id"]) == letter
    ]

    candidates.sort(key=lambda p: (-_contest_number(p["contest_id"]), p["id"]))

    for problem in candidates:
        if problem["id"] not in solved:
            url = "https://atcoder.jp/contests/{}/tasks/{}".format(
                problem["contest_id"], problem["id"]
            )
            print("Opening AtCoder ABC contest {} task {}".format(
                problem["contest_id"], problem["id"]
            ))
            if open_browser:
                webbrowser.open(url)
            return

    print("No unsolved AtCoder ABC '{}' problem found.".format(letter.upper()))
