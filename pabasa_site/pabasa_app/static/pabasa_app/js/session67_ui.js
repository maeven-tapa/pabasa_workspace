(() => {
  'use strict';
  const node=document.getElementById('prescribed-activity-data');
  let data;try{data=JSON.parse(node?.textContent||'{}')}catch(_){return}
  const key=String(data.activity_key||'');
  const session6=new Set(['lesson-16-gawain-1','lesson-16-gawain-2','lesson-16-gawain-3','session-6-lesson-16-gawain-4','lesson-17-18-gawain-5','lesson-17-18-gawain-6','lesson-17-18-gawain-7','lesson-17-18-gawain-8','lesson-17-18-gawain-9']);
  if(!session6.has(key)&&!key.startsWith('session-7-'))return;
  const label='Bumalik sa Aking Gawain';
  const listUrl=document.querySelector('a.back,a.l16g3-back')?.getAttribute('href')||'/dashboard/assessment/';
  // Load last so activity-specific historical back-link rules cannot override it.
  const css=document.createElement('link');css.rel='stylesheet';css.href='/static/pabasa_app/css/session67_reference.css?v=2';document.head.append(css);
  function refresh(){
    document.querySelectorAll('[data-session6-controls],[data-prescribed-session-controls]').forEach(root=>{
      const buttons=['-help-btn','-mic-toggle','-audio-settings-btn'].map(suffix=>root.querySelector(`[id$="${suffix}"]`));
      if(buttons.every(Boolean)&&buttons.some((button,index)=>root.children[index]!==button))root.append(...buttons);
    });
    document.querySelectorAll('a[href]').forEach(link=>{
      if(link.getAttribute('href')===listUrl&&link.textContent!==label){link.textContent=label;link.setAttribute('aria-label',label)}
    });
    document.querySelectorAll('button[id$="-back"]').forEach(button=>{if(button.textContent!==label)button.textContent=label});
    document.querySelectorAll('.lesson-start-modal').forEach(modal=>{
      if(modal.querySelector('.session67-list-link'))return;
      const link=document.createElement('a');link.className='session67-list-link';link.href=listUrl;link.textContent=label;modal.append(link);
    });
    document.querySelectorAll('[id$="-help-btn"]').forEach(button=>button.setAttribute('aria-label','Tulong'));
    document.querySelectorAll('[id$="-audio-settings-btn"]').forEach(button=>button.setAttribute('aria-label','I-pause ang gawain'));
    document.querySelectorAll('[id$="-mic-toggle"]').forEach(button=>{
      const muted=button.getAttribute('aria-pressed')==='true';const name=muted?'I-unmute ang mikropono':'I-mute ang mikropono';
      if(button.getAttribute('aria-label')!==name)button.setAttribute('aria-label',name);
      button.title=name;
    });
  }
  if(key.startsWith('session-7-')){
    const NativeAudio=window.Audio,players=new Set();let paused=false;
    window.Audio=function(...args){
      players.forEach(player=>player.pause());
      const player=new NativeAudio(...args),play=player.play.bind(player);players.add(player);
      player.play=()=>paused?Promise.reject(new DOMException('Activity paused.','AbortError')):play();
      player.addEventListener('ended',()=>players.delete(player),{once:true});
      player.addEventListener('error',()=>players.delete(player),{once:true});
      return player;
    };
    window.Audio.prototype=NativeAudio.prototype;
    const stop=()=>players.forEach(player=>player.pause());
    addEventListener('session7-prescribed-cancel',stop);
    addEventListener('prescribed-session-paused',()=>{paused=true;stop()});
    addEventListener('prescribed-session-resumed',()=>{paused=false});
    addEventListener('pagehide',stop,{once:true});
  }
  document.addEventListener('click',event=>{
    if(event.target.closest('[id$="-help-btn"]')){
      window.Basahin?.cancelAll?.();
      dispatchEvent(new CustomEvent(key.startsWith('session-7-')?'session7-prescribed-cancel':'session6-prescribed-cancel',{detail:{reason:'help'}}));
    }
  },true);
  refresh();new MutationObserver(refresh).observe(document.body,{childList:true,subtree:true});
  document.addEventListener('click',event=>{if(event.target.closest('[id$="-mic-toggle"]'))queueMicrotask(refresh)});
})();
