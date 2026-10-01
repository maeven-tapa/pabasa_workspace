(() => {
  'use strict';
  const payload = document.getElementById('workbook-payload');
  const modal = document.getElementById('wb-l24-start');
  if (!payload || !modal) return;
  let data;
  try { data = JSON.parse(payload.textContent || '{}'); } catch (_) { return; }
  const activity = data.activity || {};
  const key = activity.activity_key || '';
  if (!key.startsWith('aral-l24-') || data.preview || data.state?.completed) { modal.remove(); return; }
  const label = [
    `SESSION ${activity.session || 8}`,
    `LESSON ${activity.lesson || 24}`,
    activity.section_label,
    `GAWAIN ${activity.display_gawain_number || activity.activity_number}`,
  ].filter(Boolean).join(' · ');
  const meta = modal.querySelector('[data-l24-start-meta]');
  const title = modal.querySelector('[data-l24-start-title]');
  const instruction = modal.querySelector('[data-l24-start-instruction]');
  if (meta) meta.textContent = label;
  if (title) title.textContent = activity.title || '';
  if (instruction) instruction.textContent = activity.instruction || '';
  const start = modal.querySelector('[data-l24-start-button]');
  const later = modal.querySelector('[data-l24-later-button]');
  if (!start || !later) return;
  document.body.classList.add('lesson-start-open');
  let finished = false;
  const finish = () => {
    if (finished) return false;
    finished = true;
    start.disabled = true;
    later.disabled = true;
    modal.remove();
    document.body.classList.remove('lesson-start-open');
    return true;
  };
  start.onclick = () => {
    if (!finish()) return;
    document.dispatchEvent(new CustomEvent('pabasa:l24-started', {detail: {activityKey: key}}));
  };
  later.onclick = () => {
    if (!finish()) return;
    window.location.href = data.back_url || document.getElementById('wb-back')?.href || '/dashboard/assessment/';
  };
})();
