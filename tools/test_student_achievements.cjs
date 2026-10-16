// Actual dashboard template/scripts; synthetic student context and local HTTP only.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const {spawnSync} = require('node:child_process');
const {chromium} = require('playwright-core');
const root = path.resolve(__dirname, '..');
const staticRoot = path.join(root, 'pabasa_site/pabasa_app/static');
const rendered = spawnSync(path.join(root, '.venv/Scripts/python.exe'), ['-c', `
import json,os,sys
sys.path.insert(0,'pabasa_site');os.environ.setdefault('DJANGO_SETTINGS_MODULE','pabasa_site.settings')
import django;django.setup()
from django.template.loader import render_to_string
from pabasa_app.achievements import ACHIEVEMENTS
badges=[dict(id=key,name=name,description=description,icon=icon,unlocked=key in ('first-steps','star-collector','color-champion')) for key,name,description,icon in ACHIEVEMENTS]
print(json.dumps([dict(theme=theme,html=render_to_string('pabasa_app/dashboard.html',{
 'nav_role':'student','account_id':4242,'first_name':'Test','dashboard_greeting_name':'Test',
 'student_theme_slug':theme,'student_achievements':{'badges':badges},
 'student_calendar_today':'2026-10-17','student_calendar_events_json':'[]',
 'student_session_progress':[], 'student_current_prescribed_activity':None,
})) for theme in ('sky','forest','treasure','space','library','zoo','ocean')]))
`], {cwd:root, encoding:'utf8', maxBuffer:8*1024*1024,
     env:{...process.env, DB_ENGINE:'sqlite', SQLITE_PATH:':memory:'}});
assert.equal(rendered.status, 0, rendered.stderr);
const fixtures = JSON.parse(rendered.stdout);

