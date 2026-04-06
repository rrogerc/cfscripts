from datetime import datetime
from rich.table import Table
from rich.console import Group
from rich.live import Live
from rich.text import Text

from cfscripts.lib.performance import UserPerformanceCalculator
from cfscripts.lib.colors import get_rating_color, get_delta_color, get_participation_type_color
from cfscripts.lib.contests import get_contest_map, get_participated_contest_ids
from cfscripts.lib import printer


def run(handle, contest_id=None, count=5):
    contest_map = get_contest_map()
    contest_ids = get_participated_contest_ids(handle)

    if contest_id is not None:
        contestpair = None
        for cid, time in contest_ids:
            if cid == contest_id:
                contestpair = (cid, time)
                break
        if contestpair is None:
            print("Contest not found")
            return
        contest_ids = [contestpair]
    else:
        contest_ids = (contest_ids[-count::])[::-1]

    table = Table(
        title="CodeForces Participations of {}".format(handle),
        title_style="on_default",
        show_lines=True,
        highlight=True,
    )
    table.add_column("handle")
    table.add_column("contest name")
    table.add_column("contest id")
    table.add_column("participation type")
    table.add_column("participation time")
    table.add_column("points | penalty")
    table.add_column("old rating")
    table.add_column("rank")
    table.add_column("predicted delta")
    table.add_column("predicted performance")

    group = Group("loading...", table)

    def set_status(status):
        group._renderables = [status, table]
        group._render = None

    printer.set_printer(set_status)

    calculator = UserPerformanceCalculator(handle)

    with Live(group, refresh_per_second=10, screen=False, transient=False, vertical_overflow="visible"):
        for cid, time in contest_ids:
            set_status("Calculating performance for {} -- {} ...".format(contest_map[cid]["name"], cid))
            data = calculator.get_performance(cid)
            data["time"] = time
            performance_color = get_rating_color(data["performance"])
            rating_color = get_rating_color(data["rating"])
            delta_color = get_delta_color(data["delta"])
            participation_type_color = get_participation_type_color(data["participation_type"])
            timestamp = datetime.fromtimestamp(data["time"]).strftime('%Y-%m-%d %H:%M:%S')
            table.add_row(
                Text(data["handle"], style=rating_color),
                data["contest_name"],
                str(data['contest_id']),
                Text(data["participation_type"], style=participation_type_color),
                Text(timestamp),
                "{} | {}".format(data["points"], data["penalty"]),
                Text(str(data["rating"]), style=rating_color),
                str(data["rank"]),
                Text(str(data["delta"]), style=delta_color),
                Text(str(data["performance"]), style=performance_color),
            )
        set_status("finished")
