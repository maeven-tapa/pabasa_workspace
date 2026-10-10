/* Only injected by the authorized admin activity renderer. */
(() => {
    'use strict';
    const fetchOriginal = window.fetch.bind(window);
    let workbookState = null;
    let workbookProgress = null;
    // Legacy activities also use browser storage for their draft work.
    // Keep that storage inside this preview instead of the shared student keys.
    const draftStorage = new Map();
    const previewStorage = {
        getItem: key => draftStorage.get(String(key)) ?? null,
        setItem: (key, value) => draftStorage.set(String(key), String(value)),
        removeItem: key => draftStorage.delete(String(key)),
        clear: () => draftStorage.clear(),
        key: index => Array.from(draftStorage.keys())[index] ?? null,
        get length() { return draftStorage.size; },
    };
    Object.defineProperty(window, 'localStorage', {value: previewStorage});
    const evaluationPaths = new Set([
        '/api/reading/transcribe/', '/api/reading/read-aloud/',
        '/api/reading/prescribed-stream/start/',
        '/api/template-activities/read-aloud/', '/api/template-activities/transcribe/',
        '/api/assessment/story-answer/check/', '/api/assessment/story-answer/transcribe/',
    ]);
    window.fetch = async (input, options = {}) => {
        const url = new URL(typeof input === 'string' || input instanceof URL ? input : input.url, window.location.href);
        const method = String(options.method || input?.method || 'GET').toUpperCase();
        const workbookPayload = document.getElementById('workbook-payload');
        if (workbookPayload && url.origin === window.location.origin && method === 'POST' && url.pathname.includes('/activity/prescribed/')) {
            const payload = JSON.parse(workbookPayload.textContent || '{}');
            workbookState ||= payload.state || {};
            if (url.pathname.endsWith('/complete/')) {
                if (!workbookState.completed) {
                    return new Response(JSON.stringify({success:false,error:'Complete the activity first.'}), {status:400,headers:{'Content-Type':'application/json'}});
                }
                return new Response(JSON.stringify({success:true,preview_only:true,result:{
                    items_completed:workbookProgress?.completed_items || 0,
                    correct_items:workbookProgress?.correct_items || 0,
                }}), {headers:{'Content-Type':'application/json'}});
            }
            let body;
            if (options.body instanceof FormData) {
                body = options.body;
                body.set('_preview_state', JSON.stringify(workbookState));
            } else {
                body = JSON.stringify({...JSON.parse(options.body || '{}'), _preview_state: workbookState});
            }
            const response = await fetchOriginal(`/api/admin/prescribed/${encodeURIComponent(window.__PABASA_ADMIN_PRESCRIBED_KEY__)}/event/`, {...options,body});
            const result = await response.clone().json();
            if (result.success && result.state) {
                workbookState = result.state;
                workbookProgress = result.progress;
            }
            return response;
        }
        if (url.origin === window.location.origin && !['GET', 'HEAD'].includes(method) && !evaluationPaths.has(url.pathname)) {
            return Promise.resolve(new Response(JSON.stringify({
                success: false, preview_only: true,
                error: 'Admin preview does not save student work.',
            }), {status: 403, headers: {'Content-Type': 'application/json'}}));
        }
        return fetchOriginal(input, options);
    };
    const patchBackLinks = () => document.querySelectorAll('a[href]').forEach(link => {
        const url = new URL(link.href, window.location.href);
        if (url.origin === window.location.origin && url.pathname.startsWith('/dashboard/assessment/')) {
            link.href = '/dashboard/admin/courses/prescribed/';
            link.target = '_top';
        }
    });
    document.addEventListener('DOMContentLoaded', () => {
        patchBackLinks();
        new MutationObserver(patchBackLinks).observe(document.body, {childList: true, subtree: true});
    }, {once: true});
})();
