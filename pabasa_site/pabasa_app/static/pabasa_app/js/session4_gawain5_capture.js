window.__s4g5CaptureReady = true;
(() => {
  const dataNode = document.getElementById('session4-gawain5-data');
  const app = document.getElementById('g4-app');
  if (!dataNode || !app) return;
  const data = JSON.parse(dataNode.textContent || '{}');
  const csrf = () => document.cookie.match(/(?:^|; )csrftoken=([^;]+)/)?.[1] || '';
  let canvas = null, active = null, strokes = [], busy = false;
  const draw = () => {
    const context = canvas?.getContext('2d');
    if (!context) return;
    const width = canvas.clientWidth, height = canvas.clientHeight;
    context.clearRect(0, 0, width, height);
    context.lineCap = 'round'; context.lineJoin = 'round';
    context.strokeStyle = '#6b6b6b'; context.lineWidth = 5;
    strokes.forEach(stroke => { if (stroke.length < 2) return; context.beginPath();
      stroke.forEach((p, i) => i ? context.lineTo(p.x * width, p.y * height) : context.moveTo(p.x * width, p.y * height)); context.stroke(); });
  };
  const point = event => {
    const rect = canvas.getBoundingClientRect();
    return {x: Math.max(0, Math.min(1, (event.clientX - rect.left) / rect.width)),
      y: Math.max(0, Math.min(1, (event.clientY - rect.top) / rect.height))};
  };
  const advanceInPage = nextIndex => {
    const target = data.letters?.[nextIndex];
    const targetNode = app.querySelector('.g4-instruction-target');
    if (targetNode && target !== undefined) targetNode.textContent = target;
    app.querySelectorAll('.g4-step').forEach((step, stepIndex) => {
      step.classList.toggle('active', stepIndex === nextIndex);
    });
    active = null;
    strokes = [];
    draw();
  };
  const bind = () => {
    canvas = app.querySelector('.g4-canvas');
    if (!canvas || canvas.dataset.s4capture) return;
    canvas.dataset.s4capture = '1';
    strokes = [];
    window.__s4g5CaptureBinding = true;
    canvas.addEventListener('pointerdown', event => {
      event.stopImmediatePropagation();
      if (event.pointerType === 'mouse' && event.button !== 0) return;
      active = [point(event)];
      strokes.push(active);
      draw();
    }, true);
    canvas.addEventListener('pointermove', event => {
      event.stopImmediatePropagation();
      if (active) { active.push(point(event)); draw(); }
    }, true);
    canvas.addEventListener('pointerup', event => { event.stopImmediatePropagation(); active = null; }, true);
    canvas.addEventListener('pointercancel', event => { event.stopImmediatePropagation(); active = null; }, true);
    const submit = app.querySelector('#g4-submit');
    const clear = app.querySelector('#g4-clear');
    if (clear) clear.onclick = () => {
      active = null;
      strokes = [];
      draw();
    };
    if (submit) submit.onclick = async () => {
      if (busy || active) return;
      busy = true;
      try {
        const progress = data.progress || {};
        const index = Number(progress.state?.current_item ?? progress.current_index ?? 0);
        const response = await fetch(data.progress_url, {method: 'POST', credentials: 'same-origin',
          headers: {'Content-Type': 'application/json', 'X-CSRFToken': csrf()},
          body: JSON.stringify({action: 'save_trace', item_index: index, strokes})});
        const result = await response.json().catch(() => ({}));
        if (!response.ok || !result.success) throw Error(result.error || 'Write the letter clearly three times, then try again.');
        data.progress = result.progress;
        strokes = [];
        if (Number(result.progress?.state?.current_item) >= Number(data.letters?.length || 0)) {
          await fetch(data.completion_url, {method: 'POST', credentials: 'same-origin',
            headers: {'Content-Type': 'application/json', 'X-CSRFToken': csrf()}, body: '{}'});
          location.reload();
        } else {
          advanceInPage(Number(result.progress?.state?.current_item || index + 1));
        }
      } catch (error) {
        alert(error.message);
      } finally { busy = false; }
    };
  };
  new MutationObserver(bind).observe(app, {childList: true, subtree: true});
  bind();
})();
