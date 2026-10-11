/* Share one fresh, authorized class listing between components on this page. */
(function () {
    'use strict';
    let listing = null;

    function load() {
        if (listing) return listing;
        const request = fetch('/api/student/classes/', {
            credentials: 'same-origin',
            cache: 'no-store',
            headers: { Accept: 'application/json', 'X-Requested-With': 'XMLHttpRequest' },
        }).then(async (response) => {
            const data = await response.json();
            if (!response.ok || !data.success || !Array.isArray(data.classes)) {
                throw new Error(data.error || 'Unable to load student classes');
            }
            return data;
        });
        listing = request;
        request.catch(() => {
            // Allow retry without discarding a newer request after invalidation.
            if (listing === request) listing = null;
        });
        return request;
    }

    window.PabasaStudentClasses = { load, invalidate() { listing = null; } };
})();
