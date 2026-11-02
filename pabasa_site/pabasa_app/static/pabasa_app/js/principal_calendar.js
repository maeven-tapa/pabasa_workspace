/* Published shared schedule. No Principal mutation or student-progress controls. */
(() => {
  'use strict';
  const grid=document.getElementById('principalMonthGrid');
  if(!grid)return;
  const status=document.getElementById('principalCalendarStatus');
  if(!window.FullCalendar||!window.PabasaCalendarViews){status.textContent='Calendar could not load. Reload the page to try again.';return;}
  let events=JSON.parse(document.getElementById('principal-calendar-events').textContent);
  let config=JSON.parse(document.getElementById('principal-calendar-config').textContent);
  const colors=window.PabasaCalendarPalette.colors;
  const yearGrid=document.getElementById('principalYearView');
  const modal=document.getElementById('principalEventModal');
  const title=document.getElementById('principalMonthLabel');
  const viewField=document.getElementById('principalCalendarView');
  const modes={month:'dayGridMonth',week:'timeGridWeek',year:'year'};
  const requested=new URL(location.href).searchParams.get('view');
  let activeView=Object.hasOwn(modes,requested)?requested:'month';
  function showDetails(rows,date){
    document.getElementById('principalEventModalTitle').textContent=date?`Events on ${date}`:'Event details';
    const body=document.getElementById('principalEventDetails');body.replaceChildren();
    for(const event of rows){
      const item=document.createElement('article');item.className='principal-calendar-detail';
      const heading=document.createElement('h3');heading.textContent=event.title;
      const details=document.createElement('p');details.className='principal-note';
      details.textContent=`${event.start} – ${event.end_date||event.start} · ${event.event_type_label||'School event'} · Term ${event.term} · Read-only`;
      const description=document.createElement('p');description.className='principal-calendar-description';description.textContent=event.description||'No description provided.';
      item.append(heading,details,description);body.append(item);
    }
    bootstrap.Modal.getOrCreateInstance(modal).show();
  }
  function yearView(){
    window.PabasaCalendarViews.renderYear({element:yearGrid,events,rangeEvents:config.rangeEvents,
      schoolYear:config.schoolYear,termBlocks:config.termBlocks,today:config.today,
      onDate:date=>showDetails(events.filter(event=>event.start<=date&&(event.end_date||event.start)>=date),date),
      onMonth:date=>{setView('month',date);document.getElementById('principalMonth').focus({preventScroll:true});}});
  }
  const calendar=new FullCalendar.Calendar(grid,{
    initialView:activeView==='year'?'dayGridMonth':modes[activeView],initialDate:grid.dataset.initialDate||undefined,
    now:config.today,headerToolbar:false,height:'auto',dayMaxEvents:3,fixedWeekCount:false,
    editable:false,selectable:false,eventStartEditable:false,eventDurationEditable:false,
    allDayText:'All day',eventMinHeight:24,slotEventOverlap:false,
    views:{timeGridWeek:{titleFormat:{year:'numeric',month:'short',day:'numeric'}}},
    eventClick:info=>{const event=events.find(event=>String(event.id)===info.event.id);if(event)showDetails([event]);},
    dateClick:info=>{if(activeView==='month')setView('week',info.date);},
    datesSet:()=>{title.textContent=calendar.view.title;},
    eventDidMount:info=>{
      info.el.setAttribute('title',info.event.title);info.el.setAttribute('tabindex','0');info.el.setAttribute('role','button');
      info.el.addEventListener('keydown',event=>{if(event.key==='Enter'||event.key===' '){event.preventDefault();const row=events.find(row=>String(row.id)===info.event.id);if(row)showDetails([row]);}});
    }
  });
  function setView(view,date){
    activeView=view;viewField.value=view;
    const url=new URL(location.href);url.searchParams.set('view',view);history.replaceState(null,'',url);
    const isYear=view==='year';grid.hidden=isYear;yearGrid.classList.toggle('d-none',!isYear);
    for(const key of Object.keys(modes)){
      const button=document.getElementById('principal'+key[0].toUpperCase()+key.slice(1));const selected=key===view;
      button.classList.toggle('btn-primary',selected);button.classList.toggle('btn-outline-secondary',!selected);button.setAttribute('aria-pressed',String(selected));
    }
    document.getElementById('principalPrev').disabled=isYear;document.getElementById('principalNext').disabled=isYear;
    if(isYear){yearView();title.textContent=config.schoolYear?`School Year ${config.schoolYear}`:'Year overview';}
    else{calendar.changeView(modes[view],date);calendar.updateSize();}
  }
  function renderEvents(){
    calendar.removeAllEvents();calendar.addEventSource(events.map(event=>({...event,id:String(event.id),allDay:true,
      color:colors[event.event_type]||colors.other,textColor:['school_opening','aral_2','holiday','midline_assessment'].includes(event.event_type)?'#0F2D45':'#fff'})));
    if(activeView==='year')yearView();
  }
  calendar.render();renderEvents();setView(activeView);
  const selected=new URL(location.href).searchParams.get('event');const event=events.find(event=>String(event.id)===selected);
  if(event){setView('month',event.start);showDetails([event]);}
  window.PabasaCalendarLegend.render(document.getElementById('principalCalendarLegend'));
  for(const mode of Object.keys(modes))document.getElementById('principal'+mode[0].toUpperCase()+mode.slice(1)).addEventListener('click',()=>setView(mode));
  document.getElementById('principalPrev').onclick=()=>calendar.prev();document.getElementById('principalNext').onclick=()=>calendar.next();
  document.getElementById('principalToday').onclick=()=>{if(activeView==='year')setView('month',config.today);else calendar.gotoDate(config.today);};
  let refreshing=false;
  async function refresh(){
    if(refreshing)return;refreshing=true;status.textContent='Updating shared schedule…';
    try{
      const url=new URL(location.href);url.searchParams.set('format','json');
      const response=await fetch(url,{headers:{Accept:'application/json'},cache:'no-store'});
      if(!response.ok)throw Error();const data=await response.json();if(!Array.isArray(data.events))throw Error();
      events=data.events;config=data.calendar;calendar.setOption('now',config.today);renderEvents();
      status.textContent='Shared calendar updated.';
    }catch(_){status.textContent='Unable to update the schedule. Reload the page to try again.';}
    finally{refreshing=false;}
  }
  document.addEventListener('visibilitychange',()=>{if(!document.hidden)refresh();});
})();
