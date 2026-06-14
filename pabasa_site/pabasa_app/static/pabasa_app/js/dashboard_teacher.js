(function () {
    document.addEventListener('DOMContentLoaded', function () {
        const createClassForm = document.getElementById("createClassForm");
        const titleInput = document.getElementById("titleInput");
        const subjectInput = document.getElementById("subjectInput");
        const classDescriptionInput = document.getElementById("classDescriptionInput");
        const generatedClassCode = document.getElementById("generatedClassCode"); // This is for the create class form, not the stat card
        const regenerateCodeBtn = document.getElementById("regenerateCodeBtn");
        const classList = document.getElementById("classList");
        const classCountMirror = document.getElementById("classCountMirror"); // Renamed from classCount to target the 'Class' stat card
        const copyClassCodeBtn = document.getElementById("copyClassCodeBtn");
        const manageClassLink = document.getElementById("manageClassLink");
        const sidebarClassLink = document.getElementById("sidebarClassLink");

        const activeClassName = document.getElementById("activeClassName");
        const activeClassSubject = document.getElementById("activeClassSubject");
        const activeClassDescription = document.getElementById("activeClassDescription");
        const activeClassCode = document.getElementById("activeClassCode");
        const activeStudentCount = document.getElementById("activeStudentCount");
        const classBanner = document.getElementById("classBanner");

        if (!createClassForm || !classList || !generatedClassCode) {
            return;
        }

        const teacherEmail = (window.PABASA_USER_EMAIL || localStorage.getItem("pabasaUserEmail") || '').trim();
        const scopedKey = teacherEmail ? `pabasa_teacher_classes_${teacherEmail}` : null;

        function makeClassCode() {
            const letters = "ABCDEFGHJKLMNPQRSTUVWXYZ";
            let prefix = "";
            for (let i = 0; i < 4; i += 1) {
                prefix += letters[Math.floor(Math.random() * letters.length)];
            }
            const number = String(Math.floor(Math.random() * 1000)).padStart(3, "0");
            return prefix + "-" + number;
        }

        function setGeneratedCode() {
            if (generatedClassCode) {
                generatedClassCode.textContent = makeClassCode();
            }
        }

        function updateClassCount() {
            if (classCountMirror && classList) {
                classCountMirror.textContent = String(classList.querySelectorAll('.class-card').length);
            }
        }

        // Remove students from localStorage whose class no longer exists
        function cleanupLocalStudents(activeClasses) {
            try {
                const classNames = new Set((activeClasses || []).map(c => (c.name || '').toString()));
                const students = JSON.parse(localStorage.getItem('pabasa_added_students') || '[]');
                const filtered = students.filter(s => {
                    // keep students without a class
                    if (!s.class) return true;
                    // keep students whose class still exists
                    if (classNames.has(s.class)) return true;
                    // otherwise drop (stale)
                    return false;
                });
                if (filtered.length !== students.length) {
                    localStorage.setItem('pabasa_added_students', JSON.stringify(filtered));
                    console.info('Cleaned up', students.length - filtered.length, 'stale student entries from localStorage');
                }
            } catch (e) {
                console.warn('Failed to cleanup local students', e);
            }
        }

        function loadSavedClasses() {
            localStorage.removeItem('pabasa_teacher_classes');

            Object.keys(localStorage).forEach(function (key) {
                if (
                    key.startsWith('pabasa_teacher_classes_') &&
                    key !== `pabasa_teacher_classes_${teacherEmail}`
                ) {
                    localStorage.removeItem(key);
                }
            });

            fetch('/dashboard/teacher/classes/', {
                method: 'GET',
                headers: { 'X-Requested-With': 'XMLHttpRequest' }
            })
            .then(response => response.json())
            .then(data => {
                if (!data.success) {
                    console.error('Failed to load classes:', data.error);
                    return;
                }

                if (scopedKey) {
                    localStorage.setItem(scopedKey, JSON.stringify(data.classes));
                }

                // Remove any students in localStorage that belong to classes no longer returned by the server
                try {
                    cleanupLocalStudents(data.classes);
                } catch (e) {
                    console.warn('Error running cleanupLocalStudents', e);
                }

                classList.innerHTML = '';

                data.classes.forEach(function (classData) {
                    const classTeacherEmail = classData.teacher_email || '';

                    if (teacherEmail && classTeacherEmail && classTeacherEmail !== teacherEmail) {
                        return;
                    }

                    const card = createClassCard(
                        classData.name,
                        classData.header || 'READ',
                        classData.description || '',
                        classData.code,
                        classData.subject || '',
                        classData.students || '0', // Use accurate count from server
                        classTeacherEmail
                    );

                    classList.appendChild(card);
                });

                // Update total class count stat
                if (classCountMirror) {
                    classCountMirror.textContent = String(data.classes.length);
                }

                const firstCard = classList.querySelector('.class-card');
                if (firstCard && activeClassName) {
                    selectClass(firstCard);
                }
            })
            .catch(function (error) {
                console.error('Error loading classes:', error);
            });
        }

        function selectClass(card) {
            // Defensive check for pages that list classes but don't have an "Active Class" detail area
            if (!activeClassName) return;

            classList.querySelectorAll(".class-card").forEach(function (item) {
                item.classList.toggle("is-active", item === card);
            });

            const name = card.getAttribute("data-class-name") || "Reading Class";
            const subject = card.getAttribute("data-subject") || "Reading";
            const code = card.getAttribute("data-code") || "READ-000";
            const header = card.getAttribute("data-header") || "READ";
            const description = card.getAttribute("data-description") || "Class reading workspace.";
            const actualStudentCount = card.getAttribute("data-students") || "0";

            activeClassName.textContent = name;
            activeClassSubject.textContent = subject;
            activeClassDescription.textContent = description;
            activeClassCode.textContent = code;
            activeStudentCount.textContent = actualStudentCount;
            if (classBanner) classBanner.setAttribute("data-header", header);
            if (generatedClassCode) generatedClassCode.textContent = code;

            if (copyClassCodeBtn) {
                copyClassCodeBtn.style.display = "block";
            }

            // Update all "Manage Class" or "Class" buttons in the dashboard and workspace card
            const classManagementUrls = document.querySelectorAll('#manageClassLink, .workspace-card .btn-class, [data-manage-class-btn]');
            classManagementUrls.forEach(link => {
                if (link.tagName === 'A') {
                    link.href = `/dashboard/teacher/manage/?code=${code}`;
                    link.style.display = "inline-flex";
                }
            });

            // Persist the active class so the sidebar stays updated on other pages
            localStorage.setItem("pabasa_last_active_class_code", code);
            window.dispatchEvent(new Event("pabasa:teacher-class-selected"));

            // Refresh student directory to show students for the selected class (if present)
            try {
                if (typeof loadPersistedStudents === 'function') {
                    loadPersistedStudents();
                } else if (window.refreshStudentDirectory) {
                    window.refreshStudentDirectory();
                }
            } catch (e) {
                console.warn('Could not refresh student directory after class select', e);
            }
        }

        function createClassCard(name, header, description, code, subject, students, teacherEmailArg) {
            const card = document.createElement("div");
            card.className = "class-card";
            card.setAttribute("data-class-name", name);
            card.setAttribute("data-subject", subject || name);
            card.setAttribute("data-code", code);
            card.setAttribute("data-header", header);
            card.setAttribute("data-description", description);

            const email = teacherEmailArg || window.PABASA_USER_EMAIL || localStorage.getItem("pabasaUserEmail") || "";
            card.setAttribute("data-teacher-email", email);

            card.setAttribute("data-students", students);

            const head = document.createElement("span");
            head.className = "class-card-head";

            const title = document.createElement("strong");
            title.textContent = name;

            const codePill = document.createElement("span");
            codePill.className = "class-code-pill";
            codePill.textContent = code;

            const deleteBtn = document.createElement("button");
            deleteBtn.className = "class-card-delete";
            deleteBtn.type = "button";
            deleteBtn.title = "Delete class";
            deleteBtn.innerHTML = '<i class="bi bi-trash3"></i>';
            deleteBtn.setAttribute("data-class-code", code);
            deleteBtn.setAttribute("data-class-name", name);
            deleteBtn.addEventListener("click", function(e) {
                e.preventDefault();
                e.stopPropagation();
                showDeleteClassConfirmation(code, name);
            });

            const meta = document.createElement("span");
            meta.className = "small text-secondary";
            meta.textContent = (subject || name) + " • " + students + " students";

            head.appendChild(title);
            head.appendChild(codePill);
            head.appendChild(deleteBtn);
            card.appendChild(head);
            card.appendChild(meta);

            return card;
        }

        classList.addEventListener("click", function (event) {
            const card = event.target.closest(".class-card");
            if (card) {
                selectClass(card);
            }
        });

        if (createClassForm) {
        createClassForm.addEventListener("submit", function (event) {
            event.preventDefault();

            const title = titleInput.value.trim();
            const subject = subjectInput.value;

            if (!title || !subject) {
                alert("Please provide a Title and select a Subject.");
                return;
            }

            const description = classDescriptionInput.value.trim() || "Reading class workspace.";
            const name = title;

            fetch('/dashboard/teacher/create-class/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': document.querySelector("[name=csrfmiddlewaretoken]")?.value || ""
                },
                body: JSON.stringify({
                    class_name: name,
                    subject: subject,
                    description: description
                })
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    const currentTeacherEmail = window.PABASA_USER_EMAIL || localStorage.getItem("pabasaUserEmail") || "";
                    const description = classDescriptionInput.value.trim() || "Reading class workspace.";
                    
                    // Update the dashboard UI in the background
                    const card = createClassCard(
                        data.class_name,
                        "READ",
                        description,
                        data.class_code,
                        subject,
                        "0",
                        currentTeacherEmail
                    );
                    classList.prepend(card);
                    selectClass(card);
                    updateClassCount();

                    // Apply refined styling to the success popup content
                    const nameDisplay = document.getElementById("createdClassName");
                    if (nameDisplay) {
                        nameDisplay.textContent = data.class_name;
                        nameDisplay.style.color = '#64748b';
                        nameDisplay.style.fontWeight = '600';
                        nameDisplay.style.fontSize = '1.25rem';
                    }
                    
                    const codeDisplay = document.getElementById("createdClassCode");
                    if (codeDisplay) {
                        codeDisplay.textContent = data.class_code;
                        codeDisplay.style.letterSpacing = '8px';
                        codeDisplay.style.fontFamily = "'JetBrains Mono', monospace";
                        codeDisplay.style.fontSize = '3.5rem';
                        codeDisplay.style.fontWeight = '800';
                        codeDisplay.style.color = '#1e293b';
                        codeDisplay.style.background = '#f8fafc';
                        codeDisplay.style.padding = '30px 45px';
                        codeDisplay.style.borderRadius = '24px';
                        codeDisplay.style.display = 'inline-block';
                        codeDisplay.style.margin = '25px 0';
                        codeDisplay.style.border = '2px solid #e2e8f0';
                        codeDisplay.style.boxShadow = '0 4px 6px -1px rgba(0, 0, 0, 0.1)';
                    }

                    // Handle modal transition reliably
                    const createModalEl = document.getElementById("createClassModal");
                    const successModalEl = document.getElementById("classCreatedModal");

                    if (createModalEl && successModalEl) {
                        console.log("PABASA: Class created, transitioning modals...");
                        const createModal = bootstrap.Modal.getOrCreateInstance(createModalEl);
                        const successModal = bootstrap.Modal.getOrCreateInstance(successModalEl, { 
                            backdrop: 'static', 
                            keyboard: true 
                        });

                        if (createModalEl.classList.contains('show')) {
                            createModalEl.addEventListener('hidden.bs.modal', function () {
                                // Force removal of any lingering backdrops before showing the next modal
                                document.querySelectorAll('.modal-backdrop').forEach(b => b.remove());
                                successModal.show();
                            }, { once: true });
                            createModal.hide();
                        } else {
                            successModal.show();
                        }
                    }

                    const currentScopedKey = `pabasa_teacher_classes_${currentTeacherEmail}`;
                    const existing = JSON.parse(localStorage.getItem(currentScopedKey) || '[]');
                    existing.unshift({
                        code: data.class_code,
                        name: data.class_name,
                        subject: subject,
                        grade_level: 'N/A',
                        section: 'N/A',
                        description: description,
                        header: 'READ',
                        students: '0',
                        teacher_email: currentTeacherEmail,
                    });
                    localStorage.setItem(currentScopedKey, JSON.stringify(existing));

                    createClassForm.reset();

                } else {
                    alert("Creation failed: " + data.error);
                }
            })
            .catch(error => {
                console.error("Error creating classroom:", error);
                alert("An error occurred while creating the classroom.");
            });
        });
        }

        if (regenerateCodeBtn) {
            regenerateCodeBtn.addEventListener("click", setGeneratedCode);
        }

        if (copyClassCodeBtn) {
            copyClassCodeBtn.addEventListener("click", function () {
                const code = activeClassCode.textContent.trim();
                if (navigator.clipboard && code) {
                    navigator.clipboard.writeText(code);
                }
                copyClassCodeBtn.innerHTML = '<i class="bi bi-check2 me-1"></i>Copied';
                window.setTimeout(function () {
                    copyClassCodeBtn.innerHTML = '<i class="bi bi-copy me-1"></i>Copy Code';
                }, 1400);
            });
        }

        // Load and display persisted students from localStorage
        (function () {
            const studentRow = document.querySelector(".student-row");
            if (!studentRow) return;

            let students = JSON.parse(localStorage.getItem("pabasa_added_students") || "[]");

            const filteredStudents = students.filter(student => student.name !== "Jay Park");
            if (filteredStudents.length !== students.length) {
                localStorage.setItem("pabasa_added_students", JSON.stringify(filteredStudents));
                students = filteredStudents;
            }

            students.forEach(studentData => {
                const exists = Array.from(studentRow.querySelectorAll(".student-card"))
                    .some(card => card.textContent.includes(studentData.name));
                if (exists) return;

                const levelClass = {
                    "Low Emerging Readers": "level-low",
                    "High Emerging Readers": "level-high",
                    "Developing Readers": "level-developing",
                    "Transitioning Readers": "level-transitioning",
                    "Readers at Grade Level": "level-grade"
                }[studentData.level] || "level-high";

                const initials = studentData.name
                    .split(" ")
                    .map(n => n.charAt(0).toUpperCase())
                    .join("")
                    .substring(0, 2);

                const studentCard = document.createElement("div");
                studentCard.className = "student-card";
                studentCard.innerHTML = `
                    <span class="student-avatar">${initials}</span>
                    <div>
                        <strong>${studentData.name}</strong>
                        <div class="small text-secondary">
                            WPM ${studentData.wpm} • ${studentData.accuracy}%
                        </div>
                    </div>
                    <span class="level-chip ${levelClass}">
                        ${studentData.level}
                    </span>
                `;
                studentRow.appendChild(studentCard);
            });
        })();

        // Success modal cleanup
        const classCreatedModalEl = document.getElementById("classCreatedModal");
        if (classCreatedModalEl) {
            classCreatedModalEl.addEventListener("hidden.bs.modal", function () {
                document.querySelectorAll(".modal-backdrop").forEach(el => el.remove());
                document.body.classList.remove("modal-open");
                document.body.style.overflow = "";
                document.body.style.paddingRight = "";
                
                // Trigger page refresh to update all dashboard stats and sidebar links
                window.location.reload();
            });
        }

        // Copy code button
        const copyCreatedBtn = document.getElementById("copyCreatedClassCode");
        if (copyCreatedBtn) {
            copyCreatedBtn.addEventListener("click", function () {
                const codeEl = document.getElementById("createdClassCode");
                const code = codeEl ? codeEl.textContent : "";
                if (navigator.clipboard && code) {
                    navigator.clipboard.writeText(code).then(() => {
                        const btn = this;
                        const originalHTML = btn.innerHTML;
                        
                        btn.innerHTML = '<i class="bi bi-check-circle-fill me-2"></i>Copied!';
                        btn.classList.replace('btn-primary', 'btn-success');
                        btn.style.transform = 'translateY(-2px)';
                        btn.style.transition = 'all 0.2s cubic-bezier(0.175, 0.885, 0.32, 1.275)';
                        btn.style.boxShadow = '0 10px 15px -3px rgba(22, 163, 74, 0.3)';
                        
                        if (codeEl) {
                            codeEl.style.color = '#15803d';
                            codeEl.style.borderColor = '#22c55e';
                            codeEl.style.transition = 'all 0.2s ease';
                        }
                        
                        setTimeout(() => {
                            btn.innerHTML = originalHTML;
                            btn.classList.replace('btn-success', 'btn-primary');
                            btn.style.transform = '';
                            btn.style.boxShadow = '';
                            if (codeEl) {
                                codeEl.style.color = '#1e293b';
                                codeEl.style.borderColor = '#94a3b8';
                            }
                        }, 2000);
                    }).catch(() => {
                        alert('Failed to copy. Please try again.');
                    });
                }
            });
        }

        // Toast notification function
        function showToast(message, type = 'info') {
            const toastContainer = document.getElementById('toastContainer') || (() => {
                const container = document.createElement('div');
                container.id = 'toastContainer';
                container.style.cssText = 'position: fixed; top: 20px; right: 20px; z-index: 9999; max-width: 400px;';
                document.body.appendChild(container);
                return container;
            })();

            const toastId = 'toast-' + Date.now();
            const bgColor = type === 'success' ? 'bg-success' : type === 'error' ? 'bg-danger' : 'bg-info';
            
            const toastHTML = `
                <div class="toast align-items-center text-white ${bgColor} border-0" role="alert" aria-live="assertive" aria-atomic="true" id="${toastId}">
                    <div class="d-flex">
                        <div class="toast-body">
                            ${message}
                        </div>
                        <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast" aria-label="Close"></button>
                    </div>
                </div>
            `;
            
            const toastElement = document.createElement('div');
            toastElement.innerHTML = toastHTML;
            toastContainer.appendChild(toastElement.firstElementChild);
            
            const toast = new bootstrap.Toast(document.getElementById(toastId));
            toast.show();
            
            setTimeout(() => {
                document.getElementById(toastId)?.remove();
            }, 5000);
        }

        // Delete class functionality
        let classToDeleteCode = null;
        let classToDeleteName = null;

        function showDeleteClassConfirmation(classCode, className) {
            classToDeleteCode = classCode;
            classToDeleteName = className;
            const deleteClassNameDisplay = document.getElementById("deleteClassNameDisplay");
            if (deleteClassNameDisplay) {
                deleteClassNameDisplay.textContent = className;
            }
            const deleteModal = new bootstrap.Modal(document.getElementById("deleteClassModal"));
            deleteModal.show();
        }

        function deleteTeacherClass(classCode) {
            // Call backend to delete the class
            fetch('/dashboard/teacher/delete-class/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': document.querySelector("[name=csrfmiddlewaretoken]")?.value || ""
                },
                body: JSON.stringify({ class_code: classCode })
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    // Remove from classList DOM
                    const cardToRemove = classList.querySelector(`[data-code="${classCode}"]`);
                    if (cardToRemove) {
                        cardToRemove.remove();
                    }
                    
                    // Update localStorage for classes
                    const _email = (window.PABASA_USER_EMAIL || localStorage.getItem("pabasaUserEmail") || '').trim();
                    if (_email && scopedKey) {
                        const existing = JSON.parse(localStorage.getItem(scopedKey) || '[]');
                        const updated = existing.filter(cls => cls.code !== classCode);
                        localStorage.setItem(scopedKey, JSON.stringify(updated));
                    }

                    // Remove students associated with this class from localStorage
                    try {
                        const studentsRaw = JSON.parse(localStorage.getItem('pabasa_added_students') || '[]');
                        const filteredStudents = studentsRaw.filter(s => (s.class || '') !== classToDeleteName);
                        if (filteredStudents.length !== studentsRaw.length) {
                            localStorage.setItem('pabasa_added_students', JSON.stringify(filteredStudents));
                        }
                    } catch (e) {
                        console.warn('Could not update pabasa_added_students after class delete', e);
                    }

                    // Remove class readings/materials from localStorage
                    try {
                        const readings = JSON.parse(localStorage.getItem('pabasa_class_readings') || '{}');
                        if (readings && readings[classCode]) {
                            delete readings[classCode];
                            localStorage.setItem('pabasa_class_readings', JSON.stringify(readings));
                        }

                        // Also update flattened materials list if present
                        const flat = JSON.parse(localStorage.getItem('pabasa_materials') || '[]');
                        const filteredFlat = flat.filter(m => (m.classCode || '') !== classCode);
                        if (filteredFlat.length !== flat.length) {
                            localStorage.setItem('pabasa_materials', JSON.stringify(filteredFlat));
                        }
                    } catch (e) {
                        console.warn('Could not update class readings/materials after class delete', e);
                    }
                    
                    // Update counts
                    updateClassCount();
                    
                    // Clear active class if it's the one being deleted
                    if (activeClassName && activeClassName.textContent === classToDeleteName) {
                        const firstCard = classList.querySelector('.class-card');
                        if (firstCard) {
                            selectClass(firstCard);
                        } else {
                            activeClassName.textContent = "No class selected";
                            activeClassSubject.textContent = "";
                            activeClassDescription.textContent = "";
                            activeClassCode.textContent = "";
                            activeStudentCount.textContent = "0";
                        }
                    }

                    // Show success message
                    showToast("Class deleted successfully.", 'success');
                } else {
                    showToast('Error deleting class: ' + (data.error || 'Unknown error'), 'error');
                }
            })
            .catch(error => {
                console.error('Error deleting class:', error);
                showToast('An error occurred while deleting the class.', 'error');
            });
        }

        // Handle confirm delete button click
        const confirmDeleteBtn = document.getElementById("confirmDeleteBtn");
        if (confirmDeleteBtn) {
            confirmDeleteBtn.addEventListener("click", function() {
                if (classToDeleteCode) {
                    const modal = bootstrap.Modal.getInstance(document.getElementById("deleteClassModal"));
                    if (modal) modal.hide();
                    deleteTeacherClass(classToDeleteCode);
                    classToDeleteCode = null;
                    classToDeleteName = null;
                }
            });
        }

        loadSavedClasses();
        updateClassCount();

    }); // closes DOMContentLoaded

})(); // closes IIFE