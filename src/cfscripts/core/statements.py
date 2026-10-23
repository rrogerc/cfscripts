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
    return _sanitize_statement_html(str(root), source_url)


def _sanitize_statement_html(raw_html, source_url):
    return nh3.clean(
        raw_html,
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


def extract_atcoder_statement(page_html, contest_id, problem_id, source_url):
    """Extract and sanitize the English statement from an AtCoder task page."""
    normalized = page_html.replace("\r\n", "\n").replace("\r", "\n")
    soup = BeautifulSoup(normalized, "html.parser")
    if soup.title is None:
        raise ValueError("The provider returned a page without a title")
    title_match = re.match(r"^([A-Za-z0-9]+)\s*-\s*(.+)$", soup.title.get_text(strip=True))
    if title_match is None:
        raise ValueError("The provider returned a different page")
    if soup.select_one(f'a[href*="/contests/{contest_id}"]') is None:
        raise ValueError("The provider returned a different contest")

    index = title_match.group(1)
    problem_title = escape(title_match.group(2))

    limits_match = re.search(
        r"Time Limit:\s*([^/\n\r]+?)\s*/\s*Memory Limit:\s*([^\n\r<]+)",
        soup.get_text(),
    )
    if limits_match is None:
        raise ValueError("Missing statement limits")
    time_limit = escape(limits_match.group(1).strip())
    memory_limit = escape(limits_match.group(2).strip())

    en = soup.select_one("#task-statement .lang-en")
    if en is None:
        raise ValueError("The original English statement is unavailable")

    # Input/Output format boxes in AtCoder wrap <var> inside <pre>. MathJax skips
    # <pre> by default, so turn format boxes into .atc-io-pre divs while keeping
    # sample test <pre> elements intact.
    for pre in en.select("pre"):
        if pre.find("var") is not None:
            pre.name = "div"
            pre["class"] = ["atc-io-pre"]

    for var in en.select("var"):
        tex = var.get_text().strip()
        var.replace_with(f"$$${tex}$$$" if tex else "")

    description_parts = []
    input_parts = []
    output_parts = []
    sample_inputs = {}
    sample_outputs = {}
    sample_notes = {}
    extra_notes = []

    for sec in en.select("section"):
        h3 = sec.find("h3")
        if h3 is None:
            continue
        heading = h3.get_text(" ", strip=True)
        if heading == "Problem Statement":
            h3.decompose()
            description_parts.append(sec.decode_contents())
        elif heading == "Constraints":
            title_div = soup.new_tag("div", attrs={"class": "section-title"})
            title_div.string = "Constraints"
            h3.replace_with(title_div)
            description_parts.append(sec.decode_contents())
        elif heading == "Input":
            title_div = soup.new_tag("div", attrs={"class": "section-title"})
            title_div.string = "Input"
            h3.replace_with(title_div)
            input_parts.append(sec.decode_contents())
        elif heading in ("Output", "Input and Output", "Interaction"):
            title_div = soup.new_tag("div", attrs={"class": "section-title"})
            title_div.string = heading
            h3.replace_with(title_div)
            output_parts.append(sec.decode_contents())
        elif m := re.fullmatch(r"Sample Input\s*(\d+)", heading):
            num = m.group(1)
            h3.decompose()
            pre = sec.find("pre")
            if pre is None:
                raise ValueError(f"Missing sample input {num}")
            pre_extracted = pre.extract()
            pre_extracted.insert(0, soup.new_tag("span"))
            sample_inputs[num] = str(pre_extracted)
            rem = sec.decode_contents().strip()
            if rem:
                sample_notes.setdefault(num, []).append(rem)
        elif m := re.fullmatch(r"Sample Output\s*(\d+)", heading):
            num = m.group(1)
            h3.decompose()
            pre = sec.find("pre")
            if pre is None:
                raise ValueError(f"Missing sample output {num}")
            pre_extracted = pre.extract()
            pre_extracted.insert(0, soup.new_tag("span"))
            sample_outputs[num] = str(pre_extracted)
            rem = sec.decode_contents().strip()
            if rem:
                sample_notes.setdefault(num, []).append(rem)
        else:
            title_div = soup.new_tag("div", attrs={"class": "section-title"})
            title_div.string = heading
            h3.replace_with(title_div)
            extra_notes.append(sec.decode_contents())

    if not description_parts or (not input_parts and not output_parts):
        raise ValueError("The complete English statement is unavailable")

    sample_pairs = []
    for num, in_pre in sample_inputs.items():
        if num not in sample_outputs:
            raise ValueError(f"Missing sample output {num}")
        sample_pairs.append(
            f'<div class="input"><div class="title">Input</div>{in_pre}</div>'
            f'<div class="output"><div class="title">Output</div>{sample_outputs[num]}</div>'
        )

    if not sample_pairs and not extra_notes:
        raise ValueError("The sample tests are unavailable")

    note_blocks = list(extra_notes)
    if sample_notes:
        sample_note_items = []
        for num in sample_inputs:
            if num in sample_notes:
                label = f"<p><strong>Sample {escape(num)}:</strong></p>" if len(sample_inputs) > 1 else ""
                sample_note_items.append(label + "".join(sample_notes[num]))
        if sample_note_items:
            note_blocks.append(
                '<div class="section-title">Note</div>' + "".join(sample_note_items)
            )

    assembled = (
        '<div class="problem-statement">'
        f'<div class="header"><div class="title">{escape(index)}. {problem_title}</div>'
        f'<div class="time-limit"><div class="property-title">time limit per test</div>{time_limit}</div>'
        f'<div class="memory-limit"><div class="property-title">memory limit per test</div>{memory_limit}</div></div>'
        f'<div>{"".join(description_parts)}</div>'
        + (f'<div class="input-specification">{"".join(input_parts)}</div>' if input_parts else "")
        + (f'<div class="output-specification">{"".join(output_parts)}</div>' if output_parts else "")
        + (
            '<div class="sample-tests"><div class="section-title">Examples</div>'
            f'<div class="sample-test">{"".join(sample_pairs)}</div></div>'
            if sample_pairs else ""
        )
        + (f'<div class="note">{"".join(note_blocks)}</div>' if note_blocks else "")
        + "</div>"
    )
    return _sanitize_statement_html(assembled, source_url)


def fetch_atcoder_statement(contest_id, problem_id):
    if (
        not isinstance(contest_id, str)
        or not re.fullmatch(r"abc\d+", contest_id)
        or not isinstance(problem_id, str)
        or not re.fullmatch(r"[a-z0-9_]+", problem_id)
    ):
        raise ValueError("Invalid AtCoder problem identifier")
    url = f"https://atcoder.jp/contests/{contest_id}/tasks/{problem_id}"
    try:
        response = requests.get(url, headers=_HEADERS, timeout=_TIMEOUT)
        response.raise_for_status()
        html = extract_atcoder_statement(response.text, contest_id, problem_id, url)
    except (requests.RequestException, ValueError, KeyError, TypeError, AttributeError) as exc:
        logger.warning("Could not load AtCoder statement data from %s: %s", url, exc)
        raise ProblemUnavailable(
            "The problem statement is temporarily unavailable. Please try again shortly."
        ) from exc
    return Statement(html=html, source_url=url)
