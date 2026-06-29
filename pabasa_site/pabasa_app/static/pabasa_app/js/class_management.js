document.addEventListener('DOMContentLoaded', function () {
    const updateForm = document.getElementById('updateClassForm');
    if (updateForm) {
        updateForm.addEventListener('submit', function (e) {
            e.preventDefault();
            const formData = new FormData(updateForm);
            const data = Object.fromEntries(formData.entries());

            fetch('/dashboard/teacher/update-class/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': data.csrfmiddlewaretoken
                },
                body: JSON.stringify(data)
            })
            .then(response => response.json())
            .then(res => {
                if (res.success) {
                    if (typeof showToast === 'function') showToast('Class details updated successfully.', 'success'); else try{ alert('Class details updated successfully.'); }catch(e){}
                    setTimeout(() => window.location.reload(), 1200);
                } else {
                    if (typeof showToast === 'function') showToast('Error: ' + res.error, 'error'); else try{ alert('Error: ' + res.error); }catch(e){}
                }
            });
        });
    }

    // Student Search & Filter Logic for Modal
    const studentSearch = document.getElementById('studentSearch');
    const studentFilter = document.getElementById('studentFilter');
    const tableRows = document.querySelectorAll('#availableStudentsTable tbody tr');
    const noStudentsFoundMessage = document.getElementById('noStudentsFoundMessage');

    function filterTable() {
        const query = (studentSearch?.value || '').toLowerCase().trim();
        const filterType = studentFilter?.value || '';
        let visibleRowCount = 0;

        tableRows.forEach(row => {
            const name = row.dataset.name;
            const pabasaId = row.dataset.id;
            const grade = row.dataset.grade;

            let matches = false;
            if (filterType === 'all') {
                matches = name.includes(query) || pabasaId.includes(query) || grade.includes(query);
            } else if (filterType === 'name') {
                matches = name.includes(query);
            } else if (filterType === 'pabasa_id') {
                matches = pabasaId.includes(query);
            } else if (filterType === 'grade') {
                matches = grade.includes(query);
            }

            row.style.display = matches ? '' : 'none';
            if (matches) {
                visibleRowCount++;
            }
        });

        if (noStudentsFoundMessage) {
            if (visibleRowCount === 0) {
                noStudentsFoundMessage.classList.remove('d-none');
            } else {
                noStudentsFoundMessage.classList.add('d-none');
            }
        }
    }

    if (studentSearch) studentSearch.addEventListener('input', filterTable);
    if (studentFilter) studentFilter.addEventListener('change', filterTable);

    // Manual Enrollment Action
    document.querySelectorAll('.add-student-btn').forEach(btn => {
        btn.addEventListener('click', function() {
            const studentId = this.dataset.studentId;
            const classCode = new URLSearchParams(window.location.search).get('code');
            const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]')?.value || '';
            const clickedButton = this;
            const addStudentModalEl = document.getElementById('addStudentModal');
            const loadingModalEl = document.getElementById('addStudentLoadingModal');

            clickedButton.disabled = true;
            if (typeof window.showClassStudentLoading === 'function') {
                window.showClassStudentLoading();
            } else if (loadingModalEl) {
                loadingModalEl.classList.add('is-visible');
            }
            try { bootstrap.Modal.getInstance(addStudentModalEl)?.hide(); } catch (e) { console.warn(e); }

            fetch('/dashboard/teacher/add-student-to-class/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': csrfToken
                },
                body: JSON.stringify({ student_id: studentId, class_code: classCode })
            })
            .then(res => res.json())
            .then(data => {
                if (typeof window.hideClassStudentLoading === 'function') {
                    window.hideClassStudentLoading();
                } else if (loadingModalEl) {
                    loadingModalEl.classList.remove('is-visible');
                }

                if (data.success) {
                    // Notify other modules to refresh authoritative data without forcing a full reload
                    try { window.dispatchEvent(new CustomEvent('studentAdded', { detail: { student_id: studentId, class_code: classCode } })); } catch (e) { console.warn(e); }
                    try { window.dispatchEvent(new CustomEvent('pabasa:teacher-classes-updated', { detail: { class_code: classCode } })); } catch (e) { console.warn(e); }

                    if (typeof showToast === 'function') showToast('Student added successfully.', 'success'); else try{ alert('Student added successfully.'); }catch(e){}
                    setTimeout(() => window.location.reload(), 1200);
                } else {
                    if (typeof showToast === 'function') showToast('Error: ' + data.error, 'error'); else try{ alert('Error: ' + data.error); }catch(e){}
                    clickedButton.disabled = false;
                }
            })
            .catch(error => {
                if (typeof window.hideClassStudentLoading === 'function') {
                    window.hideClassStudentLoading();
                } else if (loadingModalEl) {
                    loadingModalEl.classList.remove('is-visible');
                }
                clickedButton.disabled = false;
                console.error('Error adding student to class:', error);
                if (typeof showToast === 'function') showToast('Error: Unable to add student. Please try again.', 'error'); else try{ alert('Error: Unable to add student. Please try again.'); }catch(e){}
            });
        });
    });
});
