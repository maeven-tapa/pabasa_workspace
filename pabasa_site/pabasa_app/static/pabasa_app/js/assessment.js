document.addEventListener("DOMContentLoaded", function () {
    const addItemModal = document.getElementById("addItemModal");
    const itemLessonName = document.getElementById("itemLessonName");
    const readingType = document.getElementById("readingType");
    const viewResponseModal = document.getElementById("viewResponseModal");
    const responseTestName = document.getElementById("responseTestName");
    const responseSummaryModal = document.getElementById("responseSummaryModal");
    const startAssessmentModal = document.getElementById("startAssessmentModal");
    const startAssessmentName = document.getElementById("startAssessmentName");
    const startAssessmentCode = document.getElementById("startAssessmentCode");
    const summaryStudentName = document.getElementById("summaryStudentName");
    const summaryAccuracy = document.getElementById("summaryAccuracy");
    const summaryTimeRead = document.getElementById("summaryTimeRead");
    const summaryWordsToPractice = document.getElementById("summaryWordsToPractice");
    const summaryWpm = document.getElementById("summaryWpm");
    const summaryReadOverTotal = document.getElementById("summaryReadOverTotal");
    const editTestModal = document.getElementById("editTestModal");
    const editTestIcon = document.getElementById("editTestIcon");
    const editTestIconPreview = document.getElementById("editTestIconPreview");
    const editTestTitle = document.getElementById("editTestTitle");
    const editTestDescription = document.getElementById("editTestDescription");
    const enableTargetReadingTime = document.getElementById("enableTargetReadingTime");
    const targetReadingTimeRow = document.getElementById("targetReadingTimeRow");
    const targetReadingTime = document.getElementById("targetReadingTime");
    const editSectionOnly = document.getElementById("editSectionOnly");
    const editSectionOnlyRow = document.getElementById("editSectionOnlyRow");
    const editAllowedSection = document.getElementById("editAllowedSection");
    const sendParentEmail = document.getElementById("sendParentEmail");
    const parentEmailRow = document.getElementById("parentEmailRow");
    const parentEmail = document.getElementById("parentEmail");
    const enableAssessmentAvailability = document.getElementById("enableAssessmentAvailability");
    const scheduleSectionRow = document.getElementById("scheduleSectionRow");
    const availabilityStartDate = document.getElementById("availabilityStartDate");
    const availabilityStartTime = document.getElementById("availabilityStartTime");
    const availabilityEndDate = document.getElementById("availabilityEndDate");
    const availabilityEndTime = document.getElementById("availabilityEndTime");
    const addItemStatus = document.getElementById("addItemStatus");
    const itemPublishDateRow = document.getElementById("itemPublishDateRow");
    const itemPublishDate = document.getElementById("itemPublishDate");

        /**
         * Updates the Class Status card on the student assessment dashboard.
         * Reflects the current enrollment status from localStorage.
         */
    function updateClassStatusUI() {
        console.log("UPDATE CLASS STATUS RUNNING");
        const classStatusTitle = document.getElementById("classStatusTitle");
        const classStatusText = document.getElementById("classStatusText");

        if (!classStatusTitle || !classStatusText) return;

        let codes = [];

        try {
            codes = JSON.parse(localStorage.getItem("pabasaStudentClassCodes") || "[]");

            const legacy = localStorage.getItem("pabasaStudentClassCode");
            if (
                legacy &&
                !codes.some(
                    c => String(c).toUpperCase() === String(legacy).toUpperCase()
                )
            ) {
                codes.push(legacy);
            }
        } catch (e) {
            const legacy = localStorage.getItem("pabasaStudentClassCode");
            if (legacy) codes = [legacy];
        }

        const activeCodes = codes.filter(Boolean);

        if (activeCodes.length === 0) {
            classStatusTitle.textContent = "Waiting for class";
            classStatusTitle.className = "fw-bold text-muted";
            classStatusText.innerHTML = '<p class="small mb-0" style="color: rgba(255,255,255,.64);">Join a class from the dashboard to receive assigned tests.</p>';
            return;
        }

        const readingsByClass = JSON.parse(localStorage.getItem("pabasa_class_readings") || "{}");
        const readingsMap = {};
        Object.keys(readingsByClass).forEach(key => { readingsMap[key.toUpperCase()] = readingsByClass[key]; });

        const seenIds = JSON.parse(localStorage.getItem("pabasa_seen_material_ids") || "[]").map(id => String(id).trim());

        let totalAssigned = 0;
        let totalCompleted = 0;

        activeCodes.forEach(rawCode => {
            const code = String(rawCode).toUpperCase();
            const readings = readingsMap[code] || {};
            ["word", "sentence", "paragraph"].forEach(type => {
                const list = Array.isArray(readings[type]) ? readings[type] : (Array.isArray(readings[type + 's']) ? readings[type + 's'] : []);
                list.forEach(m => {
                    if (m && m.type && (m.type.toLowerCase() === "assessment" || m.type.toLowerCase() === "both")) {
                         let isLive = !m.status || m.status === 'published';
                         if (m.status === 'scheduled' && m.schedule) {
                             isLive = new Date(m.schedule).getTime() <= Date.now();
                         }
                         if (isLive) {
                             totalAssigned++;
                             const mId = (m.id !== undefined && m.id !== null) ? String(m.id).trim() : null;
                             if (mId && seenIds.includes(mId)) {
                                 totalCompleted++;
                             }
                         }
                    }
                });
            });
        });

        const progress = totalAssigned > 0 ? Math.round((totalCompleted / totalAssigned) * 100) : 0;
        const remaining = Math.max(0, totalAssigned - totalCompleted);

        classStatusTitle.textContent = activeCodes.length === 1 ? "Classroom Active" : "Classrooms Active";
        classStatusTitle.className = "class-status-title";

        classStatusText.innerHTML = `
            <div class="ticket-progress">
                <div class="ticket-progress-bar" style="width: ${progress}%"></div>
            </div>
            <div class="ticket-metrics mb-2">
                <span><span class="highlight">${progress}%</span> Progress</span>
                <span><span class="highlight">${totalCompleted}/${totalAssigned}</span> Completed</span>
            </div>
            <p class="small mb-0" style="color: rgba(255,255,255,.64); line-height: 1.4;">
                ${totalAssigned === 0 
                    ? "No assessments assigned yet." 
                    : (remaining === 0 
                        ? "<strong>Mission Accomplished!</strong> All assessments are finished." 
                        : `You have <strong>${remaining}</strong> assessment${remaining === 1 ? "" : "s"} left to complete.`)}
            </p>
        `;
    }

    function toggleSectionOnlyRow() {
        if (!editSectionOnly || !editSectionOnlyRow || !editAllowedSection) {
            return;
        }

        const isChecked = editSectionOnly.checked;
        editSectionOnlyRow.classList.toggle("d-none", !isChecked);
        editAllowedSection.required = isChecked;
        if (!isChecked) {
            editAllowedSection.value = "grade5a";
        }
    }

    if (editSectionOnly) {
        editSectionOnly.addEventListener("change", toggleSectionOnlyRow);
    }

    function toggleTargetReadingTimeRow() {
        if (!enableTargetReadingTime || !targetReadingTimeRow || !targetReadingTime) {
            return;
        }

        const isEnabled = enableTargetReadingTime.checked;
        targetReadingTimeRow.classList.toggle("d-none", !isEnabled);
        targetReadingTime.required = isEnabled;

        if (!isEnabled) {
            targetReadingTime.value = "";
        }
    }

    if (enableTargetReadingTime) {
        enableTargetReadingTime.addEventListener("change", toggleTargetReadingTimeRow);
    }

    function toggleParentEmailRows() {
        if (!sendParentEmail || !parentEmailRow || !parentEmail) {
            return;
        }

        const isParentEmailEnabled = sendParentEmail.checked;
        parentEmailRow.classList.toggle("d-none", !isParentEmailEnabled);
        parentEmail.required = isParentEmailEnabled;

        if (!isParentEmailEnabled) {
            parentEmail.value = "";
        }
    }

    if (sendParentEmail) {
        sendParentEmail.addEventListener("change", toggleParentEmailRows);
    }

    function toggleAvailabilitySection() {
        if (!enableAssessmentAvailability || !scheduleSectionRow) {
            return;
        }

        const isEnabled = enableAssessmentAvailability.checked;
        scheduleSectionRow.classList.toggle("d-none", !isEnabled);

        [availabilityStartDate, availabilityStartTime, availabilityEndDate, availabilityEndTime].forEach(function (field) {
            if (!field) {
                return;
            }

            field.required = isEnabled;
            if (!isEnabled) {
                field.value = "";
            }
        });
    }

    if (enableAssessmentAvailability) {
        enableAssessmentAvailability.addEventListener("change", toggleAvailabilitySection);
    }

    function updateReadingSections(value) {
        document.querySelectorAll("[data-reading-section]").forEach(function (section) {
            section.classList.toggle("d-none", section.getAttribute("data-reading-section") !== value);
        });
    }

    if (readingType) {
        readingType.addEventListener("change", function () {
            updateReadingSections(readingType.value);
        });
        updateReadingSections(readingType.value);
    }

    if (addItemModal && itemLessonName) {
        addItemModal.addEventListener("show.bs.modal", function (event) {
            const trigger = event.relatedTarget;
            const lessonTitle = trigger ? trigger.getAttribute("data-lesson-title") : "Assessment";
            itemLessonName.textContent = lessonTitle || "Assessment";

            // Safety: Hide legacy reading level dropdown if still present in HTML
            const legacyLevel = document.getElementById("itemLevel") || document.querySelector('[name="level"]');
            if (legacyLevel && legacyLevel.closest('.mb-3')) {
                legacyLevel.closest('.mb-3').style.display = 'none';
            }

            const mId = trigger ? trigger.getAttribute("data-material-id") : null;
            const mStatus = trigger ? trigger.getAttribute("data-material-status") : "published";
            const mSchedule = trigger ? trigger.getAttribute("data-material-schedule") : "";

            if (mId) {
                if (addItemStatus) addItemStatus.value = mStatus;
                if (itemPublishDate) itemPublishDate.value = mSchedule || "";
            } else {
                if (addItemStatus) addItemStatus.value = "published";
                if (itemPublishDate) itemPublishDate.value = "";
            }

            if (itemPublishDateRow) {
                const isScheduled = (addItemStatus ? addItemStatus.value : "published") === "scheduled";
                itemPublishDateRow.classList.toggle("d-none", !isScheduled);
                if (itemPublishDate) itemPublishDate.required = isScheduled;
            }
        });
    }

    if (viewResponseModal && responseTestName) {
        viewResponseModal.addEventListener("show.bs.modal", function (event) {
            const trigger = event.relatedTarget;
            const testTitle = trigger ? trigger.getAttribute("data-test-title") : "Assessment";
            responseTestName.textContent = testTitle || "Assessment";
        });
    }

    if (responseSummaryModal) {
        responseSummaryModal.addEventListener("show.bs.modal", function (event) {
            const trigger = event.relatedTarget;
            const studentName = trigger ? trigger.getAttribute("data-student-name") : "Student";
            const accuracy = trigger ? trigger.getAttribute("data-accuracy") : "-";
            const timeRead = trigger ? trigger.getAttribute("data-time-read") : "-";
            const wordsToPractice = trigger ? trigger.getAttribute("data-words-practice") : "-";
            const wpm = trigger ? trigger.getAttribute("data-wpm") : "-";
            const readWords = trigger ? trigger.getAttribute("data-read-words") : "-";
            const totalWords = trigger ? trigger.getAttribute("data-total-words") : "-";

            if (summaryStudentName) {
                summaryStudentName.textContent = studentName || "Student";
            }

            if (summaryAccuracy) {
                summaryAccuracy.textContent = accuracy || "-";
            }

            if (summaryTimeRead) {
                summaryTimeRead.textContent = timeRead || "-";
            }

            if (summaryWordsToPractice) {
                summaryWordsToPractice.textContent = wordsToPractice || "-";
            }

            if (summaryWpm) {
                summaryWpm.textContent = wpm || "-";
            }

            if (summaryReadOverTotal) {
                summaryReadOverTotal.textContent = (readWords || "-") + " / " + (totalWords || "-");
            }
        });
    }

    if (startAssessmentModal) {
        startAssessmentModal.addEventListener("show.bs.modal", function (event) {
            const trigger = event.relatedTarget;
            const testTitle = trigger ? trigger.getAttribute("data-test-title") : "Assessment";
            const testCode = trigger ? trigger.getAttribute("data-test-code") : "TST-000";

            if (startAssessmentName) {
                startAssessmentName.textContent = testTitle || "Assessment";
            }

            if (startAssessmentCode) {
                startAssessmentCode.textContent = testCode || "TST-000";
            }
        });
    }

    if (editTestIcon && editTestIconPreview) {
        editTestIcon.addEventListener("change", function () {
            editTestIconPreview.className = "bi " + editTestIcon.value;
        });
    }

    if (editTestModal) {
        editTestModal.addEventListener("show.bs.modal", function (event) {
            const trigger = event.relatedTarget;
            const testTitle = trigger ? trigger.getAttribute("data-test-title") : "";
            const testDescription = trigger ? trigger.getAttribute("data-test-description") : "";
            const testIcon = trigger ? trigger.getAttribute("data-test-icon") : "bi-journal-check";
            const sectionOnly = trigger ? trigger.getAttribute("data-section-only") : "false";
            const testSection = trigger ? trigger.getAttribute("data-test-section") : "grade5a";

            if (editTestTitle) {
                editTestTitle.value = testTitle || "";
            }

            if (editTestDescription) {
                editTestDescription.value = testDescription || "";
            }

            if (editTestIcon) {
                editTestIcon.value = testIcon || "bi-journal-check";
            }

            if (editTestIconPreview) {
                editTestIconPreview.className = "bi " + (testIcon || "bi-journal-check");
            }

            if (editSectionOnly) {
                editSectionOnly.checked = sectionOnly === "true";
            }

            if (enableTargetReadingTime) {
                enableTargetReadingTime.checked = false;
            }

            if (editAllowedSection) {
                editAllowedSection.value = testSection || "grade5a";
            }

            if (sendParentEmail) {
                sendParentEmail.checked = false;
            }

            if (enableAssessmentAvailability) {
                enableAssessmentAvailability.checked = false;
            }

            toggleParentEmailRows();
            toggleAvailabilitySection();
            toggleTargetReadingTimeRow();

            toggleSectionOnlyRow();
        });
    }

    toggleSectionOnlyRow();
    toggleParentEmailRows();
    toggleAvailabilitySection();
    toggleTargetReadingTimeRow();

    // Initialize the class status UI
    updateClassStatusUI();

    // Listen for enrollment updates to keep the UI in sync
    window.addEventListener("pabasa:student-class-updated", updateClassStatusUI);
    window.addEventListener("storage", (e) => {
        const updateKeys = ["pabasaStudentClassJoined", "pabasaStudentClassCodes", "pabasa_assessments_completed"];
        if (updateKeys.includes(e.key)) updateClassStatusUI();
    });
});
