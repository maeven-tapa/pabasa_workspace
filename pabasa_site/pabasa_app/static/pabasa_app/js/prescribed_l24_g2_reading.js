(() => {
  'use strict';
  const data = JSON.parse(document.getElementById('workbook-payload').textContent || '{}');
  const activity = data.activity || {}, root = document.querySelector('.wb-shell');
  if (!root) return;
  const items = activity.items || [], rows = activity.rows || [], headers = activity.column_headers || [];
  let state = {...(data.state || {})}, busy = false, audio = null, stream = null, requestId = 0;
  const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const csrf = () => (document.cookie.match(/(?:^|; )csrftoken=([^;]+)/) || [])[1] || '';
  const current = () => Number(state.sequence_index ?? state.index ?? 0);
  const done = () => Array.isArray(state.completed_words) ? state.completed_words : [];
  const word = () => items[current()]?.text || '';
  const progressText = () => `Nabasa: ${done().length} / ${items.length}`;
  const column = (title, words) => `<div class="l24g2-word-column"><h2>${esc(title)}</h2><ul>${words.map(text => { const itemIndex = items.findIndex(item => item.text === text); const cls = done().includes(itemIndex) ? 'done' : itemIndex === current() ? 'current' : 'future'; return `<li class="l24g2-word ${cls}" aria-current="${itemIndex === current() ? 'true' : 'false'}">${esc(text)}</li>`; }).join('')}</ul></div>`;
  function render(message = '', kind = '') {
    const finished = Boolean(state.completed) || current() >= items.length;
    const next = esc(data.next_url || data.back_url || '/dashboard/assessment/');
    root.innerHTML = `<div class="l24g2-shell">
      <a class="l24g2-back" href="${esc(data.back_url || '/dashboard/assessment/')}">← <span>Aking Aralin</span></a>
      <section class="l24g2-card">
        <header class="l24g2-header">
          <p class="l24g2-eyebrow">SESSION ${esc(activity.session || 8)} · LESSON ${esc(activity.lesson || 24)} · BAHAGI 1 · GAWAIN ${esc(activity.display_gawain_number || activity.activity_number || 2)} · P. ${esc(activity.printed_page || 44)}</p>
          <h1>${esc(activity.title || '')}</h1>
          <p class="l24g2-instruction">${esc(activity.instruction || '')}</p>
          <button class="l24g2-replay" id="instruction" type="button">🔊 Pakinggan Muli</button>
          <div class="l24g2-progress"><span>${progressText()}</span><i><b style="width:${items.length ? done().length / items.length * 100 : 0}%"></b></i></div>
        </header>
        ${finished ? `<section class="l24g2-complete"><h2>Magaling!</h2><p>Natapos mo ang Gawain 2.</p><div><a class="l24g2-primary" href="${next}">Susunod</a><a class="l24g2-secondary" href="${esc(data.back_url || '/dashboard/assessment/')}">Bumalik sa Aking Aralin</a></div></section>` : `<div class="l24g2-layout">
          <section class="l24g2-word-panel">${column(headers[0] || 'V', rows.map(row => row[0]).filter(Boolean))}${column(headers[1] || 'v', rows.map(row => row[1]).filter(Boolean))}</section>
          <section class="l24g2-reading-panel"><h2>BASAHIN</h2><p class="l24g2-label">Tunog / Salitang Babasahin</p><strong class="l24g2-target">${esc(word())}</strong><p class="l24g2-attempts">Pagsubok: ${Number(state.reading_attempts || 0)} / 3</p><div class="l24g2-actions"><button class="l24g2-primary" id="read" type="button">🎙 Simulan ang Pagbasa</button>${state.reading_phase === 'help' ? '<button class="l24g2-secondary" id="retry" type="button">Subukan Muli</button>' : ''}</div><div class="l24g2-heard"><span>NARINIG KO</span><strong>${esc(state.last_transcript || '—')}</strong></div><p class="l24g2-feedback ${kind}" role="status" aria-live="polite">${esc(message || state.last_feedback || '')}</p><button class="l24g2-reset" id="restart" type="button">Ulitin Mula sa Simula</button></section>
        </div>`}
      </section></div>`;
    document.getElementById('instruction').onclick = playInstruction;
    if (!finished) { document.getElementById('read').onclick = state.reading_phase === 'help' ? listen : record; document.getElementById('restart').onclick = restart; document.getElementById('retry')?.addEventListener('click', retry); }
  }
  async function request(event, form = null) {
    const body = form || JSON.stringify({...event, revision: Number(state.revision || 0)});
    const headers = {'X-CSRFToken': csrf()}; if (!form) headers['Content-Type'] = 'application/json';
    const response = await fetch(data.progress_url, {method:'POST', credentials:'same-origin', headers, body});
    const result = await response.json().catch(() => ({}));
    if (!response.ok || !result.success) throw Error(result.error || 'Hindi na-save ang iyong gawain.');
    state = result.state || result.progress?.state || state; return result;
  }
  async function playAudio(text) {
    const form = new FormData(); form.append('target_text', text); form.append('language', 'Filipino'); form.append('mode', 'reading'); form.append('prescribed_activity_key', activity.activity_key);
    const response = await fetch(data.read_aloud_url, {method:'POST', credentials:'same-origin', headers:{'X-CSRFToken':csrf()}, body:form});
    const result = await response.json(); if (!response.ok || !result.audio_content) throw Error('Hindi available ang audio.');
    audio = new Audio(`data:${result.mime_type || 'audio/mpeg'};base64,${result.audio_content}`); await audio.play(); await new Promise(resolve => {audio.onended = resolve; audio.onerror = resolve;}); audio = null;
  }
  async function playInstruction() { if (busy || audio) return; busy = true; render(); try { await playAudio(activity.instruction || ''); } catch (_) {} finally { audio = null; busy = false; render(); } }
  async function record() {
    if (busy) return; busy = true; const mine = ++requestId; render();
    try { await request({action:'reading_started'}); if (!navigator.mediaDevices?.getUserMedia || !window.MediaRecorder) throw Error('Hindi available ang mikropono.'); stream = await window.Basahin.openMicrophone({audio:true}); const blob = await window.Basahin.capture({button:document.getElementById('read'), stream}); stream.getTracks().forEach(track => track.stop()); stream = null; if (mine !== requestId) return; const form = new FormData(); form.append('audio', blob, 'lesson24-gawain2-reading.webm'); form.append('action', 'reading_attempt'); form.append('revision', String(state.revision || 0)); form.append('item_index', String(current())); const result = await request({}, form); render(result.state?.last_feedback || ''); } catch (error) { stream?.getTracks().forEach(track => track.stop()); stream = null; render(error.message || 'Hindi nakuha ang iyong boses. Subukan muli.', 'bad'); } finally { busy = false; }
  }
  async function listen() { if (busy) return; busy = true; render(); try { await playAudio(word()); await request({action:'read_aloud'}); render('Pakinggan ang tamang pagbigkas, pagkatapos ay subukan mong basahin.'); } catch (error) { render(error.message || 'Hindi available ang audio.', 'bad'); } finally { busy = false; } }
  async function retry() { if (busy) return; busy = true; try { await request({action:'retry_reading'}); render('Handa ka na?'); } catch (error) { render(error.message || 'Hindi pa kailangan ang pag-ulit.', 'bad'); } finally { busy = false; } }
  async function restart() { if (busy || !window.confirm('Sigurado ka bang gusto mong magsimula muli? Mawawala ang kasalukuyang progreso sa Gawain 2.')) return; busy = true; try { await request({action:'restart'}); render(); } catch (error) { render(error.message || 'Hindi na-reset ang gawain.', 'bad'); } finally { busy = false; } }
  window.addEventListener('pagehide', () => {stream?.getTracks().forEach(track => track.stop()); if (audio) audio.pause();});
  render();
})();
