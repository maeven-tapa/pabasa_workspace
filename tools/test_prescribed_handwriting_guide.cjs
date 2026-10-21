// Render real Django fixtures and local assets; no account or progress writes.
// The black-on-white crop measures visible glyph pixels, not an HTML line box.
const fs = require('node:fs'), path = require('node:path'), assert = require('node:assert/strict');
const root = path.resolve(__dirname, '..'), dir = path.join(root, 'tmp/prescribed-responsive-audit');
const runtime = path.join(process.env.USERPROFILE, '.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules');
const pw = require(path.join(runtime, 'playwright-core')), {PNG} = require(path.join(runtime, 'pngjs'));
const assets = path.join(root, 'pabasa_site/pabasa_app/static');
const aliases = JSON.parse(fs.readFileSync(path.join(root, 'pabasa_site/pabasa_app/static_image_aliases.json')));
const url = 'http://localhost:9877/dashboard/assessment/activity/prescribed/lesson7-gawain2c/';
const sizes = [[1366,768],[1440,900],[1920,1080],[2560,1440],[3440,1440],[768,1024],[375,812],[320,568]];
const results = [], errors = [];
const unchangedScreens = new Map();
const dpr = Number(process.env.PABASA_AUDIT_DPR || 1);

function inkBounds(buffer) {
  const image = PNG.sync.read(buffer), rows = [];
  let left = image.width, right = -1;
  for (let y=0;y<image.height;y++) {
    let ink = false;
    for (let x=0;x<image.width;x++) {
      const i = (y*image.width+x)*4;
      if (image.data[i]<150 && image.data[i+1]<150 && image.data[i+2]<150) {
        left = Math.min(left,x); right = Math.max(right,x); ink = true;
      }
    }
    if (ink) rows.push(y);
  }
  assert.ok(rows.length, 'No rendered guide pixels');
  const groups = [];
  for (const y of rows) {
    const last = groups.at(-1);
    if (!last || y>last.bottom+1) groups.push({top:y,bottom:y}); else last.bottom=y;
  }
  return {left:left/dpr,right:(right+1)/dpr,top:rows[0]/dpr,bottom:(rows.at(-1)+1)/dpr,
    groups:groups.map(g=>({top:g.top/dpr,bottom:(g.bottom+1)/dpr}))};
}

