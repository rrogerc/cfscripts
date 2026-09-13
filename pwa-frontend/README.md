# CF Picker web app and PWA

One React app serves desktop browsers, mobile browsers, and installation on the
Home Screen. Native iOS app packaging is not part of this repository.

## Quick iPhone preview

```bash
cd pwa-frontend
npm ci --legacy-peer-deps
npm run dev:iphone
```

This opens [the preview](http://127.0.0.1:5174/dev/iphone.html) with interactive
sample data. Pick problems, queue/surrender sample matches, review a match,
view ratings, and change Settings. No backend or credentials are needed.
Sample matches live in this local server's memory and reset when it restarts.
Use the app's theme button to switch between dark, system, and light appearance.

The frame renders the actual app, with Vite live updates. Rotation and layout
changes keep its current screen and timer. Controls offer PWA layout, browser
content area, portrait, landscape, fit-to-window, and 100% scale. Scaling only
changes the preview's size on your monitor; it preserves the iframe's CSS viewport.

The iPhone 17 Pro's full screen is **402 × 874 CSS pixels at 3×**
([Apple's physical display specifications](https://www.apple.com/iphone-17-pro/specs/),
[Playwright device definitions](https://github.com/microsoft/playwright/blob/main/packages/playwright-core/src/server/deviceDescriptorsSource.json)).
`dev/iphone-presets.ts` defines these viewports and estimated safe areas. The PWA
portrait preset reserves 62 px above content and 34 px below it; landscape reserves
62 px at the sides and 21 px below. Browser presets model a smaller content area;
actual Safari toolbar heights vary with iOS version, settings, and scrolling.

**This is a layout preview in your current browser.** It does not emulate touch
hardware, Safari, the software keyboard, installation, or standalone browser APIs.
It does not change `navigator.standalone` or `display-mode` media queries. Use the
Simulator below for those iOS behaviors. The preview files and demo API are tooling;
they are not included in the production app bundle.

## Preview with your live local API

From the repository root, start the backend using your usual local configuration:

```bash
PYTHONPATH=src .venv/bin/python -m uvicorn cfscripts.web.server:app --reload --port 8000
```

Then, from `pwa-frontend`:

```bash
npm run dev:iphone:live
```

The normal desktop app is at `http://127.0.0.1:5173/` and its phone preview is at
`http://127.0.0.1:5173/dev/iphone.html`. Both use the same app and local storage.
Vite proxies `/api` to `127.0.0.1:8000`. Live mode uses your account; queue and
surrender have their usual effects. Demo mode uses port 5174, keeping its browser
storage separate from live development on 5173.

## iOS Simulator on a Mac

Install Xcode and an iOS 26+ Simulator runtime once. In Xcode, use Settings →
Components, or run `xcodebuild -downloadPlatform iOS` (a multi-GB download).
See [Apple's runtime installation guide](https://developer.apple.com/documentation/xcode/downloading-and-installing-additional-xcode-components).

```bash
npm run ios
```

The launcher reuses or creates an iPhone 17 Pro in the newest installed compatible
iOS runtime, boots it, and opens the sample app in Safari. It starts the local
sample server on port 5174 if needed. Leave that terminal running while using it.
You can also pass an existing app URL, such as `npm run ios -- http://127.0.0.1:5173/`.
The simulated phone can reach the Mac's loopback address.

### Test the installed PWA

Vite development mode deliberately does not register a service worker. Use the
production build when checking installation, offline reload, or service-worker
updates. In one terminal:

```bash
npm run preview:pwa
```

In another:

```bash
npm run ios -- http://127.0.0.1:4173/
```

In Simulator Safari, choose **Share → Add to Home Screen**, leave **Open as Web App**
enabled if shown, then launch **CF Picker** from the Home Screen. This exercises
the iOS standalone container, safe areas, native selectors, and app switching.
Localhost is a secure context for service workers; a deployed app needs HTTPS.
`preview:pwa` serves sample API data alongside the normal production build. To use
the live local backend instead, build with `npm run build` and run `npm run preview`.

For release checks, rotate the installed app, open Settings, use the difficulty
selector, scroll a long statement, and background/resume a timer. Rebuild while
it is installed to check service-worker updates. The app shell can reopen offline;
fetching new problems, ratings, ranked state, and uncached MathJax still needs a
network connection. Simulator timing, storage pressure, push delivery, and touch
feel cannot guarantee behavior on physical hardware. Keep an occasional real-phone
check before releases.

## Automated desktop and iPhone checks

Install the test browsers once (and again after upgrading Playwright):

```bash
npm run test:e2e:install
npm run test:e2e
```

The test command builds the app and starts isolated servers automatically. It
uses sample API fixtures; no backend credentials or live account writes occur.
Tests cover desktop Chromium and WebKit, iPhone 17 Pro browser/PWA layout in both
orientations, safe-area spacing, navigation, all text widths, table overflow,
light/dark appearance, ranked queue/review, request retry, install assets, and
offline app-shell reload. PWA layout tests inject estimated CSS safe areas;
service-worker behavior is tested separately in Chromium.

[Playwright WebKit](https://playwright.dev/docs/browsers#webkit) is a patched WebKit
build, not shipping Safari or iOS Simulator. It catches engine-specific problems
but does not replace the installed-iOS check.

```bash
npm run test:iphone       # Only the iPhone WebKit projects
npm run test:e2e:ui       # Interactive test runner
npx playwright show-report
```

The report includes screenshots of home, settings, problem, rating, and the phone
preview. Failures also retain traces for inspection. Screenshots are review
artifacts, not pixel-diff baselines. For UI changes, run the browser checks and
inspect the relevant screenshot or use the live preview. Extend these tests when
adding a new screen or interaction. GitHub Actions runs lint and the browser suite
for frontend pushes and pull requests and saves the report as an artifact.

## Icons

`public/favicon.svg` is the source for the app's book icon. After editing it, run
`npm run icons` to regenerate the committed 180, 192, and 512 px PNGs. This needs
Playwright Chromium installed. Normal builds use the committed icons.

## Dependency installation

Use `npm ci --legacy-peer-deps`, matching deployment. The current
`vite-plugin-pwa@1.2.0` peer range stops at Vite 7 while this app uses Vite 8.
The production PWA build is covered by the browser tests above.
