"""LLM-written helpers cached per problem: editorials and sample-input
line maps.

Editorials (for finished ranked problems):

The model is never asked to solve the problem cold when we can avoid it:
we scrape the contest's official editorial blog (which carries the
authors' reference solution code) and have the model explain that. A
flash-tier model is unreliable at *solving* problems near a player's
elo, but very good at *explaining* a known-correct solution — grounding
it in the official editorial is what makes cheap generation trustworthy.
Solving from scratch is only a fallback for contests with no editorial.

Calls go through the Vercel AI Gateway (OpenAI-compatible endpoint), so
the model is just a string to swap while tuning.
"""

import json
import os
import re
from time import sleep

import requests

from cfscripts.core.scraper import (
    NoEditorial,
    get_editorial_excerpt,
    get_input_spec_paragraphs,
    get_problem_html,
    get_sample_input_lines,
    html_to_text,
    split_clauses,
)

GATEWAY_URL = "https://ai-gateway.vercel.sh/v1/chat/completions"
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions"
GATEWAY_MODEL = "google/gemini-3.7-flash"
GEMINI_MODEL = "gemini-3.7-flash"
# Tried when the primary answers "high demand". The newest flash model goes
# through capacity spikes that last hours, and an annotation that silently
# doesn't appear is worse than one written by the previous model.
GATEWAY_FALLBACK_MODEL = "google/gemini-3.6-flash"
GEMINI_FALLBACK_MODEL = "gemini-3.6-flash"
_TIMEOUT_SECONDS = 240


class SolutionUnavailable(Exception):
    pass


_STYLE_RULES = """\
You are writing a short, beginner-friendly editorial for a Codeforces problem.

Output rules:
- Markdown only.
- Wrap ALL math in triple-dollar delimiters, e.g. $$$n \\le 10^5$$$ — this is
  the site's renderer format. Every math span must open AND close with exactly
  three dollar signs. Never use one or two dollar signs, \\( \\), or \\[ \\].
- Simple language, short sentences. The reader knows basic programming but this
  problem is at the edge of their ability. No unexplained jargon.
- Use exactly this structure:

## The key idea
1-3 sentences: the single insight that unlocks the problem.

## Step by step
How to get from the statement to that insight. Build intuition. If the problem
has a classic wrong first instinct, name it and show why it fails.

## The code
Walk through the solution briefly in reading order, then give the complete
code in one ```cpp fenced block. If the original code is messy or golfed,
present a cleaned-up version with clear variable names but identical logic.

## Complexity
One line: time and memory.
"""

_WITH_EDITORIAL = """\
Below are the problem statement and an excerpt of the contest's official
editorial (scraped, so its formatting is rough; it usually contains the
authors' reference solution code). Base your explanation on the
editorial's approach — especially its code — and do NOT invent a
different approach. Do not mention the editorial or that material was
provided to you; present the approach simply as "the solution".

# Problem: {title}

{statement}

# Official editorial material

{editorial}
"""

_WITHOUT_CODE = """\
Below is the problem statement. Solve the problem yourself first, carefully.
Check your approach against the sample tests before writing anything — if
your idea disagrees with a sample, rethink it.

# Problem: {title}

{statement}
"""


def _endpoint():
    """Resolve (url, bearer_token, model, fallback_model): direct Gemini API
    when a key is set, otherwise the Vercel AI Gateway. Both speak the OpenAI
    chat format, so only the URL, token, and model slug differ. LLM_MODEL
    overrides the primary model on either path."""
    override = os.environ.get("LLM_MODEL")
    gemini_key = os.environ.get("GEMINI_API_KEY")
    if gemini_key:
        return GEMINI_URL, gemini_key, override or GEMINI_MODEL, GEMINI_FALLBACK_MODEL
    token = os.environ.get("AI_GATEWAY_API_KEY") or os.environ.get("VERCEL_OIDC_TOKEN")
    if token:
        return GATEWAY_URL, token, override or GATEWAY_MODEL, GATEWAY_FALLBACK_MODEL
    raise SolutionUnavailable(
        "No LLM credentials — set GEMINI_API_KEY (free key at "
        "aistudio.google.com) or enable the Vercel AI Gateway"
    )


def generate(contest_id, index, name):
    """Write an explanation for a problem.

    Returns (markdown, source_url, model). source_url is the editorial
    blog the explanation is grounded in, or None if the model had to
    solve from scratch.
    """
    statement = html_to_text(get_problem_html(contest_id, index))
    if not statement or statement.startswith("Error:"):
        raise SolutionUnavailable(
            f"Could not fetch the statement for {contest_id}{index}"
        )

    try:
        editorial, source_url = get_editorial_excerpt(contest_id, index)
    except NoEditorial:
        editorial, source_url = None, None

    title = f"{contest_id}{index}. {name}"
    if editorial is not None:
        task = _WITH_EDITORIAL.format(
            title=title, statement=statement, editorial=editorial
        )
    else:
        task = _WITHOUT_CODE.format(title=title, statement=statement)

    content, model = _chat(f"{_STYLE_RULES}\n\n{task}")
    return content, source_url, model


