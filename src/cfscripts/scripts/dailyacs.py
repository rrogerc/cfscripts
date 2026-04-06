from datetime import datetime

from cfscripts.lib.submissions import get_submissions


def run(handle):
    subs = get_submissions(handle)[::-1]
    problems = {}
    for sub in subs:
        problem = ""
        if "contestId" not in sub["problem"]: problem = sub["problem"]["name"]
        else: problem = sub["problem"]["name"] + " (" + str(sub["problem"]["contestId"]) + sub["problem"]["index"] + ")"
        if "verdict" in sub and sub["verdict"] == "OK" and problem not in problems:
            problems[problem] = sub["problem"]
            problems[problem]["time"] = int(sub["creationTimeSeconds"])
    days = {}
    for problemID in problems:
        problem = problems[problemID]
        date = datetime.fromtimestamp(problem["time"])
        newtime = problem["time"] - date.hour * 60 * 60 - date.minute * 60 - date.second
        if newtime not in days: days[newtime] = []
        problem["name"] = problemID
        days[newtime].append(problem)
    for day in days:
        probs = days[day]
        date = datetime.fromtimestamp(day)
        print(date.strftime('%b/%d/%Y')+":", len(probs))
        for problem in probs:
            print("    -", str(problem["rating"]if "rating" in problem else "unrated")+":", problem["name"])
