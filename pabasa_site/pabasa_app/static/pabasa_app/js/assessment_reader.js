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

        const urlParams = new URLSearchParams(window.location.search);
        const testTitle = urlParams.get("test") || "Assessment";
        const testCode = urlParams.get("code") || "TST-000";
        const materialId = urlParams.get("id");
        if (testMeta) testMeta.textContent = `${testTitle} - ${testCode}`;

        let items = [];
        let currentIndex = 0;

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
                            
                            // Load material only if it matches the requested test title for this specific class
                            if (isAssessment && (material.title === testTitle || (!testTitle && aggregatedItems.length === 0))) {
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
            if (prevBtn) prevBtn.disabled = (currentIndex === 0);
            if (nextBtn) {
                nextBtn.disabled = false;
                nextBtn.textContent = currentIndex === items.length - 1 ? "Finish" : "Next";
            }
        }

        function showCompletion() {
            shell.classList.add("is-complete");
            closePauseMenu();
            if (completionCount) completionCount.textContent = items.length;
            if (completionLevel) completionLevel.textContent = mode.charAt(0).toUpperCase() + mode.slice(1);
            const count = parseInt(localStorage.getItem("pabasa_assessments_completed") || "0");
            localStorage.setItem("pabasa_assessments_completed", count + 1);

            // Explicitly mark this specific material as seen to decrease sidebar badges
            if (materialId) {
                const seenIds = getStoredData("pabasa_seen_material_ids", []);
                if (!seenIds.map(String).includes(String(materialId))) {
                    const idToSave = isNaN(materialId) ? materialId : Number(materialId);
                    seenIds.push(idToSave);
                    localStorage.setItem("pabasa_seen_material_ids", JSON.stringify(seenIds));
                    window.dispatchEvent(new CustomEvent('pabasa:student-class-updated'));
                }
            }

            // Notify teacher that activity finished
            const studentName = window.PABASA_USER_NAME || "A student";
            let notifications = JSON.parse(localStorage.getItem('pabasa_notifications') || '[]');
            notifications.unshift({
                id: Date.now() + Math.random(),
                classCode: testCode,
                title: "Activity Update",
                message: `${studentName} finished reading "${testTitle}"`,
                timestamp: Date.now(),
                read: false,
                role: 'teacher'
            });
            localStorage.setItem('pabasa_notifications', JSON.stringify(notifications.slice(0, 100)));
            window.dispatchEvent(new Event('pabasa:notifications-updated'));
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
            else { showCompletion(); }
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

        loadItems();
    };

    if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", initReader);
    else initReader();
})();