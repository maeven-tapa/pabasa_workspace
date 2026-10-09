/* Transport only. The shared reader evaluates signed finals using its existing rules. */
(() => {
    'use strict';
    class CrlaSpeechStream {
        constructor(options) {
            this.options = options;
            this.active = true;
            this.queuedFinals = 0;
            this.flushing = false;
            this.queue = Promise.resolve();
            this.seen = new Set();
            this.backlog = [];
            this.socket = null;
            this.finishing = false;
            this.rotation = null;
        }
        get pending() { return this.queuedFinals > 0 || this.finishing || this.flushing; }
        async open() {
            const controller = new AbortController();
            this.ticketController = controller;
            const ticketTimeout = setTimeout(() => controller.abort(), 8000);
            let response;
            try {
                response = await fetch('/api/reading/crla-stream/start/', {
                    method: 'POST', credentials: 'same-origin', signal: controller.signal,
                    headers: {'Content-Type': 'application/json', 'X-CSRFToken': this.options.csrf()},
                    body: JSON.stringify(this.options.fields),
                });
            } finally {
                clearTimeout(ticketTimeout);
                if (this.ticketController === controller) this.ticketController = null;
            }
            const result = await response.json();
            if (!response.ok || !result.success || !this.active) throw new Error(result.error || 'Live speech is unavailable.');
            const url = new URL(result.path, window.location.href);
            url.protocol = url.protocol === 'https:' ? 'wss:' : 'ws:';
            const socket = new WebSocket(url.href);
            socket.binaryType = 'arraybuffer';
            this.socket = socket;
            await new Promise((resolve, reject) => {
                const timer = setTimeout(() => { reject(new Error('Live speech connection timed out.')); socket.close(); }, 8000);
                let ready = false;
                let serverEnded = false;
                let finishResolver;
                this.serverFinished = new Promise(done => { finishResolver = done; this.resolveFinished = done; });
                socket.onopen = () => socket.send(JSON.stringify({ticket: result.ticket}));
                socket.onmessage = event => {
                    if (!this.active || this.socket !== socket) return;
                    const message = JSON.parse(event.data);
                    if (message.type === 'ready') {
                        ready = true;
                        clearTimeout(timer);
                        for (const audio of this.backlog.splice(0)) socket.send(audio);
                        resolve();
                    } else if (message.type === 'interim') {
                        if (!this.finishing) this.options.onInterim(message.transcript);
                    } else if (message.type === 'final' && !this.seen.has(message.id)) {
                        this.seen.add(message.id);
                        this.queuedFinals++;
                        this.queue = this.queue.then(async () => {
                            if (this.active) await this.options.onFinal(message);
                        }).catch(error => this.fail(error)).finally(() => { this.queuedFinals--; });
                    } else if (message.type === 'finished') {
                        serverEnded = true;
                        finishResolver(true);
                        if (!this.finishing) this.fail(new Error('Live speech ended unexpectedly. Please restart the microphone.'));
                    } else if (message.type === 'error') {
                        if (ready) this.fail(new Error(message.error));
                        else { clearTimeout(timer); reject(new Error(message.error)); }
                    }
                };
                socket.onerror = () => {
                    if (this.socket !== socket) return;
                    clearTimeout(timer);
                    if (!ready) reject(new Error('Live speech is unavailable.'));
                    else if (this.active) this.fail(new Error('Live speech connection interrupted.'));
                };
                socket.onclose = () => {
                    clearTimeout(timer);
                    if (!ready) reject(new Error('Live speech is unavailable.'));
                    finishResolver(false);
                    if (this.socket === socket && this.active && !this.finishing && !serverEnded) this.fail(new Error('Live speech connection closed.'));
                };
            });
        }
        async start(stream) {
            // Capture while the socket connects, so its handshake does not
            // drop the first spoken word. Keep this bounded like rotation.
            this.rotating = true;
            const opening = this.open();
            opening.catch(() => {});
            const AudioContext = window.AudioContext || window.webkitAudioContext;
            this.audioContext = new AudioContext();
            try {
                await this.audioContext.audioWorklet.addModule(window.__PABASA_CRLA_PCM_WORKLET__);
                if (!this.active) return;
                this.source = this.audioContext.createMediaStreamSource(stream);
                this.node = new AudioWorkletNode(this.audioContext, 'crla-pcm');
                this.silent = this.audioContext.createGain();
                this.silent.gain.value = 0;
                this.node.port.onmessage = event => {
                    if (event.data.flushed) { this.resolveFlushed?.(); return; }
                    if (!this.active || !event.data.audio) return;
                    this.sendAudio(event.data.audio);
                };
                this.source.connect(this.node).connect(this.silent).connect(this.audioContext.destination);
                await this.audioContext.resume();
                await opening;
                this.rotating = false;
                for (const audio of this.backlog.splice(0)) this.sendAudio(audio);
                this.scheduleRotation();
            } catch (error) {
                this.fallbackAudio = this.backlog.length ? this.wavBlob(this.backlog) : null;
                this.stop();
                throw error;
            }
        }
        wavBlob(frames) {
            const length = frames.reduce((total, frame) => total + frame.byteLength, 0);
            const header = new ArrayBuffer(44);
            const view = new DataView(header);
            const text = (offset, value) => [...value].forEach((char, index) => view.setUint8(offset + index, char.charCodeAt(0)));
            text(0, 'RIFF'); view.setUint32(4, length + 36, true); text(8, 'WAVE'); text(12, 'fmt ');
            view.setUint32(16, 16, true); view.setUint16(20, 1, true); view.setUint16(22, 1, true);
            view.setUint32(24, 16000, true); view.setUint32(28, 32000, true);
            view.setUint16(32, 2, true); view.setUint16(34, 16, true); text(36, 'data'); view.setUint32(40, length, true);
            return new Blob([header, ...frames], {type: 'audio/wav'});
        }
        sendAudio(audio) {
            if (this.rotating) {
                if (this.backlog.length >= 50) { this.fail(new Error('Live speech connection is too slow.')); return; }
                this.backlog.push(audio);
            } else if (this.socket?.readyState === WebSocket.OPEN) {
                if (this.socket.bufferedAmount > 128000) { this.fail(new Error('Live speech connection is too slow.')); return; }
                this.socket.send(audio);
            }
        }
        scheduleRotation() {
            clearTimeout(this.rotation);
            this.rotation = setTimeout(() => this.rotate(), 230000);
        }
        async rotate() {
            if (!this.active || this.finishing) return;
            this.rotating = true;
            try {
                await this.finishSocket();
                if (!this.active || this.finishing) return;
                this.seen.clear();
                await this.open();
                this.rotating = false;
                this.scheduleRotation();
            } catch (error) { this.fail(error); }
        }
        async finishSocket() {
            this.finishing = true;
            if (this.socket?.readyState === WebSocket.OPEN) this.socket.send('{"type":"finish"}');
            let timeout;
            const complete = await Promise.race([
                this.serverFinished,
                new Promise(resolve => { timeout = setTimeout(() => resolve(false), 12000); }),
            ]);
            clearTimeout(timeout);
            await this.queue;
            if (!complete && this.active) throw new Error('Final speech result did not arrive. Please restart the microphone.');
            this.socket?.close();
            this.finishing = false;
        }
        async finish() {
            clearTimeout(this.rotation);
            if (!this.active) return;
            if (this.rotating) throw new Error('Please wait for the speech connection to finish reconnecting.');
            this.flushing = true;
            try {
                if (this.node) {
                    let timeout;
                    await Promise.race([
                        new Promise(resolve => { this.resolveFlushed = resolve; this.node.port.postMessage('flush'); }),
                        new Promise((_, reject) => { timeout = setTimeout(() => reject(new Error('Audio capture did not finish.')), 2000); }),
                    ]).finally(() => clearTimeout(timeout));
                }
                await this.finishSocket();
            } finally {
                this.flushing = false;
                this.stop();
            }
        }
        fail(error) {
            if (!this.active) return;
            this.stop();
            this.options.onError(error);
        }
        stop() {
            this.active = false;
            this.ticketController?.abort();
            clearTimeout(this.rotation);
            this.source?.disconnect();
            this.node?.disconnect();
            this.silent?.disconnect();
            this.audioContext?.close().catch(() => {});
            this.socket?.close();
            this.resolveFinished?.(false);
            this.backlog.length = 0;
        }
    }
    window.CrlaSpeechStream = CrlaSpeechStream;
})();
