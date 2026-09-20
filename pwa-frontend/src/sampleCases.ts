function caseNumber(row: Element): number | null {
  const marker = Array.from(row.classList).find(name => /^test-example-line-\d+$/.test(name));
  return marker ? Number(marker.slice('test-example-line-'.length)) : null;
}

function rowsOf(pre: Element): HTMLElement[] {
  return Array.from(pre.children).filter((child): child is HTMLElement => child.tagName === 'DIV');
}

/** Link CF's explicit input case groups to the adjacent sample output.
 * Numbered output groups support multiline answers; otherwise one output
 * line per case is usable only when the counts agree. Unmarked inputs and
 * ambiguous outputs stay untouched rather than acquiring guessed matches. */
export function attachSampleCaseHighlight(root: HTMLElement): () => void {
  const counterparts = new Map<HTMLElement, HTMLElement[]>();
  root.querySelectorAll('.sample-test .input').forEach(input => {
    const output = input.nextElementSibling;
    const inputPre = input.querySelector(':scope > pre');
    const outputPre = output?.matches('.output') ? output.querySelector(':scope > pre') : null;
    if (!inputPre || !outputPre) return;

    const inputRows = rowsOf(inputPre);
    const caseIds = [...new Set(inputRows.map(caseNumber).filter((id): id is number => id !== null && id > 0))]
      .sort((a, b) => a - b);
    if (!caseIds.length || caseIds.some((id, i) => id !== i + 1)) return;

    let outputRows = rowsOf(outputPre);
    const byCase = new Map<number, HTMLElement[]>();
    if (outputRows.some(row => caseNumber(row) !== null)) {
      for (const row of outputRows) {
        const id = caseNumber(row);
        if (id === 0) continue;
        if (id === null || !caseIds.includes(id)) return;
        byCase.set(id, [...(byCase.get(id) ?? []), row]);
      }
      if (byCase.size !== caseIds.length) return;
    } else {
      const lines = outputRows.length
        ? outputRows.map(row => row.textContent ?? '')
        : (outputPre.textContent ?? '').split('\n');
      // A terminating newline ends the last row; it isn't another answer.
      if (!outputRows.length && lines.at(-1) === '') lines.pop();
      if (lines.length !== caseIds.length) return;
      if (!outputRows.length) {
        outputRows = lines.map(line => {
          const row = document.createElement('div');
          row.className = 'cf-sample-output-line';
          row.textContent = line;
          return row;
        });
        outputPre.replaceChildren(...outputRows);
      }
      caseIds.forEach((id, i) => byCase.set(id, [outputRows[i]]));
    }
    for (const row of inputRows) {
      const outputs = byCase.get(caseNumber(row) ?? 0);
      if (outputs) counterparts.set(row, outputs);
    }
  });

  let active: HTMLElement[] = [];
  let pinned: HTMLElement | null = null;
  const clear = () => {
    active.forEach(row => row.classList.remove('cf-case-active'));
    active = [];
  };
  const rowAt = (target: EventTarget | null) => {
    const row = target instanceof Element
      ? target.closest<HTMLElement>('.sample-test .input > pre > div') : null;
    return row && counterparts.has(row) ? row : null;
  };
  const show = (row: HTMLElement | null) => {
    clear();
    if (!row) return;
    active = [row, ...counterparts.get(row)!];
    active.forEach(line => line.classList.add('cf-case-active'));
  };
  const onOver = (event: MouseEvent) => {
    if (!pinned) show(rowAt(event.target));
  };
  const onLeave = () => { if (!pinned) clear(); };
  const onClick = (event: MouseEvent) => {
    if (event.target instanceof Element && event.target.closest('.cf-copy')) return;
    const row = rowAt(event.target);
    // Tap to keep the answer lit while scrolling on a phone; tap again to clear.
    pinned = row === pinned ? null : row;
    show(pinned);
  };
  root.addEventListener('mouseover', onOver);
  root.addEventListener('mouseleave', onLeave);
  root.addEventListener('click', onClick);
  return () => {
    root.removeEventListener('mouseover', onOver);
    root.removeEventListener('mouseleave', onLeave);
    root.removeEventListener('click', onClick);
    clear();
  };
}
