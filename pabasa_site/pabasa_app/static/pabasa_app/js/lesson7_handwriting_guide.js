/* Decorative guide typography only. Never reads or resizes the writing canvas. */
(() => {
  'use strict';
  const app = document.getElementById('app');
  if (!app) return;
  const rowSelector = document.currentScript?.dataset.guideRows || '.canvas-wrap';
  const letters = document.currentScript?.dataset.guideLetters || 'Ii';
  const ns = 'http://www.w3.org/2000/svg';
  const measure = document.createElement('canvas').getContext('2d');
  const observed = new Set();

  function align(wrap) {
    const model = wrap.querySelector('.model');
    if (!model || model.textContent.length !== 1 || !letters.includes(model.textContent)) return;
    const letter = model.textContent;
    // Gawain 4 declares the original font on b/i children. Once presented as
    // SVG, read that retained font from its text rather than the parent span.
    const font = getComputedStyle(model.querySelector('b, i, svg text') || model);
    // An SVG viewBox uses ink bounds, avoiding the HTML line box's extra
    // ascender/descender space. Keep the activity's existing font and weight.
    const referenceFont = `${font.fontStyle} ${font.fontWeight} 1000px ${font.fontFamily}`;
    measure.font = referenceFont;
    const ink = measure.measureText(letter);
    // Dotless i has the same stem: align its body to the middle/baseline
    // guides while letting the dot occupy the upper half of the writing row.
    const body = letter === 'i' ? measure.measureText('\u0131') : ink;
    const width = ink.actualBoundingBoxLeft + ink.actualBoundingBoxRight;
    const height = body.actualBoundingBoxAscent + ink.actualBoundingBoxDescent;
    if (!(width > 0 && height > 0)) return;

    const style = getComputedStyle(wrap);
    const positions = style.backgroundPositionY.split(',').map(parseFloat);
    const thicknesses = style.backgroundSize.split(',').map(size => parseFloat(size.trim().split(/\s+/)[1]));
    const rowHeight = parseFloat(style.height);
    // CSS percentage background positions apply to (box - stripe thickness).
    // Place ink between the inside edges of the existing, unchanged stripes.
    const topIndex = letter === letter.toLowerCase() ? 1 : 0;
    const top = (rowHeight - thicknesses[topIndex]) * positions[topIndex] / 100 + thicknesses[topIndex];
    const bottom = (rowHeight - thicknesses[2]) * positions[2] / 100;

    let svg = model.querySelector('svg');
    if (!svg) {
      svg = document.createElementNS(ns, 'svg');
      const text = document.createElementNS(ns, 'text');
      text.textContent = letter;
      text.setAttribute('x', '0');
      text.setAttribute('y', '0');
      text.setAttribute('fill', 'currentColor');
      svg.append(text);
      svg.setAttribute('aria-hidden', 'true');
      svg.setAttribute('focusable', 'false');
      model.replaceChildren(svg);
    }
    svg.setAttribute('viewBox', `${-ink.actualBoundingBoxLeft} ${-body.actualBoundingBoxAscent} ${width} ${height}`);
    svg.setAttribute('preserveAspectRatio', 'xMinYMid meet');
    svg.querySelector('text').style.font = referenceFont;
    model.style.top = `${top}px`;
    model.style.height = `${bottom - top}px`;
    model.dataset.guideAligned = '';
  }

  const resize = new ResizeObserver(entries => entries.forEach(entry => align(entry.target)));
  function sync() {
    for (const wrap of observed) {
      if (!app.contains(wrap)) { resize.unobserve(wrap); observed.delete(wrap); }
    }
    for (const wrap of app.querySelectorAll(rowSelector)) {
      if (!observed.has(wrap)) { observed.add(wrap); resize.observe(wrap); align(wrap); }
    }
  }
  new MutationObserver(sync).observe(app, {childList: true, subtree: true});
  document.fonts.ready.then(() => { sync(); observed.forEach(align); });
  document.fonts.addEventListener('loadingdone', () => observed.forEach(align));
})();
