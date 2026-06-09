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
            classStatusText.textContent =
                "Join a class from the dashboard to receive assigned tests.";
            return;
        }

        const classCode = activeCodes[0];

        const teacherClasses = JSON.parse(
            localStorage.getItem("pabasa_teacher_classes") || "[]"
        );

        const currentClass = teacherClasses.find(
            c => String(c.code).toUpperCase() === String(classCode).toUpperCase()
        );

        const className =
            currentClass?.name ||
            currentClass?.subject ||
            "Unknown Class";

        const readings = JSON.parse(
            localStorage.getItem("pabasa_class_readings") || "{}"
        );

        const classReadings =
            readings[classCode] ||
            readings[classCode.toUpperCase()] ||
            {};

        const assignedAssessments =
            (classReadings.words?.length || classReadings.word?.length || 0) +
            (classReadings.sentences?.length || classReadings.sentence?.length || 0) +
            (classReadings.paragraphs?.length || classReadings.paragraph?.length || 0);

        const completedAssessments = parseInt(
            localStorage.getItem("pabasa_assessments_completed") || "0"
        );

        const progress =
            assignedAssessments > 0
                ? Math.round(
                    (completedAssessments / assignedAssessments) * 100
                )
                : 0;

    const classCount = activeCodes.length;
    const remaining = Math.max(0, assignedAssessments - completedAssessments);

    classStatusTitle.textContent = "Classrooms Active";
    classStatusTitle.className = "class-status-title";

    let summary = `You have joined ${classCount} class${classCount === 1 ? '' : 'es'}. `;
    summary += `There are ${assignedAssessments} assigned assessments. `;

    if (assignedAssessments === 0) {
        summary += "No assessments assigned yet.";
    } else if (remaining === 0) {
        summary += "All assigned assessments are completed.";
    } else {
        summary += `You have ${remaining} assessment${remaining === 1 ? '' : 's'} remaining.`;
    }

    classStatusText.innerHTML = `
        <span class="class-status-label">CLASS STATUS</span>
        <div class="class-status-summary">${summary}</div>
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

            // Reset publication status to default when opening the modal
            if (addItemStatus) {
                addItemStatus.value = "published";
                toggleItemPublishDate();
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
