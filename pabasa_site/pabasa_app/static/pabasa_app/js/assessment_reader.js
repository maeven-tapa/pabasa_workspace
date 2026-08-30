(function () {
    console.log("PABASA: Assessment Reader script loaded.");

    const initReader = () => {
        const shell = document.querySelector(".reader-shell");
        if (!shell) return;

        let mode = 'word'; 
        if (shell.classList.contains('reader-sentence')) mode = 'sentence';
        if (shell.classList.contains('reader-paragraph')) mode = 'paragraph';
        if (shell.classList.contains('reader-vowel')) mode = 'vowel';
        if (shell.classList.contains('reader-phrase')) mode = 'phrase';

        const readingWord = document.getElementById("readingWord");
        const readingTitle = document.getElementById("readingTitle");
        const readingHelperText = document.getElementById("readingHelperText");
        const speechTranscript = document.getElementById("speechTranscript");
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
        const completionClassificationValue = document.getElementById("completionClassificationValue");
        const completionClassificationPanel = document.getElementById("completionClassificationPanel");
        const storySelectionPanel = document.getElementById("storySelectionPanel");
        const storySelectionGrid = document.getElementById("storySelectionGrid");
        const storySelectionTitle = document.getElementById("storySelectionTitle");
        const storySelectionSubtitle = document.getElementById("storySelectionSubtitle");
        const storyReadyInstruction = document.getElementById("storyReadyInstruction");
        const storyReadingProgress = document.getElementById("storyReadingProgress");
        const storyQuestionPanel = document.getElementById("storyQuestionPanel");
        const storyQuestionTitle = document.getElementById("storyQuestionTitle");
        const storyQuestionCounter = document.getElementById("storyQuestionCounter");
        const storyQuestionProgressFill = document.getElementById("storyQuestionProgressFill");
        const storyQuestionText = document.getElementById("storyQuestionText");
        const storyAnswerText = document.getElementById("storyAnswerText");
        const storyAnswerFeedback = document.getElementById("storyAnswerFeedback");
        const storyQuestionFinishReadingBtn = document.getElementById("storyQuestionFinishReadingBtn");
        const storyQuestionReadAloudBtn = document.getElementById("storyQuestionReadAloudBtn");
        const storyQuestionBackBtn = document.getElementById("storyQuestionBackBtn");
        const storyQuestionNextBtn = document.getElementById("storyQuestionNextBtn");
        const storyQuestionFinishBtn = document.getElementById("storyQuestionFinishBtn");
        const storyQuestionCompletion = document.getElementById("storyQuestionCompletion");
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
        const speechPanel = document.getElementById("speechPanel");
        const speechDebugToggle = document.getElementById("speechDebugToggle");

        // Keep the helper caption and optional debug panel in sync. The caption
        // therefore shows the speech assessment result, not a repeated prompt.
        if (readingHelperText && speechTranscript) {
            readingHelperText.textContent = speechTranscript.textContent;
        }

        const urlParams = new URLSearchParams(window.location.search);
        const isMyMaterials = window.__PABASA_MY_MATERIALS__ === true;
        const officialAssessmentId = urlParams.get("official_assessment_id") || "";
        const customMaterialData = window.__PABASA_CUSTOM_MATERIAL__ || null;
        let officialAssessmentData = officialAssessmentId
            ? (window.__PABASA_OFFICIAL_ASSESSMENT__ || null)
            : null;
        const isOfficialAssessmentLaunch = Boolean(officialAssessmentId);
        if (isOfficialAssessmentLaunch && !officialAssessmentData) {
            try {
                const rawOfficialData = urlParams.get("official_assessment_data") || "";
                if (rawOfficialData) officialAssessmentData = JSON.parse(rawOfficialData);
            } catch (error) {
                officialAssessmentData = null;
            }
        }
        const testTitle = (officialAssessmentData && officialAssessmentData.official_title) || customMaterialData?.title || urlParams.get("test") || "Assessment";
        const testCode = (officialAssessmentData && officialAssessmentData.official_code) || customMaterialData?.code || urlParams.get("code") || "TST-000";
        const sectionId = customMaterialData?.section_id || urlParams.get("section_id") || "";
        const materialId = (
            (officialAssessmentData && (officialAssessmentData.id || officialAssessmentData.material_id)) ||
            officialAssessmentId ||
            customMaterialData?.id ||
            urlParams.get("id") ||
            ""
        );
        const viewMode = urlParams.get("viewMode");
        const isAssistMode = urlParams.get("assist") === "1";
        const assistToken = urlParams.get("assist_token") || "";
        const liveContent = customMaterialData?.content || urlParams.get("content") || "";
        const liveItemType = (customMaterialData?.item_type || urlParams.get("item_type") || urlParams.get("type") || "").toLowerCase();
        const liveLanguage = customMaterialData?.language || urlParams.get("language") || "";
        console.log("PABASA_OFFICIAL_TRACE", {
            stage: "reader_url_params",
            requested_assessment_type: urlParams.get("test") || "",
            requested_system_assessment_key: urlParams.get("code") || "",
            selected_material_id: materialId || "",
            official_assessment_id: officialAssessmentId || "",
            official_assessment_data: officialAssessmentData,
            launch_url: window.location.href,
        });
        console.log("PABASA_OFFICIAL_TRACE", {
            stage: "reader_identity_resolved",
            resolved_material_id: materialId || "",
            official_assessment_id: officialAssessmentId || "",
            resolved_assessment_code: testCode || "",
            resolved_assessment_title: testTitle || "",
        });
        const isReviewMode = viewMode === "view";
        const isRetakeMode = viewMode === "retake";
        const isPractice = false;
        const updateAssessmentLanguageLabel = (language) => {
            const displayLanguage = /filipino|fil\b/i.test(String(language || "")) ? "Filipino" : "English";
            if (testMeta) testMeta.textContent = `${testTitle} - ${testCode} · Language: ${displayLanguage}`;
        };
        updateAssessmentLanguageLabel((officialAssessmentData && officialAssessmentData.language) || liveLanguage);

        function isCurrentLiveAssessment() {
            if (isReviewMode || isRetakeMode) return false;
            const liveParam = urlParams.get('live');
            const liveSessionId = urlParams.get('live_session_id');
            const countdown = Number.parseInt(urlParams.get('countdown') || '10', 10);
            return liveParam === '1' && Boolean(liveSessionId) && Number.isFinite(countdown) && countdown >= 0;
        }

        let items = [];
        let itemTypes = [];
        let itemPages = [];
        let itemTitles = [];
        let pageCorrectWordCounts = [];
        let currentIndex = 0;
        let currentPageIndex = 0;
        let paragraphWordResults = {};
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
        let completionLoadingStartTime = 0;
        let completionLoadingHideTimer = null;
        let completionResultsFallbackTimer = null;
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
        let currentSttLanguageCode = "";
        let currentAssessmentBranch = "words";
        let currentStoryChoices = [];
        let currentSelectedStory = null;
        let currentStoryState = "story_selection";
        let currentAssessmentUiMode = "standard";
        let currentStorySegmentIndex = 0;
        let currentStoryQuestions = [];
        let currentStoryAnswers = [];
        let currentStoryResults = [];
        let storyAnswerRecorder = null;
        let storyAnswerStream = null;
        let storyAnswerRecording = false;
        let storyAnswerUploadChain = Promise.resolve();
        let storyAnswerRecordingToken = 0;
        let storyBrowserRecognition = null;
        let storyBrowserFinalTranscript = "";
        let storyAnswerValidationPending = false;
        let currentStoryQuestionIndex = 0;
        let syllableStitchingContext = "";
        let syllableStitchingContextAt = 0;
        const syllableStitchingWindowMs = 4000;
        let liveCountdownTimer = null;
        let liveCountdownStarted = false;
        // CRLA Official Assessment: Item Locking
        // Track whether each item has been scored and locked (no further updates allowed)
        let itemLocked = [];
        let itemScores = [];
        let autoAdvanceTimer = null;
        let liveServerTimeOffsetMs = 0;
        const liveSessionId = urlParams.get("live_session_id");
        const liveSessionStateUrl = liveSessionId ? `/api/live-assessment/session/${liveSessionId}/` : null;
        let liveSessionPollTimer = null;
        let liveSessionPaused = false;
        let liveSessionEnded = false;
        let liveSessionHeartbeatTimer = null;
        let liveSessionLastHeartbeatAt = 0;

        function traceEndSession(event, details = {}) {
            try {
                console.log('[END_SESSION_TRACE][student-reader]', {
                    event,
                    liveSessionId,
                    liveSessionEnded,
                    liveSessionPaused,
                    isRecording,
                    recognitionActive,
                    currentIndex,
                    at: new Date().toISOString(),
                    ...details,
                });
            } catch (error) {}
        }

        let audioContext = null;
        let audioAnalyser = null;
        let audioMeterFrame = null;
        let lastHeardAt = 0;
        let hasHeardSinceLastChunk = false;
        let ambientNoiseFloor = 0;
        let speechFrameCount = 0;
        // Sentences, phrases, and paragraphs need enough context for reliable recognition.
        // Keep fast feedback for word/vowel assessments, but allow longer
        // recordings for continuous reading while remaining below Google's
        // 12-second transcription timeout.
        let speechChunkMs = ["sentence", "phrase", "paragraph"].includes(mode) ? 10000 : 2400;
        const speechLevelThreshold = 0.014;
        const speechNoiseMultiplier = 3.2;
        let micDeviceOptionButtons = [];

        function setCurrentItemMode(nextMode) {
            const normalized = String(nextMode || mode || "word").toLowerCase();
            mode = normalized;
            speechChunkMs = ["sentence", "phrase", "paragraph"].includes(mode) ? 10000 : 2400;
        }

        function setSpeechDebugPanelVisible(isVisible, persist = true) {
            const enabled = Boolean(isVisible);
            const shouldRender = enabled
                && !shell?.classList.contains("is-story-selection")
                && !shell?.classList.contains("is-story-ready-state")
                && !["story_comprehension", "story_complete"].includes(currentStoryState);
            speechPanel?.classList.toggle("d-none", !shouldRender);
            speechPanel?.toggleAttribute("hidden", !shouldRender);
            speechPanel?.setAttribute("aria-hidden", String(!shouldRender));
            shell?.classList.toggle("is-speech-debug-visible", shouldRender);
            if (speechDebugToggle) speechDebugToggle.checked = enabled;
            if (persist) {
                localStorage.setItem("pabasaShowSpeechDebugPanel", enabled ? "true" : "false");
            }
        }

        const persistedSpeechDebugSetting = localStorage.getItem("pabasaShowSpeechDebugPanel");
        setSpeechDebugPanelVisible(persistedSpeechDebugSetting === "true", false);

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

        const studentClassCodesKey = "pabasaStudentSectionIds";
        const readingsStorageKey = "pabasa_section_readings";
        const completedAssessmentIdsKey = "pabasa_completed_assessment_ids";
        const studentEndStateKeyBase = "pabasa_student_end_assessment_state";
        const studentEndStateVersion = "crla_grade2_v1";
        const studentEndStateResetKey = "pabasa_student_end_assessment_state_reset";

        function getStoredData(key, fallback = []) {
            try { return JSON.parse(localStorage.getItem(key) || JSON.stringify(fallback)); } catch (e) { return fallback; }
        }

        function getStudentEndStateKey() {
            const userId = String(window.PABASA_USER_ID || localStorage.getItem("pabasaUserId") || "").trim();
            const materialKey = String(materialId || testCode || "assessment").trim();
            return `${studentEndStateKeyBase}:${userId || "guest"}:${materialKey}`;
        }

        function readStudentEndState() {
            try {
                if (sessionStorage.getItem(studentEndStateResetKey) === "1") {
                    sessionStorage.removeItem(studentEndStateResetKey);
                    return {};
                }
                const raw = localStorage.getItem(getStudentEndStateKey());
                if (!raw) {
                    const serverState = window.__PABASA_STUDENT_END_STATE__ || {};
                    const serverMaterialId = String(serverState.material_id || "").trim();
                    return !serverMaterialId || serverMaterialId === String(officialAssessmentId || materialId || "").trim() ? serverState : {};
                }
                const parsed = JSON.parse(raw);
                return parsed && typeof parsed === "object" ? parsed : {};
            } catch (error) {
                return {};
            }
        }

        function writeStudentEndState(nextState) {
            const savedState = {
                version: studentEndStateVersion,
                ...(nextState || {}),
                material_id: String(officialAssessmentId || materialId || "").trim(),
                updated_at: new Date().toISOString(),
            };
            try {
                localStorage.setItem(getStudentEndStateKey(), JSON.stringify(savedState));
            } catch (error) {}
            if (savedState.stage) {
                return fetch('/api/assessment/end-state/', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCsrfToken() },
                    credentials: 'same-origin',
                    body: JSON.stringify(savedState),
                }).then(async response => {
                    const result = await response.json().catch(() => ({}));
                    if (!response.ok) {
                        console.warn('PABASA: Failed to persist CRLA end state', {
                            status: response.status,
                            stage: savedState.stage,
                            response: result,
                        });
                    }
                    return response.ok ? result : null;
                }).catch((error) => {
                    console.warn('PABASA: CRLA end-state request failed', {
                        stage: savedState.stage,
                        message: String(error?.message || error),
                    });
                    return null;
                });
            }
            return Promise.resolve(null);
        }

        function updateStudentEndState(patch) {
            const current = readStudentEndState();
            return writeStudentEndState({
                ...current,
                ...(patch || {}),
            });
        }

        // CRLA Official Assessment: Persist item score immediately when locked
        function persistLockedItemResult(itemIndex) {
            if (!isOfficialAssessmentLaunch || !itemLocked[itemIndex]) return;
            const itemScore = itemScores[itemIndex];
            if (!itemScore) return;
            
            // Save to localStorage for resilience
            try {
                const savedResults = JSON.parse(localStorage.getItem('crla_item_results') || '{}');
                const key = `${officialAssessmentId}_${itemIndex}`;
                savedResults[key] = itemScore;
                localStorage.setItem('crla_item_results', JSON.stringify(savedResults));
            } catch (error) {
                console.warn("[CRLA_STRICT_ASSESSMENT] Failed to persist item result to localStorage", error);
            }
            
            // Notify server immediately
            const endState = readStudentEndState();
            return updateStudentEndState({
                ...endState,
                last_locked_item_index: itemIndex,
                locked_items_count: (itemLocked.filter(Boolean) || []).length,
                updated_at: new Date().toISOString(),
            });
        }

        function clearStudentEndState() {
            try {
                localStorage.removeItem(getStudentEndStateKey());
            } catch (error) {}
            try {
                sessionStorage.setItem(studentEndStateResetKey, "1");
            } catch (error) {}
        }

        // A dashboard Start Assessment launch is an explicit fresh attempt.
        // Consume this marker before loadItems() so stale browser state cannot
        // override the reset server state, while transition URLs remain resumable.
        if (urlParams.get("crla_fresh") === "1") {
            clearStudentEndState();
            urlParams.delete("crla_fresh");
            const cleanLaunchUrl = new URL(window.location.href);
            cleanLaunchUrl.searchParams.delete("crla_fresh");
            window.history.replaceState({}, document.title, cleanLaunchUrl.toString());
        }

        function normalizeStudentEndStatus(value) {
            return String(value || "").trim().toLowerCase();
        }

        function getStudentEndStageFromScore(stageName, routingValue) {
            const score = Number(routingValue);
            if (stageName === "words") {
                return Number.isFinite(score) && score <= 6 ? "rhymes" : "sentences";
            }
            if (stageName === "sentences" || stageName === "rhymes") {
                return "story";
            }
            if (stageName === "story") {
                if (!Number.isFinite(score)) return "completed";
                return score < 25 ? "completed_high_emerging"
                    : score <= 50 ? "completed_developing"
                    : score <= 75 ? "completed_transitioning"
                    : "completed_grade_level";
            }
            return "completed";
        }

        function getStoryClassificationFromResult(storyReadPercent, correctAnswers) {
            const percent = Number(storyReadPercent);
            const correct = Number(correctAnswers);
                if (!Number.isFinite(percent) || !Number.isFinite(correct)) return "";
            const readingBand = percent <= 25 ? 0 : percent <= 50 ? 1 : percent <= 75 ? 2 : 3;
            const comprehensionBand = correct <= 0 ? 0 : correct <= 2 ? 1 : correct <= 4 ? 2 : 3;
            return [
                "High Emerging Reader",
                "Developing Reader",
                "Transitioning Reader",
                "Reading at Grade Level",
            ][Math.min(readingBand, comprehensionBand)];
        }

        function getStoryChoicesFromAssessment() {
            const passages = Array.isArray(officialAssessmentData?.passages) ? officialAssessmentData.passages : [];
            return passages
                .filter(item => item && typeof item === "object")
                .map(item => ({
                    title: String(item.title || "").trim(),
                    content: String(item.content || "").trim(),
                }))
                .filter(item => item.title || item.content);
        }

        function shortStoryPreview(text) {
            const source = String(text || "").trim().replace(/\s+/g, " ");
            if (!source) return "No story content available.";
            return source.length > 150 ? `${source.slice(0, 150)}...` : source;
        }

        function getStoryCardMeta(story) {
            const title = String(story?.title || "").trim().toLowerCase();
            if (title.includes("kakaibang") || title.includes("jeepney")) {
                return { category: "Everyday", duration: "4 min read", level: "Level 1", thumbnail: "reading9.jpg" };
            }
            if (title.includes("pagong") || title.includes("kuneho")) {
                return { category: "Fable", duration: "3 min read", level: "Level 1", thumbnail: "reading8.jpg" };
            }
            return { category: "Adventure", duration: "3 min read", level: "Level 1", thumbnail: "reading7.jpg" };
        }

        function getStoryQuestionsForTitle(storyTitle) {
            const normalizedTitle = String(storyTitle || "").trim().toLowerCase();
            const grouped = Array.isArray(officialAssessmentData?.story_qas) ? officialAssessmentData.story_qas : [];
            const questions = [];
            grouped.forEach(entry => {
                if (!entry || typeof entry !== "object") return;
                const entryTitle = String(entry.story_title || entry.title || "").trim().toLowerCase();
                if (entryTitle !== normalizedTitle) return;
                const entries = Array.isArray(entry.questions) ? entry.questions : [entry];
                entries.forEach(item => {
                    if (!item || typeof item !== "object") return;
                    const questionText = String(item.question || "").trim();
                    if (questionText) questions.push({ question: questionText });
                });
            });
            return questions;
        }

        function getVisibleStoryAnswerText() {
            return String(currentStoryAnswers[currentStoryQuestionIndex] || "").trim();
        }

        function syncStoryAnswerText() {
            if (!storyAnswerText) return;
            const answer = currentStoryAnswers[currentStoryQuestionIndex] || "";
            storyAnswerText.textContent = answer || "Your spoken answer will appear here.";
            storyAnswerText.classList.toggle("is-empty", !answer);
            if (storyAnswerFeedback) {
                storyAnswerFeedback.textContent = "";
                storyAnswerFeedback.classList.add("d-none");
            }
        }

        function updateStoryQuestionProgress() {
            const total = Math.max(1, currentStoryQuestions.length || 6);
            const current = Math.min(currentStoryQuestionIndex + 1, total);
            if (storyQuestionCounter) {
                storyQuestionCounter.textContent = `Question ${current} of ${total}`;
            }
            if (storyQuestionProgressFill) {
                storyQuestionProgressFill.style.width = `${(current / total) * 100}%`;
            }
            if (storyQuestionBackBtn) {
                storyQuestionBackBtn.disabled = currentStoryQuestionIndex <= 0;
            }
            if (storyQuestionNextBtn) {
                const isLast = currentStoryQuestionIndex >= total - 1;
                storyQuestionNextBtn.disabled = currentStoryResults[currentStoryQuestionIndex] === null;
                storyQuestionNextBtn.textContent = isLast ? "Finish" : "Next →";
            }
        }

        function renderCurrentStoryQuestion() {
            const question = currentStoryQuestions[currentStoryQuestionIndex] || null;
            if (storyQuestionTitle) {
                storyQuestionTitle.textContent = currentSelectedStory?.title || "Reading Comprehension";
            }
            if (storyQuestionText) {
                storyQuestionText.textContent = question?.question || "No comprehension question is available for this story.";
            }
            syncStoryAnswerText();
            updateStoryQuestionProgress();
            if (storyQuestionFinishReadingBtn) {
                storyQuestionFinishReadingBtn.disabled = false;
                storyQuestionFinishReadingBtn.textContent = "Start Reading";
            }
        }

        function appendStoryAnswerTranscript(transcript, questionIndex) {
            const detected = String(transcript || "").trim();
            if (!detected) return;
            const previous = String(currentStoryAnswers[questionIndex] || "").trim();
            currentStoryAnswers[questionIndex] = [previous, detected].filter(Boolean).join(" ");
            if (questionIndex === currentStoryQuestionIndex && storyAnswerText) {
                storyAnswerText.textContent = currentStoryAnswers[questionIndex];
                storyAnswerText.classList.remove("is-empty");
            }
        }

        async function uploadStoryAnswerChunk(blob, questionIndex, recordingToken) {
            if (!blob?.size || recordingToken !== storyAnswerRecordingToken) return;
            const formData = new FormData();
            formData.append("audio", blob, `story-answer.${audioExtensionForBlob(blob)}`);
            formData.append("material_id", materialId);
            formData.append("story_title", currentSelectedStory?.title || "");
            formData.append("question_index", String(questionIndex));
            const response = await fetch("/api/assessment/story-answer/transcribe/", {
                method: "POST", credentials: "same-origin",
                headers: { "X-CSRFToken": getCsrfToken() }, body: formData,
            });
            const result = await response.json();
            if (!response.ok || !result.success) throw new Error(result.error || "Speech recognition failed");
            appendStoryAnswerTranscript(result.transcript, questionIndex);
        }

        async function checkStoryAnswerTranscript(answer, questionIndex) {
            const response = await fetch("/api/assessment/story-answer/check/", {
                method: "POST", credentials: "same-origin",
                headers: { "Content-Type": "application/json", "X-CSRFToken": getCsrfToken() },
                body: JSON.stringify({
                    material_id: materialId,
                    story_title: currentSelectedStory?.title || "",
                    question_index: questionIndex,
                    answer,
                }),
            });
            const result = await response.json();
            if (!response.ok || !result.success) throw new Error(result.error || "Answer check failed");
            return Boolean(result.is_correct);
        }

        async function validateLiveStoryAnswer(answer, questionIndex, recordingToken) {
            const spokenAnswer = String(answer || "").trim();
            if (!spokenAnswer || storyAnswerValidationPending || !storyAnswerRecording) return;
            storyAnswerValidationPending = true;
            try {
                const isCorrect = await checkStoryAnswerTranscript(spokenAnswer, questionIndex);
                if (recordingToken !== storyAnswerRecordingToken || questionIndex !== currentStoryQuestionIndex) return;
                if (isCorrect) {
                    currentStoryAnswers[questionIndex] = spokenAnswer;
                    currentStoryResults[questionIndex] = true;
                    storyAnswerFeedback.textContent = "Correct answer detected. Submitting…";
                    storyAnswerFeedback.classList.remove("d-none");
                    await finishStoryAnswerRecording(true);
                    return;
                }
                storyBrowserFinalTranscript = "";
                currentStoryAnswers[questionIndex] = "";
                if (storyAnswerText) {
                    storyAnswerText.textContent = "Your spoken answer will appear here.";
                    storyAnswerText.classList.add("is-empty");
                }
                storyAnswerFeedback.textContent = "Try again. Listening for your answer…";
                storyAnswerFeedback.classList.remove("d-none");
            } catch (error) {
                console.warn("PABASA: Live story answer validation failed", error);
                storyAnswerFeedback.textContent = "We could not check that answer yet. Please say it again.";
                storyAnswerFeedback.classList.remove("d-none");
            } finally {
                storyAnswerValidationPending = false;
            }
        }

        async function startStoryAnswerRecording() {
            if (storyAnswerRecording || !currentStoryQuestions.length) return;
            const BrowserSpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
            if (!BrowserSpeechRecognition && (!navigator.mediaDevices?.getUserMedia || !window.MediaRecorder)) {
                storyAnswerFeedback.textContent = "Speech recognition is unavailable in this browser.";
                storyAnswerFeedback.classList.remove("d-none");
                return;
            }
            const questionIndex = currentStoryQuestionIndex;
            const recordingToken = ++storyAnswerRecordingToken;
            storyAnswerValidationPending = false;
            currentStoryAnswers[questionIndex] = "";
            currentStoryResults[questionIndex] = null;
            syncStoryAnswerText();
            try {
                if (BrowserSpeechRecognition) {
                    storyBrowserFinalTranscript = "";
                    storyBrowserRecognition = new BrowserSpeechRecognition();
                    storyBrowserRecognition.lang = /filipino|fil\b/i.test(currentMaterialLanguage || "") ? "fil-PH" : "en-US";
                    storyBrowserRecognition.continuous = true;
                    storyBrowserRecognition.interimResults = true;
                    storyBrowserRecognition.onresult = event => {
                        let interimTranscript = "";
                        let receivedFinalResult = false;
                        for (let index = event.resultIndex; index < event.results.length; index += 1) {
                            const detected = String(event.results[index][0]?.transcript || "").trim();
                            if (event.results[index].isFinal) {
                                storyBrowserFinalTranscript = [storyBrowserFinalTranscript, detected].filter(Boolean).join(" ");
                                receivedFinalResult = true;
                            } else {
                                interimTranscript = [interimTranscript, detected].filter(Boolean).join(" ");
                            }
                        }
                        const visibleTranscript = [storyBrowserFinalTranscript, interimTranscript].filter(Boolean).join(" ").trim();
                        currentStoryAnswers[questionIndex] = visibleTranscript;
                        if (questionIndex === currentStoryQuestionIndex && storyAnswerText) {
                            storyAnswerText.textContent = visibleTranscript || "Listening…";
                            storyAnswerText.classList.toggle("is-empty", !visibleTranscript);
                        }
                        if (receivedFinalResult) {
                            validateLiveStoryAnswer(storyBrowserFinalTranscript, questionIndex, recordingToken);
                        }
                    };
                    storyBrowserRecognition.onerror = event => {
                        if (event.error === "no-speech" && storyAnswerRecording) return;
                        storyAnswerFeedback.textContent = event.error === "not-allowed"
                            ? "Please allow microphone access, then try again."
                            : "Speech recognition had trouble. Tap Start Reading and try again.";
                        storyAnswerFeedback.classList.remove("d-none");
                    };
                    storyBrowserRecognition.onend = () => {
                        if (storyAnswerRecording && storyBrowserRecognition) {
                            try { storyBrowserRecognition.start(); } catch (error) {}
                        }
                    };
                    storyAnswerRecording = true;
                    storyBrowserRecognition.start();
                    storyQuestionFinishReadingBtn.textContent = "Finish Reading";
                    storyQuestionFinishReadingBtn.classList.add("is-recording");
                    storyQuestionBackBtn.disabled = true;
                    storyQuestionNextBtn.disabled = true;
                    storyAnswerFeedback.textContent = "Listening… Speak your answer clearly.";
                    storyAnswerFeedback.classList.remove("d-none");
                    return;
                }
                storyAnswerStream = await navigator.mediaDevices.getUserMedia(microphoneConstraints());
                const mimeType = pickAudioMimeType();
                storyAnswerRecorder = new MediaRecorder(storyAnswerStream, mimeType ? { mimeType } : undefined);
                storyAnswerUploadChain = Promise.resolve();
                storyAnswerRecorder.ondataavailable = event => {
                    if (!event.data?.size) return;
                    storyAnswerUploadChain = storyAnswerUploadChain
                        .then(() => uploadStoryAnswerChunk(event.data, questionIndex, recordingToken))
                        .catch(error => {
                            console.warn("PABASA: Story answer recognition failed", error);
                            storyAnswerFeedback.textContent = "We could not recognize that speech. Please try again.";
                            storyAnswerFeedback.classList.remove("d-none");
                        });
                };
                storyAnswerRecorder.start();
                storyAnswerRecording = true;
                storyQuestionFinishReadingBtn.textContent = "Finish Reading";
                storyQuestionFinishReadingBtn.classList.add("is-recording");
                storyQuestionBackBtn.disabled = true;
                storyQuestionNextBtn.disabled = true;
                storyAnswerFeedback.textContent = "Listening… Speak your answer clearly.";
                storyAnswerFeedback.classList.remove("d-none");
            } catch (error) {
                storyAnswerStream?.getTracks().forEach(track => track.stop());
                storyAnswerStream = null;
                storyAnswerFeedback.textContent = "Please allow microphone access, then try again.";
                storyAnswerFeedback.classList.remove("d-none");
            }
        }

        async function finishStoryAnswerRecording(alreadyValidated = false) {
            if (!storyAnswerRecording) return;
            const questionIndex = currentStoryQuestionIndex;
            storyAnswerRecording = false;
            storyQuestionFinishReadingBtn.disabled = true;
            storyQuestionFinishReadingBtn.textContent = "Checking…";
            if (storyBrowserRecognition) {
                try { storyBrowserRecognition.stop(); } catch (error) {}
                storyBrowserRecognition = null;
                await new Promise(resolve => window.setTimeout(resolve, 350));
            }
            const stopped = new Promise(resolve => {
                if (!storyAnswerRecorder || storyAnswerRecorder.state === "inactive") return resolve();
                storyAnswerRecorder.addEventListener("stop", resolve, { once: true });
                storyAnswerRecorder.requestData();
                storyAnswerRecorder.stop();
            });
            await stopped;
            storyAnswerStream?.getTracks().forEach(track => track.stop());
            storyAnswerStream = null;
            storyAnswerRecorder = null;
            await storyAnswerUploadChain;
            const answer = String(currentStoryAnswers[questionIndex] || "").trim();
            if (answer && alreadyValidated) {
                currentStoryResults[questionIndex] = true;
                storyAnswerFeedback.textContent = "Correct answer captured. You may continue.";
            } else if (answer) {
                try {
                    currentStoryResults[questionIndex] = await checkStoryAnswerTranscript(answer, questionIndex);
                    storyAnswerFeedback.textContent = "Answer captured. You may continue.";
                } catch (error) {
                    storyAnswerFeedback.textContent = "We could not evaluate that answer. Please try again.";
                }
            } else {
                storyAnswerFeedback.textContent = "No speech was detected. Tap Start Reading and try again.";
            }
            storyAnswerFeedback.classList.remove("d-none");
            storyQuestionFinishReadingBtn.disabled = false;
            storyQuestionFinishReadingBtn.textContent = "Start Reading";
            storyQuestionFinishReadingBtn.classList.remove("is-recording");
            updateStoryQuestionProgress();
        }

        async function showStoryCompletionScreen() {
            currentStoryState = "story_complete";
            const readingScores = calculateScores();
            const answered = currentStoryAnswers.filter(answer => String(answer || "").trim()).length;
            const correctAnswers = currentStoryResults.filter(result => result === true).length;
            const accuracy = answered ? Math.round((correctAnswers / answered) * 100) : 0;
            const totalStoryWords = Math.max(1, readableWordCount(currentSelectedStory?.content || ""));
            const storyReadPercent = Math.min(100, Math.round((correctWordsRead() / totalStoryWords) * 100));
            const classification = getStoryClassificationFromResult(storyReadPercent, correctAnswers);
            latestScores = {
                ...readingScores,
                correct_answers: correctAnswers,
                comprehension_correct: correctAnswers,
                correct_items: correctAnswers,
                total_items: currentStoryQuestions.length,
                accuracy,
                story_read_percent: storyReadPercent,
                total_story_words: totalStoryWords,
                words_read: correctWordsRead(),
                miscues: Math.max(0, totalStoryWords - correctWordsRead()),
                total_questions: currentStoryQuestions.length,
            };
            storyQuestionPanel?.classList.add("is-complete");
            if (storyQuestionCompletion) storyQuestionCompletion.classList.remove("d-none");
            storyQuestionPanel?.classList.remove("d-none");
            [storyQuestionTitle, storyQuestionCounter, storyQuestionProgressFill, storyQuestionText, storyAnswerText, storyQuestionBackBtn, storyQuestionNextBtn].forEach((node) => {
                if (node) {
                    node.classList.add("d-none");
                }
            });
            if (storyQuestionBackBtn) storyQuestionBackBtn.disabled = true;
            if (storyQuestionNextBtn) storyQuestionNextBtn.disabled = true;
            if (storyQuestionFinishBtn) storyQuestionFinishBtn.disabled = false;
            const classificationValue = document.getElementById("storyResultsClassificationTitle");
            if (classificationValue) classificationValue.textContent = classification || "Completed";
            const resultMessages = {
                "High Emerging Reader": "Great work finishing your CRLA reading assessment. Keep practicing—you’re making progress with every page you read.",
                "Developing Reader": "Great work finishing your CRLA reading assessment. Keep reading and practicing to build your skills even further.",
                "Transitioning Reader": "Great work finishing your CRLA reading assessment. You’re making great progress—keep reading to strengthen your skills.",
                "Reading at Grade Level": "Excellent work finishing your CRLA reading assessment. Keep reading and challenging yourself with new stories!",
                "Reader at Grade Level": "Excellent work finishing your CRLA reading assessment. Keep reading and challenging yourself with new stories!",
            };
            const resultsMessage = document.getElementById("storyResultsMessage");
            if (resultsMessage) {
                resultsMessage.textContent = resultMessages[classification]
                    || "Great work finishing your CRLA reading assessment. Keep reading and practicing to build your skills even further.";
            }
            const persistedState = await updateStudentEndState({
                stage: "completed",
                selected_story: currentSelectedStory?.title || "",
                story_read_percent: storyReadPercent,
                correct_words_percentage: storyReadPercent,
                total_words_read: correctWordsRead(),
                total_story_words: totalStoryWords,
                miscues: Math.max(0, totalStoryWords - correctWordsRead()),
                duration_seconds: readingScores.duration_seconds ?? null,
                wpm: readingScores.wpm ?? null,
                correct_answers: correctAnswers,
                total_questions: currentStoryQuestions.length,
                comprehension_correct: correctAnswers,
                comprehension_total: currentStoryQuestions.length,
                story_total_words: totalStoryWords,
                words_read: correctWordsRead(),
                classification,
            });
            await showCompletion(true);
            if (!isAssistMode && persistedState?.next_url) {
                window.location.assign(persistedState.next_url);
            }
        }

        function hideStoryCompletionScreen() {
            storyQuestionPanel?.classList.remove("is-complete");
            if (storyQuestionCompletion) storyQuestionCompletion.classList.add("d-none");
            [storyQuestionTitle, storyQuestionCounter, storyQuestionProgressFill, storyQuestionText, storyAnswerText, storyQuestionBackBtn, storyQuestionNextBtn].forEach((node) => {
                if (node) {
                    node.classList.remove("d-none");
                }
            });
        }

        function hideStoryPanels() {
            storySelectionPanel?.classList.add("d-none");
            storyQuestionPanel?.classList.add("d-none");
            storyReadyInstruction?.classList.add("d-none");
            storyReadingProgress?.classList.add("d-none");
        }

        function updateStandardAssessmentControls() {
            currentAssessmentUiMode = "standard";
            btnStartReading?.classList.remove("d-none");
            btnStopReading?.classList.add("d-none");
            btnReadAloud?.classList.remove("d-none");
            btnReadAloud?.classList.remove("is-playing");
            prevBtn?.classList.remove("d-none");
            nextBtn?.classList.remove("d-none");
        }

        function renderStoryQuestions(storyTitle) {
            const questions = getStoryQuestionsForTitle(storyTitle);
            currentStoryQuestions = questions.length ? questions.slice(0, 6) : [];
            currentStoryQuestionIndex = 0;
            currentStoryAnswers = new Array(currentStoryQuestions.length).fill("");
            currentStoryResults = new Array(currentStoryQuestions.length).fill(null);
            if (storyQuestionTitle) storyQuestionTitle.textContent = storyTitle || "Selected story";
            hideStoryCompletionScreen();
            renderCurrentStoryQuestion();
        }

        function renderStorySelectionState() {
            currentStoryState = "story_selection";
            currentAssessmentUiMode = "story";
            hideStoryPanels();
            if (storySelectionPanel) storySelectionPanel.classList.remove("d-none");
            if (readingWord) {
                readingWord.hidden = true;
                readingWord.textContent = "Choose a story to continue.";
            }
            if (readingTitle) readingTitle.hidden = true;
            btnStartReading?.classList.add("d-none");
            btnStopReading?.classList.add("d-none");
            btnReadAloud?.classList.add("d-none");
            prevBtn?.classList.add("d-none");
            nextBtn?.classList.add("d-none");
            updateFooterForStoryState("story_selection");
            if (storySelectionPanel) storySelectionPanel.scrollIntoView({ behavior: "smooth", block: "start" });
        }

        function renderStoryReadyState(story) {
            currentStoryState = "story_ready";
            currentAssessmentUiMode = "story";
            if (recognitionActive) stopSpeechRecognition();
            isRecording = false;
            hideStoryPanels();
            if (readingWord) {
                readingWord.hidden = true;
                const segments = splitTextIntoDisplayPages(story.content || "", "story");
                currentStorySegmentIndex = Math.min(currentStorySegmentIndex, Math.max(0, segments.length - 1));
                readingWord.textContent = "";
            }
            if (readingTitle) {
                readingTitle.hidden = false;
                readingTitle.textContent = story.title || "";
            }
            storyReadyInstruction?.classList.remove("d-none");
            btnStartReading?.classList.remove("d-none");
            if (btnStartReading) {
                btnStartReading.disabled = false;
                btnStartReading.innerHTML = '<i class="bi bi-play-fill"></i> Start Reading';
                btnStartReading.classList.remove("is-playing");
                btnStartReading.removeAttribute("aria-busy");
                delete btnStartReading.dataset.speechProcessingState;
            }
            btnStopReading?.classList.add("d-none");
            btnReadAloud?.classList.add("d-none");
            prevBtn?.classList.add("d-none");
            nextBtn?.classList.add("d-none");
            updateFooterForStoryState("story_ready");
        }

        function renderStoryReadingState(story) {
            currentStoryState = "story_reading";
            currentAssessmentUiMode = "story";
            hideStoryPanels();
            if (readingWord) {
                readingWord.hidden = false;
                readingWord.textContent = getCurrentDisplayText() || "Selected story has no content.";
            }
            if (readingTitle) {
                readingTitle.hidden = false;
                readingTitle.textContent = story.title || "";
            }
            if (storyReadingProgress) {
                storyReadingProgress.textContent = `${currentPageIndex + 1} / ${getCurrentPageCount()}`;
                storyReadingProgress.classList.remove("d-none");
            }
            btnStartReading?.classList.remove("d-none");
            btnStopReading?.classList.add("d-none");
            btnReadAloud?.classList.remove("d-none");
            prevBtn?.classList.remove("d-none");
            nextBtn?.classList.remove("d-none");
            if (prevBtn) prevBtn.disabled = currentPageIndex <= 0;
            if (nextBtn) {
                nextBtn.disabled = false;
                nextBtn.textContent = "Next →";
            }
            if (prevBtn) prevBtn.textContent = "← Back";
            if (counter) counter.textContent = `Story segment ${currentPageIndex + 1}/${getCurrentPageCount()}`;
            if (progressFill) progressFill.style.width = `${((currentPageIndex + 1) / getCurrentPageCount()) * 100}%`;
            updateFooterForStoryState("story_reading");
        }

        function renderStoryComprehensionState(storyTitle) {
            currentStoryState = "story_comprehension";
            currentAssessmentUiMode = "story";
            hideStoryPanels();
            if (storyQuestionPanel) storyQuestionPanel.classList.remove("d-none");
            if (readingWord) {
                readingWord.hidden = true;
                readingWord.textContent = "";
            }
            if (readingTitle) readingTitle.hidden = true;
            storyReadingProgress?.classList.add("d-none");
            renderStoryQuestions(storyTitle);
            btnStartReading?.classList.add("d-none");
            btnStopReading?.classList.add("d-none");
            btnReadAloud?.classList.add("d-none");
            prevBtn?.classList.add("d-none");
            nextBtn?.classList.add("d-none");
            updateFooterForStoryState("story_comprehension");
        }

        function renderStorySelection() {
            if (!storySelectionPanel || !storySelectionGrid) return;
            const choices = currentStoryChoices.length ? currentStoryChoices : getStoryChoicesFromAssessment();
            currentStoryChoices = choices;
            storySelectionGrid.replaceChildren();
            if (storySelectionTitle) storySelectionTitle.textContent = "Choose a story";
            if (storySelectionSubtitle) storySelectionSubtitle.textContent = "Choose one story to begin.";
            choices.forEach((story) => {
                const card = document.createElement("article");
                card.className = "story-choice-card";
                const isSelected = currentSelectedStory && String(currentSelectedStory.title || "").trim().toLowerCase() === String(story.title || "").trim().toLowerCase();
                if (isSelected) card.classList.add("is-selected");
                const meta = getStoryCardMeta(story);
                const imageUrl = `/static/pabasa_app/images/${meta.thumbnail}`;
                card.setAttribute("role", "button");
                card.setAttribute("tabindex", "0");
                card.setAttribute("aria-label", `Read story ${story.title || "Untitled story"}`);
                card.addEventListener("click", () => selectStoryChoice(story));
                card.addEventListener("keydown", (event) => {
                    if (event.key === "Enter" || event.key === " ") {
                        event.preventDefault();
                        selectStoryChoice(story);
                    }
                });
                if (isSelected) card.setAttribute("aria-pressed", "true");
                else card.setAttribute("aria-pressed", "false");

                const banner = document.createElement("div");
                banner.className = "story-choice-banner";
                banner.style.backgroundImage = `linear-gradient(135deg, rgba(31,111,139,0.22), rgba(122,139,95,0.18)), url('${imageUrl}')`;

                const badgeRow = document.createElement("div");
                badgeRow.className = "story-choice-badges";
                const categoryBadge = document.createElement("span");
                categoryBadge.className = "story-choice-badge";
                categoryBadge.textContent = meta.category;
                const durationBadge = document.createElement("span");
                durationBadge.className = "story-choice-badge";
                durationBadge.textContent = meta.duration;
                const levelBadge = document.createElement("span");
                levelBadge.className = "story-choice-badge";
                levelBadge.textContent = meta.level;
                badgeRow.append(categoryBadge, durationBadge, levelBadge);

                const title = document.createElement("h3");
                title.textContent = story.title || "Untitled story";
                const previewWrap = document.createElement("div");
                previewWrap.className = "story-choice-preview";
                const snippet = document.createElement("p");
                snippet.textContent = shortStoryPreview(story.content);
                previewWrap.appendChild(snippet);
                const actions = document.createElement("div");
                actions.className = "story-choice-actions";
                const button = document.createElement("button");
                button.type = "button";
                button.className = "btn btn-primary rounded-pill w-100 story-selection-cta";
                button.textContent = isSelected ? "Selected" : "Read Story →";
                button.disabled = Boolean(isSelected);
                button.addEventListener("click", (event) => {
                    event.stopPropagation();
                    selectStoryChoice(story);
                });
                actions.appendChild(button);
                card.append(banner, badgeRow, title, previewWrap, actions);
                storySelectionGrid.appendChild(card);
            });
            renderStorySelectionState();
        }

        function selectStoryChoice(story) {
            const choice = story && typeof story === "object" ? story : null;
            if (!choice || !choice.title) return;
            currentSelectedStory = choice;
            updateStudentEndState({
                stage: "story_ready",
                selected_story: choice.title,
                selected_story_content: choice.content || "",
                story_segment_index: 0,
            });
            currentStorySegmentIndex = 0;
            renderStoryReadyState(choice);
        }

        function updateFooterForStoryState(state) {
            const nextState = String(state || "story_selection");
            shell?.classList.toggle("is-story-selection", nextState === "story_selection");
            shell?.classList.toggle("is-story-ready", nextState !== "story_selection");
            shell?.classList.toggle("is-story-ready-state", nextState === "story_ready");
            shell?.classList.toggle("is-story-reading", nextState === "story_reading");
            shell?.classList.toggle("is-story-comprehension", ["story_comprehension", "story_complete"].includes(nextState));
            if (nextState !== "story_reading") btnStartReading?.classList.remove("is-playing");
            if (nextState === "story_selection") {
                btnStartReading?.classList.add("d-none");
                btnStopReading?.classList.add("d-none");
                btnReadAloud?.classList.add("d-none");
                prevBtn?.classList.add("d-none");
                nextBtn?.classList.add("d-none");
            } else if (nextState === "story_ready") {
                btnStartReading?.classList.remove("d-none");
                if (btnStartReading) btnStartReading.innerHTML = '<i class="bi bi-play-fill"></i> Start Reading →';
                btnStopReading?.classList.add("d-none");
                btnReadAloud?.classList.add("d-none");
                prevBtn?.classList.add("d-none");
                nextBtn?.classList.add("d-none");
            } else if (nextState === "story_reading") {
                btnStartReading?.classList.remove("d-none");
                btnStopReading?.classList.add("d-none");
                btnReadAloud?.classList.remove("d-none");
                prevBtn?.classList.remove("d-none");
                nextBtn?.classList.remove("d-none");
            } else if (nextState === "story_comprehension") {
                btnStartReading?.classList.add("d-none");
                btnStopReading?.classList.add("d-none");
                btnReadAloud?.classList.add("d-none");
                prevBtn?.classList.add("d-none");
                nextBtn?.classList.add("d-none");
            }

            const debugEnabled = speechDebugToggle?.checked || localStorage.getItem("pabasaShowSpeechDebugPanel") === "true";
            setSpeechDebugPanelVisible(debugEnabled, false);
            if (nextState === "story_selection" || nextState === "story_ready") {
                if (readingHelperText) readingHelperText.textContent = "Choose a story to continue.";
            }
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
            const normalizeDisplayItem = (item) => {
                if (item === null || item === undefined) return '';
                if (typeof item === 'object') {
                    return item.text || item.content || item.title || item.sentence || item.paragraph || item.word || '';
                }
                const text = String(item || '').trim();
                if (!text) return '';
                const parts = text.split(/\s*\|\s*/).map(part => part.trim()).filter(Boolean);
                return parts[0] || text;
            };
            const originalItems = Array.isArray(material.items)
                ? material.items.slice()
                : (material.content_json && Array.isArray(material.content_json.items))
                    ? material.content_json.items.slice()
                    : [];
            const normalizedItems = originalItems.map(normalizeDisplayItem).map(item => String(item || '').trim()).filter(Boolean);
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

        function parseOfficialAssessmentItems(data) {
            if (!data || typeof data !== "object") return [];
            const words = Array.isArray(data.words) ? data.words.map(item => String(item || "").trim()).filter(Boolean) : [];
            const sentences = Array.isArray(data.sentences) ? data.sentences.map(item => String(item || "").trim()).filter(Boolean) : [];
            const passages = Array.isArray(data.passages)
                ? data.passages
                    .map(item => {
                        if (!item || typeof item !== "object") return "";
                        const title = String(item.title || "").trim();
                        const content = String(item.content || "").trim();
                        return [title, content].filter(Boolean).join("\n");
                    })
                    .filter(Boolean)
                : [];
            const orderedItems = [...words, ...sentences, ...passages];
            return orderedItems;
        }

        function parsePersistedAssessmentItems(raw) {
            if (!Array.isArray(raw)) return [];
            return raw.map((item) => {
                if (item && typeof item === 'object') {
                    return {
                        text: String(item.text || item.content || '').trim(),
                        type: String(item.type || 'word').trim().toLowerCase() || 'word',
                        title: String(item.title || '').trim(),
                    };
                }
                return { text: String(item || '').trim(), type: 'word', title: '' };
            }).filter((item) => item.text);
        }

        function splitTextIntoDisplayPages(text, itemType = mode) {
            const source = String(text || "").trim();
            if (!source) return [""];
            const normalizedType = String(itemType || "").trim().toLowerCase();
            if (!["paragraph", "para", "story"].includes(normalizedType)) {
                return [source];
            }

            const hardParagraphs = source.split(/\n{2,}/).map(part => part.trim()).filter(Boolean);
            const chunks = hardParagraphs.length > 1 ? hardParagraphs : [source];
            const pages = [];
            const maxCharsPerPage = 260;
            const maxSentencesPerPage = 2;

            const sentenceGroups = (paragraph) => {
                const sentences = paragraph.match(/[^.!?]+[.!?]+|[^.!?]+$/g)?.map(part => part.trim()).filter(Boolean) || [paragraph];
                let buffer = [];
                let bufferLength = 0;
                sentences.forEach((sentence) => {
                    const nextLength = bufferLength ? bufferLength + 1 + sentence.length : sentence.length;
                    if (buffer.length && (buffer.length >= maxSentencesPerPage || nextLength > maxCharsPerPage)) {
                        pages.push(buffer.join(" "));
                        buffer = [sentence];
                        bufferLength = sentence.length;
                    } else {
                        buffer.push(sentence);
                        bufferLength = nextLength;
                    }
                });
                if (buffer.length) {
                    pages.push(buffer.join(" "));
                }
            };

            chunks.forEach((paragraph) => {
                if (paragraph.length > maxCharsPerPage) {
                    sentenceGroups(paragraph);
                } else {
                    pages.push(paragraph);
                }
            });

            return pages.length ? pages : [source];
        }

        function extractItemTitle(itemText, itemType) {
            const normalizedType = String(itemType || mode || "").trim().toLowerCase();
            if (!["paragraph", "para", "story"].includes(normalizedType)) return "";
            const source = String(itemText || "").trim();
            if (!source) return "";
            const parts = source.split(/\n{2,}/).map(part => part.trim()).filter(Boolean);
            return parts.length > 1 ? parts[0] : "";
        }

        function getCurrentItemTitle() {
            return itemTitles[currentIndex] || "";
        }

        function escapeRegExp(value) {
            return String(value || "").replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
        }

        function splitDisplayTextByTitle(displayText, itemTitle) {
            const title = String(itemTitle || "").trim();
            const source = String(displayText || "").trim();
            if (!title || !source) return { titleText: "", bodyText: source };
            const titleRegex = new RegExp(`^${escapeRegExp(title)}([\r\n]{1,2})`);
            if (titleRegex.test(source)) {
                const bodyText = source.replace(titleRegex, "").trim();
                return { titleText: title, bodyText: bodyText };
            }
            return { titleText: "", bodyText: source };
        }

        function buildItemPages(sourceItems, sourceTypes) {
            return sourceItems.map((text, index) => splitTextIntoDisplayPages(text, sourceTypes[index] || mode));
        }

        function syncPhraseSelectionIntoReadingUI(selectedItem = window.__PABASA_SELECTED_READING_ITEM__ || window.__PABASA_SELECTED_PHRASE__ || null, options = {}) {
            const force = Boolean(options.force);
            const targetItem = selectedItem && typeof selectedItem === 'object' ? selectedItem : null;
            if (!targetItem && !force) return false;

            const selectedText = String(targetItem?.text || targetItem?.phrase || targetItem?.content || targetItem?.word || targetItem || "").trim();
            if (!selectedText) return false;

            const selectedIndex = Number.isInteger(targetItem?.sourceIndex) ? targetItem.sourceIndex : 0;
            const phraseId = String(targetItem?.sourceId || targetItem?.id || `phrase-${selectedIndex}`).trim();

            items = [selectedText];
            itemTypes = ['phrase'];
            itemPages = buildItemPages(items, itemTypes);
            itemTitles = [selectedText];
            pageCorrectWordCounts = items.map(() => []);
            correctWordCounts = new Array(items.length).fill(0);
            currentIndex = 0;
            currentPageIndex = 0;
            window.__PABASA_CURRENT_PHRASE_INDEX__ = selectedIndex;
            window.__PABASA_SELECTED_PHRASE__ = targetItem || { text: selectedText, sourceId: phraseId, sourceIndex: selectedIndex };
            window.__PABASA_SELECTED_READING_ITEM__ = window.__PABASA_SELECTED_PHRASE__;

            console.log('Phrase selection synced to reading UI', {
                phraseIndex: selectedIndex,
                phraseId,
                phraseText: selectedText,
                selectedItem,
            });

            updateUI();
            animateCurrentItem();
            return true;
        }

        document.addEventListener('phraseReadingStarted', (event) => {
            const detail = event?.detail || {};
            const selectedItem = detail.phrase || window.__PABASA_SELECTED_READING_ITEM__ || window.__PABASA_SELECTED_PHRASE__ || null;
            if (mode !== 'phrase' && !shell.classList.contains('reader-phrase')) return;
            if (selectedItem) {
                syncPhraseSelectionIntoReadingUI(selectedItem, { force: true });
            }
        });

        function getCurrentItemPages() {
            return itemPages[currentIndex] || [items[currentIndex] || ""];
        }

        function getCurrentDisplayText() {
            return getCurrentItemPages()[Math.min(currentPageIndex, Math.max(0, getCurrentItemPages().length - 1))] || "";
        }

        function isCurrentItemPaged() {
            return getCurrentItemPages().length > 1;
        }

        function getCurrentPageCount() {
            return Math.max(1, getCurrentItemPages().length);
        }

        function getCurrentPageLabel() {
            const totalPages = getCurrentPageCount();
            if (totalPages <= 1) return "";
            return `Page ${currentPageIndex + 1} of ${totalPages}`;
        }

        function goToPreviousPageOrItem() {
            if (isSpeechResponsePending()) return;
            const totalPages = getCurrentPageCount();
            if (currentPageIndex > 0) {
                currentPageIndex -= 1;
                updateUI();
                animateCurrentItem();
                return;
            }
            if (currentIndex > 0) {
                transitionToItem(currentIndex - 1);
            }
        }

        function goToNextPageOrItem() {
            if (isSpeechResponsePending()) return;
            const totalPages = getCurrentPageCount();
            if (currentPageIndex < totalPages - 1) {
                currentPageIndex += 1;
                updateUI();
                animateCurrentItem();
                return;
            }
            if (currentIndex < items.length - 1) {
                transitionToItem(currentIndex + 1, "Next item loaded.", "Keep reading clearly.");
            } else if (!isReviewMode) {
                showCompletion(true);
            }
        }

        function buildCrlaStageUrl(stageName, endState = {}) {
            const url = new URL(window.location.href);
            const normalizedStageName = String(stageName || "").trim().toLowerCase();
            const stagePath = {
                rhymes: "word",
                sentences: "sentence",
                story_selection: "para",
            }[normalizedStageName];
            if (stagePath) {
                url.pathname = url.pathname.replace(
                    /\/reading_ui\/(?:word|sentence|para|vowel)\/?$/i,
                    `/reading_ui/${stagePath}/`
                );
                url.searchParams.set("crla_stage", normalizedStageName);
            }
            const assessmentId = String(
                officialAssessmentId || materialId || endState.material_id || ""
            ).trim();
            if (assessmentId && !url.searchParams.get("official_assessment_id")) {
                url.searchParams.set("official_assessment_id", assessmentId);
            }
            return url.toString();
        }

        function syncItemCorrectWordCount(itemIndex) {
            const counts = pageCorrectWordCounts[itemIndex] || [];
            const total = counts.reduce((sum, count) => sum + Number(count || 0), 0);
            correctWordCounts[itemIndex] = Math.min(total, readableWordCount(items[itemIndex] || ""));
        }

        function syncAllItemCorrectWordCounts() {
            items.forEach((_, index) => syncItemCorrectWordCount(index));
        }

        function renderPersistedEndState(endState) {
            const stage = normalizeStudentEndStatus(endState.stage);
            if (!["transition_to_rhymes", "transition_to_sentence", "transition_to_story", "early_completed_words", "early_completed_sentences", "completed"].includes(stage)) return false;
            shell.classList.add("is-complete");
            const title = document.getElementById("completionTitle");
            const message = document.getElementById("completionMessage");
            const classificationText = endState.classification || "Assessment completed";
            if (completionClassificationValue) completionClassificationValue.textContent = classificationText;
            if (completionClassificationPanel) completionClassificationPanel.hidden = false;
            if (title) title.textContent = stage === "completed" ? "Assessment complete" : "Assessment complete";
            if (message) message.textContent = stage === "transition_to_rhymes"
                ? "You completed Word Reading. You’re ready for Rhymes."
                : stage === "transition_to_sentence"
                    ? "You completed Word Reading. You’re ready for Sentence Reading."
                : stage === "transition_to_story"
                    ? (endState.branch === "rhymes"
                        ? "You completed Rhymes. You’re ready for Story Reading."
                        : "You completed Sentence Reading. You’re ready for Story Reading.")
                    : "You completed the reading assessment.";
            if (finishBtn) {
                finishBtn.dataset.transitionUrl = stage === "transition_to_sentence"
                    ? buildCrlaStageUrl("sentences", endState)
                    : stage === "transition_to_rhymes"
                        ? buildCrlaStageUrl("rhymes", endState)
                    : stage === "transition_to_story"
                        ? buildCrlaStageUrl("story_selection", endState)
                        : "";
                finishBtn.textContent = stage === "transition_to_rhymes" ? "Continue to Rhymes →" : stage === "transition_to_sentence" ? "Continue to Sentence Reading →" : stage === "transition_to_story" ? "Continue to Story Reading →" : "Back to Assessment";
            }
            reviewBtn?.classList.toggle("d-none", !["early_completed_words", "early_completed_sentences", "completed"].includes(stage));
            setCompletionLoadingState(false);
            return true;
        }

        function loadItems() {
            const requestedCrlaStage = normalizeStudentEndStatus(urlParams.get("crla_stage"));
            const persistedEndState = readStudentEndState();
            const persistedStage = normalizeStudentEndStatus(persistedEndState.stage);
            const persistedNextStage = normalizeStudentEndStatus(persistedEndState.next_stage);
            if (isOfficialAssessmentLaunch && officialAssessmentData) {
                const hasExplicitStageRequest = ["rhymes", "sentences", "story_selection"].includes(requestedCrlaStage);
                if (!hasExplicitStageRequest && renderPersistedEndState(persistedEndState)) return;
                const officialTitle = String(
                    officialAssessmentData.official_title
                    || officialAssessmentData.title
                    || testTitle
                    || "Assessment"
                ).trim();
                const officialCode = String(officialAssessmentData.official_code || officialAssessmentData.code || "OFFICIAL").trim();
                const officialLanguage = String(officialAssessmentData.language || liveLanguage || "").trim();
                const officialWords = Array.isArray(officialAssessmentData.words) ? officialAssessmentData.words.map(item => String(item || "").trim()).filter(Boolean) : [];
                const officialSentences = Array.isArray(officialAssessmentData.sentences) ? officialAssessmentData.sentences.map(item => String(item || "").trim()).filter(Boolean) : [];
                const officialPassages = [];
                if (Array.isArray(officialAssessmentData.passages)) {
                    officialAssessmentData.passages.forEach(item => {
                        if (!item || typeof item !== "object") return;
                        const title = String(item.title || "").trim();
                        const content = String(item.content || "").trim();
                        const combined = [title, content].filter(Boolean).join("\n\n");
                        if (!combined) return;
                        officialPassages.push(combined);
                    });
                }
                const stageMap = {
                    words: { items: officialWords, type: "word", label: "Words" },
                    rhymes: { items: officialWords, type: "word", label: "Rhymes" },
                    sentences: { items: officialSentences, type: "sentence", label: "Sentences" },
                    story: { items: [], type: "paragraph", label: "Story Reading" },
                };
                const requestedStage = requestedCrlaStage === "story_selection" ? "story" : requestedCrlaStage;
                let activeStage = "words";
                if (stageMap[requestedStage]) {
                    activeStage = requestedStage;
                } else if (stageMap[persistedNextStage]) {
                    activeStage = persistedNextStage;
                } else if (stageMap[persistedStage]) {
                    activeStage = persistedStage;
                } else if (["story_selection", "story_ready", "story_reading"].includes(persistedStage)) {
                    activeStage = "story";
                } else if (persistedStage.startsWith("completed_")) {
                    activeStage = persistedStage;
                }
                currentAssessmentBranch = activeStage;

                if (stageMap[activeStage]) {
                    items = stageMap[activeStage].items.slice();
                    itemTypes = new Array(items.length).fill(stageMap[activeStage].type);
                } else {
                    items = [];
                    itemTypes = [];
                }
                console.log("PABASA_OFFICIAL_TRACE", {
                    stage: "final_reader_assessment",
                    requested_assessment_type: testTitle,
                    requested_system_assessment_key: testCode,
                    selected_material_id: officialAssessmentData.id || officialAssessmentId || "",
                    selected_material_title: officialTitle,
                    selected_material_system_assessment_key: officialAssessmentData.system_assessment_key || "",
                    selected_material_is_official: true,
                    selected_material_is_system_owned: true,
                    selected_assessment_branch: activeStage,
                    official_assessment_data: officialAssessmentData,
                    final_reader_assessment_title: officialTitle,
                    final_reader_assessment_id: officialAssessmentData.id || officialAssessmentId || "",
                    final_reader_item_count: items.length,
                });
                itemPages = buildItemPages(items, itemTypes);
                itemTitles = items.map((text, index) => extractItemTitle(text, itemTypes[index]));
                pageCorrectWordCounts = items.map(() => []);
                currentMaterialLanguage = officialLanguage || "";
                correctWordCounts = new Array(items.length).fill(0);
                // CRLA Official Assessment: Initialize item locking
                itemLocked = new Array(items.length).fill(false);
                itemScores = new Array(items.length).fill(null);
                currentStoryChoices = getStoryChoicesFromAssessment();
                const persistedStoryTitle = String(persistedEndState.selected_story || "").trim().toLowerCase();
                if (activeStage === "story") {
                    const restoredStory = currentStoryChoices.find(item => String(item.title || "").trim().toLowerCase() === persistedStoryTitle);
                    if (restoredStory) {
                        currentSelectedStory = restoredStory;
                        const persistedSegmentIndex = Number.parseInt(persistedEndState.story_segment_index, 10);
                        currentStorySegmentIndex = Number.isFinite(persistedSegmentIndex) ? Math.max(0, persistedSegmentIndex) : 0;
                        updateStudentEndState({
                            stage: "story_ready",
                            selected_story: restoredStory.title,
                            selected_story_content: restoredStory.content || "",
                            story_segment_index: currentStorySegmentIndex,
                        });
                        renderStoryReadyState(restoredStory);
                    } else {
                        currentSelectedStory = null;
                        renderStorySelection();
                        return;
                    }
                }
                if (items.length === 0 && activeStage.startsWith("completed_")) {
                    shell.classList.add("is-complete");
                    if (readingWord) {
                        readingWord.textContent = persistedEndState.classification || "Assessment completed.";
                    }
                    if (readingTitle) readingTitle.hidden = true;
                    if (completionLevel) completionLevel.textContent = persistedEndState.classification || "Completed";
                    if (counter) counter.textContent = "Assessment completed";
                    if (progressFill) progressFill.style.width = "100%";
                    setCompletionLoadingState(false);
                    return;
                }
                if (items.length === 0) {
                    if (activeStage === "story") {
                        renderStorySelection();
                        return;
                    }
                    if (readingWord) {
                        readingWord.textContent = activeStage.startsWith("completed_")
                            ? (persistedEndState.classification || "Assessment completed.")
                            : "No assessment items assigned.";
                    }
                    if (nextBtn) nextBtn.disabled = true;
                    return;
                }
                if (testMeta) {
                    // keep the top metadata as the assessment header, not the story title,
                    // so the story title only appears once inside the reading card.
                }
                console.log("PABASA_OFFICIAL_TRACE", {
                    stage: "final_reader_render",
                    final_reader_assessment_title: officialTitle,
                    final_reader_assessment_id: officialAssessmentData.id || officialAssessmentId || "",
                    final_reader_assessment_branch: activeStage,
                    final_reader_item_count: items.length,
                });
                if (counter) {
                    counter.textContent = activeStage === "story"
                        ? "Story Reading"
                        : `${stageMap[activeStage]?.label || "Word"} 1/${items.length}`;
                }
                currentIndex = 0;
                resetCurrentPageState();
                updateUI();
                if (activeStage !== "story") {
                    updateStandardAssessmentControls();
                }
                animateCurrentItem();
                return;
            }

            if (!isOfficialAssessmentLaunch) {
                if (customMaterialData || liveContent) {
                    console.log("PABASA_OFFICIAL_TRACE", {
                        stage: "live_content_fallback",
                        live_content_preview: String(liveContent).slice(0, 120),
                        live_item_type: liveItemType,
                        requested_assessment_type: testTitle,
                        requested_system_assessment_key: testCode,
                    });
                    items = customMaterialData
                        ? parseItems(customMaterialData, liveItemType || mode)
                        : parseLiveContent(liveContent, liveItemType || mode);
                    itemTypes = new Array(items.length).fill(String(liveItemType || mode || 'word').toLowerCase());
                    itemPages = buildItemPages(items, itemTypes);
                    pageCorrectWordCounts = items.map(() => []);
                    currentMaterialLanguage = liveLanguage || "";
                    correctWordCounts = new Array(items.length).fill(0);
                    // CRLA Official Assessment: Initialize item locking for live content
                    itemLocked = new Array(items.length).fill(false);
                    itemScores = new Array(items.length).fill(null);
                    // CRLA Official Assessment: Initialize item locking for live content
                    itemLocked = new Array(items.length).fill(false);
                    itemScores = new Array(items.length).fill(null);
                    if (items.length === 0) {
                        if (readingWord) readingWord.textContent = "No assessment items assigned.";
                        if (nextBtn) nextBtn.disabled = true;
                        return;
                    }
                    currentIndex = 0;
                    currentPageIndex = 0;
                    updateUI();
                    updateStandardAssessmentControls();
                    animateCurrentItem();
                    return;
                }
            }

            // Prioritize the canonical Section ID from the URL to prevent mixing materials from other Sections.
            const targetSectionId = sectionId || null;
            let codes = targetSectionId ? [targetSectionId] : getStoredData(studentClassCodesKey, []).map(String);

            const readings = getStoredData(readingsStorageKey, {});
            
            // Section-keyed cache; class_code remains display metadata only.
            const readingsMap = {};
            Object.keys(readings).forEach(key => readingsMap[String(key)] = readings[key]);

            let aggregatedItems = [];
            let aggregatedTypes = [];
            currentMaterialLanguage = "";
            codes.forEach(code => {
                const classReadings = readingsMap[String(code)];
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
                                console.log("PABASA_OFFICIAL_TRACE", {
                                    stage: "legacy_class_readings_match",
                                    requested_assessment_type: testTitle,
                                    requested_system_assessment_key: testCode,
                                    selected_material_id: mId || "",
                                    selected_material_title: material.title || "",
                                    selected_material_system_assessment_key: material.system_assessment_key || "",
                                    selected_material_is_official: Boolean(material.is_official_reading),
                                    selected_material_is_system_owned: Boolean(material.is_system_owned),
                                });
                                const parsedItems = parseItems(material, mode);
                                aggregatedItems = aggregatedItems.concat(parsedItems);
                                aggregatedTypes = aggregatedTypes.concat(new Array(parsedItems.length).fill(String(material.item_type || mode || 'word').toLowerCase()));
                                if (!currentMaterialLanguage && material.language) {
                                    currentMaterialLanguage = material.language;
                                }
                                updateAssessmentLanguageLabel(currentMaterialLanguage);
                            }
                        });
                    }
                });
            });

            items = aggregatedItems;
            itemTypes = aggregatedTypes.length ? aggregatedTypes : new Array(items.length).fill(mode);
            itemPages = buildItemPages(items, itemTypes);
            pageCorrectWordCounts = items.map(() => []);
            correctWordCounts = new Array(items.length).fill(0);
            // CRLA Official Assessment: Initialize item locking for legacy materials
            itemLocked = new Array(items.length).fill(false);
            itemScores = new Array(items.length).fill(null);
            if (items.length === 0) {
                if (readingWord) readingWord.textContent = "No assessment items assigned.";
                if (nextBtn) nextBtn.disabled = true;
                return;
            }
            console.log("PABASA_OFFICIAL_TRACE", {
                stage: "final_reader_assessment",
                requested_assessment_type: testTitle,
                requested_system_assessment_key: testCode,
                final_reader_assessment_title: testTitle,
                final_reader_assessment_id: materialId || "",
                final_reader_item_count: items.length,
            });
            currentIndex = 0;
            currentPageIndex = 0;
            updateUI();
            updateStandardAssessmentControls();
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

        function getCrlaGrade2Part1Level(task1Score, totalScore) {
            const task1 = Number(task1Score);
            const total = Number(totalScore);
            if (!Number.isFinite(task1) || !Number.isFinite(total)) return "";
            if (total <= 10) return "Full Refresher";
            if (total <= 16) return "Moderate Refresher";
            if (total <= 26) return "Light Refresher";
            return "Grade Ready";
        }

        function calculateScores() {
            const targetText = items.join(" ");
            const targetWords = normalizeWords(targetText);
            const spokenWords = normalizeWords(spokenTranscript);
            const durationSeconds = Math.max(1, Math.round(((Date.now() - (startTime || Date.now())) / 1000) * 100) / 100);
            const matchedWords = correctWordsRead();
            const speechRecognitionUsed = spokenWords.length > 0;
            const targetWordCount = targetWords.length;
            const correctItems = items.reduce((total, item, index) => {
                const itemWordCount = readableWordCount(item);
                return total + (itemWordCount > 0 && Number(correctWordCounts[index] || 0) >= itemWordCount ? 1 : 0);
            }, 0);
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
                correct_items: correctItems,
                items_completed: items.length,
                incorrect_words: Math.max(0, targetWordCount - matchedWords),
                skipped_words: 0,
                raw_metrics: {
                    correct_words: matchedWords,
                    correct_items: correctItems,
                    items_completed: items.length,
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
            syncAllItemCorrectWordCounts();
            return correctWordCounts.reduce((sum, count) => sum + Number(count || 0), 0);
        }

        function readableWordCount(text) {
            return normalizeWords(text).length;
        }

        function punctuationHelperForProgress(text, wordsRead) {
            if (!["sentence", "paragraph"].includes(mode) || wordsRead < 1) return "";

            const source = String(text || "");
            const targetWords = Array.from(source.matchAll(/[a-z0-9]+(?:['-][a-z0-9]+)*/gi))
                .filter(match => !/^\d+$/.test(match[0]));
            const completedWord = targetWords[wordsRead - 1];
            if (!completedWord) return "";

            const followingText = source.slice((completedWord.index || 0) + completedWord[0].length);
            const punctuation = followingText.match(/^\s*(\.\.\.|…|[.,;:!?])/);
            if (!punctuation) return "";

            const reminders = {
                ",": "Pause briefly at the comma.",
                ";": "Pause briefly at the semicolon.",
                ":": "Pause briefly at the colon.",
                ".": "Stop briefly at the period.",
                "?": "Pause at the question mark.",
                "!": "Pause at the exclamation mark.",
                "...": "Pause at the ellipsis.",
                "…": "Pause at the ellipsis.",
            };
            return reminders[punctuation[1]] || "";
        }

        function appendPunctuationHelper(detail, wordsRead) {
            const helper = punctuationHelperForProgress(getCurrentDisplayText(), wordsRead);
            return helper ? `${detail} | ${helper}` : detail;
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
            const explicitLevel = scorePayload?.crla_classification || scorePayload?.adapted_reading_level || scorePayload?.classification || scorePayload?.reading_level;
            if (explicitLevel) {
                return helper?.normalizeReadingLevelLabel?.(explicitLevel) || explicitLevel;
            }
            const totalScore = scorePayload?.final_score ?? scorePayload?.total_score ?? scorePayload?.overall_raw_score;
            if (helper?.getClassificationFromScore && totalScore !== undefined && totalScore !== null && totalScore !== "") {
                return helper.getClassificationFromScore(totalScore);
            }
            return fallback;
        }

        function isAralEligibleClassification(classification) {
            const normalized = String(classification || "").trim().toLowerCase();
            return [
                "low emerging readers",
                "high emerging readers",
                "developing readers",
                "transitioning readers",
                "low emerging",
                "high emerging",
                "developing",
                "transitioning",
            ].includes(normalized);
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

        function buildCrlaScoreData(scores) {
            const endState = readStudentEndState() || {};
            const source = { ...endState, ...(scores || {}) };
            const task1ScoreCandidate = source.task1_score ?? source.task1_correct_words
                ?? (currentAssessmentBranch === "words" ? source.correct_words ?? source.word_count : null);
            const task1ScoreNumber = Number(task1ScoreCandidate);
            const task1Score = Number.isInteger(task1ScoreNumber) && task1ScoreNumber >= 0 && task1ScoreNumber <= 10
                ? task1ScoreNumber
                : null;
            const task2Score = source.task2_score
                ?? source.task2_rhymes_score
                ?? source.task2_sentences_score
                ?? null;
            const storyTotalWords = source.total_story_words ?? source.story_total_words ?? null;
            const wordsRead = source.words_read ?? source.total_words_read ?? null;
            const miscues = source.miscues ?? null;
            const passageAccuracy = source.passage_accuracy_percent
                ?? source.story_read_percent
                ?? (storyTotalWords && wordsRead != null ? Math.round((Math.max(0, wordsRead - (miscues || 0)) / storyTotalWords) * 10000) / 100 : null);
            return {
                task1_total_words: 10,
                task1_correct_words: task1Score,
                task1_score: task1Score,
                task2_type: source.task2_type ?? (source.task2_rhymes_score != null ? "Task 2L / Rhymes" : source.task2_sentences_score != null ? "Task 2H / Sentences" : null),
                task2_score: task2Score,
                part1_total_score: source.part1_total_score ?? null,
                story_number: source.story_number ?? currentSelectedStory?.key ?? null,
                story_total_words: storyTotalWords,
                words_read: wordsRead,
                miscues,
                duration_seconds: source.duration_seconds ?? null,
                wpm: source.wpm ?? null,
                comprehension_total: source.comprehension_total ?? source.total_questions ?? null,
                comprehension_correct: source.comprehension_correct ?? source.correct_answers ?? null,
                passage_accuracy_percent: passageAccuracy,
                crla_classification: source.crla_classification ?? source.classification ?? null,
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

        function setCompletionLoadingState(isLoading, { minDurationMs = 500 } = {}) {
            const loadingState = document.getElementById("completionLoadingState");
            const summary = document.getElementById("completionSummary") || document.querySelector(".completion-summary");
            const disclaimer = document.getElementById("completionReadingLevelDisclaimer");

            if (isLoading) {
                clearTimeout(completionLoadingHideTimer);
                completionLoadingStartTime = Date.now();
                if (loadingState) {
                    loadingState.classList.remove("is-hidden");
                    loadingState.setAttribute("aria-busy", "true");
                }
                if (summary) {
                    summary.classList.remove("is-visible");
                    summary.setAttribute("aria-hidden", "true");
                }
                if (disclaimer) {
                    disclaimer.textContent = "Calculating your score breakdown...";
                }
                console.log("PABASA_COMPLETION_TRACE", {
                    stage: "setCompletionLoadingState_enter",
                    isLoading: true,
                    minDurationMs,
                });
                return;
            }

            const finishTransition = () => {
                if (loadingState) {
                    loadingState.classList.add("is-hidden");
                    loadingState.setAttribute("aria-busy", "false");
                }
                if (summary) {
                    summary.classList.add("is-visible");
                    summary.setAttribute("aria-hidden", "false");
                }
            };

            const elapsed = Date.now() - completionLoadingStartTime;
            const remaining = Math.max(0, minDurationMs - elapsed);
            clearTimeout(completionLoadingHideTimer);
            if (remaining > 0) {
                completionLoadingHideTimer = window.setTimeout(finishTransition, remaining);
            } else {
                finishTransition();
            }
            console.log("PABASA_COMPLETION_TRACE", {
                stage: "setCompletionLoadingState_exit",
                isLoading: false,
                minDurationMs,
                elapsed_ms: elapsed,
                remaining_ms: remaining,
            });
        }

        function createCompletionResultRow(label, value, valueClass = "") {
            const row = document.createElement("div");
            row.className = "completion-result-row";

            const labelNode = document.createElement("span");
            labelNode.className = "completion-result-label";
            labelNode.textContent = label;

            const valueNode = document.createElement("strong");
            valueNode.className = `completion-result-value${valueClass ? ` ${valueClass}` : ""}`;
            valueNode.textContent = value ?? "—";

            row.append(labelNode, valueNode);
            return row;
        }

        function buildCompletionSummary(summary, scores, options = {}) {
            if (!summary) return;
            const normalizedScores = normalizeCompletionScores(scores, {});
            summary.querySelectorAll("[data-score-tile]").forEach(tile => tile.remove());
            summary.classList.remove("is-visible");

            const readingTypeLabel = String(options.readingType || mode || "word").charAt(0).toUpperCase() + String(options.readingType || mode || "word").slice(1);
            const wordCount = normalizedScores.word_count != null ? String(Math.round(normalizedScores.word_count)) : "—";
            const accuracyValue = normalizedScores.accuracy != null ? `${Math.round(normalizedScores.accuracy)}%` : "—";
            const durationValue = normalizedScores.duration_seconds != null ? formatDuration(normalizedScores.duration_seconds) : "—";
            const fluencyValue = normalizedScores.fluency_score != null ? `${Math.round(normalizedScores.fluency_score)}%` : "—";
            const pronunciationValue = normalizedScores.pronunciation_score != null ? `${Math.round(normalizedScores.pronunciation_score)}%` : "—";
            const finalScoreValue = normalizedScores.final_score != null ? `${Math.round(normalizedScores.final_score)}%` : normalizedScores.total_score != null ? `${Math.round(normalizedScores.total_score)}%` : "—";
            const classificationValue = options.classification || resolveClassificationLabel(normalizedScores) || "—";

            const columns = [
                {
                    title: "Results overview",
                    rows: [
                        ["Correct words read", wordCount],
                        ["Accuracy", accuracyValue],
                        ["Fluency", fluencyValue],
                        ["Final score", finalScoreValue],
                    ],
                },
                {
                    title: "Reading details",
                    rows: [
                        ["Reading type", readingTypeLabel],
                        ["Reading time", durationValue],
                        ["Pronunciation", pronunciationValue],
                        ["Reading classification", classificationValue],
                    ],
                },
            ];

            columns.forEach(({ title, rows }, index) => {
                const tile = document.createElement("section");
                tile.className = `completion-score-tile completion-score-tile--panel${index === 1 ? " completion-score-tile--status" : ""}`;
                tile.dataset.scoreTile = "true";

                const heading = document.createElement("div");
                heading.className = "completion-score-label";
                heading.textContent = title;

                const grid = document.createElement("div");
                grid.className = "completion-result-grid";
                rows.forEach(([label, value]) => {
                    const valueClass = label === "Reading type" || label === "Reading classification" ? "completion-result-value--soft" : "";
                    grid.appendChild(createCompletionResultRow(label, value, valueClass));
                });

                tile.append(heading, grid);
                summary.appendChild(tile);
            });

            summary.classList.add("is-visible");
        }

        function setCompletionClassification(scores, fallback = "—") {
            const normalizedScores = normalizeCompletionScores(scores, {});
            const classification = resolveClassificationLabel(normalizedScores, fallback) || fallback;
            if (completionClassificationValue) completionClassificationValue.textContent = classification;
            if (completionClassificationPanel) completionClassificationPanel.hidden = false;
            return classification;
        }

        function renderScoreSummary(scores) {
            const disclaimer = document.getElementById("completionReadingLevelDisclaimer");
            const normalizedScores = normalizeCompletionScores(scores, {});
            setCompletionClassification(scores, "—");
            if (disclaimer) {
                disclaimer.textContent = normalizedScores.adapted_reading_level_disclaimer || window.PABASA_READING_LEVEL?.DISCLAIMER || "Great job completing your reading assessment! Keep practicing to improve your reading skills.";
            }
            setCompletionLoadingState(false);
        }

        function renderMyMaterialsCompletion(scores) {
            const disclaimer = document.getElementById("completionReadingLevelDisclaimer");
            const normalizedScores = normalizeCompletionScores(scores, calculateScores());
            const classification = resolveClassificationLabel(normalizedScores, "—") || "—";
            setCompletionClassification(normalizedScores, classification);
            if (disclaimer) {
                const correctWords = Math.max(0, Math.round(Number(normalizedScores.correct_words) || 0));
                const totalWords = Math.max(correctWords, Math.round(Number(normalizedScores.target_word_count) || 0));
                const accuracy = totalWords ? Math.round((correctWords / totalWords) * 100) : 0;
                const feedbackRules = mode === "paragraph"
                    ? [[90, "Excellent reading! Keep it up!"], [75, "Great job! Your reading is getting stronger."], [60, "Good effort! Keep practicing."], [0, "Nice try! Every reading helps you improve."]]
                    : mode === "sentence"
                        ? [[90, "Amazing reading! Keep it up!"], [75, "Great reading! You are doing well."], [50, "Nice try! Keep practicing."], [0, "Keep going! Practice makes progress."]]
                        : [[90, "Excellent! Keep up the great reading!"], [75, "Great job! You are doing well."], [50, "Good try! Keep practicing."], [0, "Keep going! You can do it!"]];
                disclaimer.textContent = feedbackRules.find(([minimum]) => accuracy >= minimum)[1];
            }
            setCompletionLoadingState(false, { minDurationMs: 0 });
        }

        function setSpeechStatus(message, detail = "", listening = false) {
            const panel = document.getElementById("speechPanel");
            const status = document.getElementById("speechStatus");
            const transcriptText = detail || "No words recognized yet. Keep reading clearly.";
            panel?.classList.toggle("is-listening", listening);
            shell?.classList.toggle("is-recording", Boolean(listening && isRecording && !isMuted));
            if (!listening || !isRecording || isMuted) shell?.classList.remove("is-hearing");
            if (status) status.textContent = message;
            if (speechTranscript) speechTranscript.textContent = transcriptText;
            if (readingHelperText) readingHelperText.textContent = transcriptText;
            if (currentStoryState === "story_comprehension" || currentStoryState === "story_complete") {
                syncStoryAnswerText();
            }
            syncPhraseMicrophoneButton();
        }

        function syncPhraseMicrophoneButton() {
            if (!btnStartReading || !shell?.classList.contains("reader-phrase")) return;

            const isProcessing = Boolean(isRecording && (isSendingChunk || pendingAudioChunk));
            const isListening = Boolean(isRecording && !isMuted && recognitionActive && !isProcessing);
            const isStarting = Boolean(isRecording && !isMuted && !recognitionActive && !isProcessing);
            let label = "Start Reading";
            let icon = "bi-mic-fill";

            if (isProcessing) {
                label = "Processing...";
                icon = "bi-hourglass-split";
            } else if (isListening) {
                label = "Listening...";
            } else if (isStarting) {
                label = "Starting microphone...";
            }

            btnStartReading.innerHTML = `<span class="phrase-mic-visual" aria-hidden="true"><i class="bi ${icon}"></i><span class="phrase-audio-wave"><i></i><i></i><i></i></span></span><span class="phrase-mic-label">${label}</span>`;
            btnStartReading.classList.toggle("is-listening", isListening);
            btnStartReading.classList.toggle("is-processing", isProcessing);
            btnStartReading.classList.toggle("is-starting", isStarting);
            btnStartReading.setAttribute("aria-label", label);
            btnStartReading.setAttribute("aria-live", "polite");
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
            mediaRecorder.onstop = async () => {
                const chunks = speechAudioChunks.slice();
                const recorderMimeType = mediaRecorder?.mimeType || mimeType || "audio/webm";
                speechAudioChunks = [];
                mediaRecorder = null;

                if (chunks.length && isRecording && !isMuted && shouldSendAudioChunk() && isCurrentSpeechContext(recorderContext)) {
                    hasHeardSinceLastChunk = false;
                    // Pause microphone capture until this spoken chunk has a final
                    // Cloud response. This prevents overlapping, unscored speech.
                    await sendAudioChunk(new Blob(chunks, { type: recorderMimeType }), recorderContext);
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
            updateSpeechProcessingControls();
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
                        const wasWaitingForSpeechResponse = hasHeardSinceLastChunk;
                        lastHeardAt = now;
                        hasHeardSinceLastChunk = true;
                        if (!wasWaitingForSpeechResponse) {
                            updateAssessmentNavigationButtons();
                            updateSpeechProcessingControls();
                        }
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

        function isSpeechResponsePending() {
            return Boolean(
                !isReviewMode
                && isRecording
                && (hasHeardSinceLastChunk || isSendingChunk || pendingAudioChunk)
            );
        }

        function updateAssessmentNavigationButtons() {
            const speechResponsePending = isSpeechResponsePending();
            const hasPreviousPage = currentPageIndex > 0;
            const hasPreviousItem = currentIndex > 0;
            const isLastPage = currentPageIndex >= getCurrentPageCount() - 1;
            const onLastItem = currentIndex === items.length - 1;
            if (prevBtn) {
                prevBtn.disabled = speechResponsePending || (isReviewMode
                    ? !(hasPreviousPage || hasPreviousItem)
                    : (!isRecording || !(hasPreviousPage || hasPreviousItem)));
            }
            if (nextBtn) {
                nextBtn.disabled = speechResponsePending || (isReviewMode
                    ? (onLastItem && isLastPage)
                    : (!isRecording || (onLastItem && isLastPage)));
            }
        }

        function updateSpeechProcessingControls() {
            const speechResponsePending = isSpeechResponsePending();
            [btnStartReading, btnStopReading, btnReadAloud].forEach((button) => {
                if (!button) return;
                if (speechResponsePending) {
                    // Phrase Reading uses the start button as a listening toggle.
                    // Keep it clickable so the learner can cancel listening without
                    // submitting, advancing, or completing the current phrase.
                    if (button === btnStartReading && shell?.classList.contains("reader-phrase")) {
                        button.disabled = false;
                        delete button.dataset.speechProcessingState;
                        button.removeAttribute("aria-busy");
                        return;
                    }
                    if (!button.dataset.speechProcessingState) {
                        button.dataset.speechProcessingState = button.disabled ? "already-disabled" : "locked";
                    }
                    button.disabled = true;
                    button.setAttribute("aria-busy", "true");
                    return;
                }
                if (button.dataset.speechProcessingState === "locked") {
                    button.disabled = false;
                }
                delete button.dataset.speechProcessingState;
                button.removeAttribute("aria-busy");
            });
            syncPhraseMicrophoneButton();
        }

        function resetSyllableStitching() {
            syllableStitchingContext = "";
            syllableStitchingContextAt = 0;
        }

        function currentSpeechContext() {
            const context = {
                index: currentIndex,
                itemText: getCurrentDisplayText() || items[currentIndex] || "",
                syllableIndex: currentSyllableIndex,
                version: itemResultVersion,
            };
            return context;
        }

        function resetCurrentPageState() {
            currentPageIndex = 0;
            currentSyllableIndex = 0;
            paragraphWordResults = {};
            itemResultVersion += 1;
            resetSyllableStitching();
        }

        function isCurrentSpeechContext(context) {
            const accepted = Boolean(
                context
                && context.index === currentIndex
                && context.itemText === (getCurrentDisplayText() || items[currentIndex])
                && context.syllableIndex === currentSyllableIndex
                && context.version === itemResultVersion
                && !isAdvancingItem
            );
            return accepted;
        }

        function recordParagraphWordResult(wordResults, activeWordIndex) {
            if (mode !== "paragraph" || !Array.isArray(wordResults) || activeWordIndex < 0) return null;
            const activeResult = wordResults.find((result) => {
                const expectedIndex = Number(result?.expected_index ?? -1);
                return Number.isInteger(expectedIndex) && expectedIndex === activeWordIndex;
            });
            const status = String(activeResult?.result || "").trim().toLowerCase();
            if (status !== "correct" && status !== "miscue") return activeResult || null;
            if (paragraphWordResults[activeWordIndex] !== "miscue") {
                paragraphWordResults[activeWordIndex] = status;
            }
            return activeResult;
        }

        function evaluatedParagraphWordIndex(wordSyllableRanges, syllableIndex) {
            if (!Array.isArray(wordSyllableRanges)) return -1;
            const cursor = Number(syllableIndex);
            if (!Number.isFinite(cursor)) return -1;
            return wordSyllableRanges.findIndex((range) => {
                const start = Number(range?.[0]);
                const end = Number(range?.[1]);
                return Number.isFinite(start) && Number.isFinite(end) && start <= cursor && cursor < end;
            });
        }

        async function sendAudioChunk(blob, context = currentSpeechContext()) {
            if (!context.itemText || !isCurrentSpeechContext(context)) return;
            if (isSendingChunk) {
                pendingAudioChunk = { blob, context };
                updateAssessmentNavigationButtons();
                updateSpeechProcessingControls();
                return;
            }
            isSendingChunk = true;
            updateAssessmentNavigationButtons();
            updateSpeechProcessingControls();
            const formData = new FormData();
            formData.append("audio", blob, `reading-${Date.now()}.${audioExtensionForBlob(blob)}`);
            formData.append("target_text", context.itemText);
            formData.append("current_syllable_index", String(context.syllableIndex));
            formData.append("mode", mode);
            formData.append("language", currentMaterialLanguage || "");
            if (
                (
                    String(currentSttLanguageCode || "").toLowerCase() === "fil-ph"
                    || String(currentMaterialLanguage || "").toLowerCase().includes("fil")
                )
                && syllableStitchingContext
                && Date.now() - syllableStitchingContextAt <= syllableStitchingWindowMs
            ) {
                formData.append("syllable_context", syllableStitchingContext);
            } else {
                resetSyllableStitching();
            }
            const requestController = new AbortController();
            // The first Chirp request can include a cold OAuth/channel setup.
            // Allow it to complete instead of cancelling it at the old 15-second cap.
            const requestTimeout = window.setTimeout(() => requestController.abort(), 35000);

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
                    signal: requestController.signal,
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
                console.log("=== CRLA PARAGRAPH RUNTIME ===");
                console.log("currentIndex:", currentIndex);
                console.log("current_word_index:", data.current_word_index);
                console.log("current_word:", data.current_word);
                console.log("matched:", data.matched);
                console.log("next_word:", data.next_word);
                console.log("next_syllable:", data.next_syllable);
                console.log("word_results:", data.word_results);
                console.log("FULL DATA:", data);
                if (!isCurrentSpeechContext(context)) return;
                currentSttLanguageCode = String(data.language_code || currentSttLanguageCode || "");
                if (String(data.language_code || "").toLowerCase() === "fil-ph" && data.syllable_context) {
                    syllableStitchingContext = String(data.syllable_context);
                    syllableStitchingContextAt = Date.now();
                } else {
                    resetSyllableStitching();
                }
                if (data.transcript) {
                    const fallbackNote = data.stt_fallback_reason ? ` | Fallback: ${data.stt_fallback_reason}` : "";
                    const languageNote = data.language_code ? ` | Language: ${data.language_code}` : "";
                    const rawNote = data.raw_transcript && data.raw_transcript !== data.transcript
                        ? ` | Raw: ${data.raw_transcript}`
                        : "";
                    const stitchingNote = data.syllable_stitching_applied
                        ? ` | TASS: ${data.syllable_stitched_transcript}`
                        : (data.syllable_context ? ` | TASS Context: ${data.syllable_context}` : "");
                    const syllableCountNote = Number(data.target_syllable_count || 0) > 0
                        ? ` | Syllables: ${Number(data.syllable_context_count || 0)}/${Number(data.target_syllable_count)}`
                        : "";
                    appendRawMicInput(`Model: ${sttModelLabel(data.stt_model)}${languageNote}${fallbackNote} | Words: ${data.transcript}${rawNote}${stitchingNote}${syllableCountNote}`);
                }
                handleSpeechResult(data, context);
            } catch (error) {
                console.warn("PABASA: Reading transcription failed", error);
                if (isCurrentSpeechContext(context)) {
                    const message = error?.name === "AbortError"
                        ? "Speech processing timed out. Keep reading; the next audio chunk will retry automatically."
                        : (error.message || "Keep reading, then try again.");
                    setSpeechStatus("Speech check had trouble.", message);
                }
            } finally {
                window.clearTimeout(requestTimeout);
                isSendingChunk = false;
                if (pendingAudioChunk && isRecording && !isMuted && isCurrentSpeechContext(pendingAudioChunk.context)) {
                    const nextChunk = pendingAudioChunk.blob;
                    const nextContext = pendingAudioChunk.context;
                    pendingAudioChunk = null;
                    sendAudioChunk(nextChunk, nextContext);
                } else {
                    pendingAudioChunk = null;
                    updateAssessmentNavigationButtons();
                    updateSpeechProcessingControls();
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
            
            // CRLA Official Assessment: Check if item is already locked
            // Official assessments allow only ONE scoring attempt per item
            if (isOfficialAssessmentLaunch && itemLocked[currentIndex]) {
                // Item is locked. Ignore this late/stale response.
                console.log("[CRLA_STRICT_ASSESSMENT] Late response rejected for locked item", {
                    currentIndex,
                    itemLocked: itemLocked[currentIndex],
                    transcript: data.transcript || "",
                });
                return;
            }
            
            const transcript = (data.transcript || "").trim();
            if (transcript) {
                spokenTranscript = [spokenTranscript, transcript].filter(Boolean).join(" ");
            }
            const previousCorrectWords = Number(correctWordCounts[currentIndex] || 0);
            const proposedCorrectWords = Number(data.correct_word_count || data.current_word_index || 0);
            const proposedSyllableIndex = Number(data.current_syllable_index || currentSyllableIndex || 0);
            const activeWordIndex = mode === "paragraph"
                ? evaluatedParagraphWordIndex(data.word_syllable_ranges, context?.syllableIndex)
                : Number(data.current_word_index || 0);
            const activeTargetResult = mode === "paragraph"
                ? recordParagraphWordResult(data.word_results, activeWordIndex)
                : (Array.isArray(data.word_results)
                    ? data.word_results.find((item) => Number(item?.expected_index ?? -1) === activeWordIndex) || null
                    : null);
            const currentTargetMisread = Boolean(
                activeTargetResult
                && String(activeTargetResult.result || "").trim().toLowerCase() === "miscue"
            );
            console.log("[CRLA] ACTIVE TARGET RESULT:", activeTargetResult);
            console.log("[CRLA] MISCUE:", currentTargetMisread);
            console.log("[CRLA] BRANCH:", currentTargetMisread ? "MISCUE_ADVANCE" : "NORMAL");
            console.log("[CRLA_STRICT_ASSESSMENT] Active target evaluation", {
                itemIndex: currentIndex,
                activeWordIndex,
                activeWord: Array.isArray(data.words) && activeWordIndex >= 0 ? data.words[activeWordIndex] : null,
                nextWord: data.next_word || null,
                nextSyllable: data.next_syllable || null,
                matched: Number(data.matched || 0),
                wordResults: Array.isArray(data.word_results) ? data.word_results : [],
                activeTargetResult,
                currentTargetMisread,
                branchTaken: currentTargetMisread ? "MISCUE_ADVANCE" : "NORMAL",
            });
            const hasProgressRegression = proposedSyllableIndex < currentSyllableIndex
                || (proposedSyllableIndex === currentSyllableIndex && proposedCorrectWords < previousCorrectWords);

            if (hasProgressRegression && !data.complete) {
                return;
            }

            const itemCorrectWords = Math.max(
                previousCorrectWords,
                proposedCorrectWords
            );
            const pageCounts = pageCorrectWordCounts[currentIndex] || [];
            pageCounts[currentPageIndex] = Math.min(itemCorrectWords, readableWordCount(getCurrentDisplayText() || items[currentIndex]));
            pageCorrectWordCounts[currentIndex] = pageCounts;
            syncItemCorrectWordCount(currentIndex);
            const speechDetail = appendPunctuationHelper(
                transcript ? `Words: ${transcript}` : "No words recognized yet. Keep reading clearly.",
                correctWordsRead()
            );
            currentSyllableIndex = Math.max(currentSyllableIndex, proposedSyllableIndex);
            if (transcript || Number(data.matched || 0) > 0) {
                renderSyllableDisplay(data, previousCorrectWords);
            }

            if (isCurrentLiveAssessment()) {
                const elapsedSeconds = Math.max(0, Math.round(((Date.now() - (startTime || Date.now())) / 1000) * 100) / 100);
                const completedItems = Math.max(0, currentIndex + (data.complete ? 1 : 0));
                publishLiveSessionState({
                    status: data.complete ? 'completed' : 'reading',
                    items_completed: completedItems,
                    items_total: Math.max(1, items.length),
                    progress: items.length ? Math.min(1, completedItems / items.length) : 0,
                    elapsed_seconds: Math.round(elapsedSeconds),
                    current_item: items[currentIndex] || '',
                    connection_status: 'connected',
                });
            }

            const hasRecognizedSpeech = Boolean(
                transcript
                || Number(data.matched || 0) > 0
                || Number(data.correct_word_count || 0) > 0
                || (Array.isArray(data.word_results) && data.word_results.some((result) => String(result?.result || "").trim().length > 0))
            );

            if (mode === 'phrase' && data.complete && !hasRecognizedSpeech) {
                console.warn("PABASA: Ignoring premature completion with no recognized speech.", {
                    transcript,
                    matched: Number(data.matched || 0),
                    correctWordCount: Number(data.correct_word_count || 0),
                    wordResults: Array.isArray(data.word_results) ? data.word_results : [],
                    currentIndex,
                    itemText: getCurrentDisplayText() || items[currentIndex] || "",
                });
                return;
            }

            if (data.complete) {
                if (mode === 'phrase') {
                    isRecording = false;
                    stopSpeechRecognition();
                    document.dispatchEvent(new CustomEvent('phraseReadingCompleted', {
                        detail: {
                            phraseIndex: window.__PABASA_CURRENT_PHRASE_INDEX__,
                            phraseId: window.__PABASA_SELECTED_READING_ITEM__?.sourceId || window.__PABASA_SELECTED_READING_ITEM__?.id || null,
                            phraseText: window.__PABASA_SELECTED_READING_ITEM__?.text || window.__PABASA_SELECTED_READING_ITEM__?.phrase || getCurrentDisplayText(),
                            transcript,
                            matched: data.matched,
                            current_word_index: data.current_word_index,
                            current_syllable_index: data.current_syllable_index,
                        },
                    }));
                    return;
                }
                // CRLA Official Assessment: Lock this item to prevent further updates
                // EXCEPTION: Story Reading segments are NOT locked; each segment is just a checkpoint in continuous reading
                const isStrictItem = isOfficialAssessmentLaunch && currentStoryState !== "story_reading";
                if (isStrictItem) {
                    itemLocked[currentIndex] = true;
                    itemScores[currentIndex] = {
                        correct_words: correctWordCounts[currentIndex] || 0,
                        transcript: transcript,
                        timestamp: new Date().toISOString(),
                    };
                    console.log("[CRLA_STRICT_ASSESSMENT] Item locked after completion", {
                        itemIndex: currentIndex,
                        result: itemScores[currentIndex],
                    });
                    // Persist immediately to backend and localStorage
                    persistLockedItemResult(currentIndex);
                }
                
                isAdvancingItem = true;
                pendingAudioChunk = null;
                setSpeechStatus("Great job! You finished this item.", transcript ? `Words: ${transcript}` : "", true);
                if (currentStoryState === "story_reading") {
                    traceEndSession('handleSpeechResult.storySegmentComplete', {
                        currentPageIndex,
                        pageCount: getCurrentPageCount(),
                    });
                    window.setTimeout(() => {
                        if (!isRecording || context.version !== itemResultVersion) return;
                        if (currentPageIndex < getCurrentPageCount() - 1) {
                            currentPageIndex += 1;
                            currentStorySegmentIndex = currentPageIndex;
                            updateStudentEndState({ stage: "story_reading", story_segment_index: currentPageIndex });
                            updateUI();
                            renderStoryReadingState(currentSelectedStory);
                            animateCurrentItem();
                        } else {
                            stopReading();
                        }
                    }, 700);
                    return;
                }
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

            const isStrictAssessmentMode = isOfficialAssessmentLaunch && currentStoryState !== "story_reading";

            if ((isStrictAssessmentMode || mode === "paragraph") && !itemLocked[currentIndex] && currentTargetMisread) {
                // Current target miscue must always take precedence over generic matched===0 retry logic.
                // Resolve the current target through the same syllable-based paragraph progression used for
                // successful reads: mark the word as a resolved miscue and advance the cursor to the next word.
                const resolvedWordEnd = Number(
                    (Array.isArray(data.word_syllable_ranges) && data.word_syllable_ranges[activeWordIndex] && data.word_syllable_ranges[activeWordIndex][1]) || 0
                );
                if (resolvedWordEnd > currentSyllableIndex) {
                    currentSyllableIndex = resolvedWordEnd;
                }
                setSpeechStatus("Not quite right.", `Expected: ${data.next_word || "the next word"}. You read: ${transcript}`, false);
                renderSyllableDisplayWithError(data, activeWordIndex, Number(correctWordCounts[currentIndex] || 0));
                console.log("[CRLA_STRICT_ASSESSMENT] Current target miscue resolved; paragraph cursor advanced", {
                    itemIndex: currentIndex,
                    currentWordIndex: activeWordIndex,
                    activeTargetResult,
                    wordResults: Array.isArray(data.word_results) ? data.word_results : [],
                    spokenText: transcript,
                    branchTaken: "MISCUE_ADVANCE",
                    resolvedSyllableIndex: currentSyllableIndex,
                    advanceCalled: true,
                });
                return;
            }

            if (Number(data.matched || 0) > 0) {
                // Clear any pending auto-advance for official assessments
                if (autoAdvanceTimer) {
                    window.clearTimeout(autoAdvanceTimer);
                    autoAdvanceTimer = null;
                }
                setSpeechStatus(
                    `Matched ${correctWordsRead()} word${Number(correctWordsRead()) === 1 ? "" : "s"}.`,
                    `${speechDetail}${data.formatted_syllables ? " | Syllables: " + data.formatted_syllables : ""}`,
                    true
                );
            } else {
                const nextHint = data.next_syllable && data.next_word ? `Try again from: ${data.next_syllable} in ${data.next_word}` : "Keep reading.";
                setSpeechStatus(transcript ? nextHint : "Listening with Google Speech...", speechDetail, true);

                if (isStrictAssessmentMode && !itemLocked[currentIndex] && transcript && Number(data.matched || 0) === 0) {
                    // Preserve original retry behavior for unmatched non-miscue responses.
                    if (autoAdvanceTimer) {
                        window.clearTimeout(autoAdvanceTimer);
                    }
                    setSpeechStatus("Not quite right.", `Expected: ${data.next_word || "the next word"}. You read: ${transcript}`, false);
                    console.log("[CRLA_STRICT_ASSESSMENT] Unmatched response kept in retry branch", {
                        itemIndex: currentIndex,
                        expectedWord: data.next_word,
                        spokenText: transcript,
                        activeWordIndex,
                    });
                    
                    autoAdvanceTimer = window.setTimeout(() => {
                        if (!isRecording || itemLocked[currentIndex]) return;
                        
                        itemLocked[currentIndex] = true;
                        itemScores[currentIndex] = {
                            correct_words: correctWordCounts[currentIndex] || 0,
                            transcript: spokenTranscript,
                            timestamp: new Date().toISOString(),
                            auto_advanced: true,
                            auto_advanced_reason: 'no_match',
                        };
                        persistLockedItemResult(currentIndex);
                        
                        if (currentIndex >= items.length - 1) {
                            isRecording = false;
                            stopSpeechRecognition();
                            showCompletion(true);
                        } else {
                            transitionToItem(currentIndex + 1, "Moving to next item.", "Keep reading clearly.");
                        }
                    }, 1200);
                } else if (currentStoryState === "story_reading" && !isRecording) {
                    // Story Reading: Continue listening for more content without locking
                    setSpeechStatus("I'm still listening", "Keep reading—I'll transcribe as you speak.", true);
                }
            }
        }

        function renderSyllableDisplay(data, previousCorrectWords = 0) {
            if (shell.classList.contains('reader-phrase')) {
                const displayText = String(getCurrentDisplayText() || items[currentIndex] || "").trim();
                renderPhraseWordGuide(displayText, data?.current_word_index);
                return;
            }
            if (!readingWord || !Array.isArray(data.words) || !Array.isArray(data.word_syllable_ranges)) return;
            const displayText = String(getCurrentDisplayText() || items[currentIndex] || "");
            const itemTitle = getCurrentItemTitle();
            const { titleText, bodyText } = splitDisplayTextByTitle(displayText, itemTitle);
            if (readingTitle) {
                readingTitle.hidden = !itemTitle;
                if (itemTitle) {
                    readingTitle.textContent = "";
                }
            }
            readingWord.textContent = "";

            let readableWordIndex = 0;
            let animatedWordCount = 0;
            const shouldAnimate = true;
            const renderTextParts = (text, container) => {
                const parts = String(text || "").split(/(\s+)/);
                parts.forEach((part) => {
                    if (!part) return;
                    if (/^\s+$/.test(part)) {
                        container.appendChild(document.createTextNode(part));
                        return;
                    }

                    if (isDisplayListMarker(part) || !normalizeDisplayWord(part)) {
                        container.appendChild(document.createTextNode(part));
                        return;
                    }

                    const range = data.word_syllable_ranges[readableWordIndex] || [0, 0];
                    const span = document.createElement("span");
                    span.className = "syllable";
                    if (paragraphWordResults[readableWordIndex] === "miscue") {
                        span.classList.add("is-wrong");
                    } else if (range[1] <= currentSyllableIndex) {
                        span.classList.add("is-read");
                        if (shouldAnimate && readableWordIndex >= previousCorrectWords) {
                            span.classList.add("is-new-read");
                            span.style.animationDelay = `${animatedWordCount * 130}ms`;
                            animatedWordCount += 1;
                        }
                    } else if (range[0] <= currentSyllableIndex && currentSyllableIndex < range[1]) {
                        span.classList.add("is-current");
                    }
                    span.textContent = part;
                    container.appendChild(span);
                    readableWordIndex += 1;
                });
            };

            if (itemTitle && readingTitle) {
                readingTitle.textContent = "";
                renderTextParts(titleText, readingTitle);
            }
            renderTextParts(bodyText || displayText, readingWord);
            if (progressFill && typeof data.progress === "number") {
                progressFill.style.width = `${((currentIndex + (data.progress / 100)) / items.length) * 100}%`;
            }
        }

        function renderPhraseWordGuide(displayText, activeWordIndex = 0) {
            if (!readingWord) return;
            const parts = String(displayText || "").split(/(\s+)/);
            let wordIndex = 0;
            const parsedActiveIndex = Number(activeWordIndex);
            const targetIndex = Number.isFinite(parsedActiveIndex) ? Math.max(0, parsedActiveIndex) : 0;
            readingWord.replaceChildren();
            parts.forEach((part) => {
                if (!part) return;
                if (/^\s+$/.test(part)) {
                    readingWord.appendChild(document.createTextNode(part));
                    return;
                }
                const word = document.createElement("span");
                word.className = "phrase-reading-word";
                if (wordIndex === targetIndex) word.classList.add("is-current");
                word.textContent = part;
                readingWord.appendChild(word);
                wordIndex += 1;
            });
            readingWord.hidden = false;
        }

        // CRLA Official Assessment: Render syllables with a specific word highlighted as wrong/error
        function renderSyllableDisplayWithError(data, activeWordIndex = -1, previousCorrectWords = 0) {
            if (shell.classList.contains('reader-phrase')) {
                const displayText = String(getCurrentDisplayText() || items[currentIndex] || "").trim();
                renderPhraseWordGuide(displayText, data?.current_word_index);
                return;
            }
            if (!readingWord || !Array.isArray(data.words) || !Array.isArray(data.word_syllable_ranges)) return;
            const displayText = String(getCurrentDisplayText() || items[currentIndex] || "");
            const itemTitle = getCurrentItemTitle();
            const { titleText, bodyText } = splitDisplayTextByTitle(displayText, itemTitle);
            if (readingTitle) {
                readingTitle.hidden = !itemTitle;
                if (itemTitle) {
                    readingTitle.textContent = "";
                }
            }
            readingWord.textContent = "";

            let readableWordIndex = 0;
            let animatedWordCount = 0;
            const shouldAnimate = true;
            const renderTextParts = (text, container) => {
                const parts = String(text || "").split(/(\s+)/);
                parts.forEach((part) => {
                    if (!part) return;
                    if (/^\s+$/.test(part)) {
                        container.appendChild(document.createTextNode(part));
                        return;
                    }

                    if (isDisplayListMarker(part) || !normalizeDisplayWord(part)) {
                        container.appendChild(document.createTextNode(part));
                        return;
                    }

                    const range = data.word_syllable_ranges[readableWordIndex] || [0, 0];
                    const span = document.createElement("span");
                    span.className = "syllable";
                    
                    // Highlight the specific word index as wrong if it matches
                    if (paragraphWordResults[readableWordIndex] === "miscue") {
                        span.classList.add("is-wrong");
                    } else if (range[1] <= currentSyllableIndex) {
                        span.classList.add("is-read");
                        if (shouldAnimate && readableWordIndex >= previousCorrectWords) {
                            span.classList.add("is-new-read");
                            span.style.animationDelay = `${animatedWordCount * 130}ms`;
                            animatedWordCount += 1;
                        }
                    } else if (range[0] <= currentSyllableIndex && currentSyllableIndex < range[1]) {
                        span.classList.add("is-current");
                    }
                    span.textContent = part;
                    container.appendChild(span);
                    readableWordIndex += 1;
                });
            };

            if (itemTitle && readingTitle) {
                readingTitle.textContent = "";
                renderTextParts(titleText, readingTitle);
            }
            renderTextParts(bodyText || displayText, readingWord);
            if (progressFill && typeof data.progress === "number") {
                progressFill.style.width = `${((currentIndex + (data.progress / 100)) / items.length) * 100}%`;
            }
        }

        function normalizeDisplayWord(word) {
            return String(word || "").toLowerCase().replace(/[^a-z0-9']/g, "");
        }

        function readableWords(text) {
            return String(text || "")
                .split(/\s+/)
                .map((word) => word.trim())
                .filter((word) => word && normalizeDisplayWord(word));
        }

        function getCurrentSectionLabel(type = mode) {
            const normalizedType = String(type || mode || "word").toLowerCase();
            if (normalizedType === "sentence") return "Sentence";
            if (normalizedType === "paragraph" || normalizedType === "para" || normalizedType === "story") return "Story/Paragraph";
            if (normalizedType === "vowel") return "Vowel";
            return "Word";
        }

        function getCurrentHeaderLabel(type = mode) {
            const sectionLabel = getCurrentSectionLabel(type);
            if (sectionLabel === "Sentence") return "Sentence Reading Assessment";
            if (sectionLabel === "Story/Paragraph") return "Story/Paragraph Reading Assessment";
            if (sectionLabel === "Vowel") return "Vowel Reading Assessment";
            return "Word Reading Assessment";
        }

        function updateAssessmentHeaderLabel() {
            if (!isOfficialAssessmentLaunch) return;
            const eyebrow = document.querySelector(".reader-top .eyebrow");
            if (!eyebrow) return;
            if (!eyebrow.dataset.baseText) {
                eyebrow.dataset.baseText = eyebrow.textContent || "";
            }
            eyebrow.textContent = getCurrentHeaderLabel();
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
            setCurrentItemMode(itemTypes[currentIndex] || mode);
            const displayText = getCurrentDisplayText();
            const itemTitle = getCurrentItemTitle();
            const { bodyText } = splitDisplayTextByTitle(displayText, itemTitle);
            if (readingTitle) {
                readingTitle.textContent = itemTitle;
                readingTitle.hidden = !itemTitle;
            }
            if (readingWord) {
                const safeText = (bodyText || displayText || "").trim();
                if (shell.classList.contains('reader-phrase')) {
                    renderPhraseWordGuide(safeText, 0);
                } else {
                    readingWord.textContent = bodyText || displayText;
                }
                readingWord.hidden = false;
            }
            resetSyllableStitching();
            pendingAudioChunk = null;
            isAdvancingItem = false;
            itemResultVersion += 1;
            const label = getCurrentSectionLabel();
            if (counter) {
                const pageLabel = getCurrentPageLabel();
                counter.textContent = pageLabel ? `${label} ${currentIndex + 1}/${items.length} · ${pageLabel}` : `${label} ${currentIndex + 1}/${items.length}`;
            }
            updateAssessmentHeaderLabel();
            if (progressFill && !shell.classList.contains('reader-phrase')) {
                progressFill.style.width = `${((currentIndex + 1) / items.length) * 100}%`;
            }
            
            updateAssessmentNavigationButtons();
            updateSpeechProcessingControls();
            if (nextBtn) {
                const isLastPage = currentPageIndex >= getCurrentPageCount() - 1;
                const onLastItem = currentIndex === items.length - 1;
                if (isReviewMode && onLastItem && isLastPage) {
                    nextBtn.textContent = "Done";
                } else if (isLastPage && getCurrentPageCount() > 1) {
                    nextBtn.textContent = onLastItem ? "Finish Passage" : "Next";
                } else {
                    nextBtn.textContent = "Next";
                }
            }

            if (currentAssessmentUiMode === "standard") {
                btnStartReading?.classList.remove("d-none");
                btnStopReading?.classList.add("d-none");
                btnReadAloud?.classList.remove("d-none");
                btnReadAloud?.classList.remove("is-playing");
                prevBtn?.classList.remove("d-none");
                nextBtn?.classList.remove("d-none");
            }

            if (btnStartReading && shell.classList.contains('reader-phrase')) {
                syncPhraseMicrophoneButton();
            } else if (btnStartReading) {
                const isActiveReading = isRecording && (
                    currentAssessmentUiMode === "standard"
                    || currentAssessmentUiMode === "story"
                );
                btnStartReading.innerHTML = isActiveReading
                    ? '<i class="bi bi-stop-fill"></i> Finish Reading'
                    : '<i class="bi bi-play-fill"></i> Start Reading';
                btnStartReading.classList.toggle("is-playing", isActiveReading);
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
            // CRLA Official Assessment: Clear auto-advance timer when transitioning
            if (autoAdvanceTimer) {
                window.clearTimeout(autoAdvanceTimer);
                autoAdvanceTimer = null;
            }
            currentIndex = nextIndex;
            currentPageIndex = 0;
            currentSyllableIndex = 0;
            paragraphWordResults = {};
            setCurrentItemMode(itemTypes[currentIndex] || mode);
            updateUI();
            animateCurrentItem();
            if (isCurrentLiveAssessment()) {
                const elapsedSeconds = Math.max(0, Math.round(((Date.now() - (startTime || Date.now())) / 1000) * 100) / 100);
                publishLiveSessionState({
                    status: 'reading',
                    items_completed: Math.max(0, currentIndex),
                    items_total: Math.max(1, items.length),
                    progress: items.length ? Math.min(1, currentIndex / items.length) : 0,
                    elapsed_seconds: Math.round(elapsedSeconds),
                    current_item: items[currentIndex] || '',
                    connection_status: 'connected',
                });
            }
            if (statusMessage) {
                setSpeechStatus(statusMessage, detail, Boolean(isRecording && !isMuted));
            }
            // A correct response pauses capture while it is processed. Once the
            // next item is visible, resume a fresh recorder for that new context.
            if (isRecording && !isMuted && !mediaRecorder && !stoppingSpeechRecognition) {
                startSpeechChunkRecorder();
            }
            updateAssessmentNavigationButtons();
            updateSpeechProcessingControls();
        }

        function showCompletion(isFullCompletion) {
            traceEndSession('showCompletion.enter', {
                isFullCompletion,
                completionSubmitted,
                isReviewMode,
                materialId,
                officialAssessmentId,
                resolvedAssessmentCode: testCode,
            });
            stopReadAloud();
            stopSpeechRecognition();
            shell.classList.add("is-complete");
            closePauseMenu();
            if (completionCount) completionCount.textContent = correctWordsRead();
            const completionSnapshot = calculateScores();
            latestScores = normalizeCompletionScores(latestScores || completionSnapshot, completionSnapshot);
            const isSentenceBranch = ["sentences_low", "sentences_high", "sentences"].includes(currentAssessmentBranch);
            const branchScore = Number(isSentenceBranch
                ? (latestScores.correct_sentences ?? latestScores.sentence_count ?? latestScores.correct_items ?? 0)
                : (latestScores.correct_words ?? latestScores.word_count ?? latestScores.correct_items ?? 0));
            const previousEndState = readStudentEndState();
            const branchState = {
                version: studentEndStateVersion,
                stage: currentAssessmentBranch,
                branch: currentAssessmentBranch,
                score: branchScore,
                classification: "",
                next_stage: "",
            };
            if (currentAssessmentBranch === "words") {
                branchState.stage = branchScore <= 6 ? "transition_to_rhymes" : "transition_to_sentence";
                branchState.next_stage = branchScore <= 6 ? "rhymes" : "sentences";
                branchState.correct_words = branchScore;
                branchState.classification = branchScore <= 6 ? "Low Emerging Reader" : "";
                branchState.branch = "rhymes";
                branchState.task1_score = branchScore;
                branchState.task2_rhymes_score = null;
                branchState.task2_sentences_score = null;
                branchState.part1_total_score = null;
                branchState.part1_reading_level = "";
            } else if (currentAssessmentBranch === "rhymes") {
                const correctWords = Number(previousEndState.correct_words ?? previousEndState.task1_score ?? 0);
                const part1Total = correctWords + branchScore;
                branchState.correct_words = correctWords;
                branchState.correct_sentences = null;
                branchState.routing_score = part1Total;
                branchState.score = part1Total;
                branchState.cumulative_correct = part1Total;
                branchState.branch = "rhymes";
                branchState.task1_score = correctWords;
                branchState.task2_rhymes_score = branchScore;
                branchState.task2_sentences_score = null;
                branchState.part1_total_score = part1Total;
                branchState.part1_reading_level = getCrlaGrade2Part1Level(correctWords, part1Total);
                if (part1Total <= 10) {
                    branchState.stage = "early_completed_words";
                    branchState.next_stage = "completed";
                    branchState.classification = "Low Emerging Reader";
                } else {
                    branchState.stage = "transition_to_story";
                    branchState.next_stage = "story_selection";
                    branchState.classification = "";
                }
            } else if (currentAssessmentBranch === "sentences_low" || currentAssessmentBranch === "sentences_high" || currentAssessmentBranch === "sentences") {
                const correctWords = Number(previousEndState.correct_words ?? 0);
                const cumulativeCorrect = correctWords + branchScore;
                const part1Total = cumulativeCorrect;
                branchState.stage = part1Total <= 10 ? "early_completed_sentences" : "transition_to_story";
                branchState.next_stage = part1Total <= 10 ? "completed" : "story_selection";
                branchState.correct_words = correctWords;
                branchState.correct_sentences = branchScore;
                branchState.sentence_items_administered = items.length;
                branchState.cumulative_correct = cumulativeCorrect;
                branchState.routing_score = part1Total;
                branchState.score = part1Total;
                branchState.classification = part1Total <= 10 ? "High Emerging Reader" : "";
                branchState.branch = "sentences";
                branchState.task1_score = correctWords;
                branchState.task2_rhymes_score = null;
                branchState.task2_sentences_score = branchScore;
                branchState.part1_total_score = part1Total;
                branchState.part1_reading_level = part1Total <= 10
                    ? "Full Refresher"
                    : part1Total <= 16
                        ? "Moderate Refresher"
                        : part1Total <= 26
                            ? "Light Refresher"
                            : "Grade Ready";
            } else if (currentAssessmentBranch === "story") {
                const preservedTask1Score = Number(previousEndState.task1_score ?? previousEndState.task1_correct_words);
                const preservedTask2Score = Number(previousEndState.task2_score
                    ?? previousEndState.task2_rhymes_score
                    ?? previousEndState.task2_sentences_score);
                const preservedTask1IsValid = Number.isInteger(preservedTask1Score)
                    && preservedTask1Score >= 0 && preservedTask1Score <= 10;
                const preservedTask2IsValid = Number.isInteger(preservedTask2Score)
                    && preservedTask2Score >= 0 && preservedTask2Score <= 10;
                const storyRead = Number(
                    latestScores.story_read_percent ??
                    latestScores.story_percent ??
                    latestScores.read_percent ??
                    latestScores.progress_percent ??
                    (Number.isFinite(Number(latestScores.progress)) ? Number(latestScores.progress) * 100 : null) ??
                    (items.length ? (Number(latestScores.items_completed ?? 0) / Math.max(1, items.length)) * 100 : null) ??
                    0
                );
                const correctAnswers = Number(
                    latestScores.correct_answers ??
                    latestScores.comprehension_correct ??
                    latestScores.correct_items ??
                    latestScores.items_correct ??
                    0
                );
                branchState.classification = getStoryClassificationFromResult(storyRead, correctAnswers);
                latestScores.crla_classification = branchState.classification;
                latestScores.classification = branchState.classification;
                branchState.stage = "completed";
                branchState.next_stage = "completed";
                branchState.task1_score = preservedTask1IsValid ? preservedTask1Score : null;
                branchState.task1_correct_words = preservedTask1IsValid ? preservedTask1Score : null;
                branchState.task2_type = previousEndState.task2_type
                    || (previousEndState.task2_rhymes_score != null ? "Task 2L / Rhymes" : "Task 2H / Sentences");
                branchState.task2_score = preservedTask2IsValid ? preservedTask2Score : null;
                branchState.task2_rhymes_score = previousEndState.task2_rhymes_score ?? null;
                branchState.task2_sentences_score = previousEndState.task2_sentences_score ?? null;
                branchState.part1_total_score = previousEndState.part1_total_score ?? null;
                branchState.story_read_percent = Number.isFinite(storyRead) ? storyRead : null;
                branchState.story_total_words = latestScores.total_story_words ?? null;
                branchState.total_story_words = latestScores.total_story_words ?? null;
                branchState.words_read = latestScores.words_read ?? null;
                branchState.total_words_read = latestScores.words_read ?? null;
                branchState.miscues = latestScores.miscues ?? null;
                branchState.duration_seconds = latestScores.duration_seconds ?? null;
                branchState.wpm = latestScores.wpm ?? null;
                branchState.correct_answers = Number.isFinite(correctAnswers) ? correctAnswers : null;
                branchState.comprehension_correct = Number.isFinite(correctAnswers) ? correctAnswers : null;
                branchState.comprehension_total = latestScores.total_questions ?? currentStoryQuestions.length;
                branchState.total_questions = latestScores.total_questions ?? currentStoryQuestions.length;
            }
            if (!isMyMaterials && branchState.stage) {
                writeStudentEndState(branchState);
            }
            const nextStageUrlMap = {
                rhymes: buildCrlaStageUrl("rhymes", branchState),
                sentences: buildCrlaStageUrl("sentences", branchState),
                story_selection: buildCrlaStageUrl("story_selection", branchState),
            };
            const nextStageUrl = nextStageUrlMap[branchState.next_stage] || "";
            const summary = document.getElementById("completionSummary") || document.querySelector(".completion-summary");
            const disclaimer = document.getElementById("completionReadingLevelDisclaimer");
            if (summary) {
                summary.querySelectorAll("[data-score-tile]").forEach(tile => tile.remove());
                summary.classList.remove("is-visible");
            }
            setCompletionLoadingState(!isMyMaterials && !isReviewMode && isFullCompletion && !completionSubmitted);
            if (!isMyMaterials && disclaimer && (!isReviewMode && isFullCompletion && !completionSubmitted)) {
                disclaimer.textContent = "Calculating your score breakdown...";
            }
            if (!isMyMaterials && completionLevel) {
                if (currentAssessmentBranch === "words") {
                    completionLevel.textContent = branchState.next_stage === "rhymes"
                        ? "Rhymes"
                        : "Sentence Reading";
                } else {
                    completionLevel.textContent = resolveClassificationLabel(latestScores, mode.charAt(0).toUpperCase() + mode.slice(1));
                }
            }
            
            // Add retake attempt information to the results title
            if (isRetakeMode && materialId) {
                const retakeCounts = JSON.parse(localStorage.getItem('pabasa_retake_counts') || '{}');
                const count = retakeCounts[String(materialId).trim()] || 0;
                const title = document.querySelector(".completion-card h1");
                if (title) title.innerHTML += ` <span style="background: var(--sun); color: #1b1a17; padding: 4px 12px; border-radius: 10px; font-size: 0.4em; vertical-align: middle; margin-left: 10px; font-weight: 900;">RETAKE ${count + 1}/3</span>`;
            }

            // Skip side effects for review mode or partial progress
            if (isReviewMode || !isFullCompletion || completionSubmitted) {
                traceEndSession('showCompletion.skipSideEffects', {
                    isReviewMode,
                    isFullCompletion,
                    completionSubmitted,
                });
                return;
            }
            if (isMyMaterials) {
                renderMyMaterialsCompletion(latestScores);
            } else {
                renderScoreSummary(latestScores);
                renderPersistedEndState(branchState);
            }
            if (!isMyMaterials && (branchState.stage === "transition_to_rhymes" || branchState.stage === "transition_to_sentence" || branchState.stage === "transition_to_story")) {
                traceEndSession('showCompletion.awaitContinue', { nextStageUrl, next_stage: branchState.next_stage });
                return;
            }
            completionSubmitted = true;
            traceEndSession('showCompletion.sideEffectsStart');

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
                    const readings = JSON.parse(localStorage.getItem('pabasa_section_readings') || '{}');
                    const normalizedId = materialId ? String(materialId).trim() : null;
                    const normalizedTitle = testTitle || null;
                    const currentSeenIds = JSON.parse(localStorage.getItem('pabasa_seen_material_ids') || '[]').map(id => String(id).trim());
                    const seenSet = new Set(currentSeenIds);

                    Object.keys(readings).forEach(function (sectionKey) {
                        const classMaterials = readings[sectionKey] || {};
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
            const metadata = JSON.parse(localStorage.getItem('pabasa_section_metadata') || '{}');
            const classInfo = metadata[String(sectionId)] || {};
            const className = classInfo.name || 'your class';
            const notifications = JSON.parse(localStorage.getItem('pabasa_notifications') || '[]');
            notifications.unshift({
                id: Date.now() + Math.random(),
                sectionId: sectionId || null,
                title: 'Student Completed an Assessment',
                message: `• ${studentName} completed the assessment "${testTitle}" in ${className}.`,
                timestamp: Date.now(),
                read: false,
                role: 'admin',
                recipientEmail: null,
            });
            localStorage.setItem('pabasa_notifications', JSON.stringify(notifications.slice(0, 100)));
            window.dispatchEvent(new Event('pabasa:notifications-updated'));

            const token = getCsrfToken();
            console.log("PABASA_COMPLETION_TRACE", {
                stage: "showCompletion.pre_submit_gate",
                materialId,
                officialAssessmentId,
                has_token: Boolean(token),
                token_length: token ? String(token).length : 0,
                completionSubmitted,
                isFullCompletion,
                isReviewMode,
            });
            if (materialId && token) {
                setCompletionActionButtonsProcessing(true);
                const elapsedSeconds = Math.max(1, Math.round(((Date.now() - (startTime || Date.now())) / 1000) * 100) / 100);
                const completionSnapshot = calculateScores();
                latestScores = normalizeCompletionScores(latestScores || completionSnapshot, completionSnapshot);
                const completionMetrics = normalizeCompletionScores(completionSnapshot || {}, {});
                const crlaScoreData = buildCrlaScoreData(latestScores);
                const payload = {
                    material_id: materialId,
                    activity_type: 'assessment',
                    section_id: sectionId || null,
                    assessment_type: mode,
                    official_assessment_id: officialAssessmentId || "",
                    official_assessment_data: officialAssessmentData || null,
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
                    part1_total_score: crlaScoreData.part1_total_score,
                    crla_score_data: crlaScoreData,
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
                        part1_total_score: crlaScoreData.part1_total_score,
                        crla_score_data: crlaScoreData,
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
                console.log("PABASA_COMPLETION_TRACE", {
                    stage: "record_completion_request_preflight",
                    request_url: "/record-assessment-completion/",
                    payload_keys: Object.keys(payload),
                    payload,
                    materialId,
                    official_assessment_id: officialAssessmentId || "",
                    official_assessment_code: testCode || "",
                    assessment_type: mode,
                });

                if (isCurrentLiveAssessment()) {
                    const completionElapsedSeconds = Math.max(0, Math.round(((Date.now() - (startTime || Date.now())) / 1000) * 100) / 100);
                    const finalScore = completionSnapshot?.final_score ?? completionSnapshot?.total_score ?? latestScores?.final_score ?? latestScores?.total_score ?? null;
                    traceEndSession('showCompletion.publishCompletedBeforeRecord', {
                        finalScore,
                        payload,
                    });
                    publishLiveSessionState({
                        status: 'completed',
                        items_completed: Math.max(1, items.length),
                        items_total: Math.max(1, items.length),
                        progress: 1,
                        elapsed_seconds: Math.round(completionElapsedSeconds),
                        current_item: items[currentIndex] || '',
                        final_score: finalScore != null ? Number(finalScore) : null,
                        connection_status: 'connected',
                        completion_payload: payload,
                    });
                }

                traceEndSession('showCompletion.recordAssessmentCompletion.request', { payload });
                console.log("PABASA_COMPLETION_TRACE", {
                    stage: "record_completion_fetch_before",
                    request_url: "/record-assessment-completion/",
                    payload,
                });
                clearTimeout(completionResultsFallbackTimer);
                completionResultsFallbackTimer = window.setTimeout(() => {
                    traceEndSession('showCompletion.recordAssessmentCompletion.timeoutFallback', {
                        request_url: "/record-assessment-completion/",
                    });
                    setCompletionActionButtonsProcessing(false);
                    setCompletionLoadingState(false);
                }, 10000);
                completionSavePromise = fetch('/record-assessment-completion/', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json', 'X-CSRFToken': token },
                    credentials: 'same-origin',
                    body: JSON.stringify(payload)
                }).then(async r => {
                    traceEndSession('showCompletion.recordAssessmentCompletion.responseStatus', { ok: r.ok, status: r.status });
                    const d = await r.json().catch(() => ({}));
                    traceEndSession('showCompletion.recordAssessmentCompletion.responseBody', {
                        success: d.success,
                        error: d.error,
                        response: d,
                    });
                    console.log("PABASA_COMPLETION_TRACE", {
                        stage: "record_completion_response",
                        response_ok: r.ok,
                        response_status: r.status,
                        response_keys: Object.keys(d || {}),
                        response_json: d,
                    });
                    console.log("PABASA_COMPLETION_TRACE", {
                        stage: "record_completion_success_callback",
                        response_keys: Object.keys(d || {}),
                    });
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
                        if (!isMyMaterials && completionLevel) {
                            const classificationText = backendScores.crla_classification || backendScores.classification || backendScores.adapted_reading_level || backendScores.reading_level || resolveClassificationLabel(backendScores, mode.charAt(0).toUpperCase() + mode.slice(1));
                            completionLevel.textContent = classificationText || mode.charAt(0).toUpperCase() + mode.slice(1);
                        }
                        if (isMyMaterials) {
                            renderMyMaterialsCompletion(latestScores);
                        } else {
                            renderScoreSummary(latestScores);
                            renderPersistedEndState(readStudentEndState());
                        }
                        const disclaimer = document.getElementById("completionReadingLevelDisclaimer");
                        if (!isMyMaterials && disclaimer) {
                            disclaimer.textContent = latestScores.adapted_reading_level_disclaimer || window.PABASA_READING_LEVEL?.DISCLAIMER || "Great job completing your reading assessment! Your results show your current reading performance. Keep practicing to improve your reading skills.";
                        }
                        if (isCurrentLiveAssessment()) {
                            const completedScore = backendScores?.final_score ?? backendScores?.total_score ?? null;
                            const liveScoreUpdate = {
                                status: 'completed',
                                items_completed: Math.max(1, items.length),
                                items_total: Math.max(1, items.length),
                                progress: 1,
                                elapsed_seconds: Math.round(elapsedSeconds),
                                current_item: items[currentIndex] || '',
                                connection_status: 'connected',
                            };
                            if (completedScore != null) {
                                liveScoreUpdate.final_score = Number(completedScore);
                            }
                            traceEndSession('showCompletion.publishCompletedAfterRecord', { liveScoreUpdate });
                            publishLiveSessionState(liveScoreUpdate);
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
                    if (!isAssistMode && d.next_url) {
                        window.location.assign(d.next_url);
                    }
                    return d;
                }).catch(e => {
                    traceEndSession('showCompletion.recordAssessmentCompletion.error', { message: String(e.message || e) });
                    console.error("PABASA: Completion error", e);
                }).finally(() => {
                    clearTimeout(completionResultsFallbackTimer);
                    completionResultsFallbackTimer = null;
                    traceEndSession('showCompletion.recordAssessmentCompletion.finally');
                    setCompletionActionButtonsProcessing(false);
                    setCompletionLoadingState(false);
                });
            } else {
                console.log("PABASA_COMPLETION_TRACE", {
                    stage: "showCompletion.submit_skipped",
                    materialId,
                    has_token: Boolean(token),
                });
                setCompletionLoadingState(false);
            }
        }

        function startAssessmentTimer() {
            if (!startTime || startTime === null) {
                startTime = Date.now();
            }
            if (isCurrentLiveAssessment()) {
                publishLiveSessionState({
                    status: 'reading',
                    items_completed: 0,
                    items_total: Math.max(1, items.length),
                    progress: 0,
                    elapsed_seconds: 0,
                    current_item: items[currentIndex] || '',
                    connection_status: 'connected',
                });
                startLiveSessionHeartbeat();
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
            liveCountdownOverlay.style.display = '';
            liveCountdownOverlay.setAttribute('aria-hidden', 'false');
        }

        function hideLiveCountdown() {
            if (!liveCountdownOverlay) return;
            liveCountdownOverlay.classList.add('d-none');
            liveCountdownOverlay.style.display = 'none';
            liveCountdownOverlay.setAttribute('aria-hidden', 'true');
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
                traceEndSession('fetchLiveSessionState.request');
                const response = await fetch(liveSessionStateUrl, {
                    cache: 'no-store',
                    credentials: 'same-origin',
                    headers: { Accept: 'application/json' },
                });
                traceEndSession('fetchLiveSessionState.responseStatus', { ok: response.ok, status: response.status });
                if (!response.ok) return null;
                const payload = await response.json();
                traceEndSession('fetchLiveSessionState.responseBody', {
                    success: payload.success,
                    error: payload.error,
                    responseStatus: payload.session?.status,
                    responseStudentStates: payload.session?.student_states || {},
                });
                return payload.success ? payload.session : null;
            } catch (error) {
                traceEndSession('fetchLiveSessionState.error', { message: String(error.message || error) });
                console.warn('PABASA: Live session state fetch failed', error);
                return null;
            }
        }

        async function publishLiveSessionState(updateValues = {}) {
            if (!liveSessionId || !isCurrentLiveAssessment()) return null;
            if (!Object.keys(updateValues).length) return null;
            try {
                traceEndSession('publishLiveSessionState.enter', { updateValues });
                const completionSnapshot = calculateScores();
                const completionMetrics = normalizeCompletionScores(completionSnapshot || {}, {});
                const elapsedSeconds = Number.isFinite(Number(updateValues.elapsed_seconds))
                    ? Number(updateValues.elapsed_seconds)
                    : Math.max(0, Math.round(((Date.now() - (startTime || Date.now())) / 1000) * 100) / 100);
                const completionPayload = {
                    assessment_type: mode,
                    material_id: materialId,
                    activity_type: 'assessment',
                    section_id: sectionId || null,
                    correct_words: completionMetrics.correct_words ?? completionMetrics.word_count ?? 0,
                    incorrect_words: completionMetrics.incorrect_words ?? 0,
                    skipped_words: completionMetrics.skipped_words ?? 0,
                    duration_seconds: completionMetrics.duration_seconds ?? elapsedSeconds,
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
                        duration_seconds: completionMetrics.duration_seconds ?? elapsedSeconds,
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
                        duration_seconds: completionMetrics.duration_seconds ?? elapsedSeconds,
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
                if (isRetakeMode && materialId) {
                    const retakeCounts = JSON.parse(localStorage.getItem('pabasa_retake_counts') || '{}');
                    completionPayload.attempt_number = retakeCounts[String(materialId).trim()] || 1;
                }
                if (assistToken) completionPayload.assist_token = assistToken;
                traceEndSession('publishLiveSessionState.request', {
                    updateValues,
                    completionPayload,
                });
                const response = await fetch(`/api/live-assessment/session/${liveSessionId}/student-update/`, {
                    method: 'POST',
                    credentials: 'same-origin',
                    headers: {
                        'Content-Type': 'application/json',
                        'Accept': 'application/json',
                        'X-CSRFToken': getCsrfToken(),
                    },
                    body: JSON.stringify({
                        ...updateValues,
                        completion_payload: completionPayload,
                    }),
                });
                traceEndSession('publishLiveSessionState.responseStatus', { ok: response.ok, status: response.status });
                if (!response.ok) return null;
                const payload = await response.json();
                traceEndSession('publishLiveSessionState.responseBody', {
                    success: payload.success,
                    error: payload.error,
                    responseStatus: payload.session?.status,
                    responseStudentStates: payload.session?.student_states || {},
                });
                return payload.success ? payload.session : null;
            } catch (error) {
                traceEndSession('publishLiveSessionState.error', { message: String(error.message || error) });
                console.warn('PABASA: Live session state update failed', error);
                return null;
            }
        }

        function stopLiveSessionHeartbeat() {
            if (liveSessionHeartbeatTimer) {
                window.clearInterval(liveSessionHeartbeatTimer);
                liveSessionHeartbeatTimer = null;
            }
        }

        function startLiveSessionHeartbeat() {
            if (!liveSessionId || !isCurrentLiveAssessment()) return;
            stopLiveSessionHeartbeat();
            liveSessionLastHeartbeatAt = Date.now();
            liveSessionHeartbeatTimer = window.setInterval(() => {
                if (!isRecording || liveSessionPaused || liveSessionEnded) return;
                const now = Date.now();
                if (now - liveSessionLastHeartbeatAt < 1000) return;
                liveSessionLastHeartbeatAt = now;
                const elapsedSeconds = Math.max(0, Math.round(((now - (startTime || now)) / 1000) * 100) / 100);
                publishLiveSessionState({
                    status: 'reading',
                    elapsed_seconds: Math.round(elapsedSeconds),
                    items_completed: correctWordsRead() > 0 ? Math.max(0, currentIndex) : Math.max(0, currentIndex),
                    items_total: Math.max(1, items.length),
                    progress: items.length ? Math.min(1, (currentIndex + 1) / items.length) : 0,
                    current_item: items[currentIndex] || '',
                    connection_status: 'connected',
                });
            }, 2000);
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
            if (liveCountdownTimer && !liveCountdownStarted) {
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
            traceEndSession('showLiveSessionEnded.enter');
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
            if (liveCountdownTimer && !liveCountdownStarted) {
                clearLiveCountdown();
                hideLiveCountdown();
            }
            setSpeechStatus('Live session ended.', 'Your teacher has ended the assessment.', false);
        }

        function hasActiveReadingAttempt() {
            return Boolean(
                isRecording || recognitionActive || currentIndex > 0 || (spokenTranscript || '').trim() ||
                correctWordCounts.some((count) => count > 0) ||
                (latestScores && (latestScores.word_count != null || latestScores.accuracy != null || latestScores.final_score != null))
            );
        }

        async function handleLiveSessionState(state) {
            if (!state || !state.status) return;
            traceEndSession('handleLiveSessionState.enter', {
                responseStatus: state.status,
                responseStudentStates: state.student_states || {},
            });
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
            if (state.status === 'ended' || state.status === 'completed') {
                if (!liveSessionEnded) {
                    liveSessionEnded = true;
                    traceEndSession('handleLiveSessionState.endedFirstSeen', {
                        hasActiveReadingAttempt: hasActiveReadingAttempt(),
                    });
                    if (hasActiveReadingAttempt()) {
                        showCompletion(true);
                    } else {
                        showLiveSessionEnded();
                    }
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
            let countdownDuration = Number.parseInt(urlParams.get('countdown') || '10', 10);
            const sessionState = await fetchLiveSessionState();
            const serverStartCountdownSeconds = Number(sessionState?.start_countdown_seconds);
            const serverConfiguredCountdownSeconds = Number(sessionState?.countdown_seconds);
            if (Number.isFinite(serverStartCountdownSeconds) && serverStartCountdownSeconds >= 0) {
                countdownDuration = Math.max(0, serverStartCountdownSeconds);
            } else if (Number.isFinite(serverConfiguredCountdownSeconds) && serverConfiguredCountdownSeconds >= 0) {
                countdownDuration = Math.max(0, serverConfiguredCountdownSeconds);
            }
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
                showLiveCountdown();
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

        const resetPhraseListening = () => {
            if (mode !== "phrase" || !isRecording) return false;

            // Invalidate a transcription response that may already be in flight.
            // It must not score or complete the phrase after listening is cancelled.
            itemResultVersion += 1;
            isRecording = false;
            isAdvancingItem = false;
            pendingAudioChunk = null;
            hasHeardSinceLastChunk = false;
            stopSpeechRecognition();
            btnStartReading?.classList.remove("d-none", "is-listening", "is-processing", "is-starting");
            btnStopReading?.classList.add("d-none");
            setSpeechStatus("Ready", "Read the message aloud when you are ready.", false);
            syncPhraseMicrophoneButton();
            return true;
        };

        const startReading = () => {
            if (isReviewMode) return;
            if (resetPhraseListening()) return;
            if (isSpeechResponsePending()) return;
            if (mode === 'phrase') {
                const selectedPhrase = window.__PABASA_SELECTED_READING_ITEM__ || window.__PABASA_SELECTED_PHRASE__ || null;
                const synced = syncPhraseSelectionIntoReadingUI(selectedPhrase, { force: true });
                if (synced) {
                    console.log('Start Reading using selected phrase item', {
                        phraseIndex: window.__PABASA_CURRENT_PHRASE_INDEX__,
                        phraseId: window.__PABASA_SELECTED_READING_ITEM__?.sourceId || window.__PABASA_SELECTED_READING_ITEM__?.id || null,
                        phraseText: window.__PABASA_SELECTED_READING_ITEM__?.text || window.__PABASA_SELECTED_READING_ITEM__?.phrase || null,
                    });
                }
            }
            if (currentStoryState === "story_ready" && currentSelectedStory) {
                currentStoryState = "story_reading";
                setCurrentItemMode("paragraph");
                items = [currentSelectedStory.content || ""];
                itemTypes = ["paragraph"];
                itemPages = buildItemPages(items, itemTypes);
                itemTitles = [currentSelectedStory.title];
                pageCorrectWordCounts = items.map(() => []);
                correctWordCounts = new Array(items.length).fill(0);
                currentIndex = 0;
                currentPageIndex = Math.min(currentStorySegmentIndex, Math.max(0, getCurrentPageCount() - 1));
                startTime = null;
                updateUI();
                animateCurrentItem();
            }
            if (
                isRecording
                && (currentAssessmentUiMode === "standard" || currentStoryState === "story_reading")
            ) {
                stopReading();
                return;
            }
            startAssessmentTimer();
            if (!isRecording) {
                isRecording = true;
                spokenTranscript = "";
                correctWordCounts = new Array(items.length).fill(0);
                latestScores = null;
                currentSyllableIndex = 0;
                paragraphWordResults = {};
                pendingAudioChunk = null;
                hasHeardSinceLastChunk = false;
                resetRawMicInput("Waiting for speech...");
                if (shell.classList.contains("reader-phrase")) {
                    btnStartReading?.classList.remove("d-none");
                } else {
                    btnStartReading?.classList.add("d-none");
                }
                btnStopReading?.classList.add("d-none");
                btnReadAloud?.classList.remove("is-playing");
                updateUI();
                animateCurrentItem();
                startSpeechRecognition();
            }
            if (currentSelectedStory && currentStoryState === "story_reading") {
                updateStudentEndState({
                    stage: "story_reading",
                    selected_story: currentSelectedStory.title,
                    story_segment_index: currentPageIndex,
                });
                renderStoryReadingState(currentSelectedStory);
            }
            console.log("PABASA: Assessment recording and timer started.");
        };

        const stopReading = async () => {
            if (isReviewMode || isSpeechResponsePending()) return;
            if (!isRecording) return;
            // CRLA Official Assessment: Cleanup auto-advance timer
            if (autoAdvanceTimer) {
                window.clearTimeout(autoAdvanceTimer);
                autoAdvanceTimer = null;
            }
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
            if (currentStoryState === "story_reading" && currentSelectedStory) {
                const readingScores = calculateScores();
                const totalStoryWords = readableWordCount(currentSelectedStory.content || "");
                const wordsRead = correctWordsRead();
                await updateStudentEndState({
                    stage: "story_reading",
                    selected_story: currentSelectedStory.title,
                    story_total_words: totalStoryWords,
                    total_story_words: totalStoryWords,
                    words_read: wordsRead,
                    total_words_read: wordsRead,
                    miscues: Math.max(0, totalStoryWords - wordsRead),
                    duration_seconds: readingScores.duration_seconds,
                    wpm: readingScores.wpm,
                    comprehension_total: currentStoryQuestions.length,
                    total_questions: currentStoryQuestions.length,
                });
                renderStoryComprehensionState(currentSelectedStory.title);
                return;
            }
            const reachedLastItem = items.length > 0 && currentIndex === items.length - 1;
            showCompletion(isAssistMode || reachedLastItem);
        };

        btnStartReading?.addEventListener("click", startReading);
        btnStopReading?.addEventListener("click", stopReading);

        if (!isReviewMode && items.length && currentAssessmentUiMode !== "story") {
            startAssessmentTimer();
        }
        btnReadAloud?.addEventListener("click", readCurrentItemAloud);

        async function readCurrentItemAloud() {
            if (!items[currentIndex] || isReadAloudLoading || isSpeechResponsePending()) return;
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
            formData.append("target_text", getCurrentDisplayText() || items[currentIndex] || "");
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
                btnReadAloud?.classList.add("is-playing");
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
        speechDebugToggle?.addEventListener("change", () => setSpeechDebugPanelVisible(speechDebugToggle.checked, true));
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
            const assessmentUrl = new URL('/dashboard/assessment/', window.location.origin);
            window.location.assign(assessmentUrl.toString());
        }

        storyQuestionBackBtn?.addEventListener("click", () => {
            if (!currentStoryQuestions.length) return;
            if (currentStoryQuestionIndex > 0) {
                currentStoryQuestionIndex -= 1;
                renderCurrentStoryQuestion();
            }
        });

        storyQuestionFinishReadingBtn?.addEventListener("click", () => {
            if (storyAnswerRecording) finishStoryAnswerRecording();
            else startStoryAnswerRecording();
        });

        storyQuestionNextBtn?.addEventListener("click", () => {
            if (!currentStoryQuestions.length) return;
            if (currentStoryResults[currentStoryQuestionIndex] === null) return;
            if (currentStoryQuestionIndex < currentStoryQuestions.length - 1) {
                currentStoryQuestionIndex += 1;
                renderCurrentStoryQuestion();
                return;
            }
            showStoryCompletionScreen();
        });

        storyQuestionFinishBtn?.addEventListener("click", () => {
            goBackToAssessments();
        });

        prevBtn?.addEventListener("click", () => { 
            if (currentStoryState === "story_reading" && currentSelectedStory) {
                if (currentPageIndex > 0) {
                    currentPageIndex -= 1;
                    currentStorySegmentIndex = currentPageIndex;
                    updateStudentEndState({ stage: "story_reading", story_segment_index: currentPageIndex });
                    updateUI();
                    renderStoryReadingState(currentSelectedStory);
                    animateCurrentItem();
                }
                return;
            }
            if (currentStoryState === "story_comprehension" && currentSelectedStory) {
                if (currentStoryQuestionIndex > 0) {
                    currentStoryQuestionIndex -= 1;
                    renderCurrentStoryQuestion();
                }
                return;
            }
            goToPreviousPageOrItem();
        });

        nextBtn?.addEventListener("click", () => {
            if (currentStoryState === "story_reading" && currentSelectedStory) {
                if (currentPageIndex < getCurrentPageCount() - 1) {
                    currentPageIndex += 1;
                    currentStorySegmentIndex = currentPageIndex;
                    updateStudentEndState({ stage: "story_reading", story_segment_index: currentPageIndex });
                    updateUI();
                    renderStoryReadingState(currentSelectedStory);
                    animateCurrentItem();
                } else {
                    stopReading();
                }
                return;
            }
            if (currentStoryState === "story_comprehension") {
                storyQuestionNextBtn?.click();
                return;
            }
            goToNextPageOrItem();
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
            paragraphWordResults = {};
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
        reviewBtn?.addEventListener("click", () => {
            if (!isMyMaterials) clearStudentEndState();
            const restartUrl = new URL(window.location.href);
            if (!isMyMaterials) {
                restartUrl.searchParams.set("official_assessment_id", String(officialAssessmentId || materialId || "").trim());
            }
            window.location.assign(restartUrl.toString());
        });
        finishBtn?.addEventListener("click", () => {
            const transitionUrl = finishBtn.dataset.transitionUrl || "";
            if (transitionUrl) {
                const state = readStudentEndState();
                if (state.stage === "transition_to_rhymes") {
                    writeStudentEndState({ ...state, stage: "transition_to_rhymes", next_stage: state.next_stage || "rhymes" });
                } else if (state.stage === "transition_to_sentence") {
                    writeStudentEndState({ ...state, stage: "transition_to_sentence", next_stage: state.next_stage || "sentences" });
                } else if (state.stage === "transition_to_story") {
                    updateStudentEndState({ stage: "story_selection", next_stage: "story_selection" });
                }
                window.location.assign(transitionUrl);
                return;
            }
            goBackToAssessments();
        });

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
        window.setTimeout(() => {
            if (isCurrentLiveAssessment()) {
                startLiveCountdown();
            }
        }, 250);
        if (liveSessionStateUrl) {
            startLiveSessionPolling();
        }
    };

    if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", initReader);
    else initReader();
})();
