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

    function renderStudentDirectory() {
        const studentDirectory = document.querySelector(".student-directory");
        if (!studentDirectory) return;
        
        // Clear current rows to re-render consolidated list
        studentDirectory.querySelectorAll(".student-card-row").forEach(row => row.remove());
        
        let students = JSON.parse(localStorage.getItem("pabasa_added_students") || "[]");
        const filteredStudents = students.filter(student => student.name !== "Jay Park");
        if (filteredStudents.length !== students.length) {
            localStorage.setItem("pabasa_added_students", JSON.stringify(filteredStudents));
            students = filteredStudents;
        }

        // Group students to aggregate multiple classes
        const consolidated = [];
        students.forEach(s => {
            const found = consolidated.find(c => {
                const namesMatch = c.name.toLowerCase().trim() === s.name.toLowerCase().trim();
                const emailsConflict = c.email && s.email && c.email.toLowerCase().trim() !== s.email.toLowerCase().trim();
                return namesMatch && !emailsConflict;
            });
            if (found) {
                if (s.class && !found.allClasses.includes(s.class)) {
                    found.allClasses.push(s.class);
                }
            } else {
                consolidated.push({ ...s, allClasses: s.class ? [s.class] : [] });
            }
        });

        // Apply Percentile Ranking before rendering directory
        // Sort by Accuracy Descending (Highest score = Top)
        consolidated.sort((a, b) => (parseInt(b.accuracy) || 0) - (parseInt(a.accuracy) || 0));
        const totalC = consolidated.length;
        
        consolidated.forEach((student, index) => {
            const pos = ((totalC - index) / totalC) * 100;
            if (pos <= 20) student.level = "Low Emerging Readers";
            else if (pos <= 40) student.level = "High Emerging Readers";
            else if (pos <= 60) student.level = "Developing Readers";
            else if (pos <= 80) student.level = "Transitioning Readers";
            else student.level = "Readers at Grade Level";
        });

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
        
        if (!parentUpdateGroupType || !studentListSection) {
            console.warn("Parent update modal elements not found");
            return;
        }

        function showHideStudents() {
            console.log("Current value:", parentUpdateGroupType.value);
            if (parentUpdateGroupType.value === "custom") {
                studentListSection.style.display = "block";
                console.log("Showing students");
            } else {
                studentListSection.style.display = "none";
                console.log("Hiding students");
            }
        }

        // Change event listener
        parentUpdateGroupType.addEventListener("change", showHideStudents);

        // Also trigger on modal open
        const modal = document.getElementById("parentUpdateModal");
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
            
            // Get form values
            const studentName = document.getElementById("studentName").value;
            const studentClass = document.getElementById("studentClass").value;
            const readingLevel = document.getElementById("studentReadingLevel").value;
            const wpm = document.getElementById("studentWPM").value || "0";
            const accuracy = document.getElementById("studentAccuracy").value || "0";
            const studentEmail = document.getElementById("parentContact").value;
            
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
            "Readers at Grade Level": "level-grade"
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
