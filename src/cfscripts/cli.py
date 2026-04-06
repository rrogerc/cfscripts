import argparse
import sys


def main():
    parser = argparse.ArgumentParser(
        prog="cfscripts",
        description="Codeforces & AtCoder competitive programming tools",
    )
    parser.add_argument("--handle", help="Override handle from config")

    subparsers = parser.add_subparsers(dest="command")

    # --- Existing scripts ---

    p_whatif = subparsers.add_parser("whatif",
        help="What if virtuals/unofficials were official?")
    p_whatif.add_argument("--no-virtual", action="store_true",
        help="Skip virtual participations")

    p_vperf = subparsers.add_parser("vperf",
        help="Calculate rank/delta/performance of contest participations")
    p_vperf.add_argument("--contest", type=int,
        help="Specific contest ID")
    p_vperf.add_argument("--count", type=int, default=5,
        help="Number of recent contests to query (default: 5)")

    p_unsolved = subparsers.add_parser("unsolved",
        help="Find unsolved problems from participated contests")
    p_unsolved.add_argument("--min-rating", type=int,
        help="Minimum problem rating filter")
    p_unsolved.add_argument("--max-rating", type=int,
        help="Maximum problem rating filter")

    p_account = subparsers.add_parser("account",
        help="Cumulative AC count since each date")

    p_dailyacs = subparsers.add_parser("dailyacs",
        help="Problems solved per day with ratings")

    p_rangerank = subparsers.add_parser("rangerank",
        help="Your rank among nearby-rated contestants")
    p_rangerank.add_argument("--contest", type=int, required=True,
        help="Contest ID")
    p_rangerank.add_argument("--range", type=int, default=200,
        help="Rating range around your rating (default: 200)")

    # --- cf-lvl features ---

    p_pick = subparsers.add_parser("pick",
        help="Pick an unsolved Codeforces Div. 2 problem")
    p_pick.add_argument("level", nargs="?", type=int,
        help="Rating level (8-32, rating = level*100)")
    p_pick.add_argument("--index", "-i",
        help="Problem index letter (A, B, C, ...)")
    p_pick.add_argument("--no-editor", action="store_true",
        help="Don't launch nvim")
    p_pick.add_argument("--no-browser", action="store_true",
        help="Don't open browser")

    p_dist = subparsers.add_parser("dist",
        help="Rating distribution of Div. 2 problems")

    p_stats = subparsers.add_parser("stats",
        help="Solved problem stats by rating (bar chart)")

    p_config = subparsers.add_parser("config",
        help="Get or set config values (stored in ~/.config/cfscripts/)")
    p_config.add_argument("key", help="Config key (handle, cpp_dir)")
    p_config.add_argument("value", nargs="?", help="Value to set (omit to read)")

    p_atcpick = subparsers.add_parser("atcpick",
        help="Pick an unsolved AtCoder ABC problem")
    p_atcpick.add_argument("index",
        help="Task letter (a, b, c, ...)")
    p_atcpick.add_argument("--no-browser", action="store_true",
        help="Don't open browser")

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        sys.exit(1)

    if args.command == "config":
        _run_config(args)
        return

    from cfscripts.config import load_config
    config = load_config(cli_handle=args.handle)

    dispatch = {
        "whatif": _run_whatif,
        "vperf": _run_vperf,
        "unsolved": _run_unsolved,
        "account": _run_account,
        "dailyacs": _run_dailyacs,
        "rangerank": _run_rangerank,
        "pick": _run_pick,
        "dist": _run_dist,
        "stats": _run_stats,
        "atcpick": _run_atcpick,
    }

    try:
        dispatch[args.command](args, config)
    except KeyboardInterrupt:
        print()
        sys.exit(1)
    except Exception as e:
        from cfscripts.lib.api import ApiError
        if isinstance(e, ApiError):
            print("Error: {}".format(e), file=sys.stderr)
            sys.exit(1)
        raise


def _run_config(args):
    from cfscripts.config import set_config, get_config_value
    if args.value is not None:
        set_config(args.key, args.value)
        print(f"{args.key} = {args.value}")
    else:
        value = get_config_value(args.key)
        if value is not None:
            print(value)
        else:
            print(f"{args.key} is not set")


def _run_whatif(args, config):
    from cfscripts.scripts.whatif import run
    run(handle=config["handle"], skip_virtual=args.no_virtual)


def _run_vperf(args, config):
    from cfscripts.scripts.vperf import run
    run(handle=config["handle"], contest_id=args.contest, count=args.count)


def _run_unsolved(args, config):
    from cfscripts.scripts.unsolved import run
    run(handle=config["handle"], min_rating=args.min_rating, max_rating=args.max_rating)


def _run_account(args, config):
    from cfscripts.scripts.account import run
    run(handle=config["handle"])


def _run_dailyacs(args, config):
    from cfscripts.scripts.dailyacs import run
    run(handle=config["handle"])


def _run_rangerank(args, config):
    from cfscripts.scripts.rangerank import run
    run(handle=config["handle"], contest_id=args.contest, rank_range=args.range)


def _run_pick(args, config):
    from cfscripts.scripts.pick import run_level, run_index
    if args.index is not None:
        run_index(
            handle=config["handle"],
            index_letter=args.index,
            cpp_dir=config.get("cpp_dir"),
            open_editor=not args.no_editor,
            open_browser=not args.no_browser,
        )
    elif args.level is not None:
        run_level(
            handle=config["handle"],
            level=args.level,
            cpp_dir=config.get("cpp_dir"),
            open_editor=not args.no_editor,
            open_browser=not args.no_browser,
        )
    else:
        print("Error: Provide a level (e.g. cfscripts pick 12) or --index (e.g. cfscripts pick -i A)")
        sys.exit(1)


def _run_dist(args, config):
    from cfscripts.scripts.pick import run_distribution
    run_distribution()


def _run_stats(args, config):
    from cfscripts.scripts.pick import run_stats
    run_stats(handle=config["handle"])


def _run_atcpick(args, config):
    from cfscripts.scripts.atcpick import run
    run(
        handle=config["handle"],
        index_letter=args.index,
        open_browser=not args.no_browser,
    )
