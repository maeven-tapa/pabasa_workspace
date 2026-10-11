(() => {
  'use strict';
  const tables = new Map();
  const labels = {GREEN: '🟢 Nabasa nang maayos', YELLOW: '🟡 Nabasa pero medyo putol-putol', RED: '🔴 Hindi Nabasa'};
  function render(items, studentId, escapeHtml, saveUrl) {
    tables.set(String(studentId), {items, escapeHtml, saveUrl});
    const graded = items.filter(item => item.review_status === 'reviewed' && item.classification_source !== 'skipped').length;
    const pending = items.filter(item => item.review_status === 'pending' && item.submission_id && (item.recording_url || item.recordings?.some(clip => clip.recording_url))).length;
    const skipped = items.filter(item => item.review_status === 'skipped').length;
    return `<div class="lesson15-reading-review compact-reading-review" data-student-id="${escapeHtml(studentId)}"><div class="session5-evaluation-summary" aria-live="polite"><strong>Reading Evaluation — ${graded} / ${items.length} Reviewed</strong><span>Pending: ${pending} · Skipped: ${skipped}</span></div><div class="session5-fluency-table reading-review-list"><div class="session5-fluency-header"><span>Reading Item</span><span>Student Recording</span><span>Classification</span></div>${items.map(item => {
      const automatic = item.classification_source === 'skipped';
      const recordings = (item.recordings?.length ? item.recordings : item.recording_url ? [{recording_url: item.recording_url}] : []).filter(clip => clip.recording_url);
      const reviewable = Boolean(item.submission_id && recordings.length && !automatic);
      return `<div class="session5-fluency-row" data-item-index="${item.item_index}" data-review-state="${automatic ? 'skipped' : item.review_status === 'reviewed' ? 'reviewed' : reviewable ? 'pending' : 'missing'}"><span class="session5-fluency-text"><strong><span class="session5-fluency-number">${item.item_index + 1}.</span> ${escapeHtml(item.expected_text)}</strong>${item.transcript ? `<small>${escapeHtml(item.transcript)}</small>` : ''}</span><span class="session5-fluency-audio">${recordings.length ? recordings.map((clip, index) => `${recordings.length > 1 ? `<small>Bahagi ${index + 1} / ${recordings.length}</small>` : ''}<audio controls preload="metadata" src="${escapeHtml(clip.recording_url)}" aria-label="Student recording: ${escapeHtml(item.expected_text)}"></audio>`).join('') : '<span class="text-muted">No recording</span>'}</span><span class="reading-review-classification">${automatic ? '<strong class="reading-review-red">🔴 Hindi Nabasa</strong><small class="session5-review-state">Nilaktawan · Awtomatiko</small>' : reviewable ? `<select class="form-select form-select-sm lesson15-fluency-select" aria-label="Classification: ${escapeHtml(item.expected_text)}"><option value="">Naghihintay ng pagsusuri</option>${Object.entries(labels).map(([code, label]) => `<option value="${code}" ${item.classification === code ? 'selected' : ''}>${label}</option>`).join('')}</select><small class="session5-review-state">${escapeHtml(item.review_status)}</small>` : '<span class="reading-review-neutral">Wala pang pagbasa</span>'}</span></div>`;
    }).join('')}</div><p class="lesson15-review-feedback" role="status" aria-live="polite"></p></div>`;
  }
  document.addEventListener('change', async event => {
    const select = event.target.closest('.lesson15-fluency-select');
    if (!select || select.disabled || !labels[select.value]) return;
    const root = select.closest('.lesson15-reading-review');
    const table = tables.get(root.dataset.studentId);
    const item = table.items.find(row => row.item_index === Number(select.closest('[data-item-index]').dataset.itemIndex));
    const previous = item.classification;
    select.disabled = true;
    root.querySelector('.lesson15-review-feedback').textContent = 'Nagse-save…';
    try {
      const response = await fetch(table.saveUrl, {method: 'POST', credentials: 'same-origin',
        headers: {'Content-Type': 'application/json', 'X-CSRFToken': decodeURIComponent(document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/)?.[1] || '')},
        body: JSON.stringify({student_id: root.dataset.studentId, item_index: item.item_index,
          classification: select.value, attempt_id: item.attempt_id, review_version: item.review_version})});
      const data = await response.json();
      if (!response.ok || !data.success) throw new Error(data.error || 'Hindi na-save ang grado. Subukan muli.');
      table.items.splice(0, table.items.length, ...data.items);
      root.outerHTML = render(table.items, root.dataset.studentId, table.escapeHtml, table.saveUrl);
    } catch (error) {
      select.value = labels[previous] ? previous : '';
      root.querySelector('.lesson15-review-feedback').textContent = error.message;
    } finally { select.disabled = false; }
  });
  window.Lesson15ReadingReview = {render};
})();
