(function () {
  'use strict';

  let attemptId = 0;

  async function recordExactWord() {
    if (busy) return;
    const currentAttemptId = ++attemptId;
    const currentPairIndex = pi;
    const currentWordIndex = wi;
    const expectedWord = pairs[currentPairIndex][currentWordIndex];
    const readButton = document.getElementById('read');
    const status = document.getElementById('status');
    const answers = document.getElementById('answers');
    const listenButton = document.getElementById('listen');
    if (!readButton || !status || !answers || !navigator.mediaDevices?.getUserMedia || !MediaRecorder) return;

    busy = true;
    readButton.disabled = true;
    readButton.classList.add('is-recording');
    readButton.textContent = 'Nagbabasa...';
    let stream;
    try {
      stream = await navigator.mediaDevices.getUserMedia({audio: true});
      const chunks = [];
      const recorder = new MediaRecorder(stream);
      recorder.ondataavailable = event => event.data.size && chunks.push(event.data);
      const recordingStopped = new Promise(resolve => {
        recorder.onstop = () => resolve(new Blob(chunks, {type: recorder.mimeType || 'audio/webm'}));
      });
      recorder.start();
      setTimeout(() => recorder.state === 'recording' && recorder.stop(), 3500);
      const blob = await recordingStopped;
      const form = new FormData();
      form.append('audio', blob, 'rhyme.webm');
      form.append('target_text', expectedWord);
      form.append('language', 'Filipino');
      form.append('mode', 'reading');
      form.append('salitang_magkatugma_exact', '1');
      readButton.classList.remove('is-recording');
      readButton.classList.add('is-processing');
      readButton.textContent = 'Pinoproseso...';
      const response = await fetch('/api/reading/transcribe/', {
        method: 'POST',
        credentials: 'same-origin',
        headers: {'X-CSRFToken': document.cookie.match(/csrftoken=([^;]+)/)?.[1] || ''},
        body: form
      });
      const data = await response.json();
      if (currentAttemptId !== attemptId || currentPairIndex !== pi || currentWordIndex !== wi) return;

      const rawTranscript = String(data.raw_transcript ?? '');
      const finalTranscript = String(data.transcript ?? '');
      const heard = norm(rawTranscript);
      const expected = norm(expectedWord);
      const isCorrect = Boolean(response.ok && data.success && data.complete === true);
      window.salitangSpeechDebugLog?.({
        attempt_number: currentAttemptId,
        current_pair: currentPairIndex + 1,
        current_word: currentWordIndex + 1,
        expected_word: expectedWord,
        raw_transcript: rawTranscript,
        final_transcript: finalTranscript,
        success: Boolean(data.success),
        complete: data.complete ?? null,
        matched: data.matched ?? null,
        normalized_expected: expected,
        normalized_transcript: heard,
        exact_match: isCorrect,
        advanced: Boolean(data.success && isCorrect),
        rejected: !isCorrect,
        response_ok: response.ok,
        response_data: data
      });
      if (!isCorrect) {
        answers.hidden = true;
        answers.querySelectorAll('button').forEach(button => { button.disabled = true; });
        ra[wi] += 1;
        status.textContent = `Hindi pa ito tama. Subukan muli. (${ra[wi]}/3)`;
        status.classList.add('warning');
        readButton.hidden = false;
        readButton.disabled = false;
        if (listenButton) listenButton.hidden = false;
        return;
      }

      const isLastWord = currentWordIndex === pairs[currentPairIndex].length - 1;
      status.classList.remove('warning');
      if (isLastWord) {
        answers.hidden = false;
        answers.querySelectorAll('button').forEach(button => { button.disabled = false; });
        readButton.hidden = true;
        if (listenButton) listenButton.hidden = true;
        status.textContent = 'Piliin ang tamang kamay.';
      } else {
        wi += 1;
        render();
      }
    } catch (error) {
      if (currentAttemptId !== attemptId) return;
      status.textContent = 'Hindi nakuha ang iyong boses. Subukan muli.';
      status.classList.add('warning');
      readButton.hidden = false;
      readButton.disabled = false;
      if (listenButton) listenButton.hidden = false;
    } finally {
      stream?.getTracks().forEach(track => track.stop());
      busy = false;
      readButton.classList.remove('is-recording', 'is-processing');
    }
  }

  function bindRecorder() {
    const readButton = document.getElementById('read');
    if (readButton) readButton.onclick = recordExactWord;
  }

  function install() {
    bindRecorder();
    new MutationObserver(bindRecorder).observe(document.getElementById('stage'), {
      childList: true,
      subtree: true
    });
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', install, {once: true});
  else install();
}());
