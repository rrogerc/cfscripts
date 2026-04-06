from urllib.parse import quote_plus
from rich.table import Table
from rich.console import Console

from cfscripts.lib.submissions import get_submissions, get_solved_set
from cfscripts.lib.contests import get_contest_map, get_contest_number, get_problems


def run(handle, min_rating=None, max_rating=None):
    problems = get_unsolved_problems_from_participated_contests(handle)
    if min_rating is not None and max_rating is not None:
        problems = filter_by_rating(problems, min_rating, max_rating)

    contest_mp = get_contest_map()
    table = get_table()
    for problem in problems:
        add_row(table, problem, contest_mp)

    Console().print(table)


def get_table():
    table=Table(
        title="List of codeforces problems",
        title_style="on_default",
        show_lines=True,
        highlight=True,
        expand=True,
    )
    table.add_column("contest name", ratio=4)
    table.add_column("contest id", ratio=1)
    table.add_column("problem name", ratio=3)
    table.add_column("problem id", ratio=1)
    table.add_column("problem rating", ratio=1)
    table.add_column("url", ratio=7)
    return table

def add_row(table, data, contest_mp):
    cid = None
    if "contestId" in data: cid = data["contestId"]
    cname = None
    if cid is not None: cname = contest_mp[cid]["name"]
    pname = data["name"]
    pid = data["index"]
    rating = None
    if "rating" in data: rating = data["rating"]
    url = None
    if cid is not None:
        url = "https://codeforces.com/contest/{}/problem/{}".format(
            quote_plus(str(cid)),
            quote_plus(pid),
        )
    if cname is None: cname = ""
    if cid is None: cid = ""
    if pname is None: pname = ""
    if pid is None: pid = ""
    if rating is None: rating = ""
    if url is None: url = ""
    table.add_row(cname, str(cid), pname, pid, str(rating), url)

def get_unsolved_problems_from_participated_contests(handle):
    submissions = get_submissions(handle)
    contest_mp = get_contest_map()
    solved = get_solved_set(handle)

    # Collect contest IDs the user participated in, plus sibling Div1/Div2 contests
    used_contest_ids = set()
    for submission in submissions:
        if "contestId" not in submission: continue
        cid = submission["contestId"]
        used_contest_ids.add(cid)
        if cid not in contest_mp: continue
        cnum = get_contest_number(contest_mp[cid]["name"])
        for sibling in (cid - 1, cid + 1):
            if sibling in contest_mp:
                num = get_contest_number(contest_mp[sibling]["name"])
                if num is not None and cnum == num:
                    used_contest_ids.add(sibling)

    all_problems = get_problems()
    problems = []
    for problem in all_problems:
        if "contestId" not in problem:
            problems.append(problem)
        elif problem["contestId"] in used_contest_ids:
            if (problem["contestId"], problem["index"]) not in solved:
                problems.append(problem)
    problems = problems[::-1]
    return problems

def filter_by_rating(problems, rmin, rmax):
    def filter_problem(problem):
        rating = None
        if "rating" in problem: rating = problem["rating"]
        return rating is not None and rmin <= rating <= rmax
    return list(filter(filter_problem, problems))
