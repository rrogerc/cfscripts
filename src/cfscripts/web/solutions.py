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
)

GATEWAY_URL = "https://ai-gateway.vercel.sh/v1/chat/completions"
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions"
GATEWAY_MODEL = "google/gemini-3.7-flash"
GEMINI_MODEL = "gemini-3.7-flash"
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
    """Resolve (url, bearer_token, model): direct Gemini API when a key is
    set, otherwise the Vercel AI Gateway. Both speak the OpenAI chat format,
    so only the URL, token, and model slug differ. LLM_MODEL overrides the
    model on either path."""
    override = os.environ.get("LLM_MODEL")
    gemini_key = os.environ.get("GEMINI_API_KEY")
    if gemini_key:
        return GEMINI_URL, gemini_key, override or GEMINI_MODEL
    token = os.environ.get("AI_GATEWAY_API_KEY") or os.environ.get("VERCEL_OIDC_TOKEN")
    if token:
        return GATEWAY_URL, token, override or GATEWAY_MODEL
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


# Line maps: link each line of the first sample input to the Input-spec
# paragraph that defines it, with a short concrete gloss of the values.
# Positions (not quotes) are what the model returns, because 1-based
# paragraph/line numbers survive the round trip to the frontend DOM exactly,
# while quoted text would have to be fuzzy-matched through MathJax rendering.

_LINEMAP_MAX_LINES = 40

_LINEMAP_PROMPT = """\
You annotate the sample input of a competitive programming problem so a
reader can tell at a glance what each input line means.

Below are the problem statement, the numbered paragraphs of its Input
specification, and the numbered lines of its first sample input.

Output strict JSON only — no markdown fence, no commentary — shaped like:
{{"lines": [{{"line": 1, "para": 1, "text": "n = 5 (array length), k = 2 (max swaps)"}}]}}

Rules:
- One entry per sample-input line, in order, covering every listed line.
- "para" is the 1-based number of the Input-specification paragraph that
  describes that line.
- "text" reads out the line's concrete values: variable = value, each with
  a 1-3 word meaning in parentheses when the statement gives one. For long
  arrays, abbreviate: "a = [3, 1, 4, ...] (7 values)". Keep it under 90
  characters, plain text only — no TeX, no dollar signs.
- When lines repeat (e.g. one block per test case), say which repetition a
  line belongs to: "test 2: n = 3 (string length)".

# Problem statement

{statement}

# Input specification paragraphs

{paras}

# Sample input lines

{lines}
"""


def _parse_linemap(content, para_count, line_count):
    """Validate the model's JSON into a clean {"lines": [...]} dict.

    Entries with out-of-range positions are dropped rather than failing the
    whole map — a partially annotated sample is still useful.
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
        if not (1 <= line <= line_count and 1 <= para <= para_count):
            continue
        if line in seen:
            continue
        seen.add(line)
        lines.append({"line": line, "para": para, "text": gloss.strip()[:120]})
    if not lines:
        raise SolutionUnavailable("Model returned an empty line map")
    return {"lines": lines, "para_count": para_count}


def generate_linemap(contest_id, index):
    """Map the first sample input's lines to Input-spec paragraphs.

    Returns (data, model) where data is {"lines": [{line, para, text}],
    "para_count": N}. Raises SolutionUnavailable for problems without a
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

    prompt = _LINEMAP_PROMPT.format(
        statement=statement,
        paras="\n".join(f"[{i}] {p}" for i, p in enumerate(paras, 1)),
        lines="\n".join(f"[{i}] {ln}" for i, ln in enumerate(sample_lines, 1)),
    )
    content, model = _chat(prompt)
    return _parse_linemap(content, len(paras), len(sample_lines)), model


def _chat(prompt):
    url, token, model = _endpoint()
    res = None
    # Newest models throw transient "high demand" 503s — a couple of quick
    # retries usually rides them out.
    for attempt, delay in enumerate((2, 5, 0)):
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
        if res.status_code == 200 or (res.status_code not in (429,) and res.status_code < 500):
            break
        if delay:
            sleep(delay)

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
        raise SolutionUnavailable("Model returned an empty editorial")
    return content.strip(), model