# Line maps: link the first sample input to the statement that explains it.
# Each line carries (a) the variable behind every individual token, by its
# TeX name, so the client can light up that variable's mentions anywhere in
# the statement, and (b) the Input-spec clause that defines the line.
#
# The model returns positions and TeX names, never prose quotes to search
# for: 1-based line/paragraph/clause numbers survive the round trip to the
# DOM exactly, and TeX names match the $$$...$$$ spans Codeforces already
# writes. The resolved clause text ships alongside its index so the client
# can confirm the split agreed before highlighting anything.

_LINEMAP_MAX_LINES = 40

# Bump when the payload shape changes — cached rows below this regenerate.
LINEMAP_VERSION = 2

_LINEMAP_PROMPT = """\
You annotate the sample input of a competitive programming problem so a
reader can tell at a glance what each value means.

Below are the problem statement, the Input specification broken into
numbered paragraphs and clauses, and the numbered lines of the first sample
input with their token counts.

Output strict JSON only — no markdown fence, no commentary — shaped like:
{{"lines": [
  {{"line": 1, "para": 1, "clause": 2, "kind": "scalars",
   "text": "t = 4 (number of test cases)",
   "vars": [{{"tex": "t", "text": "number of test cases"}}]}},
  {{"line": 3, "para": 4, "clause": 2, "kind": "array",
   "text": "test 1: a = [1, 2, 1] (the array)",
   "vars": [{{"tex": "a", "text": "the array"}}]}}
]}}

Rules:
- One entry per sample-input line, in order, covering every listed line.
- "para" is the 1-based paragraph of the Input specification describing the
  line; "clause" is the 1-based clause WITHIN that paragraph that actually
  says what the values mean. Prefer the defining clause ("the number of
  rows") over the clause that merely states the format or the bounds.
- "kind" is "scalars" when the line is a fixed list of named values, or
  "array" when the whole line is one sequence of the same variable.
- "vars" gives the variable behind each token:
    * kind "scalars": exactly one entry per token, in token order.
    * kind "array": exactly one entry, covering the whole line.
  "tex" is the variable's name exactly as the statement writes it in math,
  without dollar signs — "n", "m", "a_i". For an array use its base name
  ("a", not "a_1"). "text" is a 1-4 word meaning ("number of rows").
- "text" on the line reads out the concrete values for a tooltip: variable =
  value, meaning in parentheses. For long arrays abbreviate: "a = [3, 1, 4,
  ...] (7 values)". Under 90 characters, plain text, no dollar signs.
- When lines repeat (one block per test case), say which repetition the line
  belongs to: "test 2: n = 3 (string length)".

# Problem statement

{statement}

# Input specification

{paras}

# Sample input lines

{lines}
"""


# A usable TeX variable name: an identifier with an optional subscript.
# Anything more complex (a whole constraint like "1 \le n \le 10^5") is not
# a highlight anchor, so it is dropped rather than matched against.
_TEX_IDENT = re.compile(r"\\?[A-Za-z]+(?:_\{?[A-Za-z0-9]+\}?)?")


def _clean_tex(raw):
    """Normalize a model-supplied variable name, or '' if it isn't one."""
    s = str(raw).replace("$", "").strip()
    return s if _TEX_IDENT.fullmatch(s) else ""


