(function () {
    console.log("PABASA: Assessment Reader script loaded.");

    const initReader = () => {
        const shell = document.querySelector(".reader-shell");
        if (!shell) return;

        let mode = 'word'; 
        if (shell.classList.contains('reader-sentence')) mode = 'sentence';
        if (shell.classList.contains('reader-paragraph')) mode = 'paragraph';

        const readingWord = document.getElementById("readingWord");
        const counter = document.getElementById("counter");
        const progressFill = document.getElementById("progressFill");
        const prevBtn = document.getElementById("prevBtn");
        const nextBtn = document.getElementById("nextBtn");
        const testMeta = document.getElementById("testMeta");
        const pauseBtn = document.getElementById("pauseBtn");
        const pauseOverlay = document.getElementById("pauseOverlay");
        const pauseMenu = document.getElementById("pauseMenu");
        const resumeBtn = document.getElementById("resumeBtn");
        const retryBtn = document.getElementById("retryBtn");
        const quitBtn = document.getElementById("quitBtn");
        const reviewBtn = document.getElementById("reviewBtn");
        const finishBtn = document.getElementById("finishBtn");
        const completionCount = document.getElementById("completionCount");
        const completionLevel = document.getElementById("completionLevel");
        const btnStartReading = document.getElementById("btnStartReading");
        const btnStopReading = document.getElementById("btnStopReading");
        const btnReadAloud = document.getElementById("btnReadAloud");
        const liveCountdownOverlay = document.getElementById("liveCountdownOverlay");
        const liveCountdownNumber = document.getElementById("liveCountdownNumber");
        const liveCountdownSubtext = document.getElementById("liveCountdownSubtext");
        const btnToggleMic = document.getElementById("btnToggleMic");
        const btnTestMic = document.getElementById("btnTestMic") || document.getElementById("testMic");
        const micTestOverlay = document.getElementById("micTestOverlay");
        const micTestCloseBtn = document.getElementById("micTestCloseBtn");
        const micSampleRecordBtn = document.getElementById("micSampleRecordBtn");
        const micSamplePlayBtn = document.getElementById("micSamplePlayBtn");
        const micTestStatus = document.getElementById("micTestStatus");
        const micDeviceSelect = document.getElementById("micDeviceSelect");
        const rawMicInput = document.getElementById("rawMicInput");

        const urlParams = new URLSearchParams(window.location.search);
        const testTitle = urlParams.get("test") || "Assessment";
        const testCode = urlParams.get("code") || "TST-000";
        const materialId = urlParams.get("id");
        const viewMode = urlParams.get("viewMode");
        const liveContent = urlParams.get("content") || "";
        const liveItemType = (urlParams.get("item_type") || urlParams.get("type") || "").toLowerCase();
        const liveLanguage = urlParams.get("language") || "";
        const isReviewMode = viewMode === "view";
        const isRetakeMode = viewMode === "retake";
        if (testMeta) testMeta.textContent = `${testTitle} - ${testCode}`;

        function isCurrentLiveAssessment() {
            if (isReviewMode || isRetakeMode) return false;
            const liveParam = urlParams.get('live');
            const liveSessionId = urlParams.get('live_session_id');
            const countdown = Number.parseInt(urlParams.get('countdown') || '10', 10);
            return liveParam === '1' && Boolean(liveSessionId) && Number.isFinite(countdown) && countdown > 0;
        }

        let items = [];
        let currentIndex = 0;
        let isRecording = false;
        let isMuted = false;
        let startTime = null;
        let completionSubmitted = false;
        let recognition = null;
        let recognitionActive = false;
        let spokenTranscript = "";
        let correctWordCounts = [];
        let latestScores = null;
        let readAloudAudio = null;
        let readAloudAudioUrl = "";
        let isReadAloudLoading = false;
        let isTestingMic = false;
        let micTestWasRecording = false;
        let micSampleAudioUrl = "";
        let micSampleAudio = null;
        let micTestRecorder = null;
        let micTestStream = null;
        let selectedMicDeviceId = localStorage.getItem("pabasaSelectedMicDeviceId") || "";
        let micTestAudioContext = null;
        let micTestAnalyser = null;
        let micTestMeterFrame = null;
        let micTestLastHeardAt = 0;
        let micTestNoiseFloor = 0;
        let micTestSpeechFrameCount = 0;
        let rawMicLines = [];
        let mediaStream = null;
        let mediaRecorder = null;
        let speechChunkTimer = null;
        let speechAudioChunks = [];
        let stoppingSpeechRecognition = false;
        let isSendingChunk = false;
        let pendingAudioChunk = null;
        let itemResultVersion = 0;
        let isAdvancingItem = false;
        let currentSyllableIndex = 0;
        let currentMaterialLanguage = "";
        let liveCountdownTimer = null;
        let liveCountdownStarted = false;
        let liveServerTimeOffsetMs = 0;
        let audioContext = null;
        let audioAnalyser = null;
        let audioMeterFrame = null;
        let lastHeardAt = 0;
        let hasHeardSinceLastChunk = false;
        let ambientNoiseFloor = 0;
        let speechFrameCount = 0;
        const speechChunkMs = 2400;
        const speechLevelThreshold = 0.014;
        const speechNoiseMultiplier = 3.2;

        function getCsrfToken() {
            const cookieToken = document.cookie.split('; ')
                .find(row => row.startsWith('csrftoken='))
                ?.split('=')[1];
            return cookieToken || document.querySelector('[name=csrfmiddlewaretoken]')?.value || '';
        }

        const studentClassCodesKey = "pabasaStudentClassCodes";
        const readingsStorageKey = "pabasa_class_readings";
        const completedAssessmentIdsKey = "pabasa_completed_assessment_ids";

        function getStoredData(key, fallback = []) {
            try { return JSON.parse(localStorage.getItem(key) || JSON.stringify(fallback)); } catch (e) { return fallback; }
        }

        function parseItems(material, currentMode) {
            if (Array.isArray(material.items)) return material.items.filter(Boolean);
            if (material.content && typeof material.content === 'string') {
                // Split by line to allow multiple items (words, sentences, or paragraphs)
                return material.content.split(/\n/).map(i => i.trim()).filter(item => item.length > 0);
            }
            return [];
        }

        function parseLiveContent(content, readingType) {
            const normalizedType = String(readingType || liveItemType || mode || "word").toLowerCase();
            const source = String(content || "").trim();
            if (!source) return [];
            if (normalizedType === "sentence") {
                const lines = source.split(/\r?\n/).map(item => item.trim()).filter(Boolean);
                if (lines.length > 1 && !/\n\n/.test(source)) {
                    return lines;
                }
                return source.split(/(?<=[.!?])\s+/).map(item => item.trim()).filter(Boolean);
            }
            if (normalizedType === "paragraph" || normalizedType === "para") {
                return source.split(/\n{2,}/).map(item => item.trim()).filter(Boolean);
            }
            return source.match(/\b[\w']+\b/g) || [];
        }

        function loadItems() {
            if (liveContent) {
                items = parseLiveContent(liveContent, liveItemType || mode);
                currentMaterialLanguage = liveLanguage || "";
                correctWordCounts = new Array(items.length).fill(0);
                if (items.length === 0) {
                    if (readingWord) readingWord.textContent = "No assessment items assigned.";
                    if (nextBtn) nextBtn.disabled = true;
                    return;
                }
                currentIndex = 0;
                updateUI();
                animateCurrentItem();
                return;
            }

            // Prioritize the specific class code from the URL to prevent mixing materials from other classes
            const targetCode = (testCode && testCode !== "TST-000") ? testCode.toUpperCase() : null;
            let codes = targetCode ? [targetCode] : getStoredData(studentClassCodesKey, []).map(c => String(c).toUpperCase());

            const readings = getStoredData(readingsStorageKey, {});
            
            // Create normalized map for case-insensitive class code lookups
            const readingsMap = {};
            Object.keys(readings).forEach(key => readingsMap[key.toUpperCase()] = readings[key]);

            let aggregatedItems = [];
            currentMaterialLanguage = "";
            codes.forEach(code => {
                const upperCode = String(code).toUpperCase();
                const classReadings = readingsMap[upperCode];
                if (!classReadings) return;
                
                [mode, mode + 's'].forEach(m => {
                    if (Array.isArray(classReadings[m])) {
                        classReadings[m].forEach(material => {
                            const type = String(material.type || "").toLowerCase();
                            const isAssessment = type.includes("assessment") || type.includes("both");
                            const mId = (material.id !== undefined && material.id !== null) ? String(material.id).trim() : null;

                            // Filter by ID (preferred) or Title
                            const matchesTarget = (materialId && mId === String(materialId).trim()) || (testTitle && material.title === testTitle);
                            
                            if (isAssessment && (matchesTarget || (!testTitle && !materialId && aggregatedItems.length === 0))) {
                                aggregatedItems = aggregatedItems.concat(parseItems(material, mode));
                                if (!currentMaterialLanguage && material.language) {
                                    currentMaterialLanguage = material.language;
                                }
                            }
                        });
                    }
                });
            });

            items = aggregatedItems;
            correctWordCounts = new Array(items.length).fill(0);
            if (items.length === 0) {
                if (readingWord) readingWord.textContent = "No assessment items assigned.";
                if (nextBtn) nextBtn.disabled = true;
                return;
            }
            currentIndex = 0;
            updateUI();
            animateCurrentItem();
        }

        function normalizeWords(value) {
            return String(value || "")
                .toLowerCase()
                .replace(/[^a-z0-9\s'-]/g, " ")
                .split(/\s+/)
                .map(word => word.trim())
                .filter(word => word && !/^\d+$/.test(word));
        }

        function lcsLength(a, b) {
            const prev = new Array(b.length + 1).fill(0);
            const curr = new Array(b.length + 1).fill(0);
            for (let i = 1; i <= a.length; i++) {
                for (let j = 1; j <= b.length; j++) {
                    curr[j] = a[i - 1] === b[j - 1] ? prev[j - 1] + 1 : Math.max(prev[j], curr[j - 1]);
                }
                for (let j = 0; j <= b.length; j++) prev[j] = curr[j];
            }
            return prev[b.length] || 0;
        }

        function targetWpmForMode() {
            if (mode === "word") return 45;
            if (mode === "sentence") return 65;
            return 85;
        }

        function classifyCRLA(totalScore) {
            if (totalScore >= 95) return "Readers at Grade Level";
            if (totalScore >= 85) return "Transitioning Readers";
            if (totalScore >= 75) return "Developing Readers";
            if (totalScore >= 60) return "High Emerging Readers";
            return "Low Emerging Readers";
        }

        function calculateScores() {
            const targetText = items.join(" ");
            const targetWords = normalizeWords(targetText);
            const spokenWords = normalizeWords(spokenTranscript);
            const durationSeconds = Math.max(1, Math.round(((Date.now() - (startTime || Date.now())) / 1000) * 100) / 100);
            const matchedWords = correctWordsRead();
            const wpm = Math.round((matchedWords / Math.max(durationSeconds / 60, 1 / 60)) * 100) / 100;
            const targetWpm = targetWpmForMode();
            const speechRecognitionUsed = spokenWords.length > 0;

            const accuracy = targetWords.length && speechRecognitionUsed
                ? Math.round((matchedWords / targetWords.length) * 10000) / 100
                : 0;
            const pronunciationScore = targetWords.length && speechRecognitionUsed
                ? Math.round((matchedWords / Math.max(spokenWords.length, targetWords.length)) * 10000) / 100
                : 0;
            const fluencyScore = Math.round(Math.min(100, (wpm / targetWpm) * 100) * 100) / 100;
            const expectedSeconds = Math.max(1, (targetWords.length / targetWpm) * 60);
            const timeRatio = durationSeconds / expectedSeconds;
            const timeScore = Math.round(Math.max(0, Math.min(100, 100 - Math.max(0, timeRatio - 1.15) * 55)) * 100) / 100;
            const totalScore = Math.round(((fluencyScore + accuracy + pronunciationScore + timeScore) / 4) * 100) / 100;
            const crlaClassification = classifyCRLA(totalScore);
            const needsManualReview = !speechRecognitionUsed;

            return {
                fluency_score: fluencyScore,
                accuracy,
                pronunciation_score: pronunciationScore,
                time_score: timeScore,
                total_score: totalScore,
                crla_classification: crlaClassification,
                classification: crlaClassification,
                wpm,
                duration_seconds: durationSeconds,
                word_count: matchedWords,
                target_word_count: targetWords.length,
                transcript: spokenTranscript.trim(),
                speech_recognition_used: speechRecognitionUsed,
                needs_manual_review: needsManualReview,
                remarks: needsManualReview
                    ? "Speech recognition was unavailable or did not capture speech; teacher review is recommended."
                    : `CRLA classification: ${crlaClassification}.`
            };
        }

        function correctWordsRead() {
            return correctWordCounts.reduce((sum, count) => sum + Number(count || 0), 0);
        }

        function readableWordCount(text) {
            return normalizeWords(text).length;
        }

        function formatDuration(seconds) {
            const totalSeconds = Math.max(0, Math.round(Number(seconds || 0)));
            const hours = Math.floor(totalSeconds / 3600);
            const minutes = Math.floor((totalSeconds % 3600) / 60);
            const remainingSeconds = totalSeconds % 60;
            if (hours > 0) {
                return `${hours}:${String(minutes).padStart(2, "0")}:${String(remainingSeconds).padStart(2, "0")}`;
            }
            return `${String(minutes).padStart(2, "0")}:${String(remainingSeconds).padStart(2, "0")}`;
        }

        function renderScoreSummary(scores) {
            const summary = document.querySelector(".completion-summary");
            if (!summary || !scores) return;
            summary.querySelectorAll("[data-score-tile]").forEach(tile => tile.remove());
            const tiles = [
                [`${Math.round(scores.fluency_score)}%`, "fluency"],
                [`${Math.round(scores.accuracy)}%`, "accuracy"],
                [`${Math.round(scores.pronunciation_score)}%`, "pronunciation"],
                [formatDuration(scores.duration_seconds), "time"],
                [`${Math.round(scores.total_score)}%`, "total score"],
                [scores.crla_classification, "CRLA level"],
            ];
            tiles.forEach(([value, label]) => {
                const tile = document.createElement("div");
                tile.className = "summary-tile";
                tile.dataset.scoreTile = "true";
                const strong = document.createElement("strong");
                strong.textContent = value;
                const span = document.createElement("span");
                span.textContent = label;
                tile.append(strong, span);
                summary.appendChild(tile);
            });
        }

        function setSpeechStatus(message, detail = "", listening = false) {
            const panel = document.getElementById("speechPanel");
            const status = document.getElementById("speechStatus");
            const transcript = document.getElementById("speechTranscript");
            panel?.classList.toggle("is-listening", listening);
            shell?.classList.toggle("is-recording", Boolean(listening && isRecording && !isMuted));
            if (!listening || !isRecording || isMuted) shell?.classList.remove("is-hearing");
            if (status) status.textContent = message;
            if (transcript) transcript.textContent = detail || "Google Speech results will appear here while you read.";
        }

        function setRawMicInput(value) {
            if (rawMicInput) rawMicInput.textContent = value || "Waiting for speech...";
        }

        function appendRawMicInput(value) {
            if (!value) return;
            rawMicLines.push(value);
            rawMicLines = rawMicLines.slice(-6);
            setRawMicInput(rawMicLines.join("\n"));
        }

        function resetRawMicInput(value = "Waiting for speech...") {
            rawMicLines = [];
            setRawMicInput(value);
        }

        function pickAudioMimeType() {
            const candidates = [
                "audio/webm;codecs=opus",
                "audio/webm",
                "audio/ogg;codecs=opus",
                "audio/ogg",
            ];
            return candidates.find(type => window.MediaRecorder?.isTypeSupported?.(type)) || "";
        }

        function microphoneConstraints() {
            const audio = {
                echoCancellation: true,
                noiseSuppression: false,
                autoGainControl: true,
            };
            if (selectedMicDeviceId) {
                audio.deviceId = { exact: selectedMicDeviceId };
            }
            return { audio };
        }

        async function startSpeechRecognition() {
            if (isReviewMode || isMuted || recognitionActive) return;
            if (!navigator.mediaDevices?.getUserMedia || !window.MediaRecorder) {
                setSpeechStatus("Speech recording is unavailable in this browser.", "Use a current Chrome or Edge browser for live Google Speech checking.");
                return;
            }
            try {
                mediaStream = await navigator.mediaDevices.getUserMedia(microphoneConstraints());
                startAudioMeter(mediaStream);
                stoppingSpeechRecognition = false;
                startSpeechChunkRecorder();
                speechChunkTimer = window.setInterval(finishCurrentAudioChunk, speechChunkMs);
                recognitionActive = true;
                resetRawMicInput("Waiting for speech...");
                setSpeechStatus("Listening with Google Speech...", "Read the text on screen. Correct syllables will highlight as they are confirmed.", true);
            } catch (error) {
                console.warn("PABASA: Microphone unavailable", error);
                setSpeechStatus("Microphone access was not allowed.", "Please allow microphone access and try again.");
            }
        }

        function startSpeechChunkRecorder() {
            if (!mediaStream || stoppingSpeechRecognition || isMuted || !isRecording || isAdvancingItem) return;
            const recorderContext = currentSpeechContext();
            const mimeType = pickAudioMimeType();
            speechAudioChunks = [];
            try {
                mediaRecorder = new MediaRecorder(mediaStream, mimeType ? { mimeType } : undefined);
            } catch (error) {
                console.warn("PABASA: MediaRecorder could not start", error);
                setSpeechStatus("Speech recorder error.", error.message || "Please try starting again.");
                return;
            }
            mediaRecorder.ondataavailable = (event) => {
                if (event.data && event.data.size > 0) {
                    speechAudioChunks.push(event.data);
                }
            };
            mediaRecorder.onerror = (event) => {
                console.warn("PABASA: MediaRecorder error", event.error);
                setSpeechStatus("Speech recorder error.", event.error?.message || "Please try starting again.");
            };
            mediaRecorder.onstop = () => {
                const chunks = speechAudioChunks.slice();
                const recorderMimeType = mediaRecorder?.mimeType || mimeType || "audio/webm";
                speechAudioChunks = [];
                mediaRecorder = null;

                if (chunks.length && isRecording && !isMuted && shouldSendAudioChunk() && isCurrentSpeechContext(recorderContext)) {
                    hasHeardSinceLastChunk = false;
                    sendAudioChunk(new Blob(chunks, { type: recorderMimeType }), recorderContext);
                }

                if (!stoppingSpeechRecognition && isRecording && !isMuted && !isAdvancingItem) {
                    startSpeechChunkRecorder();
                }
            };
            mediaRecorder.start();
        }

        function finishCurrentAudioChunk() {
            if (!mediaRecorder || mediaRecorder.state !== "recording") return;
            try {
                mediaRecorder.requestData();
                mediaRecorder.stop();
            } catch (error) {
                console.warn("PABASA: Could not finish speech chunk", error);
            }
        }

        async function flushCurrentSpeechChunk(maxMs = 1200) {
            if (!mediaRecorder || mediaRecorder.state !== "recording") return;
            stoppingSpeechRecognition = true;
            finishCurrentAudioChunk();
            const started = Date.now();
            while (mediaRecorder && Date.now() - started < maxMs) {
                await new Promise(resolve => window.setTimeout(resolve, 50));
            }
        }

        function stopSpeechRecognition() {
            stoppingSpeechRecognition = true;
            if (speechChunkTimer) {
                window.clearInterval(speechChunkTimer);
                speechChunkTimer = null;
            }
            try {
                if (mediaRecorder && mediaRecorder.state !== "inactive") {
                    mediaRecorder.requestData();
                    mediaRecorder.stop();
                }
            } catch (error) {
                console.warn("PABASA: MediaRecorder stop failed", error);
            }
            stopAudioMeter();
            mediaStream?.getTracks().forEach(track => track.stop());
            mediaStream = null;
            mediaRecorder = null;
            recognitionActive = false;
            pendingAudioChunk = null;
            speechAudioChunks = [];
            hasHeardSinceLastChunk = false;
            shell?.classList.remove("is-recording", "is-hearing");
            setSpeechStatus("Speech check stopped.", spokenTranscript || "No speech transcript was captured.");
        }

        function startAudioMeter(stream) {
            stopAudioMeter();
            const AudioContextClass = window.AudioContext || window.webkitAudioContext;
            if (!AudioContextClass) return;
            try {
                audioContext = new AudioContextClass();
                if (audioContext.state === "suspended") {
                    audioContext.resume().catch(() => {});
                }
                const source = audioContext.createMediaStreamSource(stream);
                audioAnalyser = audioContext.createAnalyser();
                audioAnalyser.fftSize = 1024;
                source.connect(audioAnalyser);
                const samples = new Uint8Array(audioAnalyser.fftSize);
                const meterStartedAt = Date.now();
                const tick = () => {
                    if (!audioAnalyser || !isRecording || isMuted) {
                        shell?.classList.remove("is-hearing");
                        return;
                    }
                    audioAnalyser.getByteTimeDomainData(samples);
                    let sum = 0;
                    for (let index = 0; index < samples.length; index += 1) {
                        const centered = (samples[index] - 128) / 128;
                        sum += centered * centered;
                    }
                    const rms = Math.sqrt(sum / samples.length);
                    const now = Date.now();
                    const isCalibrating = now - meterStartedAt < 800;
                    if (!ambientNoiseFloor) {
                        ambientNoiseFloor = rms;
                    } else if (isCalibrating || rms < ambientNoiseFloor * 1.8) {
                        ambientNoiseFloor = (ambientNoiseFloor * 0.94) + (rms * 0.06);
                    }

                    const activeSpeechThreshold = Math.max(
                        speechLevelThreshold,
                        (ambientNoiseFloor * speechNoiseMultiplier) + 0.004
                    );
                    if (!isCalibrating && rms > activeSpeechThreshold) {
                        speechFrameCount += 1;
                    } else {
                        speechFrameCount = Math.max(0, speechFrameCount - 1);
                    }

                    if (speechFrameCount >= 3) {
                        lastHeardAt = now;
                        hasHeardSinceLastChunk = true;
                    }
                    shell?.classList.toggle("is-hearing", now - lastHeardAt < 240);
                    audioMeterFrame = window.requestAnimationFrame(tick);
                };
                tick();
            } catch (error) {
                console.warn("PABASA: Audio meter unavailable", error);
                stopAudioMeter();
            }
        }

        function stopAudioMeter() {
            if (audioMeterFrame) {
                window.cancelAnimationFrame(audioMeterFrame);
                audioMeterFrame = null;
            }
            shell?.classList.remove("is-hearing");
            audioAnalyser = null;
            if (audioContext) {
                audioContext.close().catch(() => {});
                audioContext = null;
            }
            lastHeardAt = 0;
            hasHeardSinceLastChunk = false;
            ambientNoiseFloor = 0;
            speechFrameCount = 0;
        }

        function shouldSendAudioChunk() {
            return !audioAnalyser || hasHeardSinceLastChunk || Date.now() - lastHeardAt < speechChunkMs + 700;
        }

        function currentSpeechContext() {
            return {
                index: currentIndex,
                itemText: items[currentIndex] || "",
                syllableIndex: currentSyllableIndex,
                version: itemResultVersion,
            };
        }

        function isCurrentSpeechContext(context) {
            return Boolean(
                context
                && context.index === currentIndex
                && context.itemText === items[currentIndex]
                && context.version === itemResultVersion
                && !isAdvancingItem
            );
        }

        async function sendAudioChunk(blob, context = currentSpeechContext()) {
            if (!context.itemText || !isCurrentSpeechContext(context)) return;
            if (isSendingChunk) {
                pendingAudioChunk = { blob, context };
                return;
            }
            isSendingChunk = true;
            const formData = new FormData();
            formData.append("audio", blob, `reading-${Date.now()}.${audioExtensionForBlob(blob)}`);
            formData.append("target_text", context.itemText);
            formData.append("current_syllable_index", String(context.syllableIndex));
            formData.append("mode", mode);
            formData.append("language", currentMaterialLanguage || "");

            try {
                const response = await fetch("/api/reading/transcribe/", {
                    method: "POST",
                    headers: { "X-CSRFToken": getCsrfToken() },
                    credentials: "same-origin",
                    body: formData,
                });
                const data = await response.json();
                if (!response.ok || !data.success) {
                    throw new Error(data.error || "Speech check failed.");
                }
                if (!isCurrentSpeechContext(context)) return;
                if (data.transcript) {
                    const fallbackNote = data.stt_fallback_reason ? ` | Fallback: ${data.stt_fallback_reason}` : "";
                    appendRawMicInput(`Model: ${sttModelLabel(data.stt_model)}${fallbackNote} | Words: ${data.transcript}`);
                }
                handleSpeechResult(data, context);
            } catch (error) {
                console.warn("PABASA: Reading transcription failed", error);
                if (isCurrentSpeechContext(context)) {
                    setSpeechStatus("Speech check had trouble.", error.message || "Keep reading, then try again.");
                }
            } finally {
                isSendingChunk = false;
                if (pendingAudioChunk && isRecording && !isMuted && isCurrentSpeechContext(pendingAudioChunk.context)) {
                    const nextChunk = pendingAudioChunk.blob;
                    const nextContext = pendingAudioChunk.context;
                    pendingAudioChunk = null;
                    sendAudioChunk(nextChunk, nextContext);
                } else {
                    pendingAudioChunk = null;
                }
            }
        }

        function audioExtensionForBlob(blob) {
            const type = String(blob?.type || "").toLowerCase();
            if (type.includes("ogg")) return "ogg";
            if (type.includes("wav")) return "wav";
            return "webm";
        }

        function sttModelLabel(model) {
            if (model === "chirp_3") return "Chirp 3";
            if (model === "stt_v1") return "STT v1";
            return model || "Google STT";
        }

        function handleSpeechResult(data, context = currentSpeechContext()) {
            if (!isCurrentSpeechContext(context)) return;
            const transcript = (data.transcript || "").trim();
            if (transcript) {
                spokenTranscript = [spokenTranscript, transcript].filter(Boolean).join(" ");
            }
            const previousCorrectWords = Number(correctWordCounts[currentIndex] || 0);
            const itemCorrectWords = Math.max(
                previousCorrectWords,
                Number(data.correct_word_count || data.current_word_index || 0)
            );
            correctWordCounts[currentIndex] = Math.min(itemCorrectWords, readableWordCount(items[currentIndex]));
            currentSyllableIndex = Number(data.current_syllable_index || currentSyllableIndex || 0);
            if (transcript || Number(data.matched || 0) > 0) {
                renderSyllableDisplay(data, previousCorrectWords);
            }

            if (data.complete) {
                isAdvancingItem = true;
                pendingAudioChunk = null;
                setSpeechStatus("Great job! You finished this item.", transcript ? `Words: ${transcript}` : "", true);
                if (currentIndex >= items.length - 1) {
                    isRecording = false;
                    stopSpeechRecognition();
                    showCompletion(true);
                } else {
                    window.setTimeout(() => {
                        if (!isRecording || context.version !== itemResultVersion) return;
                        transitionToItem(currentIndex + 1, "Next item loaded.", "Keep reading clearly.");
                    }, 700);
                }
                return;
            }

            if (Number(data.matched || 0) > 0) {
                setSpeechStatus(
                    `Matched ${correctWordCounts[currentIndex]} word${Number(correctWordCounts[currentIndex]) === 1 ? "" : "s"}.`,
                    `Words: ${transcript || "..."}${data.formatted_syllables ? " | Syllables: " + data.formatted_syllables : ""}`,
                    true
                );
            } else {
                const nextHint = data.next_syllable && data.next_word ? `Try again from: ${data.next_syllable} in ${data.next_word}` : "Keep reading.";
                setSpeechStatus(transcript ? nextHint : "Listening with Google Speech...", transcript ? `Words: ${transcript}` : "No words recognized yet. Keep reading clearly.", true);
            }
        }

        function renderSyllableDisplay(data, previousCorrectWords = 0) {
            if (!readingWord || !Array.isArray(data.words) || !Array.isArray(data.word_syllable_ranges)) return;
            readingWord.textContent = "";
            let readableWordIndex = 0;
            let animatedWordCount = 0;
            const shouldAnimate = true;
            const parts = String(items[currentIndex] || "").split(/(\s+)/);
            parts.forEach((part) => {
                if (!part) return;
                if (/^\s+$/.test(part)) {
                    readingWord.appendChild(document.createTextNode(part));
                    return;
                }

                if (isDisplayListMarker(part) || !normalizeDisplayWord(part)) {
                    readingWord.appendChild(document.createTextNode(part));
                    return;
                }

                const range = data.word_syllable_ranges[readableWordIndex] || [0, 0];
                const span = document.createElement("span");
                span.className = "syllable";
                if (range[1] <= currentSyllableIndex) {
                    span.classList.add("is-read");
                    if (shouldAnimate && readableWordIndex >= previousCorrectWords) {
                        span.classList.add("is-new-read");
                        span.style.animationDelay = `${animatedWordCount * 130}ms`;
                        animatedWordCount += 1;
                    }
                }
                else if (range[0] <= currentSyllableIndex && currentSyllableIndex < range[1]) span.classList.add("is-current");
                span.textContent = part;
                readingWord.appendChild(span);
                readableWordIndex += 1;
            });
            if (progressFill && typeof data.progress === "number") {
                progressFill.style.width = `${((currentIndex + (data.progress / 100)) / items.length) * 100}%`;
            }
        }

        function normalizeDisplayWord(word) {
            return String(word || "").toLowerCase().replace(/[^a-z0-9']/g, "");
        }

        function isDisplayListMarker(word) {
            const raw = String(word || "").trim();
            const normalized = normalizeDisplayWord(raw);
            return /^\d+[\.)]?$/.test(raw) || /^\(?\d+[\.)]$/.test(raw) || /^\d+$/.test(normalized);
        }

        async function waitForPendingSpeech(maxMs = 3500) {
            const started = Date.now();
            while (isSendingChunk && Date.now() - started < maxMs) {
                await new Promise(resolve => window.setTimeout(resolve, 100));
            }
        }

        function updateUI() {
            if (!items.length) return;
            stopReadAloud();
            if (readingWord) readingWord.textContent = items[currentIndex];
            currentSyllableIndex = 0;
            pendingAudioChunk = null;
            isAdvancingItem = false;
            itemResultVersion += 1;
            const label = mode.charAt(0).toUpperCase() + mode.slice(1);
            if (counter) counter.textContent = `${label} ${currentIndex + 1}/${items.length}`;
            if (progressFill) progressFill.style.width = `${((currentIndex + 1) / items.length) * 100}%`;
            
            if (prevBtn) prevBtn.disabled = isReviewMode ? currentIndex === 0 : (!isRecording || (currentIndex === 0));
            if (nextBtn) {
                nextBtn.disabled = isReviewMode ? currentIndex === items.length - 1 : (!isRecording || (currentIndex === items.length - 1));
                nextBtn.textContent = isReviewMode && currentIndex === items.length - 1 ? "Done" : "Next";
            }
        }

        function animateCurrentItem() {
            if (!readingWord) return;
            readingWord.classList.remove("is-changing");
            void readingWord.offsetWidth;
            readingWord.classList.add("is-changing");
            window.setTimeout(() => readingWord.classList.remove("is-changing"), 380);
        }

        function transitionToItem(nextIndex, statusMessage = "", detail = "") {
            if (nextIndex < 0 || nextIndex >= items.length || nextIndex === currentIndex) return;
            currentIndex = nextIndex;
            currentSyllableIndex = 0;
            updateUI();
            animateCurrentItem();
            if (statusMessage) {
                setSpeechStatus(statusMessage, detail, Boolean(isRecording && !isMuted));
            }
        }

        function showCompletion(isFullCompletion) {
            stopReadAloud();
            stopSpeechRecognition();
            shell.classList.add("is-complete");
            closePauseMenu();
            if (completionCount) completionCount.textContent = correctWordsRead();
            if (completionLevel) completionLevel.textContent = mode.charAt(0).toUpperCase() + mode.slice(1);
            latestScores = latestScores || calculateScores();
            renderScoreSummary(latestScores);
            
            // Add retake attempt information to the results title
            if (isRetakeMode && materialId) {
                const retakeCounts = JSON.parse(localStorage.getItem('pabasa_retake_counts') || '{}');
                const count = retakeCounts[String(materialId).trim()] || 0;
                const title = document.querySelector(".completion-card h1");
                if (title) title.innerHTML += ` <span style="background: var(--sun); color: #1b1a17; padding: 4px 12px; border-radius: 10px; font-size: 0.4em; vertical-align: middle; margin-left: 10px; font-weight: 900;">RETAKE ${count + 1}/3</span>`;
            }

            // Skip side effects for review mode or partial progress
            if (isReviewMode || !isFullCompletion || completionSubmitted) return;
            completionSubmitted = true;

            if (isRetakeMode && materialId) {
                const retakeCounts = JSON.parse(localStorage.getItem('pabasa_retake_counts') || '{}');
                const mId = String(materialId).trim();
                retakeCounts[mId] = (retakeCounts[mId] || 0) + 1;
                localStorage.setItem('pabasa_retake_counts', JSON.stringify(retakeCounts));
            }

            const count = parseInt(localStorage.getItem("pabasa_assessments_completed") || "0");
            localStorage.setItem("pabasa_assessments_completed", count + 1);

            // Explicitly mark this specific material as seen to decrease sidebar badges
            if (materialId) {
                const completedAssessmentIds = JSON.parse(localStorage.getItem(completedAssessmentIdsKey) || "[]").map(id => String(id).trim());
                const completedId = String(materialId).trim();
                if (!completedAssessmentIds.includes(completedId)) {
                    completedAssessmentIds.push(completedId);
                    localStorage.setItem(completedAssessmentIdsKey, JSON.stringify(completedAssessmentIds));
                }

                const seenIds = JSON.parse(localStorage.getItem("pabasa_seen_material_ids") || "[]").map(id => String(id).trim());
                const mId = String(materialId).trim();

                if (!seenIds.includes(mId)) {
                    seenIds.push(mId);
                    localStorage.setItem("pabasa_seen_material_ids", JSON.stringify(seenIds));
                    // Dispatch both events to ensure sidebar and dashboard update
                    window.dispatchEvent(new CustomEvent('pabasa:student-class-updated', { bubbles: true }));
                    window.dispatchEvent(new Event('storage')); // Fake storage event for current tab consistency
                }

                // Also mark linked practice materials (type 'practice' or 'both') that share the same id or title
                try {
                    const readings = JSON.parse(localStorage.getItem('pabasa_class_readings') || '{}');
                    const normalizedId = materialId ? String(materialId).trim() : null;
                    const normalizedTitle = testTitle || null;
                    const currentSeenIds = JSON.parse(localStorage.getItem('pabasa_seen_material_ids') || '[]').map(id => String(id).trim());
                    const seenSet = new Set(currentSeenIds);

                    Object.keys(readings).forEach(function (classCode) {
                        const classMaterials = readings[classCode] || {};
                        ['word', 'sentence', 'paragraph', 'story'].forEach(function (type) {
                            const keys = [type, type + 's', type === 'story' ? 'stories' : null].filter(Boolean);
                            keys.forEach(function (key) {
                                const list = classMaterials[key] || [];
                                if (!Array.isArray(list)) return;
                                list.forEach(function (mat) {
                                    if (!mat) return;
                                    const matType = String(mat.type || '').toLowerCase();
                                    if (!matType.includes('practice') && !matType.includes('both')) return;

                                    const matId = (mat.id !== undefined && mat.id !== null) ? String(mat.id).trim() : null;
                                    const matTitle = (mat.title || mat.content || '').toString();

                                    if ((normalizedId && matId && normalizedId === matId) || (normalizedTitle && matTitle && normalizedTitle === normalizedTitle)) {
                                        if (matId && !seenSet.has(matId)) {
                                            seenSet.add(matId);
                                        }
                                    }
                                });
                            });
                        });
                    });
                    localStorage.setItem('pabasa_seen_material_ids', JSON.stringify(Array.from(seenSet)));
                } catch (e) {
                    console.warn('PABASA: Could not mark linked materials as seen', e);
                }
            }

            // Emit an immediate in-app notification for the admin so the bell updates even before a full page reload.
            const studentName = window.PABASA_USER_NAME || window.localStorage.getItem('pabasaUserName') || 'A student';
            const metadata = JSON.parse(localStorage.getItem('pabasa_class_metadata') || '{}');
            const classInfo = metadata[String(testCode).toUpperCase()] || {};
            const className = classInfo.name || 'your class';
            const notifications = JSON.parse(localStorage.getItem('pabasa_notifications') || '[]');
            notifications.unshift({
                id: Date.now() + Math.random(),
                classCode: testCode,
                title: 'Student Completed an Assessment',
                message: `• ${studentName} completed the assessment "${testTitle}" in ${className}.`,
                timestamp: Date.now(),
                read: false,
                role: 'admin',
                recipientEmail: null,
            });
            localStorage.setItem('pabasa_notifications', JSON.stringify(notifications.slice(0, 100)));
            window.dispatchEvent(new Event('pabasa:notifications-updated'));

            // Persist completion server-side so the teacher receives an in-app notification.
            const token = getCsrfToken();
            if (materialId && token) {
                const elapsedSeconds = Math.max(1, Math.round(((Date.now() - (startTime || Date.now())) / 1000) * 100) / 100);
                const payload = {
                    material_id: materialId,
                    activity_type: 'assessment',
                    class_code: testCode,
                    scores: {
                        ...(latestScores || {}),
                        duration_seconds: latestScores?.duration_seconds || elapsedSeconds,
                    },
                };
                if (isRetakeMode) {
                    payload.is_retake = true;
                    const retakeCounts = JSON.parse(localStorage.getItem('pabasa_retake_counts') || '{}');
                    payload.attempt_number = retakeCounts[String(materialId).trim()] || 1;
                }
                const normalizedId = String(materialId).trim();
                if (normalizedId && !normalizedId.toLowerCase().startsWith('assessment-') && !normalizedId.toLowerCase().startsWith('material-') && !normalizedId.toLowerCase().startsWith('practice-')) {
                    payload.assessment_id = `assessment-${normalizedId}`;
                } else if (normalizedId.toLowerCase().startsWith('assessment-')) {
                    payload.assessment_id = normalizedId;
                }
                fetch('/record-assessment-completion/', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json', 'X-CSRFToken': token },
                    credentials: 'same-origin',
                    body: JSON.stringify(payload)
                }).then(r => r.json()).then(d => {
                    if (d.success) console.log("PABASA: Assessment completion recorded.");
                }).catch(e => console.error("PABASA: Completion error", e));
            }
        }

        function startAssessmentTimer() {
            if (!startTime || startTime === null) {
                startTime = Date.now();
            }
            return startTime;
        }

        function clearLiveCountdown() {
            if (liveCountdownTimer) {
                window.clearInterval(liveCountdownTimer);
                liveCountdownTimer = null;
            }
        }

        function showLiveCountdown() {
            if (!liveCountdownOverlay) return;
            liveCountdownOverlay.classList.remove('d-none');
        }

        function hideLiveCountdown() {
            if (!liveCountdownOverlay) return;
            liveCountdownOverlay.classList.add('d-none');
        }

        async function syncLiveServerTime() {
            if (liveServerTimeOffsetMs !== 0 || !isCurrentLiveAssessment()) return Promise.resolve();
            try {
                const response = await fetch('/api/live-assessment/server-time/', { credentials: 'same-origin' });
                const data = await response.json();
                if (data.success && data.server_time) {
                    const serverTime = Date.parse(data.server_time);
                    const localTime = Date.now();
                    if (Number.isFinite(serverTime)) {
                        liveServerTimeOffsetMs = serverTime - localTime;
                    }
                }
            } catch (error) {
                console.warn('PABASA: Unable to sync live assessment server time', error);
            }
        }

        function getAdjustedServerTime() {
            return Date.now() + liveServerTimeOffsetMs;
        }

        async function startLiveCountdown() {
            if (isReviewMode || liveCountdownStarted) return;
            const isLiveAssessment = isCurrentLiveAssessment();
            if (!isLiveAssessment) return;
            if (!items.length) {
                window.setTimeout(() => startLiveCountdown(), 120);
                return;
            }

            liveCountdownStarted = true;
            showLiveCountdown();
            const countdownDuration = Number.parseInt(urlParams.get('countdown') || '10', 10);
            const countdownStartedAt = Date.now();
            const getRemainingSeconds = () => {
                const elapsedSeconds = Math.floor((Date.now() - countdownStartedAt) / 1000);
                return Math.max(0, countdownDuration - elapsedSeconds);
            };

            const syncCountdownToStart = () => {
                let remaining = getRemainingSeconds();
                if (!Number.isFinite(remaining) || remaining < 0) remaining = 0;
                if (liveCountdownNumber) liveCountdownNumber.textContent = String(remaining);
                if (remaining <= 0) {
                    clearLiveCountdown();
                    hideLiveCountdown();
                    startReading();
                    return true;
                }
                if (liveCountdownSubtext) liveCountdownSubtext.textContent = 'Everyone will begin together in a moment.';
                return false;
            };

            if (liveCountdownNumber) liveCountdownNumber.textContent = String(countdownDuration);
            if (syncCountdownToStart()) return;
            liveCountdownTimer = window.setInterval(() => {
                if (syncCountdownToStart()) {
                    clearLiveCountdown();
                }
            }, 1000);
        }

        const startReading = () => {
            if (isReviewMode) return;
            startAssessmentTimer();
            if (!isRecording) {
                isRecording = true;
                spokenTranscript = "";
                correctWordCounts = new Array(items.length).fill(0);
                latestScores = null;
                currentSyllableIndex = 0;
                pendingAudioChunk = null;
                hasHeardSinceLastChunk = false;
                resetRawMicInput("Waiting for speech...");
                btnStartReading?.classList.add("d-none");
                btnStopReading?.classList.remove("d-none");
                updateUI();
                animateCurrentItem();
                startSpeechRecognition();
            }
            console.log("PABASA: Assessment recording and timer started.");
        };

        const stopReading = async () => {
            if (isReviewMode) return;
            if (!isRecording) return;
            if (mediaRecorder && mediaRecorder.state === "recording") {
                try {
                    await flushCurrentSpeechChunk();
                    await waitForPendingSpeech();
                } catch (error) {
                    console.warn("PABASA: Final audio request failed", error);
                }
            }
            isRecording = false;
            stopSpeechRecognition();
            const reachedLastItem = items.length > 0 && currentIndex === items.length - 1;
            showCompletion(reachedLastItem);
        };

        btnStartReading?.addEventListener("click", startReading);
        btnStopReading?.addEventListener("click", stopReading);

        if (!isReviewMode && items.length) {
            startAssessmentTimer();
        }
        btnReadAloud?.addEventListener("click", readCurrentItemAloud);

        async function readCurrentItemAloud() {
            if (!items[currentIndex] || isReadAloudLoading) return;
            if (readAloudAudio && !readAloudAudio.paused) {
                stopReadAloud();
                return;
            }

            isReadAloudLoading = true;
            btnReadAloud?.setAttribute("disabled", "disabled");
            btnReadAloud?.classList.add("is-playing");
            const originalHtml = btnReadAloud?.innerHTML || "";
            if (btnReadAloud) btnReadAloud.innerHTML = '<i class="bi bi-hourglass-split"></i> Loading';

            const formData = new FormData();
            formData.append("target_text", items[currentIndex]);
            formData.append("mode", mode);
            formData.append("language", currentMaterialLanguage || "");

            try {
                const response = await fetch("/api/reading/read-aloud/", {
                    method: "POST",
                    headers: { "X-CSRFToken": getCsrfToken() },
                    credentials: "same-origin",
                    body: formData,
                });
                const data = await response.json();
                if (!response.ok || !data.success) {
                    throw new Error(data.error || "Read aloud failed.");
                }
                revokeReadAloudUrl();
                const audioBlob = base64ToBlob(data.audio_content, data.mime_type || "audio/mpeg");
                readAloudAudioUrl = URL.createObjectURL(audioBlob);
                readAloudAudio = new Audio(readAloudAudioUrl);
                readAloudAudio.onended = stopReadAloud;
                readAloudAudio.onerror = stopReadAloud;
                if (btnReadAloud) btnReadAloud.innerHTML = '<i class="bi bi-stop-fill"></i> Stop Audio';
                btnReadAloud?.removeAttribute("disabled");
                await readAloudAudio.play();
            } catch (error) {
                console.warn("PABASA: Read aloud failed", error);
                setSpeechStatus("Read aloud had trouble.", error.message || "Please try again.");
                if (btnReadAloud) btnReadAloud.innerHTML = originalHtml;
                btnReadAloud?.classList.remove("is-playing");
                btnReadAloud?.removeAttribute("disabled");
            } finally {
                isReadAloudLoading = false;
            }
        }

        function stopReadAloud() {
            if (readAloudAudio) {
                readAloudAudio.pause();
                readAloudAudio.currentTime = 0;
            }
            revokeReadAloudUrl();
            btnReadAloud?.classList.remove("is-playing");
            btnReadAloud?.removeAttribute("disabled");
            if (btnReadAloud) btnReadAloud.innerHTML = '<i class="bi bi-volume-up-fill"></i> Read Aloud';
        }

        function revokeReadAloudUrl() {
            if (readAloudAudioUrl) {
                URL.revokeObjectURL(readAloudAudioUrl);
                readAloudAudioUrl = "";
            }
            readAloudAudio = null;
        }

        function base64ToBlob(base64Value, mimeType) {
            const binary = atob(base64Value || "");
            const bytes = new Uint8Array(binary.length);
            for (let index = 0; index < binary.length; index += 1) {
                bytes[index] = binary.charCodeAt(index);
            }
            return new Blob([bytes], { type: mimeType });
        }
        
        btnToggleMic?.addEventListener("click", () => {
            isMuted = !isMuted;
            const icon = btnToggleMic.querySelector("i");
            if (icon) icon.className = isMuted ? "bi bi-mic-mute-fill" : "bi bi-mic-fill";
            btnToggleMic.classList.toggle("btn-outline-danger", isMuted);
            btnToggleMic.classList.toggle("btn-outline-dark", !isMuted);
            if (isMuted) stopSpeechRecognition();
            else if (isRecording) startSpeechRecognition();
        });

        if (btnTestMic) {
            btnTestMic.addEventListener("click", openMicTestDialog);
        }
        micDeviceSelect?.addEventListener("change", () => {
            selectedMicDeviceId = micDeviceSelect.value || "";
            localStorage.setItem("pabasaSelectedMicDeviceId", selectedMicDeviceId);
            revokeMicSampleUrl();
            micSamplePlayBtn?.setAttribute("disabled", "disabled");
            setMicTestStatus("Microphone selected. Record a sample to check it.");
            if (micTestWasRecording && isRecording && !isMuted) {
                stopSpeechRecognition();
            }
        });
        micTestCloseBtn?.addEventListener("click", closeMicTestDialog);
        micTestOverlay?.addEventListener("click", (event) => {
            if (event.target === micTestOverlay) closeMicTestDialog();
        });
        micSampleRecordBtn?.addEventListener("click", runMicPlaybackTest);
        micSamplePlayBtn?.addEventListener("click", playMicSample);

        function openMicTestDialog() {
            if (!micTestOverlay) {
                runMicPlaybackTest();
                return;
            }
            micTestWasRecording = isRecording && recognitionActive;
            if (micTestWasRecording) {
                stopSpeechRecognition();
                setSpeechStatus("Reading paused for microphone check.", "Close the microphone check to continue listening.", false);
            }
            micTestOverlay.classList.remove("d-none");
            document.body.style.overflow = "hidden";
            setMicTestStatus(micTestWasRecording ? "Reading paused.\nReady for a sample recording." : "Ready for a sample recording.");
            loadMicrophoneDevices();
        }

        async function loadMicrophoneDevices() {
            if (!micDeviceSelect || !navigator.mediaDevices?.enumerateDevices) return;
            try {
                let devices = await navigator.mediaDevices.enumerateDevices();
                if (!devices.some(device => device.kind === "audioinput" && device.label)) {
                    const permissionStream = await navigator.mediaDevices.getUserMedia({ audio: true });
                    permissionStream.getTracks().forEach(track => track.stop());
                    devices = await navigator.mediaDevices.enumerateDevices();
                }
                const audioInputs = devices.filter(device => device.kind === "audioinput");
                micDeviceSelect.replaceChildren(new Option("Default microphone", ""));
                audioInputs.forEach((device, index) => {
                    const label = device.label || `Microphone ${index + 1}`;
                    micDeviceSelect.appendChild(new Option(label, device.deviceId));
                });
                if (selectedMicDeviceId && audioInputs.some(device => device.deviceId === selectedMicDeviceId)) {
                    micDeviceSelect.value = selectedMicDeviceId;
                } else {
                    selectedMicDeviceId = "";
                    localStorage.removeItem("pabasaSelectedMicDeviceId");
                    micDeviceSelect.value = "";
                }
            } catch (error) {
                console.warn("PABASA: Could not load microphones", error);
                setMicTestStatus("Could not load microphone list. Check browser permission.");
            }
        }

        function closeMicTestDialog() {
            stopMicSampleCapture();
            micTestOverlay?.classList.add("d-none");
            document.body.style.overflow = "";
            if (micTestWasRecording && isRecording && !isMuted) {
                startSpeechRecognition();
            }
            micTestWasRecording = false;
        }

        async function runMicPlaybackTest() {
            if (isTestingMic) return;
            if (!navigator.mediaDevices?.getUserMedia || !window.MediaRecorder) {
                setMicTestStatus("This browser cannot record microphone audio. Use a current Chrome or Edge browser.");
                return;
            }

            isTestingMic = true;
            const icon = btnTestMic?.querySelector("i");
            const originalIconClass = icon?.className || "";
            if (icon) icon.className = "bi bi-record-circle-fill";
            btnTestMic?.classList.add("btn-outline-danger");
            micSampleRecordBtn?.setAttribute("disabled", "disabled");
            micSamplePlayBtn?.setAttribute("disabled", "disabled");
            setMicTestStatus("Recording sample... say a short phrase now.");
            resetRawMicInput("Mic test recording... say something now.");

            try {
                revokeMicSampleUrl();
                micTestStream = await navigator.mediaDevices.getUserMedia(microphoneConstraints());
                startMicTestMeter(micTestStream);
                const mimeType = pickAudioMimeType();
                micTestRecorder = new MediaRecorder(micTestStream, mimeType ? { mimeType } : undefined);
                const chunks = [];
                micTestRecorder.ondataavailable = (event) => {
                    if (event.data && event.data.size > 0) chunks.push(event.data);
                };

                await new Promise((resolve, reject) => {
                    micTestRecorder.onerror = () => reject(new Error("The microphone test recorder failed."));
                    micTestRecorder.onstop = resolve;
                    micTestRecorder.start();
                    window.setTimeout(() => {
                        if (micTestRecorder && micTestRecorder.state !== "inactive") micTestRecorder.stop();
                    }, 3000);
                });

                const blob = new Blob(chunks, { type: micTestRecorder?.mimeType || mimeType || "audio/webm" });
                if (!blob.size) {
                    setRawMicInput("No audio was captured during the mic test.");
                    setMicTestStatus("No audio was captured. Check the selected microphone and try again.");
                    return;
                }

                micSampleAudioUrl = URL.createObjectURL(blob);
                micSampleAudio = new Audio(micSampleAudioUrl);
                micSampleAudio.controls = false;
                micSamplePlayBtn?.removeAttribute("disabled");
                setRawMicInput(`Mic test captured ${(blob.size / 1024).toFixed(1)} KB. Use Play Sample to listen.`);
                setMicTestStatus("Sample captured. Play it back to check if your voice is clear.");
            } catch (error) {
                console.warn("PABASA: Mic test failed", error);
                setRawMicInput("Mic test failed: " + (error.message || "microphone access was not available."));
                setMicTestStatus(error.message || "Microphone access was not available.");
            } finally {
                stopMicSampleCapture();
                if (icon) icon.className = originalIconClass || "bi bi-headphones";
                btnTestMic?.classList.remove("btn-outline-danger");
                micSampleRecordBtn?.removeAttribute("disabled");
                isTestingMic = false;
            }
        }

        async function playMicSample() {
            if (!micSampleAudio) {
                setMicTestStatus("Record a sample first.");
                return;
            }
            try {
                micSampleAudio.currentTime = 0;
                await micSampleAudio.play();
                setMicTestStatus("Playing sample. If you hear your voice clearly, the microphone is ready.");
            } catch (error) {
                setMicTestStatus(error.message || "Could not play the sample.");
            }
        }

        function setMicTestStatus(message) {
            if (!micTestStatus) return;
            micTestStatus.replaceChildren();
            String(message || "").split("\n").forEach((line, index) => {
                if (index) micTestStatus.appendChild(document.createElement("br"));
                micTestStatus.appendChild(document.createTextNode(line));
            });
        }

        function stopMicSampleCapture() {
            stopMicTestMeter();
            if (micTestRecorder && micTestRecorder.state !== "inactive") {
                try { micTestRecorder.stop(); } catch (error) { console.warn("PABASA: Mic sample stop failed", error); }
            }
            micTestRecorder = null;
            micTestStream?.getTracks().forEach(track => track.stop());
            micTestStream = null;
        }

        function startMicTestMeter(stream) {
            stopMicTestMeter();
            const AudioContextClass = window.AudioContext || window.webkitAudioContext;
            if (!AudioContextClass) return;
            try {
                micTestAudioContext = new AudioContextClass();
                if (micTestAudioContext.state === "suspended") {
                    micTestAudioContext.resume().catch(() => {});
                }
                const source = micTestAudioContext.createMediaStreamSource(stream);
                micTestAnalyser = micTestAudioContext.createAnalyser();
                micTestAnalyser.fftSize = 1024;
                source.connect(micTestAnalyser);
                const samples = new Uint8Array(micTestAnalyser.fftSize);
                const meterStartedAt = Date.now();
                const tick = () => {
                    if (!micTestAnalyser || !isTestingMic) {
                        micTestStatus?.classList.remove("is-hearing");
                        return;
                    }
                    micTestAnalyser.getByteTimeDomainData(samples);
                    let sum = 0;
                    for (let index = 0; index < samples.length; index += 1) {
                        const centered = (samples[index] - 128) / 128;
                        sum += centered * centered;
                    }
                    const rms = Math.sqrt(sum / samples.length);
                    const now = Date.now();
                    const isCalibrating = now - meterStartedAt < 450;
                    if (!micTestNoiseFloor) {
                        micTestNoiseFloor = rms;
                    } else if (isCalibrating || rms < micTestNoiseFloor * 1.8) {
                        micTestNoiseFloor = (micTestNoiseFloor * 0.94) + (rms * 0.06);
                    }
                    const activeSpeechThreshold = Math.max(
                        speechLevelThreshold,
                        (micTestNoiseFloor * speechNoiseMultiplier) + 0.004
                    );
                    if (!isCalibrating && rms > activeSpeechThreshold) {
                        micTestSpeechFrameCount += 1;
                    } else {
                        micTestSpeechFrameCount = Math.max(0, micTestSpeechFrameCount - 1);
                    }
                    if (micTestSpeechFrameCount >= 3) {
                        micTestLastHeardAt = now;
                    }
                    micTestStatus?.classList.toggle("is-hearing", now - micTestLastHeardAt < 260);
                    micTestMeterFrame = window.requestAnimationFrame(tick);
                };
                tick();
            } catch (error) {
                console.warn("PABASA: Mic test meter unavailable", error);
                stopMicTestMeter();
            }
        }

        function stopMicTestMeter() {
            if (micTestMeterFrame) {
                window.cancelAnimationFrame(micTestMeterFrame);
                micTestMeterFrame = null;
            }
            micTestStatus?.classList.remove("is-hearing");
            micTestAnalyser = null;
            if (micTestAudioContext) {
                micTestAudioContext.close().catch(() => {});
                micTestAudioContext = null;
            }
            micTestLastHeardAt = 0;
            micTestNoiseFloor = 0;
            micTestSpeechFrameCount = 0;
        }

        function revokeMicSampleUrl() {
            if (micSampleAudioUrl) {
                URL.revokeObjectURL(micSampleAudioUrl);
                micSampleAudioUrl = "";
            }
            micSampleAudio = null;
        }

        function closePauseMenu() {
            pauseMenu?.classList.add("d-none");
            pauseOverlay?.classList.add("d-none");
        }

        function goBackToAssessments() {
            window.location.assign('/dashboard/assessment/');
        }

        prevBtn?.addEventListener("click", () => { 
            if (currentIndex > 0) { 
                transitionToItem(currentIndex - 1);
            } 
        });

        nextBtn?.addEventListener("click", () => {
            if (currentIndex < items.length - 1) { 
                transitionToItem(currentIndex + 1);
            } 
            else if (!isReviewMode) { showCompletion(true); }
        });

        function isInteractiveElement(element) {
            if (!element) return false;
            const tagName = element.tagName;
            if (!tagName) return false;
            if (["INPUT", "TEXTAREA", "SELECT", "BUTTON", "A"].includes(tagName)) return true;
            return element.isContentEditable;
        }

        document.addEventListener("keydown", function (event) {
            if (event.defaultPrevented) return;
            const activeElement = document.activeElement;
            if (isInteractiveElement(activeElement)) return;

            const isSpace = event.key === " " || event.key === "Spacebar" || event.code === "Space";
            if (isSpace) {
                if (btnStartReading && !btnStartReading.classList.contains("d-none")) {
                    btnStartReading.click();
                    event.preventDefault();
                    return;
                }

                if (nextBtn && !nextBtn.disabled) {
                    nextBtn.click();
                    event.preventDefault();
                }
                return;
            }

            if (event.key === "Escape") {
                if (!shell.classList.contains("is-complete") && !isReviewMode) {
                    showCompletion(true);
                } else if (finishBtn) {
                    finishBtn.click();
                } else {
                    goBackToAssessments();
                }
                event.preventDefault();
            }
        });

        pauseBtn?.addEventListener("click", () => {
            const isHidden = pauseMenu?.classList.contains("d-none");
            pauseMenu?.classList.toggle("d-none", !isHidden);
            pauseOverlay?.classList.toggle("d-none", !isHidden);
        });
        pauseOverlay?.addEventListener("click", closePauseMenu);
        resumeBtn?.addEventListener("click", closePauseMenu);
        retryBtn?.addEventListener("click", () => {
            if (isReviewMode) return;
            shell.classList.remove("is-complete");
            stopReadAloud();
            currentIndex = 0;
            currentSyllableIndex = 0;
            spokenTranscript = "";
            correctWordCounts = new Array(items.length).fill(0);
            pendingAudioChunk = null;
            hasHeardSinceLastChunk = false;
            resetRawMicInput("Waiting for speech...");
            updateUI();
            animateCurrentItem();
            setSpeechStatus("Ready to start reading");
            closePauseMenu();
        });
        quitBtn?.addEventListener("click", goBackToAssessments);
        reviewBtn?.addEventListener("click", () => { location.reload(); });
        finishBtn?.addEventListener("click", goBackToAssessments);

        if (isReviewMode) {
            [pauseBtn, btnStartReading, btnStopReading, btnToggleMic, btnTestMic].forEach((button) => button?.classList.add("d-none"));
            document.querySelector(".read-helper span:last-child")?.replaceChildren(document.createTextNode("Review your completed assessment. This view does not record or update your score."));
            if (testMeta) testMeta.innerHTML += ' <span style="background: rgba(148, 163, 184, 0.2); color: var(--muted); padding: 2px 8px; border-radius: 6px; font-size: 0.6em; vertical-align: middle; margin-left: 8px;">Review Mode</span>';

            const headerActions = document.querySelector(".header-actions");
            if (headerActions && !document.getElementById("btnBackAssessment")) {
                const backBtn = document.createElement("button");
                backBtn.id = "btnBackAssessment";
                backBtn.type = "button";
                backBtn.className = "header-action-btn";
                backBtn.title = "Back to assessments";
                backBtn.setAttribute("aria-label", "Back to assessments");
                backBtn.innerHTML = '<i class="bi bi-arrow-left"></i>';
                backBtn.addEventListener("click", goBackToAssessments);
                headerActions.prepend(backBtn);
            }
        }

        loadItems();
        startLiveCountdown();
    };

    if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", initReader);
    else initReader();
})();
