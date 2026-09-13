"""Browser regression checks against a running frontend, with isolated API fixtures.

Run after building/serving the frontend:
  PYTHONPATH=src .venv/bin/python tests/browser_statement_features.py
Requires Playwright and Chromium (or the installed macOS Chrome).
"""

import argparse
import asyncio
import json
import re
from copy import deepcopy
from pathlib import Path
from urllib.parse import urlparse

from bs4 import BeautifulSoup
from markdown_it import MarkdownIt
from playwright.async_api import async_playwright, expect

from cfscripts.core.scraper import get_input_spec_paragraphs, split_clauses
from cfscripts.core.statements import extract_statement, render_statement
from cfscripts.web.statements import statement_hash
from test_ranked_queue import PAYLOAD


def fixture():
    payload = deepcopy(PAYLOAD)
    problem = payload["data"]["problem"]
    problem["content"]["description"] = (
        r"Find $a_1 + a_2$ where $a_i \le 10^9$. Read $n$ and $m$."
        "\n\n$$\\sum_{i=1}^{n} a_i$$\n\n"
        + "$" + " + ".join(f"a_{{{i}}}" for i in range(1, 50)) + "$"
        "\n\n![Diagram](https://example.com/statement-diagram.svg)"
    )
    problem["content"]["formatI"] = (
        r"Read $t$ ($1 \le t \le 100$) — the number of test cases."
        "\n\n" + r"Read $n$ and $m$ — the two values in each test case."
    )
    problem["samples"] = [["\n2\n1  2  \n", "3\n"], ["<literal>\n```\n", "&\n"]]
    html = render_statement(payload, 2049, "C")
    html = html.replace('<div class="note">', '<div class="note">'
                        '<table><tr><th colspan="2">Limits</th><th>Outcome</th></tr>'
                        '<tr><td rowspan="0">$$$a_i$$$</td><td>x | y</td><td>First</td></tr>'
                        '<tr><td>z</td><td>Second</td></tr></table>')
    paras = get_input_spec_paragraphs(html)
    lines = [
        {"line": 2, "para": 1, "clause": 2, "kind": "scalars",
         "vars": [{"tex": "t", "text": "test cases"}], "text": "Number of test cases"},
        {"line": 3, "para": 2, "clause": 2, "kind": "scalars",
         "vars": [{"tex": "n", "text": "first value"}, {"tex": "m", "text": "second value"}],
         "text": "The two values"},
    ]
    for line in lines:
        line["clause_text"] = split_clauses(paras[line["para"] - 1])[line["clause"] - 1]
    return {
        "problem": {"contestId": 2049, "index": "C", "name": "Test Problem", "rating": 1300},
        "html": html, "samples": problem["samples"],
        "map": {"v": 3, "statement_hash": statement_hash(html), "para_count": len(paras), "lines": lines},
    }


