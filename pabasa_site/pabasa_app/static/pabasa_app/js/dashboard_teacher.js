(function () {
    document.addEventListener('DOMContentLoaded', function () {
        const createClassForm = document.getElementById("createClassForm");
        const subjectInput = document.getElementById("subjectInput");
        const classDescriptionInput = document.getElementById("classDescriptionInput");
        const gradeLevelInput = document.getElementById("gradeLevelInput");
        const sectionInput = document.getElementById("sectionInput");
        const generatedClassCode = document.getElementById("generatedClassCode");
        const regenerateCodeBtn = document.getElementById("regenerateCodeBtn");
        const classList = document.getElementById("classList");
        const classCount = document.getElementById("classCount");
        const copyClassCodeBtn = document.getElementById("copyClassCodeBtn");

        const activeClassName = document.getElementById("activeClassName");
        const activeClassSubject = document.getElementById("activeClassSubject");
        const activeClassDescription = document.getElementById("activeClassDescription");
        const activeClassCode = document.getElementById("activeClassCode");
        const activeStudentCount = document.getElementById("activeStudentCount");
        const classBanner = document.getElementById("classBanner");

        const deleteClassModal = document.getElementById("deleteClassModal");
        const deleteClassNameDisplay = document.getElementById("deleteClassNameDisplay");
        const confirmDeleteBtn = document.getElementById("confirmDeleteBtn");

        if (!createClassForm || !classList || !generatedClassCode) {
            return;
        }

        let classToDelete = null;
        const teacherEmail = (window.PABASA_USER_EMAIL || '').trim();
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
            generatedClassCode.textContent = makeClassCode();
        }

        function updateClassCount() {
            if (classCount) {
                classCount.textContent = String(classList.querySelectorAll(".class-card").length);
            }
        }

        function getStudentCountForClass(className) {
            try {
                const allStudents = JSON.parse(localStorage.getItem("pabasa_added_students") || "[]");
                return allStudents.filter(s => s.class === className && s.name !== "Jay Park").length;
            } catch (e) {
                console.error("Error getting student count for class:", e);
                return 0;
            }
        }

        function saveClasses() {
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
                        classData.students || '0',
                        classTeacherEmail
                    );

                    classList.appendChild(card);
                });

                updateClassCount();

                const firstCard = classList.querySelector('.class-card');
                if (firstCard) {
                    selectClass(firstCard);
                }
            })
            .catch(function (error) {
                console.error('Error loading classes:', error);
            });
        }

        function selectClass(card) {
            classList.querySelectorAll(".class-card").forEach(function (item) {
                item.classList.toggle("is-active", item === card);
            });

            const name = card.getAttribute("data-class-name") || "Reading Class";
            const subject = card.getAttribute("data-subject") || "Reading";
            const code = card.getAttribute("data-code") || "READ-000";
            const header = card.getAttribute("data-header") || "READ";
            const description = card.getAttribute("data-description") || "Class reading workspace.";
            const actualStudentCount = getStudentCountForClass(name);

            activeClassName.textContent = name;
            activeClassSubject.textContent = subject;
            activeClassDescription.textContent = description;
            activeClassCode.textContent = code;
            activeStudentCount.textContent = actualStudentCount;
            classBanner.setAttribute("data-header", header);
            generatedClassCode.textContent = code;

            if (copyClassCodeBtn) {
                copyClassCodeBtn.style.display = "block";
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

            const actualStudentCount = getStudentCountForClass(name);
            card.setAttribute("data-students", actualStudentCount);

            const head = document.createElement("span");
            head.className = "class-card-head";

            const title = document.createElement("strong");
            title.textContent = name;

            const codePill = document.createElement("span");
            codePill.className = "class-code-pill";
            codePill.textContent = code;

            const meta = document.createElement("span");
            meta.className = "small text-secondary";
            meta.textContent = (subject || name) + " • " + actualStudentCount + " students";

            head.appendChild(title);
            head.appendChild(codePill);
            card.appendChild(head);
            card.appendChild(meta);

            return card;
        }

        function showDeleteConfirmation(card) {
            classToDelete = card;
            const className = card.getAttribute("data-class-name") || "this class";
            deleteClassNameDisplay.textContent = className;
            const modal = new bootstrap.Modal(deleteClassModal);
            modal.show();
        }

        function deleteClass(card) {
            const nextCard = card.nextElementSibling || card.previousElementSibling;
            card.remove();
            updateClassCount();
            saveClasses();

            if (nextCard && nextCard.classList && nextCard.classList.contains("class-card")) {
                selectClass(nextCard);
            } else {
                const remaining = classList.querySelector(".class-card");
                if (remaining) {
                    selectClass(remaining);
                }
            }
        }

        classList.addEventListener("click", function (event) {
            const card = event.target.closest(".class-card");
            if (card) {
                selectClass(card);
            }
        });

        confirmDeleteBtn.addEventListener("click", function () {
            if (classToDelete) {
                deleteClass(classToDelete);
                classToDelete = null;
                const modal = bootstrap.Modal.getInstance(deleteClassModal);
                if (modal) {
                    modal.hide();
                }
            }
        });

        createClassForm.addEventListener("submit", function (event) {
            event.preventDefault();

            const subject = subjectInput.value;
            const gradeLevel = gradeLevelInput.value;
            const section = sectionInput.value;

            if (!subject || !gradeLevel || !section) {
                alert("Please select Subject, Grade Level, and Section.");
                return;
            }

            const description = classDescriptionInput.value.trim() || "Reading class workspace.";
            const name = `${gradeLevel} - ${section} (${subject})`;

            fetch('/dashboard/teacher/create-class/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': document.querySelector("[name=csrfmiddlewaretoken]")?.value || ""
                },
                body: JSON.stringify({
                    class_name: name,
                    subject: subject,
                    grade_level: gradeLevel,
                    section: section,
                    description: description
                })
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    document.getElementById("createdClassName").textContent = data.class_name;
                    document.getElementById("createdClassCode").textContent = data.class_code;

                    const successModal = new bootstrap.Modal(
                        document.getElementById("classCreatedModal"),
                        { backdrop: false, keyboard: true }
                    );
                    successModal.show();

                    document.querySelectorAll(".modal-backdrop").forEach(el => el.remove());
                    document.body.classList.remove("modal-open");
                    document.body.style.overflow = "auto";
                    document.body.style.paddingRight = "0";

                    const currentTeacherEmail = window.PABASA_USER_EMAIL
                        || localStorage.getItem("pabasaUserEmail")
                        || "";

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

                    const currentScopedKey = `pabasa_teacher_classes_${currentTeacherEmail}`;
                    const existing = JSON.parse(localStorage.getItem(currentScopedKey) || '[]');
                    existing.unshift({
                        code: data.class_code,
                        name: data.class_name,
                        subject: subject,
                        grade_level: gradeLevel,
                        section: section,
                        description: description,
                        header: 'READ',
                        students: '0',
                        teacher_email: currentTeacherEmail,
                    });
                    localStorage.setItem(currentScopedKey, JSON.stringify(existing));

                    setGeneratedCode();
                    classDescriptionInput.value = "";

                } else {
                    alert("Creation failed: " + data.error);
                }
            })
            .catch(error => {
                console.error("Error creating classroom:", error);
                alert("An error occurred while creating the classroom.");
            });
        });

        regenerateCodeBtn.addEventListener("click", setGeneratedCode);

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
            });
        }

        // Copy code button
        const copyCreatedBtn = document.getElementById("copyCreatedClassCode");
        if (copyCreatedBtn) {
            copyCreatedBtn.addEventListener("click", function () {
                const code = document.getElementById("createdClassCode").textContent;
                navigator.clipboard.writeText(code);
                this.innerHTML = '<i class="bi bi-check2 me-2"></i>Copied!';
                setTimeout(() => {
                    this.innerHTML = '<i class="bi bi-copy me-2"></i>Copy Code';
                }, 1500);
            });
        }

        loadSavedClasses();
        updateClassCount();

    }); // closes DOMContentLoaded

})(); // closes IIFE