"""LLM-written explanations for finished ranked problems.

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

import os
from time import sleep

import requests

from cfscripts.core.scraper import (
    NoEditorial,
    get_editorial_excerpt,
    get_problem_html,
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
