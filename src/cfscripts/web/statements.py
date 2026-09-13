"""Persist validated statements so matches can survive provider outages."""

import argparse
from hashlib import sha256
from time import time

from cfscripts.core.statements import fetch_statement
from cfscripts.web import db


def statement_hash(html):
    return sha256(html.encode("utf-8")).hexdigest()


def get_problem_html(contest_id, index, refresh=False):
    try:
        with db.connect() as conn:
            cached = db.get_statement(conn, contest_id, index)
    except db.DatabaseNotConfigured:
        # The standalone picker can still run without ranked/Neon configured.
        return fetch_statement(contest_id, index).html

    if cached is not None and not refresh:
        return cached["html"]

    statement = fetch_statement(contest_id, index)
    with db.connect() as conn:
        db.save_statement(conn, contest_id, index, statement.html,
                          statement.source_url, int(time()))
    return statement.html


def main():
    parser = argparse.ArgumentParser(description="Cache Codeforces statements for offline reuse")
    parser.add_argument("problems", nargs="+", metavar="CONTEST/INDEX")
    parser.add_argument("--refresh", action="store_true", help="Refresh a saved statement after an erratum")
    args = parser.parse_args()
    # Warming should fail explicitly if it cannot persist anything.
    with db.connect():
        pass
    for problem in args.problems:
        contest_id, index = problem.split("/", 1)
        html = get_problem_html(int(contest_id), index, refresh=args.refresh)
        print(f"Cached {problem}: {len(html)} characters")


if __name__ == "__main__":
    main()
