declare global {
  interface Window {
    MathJax?: {
      startup?: { promise?: Promise<unknown> };
      typesetClear?: (elements: Element[]) => void;
      typesetPromise?: (elements: Element[]) => Promise<void>;
    };
  }
}

// MathJax 3 typesetting calls must be serialized, including startup.
// https://docs.mathjax.org/en/v3.2/advanced/typeset.html
let rendering: Promise<void> = Promise.resolve();

export function typesetMath(element: HTMLElement, onDone?: () => void): () => void {
  let cancelled = false;
  const script = document.getElementById('MathJax-script');
  const schedule = () => {
    rendering = rendering.then(async () => {
      const math = window.MathJax;
      await math?.startup?.promise;
      if (cancelled || !math?.typesetPromise) return;
      math.typesetClear?.([element]);
      await math.typesetPromise([element]);
      if (!cancelled) onDone?.();
    }).catch((error: unknown) => {
      if (!cancelled) console.error('MathJax error', error);
    });
  };

  if (window.MathJax?.startup?.promise || window.MathJax?.typesetPromise) {
    schedule();
  } else {
    script?.addEventListener('load', schedule, { once: true });
  }

  return () => {
    cancelled = true;
    script?.removeEventListener('load', schedule);
    // Clear before React replaces the contents or unmounts the element.
    window.MathJax?.typesetClear?.([element]);
  };
}
