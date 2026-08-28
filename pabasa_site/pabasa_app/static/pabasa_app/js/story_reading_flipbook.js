(() => {
    'use strict';
    const dataNode = document.getElementById('story-reading-data');
    const story = dataNode ? JSON.parse(dataNode.textContent || '{}') : {};
    const app = document.getElementById('storybookApp');
    const book = document.getElementById('book');
    const leftPage = document.getElementById('leftPage');
    const rightPage = document.getElementById('rightPage');
    const turningPage = document.getElementById('turningPage');
    const previousButton = document.getElementById('previousPage');
    const nextButton = document.getElementById('nextPage');
    const listenButton = document.getElementById('listenButton');
    const oralReadingButton = document.getElementById('oralReadingButton');
    const oralReadingStatus = document.getElementById('oralReadingStatus');
    const oralReadingDetail = document.getElementById('oralReadingDetail');
    const pageCount = document.getElementById('pageCount');
    const pageDots = document.getElementById('pageDots');
    const completionPanel = document.getElementById('completionPanel');
    const completionStudentName = document.getElementById('completionStudentName');
    let pages = [];
    let spreadIndex = 0;
    let animating = false;
    let speaking = false;
    let completed = false;
    let readAloudAudio = null;
    let readAloudAudioUrl = '';
    let readAloudLoading = false;
    let readAloudRequestVersion = 0;
    let readAloudController = null;
    let oralActive = false;
    let oralStarting = false;
    let oralStopping = false;
    let oralStream = null;
    let oralRecorder = null;
    let oralChunkTimer = null;
    let oralContextVersion = 0;
    let oralSyllableIndex = 0;
    let oralWordIndex = 0;
    let oralSending = false;
    let pendingOralChunks = [];
    let oralRequestController = null;
    let oralRequestSerial = 0;
    let oralPageCompletionTimer = null;
    // Story pages contain only two sentences. A bounded 3.2-second chunk gives
    // useful follow-along feedback while requests remain strictly serialized.
    const SPEECH_CHUNK_MS = 3200;
    const SPEECH_REQUEST_TIMEOUT_MS = 35000;
    const mobileQuery = window.matchMedia('(max-width: 760px)');

    const escapeHtml = value => String(value || '').replace(/[&<>'"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c]));
    const imageForPage = index => {
        if (index === 0) return '';
        const image = Array.isArray(story.images) ? story.images[index - 1] : null;
        if (typeof image === 'string') return image;
        return image && typeof image === 'object' ? (image.url || image.src || '') : '';
    };
    const imageAltForPage = index => {
        if (index === 0) return '';
        const image = Array.isArray(story.images) ? story.images[index - 1] : null;
        return image && typeof image === 'object' ? String(image.alt || '') : '';
    };
    const sentenceParts = text => String(text || '').match(/[^.!?]+(?:[.!?]+[\u201d\u2019"']*|$)/gu)?.map(value => value.trim()).filter(Boolean) || [String(text || '')];
    const storyTextMarkup = text => {
        let wordIndex = 0;
        return String(text || '').split(/\n\s*\n/).map(paragraph => {
            const sentences = sentenceParts(paragraph);
            return `<span class="story-paragraph">${sentences.map(sentence => {
                const tokenPattern = /[\p{L}\p{N}]+(?:[\u2019'][\p{L}\p{N}]+)*/gu;
                let sentenceMarkup = '';
                let sourceIndex = 0;
                for (const match of sentence.matchAll(tokenPattern)) {
                    sentenceMarkup += escapeHtml(sentence.slice(sourceIndex, match.index));
                    sentenceMarkup += `<span class="story-word" data-word-index="${wordIndex}">${escapeHtml(match[0])}</span>`;
                    wordIndex += 1;
                    sourceIndex = match.index + match[0].length;
                }
                sentenceMarkup += escapeHtml(sentence.slice(sourceIndex));
                return `<span class="story-sentence">${sentenceMarkup}</span>`;
            }).join(' ')}</span>`;
        }).join('');
    };
    const openingPageMarkup = index => index === 0
        ? `<header class="book-opening"><h1>${escapeHtml(story.title || 'Story Reading')}</h1><p>Read at your own pace</p></header>`
        : '';
    const pageMarkup = index => {
        if (index < 0 || index >= pages.length) return '<div class="empty-page" aria-hidden="true"></div>';
        const image = imageForPage(index);
        const shortClass = sentenceParts(pages[index]).length <= 3 ? ' is-short-page' : '';
        if (index === 0) return '<div class="page-composition is-opening-page is-text-only">' + openingPageMarkup(index) + '</div>';
        return `<div class="page-composition${shortClass}${image ? ' has-illustration' : ' is-text-only'}">${image ? `<img class="page-image" src="${escapeHtml(image)}" alt="${escapeHtml(imageAltForPage(index))}">` : ''}<div class="page-content" lang="${escapeHtml(story.language || 'en')}">${storyTextMarkup(pages[index])}</div></div>`;
    };
    const isMobile = () => mobileQuery.matches;
    const step = () => 1;
    const visibleStart = () => spreadIndex;
    const spreadTotal = () => Math.max(1, pages.length);

    function semanticUnits(text) {
        const units = [];
        text.split(/\n\s*\n/).map(value => value.trim()).filter(Boolean).forEach((paragraph, paragraphIndex) => {
            const sentences = paragraph.match(/[^.!?]+(?:[.!?]+[\u201d\u2019"']*|$)/gu) || [paragraph];
            sentences.map(value => value.trim()).filter(Boolean).forEach((sentence, sentenceIndex) => {
                units.push({ text: sentence, paragraphStart: paragraphIndex > 0 && sentenceIndex === 0 });
            });
        });
        return units;
    }

    function paginateIntelligently() {
        const text = String(story.text || '').replace(/\r/g, '').trim();
        const sentences = semanticUnits(text).map(unit => unit.text);
        pages = [''];
        for (let index = 0; index < sentences.length; index += 2) {
            pages.push(sentences.slice(index, index + 2).join('\n\n'));
        }
        spreadIndex = Math.min(spreadIndex, Math.max(0, spreadTotal() - 1));
        render();
    }

    function render() {
        const start = visibleStart();
        leftPage.innerHTML = pageMarkup(start);
        rightPage.innerHTML = '';
        pageCount.textContent = `Page ${start + 1} of ${pages.length}`;
        const onTitlePage = start === 0;
        oralReadingButton.disabled = onTitlePage;
        listenButton.disabled = onTitlePage;
        if (onTitlePage) setOralStatus('', '', 'idle');
        else if (!oralActive && app.dataset.oralState !== 'error') setOralStatus('', '', 'idle');
        previousButton.disabled = spreadIndex === 0;
        nextButton.disabled = !onTitlePage;
        nextButton.setAttribute('aria-label', spreadIndex === spreadTotal() - 1 ? 'Finish story' : 'Next page');
        const nextLabel = nextButton.querySelector('span');
        if (nextLabel) nextLabel.textContent = spreadIndex === spreadTotal() - 1 ? 'Finish' : 'Next';
        pageDots.innerHTML = Array.from({length: spreadTotal()}, (_, i) => `<span class="page-dot${i === spreadIndex ? ' is-active' : ''}" aria-hidden="true"></span>`).join('');
        pageDots.hidden = spreadTotal() <= 1;
    }

    function turn(direction) {
        if (animating) return;
        if (oralPageCompletionTimer) { window.clearTimeout(oralPageCompletionTimer); oralPageCompletionTimer = null; }
        stopReadAloud();
        if (direction < 0 && spreadIndex === 0) return;
        if (direction > 0 && spreadIndex === spreadTotal() - 1) { finishStory(); return; }
        const resumeOralReading = oralActive;
        if (resumeOralReading) stopOralReading({ quiet: true });
        animating = true;
        const start = visibleStart();
        turningPage.querySelector('.turn-front').innerHTML = pageMarkup(direction > 0 ? start + step() - 1 : start);
        turningPage.querySelector('.turn-back').innerHTML = pageMarkup(direction > 0 ? start + step() : Math.max(0, start - 1));
        turningPage.className = `turning-page ${direction > 0 ? 'is-next' : 'is-previous'}`;
        window.setTimeout(() => {
            spreadIndex += direction;
            turningPage.className = 'turning-page';
            render();
            animating = false;
            oralSyllableIndex = 0;
            oralWordIndex = 0;
            if (resumeOralReading && !completed) startOralReading();
        }, 620);
    }

    function getCsrfToken() {
        return document.cookie.split(';').map(v => v.trim()).find(v => v.startsWith('csrftoken='))?.split('=').slice(1).join('=') || '';
    }
    async function saveCompletion() {
        const status = document.getElementById('saveStatus');
        try {
            const response = await fetch('/api/story-reading/complete/', {
                method: 'POST', credentials: 'same-origin',
                headers: {'Content-Type':'application/json','X-CSRFToken':getCsrfToken()},
                body: JSON.stringify({
                    material_id: story.material_id || story.id,
                    story_title: story.title || '',
                    total_words: String(story.text || '').trim().split(/\s+/).filter(Boolean).length,
                    words_read: String(story.text || '').trim().split(/\s+/).filter(Boolean).length,
                    progress_percent: 100,
                    duration_seconds: 0,
                })
            });
            const payload = await response.json().catch(() => ({}));
            if (!response.ok || !payload.success) throw new Error(payload.error || 'Unable to save');
            status.textContent = 'Your reading progress is saved.';
            return true;
        } catch (error) {
            status.textContent = 'We could not save your reading progress. Please try again before continuing.';
            return false;
        }
    }
    function showCompletionScreen() {
        stopOralReading({ quiet: true });
        stopReadAloud();
        completed = true;
        app.classList.add('is-complete');
        completionPanel.hidden = false;
        document.getElementById('completedStoryTitle').textContent = `“${story.title || 'this story'}”`;
        if (completionStudentName && story.first_name) completionStudentName.textContent = `, ${story.first_name}`;
        document.getElementById('continueButton').href = story.return_url || '/dashboard/';
    }
    async function finishStory() {
        if (completed) return;
        stopOralReading({ quiet: true });
        stopReadAloud();
        const status = document.getElementById('saveStatus');
        const continueButton = document.getElementById('continueButton');
        if (status) status.textContent = 'Saving your reading progress…';
        if (continueButton) continueButton.removeAttribute('href');
        const saved = await saveCompletion();
        if (!saved) {
            setOralStatus('Reading progress was not saved', 'Please try finishing the story again before leaving.', 'error');
            if (continueButton) {
                continueButton.textContent = 'Retry Save';
                continueButton.href = '#';
            }
            return;
        }
        showCompletionScreen();
        if (continueButton) {
            continueButton.textContent = 'Continue the Adventure →';
            continueButton.href = story.return_url || '/dashboard/';
        }
    }
    function visibleStoryText() {
        const start = visibleStart();
        return pages.slice(start, start + step()).join(' ');
    }
    function setReadAloudState(active, loading = false) {
        speaking = active;
        listenButton.setAttribute('aria-pressed', String(active));
        listenButton.toggleAttribute('disabled', loading);
        listenButton.innerHTML = loading
            ? '<i class="bi bi-hourglass-split"></i><span>Loading audio</span>'
            : active
                ? '<i class="bi bi-stop-circle"></i><span>Stop Listening</span>'
                : '<i class="bi bi-volume-up"></i><span>Listen to Story</span>';
    }
    function stopReadAloud() {
        readAloudRequestVersion += 1;
        readAloudController?.abort();
        readAloudController = null;
        if (readAloudAudio) { readAloudAudio.pause(); readAloudAudio.currentTime = 0; }
        if (readAloudAudioUrl) URL.revokeObjectURL(readAloudAudioUrl);
        readAloudAudio = null;
        readAloudAudioUrl = '';
        readAloudLoading = false;
        document.querySelectorAll('.story-sentence.is-speaking').forEach(element => element.classList.remove('is-speaking'));
        setReadAloudState(false);
    }
    function base64ToBlob(base64Value, mimeType) {
        const binary = atob(base64Value || '');
        const bytes = new Uint8Array(binary.length);
        for (let index = 0; index < binary.length; index += 1) bytes[index] = binary.charCodeAt(index);
        return new Blob([bytes], { type: mimeType });
    }
    async function toggleListen() {
        if (speaking) { stopReadAloud(); return; }
        if (readAloudLoading || oralActive || oralStarting) return;
        readAloudLoading = true;
        const requestVersion = ++readAloudRequestVersion;
        readAloudController = new AbortController();
        setReadAloudState(false, true);
        const formData = new FormData();
        formData.append('target_text', visibleStoryText());
        formData.append('mode', 'paragraph');
        formData.append('language', story.language || '');
        try {
            const response = await fetch('/api/reading/read-aloud/', {
                method: 'POST', credentials: 'same-origin',
                headers: { 'X-CSRFToken': getCsrfToken() }, body: formData,
                signal: readAloudController.signal
            });
            const data = await response.json();
            if (requestVersion !== readAloudRequestVersion || completed) return;
            if (!response.ok || !data.success) throw new Error(data.error || 'Listen to Story is unavailable.');
            readAloudAudioUrl = URL.createObjectURL(base64ToBlob(data.audio_content, data.mime_type || 'audio/mpeg'));
            readAloudAudio = new Audio(readAloudAudioUrl);
            readAloudAudio.onended = stopReadAloud;
            readAloudAudio.onerror = stopReadAloud;
            setReadAloudState(true);
            await readAloudAudio.play();
        } catch (error) {
            if (error?.name === 'AbortError') return;
            stopReadAloud();
            setOralStatus('Audio assistance is unavailable', error.message || 'Please try again.', 'error');
        } finally {
            if (requestVersion === readAloudRequestVersion) {
                readAloudLoading = false;
                readAloudController = null;
            }
        }
    }

    function setOralStatus(heading, detail, state = 'idle') {
        oralReadingStatus.textContent = heading;
        oralReadingDetail.textContent = detail;
        app.dataset.oralState = state;
    }
    function setOralButton(active) {
        oralReadingButton.setAttribute('aria-pressed', String(active));
        oralReadingButton.innerHTML = active
            ? '<span class="oral-reading-icon"><i class="bi bi-stop-fill"></i></span><span class="oral-reading-label">Stop Reading</span>'
            : '<span class="oral-reading-icon"><i class="bi bi-mic-fill"></i></span><span class="oral-reading-label">Start Reading</span>';
    }
    function oralContext() {
        return { version: oralContextVersion, spread: spreadIndex, targetText: visibleStoryText() };
    }
    function isCurrentOralContext(context) {
        return oralActive && context && context.version === oralContextVersion && context.spread === spreadIndex && context.targetText === visibleStoryText();
    }
    function pickAudioMimeType() {
        return ['audio/webm;codecs=opus','audio/webm','audio/ogg;codecs=opus','audio/ogg']
            .find(type => window.MediaRecorder?.isTypeSupported?.(type)) || '';
    }
    function audioExtension(blob) {
        const type = String(blob?.type || '').toLowerCase();
        if (type.includes('ogg')) return 'ogg';
        if (type.includes('wav')) return 'wav';
        return 'webm';
    }
    async function startOralReading() {
        if (oralActive || oralStarting || completed || !visibleStoryText().trim()) return;
        if (!navigator.mediaDevices?.getUserMedia || !window.MediaRecorder) {
            setOralStatus('Microphone reading is unavailable', 'Use a current Chrome or Edge browser.', 'error');
            return;
        }
        stopReadAloud();
        oralStarting = true;
        oralReadingButton.disabled = true;
        setOralStatus('Requesting microphone access…', 'Choose Allow so I can listen to you read.', 'starting');
        try {
            oralStream = await navigator.mediaDevices.getUserMedia({ audio: {
                echoCancellation: true, noiseSuppression: false, autoGainControl: true
            }});
            if (!visibleStoryText().trim() || completed) {
                oralStream.getTracks().forEach(track => track.stop());
                oralStream = null;
                return;
            }
            oralActive = true;
            oralStopping = false;
            oralContextVersion += 1;
            setOralButton(true);
            setOralStatus('I’m listening', 'Read the story aloud. Turn the page when you are ready.', 'listening');
            startOralChunk();
            oralChunkTimer = window.setInterval(finishOralChunk, SPEECH_CHUNK_MS);
        } catch (error) {
            const denied = error?.name === 'NotAllowedError' || error?.name === 'PermissionDeniedError';
            setOralStatus(denied ? 'Microphone permission was not allowed' : 'Microphone could not start', denied ? 'Allow microphone access, then press Start Reading again.' : 'Check your microphone and try again.', 'error');
        } finally { oralStarting = false; oralReadingButton.disabled = visibleStart() === 0; }
    }
    function startOralChunk() {
        if (!oralStream || oralStopping || !oralActive || oralRecorder) return;
        const context = oralContext();
        const mimeType = pickAudioMimeType();
        const chunks = [];
        let recorder;
        try { recorder = new MediaRecorder(oralStream, mimeType ? { mimeType } : undefined); }
        catch (error) { setOralStatus('Microphone recording had trouble', 'Stop reading, then try again.', 'error'); return; }
        oralRecorder = recorder;
        recorder.ondataavailable = event => { if (event.data?.size) chunks.push(event.data); };
        recorder.onerror = () => setOralStatus('Microphone recording had trouble', 'Stop reading, then try again.', 'error');
        recorder.onstop = async () => {
            if (oralRecorder === recorder) oralRecorder = null;
            const shouldContinue = !oralStopping && isCurrentOralContext(context);
            if (shouldContinue) startOralChunk();
            if (chunks.length && isCurrentOralContext(context)) {
                await sendOralChunk(new Blob(chunks, { type: recorder.mimeType || mimeType || 'audio/webm' }), context);
            }
        };
        recorder.start();
    }
    function finishOralChunk() {
        if (!oralRecorder || oralRecorder.state !== 'recording') return;
        try { oralRecorder.requestData(); oralRecorder.stop(); } catch (error) {}
    }
    function stopOralReading({ quiet = false } = {}) {
        oralStopping = true;
        oralActive = false;
        oralContextVersion += 1;
        if (oralPageCompletionTimer) { window.clearTimeout(oralPageCompletionTimer); oralPageCompletionTimer = null; }
        if (oralChunkTimer) { window.clearInterval(oralChunkTimer); oralChunkTimer = null; }
        try { if (oralRecorder && oralRecorder.state !== 'inactive') { oralRecorder.requestData(); oralRecorder.stop(); } } catch (error) {}
        oralStream?.getTracks().forEach(track => track.stop());
        oralStream = null;
        oralRecorder = null;
        pendingOralChunks = [];
        oralRequestSerial += 1;
        oralSending = false;
        oralRequestController?.abort();
        oralRequestController = null;
        document.querySelectorAll('.story-sentence.is-user-reading').forEach(element => element.classList.remove('is-user-reading'));
        setOralButton(false);
        if (!quiet) setOralStatus('Reading stopped', 'Press Start Reading when you are ready to continue.', 'idle');
    }
    function normalizeReadingToken(value) {
        return String(value || '').normalize('NFKD').toLocaleLowerCase()
            .replace(/[\u2018\u2019]/g, "'").replace(/[^\p{L}\p{N}']/gu, '');
    }
    function editDistanceWithinOne(left, right) {
        if (left === right) return true;
        if (Math.abs(left.length - right.length) > 1) return false;
        let first = left; let second = right;
        if (first.length > second.length) [first, second] = [second, first];
        let firstIndex = 0; let secondIndex = 0; let edits = 0;
        while (firstIndex < first.length && secondIndex < second.length) {
            if (first[firstIndex] === second[secondIndex]) { firstIndex += 1; secondIndex += 1; continue; }
            edits += 1;
            if (edits > 1) return false;
            if (first.length === second.length) firstIndex += 1;
            secondIndex += 1;
        }
        return true;
    }
    function tokensMatch(spoken, target) {
        if (!spoken || !target) return false;
        return spoken === target || (spoken.length >= 5 && target.length >= 5 && editDistanceWithinOne(spoken, target));
    }
    function cursorFromTranscript(transcript) {
        const targetWords = Array.from(leftPage.querySelectorAll('.story-word')).map(word => normalizeReadingToken(word.textContent));
        const spokenWords = String(transcript || '').match(/[\p{L}\p{N}]+(?:[\u2019'][\p{L}\p{N}]+)*/gu)?.map(normalizeReadingToken).filter(Boolean) || [];
        let targetIndex = Math.min(oralWordIndex, targetWords.length);
        let spokenIndex = 0;
        while (targetIndex < targetWords.length && spokenIndex < spokenWords.length) {
            let matchIndex = -1;
            for (let candidate = spokenIndex; candidate < Math.min(spokenWords.length, spokenIndex + 3); candidate += 1) {
                if (tokensMatch(spokenWords[candidate], targetWords[targetIndex])) { matchIndex = candidate; break; }
            }
            if (matchIndex < 0) break;
            targetIndex += 1;
            spokenIndex = matchIndex + 1;
        }
        return targetIndex;
    }
    function highlightOralProgress(wordIndex) {
        oralWordIndex = Math.max(oralWordIndex, Number(wordIndex || 0));
        const words = leftPage.querySelectorAll('.story-word');
        words.forEach((word, index) => {
            word.classList.toggle('is-read', index < oralWordIndex);
            word.classList.toggle('is-current', index === oralWordIndex);
        });
        if (oralActive && words.length > 0 && oralWordIndex >= words.length) schedulePageCompletion();
    }
    function schedulePageCompletion() {
        if (oralPageCompletionTimer || !oralActive) return;
        setOralStatus('Page complete', 'Turning the page…', 'listening');
        oralPageCompletionTimer = window.setTimeout(() => {
            oralPageCompletionTimer = null;
            if (!oralActive || completed || oralWordIndex < leftPage.querySelectorAll('.story-word').length) return;
            if (spreadIndex >= spreadTotal() - 1) finishStory();
            else turn(1);
        }, 700);
    }
    async function sendOralChunk(blob, context) {
        if (!isCurrentOralContext(context)) return;
        if (oralSending) {
            pendingOralChunks.push({ blob, context });
            return;
        }
        oralSending = true;
        const requestSerial = ++oralRequestSerial;
        const formData = new FormData();
        formData.append('audio', blob, `story-reading-${Date.now()}.${audioExtension(blob)}`);
        formData.append('target_text', context.targetText);
        formData.append('current_syllable_index', String(oralSyllableIndex));
        formData.append('mode', 'paragraph');
        formData.append('language', story.language || '');
        const controller = new AbortController();
        oralRequestController = controller;
        const timeout = window.setTimeout(() => controller.abort(), SPEECH_REQUEST_TIMEOUT_MS);
        try {
            const response = await fetch('/api/reading/transcribe/', {
                method: 'POST', credentials: 'same-origin', signal: controller.signal,
                headers: { 'Accept':'application/json','X-Requested-With':'XMLHttpRequest','X-CSRFToken':getCsrfToken() },
                body: formData
            });
            const data = await response.json();
            if (!response.ok || !data.success) throw new Error(data.error || 'Speech check failed.');
            if (!isCurrentOralContext(context)) return;
            oralSyllableIndex = Math.max(oralSyllableIndex, Number(data.current_syllable_index || 0));
            const transcriptCursor = cursorFromTranscript(data.raw_transcript || data.transcript || '');
            if (transcriptCursor > Number(data.current_word_index || 0)) {
                const completedRange = data.word_syllable_ranges?.[transcriptCursor - 1];
                if (Array.isArray(completedRange)) oralSyllableIndex = Math.max(oralSyllableIndex, Number(completedRange[1] || 0));
            }
            highlightOralProgress(Math.max(Number(data.current_word_index || data.correct_word_count || 0), transcriptCursor));
            setOralStatus('I’m listening', data.transcript ? `I heard: “${data.transcript}”` : 'Keep reading clearly. I’m still listening.', 'listening');
        } catch (error) {
            if (isCurrentOralContext(context)) setOralStatus('I’m still listening', error?.name === 'AbortError' ? 'Speech processing took longer than expected. Keep reading; the next chunk will retry.' : 'I had trouble hearing that part. Keep reading clearly.', 'listening');
        } finally {
            window.clearTimeout(timeout);
            if (requestSerial !== oralRequestSerial) return;
            if (oralRequestController === controller) oralRequestController = null;
            oralSending = false;
            while (pendingOralChunks.length && !isCurrentOralContext(pendingOralChunks[0].context)) {
                pendingOralChunks.shift();
            }
            const pending = pendingOralChunks.shift();
            if (pending) sendOralChunk(pending.blob, pending.context);
        }
    }

    previousButton.addEventListener('click', () => turn(-1));
    nextButton.addEventListener('click', () => turn(1));
    listenButton.addEventListener('click', toggleListen);
    oralReadingButton.addEventListener('click', () => oralActive ? stopOralReading() : startOralReading());
    document.addEventListener('keydown', event => { if (event.key === 'ArrowLeft') turn(-1); if (event.key === 'ArrowRight') turn(1); });
    mobileQuery.addEventListener?.('change', paginateIntelligently);
    let resizeTimer = 0;
    new ResizeObserver(() => {
        window.clearTimeout(resizeTimer);
        resizeTimer = window.setTimeout(paginateIntelligently, 120);
    }).observe(book);
    window.addEventListener('beforeunload', () => { stopOralReading({ quiet: true }); stopReadAloud(); });
    paginateIntelligently();
    if (story.completion?.completed) {
        const status = document.getElementById('saveStatus');
        if (status) status.textContent = 'Your reading progress is saved.';
        showCompletionScreen();
    }
})();
