(function (root) {
  'use strict';
  function create({key, storage, revision, save, restored, delay=1000, onError=()=>{}}) {
    let pending=null, running=null, timer=null, recovery=null;
    try {
      const entry=JSON.parse(storage.getItem(key)||'null');
      // Never apply an old tab's draft over a newer server save or verdict.
      if(entry && entry.revision===revision && Date.now()-entry.at<86400000) {
        pending=entry;restored(structuredClone(entry.draft));
      } else if(entry && Date.now()-entry.at<86400000)recovery=entry.draft;
      else storage.removeItem(key);
    } catch (_) {}
    function persist() {try {if(pending)storage.setItem(key,JSON.stringify(pending));else storage.removeItem(key);}catch(_) {}}
    function schedule(draft, currentRevision) {
      pending={draft:structuredClone(draft),revision:currentRevision,at:Date.now()};persist();
      clearTimeout(timer);timer=setTimeout(()=>flush().catch(onError),delay);
    }
    async function flush() {
      clearTimeout(timer);
      if(running) {await running;if(pending)return flush();return;}
      if(!pending)return;
      const entry=pending;
      running=(async()=>{
        const nextRevision=await save(structuredClone(entry.draft));
        if(pending===entry)pending=null;
        else if(pending)pending.revision=nextRevision;
        persist();
      })();
      try {await running;} finally {running=null;}
      if(pending)await flush();
    }
    function clear() {clearTimeout(timer);pending=null;recovery=null;persist();}
    if(pending)timer=setTimeout(()=>flush().catch(onError),delay);
    return {schedule,flush,clear,pending:()=>Boolean(pending),recovery:()=>recovery};
  }
  const api={create};
  if(typeof module!=='undefined'&&module.exports)module.exports=api;
  else root.PrescribedDraftQueue=api;
})(typeof window!=='undefined'?window:globalThis);
