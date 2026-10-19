const test=require('node:test');
const assert=require('node:assert/strict');
const {create}=require('../pabasa_site/pabasa_app/static/pabasa_app/js/prescribed_draft_queue.js');
const tracker=require('../pabasa_site/pabasa_app/static/pabasa_app/js/prescribed_pending_saves.js');
function storage(){const entries=new Map();return {getItem:k=>entries.get(k),setItem:(k,v)=>entries.set(k,v),removeItem:k=>entries.delete(k)};}
function queue(options={}) {return create({key:'student:term:activity',storage:storage(),revision:0,restored:()=>{},save:async()=>1,delay:100000,...options});}
test('30 students recover an offline drawing after refresh',async()=>{
  const saved=storage();
  await Promise.all(Array.from({length:30},async(_,id)=>{
    const key=`${id}:term1:drawing`;
    const first=queue({key,storage:saved,save:async()=>{throw Error('offline');}});
    first.schedule({text:`draft ${id}`,strokes:[]},0);
    await assert.rejects(first.flush(),/offline/);
    let restored;
    const next=queue({key,storage:saved,restored:d=>restored=d});
    assert.equal(restored.text,`draft ${id}`);await next.flush();assert.equal(next.pending(),false);
    first.clear();
  }));
});
test('keystrokes coalesce into one latest draft',async()=>{
  let calls=0,text;
  const q=queue({save:async draft=>{calls++;text=draft.text;return 1;}});
  for(let i=0;i<30;i++)q.schedule({text:String(i)},0);
  await q.flush();assert.equal(calls,1);assert.equal(text,'29');
});
test('edits arriving during a slow save follow it with the newest revision',async()=>{
  let resolve, calls=0;
  const q=queue({save:async()=>{calls++;if(calls===1)await new Promise(r=>resolve=r);return calls;}});
  q.schedule({text:'one'},0);const pending=q.flush();q.schedule({text:'two'},0);resolve();
  await pending;assert.equal(calls,2);assert.equal(q.pending(),false);
});
test('newer server progress is not overwritten by a stale tab backup',async()=>{
  const saved=storage();saved.setItem('student:term:activity',JSON.stringify({revision:0,at:Date.now(),draft:{text:'backup'}}));
  let applied=false;
  const q=queue({storage:saved,revision:1,restored:()=>applied=true});
  assert.equal(applied,false);assert.equal(q.pending(),false);assert.equal(q.recovery().text,'backup');q.clear();
});
test('backups cannot leak between accounts or terms',async()=>{
  const saved=storage();const one=queue({key:'1:term1',storage:saved});one.schedule({text:'private'},0);
  let applied=false;const two=queue({key:'2:term1',storage:saved,restored:()=>applied=true});
  const three=queue({key:'1:term2',storage:saved,restored:()=>applied=true});
  assert.equal(applied,false);one.clear();two.clear();three.clear();
});
test('leaving waits for a pending response and remembers its current revision',async()=>{
  const q=tracker.create();let finish;
  const response=new Promise(r=>finish=r);q.track('/progress/',response);let left=false;
  const leave=q.flush().then(()=>left=true);await Promise.resolve();assert.equal(left,false);
  finish(new Response(JSON.stringify({success:true,state:{revision:5}}),{status:200}));await leave;
  assert.equal(left,true);assert.equal(q.state('/progress/').revision,5);
});
for(const status of [400,401,403,409,500,503])test(`failed HTTP ${status} keeps navigation blocked until a successful save`,async()=>{
  const q=tracker.create();q.track('/progress/',Promise.resolve(new Response(JSON.stringify({success:false,error:'unsaved'}),{status})));
  await assert.rejects(q.flush(),/unsaved/);
  q.track('/progress/',Promise.resolve(new Response(JSON.stringify({success:true,state:{revision:2}}))));
  await q.flush();assert.equal(q.state('/progress/').revision,2);
});
test('lost connection prevents a false saved result',async()=>{
  const q=tracker.create();q.track('/progress/',Promise.reject(Error('offline')));await assert.rejects(q.flush(),/offline/);
});
