"""Check rank display with isolated API fixtures; never changes live matches.

Build and serve the frontend, then run:
  PYTHONPATH=src .venv/bin/python tests/browser_ranked_rank.py
"""

import argparse
import asyncio
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

from playwright.async_api import async_playwright, expect

from cfscripts.core.statements import render_statement
from test_ranked_queue import PAYLOAD, PROBLEM


async def exercise(browser, url, width):
    context = await browser.new_context(viewport={'width': width, 'height': 900},
                                        has_touch=width < 600, service_workers='block')
    page = await context.new_page()
    clock_start = datetime(2026, 9, 8, tzinfo=timezone.utc)
    await page.clock.install(time=clock_start)
    html = render_statement(PAYLOAD, 2049, 'C')
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)))
    state = {'elo': 1337, 'seeded': False, 'wins': 3, 'losses': 2,
             'server_now': int(clock_start.timestamp()), 'active': None, 'history': []}

    def finish(result, elo):
        state['history'].insert(0, {**state['active'], 'result': result,
                                   'elo_before': state['elo'], 'elo_after': elo,
                                   'problem_rating': 1300, 'solved_ts': state['server_now']})
        state.update(elo=elo, active=None)
        state['wins' if result == 'win' else 'losses'] += 1

    async def api(route):
        path = urlparse(route.request.url).path
        if path == '/api/ranked/state':
            body = state
        elif path == '/api/pick':
            body = {'problem': PROBLEM, 'html': html}
        elif path == '/api/participations':
            body = {'participations': [], 'official_rating': 1337}
        elif path == '/api/ranked/queue':
            state['active'] = {'id': len(state['history']) + 17, 'contest_id': 2049,
                               'problem_index': 'C', 'problem_name': 'Test Problem',
                               'start_ts': state['server_now'], 'deadline_ts': state['server_now'] + 1800}
            body = {**state, 'html': html}
        elif path == '/api/ranked/problem':
            body = {'match_id': state['active']['id'], 'html': html}
        elif path == '/api/ranked/surrender':
            finish('surrender', 1345)
            body = state
        elif path == '/api/ranked/review':
            body = {'match': state['history'][0], 'html': html, 'solution': None}
        elif path == '/api/linemap':
            body = {'linemap': None}
        else:
            raise AssertionError(f'Unexpected API request: {path}')
        await route.fulfill(json=body)

    await page.route('**/api/**', api)
    await page.goto(url, wait_until='domcontentloaded')
    await page.get_by_role('button', name='Ranked', exact=True).click()
    rank = page.locator('[aria-label="Your ranked rank"]:visible')
    await expect(rank.get_by_role('heading')).to_have_text('Pupil II')
    await expect(rank.get_by_role('progressbar')).to_have_attribute('aria-valuenow', '69')
    await expect(rank.get_by_text('13 Elo to Pupil I · 1350 Elo', exact=True)).to_be_visible()
    await expect(rank.get_by_text('1300–1349 Elo in this subdivision', exact=True)).to_be_visible()
    equivalent = rank.locator('[aria-label="League of Legends equivalent"]')
    await expect(equivalent).to_contain_text('≈ Platinum III in League')
    await expect(equivalent).to_contain_text('CF top 22.6% · NA Solo/Duo')
    for theme in ['dark', 'light']:
        await page.get_by_text('Rank ladder', exact=True).click()
        await expect(rank.locator('dt')).to_have_count(10)
        await expect(rank.get_by_role('link', name='League data', exact=True)).to_have_attribute('href', 'https://op.gg/lol/statistics/tiers?region=na')
        await expect(rank.locator('time')).to_have_attribute('datetime', '2026-09-08')
        for group in await rank.locator('dl > div').all():
            details = group.locator('details')
            if await details.get_attribute('open') is None:
                await group.get_by_text('IV–I subdivisions', exact=True).click()
            await expect(group.locator('li')).to_have_count(4)
            for subdivision in await group.locator('li').all():
                await expect(subdivision).to_be_visible()
                await expect(subdivision).to_contain_text('League ≈')
        await expect(rank.locator('li[aria-current="step"]')).to_contain_text('League ≈ Platinum III → Platinum II')
        assert await page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
        await page.get_by_text('Rank ladder', exact=True).click()
        await page.screenshot(path=f'/tmp/cfscripts-ranked-rank-{width}-{theme}.png', full_page=True)
        if theme == 'dark':
            await page.get_by_role('button', name='Theme: dark', exact=True).click()

    await page.get_by_role('button', name='Queue Up · 30:00', exact=True).click()
    await expect(rank).to_have_count(0)
    await expect(page.locator('[aria-label="League of Legends equivalent"]:visible')).to_have_count(0)
    await expect(page.get_by_text('30:00', exact=True)).to_be_visible()
    assert await page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
    # A real polling transition must update both the rank and result banner.
    state['server_now'] += 60
    finish('win', 1353)
    await page.clock.fast_forward(60_000)
    await expect(rank.get_by_role('heading')).to_have_text('Pupil I')
    await expect(equivalent).to_contain_text('≈ Platinum II in League')
    await expect(page.locator('[aria-label="Rank after match"]')).to_have_text('Pupil II → Pupil I')
    await page.get_by_role('button', name='Continue', exact=True).click()
    await page.get_by_role('button', name='Queue Up · 30:00', exact=True).click()
    await expect(rank).to_have_count(0)
    await page.get_by_role('button', name='FF', exact=True).click()
    await page.get_by_role('button', name='Sure?', exact=True).click()
    await expect(rank.get_by_role('heading')).to_have_text('Pupil II')
    await expect(page.locator('[aria-label="Rank after match"]')).to_have_text('Pupil I → Pupil II')
    await page.get_by_role('button', name='Continue', exact=True).click()
    await page.get_by_role('button', name=re.compile('2049C · Test Problem')).first.click()
    await expect(rank).to_have_count(0)
    await expect(page.locator('[aria-label="League of Legends equivalent"]:visible')).to_have_count(0)

    # Long names must fit on phones; the open-ended top rank has no false
    # promotion target, and rounded ratings must agree with their title.
    for elo, label in [(1399.5, 'Specialist IV'),
                       (2999, 'International Grandmaster I'), (4200, 'Legendary Grandmaster I')]:
        state.update(elo=elo, history=[])
        await page.reload(wait_until='domcontentloaded')
        await page.get_by_role('button', name='Ranked', exact=True).click()
        await expect(rank.get_by_role('heading')).to_have_text(label)
        assert await page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1'), label
        if elo == 4200:
            await expect(rank.get_by_text('Highest subdivision reached', exact=True)).to_be_visible()
            await expect(rank.get_by_role('progressbar')).to_have_attribute('aria-valuenow', '100')
            await expect(equivalent).to_contain_text('≈ Challenger in League')
            await expect(equivalent).to_contain_text('CF top <0.003%')
        await page.get_by_role('button', name='Queue Up · 30:00', exact=True).click()
        await expect(rank).to_have_count(0)
        assert await page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1'), label
        state['active'] = None

    assert not errors, errors
    print(json.dumps({'width': width, 'rank_progress': True, 'promotion_demotion': True,
                      'live_and_review': True, 'long_names': True, 'league_equivalents': 40, 'passed': True}), flush=True)
    await context.close()


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--url', default='http://127.0.0.1:4173')
    args = parser.parse_args()
    async with async_playwright() as p:
        chrome = Path('/Applications/Google Chrome.app/Contents/MacOS/Google Chrome')
        browser = await p.chromium.launch(executable_path=str(chrome) if chrome.exists() else None)
        try:
            await exercise(browser, args.url, 1280)
            await exercise(browser, args.url, 390)
            await exercise(browser, args.url, 320)
        finally:
            await browser.close()


if __name__ == '__main__':
    asyncio.run(main())
