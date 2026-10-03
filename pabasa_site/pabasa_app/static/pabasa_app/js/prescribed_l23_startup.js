(() => {
  'use strict';
  const payload = document.getElementById('workbook-payload');
  if (!payload) return;
  const data = JSON.parse(payload.textContent || '{}');
  const key = data.activity?.activity_key || '';
  const number = ({
    'aral-l23-g1-n-syllable-builder': 'g1',
    'aral-l23-g2-n-word-reading': 'g2',
    'aral-l23-g3-j-word-reading': 'g3',
    'aral-l23-g4-j-syllabication': 'g4',
    'aral-l23-g5-j-word-search': 'g5',
    'aral-l23-g6-q-syllable-builder': 'g6',
    'aral-l23-g7-q-word-reading': 'g7',
  })[key];
  if (!number || data.preview || data.state?.completed) return;
  const modal = document.getElementById(`wb-l23-${number}-start`);
  const start = document.getElementById(`wb-l23-${number}-start-button`);
  const later = document.getElementById(`wb-l23-${number}-later-button`);
  if (!modal || !start || !later) return;
  document.body.classList.add('lesson-start-open');
  let started = false;
  const audio = () => {
    const url = data.local_audio?.instruction;
    if (!url) return;
    const player = new Audio(url);
    player.play().catch(() => {});
  };
  start.onclick = () => {
    if (started) return;
    started = true;
    start.disabled = true;
    later.disabled = true;
    modal.remove();
    document.body.classList.remove('lesson-start-open');
    document.dispatchEvent(new CustomEvent('pabasa:l23-started', {detail: {activityKey: key}}));
    document.querySelectorAll('.wb-bigbox-tile:disabled,#wb-basahin:disabled').forEach(button => {button.disabled = false;});
    if (key === 'aral-l23-g3-j-word-reading') return;
    audio();
  };
  later.onclick = () => {
    if (started) return;
    started = true;
    start.disabled = true;
    later.disabled = true;
    window.location.href = data.back_url || document.getElementById('wb-back')?.href || '/dashboard/assessment/';
  };
})();
