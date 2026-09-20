import { test, expect, type Page } from '@playwright/test';
import { createHash } from 'node:crypto';
import { createDemoApi } from '../dev/demo-api';

test.beforeEach(async ({ page }, testInfo) => {
  const api = createDemoApi();
  await page.route('**/api/**', route => {
    const result = api(new URL(route.request().url()).pathname, route.request().method());
    return route.fulfill({ status: result.status, json: result.body });
  });
  // Layout fixtures have no math. Keep these checks independent of the CDN.
  await page.route('https://cdn.jsdelivr.net/**', route => route.fulfill({ body: '', contentType: 'text/javascript' }));
  await page.addInitScript((insets: Record<string, number>) => {
    localStorage.setItem('theme', 'dark');
    document.addEventListener('DOMContentLoaded', () => {
      for (const [edge, value] of Object.entries(insets)) {
        document.documentElement.style.setProperty(`--safe-area-${edge}`, `${value}px`);
      }
    });
  }, testInfo.project.metadata.insets ?? {});
  await page.goto('/');
});

async function fitsViewport(page: Page) {
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBe(true);
}

test('navigation and settings remain reachable inside the safe areas', async ({ page }, testInfo) => {
  await expect(page.getByRole('heading', { name: 'CF Picker' })).toBeVisible();
  await page.getByRole('button', { name: 'Increase level' }).click();
  await expect(page.getByRole('combobox', { name: 'Level' })).toHaveValue('16');
  const insets = testInfo.project.metadata.insets ?? { top: 0, right: 0, bottom: 0, left: 0 };
  const nav = page.getByRole('navigation', { name: 'Main navigation' });
  for (const button of await nav.getByRole('button').all()) {
    const box = await button.boundingBox();
    expect(box).not.toBeNull();
    expect(box!.x).toBeGreaterThanOrEqual(insets.left);
    expect(box!.x + box!.width).toBeLessThanOrEqual(page.viewportSize()!.width - insets.right);
    expect(box!.y + box!.height).toBeLessThanOrEqual(page.viewportSize()!.height - insets.bottom + 1);
    expect(box!.height).toBeGreaterThanOrEqual(44);
  }
  const settings = page.getByRole('button', { name: 'Settings', exact: true });
  expect((await settings.boundingBox())!.y).toBeGreaterThanOrEqual(insets.top);
  await settings.click();
  const sheet = page.getByRole('dialog', { name: 'Settings' });
  await expect(sheet).toBeVisible();
  await sheet.getByRole('button', { name: 'Cozy', exact: true }).click();
  await expect(page.locator('html')).toHaveAttribute('data-width', 'cozy');
  await page.getByRole('button', { name: 'Close settings' }).click();
  await fitsViewport(page);
  await testInfo.attach('home', { body: await page.screenshot({ scale: 'css' }), contentType: 'image/png' });
});

test('problem reading, tables, and settings fit at every text width', async ({ page }, testInfo) => {
  await page.getByRole('button', { name: 'Pick a problem' }).click();
  await expect(page.locator('.problem-statement .header .title')).toHaveText('A Walk Through the Array');
  for (const width of ['Cozy', 'Wide', 'Max']) {
    await page.getByRole('button', { name: 'Settings', exact: true }).click();
    await page.getByRole('dialog').getByRole('button', { name: width, exact: true }).click();
    await page.getByRole('button', { name: 'Close settings' }).click();
    await fitsViewport(page);
  }
  const table = page.getByRole('region', { name: 'Example moves' });
  await expect(table).toBeVisible();
  const tableSize = await table.evaluate(el => ({ content: el.scrollWidth, box: el.clientWidth }));
  if (page.viewportSize()!.width < 512) expect(tableSize.content).toBeGreaterThan(tableSize.box);
  await page.evaluate(() => window.scrollTo(0, document.documentElement.scrollHeight));
  const end = await page.getByText('End of sample statement.', { exact: true }).boundingBox();
  const nav = await page.getByRole('navigation').boundingBox();
  expect(end!.y + end!.height).toBeLessThan(nav!.y);
  await page.getByRole('button', { name: 'Settings', exact: true }).click();
  await testInfo.attach('settings', { body: await page.screenshot({ scale: 'css' }), contentType: 'image/png' });
  await page.getByRole('button', { name: 'Close settings' }).click();
  // dark → auto (dark OS) → light
  await page.getByRole('button', { name: 'Theme: dark' }).click();
  await page.getByRole('button', { name: 'Theme: auto' }).click();
  await expect(page.locator('html')).not.toHaveClass(/dark/);
  await fitsViewport(page);
  await testInfo.attach('problem-light', { body: await page.screenshot({ fullPage: true, scale: 'css' }), contentType: 'image/png' });
});