(async () => {
  const bootstrapCss = await (await fetch('https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css')).text();
  const bootstrapJs = await (await fetch('https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/js/bootstrap.bundle.min.js')).text();
  const browser = await chromium.launch({channel:'chrome', headless:true});
  let checks = 0, modalChecks = 0;
  try {
    for (const fixture of fixtures) {
      const page = await browser.newPage({viewport:{width:1366,height:900}});
      const errors = [];
      page.on('pageerror', error => errors.push(error.message));
      await page.addInitScript(() => {
        // Tampered/another account's old browser cache must not unlock badges.
        localStorage.setItem('pabasa_seen_material_ids', JSON.stringify(Array.from({length:200}, (_,i) => String(i))));
        const progress = {};
        for (const mode of ['free','color','hunt']) {
          progress[mode] = {};
          for (const difficulty of ['easy','medium','hard']) {
            progress[mode][difficulty] = {};
            for (let i=1;i<=5;i++) progress[mode][difficulty]['level_'+i] = {completed:true};
          }
        }
        localStorage.setItem('pabasa_practice_progress_v1', JSON.stringify(progress));
      });
      await page.route('**/*', async route => {
        const url = new URL(route.request().url());
        if (url.origin === 'http://localhost:9878' && url.pathname === '/dashboard/') {
          return route.fulfill({contentType:'text/html', body:fixture.html});
        }
        if (url.pathname.startsWith('/static/')) {
          const file = path.resolve(staticRoot, decodeURIComponent(url.pathname.slice(8)));
          if (file.startsWith(staticRoot + path.sep) && fs.existsSync(file) && fs.statSync(file).isFile()) {
            return route.fulfill({path:file});
          }
        }
        if (url.href.includes('bootstrap.min.css')) return route.fulfill({contentType:'text/css',body:bootstrapCss});
        if (url.href.includes('bootstrap.bundle.min.js')) return route.fulfill({contentType:'application/javascript',body:bootstrapJs});
        if (url.href.includes('bootstrap-icons.min.css')) return route.fulfill({path:path.join(staticRoot,'pabasa_app/vendor/bootstrap-icons/bootstrap-icons.css')});
        if (url.pathname.includes('bootstrap-icons.woff')) return route.fulfill({path:path.join(staticRoot,'pabasa_app/vendor/bootstrap-icons/fonts',path.basename(url.pathname))});
        if (url.pathname.startsWith('/api/')) return route.fulfill({json:{
          success:true, classes:[{id:1,section_id:1,name:'Test Class',class_name:'Test Class',code:'TEST'}],
          notifications:[], unread_count:0, events:[], materials:[], readings:{}, sections:[],
        }});
        return route.fulfill({status:200,body:''});
      });
      await page.goto('http://localhost:9878/dashboard/');
      const grid = page.locator('[data-achievements-grid]');
      await grid.waitFor({state:'visible'});
      await page.addStyleTag({content:'*,*::before,*::after{transition:none!important;animation:none!important}'});
      assert.equal(await grid.locator('[data-achievement-id]').count(), 12);
      assert.equal(await grid.locator('[data-achievement-id]:visible').count(), 6);
      assert.deepEqual(await grid.locator('.unlocked').evaluateAll(nodes => nodes.map(n => n.dataset.achievementId)),
                       ['first-steps','star-collector','color-champion']);
      assert.equal(await grid.locator('[data-achievement-id="practice-star"].locked').count(),1);
      const card = page.locator('[data-achievements]');
      const previous = card.locator('[data-achievement-prev]'), next = card.locator('[data-achievement-next]');
      const ids = await grid.locator('[data-achievement-id]').evaluateAll(nodes => nodes.map(n => n.dataset.achievementId));
      const modal = page.locator('#achievementDetailsModal');
      for (const [width,dark] of [[1366,false],[992,false],[390,false],[1366,true]]) {
        await page.setViewportSize({width,height:900});
        await page.evaluate(dark => document.body.classList.toggle('dark-theme',dark),dark);
        await grid.scrollIntoViewIfNeeded();
        const headerBounds = await card.locator('.achievement-header').evaluate(header => {
          const h=header.getBoundingClientRect(),title=header.querySelector('h3').getBoundingClientRect(),nav=header.querySelector('nav').getBoundingClientRect();
          const titleNode=header.querySelector('h3');
          return {singleLine:titleNode.offsetHeight<=parseFloat(getComputedStyle(titleNode).lineHeight)+1,
                  inside:nav.right<=h.right+1 && nav.left>=title.right-1,atTop:Math.abs((nav.top+nav.bottom)/2-(title.top+title.bottom)/2)<1,
                  headerHeight:h.height,navTop:nav.top-h.top,titleTop:title.top-h.top};
        });
        assert(headerBounds.inside && headerBounds.atTop && headerBounds.singleLine,JSON.stringify({theme:fixture.theme,width,headerBounds}));
        const firstHeight = (await card.boundingBox()).height;
        for (const index of [0,1]) {
          if (index===1) await next.click();
          assert.equal((await card.locator('[data-achievement-page]').textContent()).trim(),`${index+1} / 2`);
          assert.equal(await previous.isDisabled(),index===0);
          assert.equal(await next.isDisabled(),index===1);
          assert.deepEqual(await grid.locator('[data-achievement-id]:visible').evaluateAll(nodes => nodes.map(n => n.dataset.achievementId)),ids.slice(index*6,(index+1)*6));
          assert(Math.abs((await card.boundingBox()).height-firstHeight)<1,'Paging must retain card height.');
          const bounds = await grid.evaluate(grid => {
          const g = grid.getBoundingClientRect();
          const visible=[...grid.children].filter(node => !node.hidden);
          return {width:g.width, overflow:grid.scrollWidth-grid.clientWidth,
            rows:new Set(visible.map(node => Math.round(node.getBoundingClientRect().top))).size,
            badges:visible.map(node => {
              const b=node.getBoundingClientRect(),name=node.querySelector('.achievement-name');
              const n=name.getBoundingClientRect(),lock=node.querySelector('.achievement-lock');
              const l=lock.getBoundingClientRect();
              return {inside:b.left>=g.left-1 && b.right<=g.right+1 && b.bottom<=g.bottom+1,
                      labelFits:name.scrollWidth<=name.clientWidth+1,
                      lockClear:!node.classList.contains('locked') || l.bottom<=n.top || l.top>=n.bottom || l.right<=n.left || l.left>=n.right,
                      accessible:node.tabIndex===0 && !!node.getAttribute('aria-label') && !!node.title};
            })};
        });
          assert(bounds.width>0 && bounds.overflow<=1 && bounds.rows===2,JSON.stringify({theme:fixture.theme,width,bounds}));
          assert(bounds.badges.every(b => b.inside && b.labelFits && b.lockClear && b.accessible),JSON.stringify({theme:fixture.theme,width,bounds}));
          for (const badge of await grid.locator('[data-achievement-id]:visible').all()) {
            const name = (await badge.locator('.achievement-name').textContent()).trim();
            const description = await badge.getAttribute('title');
            const earned = await badge.evaluate(node => node.classList.contains('unlocked'));
            assert.equal(await badge.getAttribute('aria-haspopup'),'dialog');
            await badge.click();
            await modal.waitFor({state:'visible'});
            assert.equal((await modal.locator('#achievementDetailsTitle').textContent()).trim(),name);
            assert.equal(await modal.locator('#achievementDetailsRequirement').textContent(),description);
            assert.equal(await modal.locator('[data-achievement-details-state]').textContent(),earned?'Earned':'Locked');
            assert.equal(await modal.locator('[data-achievement-details-icon] i').count(),1);
            assert.equal((await card.locator('[data-achievement-page]').textContent()).trim(),`${index+1} / 2`);
            const dialogBounds = await modal.locator('.modal-content').evaluate(node => {
              const r=node.getBoundingClientRect();
              return {inside:r.left>=0 && r.top>=0 && r.right<=innerWidth+1 && r.bottom<=innerHeight+1,
                      horizontal:node.scrollWidth<=node.clientWidth+1};
            });
            assert(dialogBounds.inside && dialogBounds.horizontal,JSON.stringify({theme:fixture.theme,width,name,dialogBounds}));
            if (fixture.theme==='sky' && width===1366 && !dark && name==='Star Collector' && process.env.PABASA_ACHIEVEMENT_SCREENSHOT) {
              const output = path.parse(process.env.PABASA_ACHIEVEMENT_SCREENSHOT);
              await modal.locator('.modal-content').screenshot({path:path.join(output.dir,output.name+'-modal'+output.ext)});
            }
            switch (modalChecks % 4) {
              case 0: await modal.getByRole('button',{name:'Close achievement details'}).click(); break;
              case 1: await modal.getByRole('button',{name:'Got it',exact:true}).click(); break;
              case 2: await page.keyboard.press('Escape'); break;
              default: await modal.click({position:{x:3,y:3}});
            }
            await modal.waitFor({state:'hidden'});
            await page.waitForFunction(node => document.activeElement===node,await badge.elementHandle());
            assert(await badge.evaluate(node => document.activeElement===node),'Closing must restore focus to the clicked badge.');
            assert.equal(await page.locator('body.modal-open').count(),0);
            modalChecks++;
          }
          checks++;
        }
        await previous.click();
      }
      // Native buttons must also support keyboard paging.
      await next.focus();
      await page.keyboard.press('Enter');
      assert.equal(await grid.locator('[data-achievement-id="session-starter"]:visible').count(),1);
      await previous.focus();
      await page.keyboard.press('Space');
      assert.equal(await grid.locator('[data-achievement-id="first-steps"]:visible').count(),1);
      const firstBadge = grid.locator('[data-achievement-id="first-steps"]');
      await firstBadge.focus();
      for (const key of ['Enter','Space']) {
        await page.keyboard.press(key);
        await modal.waitFor({state:'visible'});
        assert.equal((await modal.locator('#achievementDetailsTitle').textContent()).trim(),'First Steps');
        await page.keyboard.press('Escape');
        await modal.waitFor({state:'hidden'});
        await page.waitForFunction(node => document.activeElement===node,await firstBadge.elementHandle());
        assert(await firstBadge.evaluate(node => document.activeElement===node));
        modalChecks++;
      }
      if (fixture.theme==='sky' && process.env.PABASA_ACHIEVEMENT_SCREENSHOT) {
        await page.evaluate(() => document.body.classList.remove('dark-theme'));
        await card.screenshot({path:process.env.PABASA_ACHIEVEMENT_SCREENSHOT});
        await next.click();
        const output = path.parse(process.env.PABASA_ACHIEVEMENT_SCREENSHOT);
        await card.screenshot({path:path.join(output.dir,output.name+'-page2'+output.ext)});
      }
      assert.deepEqual(errors,[]);
      await page.close();
    }
    console.log(`PASS: ${checks} achievement page layouts and ${modalChecks} detail dialogs across 7 themes; click/keyboard opening, correct requirements/status, responsive bounds, all dismissal methods, and focus restoration.`);
  } finally { await browser.close(); }
})().catch(error => {console.error(error);process.exitCode=1;});
