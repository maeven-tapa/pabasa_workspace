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
        const btnToggleMic = document.getElementById("btnToggleMic");
        const btnTestMic = document.getElementById("btnTestMic") || document.getElementById("testMic");

        const urlParams = new URLSearchParams(window.location.search);
        const testTitle = urlParams.get("test") || "Assessment";
        const testCode = urlParams.get("code") || "TST-000";
        const materialId = urlParams.get("id");
        const viewMode = urlParams.get("viewMode");
        const isReviewMode = viewMode === "view";
        const isRetakeMode = viewMode === "retake";
        if (testMeta) testMeta.textContent = `${testTitle} - ${testCode}`;

        let items = [];
        let currentIndex = 0;
        let isRecording = false;
        let isMuted = false;
        let startTime = null;
        let completionSubmitted = false;
        let recognition = null;
        let recognitionActive = false;
        let spokenTranscript = "";
        let latestScores = null;
        let mediaStream = null;
        let mediaRecorder = null;
        let isSendingChunk = false;
        let pendingAudioChunk = null;
        let currentSyllableIndex = 0;
        let currentMaterialLanguage = "";

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

        function loadItems() {
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
            if (items.length === 0) {
                if (readingWord) readingWord.textContent = "No assessment items assigned.";
                if (nextBtn) nextBtn.disabled = true;
                return;
            }
            currentIndex = 0;
            updateUI();
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
            const wpm = Math.round((targetWords.length / Math.max(durationSeconds / 60, 1 / 60)) * 100) / 100;
            const targetWpm = targetWpmForMode();
            const matchedWords = spokenWords.length ? lcsLength(targetWords, spokenWords) : 0;
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
                word_count: targetWords.length,
                transcript: spokenTranscript.trim(),
                speech_recognition_used: speechRecognitionUsed,
                needs_manual_review: needsManualReview,
                remarks: needsManualReview
                    ? "Speech recognition was unavailable or did not capture speech; teacher review is recommended."
                    : `CRLA classification: ${crlaClassification}.`
            };
        }

        function renderScoreSummary(scores) {
            const summary = document.querySelector(".completion-summary");
            if (!summary || !scores) return;
            summary.querySelectorAll("[data-score-tile]").forEach(tile => tile.remove());
            const tiles = [
                [`${Math.round(scores.fluency_score)}%`, "fluency"],
                [`${Math.round(scores.accuracy)}%`, "accuracy"],
                [`${Math.round(scores.pronunciation_score)}%`, "pronunciation"],
                [`${Math.round(scores.time_score)}%`, "time"],
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
            if (status) status.textContent = message;
            if (transcript) transcript.textContent = detail || "Google Speech results will appear here while you read.";
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

        async function startSpeechRecognition() {
            if (isReviewMode || isMuted || recognitionActive) return;
            if (!navigator.mediaDevices?.getUserMedia || !window.MediaRecorder) {
                setSpeechStatus("Speech recording is unavailable in this browser.", "Use a current Chrome or Edge browser for live Google Speech checking.");
                return;
            }
            try {
                mediaStream = await navigator.mediaDevices.getUserMedia({ audio: true });
                const mimeType = pickAudioMimeType();
                mediaRecorder = new MediaRecorder(mediaStream, mimeType ? { mimeType } : undefined);
                mediaRecorder.ondataavailable = (event) => {
                    if (event.data && event.data.size > 0 && isRecording && !isMuted) {
                        sendAudioChunk(event.data);
                    }
                };
                mediaRecorder.onerror = (event) => {
                    console.warn("PABASA: MediaRecorder error", event.error);
                    setSpeechStatus("Speech recorder error.", event.error?.message || "Please try starting again.");
                };
                mediaRecorder.start(3000);
                recognitionActive = true;
                setSpeechStatus("Listening with Google Speech...", "Read the text on screen. Correct syllables will highlight as they are confirmed.", true);
            } catch (error) {
                console.warn("PABASA: Microphone unavailable", error);
                setSpeechStatus("Microphone access was not allowed.", "Please allow microphone access and try again.");
            }
        }

        function stopSpeechRecognition() {
            try {
                if (mediaRecorder && mediaRecorder.state !== "inactive") {
                    mediaRecorder.stop();
                }
            } catch (error) {
                console.warn("PABASA: MediaRecorder stop failed", error);
            }
            mediaStream?.getTracks().forEach(track => track.stop());
            mediaStream = null;
            mediaRecorder = null;
            recognitionActive = false;
            pendingAudioChunk = null;
            shell?.classList.remove("is-recording");
            setSpeechStatus("Speech check stopped.", spokenTranscript || "No speech transcript was captured.");
        }

        async function sendAudioChunk(blob) {
            if (!items[currentIndex]) return;
            if (isSendingChunk) {
                pendingAudioChunk = blob;
                return;
            }
            isSendingChunk = true;
            const formData = new FormData();
            formData.append("audio", blob, `reading-${Date.now()}.webm`);
            formData.append("target_text", items[currentIndex]);
            formData.append("current_syllable_index", String(currentSyllableIndex));
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
                handleSpeechResult(data);
            } catch (error) {
                console.warn("PABASA: Reading transcription failed", error);
                setSpeechStatus("Speech check had trouble.", error.message || "Keep reading, then try again.");
            } finally {
                isSendingChunk = false;
                if (pendingAudioChunk && isRecording && !isMuted) {
                    const nextChunk = pendingAudioChunk;
                    pendingAudioChunk = null;
                    sendAudioChunk(nextChunk);
                }
            }
        }

        function handleSpeechResult(data) {
            const transcript = (data.transcript || "").trim();
            if (transcript) {
                spokenTranscript = [spokenTranscript, transcript].filter(Boolean).join(" ");
            }
            currentSyllableIndex = Number(data.current_syllable_index || currentSyllableIndex || 0);
            if (transcript || Number(data.matched || 0) > 0) {
                renderSyllableDisplay(data);
            }

            if (data.complete) {
                setSpeechStatus("Great job! You finished this item.", transcript ? `Words: ${transcript}` : "", true);
                if (currentIndex >= items.length - 1) {
                    isRecording = false;
                    stopSpeechRecognition();
                    showCompletion(true);
                } else {
                    window.setTimeout(() => {
                        currentIndex += 1;
                        currentSyllableIndex = 0;
                        updateUI();
                        setSpeechStatus("Next item loaded.", "Keep reading clearly.", true);
                    }, 700);
                }
                return;
            }

            if (Number(data.matched || 0) > 0) {
                setSpeechStatus(
                    `Matched ${data.matched} syllable${Number(data.matched) === 1 ? "" : "s"}.`,
                    `Words: ${transcript || "..."}${data.formatted_syllables ? " | Syllables: " + data.formatted_syllables : ""}`,
                    true
                );
            } else {
                const nextHint = data.next_syllable && data.next_word ? `Try again from: ${data.next_syllable} in ${data.next_word}` : "Keep reading.";
                setSpeechStatus(transcript ? nextHint : "Still listening...", transcript ? `Words: ${transcript}` : "Read when you are ready. The microphone is still active.", true);
            }
        }

        function renderSyllableDisplay(data) {
            if (!readingWord || !Array.isArray(data.words) || !Array.isArray(data.word_syllable_ranges)) return;
            readingWord.textContent = "";
            let readableWordIndex = 0;
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
                if (range[1] <= currentSyllableIndex) span.classList.add("is-read");
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
            if (readingWord) readingWord.textContent = items[currentIndex];
            currentSyllableIndex = 0;
            const label = mode.charAt(0).toUpperCase() + mode.slice(1);
            if (counter) counter.textContent = `${label} ${currentIndex + 1}/${items.length}`;
            if (progressFill) progressFill.style.width = `${((currentIndex + 1) / items.length) * 100}%`;
            
            if (prevBtn) prevBtn.disabled = isReviewMode ? currentIndex === 0 : (!isRecording || (currentIndex === 0));
            if (nextBtn) {
                nextBtn.disabled = isReviewMode ? currentIndex === items.length - 1 : (!isRecording || (currentIndex === items.length - 1));
                nextBtn.textContent = isReviewMode && currentIndex === items.length - 1 ? "Done" : "Next";
            }
        }

        function showCompletion(isFullCompletion) {
            stopSpeechRecognition();
            shell.classList.add("is-complete");
            closePauseMenu();
            if (completionCount) completionCount.textContent = items.length;
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
                const payload = {
                    material_id: materialId,
                    activity_type: 'assessment',
                    class_code: testCode,
                    scores: latestScores,
                };
                if (isRetakeMode) {
                    payload.is_retake = true;
                    const retakeCounts = JSON.parse(localStorage.getItem('pabasa_retake_counts') || '{}');
                    payload.attempt_number = retakeCounts[String(materialId).trim()] || 1;
                }
                if (String(materialId).toLowerCase().startsWith('assessment-')) {
                    payload.assessment_id = materialId;
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

        const startReading = () => {
            if (isReviewMode) return;
            isRecording = true;
            startTime = Date.now();
            spokenTranscript = "";
            latestScores = null;
            currentSyllableIndex = 0;
            pendingAudioChunk = null;
            btnStartReading?.classList.add("d-none");
            btnStopReading?.classList.remove("d-none");
            startSpeechRecognition();
            updateUI();
            console.log("PABASA: Assessment recording and timer started.");
        };

        const stopReading = async () => {
            if (isReviewMode) return;
            if (!isRecording) return;
            if (mediaRecorder && mediaRecorder.state === "recording") {
                try {
                    mediaRecorder.requestData();
                    await new Promise(resolve => window.setTimeout(resolve, 300));
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
            btnTestMic.addEventListener("click", () => {
                const title = "Microphone Check";
                const msg = "Testing device audio input ...\n\nYour microphone is receiving signal clearly! You are ready to start reading.";
                
                // Prioritize showDialog (styled modal) as it mimics the original alert behavior best
                if (typeof window.showDialog === 'function') {
                    window.showDialog(title, msg, "success");
                } else if (typeof window.showToast === 'function') {
                    window.showToast(msg.replace(/\n\n/g, ' '), "success");
                } else {
                    console.warn("PABASA: Notification utilities not found. Falling back to native alert.");
                    alert(title + "\n\n" + msg);
                }
            });
        }

        function closePauseMenu() {
            pauseMenu?.classList.add("d-none");
            pauseOverlay?.classList.add("d-none");
        }

        function goBackToAssessments() {
            if (window.history.length > 1) {
                window.history.back();
                return;
            }
            window.location.href = '/dashboard/assessment/';
        }

        prevBtn?.addEventListener("click", () => { 
            if (currentIndex > 0) { 
                currentIndex--; 
                updateUI(); 
            } 
        });

        nextBtn?.addEventListener("click", () => {
            if (currentIndex < items.length - 1) { 
                currentIndex++; 
                updateUI(); 
            } 
            else if (!isReviewMode) { showCompletion(true); }
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
            currentIndex = 0;
            currentSyllableIndex = 0;
            spokenTranscript = "";
            pendingAudioChunk = null;
            updateUI();
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
    };

    if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", initReader);
    else initReader();
})();
