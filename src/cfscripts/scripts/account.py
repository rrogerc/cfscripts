from datetime import datetime

from cfscripts.lib.submissions import get_submissions


def run(handle):
    subs = get_submissions(handle)[::-1]
    problems = {}
    for sub in subs:
        problem = ""
        if "contestId" not in sub["problem"]: problem = sub["problem"]["name"]
        else: problem = sub["problem"]["name"] + "(" + str(sub["problem"]["contestId"]) + sub["problem"]["index"] + ")"
        if "verdict" in sub and sub["verdict"] == "OK" and problem not in problems:
            problems[problem] = sub["problem"]
            problems[problem]["time"] = int(sub["creationTimeSeconds"])
    days = {}
    for problemID in problems:
        problem = problems[problemID]
        date = datetime.fromtimestamp(problem["time"])
        newtime = problem["time"] - date.hour * 60 * 60 - date.minute * 60 - date.second
        if newtime not in days: days[newtime] = []
        days[newtime].append(problem)
    comu = []
    daynames = []
    for day in days:
        probs = days[day]
        date = datetime.fromtimestamp(day)
        comu.append(len(probs))
        daynames.append(date)
    for i in range(len(comu)-2,-1,-1):
        comu[i] += comu[i+1]
    print("\nProblem solutions cumulative count\n")
    for i in range(len(comu)):
        print("Since", daynames[i].strftime('%b/%d/%Y'), comu[i], "problems were solved")
