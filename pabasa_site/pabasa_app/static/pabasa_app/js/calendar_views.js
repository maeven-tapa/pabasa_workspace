/* School-calendar viewing logic extracted from Admin; no management actions. */
(() => {
'use strict';
const parseDateInput=value=>{if(!value)return null;const date=new Date(String(value).slice(0,10)+'T00:00:00');return Number.isNaN(date.getTime())?null:date;};
const formatDateValue=date=>`${date.getFullYear()}-${String(date.getMonth()+1).padStart(2,'0')}-${String(date.getDate()).padStart(2,'0')}`;
        function yearRange(events, schoolYear) {
            const relevant = events.filter((event) => ['school_opening', 'start_of_classes', 'school_closing', 'end_of_classes'].includes(event.event_type));
            const starts = relevant
                .map((event) => parseDateInput(event.start || event.start_date))
                .filter(Boolean)
                .map((date) => new Date(date.getFullYear(), date.getMonth(), 1));
            const ends = relevant
                .map((event) => parseDateInput(event.end_date || event.end || event.start || event.start_date))
                .filter(Boolean)
                .map((date) => new Date(date.getFullYear(), date.getMonth(), 1));
            if (starts.length || ends.length) {
                const start = starts.length ? new Date(Math.min(...starts.map((date) => date.getTime()))) : new Date();
                const end = ends.length ? new Date(Math.max(...ends.map((date) => date.getTime()))) : new Date();
                return { start, end };
            }
            schoolYear = String(schoolYear || '').trim();
            if (/^\d{4}-\d{4}$/.test(schoolYear)) {
                const startYear = Number(schoolYear.slice(0, 4));
                return {
                    start: new Date(startYear, 6, 1),
                    end: new Date(startYear + 1, 5, 31),
                };
            }
            const fallback = new Date();
            return { start: new Date(fallback.getFullYear(), 0, 1), end: new Date(fallback.getFullYear(), 11, 31) };
        }

        function termMeta(monthDate, blocks) {
            const monthStart = new Date(monthDate.getFullYear(), monthDate.getMonth(), 1);
            const monthEnd = new Date(monthDate.getFullYear(), monthDate.getMonth() + 1, 0);
            for (const term of [1, 2, 3]) {
                const opening = blocks[String(term)]?.opening ? new Date(`${blocks[String(term)].opening}T00:00:00`) : null;
                const closing = blocks[String(term)]?.closing ? new Date(`${blocks[String(term)].closing}T00:00:00`) : null;
                if (!opening && !closing) continue;
                const start = opening || new Date(monthStart.getFullYear(), 0, 1);
                const end = closing || new Date(monthEnd.getFullYear(), 11, 31);
                if (monthStart >= start && monthEnd <= end) {
                    return {
                        term,
                        label: `Term ${term}`,
                        color: term === 1 ? 'rgba(46,168,229,0.10)' : term === 2 ? 'rgba(250, 204, 21, 0.10)' : 'rgba(168, 85, 247, 0.10)',
                    };
                }
            }
            return {
                term: null,
                label: '',
                color: 'rgba(16,70,110,0.04)',
            };
        }

        function renderYear({element, events, rangeEvents=events, schoolYear, termBlocks={}, today, onDate, onMonth}) {
            const calendarYearView=element;
            const colors=window.PabasaCalendarPalette.colors;
            const getSelectedCalendarEvents=()=>events;
            const getSelectedYearMonthRange=()=>yearRange(rangeEvents,schoolYear);
            const getTermWindowForMonth=date=>termMeta(date,termBlocks);
            const currentServerDate=()=>today;
            const openYearDetailModal=onDate;
            const setView=(_view,date)=>onMonth(date);
            if (!calendarYearView) return;
            const { start, end } = getSelectedYearMonthRange();
            const monthCursor = new Date(start.getFullYear(), start.getMonth(), 1);
            const lastMonth = new Date(end.getFullYear(), end.getMonth(), 1);
            const cards = [];
            while (monthCursor <= lastMonth) {
                const monthStart = new Date(monthCursor);
                const monthEnd = new Date(monthCursor.getFullYear(), monthCursor.getMonth() + 1, 0);
                const monthEventMap = new Map();
                const monthRelevantEvents = getSelectedCalendarEvents().filter((event) => {
                    const eventStart = parseDateInput(event.start || event.start_date);
                    const eventEnd = parseDateInput(event.end_date || event.end || event.start || event.start_date);
                    if (!eventStart || !eventEnd) return false;
                    return eventStart <= monthEnd && eventEnd >= monthStart;
                });
                for (const event of monthRelevantEvents) {
                    const eventStart = parseDateInput(event.start || event.start_date);
                    const eventEnd = parseDateInput(event.end_date || event.end || event.start || event.start_date);
                    if (!eventStart || !eventEnd) continue;
                    const current = new Date(eventStart);
                    while (current <= eventEnd) {
                        const dateValue = formatDateValue(current);
                        const monthDate = new Date(`${dateValue}T00:00:00`);
                        if (monthDate.getFullYear() === monthCursor.getFullYear() && monthDate.getMonth() === monthCursor.getMonth()) {
                            const existing = monthEventMap.get(dateValue) || [];
                            existing.push(event);
                            monthEventMap.set(dateValue, existing);
                        }
                        current.setDate(current.getDate() + 1);
                    }
                }
                const monthName = new Intl.DateTimeFormat('en-US', { month: 'long' }).format(monthCursor);
                const yearNumber = monthCursor.getFullYear();
                const termMeta = getTermWindowForMonth(monthCursor);
                const termColor = termMeta.color;
                const termLabel = termMeta.label;
                const weekdayLabels = ['S', 'M', 'T', 'W', 'T', 'F', 'S'];
                const firstDay = new Date(monthCursor.getFullYear(), monthCursor.getMonth(), 1);
                const leadingDays = firstDay.getDay();
                const totalDays = new Date(monthCursor.getFullYear(), monthCursor.getMonth() + 1, 0).getDate();
                const totalCells = leadingDays + totalDays;
                const dayCells = [];
                for (let index = 0; index < leadingDays; index += 1) {
                    dayCells.push(`<div class="calendar-year-day is-muted" aria-hidden="true"></div>`);
                }
                for (let day = 1; day <= totalDays; day += 1) {
                    const date = new Date(monthCursor.getFullYear(), monthCursor.getMonth(), day);
                    const dateValue = formatDateValue(date);
                    const dayEvents = monthEventMap.get(dateValue) || [];
                    const markerHtml = dayEvents.slice(0, 3).map((event) => `<span class="calendar-year-day-marker" style="background:${colors[event.event_type] || colors.other};"></span>`).join('');
                    const isToday = dateValue === currentServerDate();
                    const hasEvent = dayEvents.length > 0;
                    dayCells.push(`
                        <button type="button" class="calendar-year-day${hasEvent ? ' has-event is-event' : ''}${isToday ? ' is-today' : ''}" data-year-date="${dateValue}" aria-label="${dateValue}${hasEvent ? `, ${dayEvents.length} events` : ', open month'}">
                            <span class="calendar-year-day-number">${day}</span>
                            ${hasEvent ? `<span class="calendar-year-day-markers">${markerHtml}</span>` : ''}
                        </button>
                    `);
                }
                const trailingCells = (7 - (totalCells % 7)) % 7;
                for (let index = 0; index < trailingCells; index += 1) {
                    dayCells.push(`<div class="calendar-year-day is-muted" aria-hidden="true"></div>`);
                }
                const daysHtml = dayCells.join('');
                cards.push(`
                    <article class="calendar-year-month" data-month-name="${monthName}" data-year-date="${formatDateValue(monthStart)}" aria-label="${monthName} ${yearNumber}">
                        <div class="calendar-year-month-header">
                            <button type="button" class="calendar-year-month-name" aria-label="Open ${monthName} ${yearNumber}">${monthName} ${yearNumber}</button>
                            <span class="calendar-year-month-term" style="background:${termColor};">${termLabel}</span>
                        </div>
                        <div class="calendar-year-month-mini">
                            <div class="calendar-year-weekdays">${weekdayLabels.map((label) => `<span>${label}</span>`).join('')}</div>
                            <div class="calendar-year-days">${daysHtml}</div>
                        </div>
                    </article>
                `);
                monthCursor.setMonth(monthCursor.getMonth() + 1);
            }
            calendarYearView.innerHTML = cards.join('');
            calendarYearView.querySelectorAll('.calendar-year-month').forEach((element) => {
                element.addEventListener('click', (event) => {
                    const clickedDay = event.target.closest('.calendar-year-day');
                    if (clickedDay && clickedDay.dataset.yearDate) {
                        event.stopPropagation();
                        const target = clickedDay.dataset.yearDate;
                        if (clickedDay.classList.contains('has-event')) openYearDetailModal(target);
                        else setView('dayGridMonth', target);
                        return;
                    }
                    const targetDate = element.dataset.yearDate ? new Date(`${element.dataset.yearDate}T00:00:00`) : new Date();
                    setView('dayGridMonth', targetDate);
                });
            });
        }


window.PabasaCalendarViews=Object.freeze({yearRange,termMeta,renderYear});
})();
