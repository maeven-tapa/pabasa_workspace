/* The calendar's dates/slots are civil dates and times. Project the application
 * clock into Manila explicitly; neither Date.now() nor the client's zone is a
 * clock source. FullCalendar 6's built-in NowTimer cannot provide this guarantee.
 */
class AdminCalendarClock {
    constructor({element, status, url, onSync}) {
        Object.assign(this, {element, status, url, onSync});
        this.anchor = null;
        this.valid = false;
        this.request = null;
        this.formatter = new Intl.DateTimeFormat('en-CA', {
            timeZone: 'Asia/Manila', year: 'numeric', month: '2-digit', day: '2-digit',
            hour: '2-digit', minute: '2-digit', second: '2-digit', hourCycle: 'h23',
        });
        this.line = document.createElement('div');
        this.line.className = 'fc-timegrid-now-indicator-line calendar-server-now-line';
        this.line.setAttribute('aria-label', 'Current server time in Asia/Manila');
    }

    parts() {
        if (!this.anchor) return null;
        const instant = this.anchor.time + performance.now() - this.anchor.elapsed;
        return Object.fromEntries(this.formatter.formatToParts(new Date(instant))
            .filter(part => part.type !== 'literal').map(part => [part.type, part.value]));
    }

    dateValue() {
        const p = this.parts();
        return p ? `${p.year}-${p.month}-${p.day}` : null;
    }

    calendarNow() {
        const p = this.parts();
        // FullCalendar accepts component arrays directly as wall time, avoiding
        // browser timezone conversion (including client DST gaps).
        return p ? [+p.year, +p.month - 1, +p.day, +p.hour, +p.minute, +p.second] : null;
    }

    hide(message) {
        this.valid = false;
        this.line.remove();
        this.status.textContent = message;
        this.status.classList.add('text-warning');
    }

    render() {
        if (!this.valid || document.hidden || this.element.hidden) {
            this.line.remove();
            return;
        }
        // Expired samples are never shown indefinitely if a timer/request stalls.
        if (performance.now() - this.anchor.elapsed > 45000) {
            this.hide('Server time is out of date. Current-time line hidden; retrying…');
            return;
        }
        const p = this.parts();
        const day = `${p.year}-${p.month}-${p.day}`;
        // FullCalendar also caches its today highlighting in NowTimer. Keep
        // that decoration aligned when an override or Manila midnight changes it.
        this.element.querySelectorAll('.fc-daygrid-day[data-date], .fc-timegrid-col[data-date], .fc-col-header-cell[data-date]')
            .forEach(cell => cell.classList.toggle('fc-day-today', cell.dataset.date === day));
        const container = this.element.querySelector(
            `.fc-timegrid-col[data-date="${day}"] .fc-timegrid-now-indicator-container`);
        if (!container) {
            this.line.remove(); // Month, Year, or a week without the server date.
            return;
        }
        const seconds = +p.hour * 3600 + +p.minute * 60 + +p.second;
        const rows = [...this.element.querySelectorAll('.fc-timegrid-slot-lane[data-time]')];
        const rowSeconds = row => row.dataset.time.split(':').reduce((sum, n) => sum * 60 + +n, 0);
        const index = rows.findIndex((row, i) => seconds >= rowSeconds(row)
            && seconds < (rows[i + 1] ? rowSeconds(rows[i + 1]) : 86400));
        if (index < 0) {
            this.line.remove();
            return;
        }
        const row = rows[index];
        const start = rowSeconds(row);
        const end = rows[index + 1] ? rowSeconds(rows[index + 1]) : 86400;
        const bounds = row.getBoundingClientRect();
        const top = bounds.top + bounds.height * (seconds - start) / (end - start)
            - container.getBoundingClientRect().top;
        this.line.style.top = `${top}px`;
        this.line.dataset.serverTime = `${day}T${p.hour}:${p.minute}:${p.second}+08:00`;
        if (this.line.parentElement !== container) container.appendChild(this.line);
    }

    async sync() {
        if (document.hidden || this.request) return;
        const controller = new AbortController();
        this.request = controller;
        const started = performance.now();
        const timeout = setTimeout(() => controller.abort(), 10000);
        try {
            const response = await fetch(this.url, {
                credentials: 'same-origin', cache: 'no-store',
                headers: {'Accept': 'application/json'}, signal: controller.signal,
            });
            if (!response.ok) throw new Error('Server time request failed');
            const data = await response.json();
            const ended = performance.now();
            const time = Date.parse(data.server_time);
            if (!data.success || data.time_zone !== 'Asia/Manila'
                || typeof data.server_time !== 'string'
                || !/T.*(?:Z|[+-]\d{2}:\d{2})$/.test(data.server_time)
                || !Number.isFinite(time) || ended - started >= 10000) {
                throw new Error('Invalid server time');
            }
            if (controller.signal.aborted || document.hidden) return;
            // Estimate transit time; interpolate subsequent ticks monotonically.
            this.anchor = {time: time + (ended - started) / 2, elapsed: ended};
            this.valid = true;
            this.status.textContent = 'Current-time line: server time (Asia/Manila).';
            this.status.classList.remove('text-warning');
            this.onSync();
            this.render();
        } catch (error) {
            if (this.request === controller) {
                this.hide('Server time unavailable. Current-time line hidden; retrying…');
            }
        } finally {
            clearTimeout(timeout);
            if (this.request === controller) this.request = null;
        }
    }

    resume() {
        this.request?.abort();
        this.request = null;
        this.hide('Synchronizing server time…');
        this.sync();
    }

    start() {
        this.sync();
        // Polling picks up override edits made in another tab/admin session.
        this.pollTimer = setInterval(() => this.sync(), 30000);
        this.tickTimer = setInterval(() => this.render(), 1000);
        this.resizeObserver = new ResizeObserver(() => this.render());
        this.resizeObserver.observe(this.element);
        document.addEventListener('visibilitychange', () => {
            if (!document.hidden) this.resume();
            else {
                this.request?.abort();
                this.hide('Synchronizing server time…');
            }
        });
        window.addEventListener('focus', () => this.resume());
        window.addEventListener('online', () => this.resume());
        window.addEventListener('offline', () => {
            this.request?.abort();
            this.hide('Offline. Current-time line hidden until server time is available.');
        });
        window.addEventListener('pageshow', event => { if (event.persisted) this.resume(); });
        window.addEventListener('pagehide', () => {
            this.request?.abort();
            this.hide('Synchronizing server time…');
        });
    }
}
