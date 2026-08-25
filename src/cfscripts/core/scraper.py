import re

import cloudscraper
from bs4 import BeautifulSoup

# Reused across requests so the Cloudflare clearance cookie is cached.
# On Vercel Fluid Compute, instances persist across invocations, so the
# JS challenge is solved once per warm instance instead of per request.
_scraper = cloudscraper.create_scraper(
    browser={'browser': 'chrome', 'platform': 'windows', 'mobile': False}
)


def get_problem_html(contest_id, index):
    """Fetch and extract the problem statement HTML from Codeforces."""
    url = f"https://codeforces.com/problemset/problem/{contest_id}/{index}"
    response = _scraper.get(url)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, 'html.parser')
    problem_statement = soup.find('div', class_='problem-statement')

    if not problem_statement:
        return "<p>Error: Could not extract problem statement from Codeforces.</p>"

    return str(problem_statement)


class NoEditorial(Exception):
    pass


# Whole-editorial fallback stays well under the model's context while still
# covering any single problem's section.
_EDITORIAL_MAX_CHARS = 30_000
_MAX_TUTORIAL_LINKS = 3


def get_editorial_excerpt(contest_id, index):
    """Official editorial material for one problem, straight from the
    contest's tutorial blog. Returns (text, blog_url).

    Submission pages are behind Codeforces' JS challenge, but blog entries
    are plain pages — and they carry the authors' reference solution code,
    which is the best possible grounding for an LLM explanation. The prose
    spoilers load via AJAX ("Tutorial is loading...") so mostly the code
    survives scraping; that's the part that matters.
    """
    contest_page = _scraper.get(f"https://codeforces.com/contest/{contest_id}")
    if contest_page.status_code != 200:
        raise NoEditorial(f"Could not load contest page for {contest_id}")
    soup = BeautifulSoup(contest_page.text, 'html.parser')

    links = []
    for a in soup.find_all('a', href=True):
        label = a.get_text(strip=True).lower()
        if '/blog/entry/' not in a['href'] or 'video' in label:
            continue
        if 'tutorial' in label or 'editorial' in label or 'разбор' in label:
            url = 'https://codeforces.com' + a['href'].split('?')[0]
            if url not in links:
                links.append(url)
    if not links:
        raise NoEditorial(f"No editorial blog linked from contest {contest_id}")

    marker = f"{contest_id}{index} - "
    first_text, first_url = None, None
    for url in links[:_MAX_TUTORIAL_LINKS]:
        text = _get_blog_text(url)
        if text is None:
            continue
        if first_text is None:
            first_text, first_url = text, url
        pos = text.find(marker)
        if pos == -1:
            continue
        # Slice from our problem's heading to the next problem's heading.
        nxt = re.search(rf"\n{contest_id}[A-Z]\d? - ", text[pos + len(marker):])
        end = pos + len(marker) + nxt.start() if nxt else len(text)
        return text[pos:end][:_EDITORIAL_MAX_CHARS], url

    if first_text is None:
        raise NoEditorial(f"Could not fetch any editorial blog for contest {contest_id}")
    # Couldn't locate the problem's section — hand over the whole blog and
    # let the model find it.
    return first_text[:_EDITORIAL_MAX_CHARS], first_url


def _get_blog_text(url):
    response = _scraper.get(url)
    if response.status_code != 200:
        return None
    soup = BeautifulSoup(response.text, 'html.parser')
    content = soup.find('div', class_='content')
    if content is None:
        return None
    return content.get_text('\n')


def get_input_spec_paragraphs(statement_html):
    """The Input section's paragraphs as plain text, in order, or None.

    Paragraph boundaries matter: the line map links each sample-input line
    to one of these paragraphs by its 1-based position, and the frontend
    resolves the same position against the rendered DOM — so both sides
    must count direct <p> children of .input-specification and nothing else.
    """
    soup = BeautifulSoup(statement_html, 'html.parser')
    spec = soup.find('div', class_='input-specification')
    if spec is None:
        return None
    paras = [html_to_text(str(p)) for p in spec.find_all('p', recursive=False)]
    return paras if any(paras) else None


def get_sample_input_lines(statement_html):
    """Lines of the first sample input block, or None.

    Handles both statement styles: modern per-line <div>s inside the <pre>
    and older raw text with newlines. The frontend splits lines the same
    way (trailing blanks dropped, interior blanks kept) so 1-based line
    numbers agree between the prompt and the DOM.
    """
    soup = BeautifulSoup(statement_html, 'html.parser')
    sample = soup.find('div', class_='sample-test')
    pre = sample.find('div', class_='input') if sample else None
    pre = pre.find('pre') if pre else None
    if pre is None:
        return None
    line_divs = pre.find_all('div', recursive=False)
    if line_divs:
        lines = [d.get_text().rstrip() for d in line_divs]
    else:
        for br in pre.find_all('br'):
            br.replace_with('\n')
        lines = [ln.rstrip() for ln in pre.get_text().split('\n')]
    while lines and not lines[-1]:
        lines.pop()
    return lines or None


def html_to_text(statement_html):
    """Flatten statement HTML to plain text for an LLM prompt.

    TeX stays in its $$$...$$$ delimiters; sample-test structure survives
    as line breaks, which is all the model needs.
    """
    soup = BeautifulSoup(statement_html, 'html.parser')
    for br in soup.find_all('br'):
        br.replace_with('\n')
    for block in soup.find_all(['div', 'p', 'li', 'tr']):
        block.append('\n')
    lines = [ln.strip() for ln in soup.get_text().split('\n')]
    out = []
    for ln in lines:
        if ln:
            out.append(ln)
        elif out and out[-1]:
            out.append('')
    return '\n'.join(out).strip()
