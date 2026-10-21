// Render real local Django fixtures with APIs fulfilled in memory. No progress writes.
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const runtime=path.join(process.env.USERPROFILE,'.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules');
const pw=require(path.join(runtime,'playwright-core')),{PNG}=require(path.join(runtime,'pngjs'));
const root=path.resolve(__dirname,'..'),dir=path.join(root,'tmp/prescribed-responsive-audit'),assets=path.join(root,'pabasa_site/pabasa_app/static');
const aliases=JSON.parse(fs.readFileSync(path.join(root,'pabasa_site/pabasa_app/static_image_aliases.json'))),results=[],errors=[];
const url='http://localhost:9877/dashboard/assessment/activity/prescribed/lesson8-gawain1/';
const quick=Boolean(process.env.PABASA_EE_QUICK),dpr=Number(process.env.PABASA_AUDIT_DPR||1);
const sizes=quick?[[1366,768],[1920,1080],[2560,1440]]:[[1366,768],[1440,900],[1680,924],[1920,1080],[2560,1440],[3440,1440],[768,1024],[375,812],[320,568],[2560,1440],[1366,768]];
// Existing buttons transition all dimensions for .16s. Wait for actual frames
// to settle after resizing instead of assuming a wall-clock delay is enough.
async function settle(page){await page.evaluate(async()=>{await document.fonts.ready;await new Promise((resolve,reject)=>{let last='',stable=0;const start=performance.now();function tick(){const signature=JSON.stringify([...document.querySelectorAll('#app,#app canvas,#app button,#app .eyebrow,#app h1,#app [role="progressbar"]')].map(e=>{const r=e.getBoundingClientRect(),s=getComputedStyle(e);return[r.x,r.y,r.width,r.height,s.font,s.padding]}));stable=signature===last?stable+1:0;last=signature;if(stable>=6)return resolve();if(performance.now()-start>15000)return reject(Error('Layout did not settle'));requestAnimationFrame(tick)}requestAnimationFrame(tick)})})}
function inkBounds(buffer,dx,dy){const p=PNG.sync.read(buffer);let left=p.width,right=-1,top=p.height,bottom=-1;for(let y=0;y<p.height;y++)for(let x=0;x<p.width;x++){const i=(y*p.width+x)*4;if(p.data[i]<150&&p.data[i+1]<150&&p.data[i+2]<150){left=Math.min(left,x);right=Math.max(right,x);top=Math.min(top,y);bottom=Math.max(bottom,y)}}assert.ok(right>=left,'No guide pixels');return{left:left/dpr-dx,right:(right+1)/dpr-dx,top:top/dpr-dy,bottom:(bottom+1)/dpr-dy}}
(async()=>{const browser=await pw.chromium.launch({channel:'chrome',headless:true,args:['--disable-gpu']});try{
 for(const row of (quick?[0,1]:[0,1,2]))for(const variant of (quick?['before']:['before','after'])){
  const context=await browser.newContext({viewport:{width:1366,height:768},deviceScaleFactor:dpr,reducedMotion:'reduce'});
  await context.route('**/*',route=>{const u=new URL(route.request().url());if(u.origin!=='http://localhost:9877')return route.abort();if(u.pathname.startsWith('/static/')){
   if(variant==='before'&&(/lesson8_gawain1_spacing\.css$/.test(u.pathname)||u.pathname.endsWith('/lesson7_handwriting_guide.js')))return route.fulfill({body:'',contentType:u.pathname.endsWith('.css')?'text/css':'application/javascript'});
   const key=decodeURIComponent(u.pathname.slice(8)),file=path.resolve(assets,aliases[key]||key);assert.ok(file.startsWith(assets+path.sep));return fs.existsSync(file)?route.fulfill({path:file}):route.fulfill({status:404});
  }if(u.href===url){let html=fs.readFileSync(path.join(dir,'lesson8-gawain1-current.html'),'utf8');html=html.replace(/(<script id="handwriting-data"[^>]*>)([\s\S]*?)(<\/script>)/,(_,a,json,b)=>{const data=JSON.parse(json);data.progress={...(data.progress||{}),current_index:row,completed_items:row,activity_completed:row===2};return a+JSON.stringify(data)+b});return route.fulfill({contentType:'text/html',body:html})}return route.fulfill({json:{success:true}})});
  await context.addInitScript(()=>{const Native=window.Audio;window.Audio=function(...args){const audio=new Native(...args);audio.play=()=>{setTimeout(()=>audio.dispatchEvent(new Event('ended')),15);return Promise.resolve()};return audio};if(window.speechSynthesis)window.speechSynthesis.speak=()=>{}});
  const page=await context.newPage();page.on('pageerror',e=>errors.push(e.message));await page.goto(url,{waitUntil:'load'});await page.evaluate(()=>document.fonts.ready);const gate=page.locator('.lesson-start-actions button');if(await gate.count()&&await gate.first().isVisible())await gate.first().click();await page.waitForTimeout(150);
  for(const [width,height]of (row===2?[[1366,768],[2560,1440]]:sizes)){
   await page.setViewportSize({width,height});await page.mouse.move(0,0);await settle(page);await page.evaluate(()=>window.scrollTo(0,0));
   const r={row,variant,width,height,dpr,...await page.evaluate(()=>{
    const card=document.querySelector('#app'),canvas=card.querySelector('canvas'),rect=e=>e.getBoundingClientRect().toJSON(),visible=e=>{const r=e.getBoundingClientRect(),s=getComputedStyle(e);return r.width&&r.height&&s.visibility!=='hidden'&&s.display!=='none'};
    const data={card:rect(card),nav:rect(document.querySelector('.back')),tools:rect(document.querySelector('.session3-controls-tools')),scroll:[document.documentElement.scrollWidth,document.documentElement.scrollHeight],parts:[...card.querySelectorAll('.eyebrow,h1,.sheet,button,.lesson8-g1-progress')].filter(visible).map(e=>({cls:e.className,tag:e.tagName,id:e.id,rect:rect(e),styles:Object.fromEntries(['font','padding','marginTop','marginBottom','gap'].map(k=>[k,getComputedStyle(e)[k]]))}))};
    if(canvas){const wrap=canvas.parentElement,style=getComputedStyle(wrap),model=wrap.querySelector('.model'),h=parseFloat(style.height),positions=style.backgroundPositionY.split(',').map(parseFloat),thicknesses=style.backgroundSize.split(',').map(s=>parseFloat(s.trim().split(/\s+/)[1]));data.canvas={rect:rect(canvas),width:canvas.width,height:canvas.height};data.guidelines=[style.backgroundImage,style.backgroundPosition,style.backgroundSize];data.wrap=rect(wrap);data.lines=positions.map((p,i)=>({top:(h-thicknesses[i])*p/100,bottom:(h-thicknesses[i])*p/100+thicknesses[i]}));data.model={rect:rect(model),text:model.textContent};data.progress=card.querySelector('.lesson8-g1-progress')?.dataset.state}
    return data;
   })};
   const debug=page.locator('.session3-controls-debug');await debug.evaluate(e=>e.hidden=false);r.debugCard=await page.locator('#app').evaluate(e=>e.getBoundingClientRect().toJSON());await debug.evaluate(e=>e.hidden=true);
   const tag=`lesson8-g1-row${row}-${width}x${height}-dpr${dpr}-${variant}`;await page.screenshot({path:path.join(dir,tag+'.png'),fullPage:width<1000,animations:'disabled'});
   if(row<2){const saved=await page.locator('.row').evaluate(w=>{const m=w.querySelector('.model'),old=[w.getAttribute('style'),m.getAttribute('style')];w.style.setProperty('background','#fff','important');m.style.setProperty('color','#000','important');return old});
    const clip={x:Math.floor(r.wrap.x),y:Math.floor(r.wrap.y),width:Math.ceil(r.wrap.right)-Math.floor(r.wrap.x),height:Math.ceil(r.wrap.bottom)-Math.floor(r.wrap.y)};
    const buffer=await page.screenshot({clip,animations:'disabled'});fs.writeFileSync(path.join(dir,tag+'-ink.png'),buffer);r.ink=inkBounds(buffer,r.wrap.x-clip.x,r.wrap.y-clip.y);r.guideErrors={top:r.ink.top-r.lines[row===1?1:0].bottom,bottom:r.ink.bottom-r.lines[2].top};
    await page.locator('.row').evaluate((w,old)=>[w,w.querySelector('.model')].forEach((e,i)=>old[i]===null?e.removeAttribute('style'):e.setAttribute('style',old[i])),saved);
   }
   results.push(r);
   if(variant==='after'){
    const b=results.find(x=>x.variant==='before'&&x.row===row&&x.width===width&&x.height===height);
    if(row===2){assert.deepEqual(r.card,b.card,'Completion layout changed');continue}
    assert.equal(r.card.width,b.card.width,'Card width changed');assert.ok(width<1000?r.card.height<=b.card.height+1:r.card.height<b.card.height,'Card did not fit contents');assert.ok(Math.abs(r.card.x+r.card.width/2-width/2)<1,'Horizontal centering');assert.deepEqual(r.debugCard,r.card,'Debug moved card');assert.ok(r.scroll[0]<=width,'Horizontal overflow');
    if(width>=1000){assert.ok(Math.abs(r.card.y+r.card.height/2-height/2)<1,'Vertical centering');assert.ok(r.scroll[1]<=height,'Unnecessary desktop scrolling')}
    assert.deepEqual([r.canvas.width,r.canvas.height,r.canvas.rect.width,r.canvas.rect.height,r.guidelines],[b.canvas.width,b.canvas.height,b.canvas.rect.width,b.canvas.rect.height,b.guidelines],'Canvas dimensions or guidelines changed');assert.equal(r.progress,`${row+1}/2`,'Progress changed');
    // Ink bounds include integer/half-pixel raster rounding at DPR 1/2.
    assert.ok(Math.abs(r.guideErrors.top)<=1.5&&Math.abs(r.guideErrors.bottom)<=1.5,'Guide does not fit its handwriting boundaries');
    for(const nav of [r.nav,r.tools])assert.ok(nav.bottom<=r.card.y+1||nav.right<=r.card.x||nav.x>=r.card.right,'Navigation overlaps card');
    for(let i=0;i<r.parts.length;i++){const p=r.parts[i],old=b.parts[i];assert.deepEqual([p.cls,p.tag,p.id,p.rect.width,p.rect.height,p.styles],[old.cls,old.tag,old.id,old.rect.width,old.rect.height,old.styles],'Component sizing or styling changed');assert.ok(Math.abs((p.rect.x-r.card.x)-(old.rect.x-b.card.x))<1,'Component horizontal alignment changed');assert.ok(Math.abs((p.rect.y-r.parts[0].rect.y)-(old.rect.y-b.parts[0].rect.y))<1,'Internal vertical spacing changed');assert.ok(p.rect.x>=r.card.x-1&&p.rect.right<=r.card.right+1&&p.rect.y>=r.card.y-1&&p.rect.bottom<=r.card.bottom+1,'Clipped component')}
    // Pointer accuracy and clear remain checks of the real activity listeners.
    const canvas=page.locator('canvas'),box=await canvas.boundingBox();await page.mouse.move(box.x+box.width*.6,box.y+box.height*.55);await page.mouse.down();await page.mouse.move(box.x+box.width*.7,box.y+box.height*.55,{steps:6});await page.mouse.up();
    const ink=await canvas.evaluate(c=>{const d=c.getContext('2d').getImageData(0,0,c.width,c.height);let left=c.width,right=-1,top=c.height,bottom=-1;for(let y=0;y<c.height;y++)for(let x=0;x<c.width;x++)if(d.data[(y*c.width+x)*4+3]>30){left=Math.min(left,x);right=Math.max(right,x);top=Math.min(top,y);bottom=Math.max(bottom,y)}return{x:(left+right)/2/c.width,y:(top+bottom)/2/c.height}});assert.ok(Math.abs(ink.x-.65)<.04&&Math.abs(ink.y-.55)<.06,'Pointer alignment changed');await page.locator('#clear').click();assert.ok(await canvas.evaluate(c=>!c.getContext('2d').getImageData(0,0,c.width,c.height).data.some((v,i)=>i%4===3&&v>0)),'Burahin failed');
   }
   console.log(`${variant} row${row} ${width}x${height}: card height ${r.card.height.toFixed(2)}, guide ${JSON.stringify(r.guideErrors)}`);
  }await context.close();
 }assert.deepEqual(errors,[],'Browser errors');console.log(`PASS ${results.filter(x=>x.variant==='after').length} rendered Lesson 8 Gawain 1 layouts`);
 }finally{await browser.close();fs.writeFileSync(path.join(dir,`lesson8-g1-spacing-${quick?'audit':`dpr${dpr}`}.json`),JSON.stringify({results,errors},null,2))}
})().catch(e=>{console.error(e);process.exitCode=1});
