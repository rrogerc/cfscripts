#!/usr/bin/env python3
"""Diagnostic: compare whatif simulation deltas against official CF deltas.

Run from the repo root:
    PYTHONPATH=src python3 diagnose_whatif.py [--handle HANDLE]
"""

import sys, os, argparse, json, time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from cfscripts.lib.rating import (
    get_rating_changes_for_contest,
    get_rating_changes_for_user,
)
from cfscripts.lib.contests import (
    get_contest_map,
    get_participated_contest_ids,
    get_contest_and_standings,
)
from cfscripts.lib.performance import (
    UserPerformanceCalculator,
    ContestantEntry,
    _UNSET,
)
from cfscripts.lib.rating_calculator import CodeforcesRatingCalculator
from cfscripts.lib.api import NoRatingChangesError
from cfscripts.lib import printer

RATING_ADJUSTMENT = [1400, 900, 550, 300, 150, 50, 0]
INITIAL_RATING = 1400


def displayed_rating(real_rating, n_contests):
    adj = RATING_ADJUSTMENT[min(n_contests, len(RATING_ADJUSTMENT) - 1)]
    return real_rating - adj


def build_official_history(handle):
    """Return {contest_id: {oldRating, newRating, delta, rank}} from official API."""
    changes = get_rating_changes_for_user(handle)
    history = {}
    for rc in changes:
        cid = rc["contestId"]
        history[cid] = {
            "oldRating": rc["oldRating"],
            "newRating": rc["newRating"],
            "delta": rc["newRating"] - rc["oldRating"],
            "rank": rc["rank"],
            "contestName": rc.get("contestName", ""),
        }
    return history


