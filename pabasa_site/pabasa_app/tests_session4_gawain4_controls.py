"""Modal regressions without student records, recordings, or backend writes."""

import json
import shutil
import subprocess
from html.parser import HTMLParser

from django.template.loader import render_to_string
from django.test import SimpleTestCase


class PageParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids = []
        self.scripts = []
        self.script = None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if attrs.get('id'):
            self.ids.append(attrs['id'])
        if tag == 'script':
            self.script = []

    def handle_data(self, data):
        if self.script is not None:
            self.script.append(data)

    def handle_endtag(self, tag):
        if tag == 'script' and self.script is not None:
            self.scripts.append(''.join(self.script))
            self.script = None


class Session4Gawain4ModalTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.html = render_to_string('pabasa_app/session_4_gawain_4_page.html', {
            'session4_gawain4_data': {
                'activity_key': 'session-4-gawain-4',
                'progress_url': '/test/progress/',
                'next_url': '/test/prescribed/',
                'columns': [['aba', 'iba', 'bibo']],
                'progress': {'current_index': 1, 'completed_items': 1,
                             'correct_items': 1, 'activity_completed': False},
            },
        })
        cls.page = PageParser()
        cls.page.feed(cls.html)

    def run_node(self, source):
        node = shutil.which('node')
        if not node:
            self.skipTest('Node.js is required for the isolated modal harness.')
        result = subprocess.run([node], input=source, capture_output=True,
                                text=True, timeout=20, check=False)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_modal_ids_are_unique(self):
        self.assertEqual(len(self.page.ids), len(set(self.page.ids)))
        self.assertEqual(self.page.ids.count('prescribed-s4g4-leave-modal'), 1)
        self.assertEqual(self.page.ids.count('prescribed-s4g4-back'), 1)

    def test_help_contains_word_specific_steps_and_acknowledgment(self):
        for text in ('1. Basahin ang salita',
                     'Tingnan ang salita at basahin ito nang malinaw.',
                     '2. Magsalita nang malinaw',
                     'Sabihin ang salita sa normal na lakas ng boses.',
                     '3. Magpatuloy sa gawain',
                     'Sundin ang mga button para magpatuloy sa susunod.',
                     'NAINTINDIHAN KO!'):
            self.assertIn(text, self.html)

    def test_other_help_variants_keep_their_existing_instructions(self):
        for variant, heading in (('session-4-gawain-1', 'Basahin ang letra'),
                                 ('session-4-gawain-2', 'Pakinggan ang mga tunog')):
            html = render_to_string('pabasa_app/session4_prescribed_controls.html',
                                    {'prefix': 'test', 'help_variant': variant})
            self.assertIn(heading, html)
            self.assertNotIn('Basahin ang salita', html)

    def test_inline_javascript_compiles(self):
        scripts = [s for s in self.page.scripts if s.strip() and not s.lstrip().startswith('{')]
        self.run_node('const vm=require("node:vm"); for(const source of '
                      + json.dumps(scripts) + ') new vm.Script(source);')

    def test_pause_navigation_awaits_existing_save_and_retries_failure(self):
        script = next(s for s in self.page.scripts
                      if "const pauseBack = document.getElementById('prescribed-s4g4-back')" in s)
        self.run_node(r'''
const vm = require('node:vm'), assert = require('node:assert/strict');
function element(){return {hidden:true,disabled:false,events:{},
  addEventListener(name,fn){this.events[name]=fn},setAttribute(){},
  click(){this.clicks=(this.clicks||0)+1},before(){}}}
const ids = ['pause-modal','back','resume','restart','audio-test','help-btn',
             'audio-settings-btn','help-ack','help-close'];
const nodes = Object.fromEntries(ids.map(id=>['prescribed-s4g4-'+id,element()]));
const actions = ['resume','restart','back','audio-test'].map(id=>nodes['prescribed-s4g4-'+id]);
nodes['prescribed-s4g4-pause-modal'].querySelectorAll=()=>actions;
nodes['prescribed-s4g4-pause-modal'].querySelector=()=>element();
nodes['session4-gawain-4-data']={textContent:JSON.stringify({next_url:'/test/prescribed/'})};
const errors=[],destinations=[],calls=[];
let resolveSave,rejectSave,saveCount=0,stopped=0;
const activityState={current_index:4,completed_items:4,activity_completed:false};
const originalState=JSON.stringify(activityState);
const window={Basahin:{cancelAll(){calls.push('cleanup')}},
  __session4SaveAdapters:{'prescribed-s4g4':()=>{saveCount++;calls.push('save');
    assert.equal(JSON.stringify(activityState),originalState);
    return new Promise((resolve,reject)=>{resolveSave=resolve;rejectSave=reject})}},
  __session4StopInstruction:{'prescribed-s4g4':()=>stopped++},
  Session4LeaveConfirmation:{init(config){assert.equal(config.returnUrl,'/test/prescribed/')}},
  location:{assign(url){destinations.push(url);calls.push('navigate')}}};
const document={getElementById:id=>nodes[id]||null,querySelector:()=>null,
  createElement:()=>{const e=element();errors.push(e);return e}};
vm.runInNewContext(SOURCE,{window,document,console:{error(){}}});
(async()=>{
  const back=nodes['prescribed-s4g4-back'],event={preventDefault(){}};
  const first=back.events.click(event);
  await Promise.resolve();
  assert.equal(saveCount,1);assert.deepEqual(destinations,[]);
  assert.ok(actions.every(button=>button.disabled));
  await back.events.click(event);assert.equal(saveCount,1);
  rejectSave(new Error('offline'));await first;
  assert.deepEqual(destinations,[]);assert.ok(actions.every(button=>!button.disabled));
  assert.equal(errors[0].hidden,false);
  const retry=back.events.click(event);await Promise.resolve();
  assert.equal(saveCount,2);resolveSave({success:true});await retry;
  assert.deepEqual(destinations,['/test/prescribed/']);
  assert.deepEqual(calls,['cleanup','save','cleanup','save','navigate']);
  assert.equal(JSON.stringify(activityState),originalState);
  nodes['prescribed-s4g4-help-btn'].events.click();
  nodes['prescribed-s4g4-audio-settings-btn'].events.click();
  assert.equal(stopped,4);
  nodes['prescribed-s4g4-help-ack'].events.click();
  assert.equal(nodes['prescribed-s4g4-help-close'].clicks,1);
})().catch(error=>{console.error(error);process.exitCode=1});
'''.replace('SOURCE', json.dumps(script)))

    def test_existing_activity_save_preserves_resumed_counts_and_attempts(self):
        script = next(s for s in self.page.scripts
                      if 'save=()=>postProgress(state())' in s)
        self.run_node(r'''
const vm=require('node:vm'),assert=require('node:assert/strict');
const classList={remove(){},toggle(){}};
const button=()=>({disabled:false,dataset:{},style:{},textContent:'',
  classList,querySelector:()=>({textContent:'',classList})});
const speak=button(),listen=button(),start=button();
const app={dataset:{},querySelector:s=>s==='#speak'?speak:s==='#listen'?listen:
  {textContent:'Ibaba ang babae.'},querySelectorAll:()=>[]};
const modal={querySelector:()=>({textContent:''}),remove(){}};
const data={activity_key:'session-4-gawain-4',progress_url:'/test/progress/',
  sentences:['Uubo si Bibo.','Bibo ang bibe.','Ibaba ang babae.','Buo ang bao.'],
  has_incomplete_progress:true,progress:{current_index:2,completed_items:2,
    correct_items:2,activity_completed:false,
    state:{reading_attempts:3,listening_attempts:2,pakinggan_unlocked:true}}};
const document={cookie:'',getElementById:id=>id==='session4-gawain-4-data'?
  {textContent:JSON.stringify(data)}:id==='session-4-gawain-4-app'?app:
  id==='session-4-gawain-4-start'?modal:id==='session-4-gawain-4-start-button'?start:null};
let requests=[],success=true,plays=0,pauses=0;
const window={BasahinButton:{LABEL:'Basahin',setState(){}},Basahin:{bindActivity(){}}};
vm.runInNewContext(SOURCE,{window,document,console,narratorActive:false,wordCompleted:false,
  Audio:class{play(){plays++;return Promise.resolve()}pause(){pauses++}
    removeAttribute(){}load(){}},
  fetch:async(url,options)=>{
    requests.push(JSON.parse(options.body));return {json:async()=>({success})}}});
(async()=>{
  start.onclick(); // Exercise the real saved-state restoration without a reset request.
  assert.equal(requests.length,0);assert.equal(plays,1);
  window.__session4StopInstruction['prescribed-s4g4']();
  assert.ok(pauses>0);
  window.session4Gawain4Resume();
  assert.equal(plays,1); // Closing Pause does not replay the instruction.
  await window.__session4SaveAdapters['prescribed-s4g4']();
  const saved=requests[0];
  assert.equal(saved.reset,false);
  assert.equal(typeof saved.state.state_version,'number');
  delete saved.state.state_version;
  assert.deepEqual(saved,{activity_key:'session-4-gawain-4',reset:false,
    state:{current_index:2,completed_items:2,correct_items:2,total_items:4,
      activity_completed:false,phase:'active',reading_attempts:3,
      listening_attempts:2,pakinggan_unlocked:true}});
  success=false;
  await assert.rejects(window.__session4SaveAdapters['prescribed-s4g4']());
})().catch(error=>{console.error(error);process.exitCode=1});
'''.replace('SOURCE', json.dumps(script)))

