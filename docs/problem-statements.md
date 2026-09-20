# Problem statement source

Problem statements retain the complete English HTML from the Codeforces mirror
at `codeforces.me` and are saved in Postgres. Queuing, reopening a match, match review and statement-based helpers
all read the same saved HTML. Codeforces' official API still supplies ratings,
problem selection and submission verdicts.

## Why this source

The previous implementation downloaded a Codeforces webpage on every request.
Codeforces started returning Cloudflare browser challenges, which the server
could not solve. The first replacement used Luogu's structured English Markdown,
but CF2109C1 exposed a source-fidelity problem: both tables were already flattened
into concatenated text in Luogu's JSON. A Markdown renderer cannot recover the
missing rows, columns or merged cells. New imports preserve the original HTML;
the persistent cache keeps matches independent of repeat webpage requests.

Sources evaluated on September 8, 2026:

| Source | Finding |
| --- | --- |
| [Codeforces problem scraper API](https://github.com/kerolloz/codeforces-problem-scraper-api) | Self-hosted Flask code that still scrapes Codeforces HTML. Last repository push was November 2023. It would inherit the same failure. |
| [Open R1 Codeforces dataset](https://huggingface.co/datasets/open-r1/codeforces) | Structured statements and samples, but a May 2025 snapshot rather than a feed for new contests. |
| [Luogu](https://www.luogu.com.cn/problem/CF2242C) | Structured English content, limits, samples and diagrams, but table structure is missing in CF2109C1's description and note. Unsuitable as a lossless statement source. |
| [Codeforces mirror](https://codeforces.me/problemset/problem/2109/C1?locale=en) | Returned the original two HTML tables, including all nine merged cells, and complete statements for older and recent problems. Used for new imports. |

The mirror is a webpage source, not an official statement API or an availability
guarantee. The adapter is isolated in `core/statements.py` so provider changes do
not affect match logic. Luogu's renderer remains for existing imports/tests but
is not a silent fallback: a successful response containing flattened tables
would still be a broken statement.

## Request and validation

Request `GET https://codeforces.me/problemset/problem/{contest_id}/{index}?locale=en`.

The adapter verifies the full problem ID in the page title, English section
headings, limits and samples. Only `.problem-statement` is retained, then `nh3`
sanitizes it with explicit allowed tags, attributes and URL schemes. Table cells,
row/column spans, TeX and sample whitespace survive; scripts, event handlers and
page navigation do not. Challenge pages and incomplete records are errors and
are never cached. Interactive statements may have Interaction instead of Output.

## Persistence and outages

`problem_statements` is keyed by `(contest_id, problem_index)` and stores the
validated HTML, source URL and fetch timestamp. Rows do not automatically expire:
a provider outage must not invalidate a usable statement. A cache hit makes no
statement-provider request. A cache miss fetches and persists the statement
before a ranked match can start, preserving the player's full 25 minutes.

An uncached problem still needs the mirror to be available. Existing cached problems
and match statements continue to load during a provider outage. This does not
make ratings or submission checks independent of Codeforces' official API.
Diagrams retain their image URLs and still require the image host to be reachable.

With the package installed and `DATABASE_URL` set, statements can be warmed
ahead of time:

```sh
python -m cfscripts.web.statements 2049/C 2242/C
```

After a statement correction, explicitly refresh it:

```sh
python -m cfscripts.web.statements --refresh 2049/C
```

A failed refresh leaves the previous saved statement intact. A standalone
picker without `DATABASE_URL` can use the provider directly, without persistence.

## Statement features

Sample annotations include a SHA-256 hash of the exact statement HTML. The
server regenerates older maps, and the browser checks the hash before applying
line or paragraph positions. Ranked browser caches use a new version so saved
matches reload the statement after the source change.

Tables have visible cell borders, padding, alignment and a keyboard-accessible
horizontal scroll region on narrow screens. Problem and Coach exports expand
merged cells into rectangular Markdown tables. Model prompts also retain cell
boundaries and repeat merged values so commands stay attached to their results.
Exports protect TeX from Markdown escaping and preserve display equations.
Sample copy buttons capture the original input before hover
annotations modify the DOM, preserving whitespace and excluding explanations.
Hovering an input line highlights just that row and its test case's output;
tapping pins the highlight for scrolling on phones. Matching uses Codeforces'
numbered case groups, with one output line per case when outputs aren't grouped.
Samples without case markers or with ambiguous output boundaries stay unlinked.
MathJax rendering waits for startup and runs sequentially, including in match
review; overflow measurements run after rendering and on layout changes.

## Verification

```sh
PYTHONPATH=src python -m unittest discover -s tests -v
```

The regression tests cover provider validation, math and sample preservation,
safe rendering, reuse during provider outages, and the requirement to save a
statement before starting a match. Integration checks use an isolated database;
production match records are not used for test writes.

Browser checks require Playwright (`pip install playwright`; then
`playwright install chromium`, or use an existing macOS Chrome). Build with
`npm --prefix pwa-frontend run build`, and serve it in another terminal:

```sh
python -m http.server 4173 --bind 127.0.0.1 --directory pwa-frontend/dist
```

Then run:

```sh
PYTHONPATH=src python tests/browser_statement_features.py
```

These checks use isolated API fixtures, including CF2109C1's actual HTML, and cover desktop/mobile layouts,
delayed MathJax loading, stale annotation rejection, hover/tap highlighting,
all copy controls, timer pause/resume/reset/expiry, problem changes, tab
switching, queue errors, match reopening and solution review. Both real tables
are checked in light/dark themes at every text-width setting, including merged
cells, math, horizontal scrolling and Problem/Coach/sample copies.
