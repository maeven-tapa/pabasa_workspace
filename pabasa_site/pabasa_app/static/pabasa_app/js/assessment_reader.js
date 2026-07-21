(function () {
    console.log("PABASA: Assessment Reader script loaded.");

    const initReader = () => {
        const shell = document.querySelector(".reader-shell");
        if (!shell) return;

        let mode = 'word'; 
        if (shell.classList.contains('reader-sentence')) mode = 'sentence';
        if (shell.classList.contains('reader-paragraph')) mode = 'paragraph';
        if (shell.classList.contains('reader-vowel')) mode = 'vowel';

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
        const micDeviceDropdown = document.getElementById("micDeviceDropdown");
        const micDeviceTrigger = document.getElementById("micDeviceTrigger");
        const micDeviceMenu = document.getElementById("micDeviceMenu");
        const micDeviceValue = document.getElementById("micDeviceValue");
        const micDeviceSelect = document.getElementById("micDeviceSelect");
        const rawMicInput = document.getElementById("rawMicInput");

        const urlParams = new URLSearchParams(window.location.search);
        const testTitle = urlParams.get("test") || "Assessment";
        const testCode = urlParams.get("code") || "TST-000";
        const materialId = urlParams.get("id");
        const viewMode = urlParams.get("viewMode");
        const isAssistMode = urlParams.get("assist") === "1";
        const assistToken = urlParams.get("assist_token") || "";
        const liveContent = urlParams.get("content") || "";
        const liveItemType = (urlParams.get("item_type") || urlParams.get("type") || "").toLowerCase();
        const liveLanguage = urlParams.get("language") || "";
        const isReviewMode = viewMode === "view";
        const isRetakeMode = viewMode === "retake";
        const isPractice = false;
        if (testMeta) testMeta.textContent = `${testTitle} - ${testCode}`;

        function isCurrentLiveAssessment() {
            if (isReviewMode || isRetakeMode) return false;
            const liveParam = urlParams.get('live');
            const liveSessionId = urlParams.get('live_session_id');
            const countdown = Number.parseInt(urlParams.get('countdown') || '10', 10);
            return liveParam === '1' && Boolean(liveSessionId) && Number.isFinite(countdown) && countdown >= 0;
        }

        let items = [];
        let currentIndex = 0;
        let isRecording = false;
        let isMuted = false;
        let startTime = null;
        let completionSubmitted = false;
        let completionSavePromise = Promise.resolve();
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
        const liveSessionId = urlParams.get("live_session_id");
        const liveSessionStateUrl = liveSessionId ? `/api/live-assessment/session/${liveSessionId}/` : null;
        let liveSessionPollTimer = null;
        let liveSessionPaused = false;
        let liveSessionEnded = false;
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
        let micDeviceOptionButtons = [];

        function setMicDropdownOpen(isOpen) {
            if (!micDeviceDropdown || !micDeviceTrigger) return;
            micDeviceDropdown.classList.toggle("is-open", Boolean(isOpen));
            micDeviceTrigger.setAttribute("aria-expanded", Boolean(isOpen));
        }

        function getMicDeviceLabel(option) {
            if (!option) return "Default microphone";
            if (!option.value) return "Default microphone";
            return option.textContent?.trim() || option.label || "Microphone";
        }

        function syncMicDropdownSelection() {
            if (!micDeviceSelect || !micDeviceValue || !micDeviceMenu) return;
            const selectedValue = micDeviceSelect.value || "";
            const options = Array.from(micDeviceSelect.options || []);
            const selectedOption = options.find(option => option.value === selectedValue) || options[0] || null;
            micDeviceValue.textContent = getMicDeviceLabel(selectedOption);

            micDeviceOptionButtons.forEach(button => {
                const isSelected = button.dataset.deviceId === selectedValue;
                button.classList.toggle("is-selected", isSelected);
                button.setAttribute("aria-selected", isSelected ? "true" : "false");
            });
        }

        function renderMicDeviceDropdown() {
            if (!micDeviceSelect || !micDeviceMenu) return;
            micDeviceMenu.replaceChildren();
            micDeviceOptionButtons = [];
            Array.from(micDeviceSelect.options || []).forEach((option, index) => {
                const button = document.createElement("button");
                button.type = "button";
                button.className = "mic-device-option";
                button.setAttribute("role", "option");
                button.dataset.deviceId = option.value || "";
                button.dataset.index = String(index);
                button.setAttribute("aria-selected", option.selected ? "true" : "false");
                const textWrap = document.createElement("span");
                textWrap.className = "mic-device-option-text";
                const title = document.createElement("span");
                title.className = "mic-device-option-title";
                title.textContent = option.value ? (option.textContent || option.label || "Microphone") : "Default microphone";
                const subtitle = document.createElement("span");
                subtitle.className = "mic-device-option-subtitle";
                subtitle.textContent = option.value ? "Connected audio input" : "Use the browser default input";
                textWrap.append(title, subtitle);
                const check = document.createElement("i");
                check.className = "bi bi-check2 mic-device-check";
                check.setAttribute("aria-hidden", "true");
                button.append(textWrap, check);
                button.addEventListener("click", () => {
                    micDeviceSelect.value = option.value || "";
                    micDeviceSelect.dispatchEvent(new Event("change", { bubbles: true }));
                    setMicDropdownOpen(false);
                });
                button.addEventListener("keydown", (event) => {
                    if (event.key === "ArrowDown") {
                        event.preventDefault();
                        focusMicOptionByOffset(button, 1);
                    } else if (event.key === "ArrowUp") {
                        event.preventDefault();
                        focusMicOptionByOffset(button, -1);
                    } else if (event.key === "Home") {
                        event.preventDefault();
                        micDeviceOptionButtons[0]?.focus();
                    } else if (event.key === "End") {
                        event.preventDefault();
                        micDeviceOptionButtons[micDeviceOptionButtons.length - 1]?.focus();
                    } else if (event.key === "Escape") {
                        event.preventDefault();
                        setMicDropdownOpen(false);
                        micDeviceTrigger?.focus();
                    } else if (event.key === "Enter" || event.key === " ") {
                        event.preventDefault();
                        button.click();
                    }
                });
                micDeviceMenu.appendChild(button);
                micDeviceOptionButtons.push(button);
            });
            syncMicDropdownSelection();
        }

        function toggleMicDropdown(forceOpen) {
            if (!micDeviceDropdown) return;
            const nextOpen = typeof forceOpen === "boolean"
                ? forceOpen
                : !micDeviceDropdown.classList.contains("is-open");
            setMicDropdownOpen(nextOpen);
            if (nextOpen) {
                syncMicDropdownSelection();
                const active = micDeviceOptionButtons.find(button => button.classList.contains("is-selected")) || micDeviceOptionButtons[0];
                active?.focus();
            }
        }

        function focusMicOptionByOffset(currentButton, offset) {
            if (!micDeviceOptionButtons.length) return;
            const currentIndex = Math.max(0, micDeviceOptionButtons.indexOf(currentButton));
            const nextIndex = (currentIndex + offset + micDeviceOptionButtons.length) % micDeviceOptionButtons.length;
            micDeviceOptionButtons[nextIndex]?.focus();
        }

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

        function hashString(value) {
            let hash = 0;
            const text = String(value || '');
            for (let i = 0; i < text.length; i += 1) {
                hash = ((hash << 5) - hash) + text.charCodeAt(i);
                hash |= 0;
            }
            return hash;
        }

        function stableShuffle(items, seed) {
            const array = items.slice();
            let currentIndex = array.length;
            let random = Math.abs(seed) || 0;
            while (currentIndex > 1) {
                random = ((random * 9301) + 49297) % 233280;
                const index = Math.floor((random / 233280) * currentIndex);
                currentIndex -= 1;
                const temp = array[currentIndex];
                array[currentIndex] = array[index];
                array[index] = temp;
            }
            return array;
        }

        function parseItems(material, currentMode) {
            const originalItems = Array.isArray(material.items)
                ? material.items.slice()
                : (material.content_json && Array.isArray(material.content_json.items))
                    ? material.content_json.items.slice()
                    : [];
            const normalizedItems = originalItems.map(item => String(item || '').trim()).filter(Boolean);
            if (material.content_json && material.content_json.randomize_order && normalizedItems.length > 0) {
                const seedSource = `${String(material.raw_id || material.id || '')}|${String(window.PABASA_USER_NAME || window.localStorage.getItem('pabasaUserName') || window.PABASA_USER_EMAIL || '').toLowerCase().trim()}`;
                const seed = hashString(seedSource);
                return stableShuffle(normalizedItems, seed);
            }
            if (normalizedItems.length > 0) {
                return normalizedItems;
            }
            if (material.content && typeof material.content === 'string') {
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

        function getOspsMultiplier(assessmentType) {
            const normalizedType = String(assessmentType || mode || "word").trim().toLowerCase();
            if (normalizedType.includes("vowel")) return 0.85;
            if (normalizedType.includes("sentence")) return 0.95;
            if (normalizedType.includes("paragraph")) return 1.00;
            return 0.90;
        }

        function classifyCRLA(totalScore) {
            return window.PABASA_READING_LEVEL?.getClassificationFromScore
                ? window.PABASA_READING_LEVEL.getClassificationFromScore(totalScore)
                : "";
        }

        function getPerformanceInterpretation(totalScore) {
            return window.PABASA_READING_LEVEL?.getPerformanceInterpretationFromScore
                ? window.PABASA_READING_LEVEL.getPerformanceInterpretationFromScore(totalScore)
                : "Needs Intensive Support";
        }

        function calculateFluencyScore(ratio, accuracy, isSkipped = false) {
            return window.PABASA_READING_LEVEL?.getFluencyScore
                ? window.PABASA_READING_LEVEL.getFluencyScore(ratio, accuracy, isSkipped)
                : (isSkipped || (Number(ratio) <= 0 && Number(accuracy) <= 0) ? 0 : 35);
        }

        function getAdaptedReadingLevel(totalScore, assessmentType = mode) {
            const helper = window.PABASA_READING_LEVEL;
            if (helper && helper.getReadingLevelFromScore) {
                return helper.getReadingLevelFromScore(totalScore, assessmentType).adapted_reading_level;
            }
            return "";
        }

        function calculateScores() {
            const targetText = items.join(" ");
            const targetWords = normalizeWords(targetText);
            const spokenWords = normalizeWords(spokenTranscript);
            const durationSeconds = Math.max(1, Math.round(((Date.now() - (startTime || Date.now())) / 1000) * 100) / 100);
            const matchedWords = correctWordsRead();
            const speechRecognitionUsed = spokenWords.length > 0;
            const targetWordCount = targetWords.length;
            const needsManualReview = !speechRecognitionUsed;

            return {
                accuracy: targetWordCount && speechRecognitionUsed ? Math.round((matchedWords / targetWordCount) * 10000) / 100 : 0,
                pronunciation_score: targetWordCount && speechRecognitionUsed ? Math.round((matchedWords / Math.max(spokenWords.length, targetWordCount)) * 10000) / 100 : 0,
                wpm: Math.round((matchedWords / Math.max(durationSeconds / 60, 1 / 60)) * 100) / 100,
                duration_seconds: durationSeconds,
                word_count: matchedWords,
                target_word_count: targetWordCount,
                transcript: spokenTranscript.trim(),
                speech_recognition_used: speechRecognitionUsed,
                needs_manual_review: needsManualReview,
                correct_words: matchedWords,
                incorrect_words: Math.max(0, targetWordCount - matchedWords),
                skipped_words: 0,
                raw_metrics: {
                    correct_words: matchedWords,
                    incorrect_words: Math.max(0, targetWordCount - matchedWords),
                    skipped_words: 0,
                    duration_seconds: durationSeconds,
                    target_word_count: targetWordCount,
                    pronunciation_metrics: { score: targetWordCount && speechRecognitionUsed ? Math.round((matchedWords / Math.max(spokenWords.length, targetWordCount)) * 10000) / 100 : 0 },
                    fluency_metrics: { score: null },
                },
                remarks: needsManualReview
                    ? "Speech recognition was unavailable or did not capture speech; teacher review is recommended."
                    : "Assessment scoring will be finalized by the server."
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

        function resolveClassificationLabel(scorePayload, fallback = "") {
            const helper = window.PABASA_READING_LEVEL;
            const totalScore = scorePayload?.final_score ?? scorePayload?.total_score ?? scorePayload?.overall_raw_score;
            if (helper?.getClassificationFromScore && totalScore !== undefined && totalScore !== null && totalScore !== "") {
                return helper.getClassificationFromScore(totalScore);
            }
            const explicitLevel = scorePayload?.crla_classification || scorePayload?.adapted_reading_level || scorePayload?.classification || scorePayload?.reading_level;
            if (explicitLevel) {
                return helper?.normalizeReadingLevelLabel?.(explicitLevel) || explicitLevel;
            }
            return fallback;
        }

        function normalizeCompletionScores(scores, fallback = {}) {
            const source = { ...(fallback || {}), ...(scores || {}) };
            return {
                ...source,
                accuracy: source.accuracy ?? fallback.accuracy ?? null,
                fluency_score: source.fluency_score ?? source.fluency ?? fallback.fluency_score ?? fallback.fluency ?? null,
                pronunciation_score: source.pronunciation_score ?? source.pronunciation ?? fallback.pronunciation_score ?? fallback.pronunciation ?? null,
                time_score: source.time_score ?? source.time ?? fallback.time_score ?? fallback.time ?? null,
                final_score: source.final_score ?? source.total_score ?? source.overall_raw_score ?? fallback.final_score ?? fallback.total_score ?? fallback.overall_raw_score ?? null,
                total_score: source.total_score ?? source.final_score ?? source.overall_raw_score ?? fallback.total_score ?? fallback.final_score ?? fallback.overall_raw_score ?? null,
                crla_classification: source.crla_classification ?? source.classification ?? fallback.crla_classification ?? fallback.classification ?? null,
                classification: source.classification ?? source.crla_classification ?? fallback.classification ?? fallback.crla_classification ?? null,
                adapted_reading_level: source.adapted_reading_level ?? source.reading_level ?? fallback.adapted_reading_level ?? fallback.reading_level ?? null,
                adapted_reading_level_disclaimer: source.adapted_reading_level_disclaimer ?? fallback.adapted_reading_level_disclaimer ?? null,
                word_count: source.word_count ?? source.correct_words ?? fallback.word_count ?? fallback.correct_words ?? null,
                correct_words: source.correct_words ?? source.word_count ?? fallback.correct_words ?? fallback.word_count ?? null,
                duration_seconds: source.duration_seconds ?? fallback.duration_seconds ?? null,
                target_word_count: source.target_word_count ?? fallback.target_word_count ?? null,
                wpm: source.wpm ?? fallback.wpm ?? null,
            };
        }

        function setCompletionActionButtonsProcessing(isProcessing) {
            [reviewBtn, finishBtn].filter(Boolean).forEach((button) => {
                button.disabled = Boolean(isProcessing);
                button.classList.toggle("is-processing", Boolean(isProcessing));
                button.style.opacity = Boolean(isProcessing) ? "0.65" : "";
                button.style.cursor = Boolean(isProcessing) ? "wait" : "";
                button.style.pointerEvents = Boolean(isProcessing) ? "none" : "";
                button.setAttribute("aria-busy", Boolean(isProcessing) ? "true" : "false");
            });
        }

        function renderScoreSummary(scores) {
            const summary = document.getElementById("completionSummary") || document.querySelector(".completion-summary");
            const disclaimer = document.getElementById("completionReadingLevelDisclaimer");
            if (!summary) return;
            const normalizedScores = normalizeCompletionScores(scores, {});
            summary.querySelectorAll("[data-score-tile]").forEach(tile => tile.remove());
            const readingTypeLabel = String(mode || "word").charAt(0).toUpperCase() + String(mode || "word").slice(1);
            const wordCount = normalizedScores.word_count != null ? String(Math.round(normalizedScores.word_count)) : "—";
            const accuracyValue = normalizedScores.accuracy != null ? `${Math.round(normalizedScores.accuracy)}%` : "—";
            const durationValue = normalizedScores.duration_seconds != null ? formatDuration(normalizedScores.duration_seconds) : "—";
            const fluencyValue = normalizedScores.fluency_score != null ? `${Math.round(normalizedScores.fluency_score)}%` : "—";
            const pronunciationValue = normalizedScores.pronunciation_score != null ? `${Math.round(normalizedScores.pronunciation_score)}%` : "—";
            const finalScoreValue = normalizedScores.final_score != null ? `${Math.round(normalizedScores.final_score)}%` : normalizedScores.total_score != null ? `${Math.round(normalizedScores.total_score)}%` : "—";
            const classificationValue = resolveClassificationLabel(normalizedScores) || "—";
            const tiles = [
                [wordCount, "correct words read"],
                [readingTypeLabel, "reading type"],
                [accuracyValue, "accuracy"],
                [durationValue, "reading time"],
                [fluencyValue, "fluency"],
                [pronunciationValue, "pronunciation"],
                [finalScoreValue, "final score"],
                [classificationValue, "reading classification"],
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
            if (disclaimer) {
                disclaimer.textContent = normalizedScores.adapted_reading_level_disclaimer || window.PABASA_READING_LEVEL?.DISCLAIMER || "Great job completing your reading assessment! Your results show your current reading performance. Keep practicing to improve your reading skills.";
            }
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
                    headers: {
                        "Accept": "application/json",
                        "X-Requested-With": "XMLHttpRequest",
                        "X-CSRFToken": getCsrfToken(),
                    },
                    credentials: "same-origin",
                    body: formData,
                });
                const responseText = await response.text();
                let data = null;
                try {
                    data = responseText ? JSON.parse(responseText) : {};
                } catch (parseError) {
                    const isHtml = /<!doctype|<html[\s>]/i.test(responseText || "");
                    throw new Error(isHtml
                        ? `The speech service returned a server page instead of data (HTTP ${response.status}).`
                        : "The speech service returned an invalid response.");
                }
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
            const completionSnapshot = calculateScores();
            latestScores = normalizeCompletionScores(latestScores || completionSnapshot, completionSnapshot);
            const summary = document.getElementById("completionSummary") || document.querySelector(".completion-summary");
            const disclaimer = document.getElementById("completionReadingLevelDisclaimer");
            if (summary) {
                summary.querySelectorAll("[data-score-tile]").forEach(tile => tile.remove());
            }
            if (disclaimer) {
                disclaimer.textContent = "Finalizing your assessment results...";
            }
            if (completionLevel) completionLevel.textContent = resolveClassificationLabel(latestScores, mode.charAt(0).toUpperCase() + mode.slice(1));
            
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

                                    if ((normalizedId && matId && normalizedId === matId) || (normalizedTitle && matTitle && normalizedTitle === matTitle)) {
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
                setCompletionActionButtonsProcessing(true);
                const elapsedSeconds = Math.max(1, Math.round(((Date.now() - (startTime || Date.now())) / 1000) * 100) / 100);
                const completionSnapshot = calculateScores();
                latestScores = latestScores || completionSnapshot;
                const completionMetrics = normalizeCompletionScores(completionSnapshot || {}, {});
                const payload = {
                    material_id: materialId,
                    activity_type: 'assessment',
                    class_code: testCode,
                    assessment_type: mode,
                    correct_words: completionMetrics.correct_words ?? completionMetrics.word_count ?? 0,
                    incorrect_words: completionMetrics.incorrect_words ?? 0,
                    skipped_words: completionMetrics.skipped_words ?? 0,
                    duration_seconds: completionMetrics.duration_seconds || elapsedSeconds,
                    target_word_count: completionMetrics.target_word_count ?? 0,
                    pronunciation_score: completionMetrics.pronunciation_score ?? 0,
                    fluency_score: completionMetrics.fluency_score ?? null,
                    time_score: completionMetrics.time_score ?? null,
                    transcript: completionMetrics.transcript || "",
                    speech_recognition_used: completionMetrics.speech_recognition_used ?? false,
                    needs_manual_review: completionMetrics.needs_manual_review ?? false,
                    wpm: completionMetrics.wpm ?? 0,
                    accuracy: completionMetrics.accuracy ?? null,
                    scores: {
                        ...(completionMetrics),
                        correct_words: completionMetrics.correct_words ?? completionMetrics.word_count ?? 0,
                        incorrect_words: completionMetrics.incorrect_words ?? 0,
                        skipped_words: completionMetrics.skipped_words ?? 0,
                        duration_seconds: completionMetrics.duration_seconds || elapsedSeconds,
                        target_word_count: completionMetrics.target_word_count ?? 0,
                        pronunciation_score: completionMetrics.pronunciation_score ?? 0,
                        fluency_score: completionMetrics.fluency_score ?? null,
                        time_score: completionMetrics.time_score ?? null,
                        transcript: completionMetrics.transcript || "",
                        speech_recognition_used: completionMetrics.speech_recognition_used ?? false,
                        needs_manual_review: completionMetrics.needs_manual_review ?? false,
                        wpm: completionMetrics.wpm ?? 0,
                        accuracy: completionMetrics.accuracy ?? null,
                    },
                    raw_metrics: {
                        correct_words: completionMetrics.correct_words ?? completionMetrics.word_count ?? 0,
                        incorrect_words: completionMetrics.incorrect_words ?? 0,
                        skipped_words: completionMetrics.skipped_words ?? 0,
                        duration_seconds: completionMetrics.duration_seconds || elapsedSeconds,
                        target_word_count: completionMetrics.target_word_count ?? 0,
                        pronunciation_metrics: {
                            score: completionMetrics.pronunciation_score ?? 0,
                        },
                        fluency_metrics: {
                            score: completionMetrics.fluency_score ?? null,
                        },
                        transcript: completionMetrics.transcript || "",
                        speech_recognition_used: completionMetrics.speech_recognition_used ?? false,
                        needs_manual_review: completionMetrics.needs_manual_review ?? false,
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
                if (assistToken) payload.assist_token = assistToken;
                completionSavePromise = fetch('/record-assessment-completion/', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json', 'X-CSRFToken': token },
                    credentials: 'same-origin',
                    body: JSON.stringify(payload)
                }).then(async r => {
                    const d = await r.json().catch(() => ({}));
                    if (!r.ok || !d.success) {
                        throw new Error(d.error || `Completion save failed (${r.status})`);
                    }
                    if (!isPractice) {
                        const backendScores = normalizeCompletionScores({
                            ...(latestScores || {}),
                            ...(d || {}),
                        }, completionSnapshot || {});
                        backendScores.fluency_score = d?.fluency_score ?? d?.fluency ?? backendScores.fluency_score ?? null;
                        backendScores.final_score = d?.final_score ?? d?.total_score ?? backendScores.final_score ?? backendScores.total_score ?? null;
                        backendScores.total_score = d?.total_score ?? d?.final_score ?? backendScores.total_score ?? backendScores.final_score ?? null;
                        backendScores.crla_classification = d?.crla_classification ?? d?.classification ?? backendScores.crla_classification ?? backendScores.classification ?? null;
                        backendScores.classification = d?.classification ?? d?.crla_classification ?? backendScores.classification ?? backendScores.crla_classification ?? null;
                        backendScores.adapted_reading_level = d?.adapted_reading_level ?? d?.reading_level ?? backendScores.adapted_reading_level ?? backendScores.reading_level ?? null;
                        backendScores.adapted_reading_level_disclaimer = d?.adapted_reading_level_disclaimer ?? backendScores.adapted_reading_level_disclaimer ?? null;
                        latestScores = backendScores;
                        if (completionCount) completionCount.textContent = latestScores.word_count != null ? String(Math.round(latestScores.word_count)) : "";
                        if (completionLevel) {
                            const classificationText = backendScores.crla_classification || backendScores.classification || backendScores.adapted_reading_level || backendScores.reading_level || resolveClassificationLabel(backendScores, mode.charAt(0).toUpperCase() + mode.slice(1));
                            completionLevel.textContent = classificationText || mode.charAt(0).toUpperCase() + mode.slice(1);
                        }
                        renderScoreSummary(latestScores);
                        const disclaimer = document.getElementById("completionReadingLevelDisclaimer");
                        if (disclaimer) {
                            disclaimer.textContent = latestScores.adapted_reading_level_disclaimer || window.PABASA_READING_LEVEL?.DISCLAIMER || "Great job completing your reading assessment! Your results show your current reading performance. Keep practicing to improve your reading skills.";
                        }
                    }
                    if (!isPractice && d.adapted_reading_level) {
                        try {
                            const storedStudents = JSON.parse(localStorage.getItem('pabasa_added_students') || '[]');
                            const updatedStudents = Array.isArray(storedStudents) ? storedStudents.map(student => {
                                const studentId = String(student?.id || student?.student_id || student?.custom_id || '').trim();
                                const responseStudentId = String(d.student_id || d.custom_id || '').trim();
                                const matches = studentId && responseStudentId && studentId === responseStudentId;
                                if (!matches) return student;
                                return {
                                    ...student,
                                    level: d.adapted_reading_level,
                                    reading_level: d.adapted_reading_level,
                                    adapted_reading_level: d.adapted_reading_level,
                                    adapted_reading_level_disclaimer: d.adapted_reading_level_disclaimer,
                                    reading_level_disclaimer: d.adapted_reading_level_disclaimer,
                                    total_score: latestScores?.final_score ?? latestScores?.total_score,
                                    assessment_type: mode,
                                    completed_at: new Date().toISOString(),
                                };
                            }) : [];
                            localStorage.setItem('pabasa_added_students', JSON.stringify(updatedStudents));
                        } catch (syncError) {
                            console.warn('PABASA: Could not sync updated reading level to localStorage', syncError);
                        }
                    }
                    console.log("PABASA: Assessment completion recorded.");
                    window.dispatchEvent(new CustomEvent('pabasa:assessment-completed', {
                        detail: {
                            assessmentType: mode,
                            totalScore: latestScores?.final_score ?? latestScores?.total_score,
                        }
                    }));
                    return d;
                }).catch(e => console.error("PABASA: Completion error", e)).finally(() => {
                    setCompletionActionButtonsProcessing(false);
                });
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

        async function fetchLiveSessionState() {
            if (!liveSessionStateUrl) return null;
            try {
                const response = await fetch(liveSessionStateUrl, {
                    cache: 'no-store',
                    credentials: 'same-origin',
                    headers: { Accept: 'application/json' },
                });
                if (!response.ok) return null;
                const payload = await response.json();
                return payload.success ? payload.session : null;
            } catch (error) {
                console.warn('PABASA: Live session state fetch failed', error);
                return null;
            }
        }

        function disableReaderInteractions(disabled) {
            [pauseBtn, btnStartReading, btnStopReading, btnReadAloud, btnToggleMic, btnTestMic, prevBtn, nextBtn].forEach((button) => {
                if (button) button.disabled = disabled;
            });
        }

        function showLiveSessionPaused() {
            if (pauseOverlay) pauseOverlay.classList.remove('d-none');
            if (pauseMenu) pauseMenu.classList.remove('d-none');
            // Hide interactive buttons for students — teacher controls resume/end
            if (resumeBtn) resumeBtn.style.display = 'none';
            if (retryBtn) retryBtn.style.display = 'none';
            if (quitBtn) quitBtn.style.display = 'none';
            const title = pauseMenu?.querySelector('.pause-title');
            const subtitle = pauseMenu?.querySelector('.pause-subtitle');
            if (title) title.textContent = 'Paused by teacher';
            if (subtitle) subtitle.textContent = 'Please wait until your teacher resumes the live assessment.';
            disableReaderInteractions(true);
            if (pauseBtn) pauseBtn.classList.add('d-none');
            if (isRecording && recognitionActive) {
                stopSpeechRecognition();
            }
            if (liveCountdownTimer) {
                clearLiveCountdown();
                hideLiveCountdown();
            }
            setSpeechStatus('Session paused by your teacher.', 'Please wait until the teacher resumes the assessment.', false);
        }

        function hideLiveSessionPaused() {
            if (pauseOverlay) pauseOverlay.classList.add('d-none');
            if (pauseMenu) pauseMenu.classList.add('d-none');
            // Keep pause control hidden for live assessments (students shouldn't control resume)
            if (pauseBtn) pauseBtn.classList.add('d-none');
            if (resumeBtn) resumeBtn.style.display = 'none';
            if (retryBtn) retryBtn.style.display = 'none';
            disableReaderInteractions(false);
            setSpeechStatus('Live session resumed. Continue reading when ready.', '', !isMuted && isRecording);
        }

        function showLiveSessionEnded() {
            liveSessionPaused = true;
            if (pauseOverlay) pauseOverlay.classList.remove('d-none');
            if (pauseMenu) pauseMenu.classList.remove('d-none');
            // Show exit button on session end so students can leave if needed
            if (resumeBtn) resumeBtn.style.display = 'none';
            if (retryBtn) retryBtn.style.display = 'none';
            if (quitBtn) quitBtn.style.display = '';
            const title = pauseMenu?.querySelector('.pause-title');
            const subtitle = pauseMenu?.querySelector('.pause-subtitle');
            if (title) title.textContent = 'Session ended';
            if (subtitle) subtitle.textContent = 'Your teacher has ended the live assessment.';
            if (pauseBtn) pauseBtn.classList.add('d-none');
            disableReaderInteractions(true);
            stopSpeechRecognition();
            stopReadAloud();
            if (liveCountdownTimer) {
                clearLiveCountdown();
                hideLiveCountdown();
            }
            setSpeechStatus('Live session ended.', 'Your teacher has ended the assessment.', false);
        }

        async function handleLiveSessionState(state) {
            if (!state || !state.status) return;
            if (state.status === 'paused') {
                if (!liveSessionPaused) {
                    liveSessionPaused = true;
                    liveSessionEnded = false;
                    showLiveSessionPaused();
                }
                return;
            }
            if (liveSessionPaused && state.status === 'started') {
                liveSessionPaused = false;
                liveSessionEnded = false;
                hideLiveSessionPaused();
                if (isRecording && !recognitionActive && !isMuted) {
                    startSpeechRecognition();
                }
            }
            if (state.status === 'ended') {
                if (!liveSessionEnded) {
                    liveSessionEnded = true;
                    showLiveSessionEnded();
                }
            }
        }

        async function pollLiveSessionState() {
            const state = await fetchLiveSessionState();
            await handleLiveSessionState(state);
        }

        function startLiveSessionPolling() {
            if (!liveSessionStateUrl) return;
            pollLiveSessionState();
            liveSessionPollTimer = window.setInterval(pollLiveSessionState, 2000);
        }

        function stopLiveSessionPolling() {
            if (liveSessionPollTimer) {
                window.clearInterval(liveSessionPollTimer);
                liveSessionPollTimer = null;
            }
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
            showCompletion(isAssistMode || reachedLastItem);
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
        micDeviceTrigger?.addEventListener("click", () => toggleMicDropdown());
        micDeviceTrigger?.addEventListener("keydown", (event) => {
            if (event.key === "ArrowDown" || event.key === "Enter" || event.key === " ") {
                event.preventDefault();
                toggleMicDropdown(true);
            } else if (event.key === "Escape") {
                setMicDropdownOpen(false);
            }
        });
        micDeviceSelect?.addEventListener("change", () => {
            selectedMicDeviceId = micDeviceSelect.value || "";
            localStorage.setItem("pabasaSelectedMicDeviceId", selectedMicDeviceId);
            revokeMicSampleUrl();
            micSamplePlayBtn?.setAttribute("disabled", "disabled");
            setMicTestStatus("Microphone selected. Record a sample to check it.");
            syncMicDropdownSelection();
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
        document.addEventListener("click", (event) => {
            if (!micDeviceDropdown?.contains(event.target)) setMicDropdownOpen(false);
        });
        document.addEventListener("keydown", (event) => {
            if (event.key === "Escape") setMicDropdownOpen(false);
        });

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
                renderMicDeviceDropdown();
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
            if (isAssistMode && window.parent && window.parent !== window) {
                window.parent.postMessage({
                    type: "pabasa-assist-returning",
                    materialId: materialId,
                }, window.location.origin);
                const notifyParent = () => {
                    window.parent.postMessage({
                        type: completionSubmitted ? "pabasa-assist-complete" : "pabasa-assist-exit",
                        materialId: materialId,
                    }, window.location.origin);
                };
                if (completionSubmitted) {
                    completionSavePromise.finally(notifyParent);
                } else {
                    notifyParent();
                }
                return;
            }
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

        if (isCurrentLiveAssessment()) {
            pauseBtn?.classList.add('d-none');
        }
        pauseBtn?.addEventListener("click", () => {
            const isHidden = pauseMenu?.classList.contains("d-none");
            pauseMenu?.classList.toggle("d-none", !isHidden);
            pauseOverlay?.classList.toggle("d-none", !isHidden);
        });
        pauseOverlay?.addEventListener("click", (event) => {
            if (!liveSessionPaused) closePauseMenu();
        });
        resumeBtn?.addEventListener("click", () => {
            if (!liveSessionPaused) closePauseMenu();
        });
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
        if (liveSessionStateUrl) {
            startLiveSessionPolling();
        }
    };

    if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", initReader);
    else initReader();
})();
