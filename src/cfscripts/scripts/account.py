from datetime import datetime

from cfscripts.lib.submissions import get_solved_problems_by_day


def run(handle):
    days = get_solved_problems_by_day(handle)
    comu = []
    daynames = []
    for day_ts in days:
        comu.append(len(days[day_ts]))
        daynames.append(datetime.fromtimestamp(day_ts))
    for i in range(len(comu) - 2, -1, -1):
        comu[i] += comu[i + 1]
    print("\nProblem solutions cumulative count\n")
    for i in range(len(comu)):
        print("Since", daynames[i].strftime('%b/%d/%Y'), comu[i], "problems were solved")
