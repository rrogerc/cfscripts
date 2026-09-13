// Full screen: 1206 × 2622 physical pixels at 3× = 402 × 874 CSS pixels.
// Insets and browser toolbar heights are layout approximations, not iOS emulation.
export const iphonePresets = {
  'pwa-portrait': {
    width: 402, height: 874,
    insets: { top: 62, right: 0, bottom: 34, left: 0 },
  },
  'pwa-landscape': {
    width: 874, height: 402,
    insets: { top: 0, right: 62, bottom: 21, left: 62 },
  },
  'browser-portrait': {
    width: 402, height: 681,
    insets: { top: 0, right: 0, bottom: 0, left: 0 },
  },
  'browser-landscape': {
    width: 756, height: 352,
    insets: { top: 0, right: 0, bottom: 0, left: 0 },
  },
} as const;

export type IphonePreset = keyof typeof iphonePresets;
