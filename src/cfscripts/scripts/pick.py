import os
import webbrowser
from collections import OrderedDict
from pathlib import Path

from cfscripts.lib.contests import get_div2_contest_ids, get_problems
from cfscripts.lib.submissions import get_solved_set


CPP_STARTER = r"""#include <iostream>

void solve();

int main() {
    int count_test_cases;

    std::cin >> count_test_cases;

    while (count_test_cases--) {
        solve();
    }
}

void solve() {
}
""".lstrip()


def _get_rated_problems():
    """Return list of problems that have a rating."""
    return [p for p in get_problems() if "rating" in p and p["rating"] is not None]


def _sanitize_filename(name):
    cleaned = ""
    for c in name:
        if c in ("/", "\\"):
            cleaned += "-"
        elif ord(c) < 32:
            cleaned += " "
        else:
            cleaned += c
    cleaned = cleaned.strip()
    return cleaned if cleaned else "problem"


def _create_cpp_stub(problem, cpp_dir):
    """Create C++ starter file. Returns (path, was_created)."""
    os.makedirs(cpp_dir, exist_ok=True)
    filename = _sanitize_filename(problem["name"]) + ".cpp"
    path = Path(cpp_dir) / filename
    if path.exists():
        return path, False
    path.write_text(CPP_STARTER)
    return path, True


def _display_path(p):
    """Return a user-friendly display path (relative or ~/...)."""
    p = Path(p)
    try:
        return str(p.relative_to(Path.cwd()))
    except ValueError:
        pass
    home = Path.home()
    try:
        return "~/" + str(p.relative_to(home))
    except ValueError:
        pass
    return str(p)


def _present_problem(best, cpp_dir=None, open_editor=True, open_browser=True):
    """Display the chosen problem, optionally create a C++ stub and open tools."""
    url = "https://codeforces.com/problemset/problem/{}/{}".format(
        best["contestId"], best["index"]
    )

    print("Problem:   {} ({} {})".format(best["name"], best["contestId"], best["index"]))
    print("Rating:    {}".format(best["rating"]))

    if cpp_dir:
        path, created = _create_cpp_stub(best, cpp_dir)
        status = "Created" if created else "Exists"
        print("File:      {} ({})".format(_display_path(path), status))

        if open_browser:
            webbrowser.open(url)

        if open_editor:
            os.execvp("nvim", ["nvim", str(path)])
    else:
        if open_browser:
            webbrowser.open(url)


def run_level(handle, level, cpp_dir=None, open_editor=True, open_browser=True):
    """Pick the latest unsolved Div. 2 problem at the given rating level."""
    if level < 8 or level > 32:
        print("Error: Level must be an integer between 8 and 32 inclusive.")
        return

    target_rating = level * 100
    rated_problems = _get_rated_problems()
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

    if best is None:
        print("No problem with rating {} found (Level {}).".format(target_rating, level))
        return

    _present_problem(best, cpp_dir, open_editor, open_browser)


def run_index(handle, index_letter, cpp_dir=None, open_editor=True, open_browser=True):
    """Pick the latest unsolved Div. 2 problem matching the index letter."""
    letter = index_letter.strip().upper()
    if len(letter) != 1 or not letter.isalpha():
        print("Error: Problem index must be a single letter (e.g., A, B, C).")
        return

    rated_problems = _get_rated_problems()
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

    if best is None:
        print("No unsolved Codeforces Div. 2 '{}' problem found.".format(letter))
        return

    _present_problem(best, cpp_dir, open_editor, open_browser)


def run_distribution():
    """Print rating distribution of all Div. 2 problems."""
    rated_problems = _get_rated_problems()
    div2_contests = get_div2_contest_ids()

    distribution = OrderedDict()
    for p in rated_problems:
        if p.get("contestId") in div2_contests:
            rating = p["rating"]
            distribution[rating] = distribution.get(rating, 0) + 1

    if not distribution:
        print("No rated Codeforces Div. 2 problems found.")
        return

    print("Rating distribution for Codeforces Div. 2 problems:")
    total = 0
    for rating in sorted(distribution):
        count = distribution[rating]
        print("  {}: {}".format(rating, count))
        total += count
    print("Total problems: {}".format(total))


def run_stats(handle):
    """Print bar chart of solved Div. 2 problems by rating."""
    div2_contests = get_div2_contest_ids()
    solved = get_solved_set(handle)
    rated_problems = _get_rated_problems()

    stats = {}
    for p in rated_problems:
        cid = p.get("contestId")
        if cid not in div2_contests:
            continue
        if (cid, p["index"]) not in solved:
            continue
        rating = p["rating"]
        stats[rating] = stats.get(rating, 0) + 1

    if not stats:
        print("No solved Codeforces Div. 2 problems found.")
        return

    print("Solved problems stats for Codeforces Div. 2:")
    total = 0
    max_count = max(stats.values())
    scale = 50.0 / max_count if max_count > 50 else 1.0

    for rating in sorted(stats):
        count = stats[rating]
        bar_len = round(count * scale)
        bar = "#" * bar_len
        print("{:4}: {:3} | {}".format(rating, count, bar))
        total += count
    print("Total solved: {}".format(total))
