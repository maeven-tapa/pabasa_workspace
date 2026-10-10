(() => {
    'use strict';
    let nextId = 0;

    function order(task) {
        const title = String(task.title || '');
        const label = String(task.activityLabel || '');
        const number = (value, pattern) => Number(String(value).match(pattern)?.[1] || Infinity);
        return [number(label, /session\s*(\d+)/i), number(title, /lessons?\s*(\d+)/i),
            number(title, /(?:activity|gawain)\s*(\d+)/i)];
    }

    function compareTasks(a, b) {
        const left = order(a), right = order(b);
        for (let index = 0; index < left.length; index++) {
            if (left[index] !== right[index]) return left[index] < right[index] ? -1 : 1;
        }
        return String(a.title || '').localeCompare(String(b.title || ''), undefined,
            {numeric: true, sensitivity: 'base'});
    }

    function stopAudio(dialog) {
        dialog.querySelectorAll('audio').forEach(audio => audio.pause());
        document.dispatchEvent(new Event('pabasa:stop-student-progress-audio'));
    }

    function closeAll(root) {
        root.querySelectorAll('.student-progress-review-dialog[open]').forEach(dialog => dialog.close());
    }

    function removeRecording(recording) {
        if (!recording) return;
        const dialog = recording.closest('.student-progress-review-dialog');
        if (!dialog) { recording.remove(); return; }
        const card = dialog.closest('.student-progress-card');
        const wasOpen = dialog.open;
        stopAudio(dialog);
        if (wasOpen) dialog.close();
        card?.querySelector(`[aria-controls="${dialog.id}"]`)?.remove();
        dialog.remove();
        if (wasOpen && card?.isConnected) {
            card.tabIndex = -1;
            card.focus({preventScroll: true});
        }
    }

    function mount(root) {
        root.querySelectorAll('.student-progress-card').forEach(card => {
            const recording = card.querySelector('.student-progress-recording');
            if (!recording || card.querySelector('.student-progress-review-dialog')) return;
            const dialog = document.createElement('dialog');
            dialog.className = 'student-progress-review-dialog';
            dialog.id = `student-progress-review-${++nextId}`;
            dialog.setAttribute('aria-labelledby', `${dialog.id}-title`);
            dialog.setAttribute('closedby', 'none');
            const header = document.createElement('header');
            header.className = 'student-progress-review-header';
            const identity = document.createElement('div');
            const label = document.createElement('small');
            label.textContent = card.querySelector('.student-progress-type')?.textContent || '';
            const title = document.createElement('h2');
            title.id = `${dialog.id}-title`;
            title.textContent = card.querySelector('.student-progress-title')?.textContent || 'Activity recordings';
            identity.append(label, title);
            const close = document.createElement('button');
            close.type = 'button';
            close.className = 'student-progress-review-close';
            close.textContent = '×';
            close.setAttribute('aria-label', 'Close recording review');
            close.addEventListener('click', () => dialog.close());
            header.append(identity, close);
            const body = document.createElement('div');
            body.className = 'student-progress-review-body';
            const trigger = document.createElement('button');
            trigger.type = 'button';
            trigger.className = 'student-progress-review-trigger';
            trigger.setAttribute('aria-haspopup', 'dialog');
            trigger.setAttribute('aria-controls', dialog.id);
            const itemCount = recording.querySelectorAll('.session4-letter-recording, .session5-fluency-row').length;
            trigger.innerHTML = '<span><strong>Review recordings</strong><small></small></span><span aria-hidden="true">→</span>';
            trigger.querySelector('small').textContent = itemCount
                ? `${itemCount} items · Open to listen and review`
                : 'Open to listen and review';
            recording.before(trigger);
            body.append(recording);
            dialog.append(header, body);
            card.append(dialog);
            trigger.addEventListener('click', () => {
                stopAudio(dialog);
                dialog.showModal();
                close.focus();
            });
            dialog.addEventListener('close', () => {
                stopAudio(dialog);
                if (trigger.isConnected) trigger.focus({preventScroll: true});
            });
            dialog.addEventListener('keydown', event => {
                // Keep Escape from dismissing the course parent.
                if (event.key === 'Escape') event.stopPropagation();
            });
            dialog.addEventListener('cancel', event => {
                // Also prevent native dismissal in browsers without closedby support.
                event.preventDefault();
                event.stopPropagation();
            });
        });
    }

    window.StudentActivityReview = {compareTasks, mount, closeAll, removeRecording};
})();