def _parse_linemap(content, paras_clauses, sample_lines):
    """Validate the model's JSON into the cached payload.

    Every field degrades on its own: an unusable clause falls back to
    highlighting the whole paragraph, and unusable per-token variables fall
    back to treating the line as one unit. Entries with out-of-range
    line/paragraph numbers are dropped — a partially annotated sample is
    still useful — but a map with nothing left is an error.
    """
    # Models sometimes fence JSON despite instructions; unwrap before parsing.
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", content.strip())
    try:
        raw = json.loads(text)
        entries = raw["lines"]
    except (ValueError, KeyError, TypeError):
        raise SolutionUnavailable("Model returned malformed line-map JSON")

    seen = set()
    lines = []
    for e in entries:
        try:
            line, para, gloss = int(e["line"]), int(e["para"]), str(e["text"])
        except (KeyError, TypeError, ValueError):
            continue
        if not (1 <= line <= len(sample_lines) and 1 <= para <= len(paras_clauses)):
            continue
        if line in seen:
            continue
        seen.add(line)

        clauses = paras_clauses[para - 1]
        try:
            clause = int(e.get("clause") or 0)
        except (TypeError, ValueError):
            clause = 0
        if not 1 <= clause <= len(clauses):
            clause = 0  # highlight the whole paragraph instead

        variables = []
        for v in e.get("vars") or []:
            if not isinstance(v, dict):
                continue
            variables.append({
                "tex": _clean_tex(v.get("tex", "")),
                "text": str(v.get("text", "")).strip()[:60],
            })

        # The token split must match the client's, which splits the same
        # line on whitespace — so a scalar mapping is only usable when it
        # names every token exactly once.
        tokens = sample_lines[line - 1].split()
        kind = e.get("kind")
        if kind == "scalars" and len(variables) != len(tokens):
            kind = "line"
        elif kind == "array" and len(variables) != 1:
            kind = "line"
        elif kind not in ("scalars", "array"):
            kind = "line"

        lines.append({
            "line": line,
            "para": para,
            "clause": clause,
            "clause_text": clauses[clause - 1] if clause else "",
            "kind": kind,
            "vars": variables,
            "text": gloss.strip()[:120],
        })

    if not lines:
        raise SolutionUnavailable("Model returned an empty line map")
    return {"v": LINEMAP_VERSION, "lines": lines, "para_count": len(paras_clauses)}


def generate_linemap(contest_id, index):
    """Map the first sample input's tokens to the statement that explains them.

    Returns (data, model). Raises SolutionUnavailable for problems without a
    standard Input section or sample (e.g. interactive/unusual formats).
    """
    html = get_problem_html(contest_id, index)
    statement = html_to_text(html)
    if not statement or statement.startswith("Error:"):
        raise SolutionUnavailable(
            f"Could not fetch the statement for {contest_id}{index}"
        )

    paras = get_input_spec_paragraphs(html)
    sample_lines = get_sample_input_lines(html)
    if not paras or not sample_lines:
        raise SolutionUnavailable(
            f"{contest_id}{index} has no standard input spec / sample to map"
        )
    # Huge samples (stress-test style) get their head annotated; the tail is
    # usually more of the same repetition anyway.
    sample_lines = sample_lines[:_LINEMAP_MAX_LINES]
    paras_clauses = [split_clauses(p) for p in paras]

    spec = "\n".join(
        f"Paragraph {i}:\n"
        + "\n".join(f"  [{i}.{j}] {c}" for j, c in enumerate(clauses, 1))
        for i, clauses in enumerate(paras_clauses, 1)
    )
    lines = "\n".join(
        f"[{i}] ({len(ln.split())} tokens) {ln}"
        for i, ln in enumerate(sample_lines, 1)
    )
    content, model = _chat(
        _LINEMAP_PROMPT.format(statement=statement, paras=spec, lines=lines)
    )
    return _parse_linemap(content, paras_clauses, sample_lines), model


def _post(url, token, model, prompt):
    """One model, with a couple of quick retries — the newest models throw
    transient "high demand" 503s that a short wait usually rides out."""
    res = None
    for delay in (2, 5, 0):
        try:
            res = requests.post(
                url,
                headers={"Authorization": f"Bearer {token}"},
                json={
                    "model": model,
                    "messages": [{"role": "user", "content": prompt}],
                },
                timeout=_TIMEOUT_SECONDS,
            )
        except requests.exceptions.RequestException as e:
            raise SolutionUnavailable(f"LLM request failed: {e}")
        if res.status_code == 200 or (res.status_code != 429 and res.status_code < 500):
            break
        if delay:
            sleep(delay)
    return res


def _chat(prompt):
    """Ask the model, falling back to the previous flash model when the
    primary is out of capacity. Returns (content, model_that_answered)."""
    url, token, model, fallback = _endpoint()

    candidates = [model] + ([fallback] if fallback and fallback != model else [])
    for candidate in candidates:
        res = _post(url, token, candidate, prompt)
        if res.status_code == 200:
            model = candidate
            break
        # Only a capacity problem is worth a different model; a bad request
        # or a bad key would fail the same way twice.
        if res.status_code != 429 and res.status_code < 500:
            break

    if res.status_code != 200:
        detail = res.text[:300]
        raise SolutionUnavailable(
            f"LLM API returned {res.status_code}: {detail}"
        )

    try:
        content = res.json()["choices"][0]["message"]["content"]
    except (KeyError, IndexError, ValueError):
        raise SolutionUnavailable("LLM API returned an unexpected response shape")
    if not content or not content.strip():
        raise SolutionUnavailable("Model returned an empty response")
    return content.strip(), model