(async () => {
  const browser = await pw.chromium.launch({channel:'chrome',headless:true,args:['--disable-gpu']});
  try {
    for (const row of [0,1]) for (const variant of ['before','after']) {
      const context = await browser.newContext({viewport:{width:1366,height:768},deviceScaleFactor:dpr,reducedMotion:'reduce'});
      await context.route('**/*', route => {
        const u = new URL(route.request().url());
        if(u.origin!=='http://localhost:9877') return route.abort();
        if(u.pathname.startsWith('/static/')) {
          if(variant==='before' && u.pathname.endsWith('/lesson7_handwriting_guide.js')) return route.fulfill({contentType:'application/javascript',body:''});
          const k=decodeURIComponent(u.pathname.slice(8)), f=path.resolve(assets,aliases[k]||k);
          assert.ok(f.startsWith(assets+path.sep));
          return fs.existsSync(f)?route.fulfill({path:f}):route.fulfill({status:404});
        }
        if(u.href===url) {
          let html=fs.readFileSync(path.join(dir,'lesson7-gawain2c-current.html'),'utf8');
          html=html.replace(/(<script id="handwriting-data"[^>]*>)([\s\S]*?)(<\/script>)/,(_,a,data,b)=>{
            const value=JSON.parse(data); value.progress={...(value.progress||{}),current_index:row,completed_items:row,activity_completed:false};
            return a+JSON.stringify(value)+b;
          });
          return route.fulfill({contentType:'text/html',body:html});
        }
        return route.fulfill({json:{success:true}});
      });
      await context.addInitScript(()=>{
        const Native=window.Audio;
        window.Audio=function(...args){const a=new Native(...args);a.play=()=>{setTimeout(()=>a.dispatchEvent(new Event('ended')),15);return Promise.resolve()};return a};
        if(window.speechSynthesis) window.speechSynthesis.speak=()=>{};
      });
      const page=await context.newPage(); page.on('pageerror',e=>errors.push(e.message));
      await page.goto(url,{waitUntil:'load'}); await page.evaluate(()=>document.fonts.ready);
      await page.locator('.lesson-start-actions button').first().click();
      await page.waitForTimeout(150);
      // Keep the same page and row mounted throughout all viewport resizes.
      for(const [width,height] of [...sizes,[2560,1440],[1440,900],[1366,768]]) {
        await page.setViewportSize({width,height}); await page.waitForTimeout(80);
        await page.evaluate(()=>window.scrollTo(0,0));
        const geometry=await page.evaluate(()=>{
          const wrap=document.querySelector('.canvas-wrap'), canvas=wrap.querySelector('canvas'), model=wrap.querySelector('.model');
          const style=getComputedStyle(wrap), h=parseFloat(style.height);
          const position=style.backgroundPositionY.split(',').map(parseFloat), thickness=style.backgroundSize.split(',').map(s=>parseFloat(s.trim().split(/\s+/)[1]));
          return {card:document.querySelector('#app').getBoundingClientRect().toJSON(),
            canvas:canvas.getBoundingClientRect().toJSON(),buffer:[canvas.width,canvas.height],
            guidelines:[style.backgroundImage,style.backgroundPosition,style.backgroundSize],
            lines:position.map((p,i)=>({top:(h-thickness[i])*p/100,bottom:(h-thickness[i])*p/100+thickness[i]})),
            wrap:wrap.getBoundingClientRect().toJSON(),model:model.getBoundingClientRect().toJSON(),
            scrollWidth:document.documentElement.scrollWidth};
        });
        const tag=`guide-left-row${row}-${width}x${height}-dpr${dpr}-${variant}`;
        await page.screenshot({path:path.join(dir,tag+'.png'),fullPage:width<1000,animations:'disabled'});
        // Hide only the intentionally corrected glyph. Regular desktop pixels,
        // including the original stripes, must match apart from one-channel-level
        // paint rounding. Record mobile fractional-border differences separately.
        await page.locator('.model').evaluate(e=>e.style.visibility='hidden');
        const unchanged=PNG.sync.read(await page.screenshot({fullPage:width<1000,animations:'disabled'}));
        await page.locator('.model').evaluate(e=>e.style.removeProperty('visibility'));
        const screenKey=`${row}-${width}-${height}`;
        let otherPixelDifferences=0, otherMaterialPixelDifferences=0;
        if(variant==='before') unchangedScreens.set(screenKey,unchanged);
        else {
          const b=unchangedScreens.get(screenKey);
          assert.ok(b.width===unchanged.width && b.height===unchanged.height,`${tag}: screenshot dimensions changed`);
          for(let i=0;i<b.data.length;i+=4) {
            const delta=Math.max(Math.abs(b.data[i]-unchanged.data[i]),Math.abs(b.data[i+1]-unchanged.data[i+1]),Math.abs(b.data[i+2]-unchanged.data[i+2]));
            if(delta>0) otherPixelDifferences++;
            if(delta>1) otherMaterialPixelDifferences++;
          }
          if(otherPixelDifferences) {
            fs.writeFileSync(path.join(dir,tag+'-other-before.png'),PNG.sync.write(b));
            fs.writeFileSync(path.join(dir,tag+'-other-after.png'),PNG.sync.write(unchanged));
          }
          if(width>=768) assert.equal(otherMaterialPixelDifferences,0,`${tag}: desktop pixels outside the guide changed`);
        }
        const previous=await page.locator('.canvas-wrap').evaluate(wrap=>{
          const m=wrap.querySelector('.model'), old=[wrap.getAttribute('style'),m.getAttribute('style')];
          wrap.style.setProperty('background','#fff','important');m.style.setProperty('color','#000','important');return old;
        });
        // Integer CSS clip bounds make the fractional row origin explicit.
        // Locator screenshots otherwise round that origin differently at DPR 2.
        const clip={x:Math.floor(geometry.wrap.x),y:Math.floor(geometry.wrap.y),
          width:Math.ceil(geometry.wrap.right)-Math.floor(geometry.wrap.x),
          height:Math.ceil(geometry.wrap.bottom)-Math.floor(geometry.wrap.y)};
        const crop=await page.screenshot({clip,animations:'disabled'}), ink=inkBounds(crop);
        const dx=geometry.wrap.x-clip.x, dy=geometry.wrap.y-clip.y;
        ink.left-=dx;ink.right-=dx;ink.top-=dy;ink.bottom-=dy;
        ink.groups.forEach(g=>{g.top-=dy;g.bottom-=dy});
        fs.writeFileSync(path.join(dir,tag+'-ink.png'),crop);
        await page.locator('.canvas-wrap').evaluate((wrap,old)=>{
          [wrap,wrap.querySelector('.model')].forEach((e,i)=>old[i]===null?e.removeAttribute('style'):e.setAttribute('style',old[i]));
        },previous);
        const body=row===1?ink.groups.at(-1):ink;
        const r={row,variant,width,height,dpr,...geometry,ink,otherPixelDifferences,otherMaterialPixelDifferences,
          topError:body.top-geometry.lines[row===1?1:0].bottom,
          bottomError:ink.bottom-geometry.lines[2].top,
          leftError:ink.left-geometry.wrap.width*.13};
        results.push(r);
        if(variant==='after') {
          assert.ok(Math.abs(r.topError)<1.5,`${tag}: ink top error ${r.topError}`);
          assert.ok(Math.abs(r.bottomError)<1.5,`${tag}: ink bottom error ${r.bottomError}`);
          assert.ok(Math.abs(r.leftError)<1.5,`${tag}: left guide inset error ${r.leftError}`);
          assert.ok(ink.top>=geometry.lines[0].bottom-1.5,`${tag}: dot above upper guide`);
          assert.ok(r.scrollWidth<=width,`${tag}: horizontal overflow`);
          const b=results.find(x=>x.variant==='before'&&x.row===row&&x.width===width&&x.height===height);
          assert.deepEqual([r.card,r.canvas,r.buffer,r.guidelines],[b.card,b.canvas,b.buffer,b.guidelines],`${tag}: activity geometry changed`);
        }
        console.log(`${variant} row${row} ${width}x${height}: top ${r.topError.toFixed(2)}, bottom ${r.bottomError.toFixed(2)}, left ${r.leftError.toFixed(2)}`);
      }
      await context.close();
    }
    assert.deepEqual(errors,[],'Browser script errors');
    console.log(`PASS ${results.filter(r=>r.variant==='after').length} rendered guide alignment checks at DPR ${dpr}`);
  } finally {
    await browser.close();
    fs.writeFileSync(path.join(dir,`handwriting-guide-left-dpr${dpr}.json`),JSON.stringify({results,errors},null,2));
  }
})().catch(e=>{console.error(e);process.exitCode=1});
