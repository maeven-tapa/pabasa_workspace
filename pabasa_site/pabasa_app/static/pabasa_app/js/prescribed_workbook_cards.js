(() => {
  'use strict';
  const escape = value => String(value ?? '').replace(/[&<>"']/g, ch => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));
  const displayNumber = activity => activity.display_gawain_number ?? activity.gawain_number;
  const label = activity => activity.section_display_label || (activity.lesson_number
    ? `Lesson ${activity.lesson_number} · Gawain ${displayNumber(activity)}`
    : `Session ${activity.session_number} · Activity ${activity.gawain_number}`);

  function init() {
    const picker = document.getElementById('prescribedActivityPicker');
    const payload = document.getElementById('prescribed-workbook-activities');
    if (!picker || !payload) return;
    let activities;
    try { activities = JSON.parse(payload.textContent || '[]'); } catch (_) { return; }
    const workbook = activities.filter(activity => activity.interaction === 'prescribed_workbook');
    const orderedWorkbook = workbook.map((activity, index) => ({activity, index})).sort((left, right) => {
      const bothLesson24 = Number(left.activity.lesson_number) === 24 && Number(right.activity.lesson_number) === 24;
      if (!bothLesson24) return left.index - right.index;
      return (Number(left.activity.section_order || 0) - Number(right.activity.section_order || 0))
        || (Number(displayNumber(left.activity)) - Number(displayNumber(right.activity)))
        || (left.index - right.index);
    }).map(entry => entry.activity);
    const existing = new Set([...picker.querySelectorAll('[data-workbook-key]')].map(node => node.dataset.workbookKey));
    let lastLesson24Section = null;
    orderedWorkbook.forEach(activity => {
      if (existing.has(activity.activity_key)) return;
      const lesson24Section = Number(activity.lesson_number) === 24 ? activity.section_key : null;
      if (lesson24Section && lesson24Section !== lastLesson24Section) {
        const heading = document.createElement('div');
        heading.className = 'prescribed-activity-group-heading';
        heading.dataset.prescribedGroup = lesson24Section;
        heading.textContent = `Lesson ${activity.lesson_number} — ${activity.section_label || lesson24Section}`;
        picker.append(heading);
        lastLesson24Section = lesson24Section;
      }
      const button = document.createElement('button');
      button.type = 'button';
      button.className = 'prescribed-activity-option';
      button.dataset.workbookKey = activity.activity_key;
      button.dataset.prescribedActivity = activity.activity_key;
      button.dataset.sessionNumber = String(activity.session_number);
      const image = activity.thumbnail ? `<img src="${escape(activity.thumbnail)}" alt="">` : '<span aria-hidden="true">📘</span>';
      button.innerHTML = `<span class="prescribed-activity-option__body"><span class="prescribed-activity-option__number">${escape(displayNumber(activity))}</span><span><strong>${escape(label(activity))}</strong><br><span class="small text-muted">${escape(activity.display_title || activity.title)}</span></span></span><span class="prescribed-activity-option__overlay">Preview</span>`;
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
    if (!document.getElementById('prescribed-activity-group-heading-style')) {
      const style = document.createElement('style');
      style.id = 'prescribed-activity-group-heading-style';
      style.textContent = '.prescribed-activity-group-heading{grid-column:1/-1;width:100%;margin:1rem 0 .25rem;padding:.45rem .75rem;border-radius:.6rem;background:#eef5ff;color:#174a7c;font-weight:700;}';
      document.head.append(style);
    }
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init, {once:true});
  else init();
})();
