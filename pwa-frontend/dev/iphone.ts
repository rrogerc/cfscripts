import { iphonePresets, type IphonePreset } from './iphone-presets';

const frame = document.querySelector<HTMLIFrameElement>('#app')!;
const phone = document.querySelector<HTMLElement>('#phone')!;
const space = document.querySelector<HTMLElement>('#phone-space')!;
const stage = document.querySelector<HTMLElement>('#stage')!;
const mode = document.querySelector<HTMLSelectElement>('#mode')!;
const orientation = document.querySelector<HTMLSelectElement>('#orientation')!;
const scaleControl = document.querySelector<HTMLSelectElement>('#scale')!;

document.querySelector('#data-source')!.textContent = import.meta.env.MODE === 'demo'
  ? 'Sample data · Try Pick, Ranked, Rating, and Settings. Local sample matches reset when this server restarts.'
  : 'Live local API · Start the Python backend on port 8000 to use your account.';

function update() {
  const preset = iphonePresets[`${mode.value}-${orientation.value}` as IphonePreset];
  frame.style.width = `${preset.width}px`;
  frame.style.height = `${preset.height}px`;
  phone.style.width = `${preset.width + 14}px`;
  phone.style.height = `${preset.height + 14}px`;
  phone.dataset.mode = mode.value;
  phone.dataset.orientation = orientation.value;
  // Overriding CSS variables exercises the app's real safe-area spacing.
  // It does not fake matchMedia, navigator.standalone, or native iOS behavior.
  for (const [edge, value] of Object.entries(preset.insets)) {
    frame.contentDocument?.documentElement.style.setProperty(`--safe-area-${edge}`, `${value}px`);
  }
  const scale = scaleControl.value === 'fit'
    ? Math.min(1, (stage.clientWidth - 28) / (preset.width + 14), (stage.clientHeight - 28) / (preset.height + 14))
    : Number(scaleControl.value);
  phone.style.transform = `scale(${scale})`;
  space.style.width = `${(preset.width + 14) * scale}px`;
  space.style.height = `${(preset.height + 14) * scale}px`;
  document.querySelector('#dimensions')!.textContent = `${preset.width} × ${preset.height} CSS px · ${Math.round(scale * 100)}% preview scale · ${mode.value === 'pwa' ? 'estimated PWA safe areas' : 'approximate browser content area'}`;
}

frame.addEventListener('load', update);
for (const control of [mode, orientation, scaleControl]) control.addEventListener('change', update);
document.querySelector('#reload')!.addEventListener('click', () => frame.contentWindow?.location.reload());
new ResizeObserver(update).observe(stage);
update();
