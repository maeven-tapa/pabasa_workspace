const test = require('node:test');
const assert = require('node:assert/strict');
const { create } = require('../pabasa_site/pabasa_app/static/pabasa_app/js/practice_completion_queue.js');
function storage() { const values = new Map(); return {getItem: k => values.get(k), setItem: (k,v) => values.set(k,v)}; }
const response = (status=200, data={success:true}) => ({status, ok:status===200, text:async()=>JSON.stringify(data)});
function job(id='42:attempt', hunt=false) {
  return {id, payload:{material_id:42, activity_type:'practice', stars_earned:hunt?0:3},
    awards:hunt?[{student_id:7,level_id:42,attempt_id:'attempt',award_type:'word',word_index:0}]:[],
    huntCompletion:hunt?{student_id:7,level_id:42,attempt_id:'attempt',award_type:'completion'}:null};
}
function queue(overrides={}) { return create({studentId:7, storage:storage(), fetch:async()=>response(), csrf:()=> 'csrf', delay:async()=>{}, ...overrides}); }
test('30 distinct students preserve their completion through a lost connection and reload', async()=>{
  const shared=storage();
  await Promise.all(Array.from({length:30},async(_,studentId)=>{
    const first=queue({studentId,storage:shared,fetch:async()=>{throw new TypeError('offline');}});
    assert.equal(await first.enqueue(job()),false); assert.equal(first.pending(),1);
    const restored=queue({studentId,storage:shared});
    assert.equal(restored.pending(),1); assert.equal(await restored.flush(),true); assert.equal(restored.pending(),0);
  }));
});
test('simultaneous completion calls share one request and snapshot original evidence', async()=>{
  let release, calls=0, sent;
  const q=queue({fetch:async(_,opts)=>{calls++; sent=JSON.parse(opts.body); await new Promise(r=>release=r);return response();}});
  const payload=job();const one=q.enqueue(payload);const two=q.enqueue(payload);
  payload.payload.stars_earned=99;assert.equal(calls,1);release();
  assert.equal(await one,true);assert.equal(await two,true);assert.equal(sent.stars_earned,3);assert.equal(sent.student_id,7);
});
for (const status of [401,403,400,409]) test(`HTTP ${status} stays pending without automatic retry`,async()=>{
  let calls=0;const q=queue({fetch:async()=>{calls++;return response(status,{success:false});}});
  assert.equal(await q.enqueue(job()),false);assert.equal(calls,1);assert.equal(q.pending(),1);
});
for (const status of [429,500,503]) test(`HTTP ${status} uses bounded one-second retries`,async()=>{
  let calls=0;const delays=[];const q=queue({delay:async ms=>delays.push(ms),fetch:async()=>++calls===1?response(status):response()});
  assert.equal(await q.enqueue(job()),true);assert.equal(calls,2);assert.deepEqual(delays,[1000]);
});
test('Hunt word deposits replay before completion, retaining the same attempt ID',async()=>{
  const calls=[];const q=queue({fetch:async(url,opts)=>{calls.push({url,body:JSON.parse(opts.body)});return response();}});
  assert.equal(await q.enqueue(job(undefined,true)),true);
  assert.equal(calls[0].body.award_type,'word');assert.equal(calls[1].body.activity_type,'practice');assert.equal(calls[2].body.award_type,'completion');
  assert.equal(calls[0].body.attempt_id,calls[2].body.attempt_id);
});
test('Hunt bonus failure cannot report completion as saved and survives a restart',async()=>{
  const saved=storage();let finalized=0;
  const q=queue({storage:saved,onSaved:()=>finalized++,fetch:async(_,opts)=>JSON.parse(opts.body).award_type==='completion'?response(409,{success:false}):response()});
  assert.equal(await q.enqueue(job(undefined,true)),false);assert.equal(finalized,0);
  const next=queue({storage:saved,onSaved:()=>finalized++});assert.equal(await next.flush(),true);assert.equal(finalized,1);
});
test('an interrupted page retains an already-dispatched completion',async()=>{
  const saved=storage();let finish;
  const q=queue({storage:saved,fetch:()=>new Promise(resolve=>finish=resolve)});
  const pending=q.enqueue(job());assert.equal(queue({storage:saved}).pending(),1);
  finish(response());assert.equal(await pending,true);
});
test('a second completion added during a save is drained by the same worker',async()=>{
  let finish,calls=0;const q=queue({fetch:async()=>{calls++;if(calls===1)await new Promise(resolve=>finish=resolve);return response();}});
  const first=q.enqueue(job('first'));const second=q.enqueue(job('second'));finish();
  assert.equal(await first,true);assert.equal(await second,true);assert.equal(calls,2);assert.equal(q.pending(),0);
});
test('one failed job remains visibly pending after another job saves',async()=>{
  const states=[];let release;
  const q=queue({onStatus:s=>states.push(s),fetch:async(_,opts)=>{
    if(JSON.parse(opts.body).stars_earned===1){await new Promise(resolve=>release=resolve);return response(401,{success:false});}
    return response();
  }});
  const first=job('failed');first.payload.stars_earned=1;
  const pending=q.enqueue(first);q.enqueue(job('healthy'));release();
  assert.equal(await pending,false);assert.equal(states.at(-1),'pending');assert.equal(q.pending(),1);
});
test('queues remain isolated when another student signs in on the same browser',async()=>{
  const saved=storage();const first=queue({storage:saved,fetch:async()=>response(401,{success:false})});
  await first.enqueue(job());assert.equal(queue({studentId:8,storage:saved}).pending(),0);
  assert.equal(queue({studentId:7,storage:saved}).pending(),1);
});
test('HTML server page leaves evidence pending and manual retry can finish',async()=>{
  let healthy=false;const q=queue({fetch:async()=>healthy?response():({status:502,ok:false,text:async()=>'<html>Gateway</html>'})});
  assert.equal(await q.enqueue(job()),false);healthy=true;assert.equal(await q.flush(),true);
});