test('a ranked match survives tab switches and can be reviewed', async ({ page }, testInfo) => {
  await page.getByRole('button', { name: 'Ranked', exact: true }).click();
  await expect(page.getByLabel('Your ranked rank').getByRole('heading')).toBeVisible();
  await page.getByRole('button', { name: 'Queue Up · 25:00', exact: true }).click();
  await expect(page.getByText('Ranked match', { exact: true })).toBeVisible();
  await expect(page.getByLabel('Your ranked rank')).toHaveCount(0);
  await expect(page.getByLabel('League of Legends equivalent')).toHaveCount(0);
  if (page.viewportSize()!.width < 900) {
    await page.evaluate(() => window.scrollTo(0, document.documentElement.scrollHeight));
    await expect(page.getByText('Ranked match', { exact: true })).not.toBeInViewport();
    await expect(page.getByRole('button', { name: 'FF', exact: true })).not.toBeInViewport();
    await page.evaluate(() => window.scrollTo(0, 0));
  }
  await fitsViewport(page);
  await page.getByRole('button', { name: 'Rating', exact: true }).click();
  await expect(page.getByText('Sample Round (Div. 2)', { exact: true })).toBeVisible();
  await fitsViewport(page);
  await testInfo.attach('rating', { body: await page.screenshot({ fullPage: true, scale: 'css' }), contentType: 'image/png' });
  await page.getByRole('button', { name: 'Ranked', exact: true }).click();
  await expect(page.getByText('Ranked match', { exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'FF', exact: true }).click();
  await page.getByRole('button', { name: 'Sure?', exact: true }).click();
  await expect(page.getByText('SURRENDERED', { exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Continue', exact: true }).click();
  await page.getByRole('button', { name: /900001C · A Walk Through the Array/ }).first().click();
  await expect(page.getByText('Approach', { exact: true })).toBeVisible();
  await expect(page.getByLabel('Your ranked rank')).toHaveCount(0);
  await expect(page.getByLabel('League of Legends equivalent')).toHaveCount(0);
  if (page.viewportSize()!.width < 900) {
    await page.evaluate(() => window.scrollTo(0, document.documentElement.scrollHeight));
    await expect(page.getByRole('button', { name: 'Back', exact: true })).not.toBeInViewport();
  }
  await fitsViewport(page);
});

test('a failed problem request can be retried', async ({ page }) => {
  await page.route('**/api/pick?**', route => route.fulfill({ status: 503, json: { detail: 'Temporarily offline. Try again.' } }));
  await page.reload();
  await page.getByRole('button', { name: 'Pick a problem' }).click();
  await expect(page.getByText('Temporarily offline. Try again.')).toBeVisible();
  await page.unroute('**/api/pick?**');
  await page.getByRole('button', { name: 'Try Again', exact: true }).click();
  await expect(page.locator('.problem-statement .header .title')).toHaveText('A Walk Through the Array');
});

const sampleFormats = {
  span: '<span>\n2\n  1  2  \n\n4\n</span>',
  br: '<span></span><br>2<br>  1  2  <br><br>4<br>',
  div: '<span></span>\n<div></div><div>2</div><div>  1  2  </div><div></div><div>4</div>',
};

for (const [format, input] of Object.entries(sampleFormats)) {
  test(`${format} samples omit leading blank lines and retain annotation alignment`, async ({ page }) => {
    const html = `<div class="problem-statement">
      <div class="header"><div class="title">A. Sample whitespace</div></div>
      <div class="input-specification"><p>Read the two values.</p></div>
      <div class="sample-test">
        <div class="input"><div class="title">Input</div><pre>${input}</pre></div>
        <div class="output"><div class="title">Output</div><pre><span>\n \t\n  3\n\n4  \n</span></pre></div>
      </div></div>`;
    await page.route('**/api/pick?**', route => route.fulfill({ json: {
      problem: { contestId: 900002, index: 'A', name: 'Sample whitespace' }, html,
    } }));
    let releaseMap!: () => void;
    const mapReady = new Promise<void>(resolve => { releaseMap = resolve; });
    await page.route('**/api/linemap?**', async route => {
      await mapReady;
      await route.fulfill({ json: { linemap: { status: 'done', data: {
        v: 3, statement_hash: createHash('sha256').update(html).digest('hex'), para_count: 1,
        lines: [{ line: 3, para: 1, clause: 0, clause_text: '', kind: 'scalars',
          vars: [{ tex: 'n', text: 'first value' }, { tex: 'm', text: 'second value' }], text: 'The two values' }],
      } } } });
    });
    // The picker prefetches on startup; reload with these fixtures installed.
    await page.reload();
    // Capture copies without depending on platform clipboard permissions.
    await page.evaluate(() => {
      let copied = '';
      Object.defineProperty(navigator, 'clipboard', { configurable: true, value: {
        writeText: async (text: string) => { copied = text; },
        readText: async () => copied,
      } });
    });
    await page.getByRole('button', { name: 'Pick a problem' }).click();
    const samples = page.locator('.sample-test pre');
    await expect(samples).toHaveCount(2);
    const startsOnFirstLine = async () => {
      for (const pre of await samples.all()) {
        expect(await pre.evaluate(el => {
          const walker = document.createTreeWalker(el, NodeFilter.SHOW_TEXT);
          while (walker.nextNode()) {
            const node = walker.currentNode;
            const first = (node.textContent ?? '').search(/\S/);
            if (first < 0) continue;
            const range = document.createRange();
            range.setStart(node, first);
            range.setEnd(node, first + 1);
            const style = getComputedStyle(el);
            const offset = range.getBoundingClientRect().top - el.getBoundingClientRect().top - parseFloat(style.paddingTop);
            return offset >= 0 && offset < parseFloat(style.lineHeight);
          }
          return false;
        })).toBe(true);
      }
    };
    await startsOnFirstLine();
    await expect(samples.nth(1)).toHaveJSProperty('textContent', '  3\n\n4  \n');
    releaseMap();
    const token = page.locator('.cf-tok[data-tex-base="n"]');
    await expect(token).toHaveText('1');
    await expect(page.locator('.cf-tok[data-tex-base="m"]')).toHaveText('2');
    await startsOnFirstLine();
    await token.click();
    await expect(page.locator('.input-specification .cf-hot')).toHaveText('Read the two values.');
    await page.getByRole('button', { name: 'Copy sample input' }).click();
    expect(await page.evaluate(() => navigator.clipboard.readText())).toBe('2\n  1  2  \n\n4\n');
    await page.getByRole('button', { name: 'Problem', exact: true }).click();
    const markdown = await page.evaluate(() => navigator.clipboard.readText());
    expect(markdown).toContain('```\n2\n  1  2  \n');
    expect(markdown).toContain('```\n  3\n\n4  \n```');
  });
}

test('test-case hover highlights its answer without coloring whole sample blocks', async ({ page }, testInfo) => {
  const input = '<div class="test-example-line-0">2</div>'
    + '<div class="test-example-line-1">2</div><div class="test-example-line-1">1 2</div>'
    + '<div class="test-example-line-2">1</div><div class="test-example-line-2">4</div>';
  const pair = (output: string) => `<div class="input"><div class="title">Input</div><pre><span></span>\n${input}</pre></div>`
    + `<div class="output"><div class="title">Output</div><pre><span></span>\n${output}</pre></div>`;
  const html = `<div class="problem-statement">
    <div class="header"><div class="title">A. Sample cases</div></div>
    <div class="input-specification"><p>Read the array values.</p></div>
    <div class="sample-test">${pair('3\n4\n')}
      ${pair('<div class="test-example-line-1">YES</div><div class="test-example-line-1">1 2</div><div class="test-example-line-2">NO</div>')}
      ${pair('YES\n1 2\nNO\n')}
    </div></div>`;
  await page.route('**/api/pick?**', route => route.fulfill({ json: {
    problem: { contestId: 900003, index: 'A', name: 'Sample cases' }, html,
  } }));
  await page.route('**/api/linemap?**', route => route.fulfill({ json: { linemap: { status: 'done', data: {
    v: 3, statement_hash: createHash('sha256').update(html).digest('hex'), para_count: 1,
    lines: [{ line: 3, para: 1, clause: 0, clause_text: '', kind: 'array',
      vars: [{ tex: 'a', text: 'array value' }], text: 'Array values' }],
  } } } }));
  await page.reload();
  await page.getByRole('button', { name: 'Pick a problem' }).click();
  const inputs = page.locator('.sample-test .input pre');
  const outputs = page.locator('.sample-test .output pre');
  const tokens = inputs.nth(0).locator('.cf-tok');
  await expect(tokens).toHaveCount(2);
  const firstRows = inputs.nth(0).locator(':scope > div');
  const activeAnswers = page.locator('.sample-test .output .cf-case-active');
  const blockStyles = () => page.locator('.sample-test pre').evaluateAll(blocks => blocks.map(block => {
    const style = getComputedStyle(block);
    return { background: style.backgroundColor, outline: style.outlineStyle };
  }));

  for (const theme of ['dark', 'light']) {
    if (theme === 'light') {
      await page.getByRole('button', { name: 'Theme: dark' }).click();
      await page.getByRole('button', { name: 'Theme: auto' }).click();
    }
    const backgrounds = await blockStyles();
    await firstRows.nth(1).hover();
    await expect(activeAnswers).toHaveText(['3']);
    await tokens.first().hover();
    await expect(activeAnswers).toHaveText(['3']);
    await expect(page.locator('.input-specification .cf-hot')).toHaveText('Read the array values.');
    await expect(page.locator('.sample-test .input .cf-case-active')).toHaveCount(1);
    await expect(activeAnswers).not.toHaveCSS('background-color', 'rgba(0, 0, 0, 0)');
    expect(await blockStyles()).toEqual(backgrounds);
    await firstRows.nth(4).hover();
    await expect(activeAnswers).toHaveText(['4']);
    await firstRows.nth(0).hover(); // The test count has no corresponding answer.
    await expect(activeAnswers).toHaveCount(0);

    await inputs.nth(1).locator('.test-example-line-1').last().hover();
    await expect(activeAnswers).toHaveText(['YES', '1 2']);
    await inputs.nth(1).locator('.test-example-line-2').last().hover();
    await expect(activeAnswers).toHaveText(['NO']);
    await inputs.nth(2).locator('.test-example-line-1').last().hover();
    await expect(activeAnswers).toHaveCount(0); // No guessed split of variable-length output.
    await expect(outputs.nth(2)).toHaveJSProperty('textContent', 'YES\n1 2\nNO\n');

    await firstRows.nth(1).hover();
    await page.mouse.move(0, 0);
    await expect(activeAnswers).toHaveCount(0);
    const pin = () => testInfo.project.use.hasTouch ? firstRows.nth(1).tap() : firstRows.nth(1).click();
    await pin();
    await page.mouse.move(0, 0);
    await expect(activeAnswers).toHaveText(['3']);
    await pin();
    await expect(activeAnswers).toHaveCount(0);
  }
});
