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

    // Load previously added students from localStorage
    (function() {
        const studentDirectory = document.querySelector(".student-directory");
        if (!studentDirectory) return;
        
        const students = JSON.parse(localStorage.getItem("pabasa_added_students") || "[]");
        const emptyState = studentDirectory.querySelector(".student-empty-state");
        
        students.forEach(studentData => {
            // Check if student already exists in the directory
            const exists = Array.from(studentDirectory.querySelectorAll(".student-card-row")).some(
                card => card.getAttribute("data-student-name") === studentData.name
            );
            
            if (exists) return; // Skip if already in the DOM
            
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
            studentCard.setAttribute("data-class-name", studentData.class);
            
            studentCard.innerHTML = `
                <span class="student-avatar">${initials}</span>
                <div class="student-row-main">
                    <div class="student-name-line">
                        <strong>${studentData.name}</strong>
                        <span class="level-chip ${levelClass}">${studentData.level}</span>
                    </div>
                    <div class="student-meta">
                        <div class="student-meta-box"><span>Class</span><strong>${studentData.class}</strong></div>
                        <div class="student-meta-box"><span>WPM</span><strong>${studentData.wpm}</strong></div>
                        <div class="student-meta-box"><span>Accuracy</span><strong>${studentData.accuracy}%</strong></div>
                    </div>
                    <div class="reading-band mt-2"><span style="width: ${studentData.wpm}%;"></span></div>
                </div>
                <div class="student-row-actions">
                    <a class="btn btn-outline-primary btn-sm d-flex justify-content-center align-items-center" href="#">View</a>
                    <button class="btn btn-light border btn-sm" type="button" data-bs-toggle="modal" data-bs-target="#progressReportModal">Report</button>
                    <button class="btn btn-light border btn-sm" type="button" data-bs-toggle="modal" data-bs-target="#parentUpdateModal">Update</button>
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
    })();

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
            const parentContact = document.getElementById("parentContact").value;
            
            // Create student data object
            const studentData = {
                name: studentName,
                class: studentClass,
                level: readingLevel,
                wpm: wpm,
                accuracy: accuracy,
                contact: parentContact,
                id: Date.now() // Simple unique ID
            };
            
            // Save to localStorage
            let students = JSON.parse(localStorage.getItem("pabasa_added_students") || "[]");
            students.push(studentData);
            localStorage.setItem("pabasa_added_students", JSON.stringify(students));
            
            // Create student avatar initials
            const initials = studentName
                .split(" ")
                .map(n => n.charAt(0).toUpperCase())
                .join("")
                .substring(0, 2);
            
            // Determine level chip class
            const levelClass = getLevelClass(readingLevel);
            
            // Create new student card HTML
            const newStudentCard = document.createElement("div");
            newStudentCard.className = "student-card-row";
            newStudentCard.setAttribute("data-student-name", studentName);
            newStudentCard.setAttribute("data-reading-level", readingLevel);
            newStudentCard.setAttribute("data-class-name", studentClass);
            
            newStudentCard.innerHTML = `
                <span class="student-avatar">${initials}</span>
                <div class="student-row-main">
                    <div class="student-name-line">
                        <strong>${studentName}</strong>
                        <span class="level-chip ${levelClass}">${readingLevel}</span>
                    </div>
                    <div class="student-meta">
                        <div class="student-meta-box"><span>Class</span><strong>${studentClass}</strong></div>
                        <div class="student-meta-box"><span>WPM</span><strong>${wpm}</strong></div>
                        <div class="student-meta-box"><span>Accuracy</span><strong>${accuracy}%</strong></div>
                    </div>
                    <div class="reading-band mt-2"><span style="width: ${wpm}%;"></span></div>
                </div>
                <div class="student-row-actions">
                    <a class="btn btn-outline-primary btn-sm d-flex justify-content-center align-items-center" href="#">View</a>
                    <button class="btn btn-light border btn-sm" type="button" data-bs-toggle="modal" data-bs-target="#progressReportModal">Report</button>
                    <button class="btn btn-light border btn-sm" type="button" data-bs-toggle="modal" data-bs-target="#parentUpdateModal">Update</button>
                </div>
            `;
            
            // Add to student directory if it exists (students.html page)
            const studentDirectory = document.querySelector(".student-directory");
            if (studentDirectory) {
                const emptyState = studentDirectory.querySelector(".student-empty-state");
                if (emptyState) {
                    studentDirectory.insertBefore(newStudentCard, emptyState);
                } else {
                    studentDirectory.appendChild(newStudentCard);
                }
            }
            
            // Reset form and close modal
            addStudentForm.reset();
            const bsModal = bootstrap.Modal.getInstance(addStudentModal) || new bootstrap.Modal(addStudentModal);
            bsModal.hide();
            
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