async def exercise(browser, url, width, *, delayed_math=False, stale_map=False):
    context = await browser.new_context(
        viewport={"width": width, "height": 900}, has_touch=width < 600,
        permissions=["clipboard-read", "clipboard-write"], service_workers="block",
    )
    page = await context.new_page()
    page.set_default_timeout(15000)
    await page.clock.install()
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    f = fixture()
    state = {"elo": 1300, "seeded": True, "wins": 0, "losses": 0,
             "server_now": 0, "active": None, "history": []}
    calls = {}
    failures = {"queue": False, "pick": False}

    async def api(route):
        path = urlparse(route.request.url).path
        calls[path] = calls.get(path, 0) + 1
        state["server_now"] = await page.evaluate("Math.floor(Date.now() / 1000)")
        if path == "/api/pick":
            if failures["pick"]:
                await route.fulfill(status=502, body="Upstream unavailable")
                return
            body = {"problem": f["problem"], "html": f["html"]}
        elif path == "/api/linemap":
            mapping = {**f["map"], "statement_hash": "old-statement"} if stale_map else f["map"]
            body = {"linemap": {"status": "done", "data": mapping}}
        elif path == "/api/ranked/queue":
            if failures["queue"]:
                await route.fulfill(status=502, body="Upstream unavailable")
                return
            state["active"] = {"id": 17, "contest_id": 2049, "problem_index": "C",
                               "problem_name": "Test Problem", "start_ts": state["server_now"],
                               "deadline_ts": state["server_now"] + 25 * 60}
            body = {**state, "html": f["html"]}
        elif path == "/api/ranked/problem":
            body = {"match_id": 17, "html": f["html"]}
        elif path == "/api/ranked/surrender":
            state["history"] = [{**state["active"], "problem_rating": 1300,
                                 "result": "surrender", "elo_before": 1300, "elo_after": 1284,
                                 "solved_ts": None}]
            state.update(active=None, seeded=False, losses=1, elo=1284)
            body = state
        elif path == "/api/ranked/review":
            body = {"match": state["history"][0], "html": f["html"], "solution": None}
        elif path == "/api/ranked/solution":
            body = {"solution": {"status": "done", "content_md": "Compare $$$a_i$$$ with $$$n$$$.", "model": "test"}}
        else:
            body = state
        await route.fulfill(json=body)

    await page.route("**/api/**", api)
    await page.route("**/statement-diagram.svg", lambda route: route.fulfill(
        content_type="image/svg+xml", body='<svg xmlns="http://www.w3.org/2000/svg" width="800" height="100"><circle cx="50" cy="50" r="40" fill="blue"/></svg>',
    ))
    if delayed_math:
        async def slow_math(route):
            await asyncio.sleep(3)
            await route.continue_()
        await page.route("**/mathjax@3/es5/tex-svg.js", slow_math)
    await page.goto(url, wait_until="domcontentloaded")
    await page.get_by_role("button", name="Pick a problem", exact=True).click()
    root = page.locator(".problem-statement > .problem-statement:visible")
    await expect(root.locator("mjx-container").first).to_be_visible()
    await expect(root.locator('[data-mjx-error]')).to_have_count(0)
    assert await root.locator("img").evaluate("el => el.complete && el.naturalWidth > 0")
    await expect(page.get_by_role("button", name="Copy sample input")).to_have_count(2)
    if stale_map:
        await page.wait_for_timeout(150)
        await expect(root.locator(".cf-tok")).to_have_count(0)
        assert not errors, errors
        await context.close()
        return

    await expect(root.locator('.cf-tok[data-tex-base="n"]')).to_have_count(1)
    token = root.locator('.cf-tok[data-tex-base="n"]')
    await token.click()
    await expect(token).to_have_class(re.compile("cf-focus"))
    assert await root.locator(".input-specification .cf-hot").count() > 0
    assert await root.locator(".cf-tex.cf-warm").count() > 0
    for i, sample in enumerate(f["samples"]):
        await page.get_by_role("button", name="Copy sample input").nth(i).click()
        assert await page.evaluate("navigator.clipboard.readText()") == sample[0]
    await expect(token).to_have_class(re.compile("cf-focus"))
    await token.click()
    await root.locator('.cf-tex[data-tex-base="n"]').first.hover()
    await expect(token).to_have_class(re.compile("cf-hot"))

    await page.get_by_role("button", name="Problem", exact=True).click()
    markdown = await page.evaluate("navigator.clipboard.readText()")
    assert r"$a_i \le 10^9$" in markdown, markdown
    assert r"a\_i" not in markdown
    assert "$$\n\\sum_{i=1}^{n} a_i\n$$" in markdown, markdown
    assert "1  2  \n" in markdown and "````\n<literal>\n```\n````" in markdown
    assert '| Limits | Limits | Outcome |' in markdown
    assert '| $a_i$ | x \\| y | First |' in markdown
    assert '| $a_i$ | z | Second |' in markdown
    exported_table = BeautifulSoup(MarkdownIt('commonmark').enable('table').render(markdown), 'html.parser').table
    assert [len(row.select('th, td')) for row in exported_table.select('tr')] == [3, 3, 3]
    await page.get_by_role("button", name="Coach", exact=True).click()
    coach = await page.evaluate("navigator.clipboard.readText()")
    assert markdown in coach and "Coach me" in coach
    await page.get_by_role("button", name="nvim", exact=True).click()
    command = await page.evaluate("navigator.clipboard.readText()")
    assert '[ -e "Test Problem.cpp" ] ||' in command and 'nvim "Test Problem.cpp"' in command

    for setting in ["Cozy", "Wide", "Max"]:
        await page.get_by_role("button", name="Settings", exact=True).click()
        await page.get_by_role("button", name=setting, exact=True).click()
        await page.get_by_role("button", name="Close settings", exact=True).click()
        await page.wait_for_timeout(100)
        if not await page.evaluate("document.documentElement.scrollWidth <= innerWidth + 1"):
            await page.screenshot(path="/tmp/cfscripts-statement-overflow.png", full_page=True)
            overflow = await root.evaluate("el => [...el.querySelectorAll('*')].filter(n => n.getBoundingClientRect().right > innerWidth + 1).slice(0, 8).map(n => ({tag: n.tagName, cls: n.getAttribute('class'), width: n.getBoundingClientRect().width, parent: n.parentElement?.tagName}))")
            raise AssertionError((width, setting, delayed_math, overflow))
    await page.get_by_role("button", name="Theme: dark", exact=True).click()
    await expect(page.locator("html")).not_to_have_class(re.compile("dark"))

    timer = page.get_by_role("timer", name="Time remaining")
    await page.clock.fast_forward(2000)
    await page.get_by_role("button", name="Pause timer", exact=True).click()
    paused = await timer.text_content()
    await page.clock.fast_forward(3000)
    await expect(timer).to_have_text(paused)
    await page.get_by_role("button", name="Resume timer", exact=True).click()
    await root.evaluate("el => { el.dataset.testStable = 'yes'; }")
    await page.get_by_role("button", name="Ranked", exact=True).click()
    await page.clock.fast_forward(2000)
    await page.get_by_role("button", name="Pick", exact=True).click()
    await expect(root).to_have_attribute("data-test-stable", "yes")
    await expect(timer).not_to_have_text(paused)
    await page.clock.fast_forward(25 * 60 * 1000)
    await expect(page.get_by_text("Time’s up", exact=True)).to_be_visible()
    await expect(page.get_by_role("button", name="Pause timer", exact=True)).to_be_disabled()
    await page.get_by_role("button", name="Reset timer to 25 minutes").click()
    await expect(timer).to_have_text("25:00")
    await page.get_by_role("button", name="Pick again", exact=True).click()
    await expect(root).to_have_attribute("data-test-stable", "yes")

    # A different problem must replace the typeset DOM and annotations, and
    # start a new timer; returning the same problem above must preserve them.
    original = deepcopy(f)
    f["problem"] = {**f["problem"], "contestId": 2050, "name": "Replacement Problem"}
    f["html"] = f["html"].replace("Test Problem", "Replacement Problem")
    f["map"] = {**f["map"], "statement_hash": statement_hash(f["html"])}
    async with page.expect_response("**/api/pick?**level=16"):
        await page.get_by_role("combobox", name="Level", exact=True).select_option("16")
        await page.clock.run_for(350)
    await page.get_by_role("button", name="Pick again", exact=True).click()
    await expect(root.locator(".header .title")).to_have_text("Replacement Problem")
    await expect(root.locator('.cf-tok[data-tex-base="n"]')).to_have_count(1)
    await expect(root.locator("mjx-container").first).to_be_visible()
    await expect(timer).to_have_text("25:00")
    f.update(original)

    await page.get_by_role("button", name="Ranked", exact=True).click()
    failures["queue"] = True
    await page.get_by_role("button", name="Queue Up · 25:00", exact=True).click()
    await expect(page.get_by_text("Request failed (HTTP 502). Please try again.", exact=True)).to_be_visible()
    failures["queue"] = False
    await page.clock.fast_forward(5000)
    await page.get_by_role("button", name="Queue Up · 25:00", exact=True).click()
    await expect(page.get_by_text("25:00", exact=True)).to_be_visible()
    await page.get_by_role("button", name="Problem", exact=True).click()
    assert "Rating:" not in await page.evaluate("navigator.clipboard.readText()")
    await page.evaluate("localStorage.removeItem('rankedHtml:v3:Exonerate:17')")
    await page.reload(wait_until="domcontentloaded")
    await page.get_by_role("button", name="Ranked", exact=True).click()
    await expect(root.locator(".header .title")).to_have_text("Test Problem")
    assert calls.get("/api/ranked/problem") == 1
    await page.get_by_role("button", name="FF", exact=True).click()
    await page.get_by_role("button", name="Sure?", exact=True).click()
    await page.get_by_role("button", name=re.compile("2049C · Test Problem")).click()
    await expect(root.locator(".header .title")).to_have_text("Test Problem")
    assert calls.get("/api/ranked/solution", 0) == 0
    await page.get_by_role("button", name="Reveal solution", exact=True).click()
    await expect(page.locator(".solution-content mjx-container")).to_have_count(2)
    assert not errors, errors
    await page.screenshot(path=f"/tmp/cfscripts-features-{width}-{delayed_math}.png", full_page=True)
    print(json.dumps({"width": width, "delayed_math": delayed_math, "features": "copy/math/annotations/layout/timer/queue/reopen/review", "passed": True}), flush=True)
    await context.close()


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://127.0.0.1:4173")
    args = parser.parse_args()
    async with async_playwright() as playwright:
        chrome = Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")
        browser = await playwright.chromium.launch(executable_path=str(chrome) if chrome.exists() else None)
        try:
            await exercise(browser, args.url, 1280)
            await exercise(browser, args.url, 390)
            await exercise(browser, args.url, 390, delayed_math=True)
            await exercise(browser, args.url, 390, stale_map=True)
            print("Stale annotation rejection passed", flush=True)
            await exercise_tables(browser, args.url, 1280)
            await exercise_tables(browser, args.url, 390)
        finally:
            await browser.close()


