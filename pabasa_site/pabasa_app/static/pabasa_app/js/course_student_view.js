document.addEventListener("DOMContentLoaded", function () {
    // Inject hover styles for material cards
    const style = document.createElement('style');
    style.textContent = `
        #wordReadings, #sentenceReadings, #paragraphReadings {
            padding: 12px 8px !important;
            overflow: visible !important;
        }
        .tab-content, .tab-pane {
            padding-top: 32px !important; /* Extra space to prevent heading clipping */
            height: auto !important;
            min-height: auto !important;
            overflow: visible !important;
        }
        .material-card-modern:hover {
            transform: translateY(-2px);
            box-shadow: 0 8px 24px rgba(31, 111, 139, 0.12) !important;
            border-color: #2ea8e5 !important;
        }
        .material-card-highlighted {
            background: linear-gradient(135deg, #fffdf7 0%, #fff9e6 100%) !important;
            border-color: rgba(255, 214, 57, 0.4) !important;
            box-shadow: 0 4px 12px rgba(255, 214, 57, 0.15) !important;
        }
        .material-card-done {
            background: #f0fdf4 !important;
            border-color: rgba(22, 163, 74, 0.2) !important;
            opacity: 0.85;
        }
    `;
    document.head.appendChild(style);

    const lessonIcon = document.getElementById("lessonIcon");
    const lessonIconPreview = document.getElementById("lessonIconPreview");

    if (lessonIcon && lessonIconPreview) {
        lessonIcon.addEventListener("change", function () {
            lessonIconPreview.className = "bi " + lessonIcon.value;
        });
    }

    // --- Student Materials View & NEW Badge Logic ---
    const urlParams = new URLSearchParams(window.location.search);
    const classCode = urlParams.get('code');
    if (!classCode) return;

    function loadReadings() {
        const readings = JSON.parse(localStorage.getItem('pabasa_class_readings') || '{}');
        
        // Normalize readings map for case-insensitive class code lookups
        const readingsMap = {};
        Object.keys(readings).forEach(key => {
            readingsMap[key.toUpperCase()] = readings[key];
        });

        const classData = readingsMap[classCode.toUpperCase()];
        if (!classData) return;

        const seenIds = JSON.parse(localStorage.getItem('pabasa_seen_material_ids') || '[]').map(id => String(id).trim());

        function renderList(type, containerId) {
            const container = document.getElementById(containerId);
            if (!container) return;

            // Support both singular and plural forms (word/words)
            const rawItems = Array.isArray(classData[type]) ? classData[type] : (Array.isArray(classData[type + 's']) ? classData[type + 's'] : []);

            const items = rawItems.filter(m => { // Ensure 'm' is defined and has 'status' and 'schedule' properties
                // Check if material is live (published or scheduled time passed)
                if (!m.status || m.status === 'published') return true;
                if (m.status === 'scheduled' && m.schedule) {
                    return new Date(m.schedule).getTime() <= Date.now();
                }
                return false;
            });
            if (items.length === 0) {
                container.innerHTML = '<div class="readings-empty text-center p-3 text-muted small"><i class="bi bi-inbox d-block mb-1"></i> No materials yet</div>';
                return;
            }

            container.innerHTML = items.map(item => {
                const mId = (item.id !== undefined && item.id !== null) ? String(item.id).trim() : null;
                const isNew = mId && !seenIds.includes(mId);
                const isDone = mId && seenIds.includes(mId);

                return `
                    <div class="material-card-modern shadow-sm border mb-2 ${isNew ? 'material-card-highlighted' : (isDone ? 'material-card-done' : '')}" 
                         data-material-id="${item.id}" 
                         data-material-type="${type}" 
                         data-material-title="${item.title}"
                         data-usage-type="${item.type}"
                         style="border-radius: 12px; padding: 1.1rem; display: flex; align-items: center; border-color: rgba(31, 111, 139, 0.1); transition: all 0.2s ease; cursor: pointer;">
                        <div class="material-leading-icon me-3" style="flex-shrink: 0; width: 42px; height: 42px; background: #eaf7fd; color: #2ea8e5; display: flex; align-items: center; justify-content: center; border-radius: 10px;">
                            <i class="bi ${type === 'word' ? 'bi-spellcheck' : type === 'sentence' ? 'bi-chat-left-text' : 'bi-file-text'}"></i>
                        </div>
                        <div style="flex: 1; min-width: 0;">
                            <h6 class="mb-0 fw-bold d-flex align-items-center text-truncate" title="${item.title}">
                                ${item.title}
                                ${isNew ? '<span class="badge bg-warning text-dark ms-2" style="font-size: 0.6rem; padding: 0.25em 0.5em;">NEW</span>' : ''}
                                ${isDone ? '<span class="badge bg-success ms-2" style="font-size: 0.6rem; padding: 0.25em 0.5em;">DONE</span>' : ''}
                            </h6>
                            <p class="mb-0 text-muted small">${Array.isArray(item.items) ? item.items.length : item.items} items</p>
                        </div>
                        <button class="btn btn-sm ${isDone ? 'btn-outline-success' : 'btn-primary'} rounded-pill px-3" style="flex-shrink: 0;">${isDone ? 'Review' : 'Start'}</button>
                    </div>
                `;
            }).join('');
        }

        // These IDs match the containers used in the teacher's Reading tab
        renderList('word', 'wordReadings');
        renderList('sentence', 'sentenceReadings');
        renderList('paragraph', 'paragraphReadings');
    }

    // --- Review Choice Logic ---
    let selectedMaterialData = null;
    
    function navigateToReader(viewMode = 'initial') {
        if (!selectedMaterialData) return;
        const { materialId, type, title, usage } = selectedMaterialData;
        
        // Notify teacher that activity started
        if (viewMode === 'initial') {
            const studentName = window.PABASA_USER_NAME || "A student";
            const teacherClasses = JSON.parse(localStorage.getItem('pabasa_teacher_classes') || '[]');
            const cls = teacherClasses.find(c => c.code === classCode);
            const teacherEmail = cls ? cls.teacherEmail : null;

            let notifications = JSON.parse(localStorage.getItem('pabasa_notifications') || '[]');
            notifications.unshift({
                id: Date.now() + Math.random(),
                classCode: classCode,
                title: "Activity Update",
                message: `${studentName} started reading "${selectedMaterialData.title}"`,
                timestamp: Date.now(),
                read: false,
                role: 'teacher',
                recipientEmail: teacherEmail
            });
            localStorage.setItem('pabasa_notifications', JSON.stringify(notifications.slice(0, 100)));
            window.dispatchEvent(new Event('pabasa:notifications-updated'));
        }

        // Determine correct base URL based on designation
        const baseUrl = (usage === 'assessment' || usage === 'both') ? '/dashboard/assessment' : '/dashboard/practice';
        window.location.href = `${baseUrl}/${type}/?code=${classCode}&test=${encodeURIComponent(selectedMaterialData.title)}&id=${selectedMaterialData.materialId}&viewMode=${viewMode}`;
    }

    // --- Click Handler for Marking as Read & Navigation ---
    function handleStartClick(e) {
        // Handle clicks on the card itself or any children, not just the start button
        const card = e.target.closest('.material-card-modern');
        if (!card) return;

        selectedMaterialData = {
            materialId: card.dataset.materialId,
            type: card.dataset.materialType,
            title: card.dataset.materialTitle,
            usage: card.dataset.usageType
        };

        navigateToReader('initial');
    }

    // Attach click listeners to the containers
    ['wordReadings', 'sentenceReadings', 'paragraphReadings'].forEach(id => {
        const el = document.getElementById(id);
        if (el) el.addEventListener('click', handleStartClick);
    });

    // Run once on load
    loadReadings();

    // Refresh highlights if storage updates (e.g., student finishes an activity)
    window.addEventListener("pabasa:student-class-updated", loadReadings);
    window.addEventListener("pabasa:preferences-updated", loadReadings);
    
    // Refresh list if a scheduled material is activated and triggers a notification
    window.addEventListener("pabasa:notifications-updated", loadReadings);

    window.addEventListener("storage", (e) => {
        if (e.key === 'pabasa_seen_material_ids' || e.key === 'pabasa_class_readings') loadReadings();
    });
});
