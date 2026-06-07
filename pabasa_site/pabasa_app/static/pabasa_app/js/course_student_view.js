document.addEventListener("DOMContentLoaded", function () {
    // Inject hover styles for material cards
    const style = document.createElement('style');
    style.textContent = `
        .material-card-modern:hover {
            transform: translateY(-2px);
            box-shadow: 0 8px 24px rgba(31, 111, 139, 0.12) !important;
            border-color: #2ea8e5 !important;
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

        const seenIds = JSON.parse(localStorage.getItem('pabasa_seen_material_ids') || '[]');

        function renderList(type, containerId) {
            const container = document.getElementById(containerId);
            if (!container) return;

            const items = classData[type] || [];
            if (items.length === 0) {
                container.innerHTML = '<div class="readings-empty text-center p-3 text-muted small"><i class="bi bi-inbox d-block mb-1"></i> No materials yet</div>';
                return;
            }

            container.innerHTML = items.map(item => {
                const isNew = !seenIds.map(String).includes(String(item.id));

                return `
                    <div class="material-card-modern shadow-sm border mb-2" 
                         data-material-id="${item.id}" 
                         data-material-type="${type}" 
                         data-material-title="${item.title}"
                         data-usage-type="${item.type}"
                         style="background: white; border-radius: 12px; padding: 1.1rem; display: flex; align-items: center; border-color: rgba(31, 111, 139, 0.1); transition: all 0.2s ease; cursor: pointer;">
                        <div class="material-leading-icon me-3" style="width: 42px; height: 42px; background: #eaf7fd; color: #2ea8e5; display: flex; align-items: center; justify-content: center; border-radius: 10px;">
                            <i class="bi ${type === 'word' ? 'bi-spellcheck' : type === 'sentence' ? 'bi-chat-left-text' : 'bi-file-text'}"></i>
                        </div>
                        <div style="flex: 1;">
                            <h6 class="mb-0 fw-bold d-flex align-items-center">
                                ${item.title}
                                ${isNew ? '<span class="badge bg-warning text-dark ms-2" style="font-size: 0.6rem; padding: 0.25em 0.5em;">NEW</span>' : ''}
                            </h6>
                            <p class="mb-0 text-muted small">${Array.isArray(item.items) ? item.items.length : item.items} items • ${item.level}</p>
                        </div>
                        <button class="btn btn-sm btn-primary rounded-pill px-3">Start</button>
                    </div>
                `;
            }).join('');
        }

        // These IDs match the containers used in the teacher's Reading tab
        renderList('word', 'wordReadings');
        renderList('sentence', 'sentenceReadings');
        renderList('paragraph', 'paragraphReadings');
    }

    // --- Click Handler for Marking as Read & Navigation ---
    function handleStartClick(e) {
        const btn = e.target.closest('button');
        if (!btn) return;

        const card = btn.closest('.material-card-modern');
        const materialId = card.dataset.materialId;
        const type = card.dataset.materialType;
        const title = card.dataset.materialTitle;
        const usage = card.dataset.usageType;

        // Mark as seen in localStorage
        const seenIds = JSON.parse(localStorage.getItem('pabasa_seen_material_ids') || '[]');
        if (!seenIds.map(String).includes(String(materialId))) {
            // Save as number if possible to maintain consistency
            const idToSave = isNaN(materialId) ? materialId : Number(materialId);
            seenIds.push(idToSave);
            localStorage.setItem('pabasa_seen_material_ids', JSON.stringify(seenIds));
            
            // Dispatch custom event so base_dashboard.js updates the sidebar badges instantly
            window.dispatchEvent(new CustomEvent('pabasa:student-class-updated'));
        }

        // Notify teacher that activity started
        const studentName = window.PABASA_USER_NAME || "A student";
        let notifications = JSON.parse(localStorage.getItem('pabasa_notifications') || '[]');
        notifications.unshift({
            id: Date.now() + Math.random(),
            classCode: classCode,
            title: "Activity Update",
            message: `${studentName} started reading "${title}"`,
            timestamp: Date.now(),
            read: false,
            role: 'teacher'
        });
        localStorage.setItem('pabasa_notifications', JSON.stringify(notifications.slice(0, 100)));
        window.dispatchEvent(new Event('pabasa:notifications-updated'));
        
        // Navigate to the appropriate reader page
        const baseUrl = usage === 'assessment' ? '/dashboard/assessment/reading_ui' : '/dashboard/practice';
        window.location.href = `${baseUrl}/${type}/?code=${classCode}&test=${encodeURIComponent(title)}&id=${materialId}`;
    }

    // Attach click listeners to the containers
    ['wordReadings', 'sentenceReadings', 'paragraphReadings'].forEach(id => {
        const el = document.getElementById(id);
        if (el) el.addEventListener('click', handleStartClick);
    });

    // Run once on load
    loadReadings();
});
