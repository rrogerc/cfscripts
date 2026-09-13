import { execFileSync, spawn } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { createServer } from 'vite';

const root = fileURLToPath(new URL('..', import.meta.url));
const run = (command, args) => execFileSync(command, args, { encoding: 'utf8' }).trim();
const simctl = (...args) => run('xcrun', ['simctl', ...args]);
let server;

try {
  if (process.platform !== 'darwin') throw new Error('iOS Simulator requires macOS and Xcode. Use npm run dev:iphone for the browser preview.');
  const runtimes = JSON.parse(simctl('list', 'runtimes', '--json')).runtimes
    .filter(r => r.isAvailable && r.identifier.includes('.iOS-') && Number(r.version.split('.')[0]) >= 26)
    .sort((a, b) => b.version.localeCompare(a.version, undefined, { numeric: true }));
  if (!runtimes.length) throw new Error('Install an iOS 26+ runtime in Xcode → Settings → Components, or run: xcodebuild -downloadPlatform iOS');
  const deviceType = 'com.apple.CoreSimulator.SimDeviceType.iPhone-17-Pro';
  const devices = JSON.parse(simctl('list', 'devices', 'available', '--json')).devices[runtimes[0].identifier] ?? [];
  const existing = devices.find(d => d.deviceTypeIdentifier === deviceType);
  const udid = existing?.udid ?? simctl('create', 'CF Picker · iPhone 17 Pro', deviceType, runtimes[0].identifier);
  const target = new URL(process.argv[2] ?? 'http://127.0.0.1:5174/');
  if (!['http:', 'https:'].includes(target.protocol)) throw new Error('Pass an http:// or https:// app URL.');

  if (!process.argv[2]) {
    const reachable = await fetch(target, { signal: AbortSignal.timeout(1500) }).then(r => r.ok).catch(() => false);
    if (!reachable) {
      server = await createServer({ root, mode: 'demo', server: { host: '127.0.0.1', port: 5174, strictPort: true } });
      await server.listen();
      console.log('Started the app with sample data at http://127.0.0.1:5174/');
    }
  }
  if (existing?.state !== 'Booted') simctl('boot', udid);
  run('open', ['-a', 'Simulator', '--args', '-CurrentDeviceUDID', udid]);
  await new Promise((resolve, reject) => {
    const boot = spawn('xcrun', ['simctl', 'bootstatus', udid, '-b'], { stdio: 'inherit' });
    boot.on('error', reject);
    boot.on('exit', code => code === 0 ? resolve() : reject(new Error(`Simulator boot failed (${code}).`)));
  });
  simctl('openurl', udid, target.href);
  console.log(`Opened ${target.href} on iPhone 17 Pro.`);
  console.log('For an installed PWA: run npm run preview:pwa, then npm run ios -- http://127.0.0.1:4173/');
  console.log('In Simulator Safari, use Share → Add to Home Screen, then launch CF Picker from the Home Screen.');
  if (server) console.log('Leave this terminal running. Press Ctrl+C to stop the local server.');
} catch (error) {
  console.error(error instanceof Error ? error.message : error);
  await server?.close();
  process.exitCode = 1;
}
