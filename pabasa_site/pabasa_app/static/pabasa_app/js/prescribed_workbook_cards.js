(() => {
  'use strict';
  const escape = value => String(value ?? '').replace(/[&<>"']/g, ch => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));
  const label = activity => activity.lesson_number
    ? `Lesson ${activity.lesson_number} · Gawain ${activity.gawain_number}`
    : `Session ${activity.session_number} · Activity ${activity.gawain_number}`;

  function init() {
    const picker = document.getElementById('prescribedActivityPicker');
    const payload = document.getElementById('prescribed-workbook-activities');
    if (!picker || !payload) return;
    let activities;
    try { activities = JSON.parse(payload.textContent || '[]'); } catch (_) { return; }
    const workbook = activities.filter(activity => activity.interaction === 'prescribed_workbook');
    const existing = new Set([...picker.querySelectorAll('[data-workbook-key]')].map(node => node.dataset.workbookKey));
    workbook.forEach(activity => {
      if (existing.has(activity.activity_key)) return;
      const button = document.createElement('button');
      button.type = 'button';
      button.className = 'prescribed-activity-option';
      button.dataset.workbookKey = activity.activity_key;
      button.dataset.prescribedActivity = activity.activity_key;
      button.dataset.sessionNumber = String(activity.session_number);
      const image = activity.thumbnail ? `<img src="${escape(activity.thumbnail)}" alt="">` : '<span aria-hidden="true">📘</span>';
      button.innerHTML = `<span class="prescribed-activity-option__body"><span class="prescribed-activity-option__number">${escape(activity.gawain_number)}</span><span><strong>${escape(label(activity))}</strong><br><span class="small text-muted">${escape(activity.display_title || activity.title)}</span></span></span><span class="prescribed-activity-option__overlay">Preview</span>`;
      const preview = document.createElement('dialog');
      preview.className = 'prescribed-workbook-teacher-preview';
      preview.setAttribute('aria-label', `${label(activity)} preview`);
      preview.innerHTML = `<header><strong>${escape(label(activity))}</strong><button type="button" aria-label="Close preview">×</button></header><div class="prescribed-workbook-teacher-preview__content">${image}<h2>${escape(activity.display_title || activity.title)}</h2><p>${escape(activity.description || activity.instruction)}</p><iframe title="${escape(label(activity))} view-only preview" src="/dashboard/assessment/activity/prescribed/${encodeURIComponent(activity.activity_key)}/?preview=1"></iframe></div><footer><span>Prescribed · View only</span><button type="button">Close</button></footer>`;
      document.body.append(preview);
      const close = () => preview.close();
      preview.querySelector('header button').addEventListener('click', close);
      preview.querySelector('footer button').addEventListener('click', close);
      preview.addEventListener('click', event => { if (event.target === preview) close(); });
      preview.addEventListener('close', () => button.focus());
      button.addEventListener('click', () => preview.showModal());
      picker.append(button);
    });
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init, {once:true});
  else init();
})();
