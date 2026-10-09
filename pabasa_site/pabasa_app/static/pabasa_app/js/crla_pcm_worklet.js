/* Continuous mono capture; downsample the device rate to 16 kHz LINEAR16. */
class CrlaPcmProcessor extends AudioWorkletProcessor {
    constructor() {
        super();
        this.frame = new Int16Array(3200);
        this.index = 0;
        this.phase = 0;
        this.sum = 0;
        this.count = 0;
        this.active = true;
        this.port.onmessage = event => {
            if (event.data === 'flush') {
                this.active = false;
                this.emit();
                this.port.postMessage({flushed: true});
            }
        };
    }
    emit() {
        if (!this.index) return;
        const buffer = this.frame.slice(0, this.index).buffer;
        this.port.postMessage({audio: buffer}, [buffer]);
        this.index = 0;
    }
    process(inputs) {
        if (!this.active) return true;
        const channels = inputs[0];
        if (!channels?.length) return true;
        for (let i = 0; i < channels[0].length; i++) {
            let sample = 0;
            for (const channel of channels) sample += channel[i] || 0;
            this.sum += sample / channels.length;
            this.count++;
            this.phase += 16000;
            if (this.phase >= sampleRate) {
                const value = Math.max(-1, Math.min(1, this.sum / this.count));
                while (this.phase >= sampleRate) {
                    this.phase -= sampleRate;
                    this.frame[this.index++] = Math.round(value * (value < 0 ? 32768 : 32767));
                    if (this.index === this.frame.length) this.emit();
                }
                this.sum = 0;
                this.count = 0;
            }
        }
        return true;
    }
}
registerProcessor('crla-pcm', CrlaPcmProcessor);
