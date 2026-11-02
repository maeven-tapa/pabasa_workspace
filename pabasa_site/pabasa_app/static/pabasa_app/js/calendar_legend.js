/* One legend and palette for Admin and Principal calendar views. */
window.PabasaCalendarLegend=Object.freeze({
entries: Object.freeze([
            { key: 'school_opening', label: 'Opening Block' },
            { key: 'pre_assessment', label: 'Pre-Assessment' },
            { key: 'midline_assessment', label: 'Mid-Assessment' },
            { key: 'post_assessment', label: 'Post-Assessment' },
            { key: 'school_closing', label: 'Closing Block' },
            { key: 'aral_1', label: 'ARAL 1 — After Class' },
            { key: 'aral_2', label: 'ARAL 2 — End of Term (last 1–5 days)' },
            { key: 'start_of_classes', label: 'Start of Classes' },
            { key: 'end_of_classes', label: 'End of Classes' },
            { key: 'holiday', label: 'Holiday' },
            { key: 'examination', label: 'Examination Week' },
            { key: 'other', label: 'Other Activity' },
        ]),
render(element) {
 if(!element)return;
 element.replaceChildren();
 for(const {key,label} of this.entries){
  const item=document.createElement('span');item.className='calendar-legend-item';item.dataset.category=key;
  const swatch=document.createElement('span');swatch.className='calendar-legend-swatch';swatch.style.backgroundColor=window.PabasaCalendarPalette.colors[key];swatch.setAttribute('aria-hidden','true');
  const text=document.createElement('span');text.textContent=label;item.append(swatch,text);element.append(item);
 }
}
});
