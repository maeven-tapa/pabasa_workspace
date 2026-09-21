(() => {
  'use strict';
  const payload = document.getElementById('workbook-payload');
  if (!payload) return;
  let data;
  try { data = JSON.parse(payload.textContent || '{}'); } catch (_) { return; }
  const activity = data.activity || {};
  if (activity.activity_key !== 'aral-l24-g2-v-word-reading' || data.preview) return;
  const main = document.querySelector('main');
  if (!main || document.querySelector('.prescribed-intro-overlay')) return;
  const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const overlay = document.createElement('div');
  overlay.className = 'prescribed-intro-overlay';
  overlay.setAttribute('role', 'dialog');
  overlay.setAttribute('aria-modal', 'true');
  overlay.setAttribute('aria-labelledby', 'prescribed-intro-instruction');
  overlay.innerHTML = `<div class="prescribed-intro-modal"><p class="prescribed-intro-meta">SESSION ${esc(activity.session)} · LESSON ${esc(activity.lesson)} · GAWAIN ${esc(activity.activity_number)}</p><p id="prescribed-intro-instruction" class="prescribed-intro-instruction">${esc(activity.instruction)}</p><div class="prescribed-intro-actions"><button type="button" class="prescribed-intro-start">SIMULAN</button><button type="button" class="prescribed-intro-later">MAMAYA NA LANG</button></div></div>`;
  document.body.appendChild(overlay);
  main.inert = true;
  main.setAttribute('aria-hidden', 'true');
  let audio = null, controller = null, narrated = false;
  const stop = () => { controller?.abort(); controller = null; if (audio) { audio.pause(); audio.currentTime = 0; audio = null; } };
  const csrf = () => document.querySelector('[name=csrfmiddlewaretoken]')?.value || '';
  const narrate = async () => {
    if (narrated || !data.read_aloud_url || !activity.instruction) return;
    narrated = true; controller = new AbortController();
    const form = new FormData(); form.append('target_text', activity.instruction); form.append('language', activity.language || 'Filipino'); form.append('mode', 'reading'); form.append('prescribed_activity_key', activity.activity_key);
    try { const response = await fetch(data.read_aloud_url, {method:'POST', credentials:'same-origin', headers:{'Accept':'application/json','X-CSRFToken':csrf()}, body:form, signal:controller.signal}); const result = await response.json().catch(() => ({})); if (!response.ok || !result.success || !result.audio_content) return; audio = new Audio(`data:${result.mime_type || 'audio/mpeg'};base64,${result.audio_content}`); audio.onended = () => { audio = null; }; await audio.play().catch(() => {}); } catch (_) {}
  };
  const start = () => { stop(); main.inert = false; main.removeAttribute('aria-hidden'); overlay.remove(); };
  overlay.querySelector('.prescribed-intro-start').addEventListener('click', start);
  overlay.querySelector('.prescribed-intro-later').addEventListener('click', () => { stop(); window.location.assign(data.back_url || '/dashboard/assessment/'); });
  window.addEventListener('pagehide', stop, {once:true});
  setTimeout(narrate, 0);
})();
