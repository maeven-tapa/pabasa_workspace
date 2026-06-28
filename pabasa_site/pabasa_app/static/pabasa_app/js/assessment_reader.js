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
        if (testMeta) testMeta.textContent = `${testTitle} - ${testCode}`;

        let items = [];
        let currentIndex = 0;
        let isRecording = false;
        let isMuted = false;
        let startTime = null;
        let completionSubmitted = false;

        function getCsrfToken() {
            const cookieToken = document.cookie.split('; ')
                .find(row => row.startsWith('csrftoken='))
                ?.split('=')[1];
            return cookieToken || document.querySelector('[name=csrfmiddlewaretoken]')?.value || '';
        }

        const studentClassCodesKey = "pabasaStudentClassCodes";
        const readingsStorageKey = "pabasa_class_readings";

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

        function updateUI() {
            if (!items.length) return;
            if (readingWord) readingWord.textContent = items[currentIndex];
            const label = mode.charAt(0).toUpperCase() + mode.slice(1);
            if (counter) counter.textContent = `${label} ${currentIndex + 1}/${items.length}`;
            if (progressFill) progressFill.style.width = `${((currentIndex + 1) / items.length) * 100}%`;
            
            if (prevBtn) prevBtn.disabled = !isRecording || (currentIndex === 0);
            if (nextBtn) {
                nextBtn.disabled = !isRecording || (currentIndex === items.length - 1);
                nextBtn.textContent = "Next";
            }
        }

        function showCompletion(isFullCompletion) {
            shell.classList.add("is-complete");
            closePauseMenu();
            if (completionCount) completionCount.textContent = items.length;
            if (completionLevel) completionLevel.textContent = mode.charAt(0).toUpperCase() + mode.slice(1);
            
            // Add retake attempt information to the results title
            if (viewMode === 'retake' && materialId) {
                const retakeCounts = JSON.parse(localStorage.getItem('pabasa_retake_counts') || '{}');
                const count = retakeCounts[String(materialId).trim()] || 0;
                const title = document.querySelector(".completion-card h1");
                if (title) title.innerHTML += ` <span style="background: var(--sun); color: #1b1a17; padding: 4px 12px; border-radius: 10px; font-size: 0.4em; vertical-align: middle; margin-left: 10px; font-weight: 900;">RETAKE ${count}/3</span>`;
            }

            // Skip side effects for review mode or partial progress
            if (viewMode === 'view' || !isFullCompletion || completionSubmitted) return;
            completionSubmitted = true;

            const count = parseInt(localStorage.getItem("pabasa_assessments_completed") || "0");
            localStorage.setItem("pabasa_assessments_completed", count + 1);

            // Explicitly mark this specific material as seen to decrease sidebar badges
            if (materialId) {
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
                };
                if (viewMode === 'retake') {
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
            isRecording = true;
            startTime = Date.now();
            btnStartReading?.classList.add("d-none");
            btnStopReading?.classList.remove("d-none");
            updateUI();
            console.log("PABASA: Assessment recording and timer started.");
        };

        const stopReading = () => {
            if (!isRecording) return;
            isRecording = false;
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
            else { showCompletion(true); }
        });

        pauseBtn?.addEventListener("click", () => {
            const isHidden = pauseMenu?.classList.contains("d-none");
            pauseMenu?.classList.toggle("d-none", !isHidden);
            pauseOverlay?.classList.toggle("d-none", !isHidden);
        });
        pauseOverlay?.addEventListener("click", closePauseMenu);
        resumeBtn?.addEventListener("click", closePauseMenu);
        retryBtn?.addEventListener("click", () => {
            shell.classList.remove("is-complete");
            currentIndex = 0;
            updateUI();
            closePauseMenu();
        });
        quitBtn?.addEventListener("click", () => { window.location.href = '/dashboard/assessment/'; });
        reviewBtn?.addEventListener("click", () => { location.reload(); });
        finishBtn?.addEventListener("click", () => { window.location.href = '/dashboard/assessment/'; });

        if (viewMode === 'view') {
            if (pauseBtn) pauseBtn.classList.add("d-none");
            if (testMeta) testMeta.innerHTML += ' <span style="background: rgba(148, 163, 184, 0.2); color: var(--muted); padding: 2px 8px; border-radius: 6px; font-size: 0.6em; vertical-align: middle; margin-left: 8px;">Review Mode</span>';
        }

        loadItems();
    };

    if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", initReader);
    else initReader();
})();