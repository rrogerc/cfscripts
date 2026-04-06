from urllib.parse import quote_plus
from rich.table import Table
from rich.console import Console

from cfscripts.lib.submissions import get_submissions
from cfscripts.lib.contests import get_contest_map, get_contest_number
from cfscripts.lib.problems import get_problems


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
    used_contest_ids = set()
    contest_mp = get_contest_map()
    solved_problems = set()
    for submission in submissions:
        is_ac = submission["verdict"] == "OK"
        if "contestId" not in submission: continue
        cid = submission["contestId"]
        if is_ac:
            full_problem_name = str(cid) + submission["problem"]["name"]
            solved_problems.add(full_problem_name)
        used_contest_ids.add(cid)
        if cid not in contest_mp: continue
        cnum = get_contest_number(contest_mp[cid]["name"])
        if cid - 1 in contest_mp:
            num = get_contest_number(contest_mp[cid - 1]["name"])
            if num is not None and cnum == num:
                used_contest_ids.add(cid - 1)
                if is_ac:
                    full_problem_name = str(cid - 1) + submission["problem"]["name"]
                    solved_problems.add(full_problem_name)
        if cid + 1 in contest_mp:
            num = get_contest_number(contest_mp[cid + 1]["name"])
            if num is not None and cnum == num:
                used_contest_ids.add(cid + 1)
                if is_ac:
                    full_problem_name = str(cid + 1) + submission["problem"]["name"]
                    solved_problems.add(full_problem_name)
    all_problems = get_problems()
    problems = []
    for problem in all_problems:
        is_problem_ok = False
        if "contestId" not in problem:
            is_problem_ok = True
        else:
            cid = problem["contestId"]
            full_problem_name = str(cid) + problem["name"]
            if cid in used_contest_ids and full_problem_name not in solved_problems:
                is_problem_ok = True
        if is_problem_ok:
            problems.append(problem)
    problems = problems[::-1]
    return problems

def filter_by_rating(problems, rmin, rmax):
    def filter_problem(problem):
        rating = None
        if "rating" in problem: rating = problem["rating"]
        return rating is not None and rmin <= rating <= rmax
    return list(filter(filter_problem, problems))
