console.error('STORY_READING_PLAYER_JS_LOADED_TEST');
(() => {
    'use strict';
    const data = JSON.parse(document.getElementById('story-reading-data')?.textContent || '{}');
    const app = document.getElementById('storyPlayerApp');
    const image = document.getElementById('sceneImage');
    const subtitle = document.getElementById('storySubtitle');
    const progress = document.getElementById('storyTimeline');
    const fill = document.getElementById('timelineFill');
    const currentTime = document.getElementById('currentTime');
    const durationLabel = document.getElementById('durationLabel');
    const playButton = document.getElementById('playButton');
    const playbackButton = document.getElementById('playbackButton');
    const previousButton = document.getElementById('previousScene');
    const mediaViewport = document.querySelector('.media-viewport');
    const muteButton = document.getElementById('muteButton');
    const listenButton = muteButton;
    const oralButton = playButton;
    const status = document.getElementById('readingStatus');
    const progressText = document.getElementById('storyProgressText');
    const scenes = String(data.text || '').split(/\n\s*\n/).map(text => text.trim()).filter(Boolean);
    const images = Array.isArray(data.images) ? data.images : [];
    const storyKey = data.story_key || (String(data.language).toLowerCase() === 'filipino' ? 'filipino-set-1' : data.title || 'story');
    const sceneDuration = 12;
    const totalSentences = scenes.length;
    const totalDuration = scenes.length * sceneDuration;
    const storageKey = `pabasa-story-player:${data.material_id || data.id}:${data.section_id || 'default'}:${storyKey}`;
    const state = { time: 0, playing: false, muted: false, scene: 1, completed: false, oral: false, readingCursor: 0, correctSentences: 0, readingScore: 0, context: 0 };
    let frame = 0;
    let lastFrameTime = 0;
    let saveTimer = 0;
    let ttsAudio = null;
    let ttsUrl = '';
    let ttsController = null;
    let stream = null;
    let recorder = null;
    let chunkTimer = 0;
    let sending = false;
    let pending = [];
    let requestSerial = 0;
    let oralSessionSerial = 0;
    let activeOralSession = 0;
    let requestController = null;
    const debugAudio = (message, details = {}) => console.debug(`[Story Reading] ${message}`, {session: activeOralSession, ...details});
    const escapeHtml = value => String(value || '').replace(/[&<>'"]/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[char]));
    const csrf = () => document.cookie.split(';').map(value => value.trim()).find(value => value.startsWith('csrftoken='))?.split('=').slice(1).join('=') || '';
    const formatTime = value => { const seconds = Math.max(0, Math.floor(value || 0)); return `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, '0')}`; };
    const token = value => String(value || '').normalize('NFKD').toLocaleLowerCase().replace(/[\u2018\u2019]/g, "'").replace(/[^\p{L}\p{N}']/gu, '');
    const wordsIn = text => String(text || '').match(/[\p{L}\p{N}]+(?:[\u2019'][\p{L}\p{N}]+)*/gu) || [];
    const wordMarkup = text => wordsIn(text).map((word, index) => `<span class="story-word" data-word-index="${index}">${escapeHtml(word)}</span>`).join(' ');
    const imageFor = scene => images[scene - 1] || `/static/pabasa_app/images/story_reading/Filipino/Set_1/${scene}.png`;
    const saveState = (completed = state.completed) => {
        const payload = { material_id: data.material_id || data.id, story_key: storyKey, story_title: data.title, total_words: scenes.join(' ').split(/\s+/).filter(Boolean).length, words_read: 0, progress_percent: totalDuration ? Math.round(state.time / totalDuration * 100) : 0, correct_sentences: state.correctSentences, reading_score: state.readingScore, duration_seconds: Math.round(state.time), current_scene: state.scene, current_time_seconds: state.time, completed };
        window.clearTimeout(saveTimer);
        const request = () => fetch('/api/story-reading/complete/', { method:'POST', credentials:'same-origin', headers:{'Content-Type':'application/json','X-CSRFToken':csrf()}, body:JSON.stringify(payload) });
        if (completed) return request();
        saveTimer = window.setTimeout(() => request().catch(() => {}), 350);
        return Promise.resolve(null);
    };
    const saveAssessmentCompletion = () => fetch('/record-assessment-completion/', {
        method: 'POST', credentials: 'same-origin',
        headers: {'Content-Type':'application/json','X-CSRFToken':csrf()},
        body: JSON.stringify({
            material_id: data.material_id || data.id,
            activity_type: 'story_reading',
            assessment_type: 'paragraph',
            items_completed: totalSentences,
            correct_items: state.correctSentences,
            accuracy: state.readingScore,
            total_score: state.readingScore,
            duration_seconds: Math.round(state.time),
            scores: {
                correct_items: state.correctSentences,
                items_completed: totalSentences,
                accuracy: state.readingScore,
                total_score: state.readingScore,
                duration_seconds: Math.round(state.time),
            },
        }),
    });
    const restoreState = () => {
        let saved = null;
        try { saved = JSON.parse(localStorage.getItem(storageKey) || 'null'); } catch (error) {}
        const server = data.completion || {};
        // A completed Story Reading record belongs to a prior attempt.  Do
        // not turn opening this activity into an already-completed session.
        // Completion is established only by the current End Activity action.
        if (server.completed || saved?.completed) {
            try { localStorage.removeItem(storageKey); } catch (error) {}
            state.time = 0;
            state.scene = 1;
            state.completed = false;
            state.correctSentences = 0;
            state.readingScore = 0;
            return;
        }
        state.time = Math.min(totalDuration, Math.max(0, Number(server.current_time_seconds ?? saved?.time) || 0));
        state.scene = Math.min(scenes.length, Math.max(1, Number(server.current_scene ?? saved?.scene) || Math.floor(state.time / sceneDuration) + 1));
        state.completed = Boolean(server.completed || saved?.completed);
        state.correctSentences = Math.max(0, Math.min(totalSentences, Number(server.correct_sentences ?? saved?.correctSentences) || 0));
        // The raw sentence count is the source of truth; older rows may have
        // stored a percentage in reading_score.
        state.readingScore = state.correctSentences;
    };
    const persist = () => { try { localStorage.setItem(storageKey, JSON.stringify({time:state.time, scene:state.scene, completed:state.completed, correctSentences:state.correctSentences, readingScore:state.readingScore})); } catch (error) {} return saveState(); };
    const liveComments = { feed: null, lastEvent: '' };
    function addLiveComment(event) {
        if (!liveComments.feed || liveComments.lastEvent === event) return;
        const score = Number(state.readingScore || 0);
        const highScore = totalSentences > 0 && score >= Math.ceil(totalSentences * 0.8);
        const isFilipino = /^(fil|tag)/i.test(String(data.language || '').trim());
        const nearCompletion = state.correctSentences >= Math.max(1, totalSentences - 1);
        const commentMap = isFilipino ? {
            welcome: ['ReadingBuddy', 'Handa na ang iyong kuwento—basahin lang nang dahan-dahan! 📚'],
            listening: ['Kaibigang Mambabasa', 'Nakikinig kami. Isa-isang salita lang! 👂'],
            progress: ['Bituing Mambabasa', nearCompletion ? 'Malapit na matapos! Ang galing mo! 🌟' : highScore ? 'Napakalinaw ng pagbasa! Ituloy mo lang! 👏' : 'Magandang simula! Ituloy mo lang! 💪'],
            encouragement: ['ReadingBuddy', 'Walang problema—dahan-dahan lang. Kaya mo ito! 🌟'],
            complete: ['Kaibigang Mambabasa', highScore ? 'Natapos mo ang kuwento! Ang galing ng pagbasa mo! 🎉' : 'Natapos mo ang kuwento! Magpatuloy lang sa pagsasanay! 🌟'],
        } : {
            welcome: ['ReadingBuddy', 'Your story is ready—take your time! 📚'],
            listening: ['StarReader', 'We’re listening. Read one word at a time! 👂'],
            progress: ['BookFriend', nearCompletion ? 'You’re almost finished—great reading! 🌟' : highScore ? 'Clear reading! Keep it up! 👏' : 'Great start! Keep going! 💪'],
            encouragement: ['ReadingBuddy', 'No worries—take your time. You can do it! 🌟'],
            complete: ['StarReader', highScore ? 'You finished the story—awesome reading! 🎉' : 'You finished the story—keep practicing! 🌟'],
        };
        const [author, message] = commentMap[event] || commentMap.encouragement;
        const item = document.createElement('article');
        item.className = 'live-comment';
        item.innerHTML = `<span class="live-comment-avatar" aria-hidden="true">${event === 'complete' ? '🎉' : event === 'progress' ? '⭐' : '📚'}</span><div><strong>${author}</strong><p>${message}</p></div>`;
        liveComments.feed.append(item);
        while (liveComments.feed.children.length > 5) liveComments.feed.firstElementChild?.remove();
        liveComments.feed.scrollTop = liveComments.feed.scrollHeight;
        liveComments.lastEvent = event;
    }
    function mountLiveShell() {
        if (!app || app.dataset.liveShellMounted === 'true') return;
        const playerHeader = app.querySelector('.player-header');
        const mediaShell = app.querySelector('.media-shell');
        if (!playerHeader || !mediaShell) return;
        app.dataset.liveShellMounted = 'true';
        app.classList.add('live-story-player');
        document.documentElement.classList.add('live-story-page');
        document.body.classList.add('live-story-page');
        const liveHeader = document.createElement('header');
        liveHeader.className = 'live-app-header';
        const logoUrl = window.pabasaStoryLogoUrl || '/static/pabasa_app/images/pabasalogo.png';
        liveHeader.innerHTML = `<div class="live-brand"><img src="${logoUrl}" alt="PABASA" class="brand-logo-image"><span>Edu<span>PABASA</span></span><b>LIVE</b><em>Story Reading</em></div>`;
        const backLink = playerHeader.querySelector('.back-link');
        if (backLink) {
            if (data.return_url) backLink.href = data.return_url;
            liveHeader.append(backLink);
        }
        if (data.first_name) {
            const profile = document.createElement('div');
            profile.className = 'live-reader-profile';
            profile.innerHTML = `<span aria-hidden="true">👋</span><span>${escapeHtml(data.first_name)}</span>`;
            liveHeader.append(profile);
        }
        const layout = document.createElement('div');
        layout.className = 'live-stream-layout';
        const main = document.createElement('section');
        main.className = 'live-stream-main';
        const chat = document.createElement('aside');
        chat.className = 'live-comments-panel';
        chat.setAttribute('aria-label', 'Active reading comments');
        chat.innerHTML = '<header><span><i aria-hidden="true"></i> Active Comments</span><small>Reading Live</small></header><div class="live-comments-feed" aria-live="polite"></div>';
        app.insertBefore(liveHeader, app.firstChild);
        app.append(layout);
        layout.append(main, chat);
        main.append(mediaShell, playerHeader, status, progressText);
        playerHeader.classList.add('live-story-meta');
        liveComments.feed = chat.querySelector('.live-comments-feed');
        addLiveComment(state.completed ? 'complete' : 'welcome');
    }
    function render() {
        state.scene = Math.min(scenes.length, Math.max(1, Math.floor(Math.min(state.time, Math.max(0, totalDuration - .001)) / sceneDuration) + 1));
        image.src = imageFor(state.scene); image.alt = `Scene ${state.scene} from ${data.title || 'the story'}`;
        subtitle.innerHTML = wordMarkup(scenes[state.scene - 1] || '');
        progress.value = String(state.time); fill.style.width = `${totalDuration ? state.time / totalDuration * 100 : 0}%`;
        currentTime.textContent = formatTime(state.time); durationLabel.textContent = formatTime(totalDuration);
        if (playbackButton) { playbackButton.textContent = state.playing ? '❚❚' : '▶'; playbackButton.setAttribute('aria-label', state.playing ? 'Pause' : 'Play'); }
        progressText.innerHTML = `<strong>Story ${state.scene} of ${scenes.length}</strong> · ${state.scene === scenes.length ? 'Almost at school!' : 'Lito is getting ready!'}`;
        document.querySelectorAll('.scene-marker').forEach((marker, index) => marker.classList.toggle('active', index === state.scene - 1));
        const atFinalEndpoint = totalDuration > 0 && state.time >= totalDuration;
        playButton.innerHTML = atFinalEndpoint
            ? '<i class="bi bi-check-circle-fill" aria-hidden="true"></i><span>End Activity</span><span aria-hidden="true">&rsaquo;</span>'
            : `<i class="bi bi-book-half" aria-hidden="true"></i><span>${state.oral ? 'Reading...' : 'Read With Me'}</span><span aria-hidden="true">&rsaquo;</span>`;
        playButton.setAttribute('aria-label', atFinalEndpoint ? 'End Activity' : (state.oral ? 'Reading' : 'Read With Me'));
        playButton.setAttribute('aria-pressed', String(state.oral));
        playButton.classList.toggle('is-complete-action', atFinalEndpoint);
        listenButton.textContent = ttsAudio ? '🔊 Listening...' : '🔊 Listen to Story';
        listenButton.setAttribute('aria-label', ttsAudio ? 'Listening' : 'Listen to Story');
        listenButton.setAttribute('aria-pressed', String(Boolean(ttsAudio)));
        previousButton.disabled = false;
        if (state.oral) highlight(state.readingCursor);
        debugAudio('Scene rendered', { scene: state.scene, target: scenes[state.scene - 1] || '', time: state.time, oral: state.oral });
    }
    function highlight(cursor) { const nodes = subtitle.querySelectorAll('.story-word'); nodes.forEach((node, index) => { node.classList.toggle('is-read', index < cursor); node.classList.toggle('is-current', index === cursor); }); }
    function tick(now) { if (!state.playing) return; if (!lastFrameTime) lastFrameTime = now; state.time += Math.min(.1, (now - lastFrameTime) / 1000); lastFrameTime = now; if (state.time >= totalDuration) { state.time = totalDuration; state.playing = false; } render(); frame = requestAnimationFrame(tick); }
    function togglePlay() { if (state.completed) return; state.playing = !state.playing; lastFrameTime = 0; if (state.playing) frame = requestAnimationFrame(tick); else cancelAnimationFrame(frame); render(); persist(); }
    function seek(value) { stopTts(); state.time = Math.min(totalDuration, Math.max(0, Number(value) || 0)); state.completed = false; state.readingCursor = 0; render(); persist(); }
    function moveScene(direction) { seek(Math.min(totalDuration - .01, Math.max(0, (state.scene - 1 + direction) * sceneDuration))); }
    function restartStory() { stopOral(true); stopTts(); cancelAnimationFrame(frame); state.playing = false; state.time = 0; state.scene = 1; state.completed = false; state.readingCursor = 0; state.correctSentences = 0; state.readingScore = 0; app.classList.remove('is-complete'); setStatus(''); render(); persist(); }
    function setStatus(message, listening = false) { status.textContent = message; status.classList.toggle('is-listening', listening); const copy = String(message || '').toLowerCase(); if (copy.includes('scene ready')) addLiveComment('progress'); else if (copy.includes('still listening') || copy.includes('try again') || copy.includes('keep reading')) addLiveComment('encouragement'); else if (listening) addLiveComment('listening'); }
    function stopTts() { ttsController?.abort(); ttsController = null; if (ttsAudio) ttsAudio.pause(); if (ttsUrl) URL.revokeObjectURL(ttsUrl); ttsAudio = null; ttsUrl = ''; listenButton.textContent = '🔊 Listen to Story'; listenButton.setAttribute('aria-pressed', 'false'); }
    async function listen() { if (ttsAudio) { stopTts(); return; } if (state.oral) return; const controller = new AbortController(); ttsController = controller; listenButton.textContent = 'Loading…'; const form = new FormData(); form.append('target_text', scenes[state.scene - 1] || ''); form.append('mode', 'paragraph'); form.append('language', data.language || ''); try { const response = await fetch('/api/reading/read-aloud/', {method:'POST', credentials:'same-origin', headers:{'X-CSRFToken':csrf()}, body:form, signal:controller.signal}); const result = await response.json(); if (!response.ok || !result.success) throw new Error(); ttsUrl = URL.createObjectURL(base64ToBlob(result.audio_content, result.mime_type || 'audio/mpeg')); ttsAudio = new Audio(ttsUrl); ttsAudio.muted = state.muted; ttsAudio.onended = stopTts; listenButton.textContent = '🔊 Listening...'; listenButton.setAttribute('aria-pressed', 'true'); await ttsAudio.play(); } catch (error) { if (error.name !== 'AbortError') setStatus('Audio is unavailable right now.'); stopTts(); } }
    function base64ToBlob(value, type) { const binary = atob(value || ''); const bytes = new Uint8Array(binary.length); for (let index=0; index<binary.length; index += 1) bytes[index] = binary.charCodeAt(index); return new Blob([bytes], {type}); }
    function mimeType() { return ['audio/webm;codecs=opus','audio/webm','audio/ogg;codecs=opus'].find(type => MediaRecorder.isTypeSupported?.(type)) || ''; }
    function oralContext() { return {version:state.context, scene:state.scene, text:scenes[state.scene - 1] || '', session:activeOralSession}; }
    function sameContext(context) { return state.oral && context.session === activeOralSession && context.version === state.context && context.scene === state.scene && context.text === scenes[state.scene - 1]; }
    function startChunk() { if (!stream || recorder || !state.oral) { debugAudio('Recorder start skipped', { hasStream: Boolean(stream), recorderState: recorder?.state || null, oral: state.oral, scene: state.scene }); return; } const context = oralContext(); const chunks = []; recorder = new MediaRecorder(stream, mimeType() ? {mimeType:mimeType()} : undefined); const activeRecorder = recorder; debugAudio('Recorder created', { scene: context.scene, target: context.text, state: activeRecorder.state, mimeType: activeRecorder.mimeType }); activeRecorder.ondataavailable = event => { debugAudio('dataavailable', { scene: context.scene, size: event.data?.size || 0, type: event.data?.type || activeRecorder.mimeType, chunks: chunks.length + (event.data?.size ? 1 : 0) }); if (event.data?.size) chunks.push(event.data); }; activeRecorder.onstop = () => { const stillCurrent = sameContext(context); const blob = chunks.length ? new Blob(chunks, {type:activeRecorder.mimeType || 'audio/webm'}) : null; debugAudio('Recorder stopped', { scene: context.scene, chunks: chunks.length, blobSize: blob?.size || 0, blobType: blob?.type || '', stillCurrent, activeState: activeRecorder.state }); if (recorder === activeRecorder) recorder = null; if (blob && blob.size > 0 && stillCurrent) sendChunk(blob, context); if (stillCurrent) { startChunk(); } else if (state.oral && state.scene !== context.scene) { debugAudio('Scene advanced during recording, starting new chunk for scene', { previousScene: context.scene, currentScene: state.scene }); startChunk(); } }; activeRecorder.onerror = event => debugAudio('Recorder error', { scene: context.scene, error: event.error?.message || event.error?.name || 'unknown' }); activeRecorder.start(); debugAudio('Recorder started', { scene: context.scene, state: activeRecorder.state, tracks: stream.getTracks().map(track => ({kind: track.kind, readyState: track.readyState, enabled: track.enabled})) }); }
    function finishChunk() { if (recorder?.state === 'recording') { recorder.requestData(); recorder.stop(); } }
    function stopOral(quiet = false) { debugAudio('Reading stop requested', { scene: state.scene, recorderState: recorder?.state || null, tracks: stream?.getTracks().map(track => ({kind: track.kind, readyState: track.readyState})) || [] }); state.oral = false; state.context += 1; window.clearInterval(chunkTimer); finishChunk(); stream?.getTracks().forEach(track => track.stop()); stream = null; recorder = null; pending = []; requestSerial += 1; requestController?.abort(); requestController = null; oralButton.textContent = '🎙 Read With Me'; oralButton.setAttribute('aria-pressed', 'false'); oralButton.classList.remove('is-active'); setStatus(quiet ? '' : 'Reading paused. Press Read With Me to continue.'); render(); }
    async function startOral() { if (state.oral) { stopOral(); return; } stopTts(); if (!navigator.mediaDevices?.getUserMedia || !window.MediaRecorder) { setStatus('Microphone reading is unavailable in this browser.'); return; } try { activeOralSession = ++oralSessionSerial; debugAudio('Microphone request', { scene: state.scene, session: activeOralSession, target: scenes[state.scene - 1] || '' }); stream = await navigator.mediaDevices.getUserMedia({audio:{echoCancellation:true,noiseSuppression:false,autoGainControl:true}}); debugAudio('Microphone stream acquired', { scene: state.scene, session: activeOralSession, stream: stream.getTracks().some(track => track.readyState === 'live') ? 'live' : 'dead', tracks: stream.getTracks().map(track => ({kind: track.kind, readyState: track.readyState, enabled: track.enabled})) }); state.playing = false; cancelAnimationFrame(frame); state.oral = true; state.context += 1; state.readingCursor = 0; oralButton.textContent = '🎙 Reading...'; oralButton.setAttribute('aria-pressed', 'true'); oralButton.classList.add('is-active'); setStatus('🎙 I’m listening… Read the subtitle aloud.', true); startChunk(); chunkTimer = window.setInterval(finishChunk, 3200); render(); } catch (error) { debugAudio('Microphone start failed', { scene: state.scene, session: activeOralSession, name: error?.name, message: error?.message }); setStatus('Please allow microphone access, then try again.'); } }
    function cursorFromTranscript(transcript) { const target = wordsIn(scenes[state.scene - 1]).map(token); const spoken = wordsIn(transcript).map(token); let cursor = state.readingCursor; let source = 0; while (cursor < target.length && source < spoken.length) { if (spoken.slice(source, source + 3).some(word => word === target[cursor] || (word.length > 4 && target[cursor].length > 4 && word[0] === target[cursor][0]))) cursor += 1; source += 1; } return cursor; }
    async function finishCompletion() { if (state.completionSaving || state.completed) return; state.completionSaving = true; try { state.completed = true; const progressResponse = await persist(); if (!progressResponse?.ok) throw new Error('Story progress was not saved.'); const completionResponse = await saveAssessmentCompletion(); const completion = await completionResponse.json().catch(() => ({})); if (!completionResponse.ok || !completion.success) throw new Error(completion.error || 'Assessment completion was not saved.'); showCompletionModal(); } catch (error) { state.completed = false; persist(); setStatus('Reading progress was not saved. Please finish the story again.', false); } finally { state.completionSaving = false; } }
    async function sendChunk(blob, context) { if (!sameContext(context)) { debugAudio('Chunk rejected before request', { scene: context.scene, size: blob?.size || 0, currentScene: state.scene, currentContext: state.context, requestContext: context.version }); return; } if (sending) { debugAudio('Chunk queued behind request', { scene: context.scene, size: blob?.size || 0 }); pending.push({blob,context}); return; } sending = true; const serial = ++requestSerial; const form = new FormData(); form.append('audio', blob, `story-reading-${Date.now()}.webm`); form.append('target_text', context.text); form.append('current_syllable_index', '0'); form.append('mode', 'paragraph'); form.append('language', data.language || ''); debugAudio('POST transcribe', { scene: context.scene, target: context.text, size: blob.size, type: blob.type, serial }); const controller = new AbortController(); requestController = controller; const timeout = setTimeout(() => controller.abort(), 35000); try { const response = await fetch('/api/reading/transcribe/', {method:'POST', credentials:'same-origin', signal:controller.signal, headers:{Accept:'application/json','X-Requested-With':'XMLHttpRequest','X-CSRFToken':csrf()}, body:form}); const result = await response.json(); debugAudio('Transcription response', { scene: context.scene, status: response.status, success: result.success, transcript: result.transcript || '', rawTranscript: result.raw_transcript || '', currentWordIndex: result.current_word_index, correctWordCount: result.correct_word_count, serial }); if (!response.ok || !result.success) throw new Error(); if (sameContext(context)) { state.readingCursor = Math.max(state.readingCursor, Number(result.current_word_index || result.correct_word_count || 0), cursorFromTranscript(result.raw_transcript || result.transcript || '')); highlight(state.readingCursor); if (state.readingCursor >= wordsIn(context.text).length) { debugAudio('Sentence complete', { scene: context.scene, target: context.text, cursor: state.readingCursor }); state.correctSentences = Math.min(totalSentences, state.correctSentences + 1); state.readingScore = state.correctSentences; persist(); stopOral(true); if (state.scene >= scenes.length) { state.time = totalDuration; render(); setStatus('Story ready to finish. Press End Activity to complete.'); } else { const nextTime = state.scene * sceneDuration + .02; const nextContextVersion = state.context; mediaViewport?.classList.add('is-transitioning'); window.setTimeout(() => { if (state.completed || state.context !== nextContextVersion) return; state.time = nextTime; state.readingCursor = 0; mediaViewport?.classList.remove('is-transitioning'); render(); setStatus('Scene ready. Press Read With Me to continue.'); }, 350); } } } else { debugAudio('TRANSCRIPT DISCARDED', { scene: context.scene, currentScene: state.scene, reason: 'context-mismatch', currentContext: state.context, responseContext: context.version, serial }); } } catch (error) { debugAudio('Transcription request failed', { scene: context.scene, name: error?.name, message: error?.message, serial }); if (sameContext(context)) setStatus('🎙 I’m still listening… Keep reading clearly.', true); } finally { clearTimeout(timeout); if (requestController === controller) requestController = null; sending = false; const next = pending.shift(); if (next && sameContext(next.context)) sendChunk(next.blob, next.context); else if (next) debugAudio('TRANSCRIPT DISCARDED', { scene: next.context.scene, currentScene: state.scene, reason: 'queued-context-mismatch', currentContext: state.context, requestContext: next.context.version }); } }
    function updateFullscreenButton() {
        return;
    }
    async function listenOneSegment() {
        if (ttsAudio) { stopTts(); return; }
        if (state.oral || state.scene > scenes.length) return;
        const segmentStart = Math.min(totalDuration, Math.max(0, (state.scene - 1) * sceneDuration));
        const segmentEnd = Math.min(totalDuration, state.scene * sceneDuration);
        state.time = segmentStart;
        render();
        const controller = new AbortController();
        ttsController = controller;
        listenButton.textContent = 'Loading…';
        const form = new FormData();
        form.append('target_text', scenes[state.scene - 1] || '');
        form.append('mode', 'paragraph');
        form.append('language', data.language || '');
        try {
            const response = await fetch('/api/reading/read-aloud/', {method:'POST', credentials:'same-origin', headers:{'X-CSRFToken':csrf()}, body:form, signal:controller.signal});
            const result = await response.json();
            if (!response.ok || !result.success) throw new Error();
            ttsUrl = URL.createObjectURL(base64ToBlob(result.audio_content, result.mime_type || 'audio/mpeg'));
            ttsAudio = new Audio(ttsUrl);
            ttsAudio.muted = state.muted;
            const stopAtNextMarker = () => {
                if (!ttsAudio || !Number.isFinite(ttsAudio.duration)) return;
                const progressRatio = Math.min(1, ttsAudio.currentTime / ttsAudio.duration);
                state.time = segmentStart + (segmentEnd - segmentStart) * progressRatio;
                render();
                if (state.time >= segmentEnd) {
                    ttsAudio.pause();
                    ttsAudio.currentTime = ttsAudio.duration;
                    ttsAudio.onended?.();
                }
            };
            ttsAudio.ontimeupdate = stopAtNextMarker;
            ttsAudio.onended = () => {
                state.time = segmentEnd;
                if (ttsAudio) ttsAudio.ontimeupdate = null;
                stopTts();
                render();
                persist();
            };
            listenButton.textContent = '🔊 Listening...';
            listenButton.setAttribute('aria-pressed', 'true');
            await ttsAudio.play();
        } catch (error) {
            if (error.name !== 'AbortError') setStatus('Audio is unavailable right now.');
            stopTts();
        }
    }
    function showCompletionModal() {
        let modal = document.getElementById('storyScoreModal');
        if (!modal) {
            const style = document.createElement('style');
            style.textContent = '.story-score-modal{position:fixed;inset:0;z-index:20;display:grid;place-items:center;padding:16px;background:rgba(3,18,34,.78);backdrop-filter:blur(4px)}.story-score-modal[hidden]{display:none}.story-score-card{position:relative;width:min(490px,100%);padding:30px 30px 25px;border:1px solid rgba(76,214,224,.42);border-radius:24px;background:linear-gradient(145deg,#102c46,#071c31);box-shadow:0 0 0 1px rgba(39,185,201,.08),0 24px 70px rgba(0,0,0,.48),0 0 35px rgba(22,151,174,.16);color:#f5fbff;text-align:center;overflow:hidden}.story-score-card:before{content:"";position:absolute;inset:0;background:radial-gradient(circle at 50% 0,rgba(40,201,208,.16),transparent 42%);pointer-events:none}.story-score-close{position:absolute;z-index:1;top:12px;right:16px;border:0;background:transparent;color:#e4f6fb;font-size:1.8rem;line-height:1;cursor:pointer}.story-score-icon{position:relative;display:grid;place-items:center;width:64px;height:64px;margin:0 auto 14px;border:2px solid #48d4d0;border-radius:50%;background:linear-gradient(145deg,#39cfc5,#138b9b);box-shadow:0 0 24px rgba(54,213,208,.4);color:#fff;font-size:2rem;font-weight:900}.story-score-card h2{position:relative;margin:0 0 4px;font-size:1.75rem}.story-score-great{position:relative;margin:0 0 22px;color:#fff;font-size:1.2rem;font-weight:900}.story-score-label{position:relative;margin:0;color:#41d1c7;font-size:1rem;font-weight:900}.story-score-value{position:relative;margin:3px 0 8px;color:#49d8d1;font-size:4rem;font-weight:900;line-height:1;text-shadow:0 0 18px rgba(54,213,208,.28)}.story-score-message{position:relative;margin:0 0 25px;color:#edf8fc;font-size:.98rem}.story-score-done,.story-score-back{position:relative;width:100%;min-height:50px;border-radius:14px;font:inherit;font-weight:900;cursor:pointer}.story-score-done{border:1px solid #24c5c0;background:linear-gradient(135deg,#12b7ac,#168d9c);color:#fff;box-shadow:0 8px 20px rgba(7,190,183,.22)}.story-score-back{margin-top:11px;border:1px solid rgba(213,240,247,.75);background:transparent;color:#f4fbff}.story-score-done:hover,.story-score-done:focus-visible{background:#18c9bf;outline:3px solid rgba(72,212,208,.3);outline-offset:2px}.story-score-back:hover,.story-score-back:focus-visible{background:rgba(255,255,255,.08);outline:3px solid rgba(185,232,239,.2);outline-offset:2px}@media(max-width:520px){.story-score-card{padding:28px 20px 20px}.story-score-value{font-size:3.4rem}.story-score-card h2{font-size:1.5rem}}';
            style.textContent += '.story-score-done:disabled{opacity:.45;cursor:not-allowed;box-shadow:none}.story-score-done:disabled:hover,.story-score-done:disabled:focus-visible{background:linear-gradient(135deg,#12b7ac,#168d9c);outline:none}';
            document.head.appendChild(style);
            modal = document.createElement('div');
            modal.id = 'storyScoreModal'; modal.className = 'story-score-modal'; modal.hidden = true;
            modal.setAttribute('role', 'dialog'); modal.setAttribute('aria-modal', 'true'); modal.setAttribute('aria-labelledby', 'storyScoreTitle');
            modal.innerHTML = `<section class="story-score-card"><button class="story-score-close" type="button" aria-label="Close score">&times;</button><div class="story-score-icon" aria-hidden="true">★</div><p class="story-score-great">Great job!</p><h2 id="storyScoreTitle">Activity Complete!</h2><p class="story-score-label">Your Score</p><p class="story-score-value">${state.correctSentences} / ${totalSentences}</p><p class="story-score-message">Keep it up! You\'re doing amazing! 🎉</p><button class="story-score-done" type="button" disabled>Proceed to 5W\'s Questions <span aria-hidden="true">→</span></button><button class="story-score-back" type="button">Back on Reading Assessment Page</button></section>`;
            document.body.appendChild(modal);
            const close = () => { modal.hidden = true; document.body.style.overflow = ''; };
            const returnToAssessment = () => { close(); window.location.assign(data.return_url || '/dashboard/assessment/'); };
            modal.querySelector('.story-score-close').onclick = returnToAssessment;
            modal.querySelector('.story-score-done').onclick = () => { close(); window.location.assign(`/dashboard/assessment/story-call?id=${encodeURIComponent(data.material_id || data.id || '')}&section_id=${encodeURIComponent(data.section_id || '')}`); };
            modal.querySelector('.story-score-back').onclick = returnToAssessment;
            modal.onclick = event => { if (event.target === modal) close(); };
        }
        const proceedButton = modal.querySelector('.story-score-done');
        proceedButton.disabled = true;
        modal.hidden = false; document.body.style.overflow = 'hidden'; proceedButton.focus();
        fetch(`/api/class/materials/?section_id=${encodeURIComponent(data.section_id || '')}`, { credentials: 'same-origin', headers: { Accept: 'application/json' } })
            .then(response => response.json()).then(payload => {
                const materials = Object.values(payload.materials || {}).flat();
                const normalizeMaterialId = value => String(value ?? '').trim().replace(/^material-/, '');
                const storyId = normalizeMaterialId(data.material_id || data.id);
                const available = materials.some(material => { const content = material?.content_json || {}; return String(material?.status || '').toLowerCase() === 'published' && String(content.template_title || '').trim() === "5W's Story Questions" && normalizeMaterialId(content.sourceMaterialId || content.source_material_id) === storyId; });
                proceedButton.disabled = !available;
            }).catch(() => { proceedButton.disabled = true; });
    }
    function endActivity() { finishCompletion(); }
    progress.oninput = event => seek(event.target.value); previousButton.onclick = restartStory; listenButton.onclick = listenOneSegment; oralButton.onclick = () => { if (state.time >= totalDuration) endActivity(); else startOral(); }; document.querySelectorAll('.scene-marker').forEach(marker => marker.onclick = () => seek(marker.dataset.time));
    window.addEventListener('beforeunload', () => { persist(); stopOral(true); stopTts(); });
    restoreState(); mountLiveShell(); render();
})();
