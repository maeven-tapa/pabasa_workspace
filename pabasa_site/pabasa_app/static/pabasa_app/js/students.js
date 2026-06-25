(function () {
function initStudentsPage() {
    const studentSearchInput = document.getElementById("studentSearchInput");
    const readingLevelFilter = document.getElementById("readingLevelFilter");
    const studentEmptyState = document.getElementById("studentEmptyState");
    const studentResultCount = document.getElementById("studentResultCount");
    const assignSectionModal = document.getElementById("assignSectionModal");
    const studentNameInput = document.getElementById("assignSectionStudentName");
    const currentSectionInput = document.getElementById("assignSectionCurrentSection");
    const changeStatusModal = document.getElementById("changeStatusModal");
    const changeStatusStudentName = document.getElementById("changeStatusStudentName");
    const changeStatusCurrent = document.getElementById("changeStatusCurrent");

    function normalize(value) {
        return (value || "").toLowerCase().trim();
    }

    function normalizeKeyPart(value) {
        return normalize(value).replace(/\s+/g, " ");
    }

    function getStudentKeys(student) {
        const keys = [];
        const id = student.pabasa_id || student.custom_id || "";
        if (id) keys.push(`id:${normalizeKeyPart(id)}`);

        const email = student.email || "";
        if (email) keys.push(`email:${normalizeKeyPart(email)}`);

        const name = normalizeKeyPart(student.name);
        if (name) keys.push(`name:${name}`);

        return keys;
    }

    function toClassList(value) {
        if (Array.isArray(value)) {
            return value.map(item => String(item || "").trim()).filter(Boolean);
        }

        if (typeof value === "string") {
            return value.split(",").map(item => item.trim()).filter(Boolean);
        }

        return [];
    }

    function collectClassNames(student) {
        return [
            ...toClassList(student.allClasses),
            ...toClassList(student.classes),
            ...toClassList(student.class)
        ];
    }

    function addUniqueClasses(target, classNames) {
        target.allClasses = Array.isArray(target.allClasses) ? target.allClasses : [];
        classNames.forEach(className => {
            if (!target.allClasses.some(existing => normalizeKeyPart(existing) === normalizeKeyPart(className))) {
                target.allClasses.push(className);
            }
        });
        target.class = target.allClasses[0] || target.class || "";
    }

    function filterStudents() {
        const query = normalize(studentSearchInput ? studentSearchInput.value : "");
        const selectedLevel = readingLevelFilter ? readingLevelFilter.value : "All levels";
        let visibleCount = 0;
        
        // Query student rows dynamically each time (includes newly added students)
        const studentRows = Array.from(document.querySelectorAll(".student-card-row"));

        studentRows.forEach(function (row) {
            const searchableText = normalize(
                [
                    row.getAttribute("data-student-name"),
                    row.getAttribute("data-reading-level"),
                    row.getAttribute("data-class-name"),
                    row.textContent
                ].join(" ")
            );
            const rowLevel = row.getAttribute("data-reading-level") || "";
            const matchesSearch = !query || searchableText.includes(query);
            const matchesLevel = selectedLevel === "All levels" || rowLevel === selectedLevel;
            const shouldShow = matchesSearch && matchesLevel;

            row.classList.toggle("d-none", !shouldShow);
            if (shouldShow) {
                visibleCount += 1;
            }
        });

        if (studentEmptyState) {
            studentEmptyState.classList.toggle("is-visible", visibleCount === 0);
        }

        if (studentResultCount) {
            studentResultCount.textContent = visibleCount;
        }
    }

    if (studentSearchInput) {
        studentSearchInput.addEventListener("input", filterStudents);
    }

    if (readingLevelFilter) {
        readingLevelFilter.addEventListener("change", filterStudents);
    }

    filterStudents();

    async function renderStudentDirectory() {
        const studentDirectory = document.querySelector(".student-directory");
        const modalStudentList = document.querySelector("#studentListSection .modal-student-checkbox-list");
        
        if (!studentDirectory && !modalStudentList) return;
        
        // Clear current rows to re-render consolidated list
        if (studentDirectory) {
            studentDirectory.querySelectorAll(".student-card-row").forEach(row => row.remove());
        }
        
        // 1. Fetch Authoritative Data from Server
        let serverStudents = [];
        try {
            const response = await fetch('/dashboard/teacher/students-api/', {
                method: 'GET',
                credentials: 'same-origin',
                headers: { 'X-Requested-With': 'XMLHttpRequest' }
            });

            if (response && response.ok) {
                // Read body once and attempt to parse as JSON
                const text = await response.text();
                let data = null;
                try {
                    data = JSON.parse(text || '{}');
                } catch (e) {
                    console.error('PABASA: Invalid JSON response when fetching students:', e);
                    console.error(text);
                }

                if (data && data.success && Array.isArray(data.students)) {
                    serverStudents = data.students.map(s => ({
                        id: s.id,
                        name: s.name,
                        email: s.email,
                        "class": Array.isArray(s.classes) ? (s.classes[0] || '') : (s.class || ''),
                        classes: Array.isArray(s.classes) ? s.classes : toClassList(s.class),
                        level: s.level,
                        wpm: s.wpm || '0',
                        accuracy: s.accuracy || '0',
                        pabasa_id: s.custom_id,
                        custom_id: s.custom_id,
                        isServer: true
                    }));
                }
            } else {
                const bodyText = response ? await response.text() : '';
                console.error('PABASA: Failed to fetch students from server (status ' + (response && response.status) + ')', bodyText);
            }
        } catch (e) {
            console.error('PABASA: Failed to fetch students from server', e);
        }

        // 2. Load Local Students (Legacy/Manual)
        let students = JSON.parse(localStorage.getItem("pabasa_added_students") || "[]");
        
        // Combine server and local, prioritizing server data for duplicate IDs/Emails
        const allStudents = [...serverStudents, ...students];

        // Group students to aggregate multiple classes into one row per student.
        let consolidated = [];
        const studentIndex = new Map();
        allStudents.forEach(s => {
            const keys = s ? getStudentKeys(s) : [];
            if (keys.length === 0) return;

            const found = keys.map(key => studentIndex.get(key)).find(Boolean);
            if (found) {
                const existingClasses = found.allClasses;
                if (s.isServer && !found.isServer) {
                    Object.assign(found, s);
                    found.allClasses = existingClasses;
                    found.isServer = true;
                }
                addUniqueClasses(found, collectClassNames(s));
                found.email = found.email || s.email || "";
                found.pabasa_id = found.pabasa_id || s.pabasa_id || s.custom_id || "";
                found.custom_id = found.custom_id || s.custom_id || s.pabasa_id || "";
                getStudentKeys(found).forEach(key => studentIndex.set(key, found));
            } else {
                const student = { ...s, allClasses: [] };
                addUniqueClasses(student, collectClassNames(s));
                consolidated.push(student);
                getStudentKeys(student).forEach(key => studentIndex.set(key, student));
            }
        });

        // Apply Percentile Ranking before rendering directory
        // Sort by Accuracy Descending (Highest score = Top)
        // Separate students with numeric accuracy from those without (pending)
        const withScore = consolidated.filter(s => !isNaN(parseFloat(s.accuracy)));
        const pending = consolidated.filter(s => isNaN(parseFloat(s.accuracy)));

        withScore.sort((a, b) => (parseFloat(b.accuracy) || 0) - (parseFloat(a.accuracy) || 0));
        const totalC = withScore.length;

        // Assign percentile-based levels to students with scores
        withScore.forEach((item, idx) => {
            const pos = ((totalC - idx) / Math.max(1, totalC)) * 100;
            if (pos <= 20) item.level = "Low Emerging Readers";
            else if (pos <= 40) item.level = "High Emerging Readers";
            else if (pos <= 60) item.level = "Developing Readers";
            else if (pos <= 80) item.level = "Transitioning Readers";
            else item.level = "Readers at Grade Level";
        });

        // Mark pending students clearly
        pending.forEach(s => s.level = "Pending");

        // Reconstruct consolidated preserving scored first then pending
        consolidated = withScore.concat(pending);

        if (studentDirectory) {
            const emptyState = studentDirectory.querySelector(".student-empty-state");

            consolidated.forEach(studentData => {
                const levelClass = getLevelClass(studentData.level);
                const initials = studentData.name
                    .split(" ")
                    .map(n => n.charAt(0).toUpperCase())
                    .join("")
                    .substring(0, 2);
                
                const studentCard = document.createElement("div");
                studentCard.className = "student-card-row";
                studentCard.setAttribute("data-student-name", studentData.name);
                studentCard.setAttribute("data-reading-level", studentData.level);
                const classDisplay = studentData.allClasses.join(", ");
                studentCard.setAttribute("data-class-name", classDisplay);
                
                studentCard.innerHTML = `
                    <span class="student-avatar">${initials}</span>
                    <div class="student-row-main">
                        <div class="student-name-line">
                            <strong>${studentData.name}</strong>
                            <span class="small text-muted">${studentData.email || ''}</span>
                            <span class="level-chip ${levelClass}">${studentData.level}</span>
                        </div>
                        <div class="student-meta">
                            <div class="student-meta-box"><span>Joined Classes</span><strong>${classDisplay}</strong></div>
                            <div class="student-meta-box"><span>WPM</span><strong>${studentData.wpm}</strong></div>
                            <div class="student-meta-box"><span>Accuracy</span><strong>${studentData.accuracy}%</strong></div>
                        </div>
                        <div class="reading-band mt-2"><span style="width: ${studentData.wpm}%;"></span></div>
                    </div>
                `;
                
                if (emptyState) {
                    studentDirectory.insertBefore(studentCard, emptyState);
                } else {
                    studentDirectory.appendChild(studentCard);
                }
            });
        }
        
        // 3. Populate the "Update & Report" Modal Student List
        if (modalStudentList) {
            if (consolidated.length === 0) {
                modalStudentList.innerHTML = '<div class="text-center text-muted py-3 small">No students found for this class.</div>';
            } else {
                modalStudentList.innerHTML = consolidated.map(s => `
                <div class="form-check mb-2">
                    <input class="form-check-input student-report-checkbox" type="checkbox" value="${s.email}" id="chk_${s.pabasa_id || s.id}">
                    <label class="form-check-label d-flex justify-content-between w-100" for="chk_${s.pabasa_id || s.id}">
                        <span>${s.name}</span>
                        <span class="badge bg-light text-dark border">${s.level}</span>
                    </label>
                </div>
            `).join('');
            }
        }

        // Re-run filter to ensure proper visibility
        filterStudents();
    }

    // Load on start
    renderStudentDirectory();
    window.refreshStudentDirectory = renderStudentDirectory;

    // Parent Update Modal - Student Selection Logic
    (function() {
        const parentUpdateGroupType = document.getElementById("parentUpdateGroupType");
        const studentListSection = document.getElementById("studentListSection");
        const selectAllBtn = document.getElementById("selectAllStudents");
        
        if (!parentUpdateGroupType || !studentListSection) return;

        function showHideStudents() {
            if (parentUpdateGroupType.value === "custom") {
                studentListSection.style.display = "block";
                // Refresh the list to ensure it's up to date
                if (window.refreshStudentDirectory) window.refreshStudentDirectory();
            } else {
                studentListSection.style.display = "none";
            }
        }

        // Select/Deselect All Logic
        if (selectAllBtn) {
            selectAllBtn.addEventListener("click", function() {
                const checkboxes = studentListSection.querySelectorAll(".student-report-checkbox");
                const anyUnchecked = Array.from(checkboxes).some(cb => !cb.checked);
                
                checkboxes.forEach(cb => cb.checked = anyUnchecked);
                this.textContent = anyUnchecked ? "Deselect All" : "Select All";
            });
        }

        // Change event listener
        parentUpdateGroupType.addEventListener("change", showHideStudents);
        
        // Reset "Select All" text when modal opens
        const modal = document.getElementById("parentUpdateModal");
        if (modal && selectAllBtn) {
            modal.addEventListener("show.bs.modal", () => selectAllBtn.textContent = "Select All");
        }

        // Also trigger on modal open
        if (modal) {
            modal.addEventListener("show.bs.modal", showHideStudents);
        }

        // Initial state
        showHideStudents();
    })();

    // Add Student Form Handler
    (function() {
        const addStudentForm = document.getElementById("addStudentForm");
        const addStudentModal = document.getElementById("addStudentModal");
        
        if (!addStudentForm || !addStudentModal) {
            return;
        }

        addStudentForm.addEventListener("submit", function(e) {
            e.preventDefault();
            
            // Get form values (guard against missing elements)
            const firstName = document.getElementById("studentFirstName")?.value.trim() || "";
            const middleInitial = document.getElementById("studentMiddleInitial")?.value.trim() || "";
            const lastName = document.getElementById("studentLastName")?.value.trim() || "";
            const suffix = document.getElementById("studentSuffix")?.value || "";
            const studentName = [firstName, middleInitial ? `${middleInitial}.` : "", lastName, suffix].filter(Boolean).join(" ");
            const studentClass = document.getElementById("studentClass")?.value || "";
            const readingLevel = document.getElementById("studentReadingLevel")?.value || "";
            const wpm = document.getElementById("studentWPM")?.value || "0";
            const accuracy = document.getElementById("studentAccuracy")?.value || "0";
            const studentEmail = document.getElementById("parentContact")?.value || "";
            
            // Create student data object
            const studentData = {
                name: studentName,
                class: studentClass,
                level: readingLevel,
                wpm: wpm,
                accuracy: accuracy,
                email: studentEmail,
                id: Date.now() // Simple unique ID
            };
            
            // Save to localStorage
            let students = JSON.parse(localStorage.getItem("pabasa_added_students") || "[]");
            students.push(studentData);
            localStorage.setItem("pabasa_added_students", JSON.stringify(students));
            
            // Refresh the directory list to handle consolidation
            renderStudentDirectory();
            
            addStudentForm.reset();
            const bsModal = bootstrap.Modal.getInstance(addStudentModal);
            if (bsModal) bsModal.hide();
            
            // Show success message
            showSuccessMessage(`${studentName} has been added to the student directory.`);
            
            // Re-filter students to show the new one
            filterStudents();
            
            // Dispatch custom event for cross-page updates
            window.dispatchEvent(new CustomEvent('studentAdded', { detail: studentData }));
        });
    })();

    function getLevelClass(level) {
        const levelMap = {
            "Low Emerging Readers": "level-low",
            "High Emerging Readers": "level-high",
            "Developing Readers": "level-developing",
            "Transitioning Readers": "level-transitioning",
            "Readers at Grade Level": "level-grade",
            "Pending": "level-pending"
        };
        return levelMap[level] || "level-high";
    }

    function showSuccessMessage(message) {
        const alertDiv = document.createElement("div");
        alertDiv.className = "alert alert-success alert-dismissible fade show";
        alertDiv.setAttribute("role", "alert");
        alertDiv.style.position = "fixed";
        alertDiv.style.top = "80px";
        alertDiv.style.right = "20px";
        alertDiv.style.zIndex = "9999";
        alertDiv.style.minWidth = "300px";
        alertDiv.innerHTML = `
            <i class="bi bi-check-circle me-2"></i>${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
        `;
        document.body.appendChild(alertDiv);
        
        // Auto dismiss after 4 seconds
        setTimeout(() => {
            if (alertDiv.parentNode) {
                alertDiv.remove();
            }
        }, 4000);
    }

    if (!assignSectionModal || !studentNameInput || !currentSectionInput) {
        return;
    }

    assignSectionModal.addEventListener("show.bs.modal", function (event) {
        const trigger = event.relatedTarget;
        if (!trigger) {
            return;
        }

        const studentName = trigger.getAttribute("data-student-name") || "";
        const currentSection = trigger.getAttribute("data-current-section") || "";

        studentNameInput.value = studentName;
        currentSectionInput.value = currentSection;
    });

    if (!changeStatusModal || !changeStatusStudentName || !changeStatusCurrent) {
        return;
    }

    changeStatusModal.addEventListener("show.bs.modal", function (event) {
        const trigger = event.relatedTarget;
        if (!trigger) {
            return;
        }

        const studentName = trigger.getAttribute("data-student-name") || "";
        const currentStatus = trigger.getAttribute("data-current-status") || "";

        changeStatusStudentName.value = studentName;
        changeStatusCurrent.value = currentStatus;
    });
}

if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initStudentsPage);
} else {
    initStudentsPage();
}
})();
