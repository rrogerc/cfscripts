# Ranked titles and subdivisions

The Ranked tab derives a title from the player's existing ranked Elo. It uses
the [Codeforces title boundaries](https://codeforces.com/blog/entry/142495),
with four CF Picker subdivisions in ascending order: IV, III, II, I. Each
bounded tier is divided evenly: 50 Elo for a 200-point tier, 75 for Expert,
25 for International Master, and 100 for International Grandmaster.

Newbie subdivisions begin at 0, 300, 600 and 900; ratings below zero also remain
in Newbie IV. Legendary Grandmaster is open-ended, with subdivisions beginning
at 3000, 3100, 3200 and 3300. Legendary Grandmaster I has no upper limit.

`pwa-frontend/src/ranks.ts` uses the same rounded whole-number Elo shown by
Ranked, so the displayed rating, title, subdivision range and promotion target
agree at boundaries. Elo calculation, problem selection and match records do
not change. Rank is derived on every render and needs no separate stored state.

The full summary shows rank, Elo, four progress segments, current subdivision
range and the next promotion target on the Ranked overview. Live problems and
match reviews omit the player's rank and League comparison; their controls scroll
away with the statement. Post-match results show any subdivision/tier change.
The Rank ladder explains the custom subdivisions and lists the tier ranges.

## League percentile comparison

The comparison shown alongside each rank uses an explicit dated
snapshot of public distributions, bundled with the frontend. It does not make
network requests while playing, and does not describe a CF Picker leaderboard.
The player's displayed ranked Elo is used as the Codeforces rating to compare.

Codeforces source: [user.ratedList](https://codeforces.com/api/user.ratedList?activeOnly=true&includeRetired=false),
with `activeOnly=true` and `includeRetired=false`. Per the
[API documentation](https://codeforces.com/apiHelp/methods#user.ratedList), this
includes users who participated in a rated contest during the past month and
were online in that period. New rated accounts are included. The September 8,
2026 snapshot contains 38,123 users. Only aggregate counts by rating are saved.

League source: [OP.GG's North America tier distribution](https://op.gg/lol/statistics/tiers?region=na),
Ranked Solo/Duo, with 1,554,744 players in the same day's snapshot. We use exact
player counts in all 31 divisions, not rounded published percentages or an
assumption that divisions contain equal numbers of players. Master, Grandmaster
and Challenger retain their actual undivided names.

For a displayed Elo `r`, `topPercent = 100 * count(CF rating >= r) / CF total`.
This includes all tied users. Find the first League division, ordered strongest
to weakest, whose cumulative player share is at least `topPercent`. There is no
interpolation between CF ratings. Above the highest sampled rating, show an
upper bound based on one CF player's share instead of an exact zero percentile.

The main summary uses the exact Elo. Each tier/subdivision in the ladder shows
the League ranks at both ends of its rating range, collapsing identical ends.
This is an approximate comparison of relative standing in different populations.
The UI states the activity window, League region/queue, date and source links.

To refresh, run `.venv/bin/python scripts/update_rank_distributions.py`, review
the generated `pwa-frontend/src/rankDistributions.ts`, run checks and deploy.
The importer validates player counts, cumulative totals, all League divisions
and the selected region before replacing the snapshot. Saved source responses
can be supplied with `--cf-json`, `--league-html` and `--date` for reproduction.

Validation:

```sh
node --test tests/ranks.test.mjs
node --test tests/league_ranks.test.mjs
PYTHONPATH=src .venv/bin/python tests/browser_ranked_rank.py
```

The Node checks require a version that supports TypeScript imports (22.18+).
Browser checks need a frontend build served on port 4173, Playwright, and Chrome
or Chromium. All API calls use isolated fixtures, including promotion/demotion,
queueing, review and long rank names at desktop and phone widths.
