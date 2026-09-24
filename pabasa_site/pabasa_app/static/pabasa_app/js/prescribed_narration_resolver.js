(() => {
  'use strict';
  if (window.__prescribedNarrationResolverInstalled) return;
  window.__prescribedNarrationResolverInstalled = true;
  const normalize = value => String(value || '').trim().replace(/[?!\.]+$/, '').replace(/\s+/g, ' ').toLocaleLowerCase();
  const toBase64 = bytes => { let binary = ''; for (let index = 0; index < bytes.length; index += 0x8000) binary += String.fromCharCode(...bytes.subarray(index, index + 0x8000)); return btoa(binary); };
  const originalFetch = window.fetch.bind(window);
  window.fetch = async (input, init) => {
    const url = typeof input === 'string' ? input : input?.url || '', config = window.__prescribedNarrationAudio;
    if (!config || !url.includes('/api/reading/read-aloud/')) return originalFetch(input, init);
    const body = init?.body, targetText = body instanceof FormData || body instanceof URLSearchParams ? body.get('target_text') || '' : '', filename = config[normalize(targetText)];
    if (!filename) return originalFetch(input, init);
    const response = await originalFetch(filename, {credentials: 'same-origin', cache: 'no-store'});
    if (!response.ok) return response;
    return new Response(JSON.stringify({success: true, audio_content: toBase64(new Uint8Array(await response.arrayBuffer())), mime_type: 'audio/mpeg', prerecorded: true}), {status: 200, headers: {'Content-Type': 'application/json'}});
  };
})();
