/* Stream recognition alongside the original clip; activity grading stays unchanged. */
(() => {
    'use strict';
    function headers() {
        const selection = window.PrescribedSttSettings?.selection || 'google';
        return {'X-Pabasa-STT-Provider': selection === 'knowlez' ? 'knowlez' : 'google',
            ...(selection.startsWith('chirp_') ? {'X-Pabasa-STT-Model': selection} : {})};
    }
    function begin(stream, fields, onInterim, onError) {
        const selection = window.PrescribedSttSettings?.selection || 'google';
        const Audio = window.AudioContext || window.webkitAudioContext;
        if (!['google', 'chirp_3'].includes(selection) || !window.CrlaSpeechStream
                || !window.AudioWorkletNode || !window.WebSocket || !Audio
                || !window.__PABASA_CRLA_PCM_WORKLET__ || !fields.material_id) return null;
        let failed = null, fallback = false, cancelled = false;
        const live = new window.CrlaSpeechStream({
            startUrl: '/api/reading/material-stream/start/',
            fields: {...fields, complete_utterance: true}, headers: headers(),
            csrf: () => decodeURIComponent(document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/)?.[1] || ''),
            onInterim: text => { if (!cancelled) onInterim?.(text); }, onFinal: () => {},
            onError: error => { failed = error; onError?.(error); },
        });
        const opening = live.start(stream).catch(error => {
            if ([400, 401, 403].includes(error.status) || failed) failed = failed || error;
            else fallback = true;
            live.stop();
        });
        return {
            async finish(blob) {
                await opening;
                if (cancelled) throw new DOMException('Reading cancelled.', 'AbortError');
                if (failed) throw failed;
                if (fallback) return blob;
                await live.finish();
                if (failed) throw failed;
                if (!live.resultToken || live.hasSpeech === false) throw new Error('No final speech was received. Please try again.');
                Object.defineProperty(blob, 'materialStreamToken', {value: live.resultToken});
                return blob;
            },
            stop() { cancelled = true; live.stop(); },
        };
    }
    function attach(form, blob) {
        if (blob?.materialStreamToken) form.set('material_stream_token', blob.materialStreamToken);
    }
    window.MaterialSpeechCapture = Object.freeze({begin, attach, headers});
})();