async def exercise_tables(browser, url, width):
    source = Path(__file__).with_name('fixtures').joinpath('codeforces_2109_c1.html').read_text()
    html = extract_statement(source, 2109, 'C1', 'https://codeforces.me/problemset/problem/2109/C1?locale=en')
    original = BeautifulSoup(html, 'html.parser')
    context = await browser.new_context(
        viewport={"width": width, "height": 900}, has_touch=width < 600,
        permissions=["clipboard-read", "clipboard-write"], service_workers="block",
    )
    page = await context.new_page()
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)))

    async def api(route):
        path = urlparse(route.request.url).path
        if path == '/api/pick':
            body = {'problem': {'contestId': 2109, 'index': 'C1', 'name': 'Hacking Numbers (Easy Version)'}, 'html': html}
        elif path == '/api/linemap':
            body = {'linemap': None}
        else:
            body = {'elo': 1300, 'seeded': True, 'wins': 0, 'losses': 0, 'active': None, 'history': []}
        await route.fulfill(json=body)

    await page.route('**/api/**', api)
    await page.goto(url, wait_until='domcontentloaded')
    await page.get_by_role('button', name='Pick a problem', exact=True).click()
    root = page.locator('.problem-statement > .problem-statement:visible')
    await expect(root.locator('.header .title')).to_have_text('Hacking Numbers (Easy Version)')
    await expect(root.locator('.cf-table-scroll')).to_have_count(2)
    await expect(root.locator('table').nth(0).locator('tr')).to_have_count(8)
    await expect(root.locator('table').nth(1).locator('tr')).to_have_count(11)
    await expect(root.locator('td[rowspan="2"]')).to_have_count(9)
    await expect(root.locator('table mjx-container').first).to_be_visible()
    await expect(root.locator('[data-mjx-error]')).to_have_count(0)
    assert await root.locator('table mjx-container').count() >= 50
    for theme in ['dark', 'light']:
        for setting in ['Cozy', 'Wide', 'Max']:
            await page.get_by_role('button', name='Settings', exact=True).click()
            await page.get_by_role('button', name=setting, exact=True).click()
            await page.get_by_role('button', name='Close settings', exact=True).click()
            assert await page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1'), (width, theme, setting)
        await root.locator('table').first.screenshot(path=f'/tmp/cfscripts-table-{width}-{theme}.png')
        if theme == 'dark':
            await page.get_by_role('button', name='Theme: dark', exact=True).click()
    for table in await root.locator('.cf-table-scroll').all():
        assert await table.evaluate("el => getComputedStyle(el.querySelector('td')).borderTopWidth === '1px'")
        if width < 600:
            assert await table.evaluate('el => el.scrollWidth > el.clientWidth')
            await table.focus()
            await page.keyboard.press('ArrowRight')
            await page.wait_for_timeout(200)
            assert await table.evaluate('el => el.scrollLeft > 0')
            assert await table.evaluate('el => { el.scrollLeft = el.scrollWidth; return el.scrollLeft + el.clientWidth >= el.scrollWidth - 1; }')
    await page.get_by_role('button', name='Copy sample input').click()
    sample = original.select_one('.sample-test .input pre').get_text()
    assert await page.evaluate('navigator.clipboard.readText()') == sample + ('' if sample.endswith('\n') else '\n')
    await page.get_by_role('button', name='Problem', exact=True).click()
    markdown = await page.evaluate('navigator.clipboard.readText()')
    assert "| Command | Constraint | Result | Case | Update | Jury's response |" in markdown, markdown
    assert '| Solution | Jury | Explanation |' in markdown, markdown
    exported = BeautifulSoup(MarkdownIt('commonmark').enable('table').render(markdown), 'html.parser')
    assert [len(table.select('tr')) for table in exported.select('table')] == [8, 11]
    command_rows = exported.select('table')[0].select('tbody tr')
    for i in range(0, 6, 2):
        assert command_rows[i].td.get_text() == command_rows[i + 1].td.get_text()
        assert len(command_rows[i + 1].select('td')) == 6
    assert r'$-10^{18} \le y \le 10^{18}$' in markdown
    await page.get_by_role('button', name='Coach', exact=True).click()
    assert markdown in await page.evaluate('navigator.clipboard.readText()')
    assert not errors, errors
    print(json.dumps({'width': width, 'tables': 2, 'merged_cells': 9, 'themes': 2,
                      'copy': 'Problem/Coach/sample', 'passed': True}), flush=True)
    await context.close()


if __name__ == "__main__":
    asyncio.run(main())
