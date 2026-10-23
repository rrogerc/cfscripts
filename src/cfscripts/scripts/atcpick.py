import webbrowser

from cfscripts.core.picker import get_abc_problem_by_index


def run(handle, index_letter, open_browser=True):
    """Pick the latest unsolved AtCoder ABC problem matching the index letter."""
    letter = index_letter.strip().lower()
    if len(letter) != 1 or not letter.isalpha():
        print("Error: Problem index must be a single letter (e.g., a, b, c).")
        return

    problem = get_abc_problem_by_index(handle, letter)
    if problem is not None:
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
