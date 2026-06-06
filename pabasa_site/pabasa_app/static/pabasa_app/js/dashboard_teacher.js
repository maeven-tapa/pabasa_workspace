(function () {
    const createClassForm = document.getElementById("createClassForm");
    const classNameInput = document.getElementById("classNameInput");
    const classHeaderInput = document.getElementById("classHeaderInput");
    const classDescriptionInput = document.getElementById("classDescriptionInput");
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

    // Modal elements
    const deleteClassModal = document.getElementById("deleteClassModal");
    const deleteClassNameDisplay = document.getElementById("deleteClassNameDisplay");
    const confirmDeleteBtn = document.getElementById("confirmDeleteBtn");

    if (!createClassForm || !classList || !generatedClassCode) {
        return;
    }

    let classToDelete = null;
    const classStorageKey = "pabasa_teacher_classes";

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

    function getCardData(card) {
        return {
            name: card.getAttribute("data-class-name") || "Reading Class",
            subject: card.getAttribute("data-subject") || "Reading",
            code: card.getAttribute("data-code") || "READ-000",
            header: card.getAttribute("data-header") || "READ",
            description: card.getAttribute("data-description") || "Class reading workspace.",
            students: card.getAttribute("data-students") || "0"
        };
    }

    function saveClasses() {
        const classes = Array.from(classList.querySelectorAll(".class-card")).map(getCardData);
        localStorage.setItem(classStorageKey, JSON.stringify(classes));
    }

    function loadSavedClasses() {
        const saved = JSON.parse(localStorage.getItem(classStorageKey) || "null");
        if (!saved || !Array.isArray(saved) || saved.length === 0) {
            saveClasses();
            return;
        }

        classList.innerHTML = "";
        saved.forEach(function (classData) {
            classList.appendChild(createClassCard(
                classData.name,
                classData.header,
                classData.description,
                classData.code,
                classData.subject,
                classData.students
            ));
        });

        const firstCard = classList.querySelector(".class-card");
        if (firstCard) {
            selectClass(firstCard);
        }
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
        const students = card.getAttribute("data-students") || "0";

        activeClassName.textContent = name;
        activeClassSubject.textContent = subject;
        activeClassDescription.textContent = description;
        activeClassCode.textContent = code;
        activeStudentCount.textContent = students;
        classBanner.setAttribute("data-header", header);
        generatedClassCode.textContent = code;
        
        // Show copy code button when class is selected
        if (copyClassCodeBtn) {
            copyClassCodeBtn.style.display = "block";
        }
    }

    function createClassCard(name, header, description, code, subject, students) {
        const card = document.createElement("div");
        card.className = "class-card";
        card.setAttribute("data-class-name", name);
        card.setAttribute("data-subject", subject || name);
        card.setAttribute("data-code", code);
        card.setAttribute("data-header", header);
        card.setAttribute("data-description", description);
        card.setAttribute("data-students", students || "0");

        const head = document.createElement("span");
        head.className = "class-card-head";

        const title = document.createElement("strong");
        title.textContent = name;

        const codePill = document.createElement("span");
        codePill.className = "class-code-pill";
        codePill.textContent = code;

        const meta = document.createElement("span");
        meta.className = "small text-secondary";
        meta.textContent = (subject || name) + " • " + (students || "0") + " students";

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

        const name = classNameInput.value.trim() || "New Reading Class";
        const header = (classHeaderInput.value.trim() || "READ").toUpperCase();
        const description = classDescriptionInput.value.trim() || "Reading class workspace.";
        const code = generatedClassCode.textContent.trim() || makeClassCode();
        const card = createClassCard(name, header, description, code);

        classList.prepend(card);
        selectClass(card);
        updateClassCount();
        saveClasses();
        setGeneratedCode();
        
        // Clear the form fields after successful class creation
        classNameInput.value = "";
        classHeaderInput.value = "";
        classDescriptionInput.value = "";
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
    (function() {
        const studentRow = document.querySelector(".student-row");
        if (!studentRow) return;
        
        const students = JSON.parse(localStorage.getItem("pabasa_added_students") || "[]");
        
        students.forEach(studentData => {
            // Check if student already exists
            const exists = Array.from(studentRow.querySelectorAll(".student-card")).some(
                card => card.textContent.includes(studentData.name)
            );
            
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
                <div><strong>${studentData.name}</strong><div class="small text-secondary">WPM ${studentData.wpm} • ${studentData.accuracy}%</div></div>
                <span class="level-chip ${levelClass}">${studentData.level}</span>
            `;
            
            studentRow.appendChild(studentCard);
        });
    })();

    loadSavedClasses();
    updateClassCount();
})();
