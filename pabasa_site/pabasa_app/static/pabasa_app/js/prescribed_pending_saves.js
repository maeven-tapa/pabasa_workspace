(function(root) {
  'use strict';
  function create() {
    const pending=new Set(),failed=new Map(),states=new Map();
    function track(route, request) {
      const checked=request.then(async response=>{
        const result=await response.clone().json();
        if(!response.ok||result.success!==true)throw Error(result.error||'Your work could not be saved. Try again.');
        failed.delete(route);
        const state=result.state||result.progress?.state;
        if(state)states.set(route,state);
      }).catch(error=>{failed.set(route,error);}).finally(()=>pending.delete(checked));
      pending.add(checked);
      return request;
    }
    async function flush() {
      while(pending.size)await Promise.all([...pending]);
      if(failed.size)throw [...failed.values()][0];
    }
    return {track,flush,state:route=>states.get(route),pending:()=>pending.size};
  }
  if(typeof module!=='undefined'&&module.exports)module.exports={create};
  else {
    // Later sessions have their own controls. Track their saves too, so the
    // common leave dialog can drain writes before navigating away.
    if(!root.PabasaPrescribedPending)root.PabasaPrescribedPending=create();
    if(root.fetch&&!root.__aralSaveTracking){
      root.__aralSaveTracking=true;
      const fetch=root.fetch.bind(root);
      root.fetch=(input,init={})=>{
        const route=String(input?.url||input||'');
        const request=fetch(input,init);
        const readingAudio=init.body instanceof FormData&&init.body.has('audio')&&/\/(?:progress|activity-progress)\//.test(route);
        if(!readingAudio&&/\/(?:progress|activity-progress|complete|recording)\//.test(route)&&String(init.method||input?.method||'GET').toUpperCase()==='POST')root.PabasaPrescribedPending.track(route,request);
        return request;
      };
      root.addEventListener('beforeunload',event=>{
        if(root.PabasaPrescribedPending.pending()){event.preventDefault();event.returnValue='';}
      });
    }
  }
})(typeof window!=='undefined'?window:globalThis);
