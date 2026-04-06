from datetime import datetime

from cfscripts.lib.submissions import get_solved_problems_by_day


def run(handle):
    days = get_solved_problems_by_day(handle)
    for day_ts in days:
        probs = days[day_ts]
        date = datetime.fromtimestamp(day_ts)
        print(date.strftime('%b/%d/%Y') + ":", len(probs))
        for problem in probs:
            print("    -", str(problem.get("rating", "unrated")) + ":", problem["key"])
