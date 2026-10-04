(() => {
  'use strict';
  window.PrescribedControls = {
    init(config) {
      // Cancel shared speech work before a pause, navigation, reset or mute can
      // make an in-flight result belong to a different activity state.
      const cancelReading = () => window.Basahin?.cancelAll?.();
      const q = id => document.getElementById(`${config.prefix}${id}`);
      const leaveEnabled = new Set(['prescribed-s1l1g1','prescribed-s1l2g1','prescribed-s1l3g1','prescribed-s1l3g2','prescribed-s2l4g1','prescribed-s2l4g2','prescribed-s2l5g1','prescribed-s2l6g1','prescribed-s3l7g1','prescribed-s3l7g2a','prescribed-s3l7g2b','prescribed-s3l7g2c','prescribed-s3l7g3','prescribed-s3l7g4','prescribed-s3l7g4a','prescribed-s3l7g4b','prescribed-s3l8g1','prescribed-s3l8g1a','prescribed-s3l9g1','prescribed-s3l9g2','prescribed-s3l9g3']).has(config.prefix);
      const dedupeBackEnabled = new Set(['prescribed-s1l1g1','prescribed-s1l3g2']).has(config.prefix);
      const noPseudoBackEnabled = new Set(['prescribed-s2l4g1','prescribed-s2l4g2','prescribed-s2l5g1','prescribed-s2l6g1','prescribed-s3l7g1','prescribed-s3l7g2a','prescribed-s3l7g2b','prescribed-s3l7g2c','prescribed-s3l7g3','prescribed-s3l7g4','prescribed-s3l7g4a','prescribed-s3l7g4b','prescribed-s3l8g1','prescribed-s3l8g1a','prescribed-s3l9g1','prescribed-s3l9g2','prescribed-s3l9g3']).has(config.prefix);
      if (leaveEnabled && !dedupeBackEnabled) { const back = document.querySelector('.back'); if (back) { back.textContent = '← Bumalik sa Aking Gawain'; back.classList.add('leave-back'); if (noPseudoBackEnabled) back.classList.add('no-pseudo'); } }
      if (dedupeBackEnabled) {
        const keepSingleBack = () => {
          const backs = [...document.querySelectorAll('.back')];
          const back = backs[0];
          backs.slice(1).forEach(redundant => redundant.remove());
          return back;
        };
        const back = keepSingleBack();
        if (back) { back.textContent = '← Bumalik sa Aking Gawain'; back.classList.add('leave-back'); if (dedupeBackEnabled || noPseudoBackEnabled) back.classList.add('no-pseudo'); }
        new MutationObserver(() => {
          const retained = keepSingleBack();
          if (retained && !retained.classList.contains('leave-back')) {
            retained.textContent = '← Bumalik sa Aking Gawain';
            retained.classList.add('leave-back');
            if (dedupeBackEnabled) retained.classList.add('no-pseudo');
          }
        }).observe(document.body, { childList: true, subtree: true });
      }
      window.addEventListener('basahin:state', event => {
        const detail = event.detail || {};
        const field = q('-debug-vad');
        if (!field) return;
        const value = detail.state === 'level'
          ? (detail.calibrating ? 'Calibrating' : detail.speaking ? 'Speech detected' : 'Quiet')
          : detail.state === 'silence' ? 'Silent clip skipped' : 'Listening';
        if (field.textContent !== value) field.textContent = value;
      });
      const help = q('-help-modal'), pause = q('-pause-modal'), restart = q('-restart-modal'), audio = q('-audio-settings-modal'), leave = q('-leave-modal');
      const close = modal => { if (modal) modal.hidden = true; };
      const closeAll = () => [help, pause, restart, audio, leave].forEach(close);
      const open = modal => { closeAll(); if (modal) modal.hidden = false; };
      q('-help-btn')?.addEventListener('click', async () => { cancelReading(); await config.adapter.cancelAttempt?.('help'); open(help); });
      q('-help-close')?.addEventListener('click', () => { config.adapter.resume?.(); close(help); });
      q('-audio-settings-btn')?.addEventListener('click', () => { cancelReading(); config.adapter.pause?.(); open(pause); });
      q('-resume')?.addEventListener('click', () => { close(pause); config.adapter.resume?.(); });
      q('-restart')?.addEventListener('click', () => open(restart));
      q('-restart-yes')?.addEventListener('click', async () => { cancelReading(); close(restart); await config.adapter.restart?.(); });
      q('-restart-no')?.addEventListener('click', () => open(pause));
      let leaveInFlight = false;
      const showLeave = source => {
        if (!leave) return;
        leave.dataset.source = source;
        q('-leave-error')?.setAttribute('hidden', '');
        close(leave); if (pause) pause.hidden = source !== 'pause'; leave.hidden = false;
        q('-leave-no')?.focus();
      };
      const requestLeave = event => { event?.preventDefault(); showLeave('activity'); };
      const resolveLeaveAdapter = () => {
        if (window.__activityLeaveAdapter) return window.__activityLeaveAdapter;
        const session2Save = window.__session4SaveAdapters?.[config.prefix];
        if (typeof session2Save === 'function') return { cleanup: config.adapter.cleanup, saveCurrentProgress: () => session2Save() };
        const session3Save = window.__session3SaveAdapters?.[config.prefix];
        if (typeof session3Save === 'function') return { cleanup: config.adapter.cleanup, saveCurrentProgress: () => session3Save() };
        const progress = window.__lessonStartProgress;
        let data = {};
        try { data = JSON.parse(document.getElementById('lesson-one-data')?.textContent || '{}'); } catch (_) {}
        const activityKey = progress?.activityKey || data.activity_key || ({'prescribed-s1l1g1':'lesson-1-gawain-1','prescribed-s1l2g1':'lesson-2-gawain-1','prescribed-s1l3g1':'lesson-3-gawain-1','prescribed-s1l3g2':'lesson-3-gawain-2'})[config.prefix];
        const progressUrl = progress?.progressUrl || data.progress_url;
        const totalItems = Number(progress?.totalItems || data.progress?.total_items || (config.prefix === 'prescribed-s1l1g1' ? 28 : 0));
        if (!activityKey || !progressUrl || !totalItems) return null;
        return {
          cleanup: config.adapter.cleanup,
          saveCurrentProgress: async () => {
            const key = progress?.storageKeys?.find(value => value.includes(activityKey)) || `pabasa:${activityKey}:progress`;
            const current = Math.max(0, Math.min(totalItems, Number(localStorage.getItem(key) || progress?.progress?.current_index || data.progress?.current_index || 0)));
            const csrf = document.cookie.match(/(?:^|; )csrftoken=([^;]+)/)?.[1] || '';
            const response = await fetch(progressUrl, { method:'POST', credentials:'same-origin', headers:{'Content-Type':'application/json','X-CSRFToken':csrf}, body:JSON.stringify({activity_key:activityKey,current_index:current,completed_items:current,correct_items:current,total_items:totalItems,activity_completed:false}) });
            const payload = await response.json().catch(() => ({}));
            if (!response.ok || payload.success !== true) throw new Error(payload.error || `Progress save failed: HTTP ${response.status}`);
            return payload;
          }
        };
      };
      if (leaveEnabled) document.querySelector('.back')?.addEventListener('click', requestLeave);
      if (leaveEnabled) q('-back')?.addEventListener('click', () => showLeave('pause'));
      q('-leave-no')?.addEventListener('click', () => {
        const fromPause = leave?.dataset.source === 'pause';
        close(leave);
        if (fromPause && pause) { pause.hidden = false; q('-back')?.focus(); }
        else document.querySelector('.back')?.focus();
      });
      q('-leave-yes')?.addEventListener('click', async () => {
        if (!leaveEnabled) return;
        if (leaveInFlight) return;
        leaveInFlight = true;
        const stay = q('-leave-no'), go = q('-leave-yes'), error = q('-leave-error');
        stay.disabled = true; go.disabled = true; error?.setAttribute('hidden', '');
        try {
          const adapter = resolveLeaveAdapter();
          if (!adapter || typeof adapter.saveCurrentProgress !== 'function') throw new Error('No leave save adapter registered');
          cancelReading();
          await adapter.cleanup?.();
          await adapter.saveCurrentProgress();
          if (!window.__leaveNavigationStarted) { window.__leaveNavigationStarted = true; window.location.assign('/dashboard/assessment/'); }
        } catch (e) {
          console.error('Leave save failed', e);
          if (error) { error.textContent = 'Hindi na-save ang iyong gawain. Subukan muli.'; error.removeAttribute('hidden'); }
          stay.disabled = false; go.disabled = false; leaveInFlight = false;
        }
      });
      q('-audio-test')?.addEventListener('click', () => open(audio));
      q('-audio-close')?.addEventListener('click', () => { config.adapter.stopAudioTest?.(); open(pause); });
      [help, pause, restart, audio].forEach(modal => modal?.addEventListener('click', e => { if (e.target === modal) { if (modal === audio) { config.adapter.stopAudioTest?.(); open(pause); } else { if (modal === help) config.adapter.resume?.(); close(modal); } } }));
      const mic = q('-mic-toggle');
      mic?.addEventListener('click', () => { const muted = !(mic.getAttribute('aria-pressed') === 'true'); if (muted) cancelReading(); config.adapter.setMuted?.(muted); });
      window.addEventListener('keydown', e => {
        if (e.key !== 'Escape') return;
        if (leave && !leave.hidden && !leaveInFlight) {
          const fromPause = leave.dataset.source === 'pause';
          close(leave);
          if (fromPause && pause) { pause.hidden = false; q('-back')?.focus(); }
          else { q('-audio-settings-btn')?.focus(); }
          return;
        }
        if (audio && !audio.hidden) open(pause);
      });
      config.adapter.bindAudioTest?.({audio, q});
      config.adapter.bindDebug?.({q});
    }
  };
})();