def diagnose_single_contest(handle, contest_id, sim_rating, official_history):
    """Run the rating calculation for one contest and return detailed diagnostics."""
    diag = {"contest_id": contest_id}

    try:
        contest, standings = get_contest_and_standings(contest_id)
    except Exception as e:
        diag["error"] = f"standings fetch failed: {e}"
        return diag

    diag["contest_name"] = contest.get("name", "?")

    # Build contestant dict (same as performance.py)
    contestants = {}
    user_part_type = None
    user_rank = None
    for stand in standings:
        part_type = stand["party"]["participantType"]
        if part_type == "PRACTICE":
            continue
        members = stand["party"]["members"]
        if len(members) == 1:
            h = members[0]["handle"]
            pts = stand["points"]
            pen = stand["penalty"]
            if part_type == "CONTESTANT":
                if h not in contestants:
                    contestants[h] = ContestantEntry(h, _UNSET, _UNSET, _UNSET)
                contestants[h] = contestants[h]._replace(points=pts, penalty=pen)
            if h.lower() == handle.lower():
                contestants[h] = ContestantEntry(h, pts, pen, _UNSET)
                user_part_type = part_type
                user_rank = stand["rank"]

    diag["participation_type"] = user_part_type

    if handle not in contestants:
        # Try case-insensitive match
        for h in contestants:
            if h.lower() == handle.lower():
                contestants[handle] = contestants.pop(h)
                break

    if handle not in contestants:
        diag["error"] = "user not found in standings"
        return diag

    # Fetch rating changes
    try:
        rating_changes = get_rating_changes_for_contest(contest_id)
    except NoRatingChangesError:
        diag["error"] = "no rating changes available"
        return diag

    if len(rating_changes) == 0:
        diag["error"] = "empty rating changes (contest just ended?)"
        return diag

    # Count how many rated participants exist in official data
    rc_handles = {rc["handle"] for rc in rating_changes}
    diag["n_rating_changes"] = len(rc_handles)

    # Apply ratings from rating_changes
    user_was_rated = False
    rated_handles = {handle}
    for rc in rating_changes:
        h = rc["handle"]
        if h == handle:
            user_was_rated = True
        if h not in contestants:
            continue
        rated_handles.add(h)
        rating = rc["oldRating"]
        if rating == 0 and contest_id >= 1360:
            rating = 1400
        contestants[h] = contestants[h]._replace(rating=rating)

    diag["user_was_rated"] = user_was_rated

    # Count how many from rating_changes were NOT in standings
    in_standings = set(contestants.keys())
    missing_from_standings = rc_handles - in_standings
    diag["n_missing_from_standings"] = len(missing_from_standings)
    if len(missing_from_standings) > 0 and len(missing_from_standings) <= 10:
        diag["missing_handles"] = sorted(missing_from_standings)

    # Filter to rated handles only
    contestants = {h: c for h, c in contestants.items() if h in rated_handles}

    # Override user rating to simulated
    contestants[handle] = contestants[handle]._replace(rating=sim_rating)

    diag["n_contestants_used"] = len(contestants)

    # Verify no UNSET values
    bad = []
    for h, c in contestants.items():
        if c.points == _UNSET or c.penalty == _UNSET or c.rating == _UNSET:
            bad.append(h)
    if bad:
        diag["error"] = f"unset values for {len(bad)} contestants"
        return diag

    # Run calculator
    calc = CodeforcesRatingCalculator(contestants.values())
    for con in calc.contestants:
        if con.party == handle:
            diag["sim_delta"] = con.delta
            diag["sim_need_rating"] = con.need_rating
            diag["sim_seed"] = round(con.seed, 4)
            diag["sim_rank"] = con.rank
            break

    # Now run with OFFICIAL rating (not simulated) for comparison
    if contest_id in official_history:
        off = official_history[contest_id]
        off_rating = off["oldRating"]
        if off_rating == 0 and contest_id >= 1360:
            off_rating = 1400
        contestants2 = dict(contestants)
        contestants2[handle] = contestants2[handle]._replace(rating=off_rating)
        calc2 = CodeforcesRatingCalculator(contestants2.values())
        for con in calc2.contestants:
            if con.party == handle:
                diag["official_rating_sim_delta"] = con.delta
                break

    return diag


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--handle", default="Exonerate")
    parser.add_argument("--save", help="Save raw diagnostics to JSON file")
    args = parser.parse_args()
    handle = args.handle

    printer.set_printer(lambda *a, **kw: None)

    print(f"=== Whatif Delta Diagnostic for {handle} ===\n")
    print("Fetching data...")

    official_history = build_official_history(handle)
    print(f"  Official rating changes: {len(official_history)} contests")

    contest_map = get_contest_map()
    contest_ids = get_participated_contest_ids(handle, contest_map)
    print(f"  Participated contests: {len(contest_ids)}")

    # Simulate whatif (--no-virtual equivalent: skip virtuals)
    real_rating = INITIAL_RATING
    n_rated = 0
    cum_diff = 0
    results = []

    # Also track the official rating progression
    official_contests = sorted(official_history.keys(),
                               key=lambda cid: official_history[cid].get("rank", 0))
    # Actually sort by the order they appear in contest_ids
    official_order = []
    for cid, t in contest_ids:
        if cid in official_history:
            official_order.append(cid)

    off_real_rating = INITIAL_RATING
    off_n_rated = 0

    print(f"\nProcessing {len(contest_ids)} contests...\n")

    for i, (contest_id, start_time) in enumerate(contest_ids):
        print(f"  [{i+1}/{len(contest_ids)}] Contest {contest_id}...", end="", flush=True)

        diag = diagnose_single_contest(handle, contest_id, real_rating, official_history)

        if "error" in diag:
            print(f" SKIP ({diag['error']})")
            continue

        if diag.get("participation_type") != "CONTESTANT":
            print(f" SKIP (type={diag.get('participation_type')})")
            continue

        if not diag.get("user_was_rated"):
            print(f" SKIP (not rated)")
            continue

        sim_delta = diag.get("sim_delta")
        if sim_delta is None:
            print(f" SKIP (no delta)")
            continue

        # Get official delta
        if contest_id not in official_history:
            print(f" SKIP (no official history)")
            continue

        off = official_history[contest_id]
        off_delta = off["delta"]

        # Compute display deltas (same as whatif.py)
        new_real = real_rating + sim_delta
        disp_old = displayed_rating(real_rating, n_rated)
        n_rated += 1
        disp_new = displayed_rating(new_real, n_rated)
        sim_display_delta = disp_new - disp_old

        # Official display delta
        off_display_delta = off_delta  # CF shows display deltas

        diff = sim_display_delta - off_display_delta
        cum_diff += diff

        # Internal delta comparison (using official rating)
        off_rating_sim_delta = diag.get("official_rating_sim_delta")

        result = {
            "contest_id": contest_id,
            "contest_name": diag.get("contest_name", "?"),
            "sim_rating_in": real_rating,
            "off_rating_in": off["oldRating"],
            "rating_gap_in": real_rating - (off["oldRating"] if off["oldRating"] != 0 else 1400),
            "sim_internal_delta": sim_delta,
            "off_rating_sim_internal_delta": off_rating_sim_delta,
            "sim_display_delta": sim_display_delta,
            "off_display_delta": off_display_delta,
            "diff": diff,
            "cum_diff": cum_diff,
            "n_contestants_used": diag.get("n_contestants_used"),
            "n_rating_changes": diag.get("n_rating_changes"),
            "n_missing_from_standings": diag.get("n_missing_from_standings", 0),
        }
        results.append(result)

        real_rating = new_real

        sign = "+" if diff >= 0 else ""
        print(f" sim={sim_display_delta:+d} off={off_display_delta:+d} diff={sign}{diff} cum={cum_diff:+d}"
              f" (missing={diag.get('n_missing_from_standings', 0)}, "
              f"used={diag.get('n_contestants_used')}/{diag.get('n_rating_changes')})")

    # Summary
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)

    if not results:
        print("No rated contests found!")
        return

    print(f"\nContests analyzed: {len(results)}")
    print(f"Final cumulative diff: {cum_diff:+d}")
    print(f"Final sim rating: {displayed_rating(real_rating, n_rated)}")

    last_off = results[-1]
    final_off = last_off["off_rating_in"] + last_off["off_display_delta"]
    print(f"Final official rating: {final_off}")

    diffs = [r["diff"] for r in results]
    print(f"\nPer-contest diff: min={min(diffs):+d} max={max(diffs):+d} "
          f"avg={sum(diffs)/len(diffs):+.1f}")

    # Rating gap progression
    print("\n--- Rating gap progression (sim - official) ---")
    for r in results:
        gap = r["rating_gap_in"]
        name = r["contest_name"][:40]
        miss = r["n_missing_from_standings"]
        used = r["n_contestants_used"]
        n_rc = r["n_rating_changes"]
        print(f"  {r['contest_id']:>6} | gap={gap:+4d} | diff={r['diff']:+3d} | "
              f"cum={r['cum_diff']:+4d} | miss={miss:>3} | "
              f"used/rc={used}/{n_rc} | {name}")

    # Highlight contests with missing contestants
    total_missing = sum(r["n_missing_from_standings"] for r in results)
    if total_missing > 0:
        print(f"\n--- {total_missing} total contestants missing from standings across all contests ---")
        for r in results:
            if r["n_missing_from_standings"] > 0:
                print(f"  Contest {r['contest_id']}: {r['n_missing_from_standings']} missing "
                      f"({r['contest_name'][:50]})")

    # Compare: what if we used official ratings instead of simulated?
    print("\n--- Internal delta comparison (sim rating vs official rating) ---")
    for r in results:
        sim_d = r["sim_internal_delta"]
        off_d = r.get("off_rating_sim_internal_delta", "?")
        if off_d != "?":
            int_diff = sim_d - off_d
            print(f"  {r['contest_id']:>6} | sim_delta={sim_d:+4d} off_rating_delta={off_d:+4d} "
                  f"int_diff={int_diff:+3d} | rating_gap={r['rating_gap_in']:+4d}")

    if args.save:
        with open(args.save, "w") as f:
            json.dump(results, f, indent=2)
        print(f"\nSaved raw data to {args.save}")


if __name__ == "__main__":
    main()
