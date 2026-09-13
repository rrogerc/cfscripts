"""Load and sanitize complete English statements without flattening tables.

Luogu's Markdown renderer remains available for existing imports, but its data
can lose tables before conversion. New statements use the original HTML from
the Codeforces mirror and are persisted by the web layer.
"""

import logging
import math
import re
from dataclasses import dataclass
from html import escape

import requests
import nh3
from bs4 import BeautifulSoup
from markdown_it import MarkdownIt
from mdit_py_plugins.dollarmath import dollarmath_plugin

logger = logging.getLogger(__name__)

_TIMEOUT = (5, 15)
_HEADERS = {
    "User-Agent": "cfscripts/0.1 (+https://github.com/rrogerc/cfscripts)",
    "Accept": "text/html",
}


class ProblemUnavailable(Exception):
    pass


@dataclass(frozen=True)
class Statement:
    html: str
    source_url: str


def _render_math(content, options):
    # Match the existing MathJax configuration, preserving TeX before
    # Markdown can interpret underscores, backslashes or angle brackets.
    content = escape(content)
    if options["display_mode"]:
        return rf"\[{content}\]"
    return f"$$${content}$$$"


_markdown = MarkdownIt("commonmark", {"html": False}).enable("table").use(
    dollarmath_plugin, allow_labels=False, double_inline=True, renderer=_render_math
)


def _text(mapping, key, required=True):
    value = mapping.get(key)
    if value is None and not required:
        return ""
    if not isinstance(value, str) or (required and not value.strip()):
        raise ValueError(f"Missing statement field: {key}")
    return value


def _limit(limits, key, divisor):
    values = limits.get(key)
    if not isinstance(values, list) or not values:
        raise ValueError(f"Missing statement limit: {key}")
    value = values[0]
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"Invalid statement limit: {key}")
    if not math.isfinite(value) or value <= 0:
        raise ValueError(f"Invalid statement limit: {key}")
    return f"{value / divisor:g}"


def render_statement(payload, contest_id, index):
    """Validate the problem identity and render English Markdown safely."""
    if payload.get("status") != 200 or payload.get("template") != "problem.show":
        raise ValueError("The provider did not return a problem")
    problem = payload["data"]["problem"]
    if problem.get("pid") != f"CF{contest_id}{index}" or problem.get("type") != "CF":
        raise ValueError("The provider returned a different problem")
    content = problem["content"]
    if content.get("locale") != "en":
        raise ValueError("The original English statement is unavailable")

    title = escape(_text(content, "name"))
    description = _markdown.render(_text(content, "description"))
    background = _markdown.render(_text(content, "background", required=False))
    input_html = _markdown.render(_text(content, "formatI"))
    output_html = _markdown.render(_text(content, "formatO"))
    note = _markdown.render(_text(content, "hint", required=False))
    seconds = _limit(problem["limits"], "time", 1000)
    megabytes = _limit(problem["limits"], "memory", 1000)

    samples = problem.get("samples")
    if not isinstance(samples, list) or not samples:
        raise ValueError("The sample tests are unavailable")
    sample_html = []
    for sample in samples:
        if not isinstance(sample, list) or len(sample) != 2:
            raise ValueError("Invalid sample test")
        if not all(isinstance(value, str) for value in sample):
            raise ValueError("Invalid sample test text")
        # Escape without Markdown processing so whitespace and literal '<'
        # in samples survive both display and the existing Copy button.
        sample_html.append(
            '<div class="input"><div class="title">Input</div>'
            f'<pre><span>{escape(sample[0])}</span></pre></div>'
            '<div class="output"><div class="title">Output</div>'
            f'<pre><span>{escape(sample[1])}</span></pre></div>'
        )

    return (
        '<div class="problem-statement">'
        f'<div class="header"><div class="title">{escape(index)}. {title}</div>'
        '<div class="time-limit"><div class="property-title">time limit per test</div>'
        f'{seconds} seconds</div>'
        '<div class="memory-limit"><div class="property-title">memory limit per test</div>'
        f'{megabytes} megabytes</div></div>'
        f'<div>{background}{description}</div>'
        '<div class="input-specification"><div class="section-title">Input</div>'
        f'{input_html}</div>'
        '<div class="output-specification"><div class="section-title">Output</div>'
        f'{output_html}</div>'
        '<div class="sample-tests"><div class="section-title">Examples</div>'
        f'<div class="sample-test">{"".join(sample_html)}</div></div>'
        + (f'<div class="note"><div class="section-title">Note</div>{note}</div>' if note else '')
        + '</div>'
    )


def extract_statement(page_html, contest_id, index, source_url):
    """Accept the requested English problem only, retaining its rich markup."""
    soup = BeautifulSoup(page_html, "html.parser")
    expected_title = f"Problem - {contest_id}{index} - Codeforces"
    if soup.title is None or soup.title.get_text(strip=True) != expected_title:
        raise ValueError("The provider returned a different page")
    root = soup.select_one(".problem-statement")
    if root is None:
        raise ValueError("The problem statement is missing")
    title = root.select_one(".header > .title")
    if title is None or not title.get_text(strip=True).startswith(f"{index}. "):
        raise ValueError("The provider returned a different problem")
    headings = {node.get_text(strip=True) for node in root.select(".section-title")}
    if "Input" not in headings or not {"Output", "Interaction"} & headings:
        raise ValueError("The complete English statement is unavailable")
    for selector in (".time-limit", ".memory-limit", ".input-specification > p",
                     ".sample-test .input pre", ".sample-test .output pre"):
        node = root.select_one(selector)
        if node is None or not node.get_text(strip=True):
            raise ValueError(f"Missing statement content: {selector}")

    for copier in root.select(".input-output-copier"):
        copier.decompose()
    # HTML5 parsers consume the first newline immediately after <pre>. An
    # empty span protects it without changing CF's direct per-line divs.
    for pre in root.select("pre"):
        pre.insert(0, soup.new_tag("span"))
    return nh3.clean(
        str(root),
        tags=set(nh3.ALLOWED_TAGS) | {"table", "thead", "tbody", "tfoot", "tr",
                                    "th", "td", "caption", "colgroup", "col"},
        attributes={
            "*": {"class"}, "a": {"href", "title"},
            "img": {"src", "alt", "title", "width", "height"},
            "td": {"rowspan", "colspan"},
            "th": {"rowspan", "colspan", "scope"}, "col": {"span"},
            "ol": {"start", "reversed"}, "li": {"value"},
        },
        clean_content_tags={"script", "style", "iframe", "object"},
        url_schemes={"http", "https"},
        url_relative=("rewrite_with_base", source_url),
    )


def fetch_statement(contest_id, index):
    if not isinstance(contest_id, int) or contest_id <= 0 or not re.fullmatch(r"[A-Z][0-9]?", index):
        raise ValueError("Invalid Codeforces problem identifier")
    url = f"https://codeforces.me/problemset/problem/{contest_id}/{index}?locale=en"
    try:
        response = requests.get(url, headers=_HEADERS, timeout=_TIMEOUT)
        response.raise_for_status()
        html = extract_statement(response.text, contest_id, index, url)
    except (requests.RequestException, ValueError, KeyError, TypeError, AttributeError) as exc:
        logger.warning("Could not load statement data from %s: %s", url, exc)
        raise ProblemUnavailable(
            "The problem statement is temporarily unavailable. Please try again shortly."
        ) from exc
    return Statement(html=html, source_url=url)
