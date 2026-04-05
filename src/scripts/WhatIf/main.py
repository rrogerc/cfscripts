from rich.table import Table
from rich.console import Console
from rich.live import Live
from rich.text import Text
from datetime import datetime
import sys
import os

sys.path.append(os.path.dirname(os.path.realpath(__file__)) + "/../..")

from lib.performance import UserPerformanceCalculator
from lib.colors import CFColors
from lib.contests import get_contest_map, get_participated_contest_ids
from lib import printer

# Suppress API status messages — progress is shown via Live display
printer.PRINT = lambda *args, **kwargs: None

def get_table(handle):
    table=Table(
        title="CodeForces Rating Simulation for {}".format(handle),
        title_style="on_default",
        show_lines=True,
        highlight=True,
    )
    table.add_column("handle")
    table.add_column("contest name")
    table.add_column("contest id")
    table.add_column("participation type")
    table.add_column("participation time")
    table.add_column("rank")
    table.add_column("points | penalty")
    table.add_column("old rating")
    table.add_column("new rating")
    table.add_column("delta")
    table.add_column("performance")
    return table

def add_row(table, data):
    performance_color = CFColors.get_rating_color(data["performance"])
    old_rating_color = CFColors.get_rating_color(data["old_rating"])
    new_rating_color = CFColors.get_rating_color(data["new_rating"])
    delta_color = CFColors.get_delta_color(data["delta"])
    participation_type_color = CFColors.get_participation_type_color(data["participation_type"])
    timestamp = datetime.utcfromtimestamp(data["time"]).strftime('%Y-%m-%d %H:%M:%S')
    table.add_row(
        data["handle"],
        data["contest"],
        str(data['contest_id']),
        Text(data["participation_type"], style=participation_type_color),
        timestamp,
        str(data["rank"]),
        "{} | {}".format(data["points"],data["penalty"]),
        Text(str(data["old_rating"]), style=old_rating_color),
        Text(str(data["new_rating"]), style=new_rating_color),
        Text(str(data["delta"]), style=delta_color),
        Text(str(data["performance"]), style=performance_color),
    )

def main():
    handle = "Exonerate"
    contest_map = get_contest_map()
    contest_ids = get_participated_contest_ids(handle, contest_map)
    only_positive = False
    calculator = UserPerformanceCalculator(handle)
    old_rating = calculator.rating_tracker.get_rating_at_time(contest_ids[0][1])

    n_total = len(contest_ids)
    progress = Text("Prefetching contest data...")

    with Live(progress, refresh_per_second=4, transient=True) as live:
        calculator.prefetch([cid for cid, _ in contest_ids])

        table = get_table(handle)

        for i, (contest_id, time) in enumerate(contest_ids):
            live.update(Text("Evaluating {}/{}: {} ...".format(i + 1, n_total, contest_map[contest_id]["name"])))
            data = calculator.get_performance(contest_id, old_rating)
            new_rating = old_rating
            if type(data["delta"]) != str:
                if (not only_positive) or data["delta"] > 0:
                    new_rating = old_rating + data["delta"]
            data["old_rating"] = old_rating
            data["new_rating"] = new_rating
            data["time"] = time
            data["contest"] = contest_map[contest_id]["name"]
            add_row(table, data)
            old_rating = new_rating

    Console().print(table)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print()
        sys.exit(1)
    sys.exit(0)
