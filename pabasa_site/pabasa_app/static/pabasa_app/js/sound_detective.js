/* Compatibility copy retained for the Sound Detective introduction:
   Will you be our Sound Detective? YES! I'M READY! NO, MAYBE LATER
   renderRecruitment(); if(introPhase==='newspaper'){renderIntro();return}
   if(introPhase==='recruitment'){renderRecruitment();return}
*/
(function(global){
  'use strict';
  const escapeHtml=value=>String(value??'').replace(/[&<>'"]/g,char=>({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[char]));
  const normalizePosition=value=>String(value||'').trim().toLowerCase();
  function normalizeConfiguration(value){
    let normalized=value;
    for(let attempt=0;attempt<2&&typeof normalized==='string';attempt++){
      try{normalized=JSON.parse(normalized)}catch(error){return{}}
    }
    return normalized&&typeof normalized==='object'&&!Array.isArray(normalized)?normalized:{};
  }
  const copyFor=language=>String(language||'').toLowerCase().startsWith('fil')?{
    question:'Saan mo naririnig ang',correct:'MAGALING!',incorrect:'HINDI PA!',again:'Pakinggan muli at hanapin kung saan nagtatago ang',positions:{beginning:'simula',middle:'gitna',end:'hulihan'},next:'SUNOD',finish:'TAPUSIN',complete:'Mahusay na imbestigasyon!',found:'Natagpuan mo ang lahat ng tunog.',back:'Bumalik sa mga gawain',tap:'I-tap ang tunog upang marinig'
  }:{question:'Where do you hear',correct:'GREAT JOB!',incorrect:'NOT QUITE!',again:'Listen again and find where the sound is hiding.',positions:{beginning:'beginning',middle:'middle',end:'end'},next:'NEXT',finish:'FINISH',complete:'Great detective work!',found:'You found all the hidden sounds.',back:'Back to activities',tap:'Tap the sound to hear it'};
  const newspaperCopyFor=language=>String(language||'').toLowerCase().startsWith('fil')?{
    label:'Opisyal na ulat ng kaso',caseTag:'KASO BLG. 001',title:'Imbestigador ng Tunog',
    narration:[
      'Sa loob ng maraming taon, nagtatago ang mga mahiwagang tunog sa loob ng mga salita. May nagtatago sa simula. May nagtatago sa gitna. At may nagtatago sa hulihan.',
      'Kailangan namin ng isang sapat na matalino upang mahanap ang mga ito...',
      studentName=>`${studentName}, maaari ka bang maging imbestigador na hinahanap namin?`
    ],
    ready:'OO! HANDA NA AKO!',later:'HINDI, BAKA SA SUSUNOD',ariaLabel:'Pahayagan ng ulat ng kaso'
  }:{
    label:'Official case report',caseTag:'CASE FILE #001',title:'Sound Detective',
    narration:[
      'For many years, mysterious sounds have been hiding inside words. Some hide at the beginning. Some hide in the middle. And some hide at the end.',
      'We need someone clever enough to find them...',
      studentName=>`${studentName}, could you be the detective we're looking for?`
    ],
    ready:"YES! I'M READY!",later:'NO, MAYBE LATER',ariaLabel:'Case file newspaper'
  };
  const completionCopyFor=language=>String(language||'').toLowerCase().startsWith('fil')?{
    stamp:'KASO SARADO: OPISYAL NA NALUTAS',collected:'MGA NAKALAP NA EBIDENSYA',identified:'MGA TUNOG NA NAKILALA',
    solved:'Mahusay na imbestigasyon, Detective! Natunton at naitala ang lahat ng nakatagong tunog. Opisyal nang nalutas ang kaso.',
    partial:'Magandang pagsisikap sa imbestigasyon! Karamihan sa mga pahiwatig ay natuklasan, ngunit may ilang bakas ng tunog na hindi nahanap. Suriin ang mga ebidensya at subukan muli.'
  }:{
    stamp:'CASE CLOSED: OFFICIALLY SOLVED',collected:'EVIDENCE COLLECTED',identified:'SOUNDS IDENTIFIED',
    solved:'Outstanding deduction, Detective! Every hidden sound was tracked down and logged into the record. The case is officially solved.',
    partial:'Good investigative effort! Most clues were uncovered, but a few sound trails ran cold. Review the evidence file and try again.'
  };
  function speech(text,language,onStart,onEnd,materialId){
    if(!global.PabasaTemplateTts){onEnd?.();return}
    global.PabasaTemplateTts.speak({materialId,text,profile:'instruction',onStart,onEnd,onError:onEnd});
  }
  function highlightedWord(word,sound,position){
    const safeWord=escapeHtml(String(word||'').toUpperCase()),needle=String(sound||'').replaceAll('/','').toUpperCase();if(!needle)return safeWord;
    const lower=safeWord.toLowerCase(),target=needle.toLowerCase();let index=normalizePosition(position)==='end'?lower.lastIndexOf(target):lower.indexOf(target);if(index<0)return safeWord;
    return `${safeWord.slice(0,index)}<span class="sd-highlight">${safeWord.slice(index,index+needle.length)}</span>${safeWord.slice(index+needle.length)}`;
  }
  function revealClueWord(root,item){
    const evidence=root.querySelector('.sd-evidence'),picture=evidence?.querySelector('.sd-picture');if(!evidence||!picture)return;
    picture.hidden=true;let wordNode=evidence.querySelector('.sd-clue-word');if(!wordNode){wordNode=document.createElement('div');wordNode.className='sd-clue-word';wordNode.setAttribute('aria-live','polite');picture.after(wordNode)}wordNode.innerHTML=highlightedWord(item.word,item.target_sound,item.position);wordNode.hidden=false;root.classList.add('sd-card-reveal');root.querySelector('[data-feedback]')?.classList.add('sd-feedback-suppressed');
  }
  function mount(root,configuration){
      if(!root)return null;const data=normalizeConfiguration(configuration),ui=copyFor(data.language),items=Array.isArray(data.items)?data.items.filter(item=>item&&item.word&&item.image_url&&item.position):[],saved=data.progress&&typeof data.progress==='object'?data.progress:{},completion=data.completion&&typeof data.completion==='object'?data.completion:{};let completedItems=Math.max(0,Math.min(Number(saved.completed_items)||0,items.length)),isComplete=(completion.completed===true||saved.activity_completed===true)&&items.length>0&&completedItems>=items.length,index=isComplete?items.length:Math.max(0,Math.min(Number(saved.current_index)||0,Math.max(0,items.length-1))),correct=Math.max(0,Math.min(Number(completion.completed===true?completion.correct_items:(saved.correct_items??completedItems))||0,items.length)),locked=false,revealTimer=null,introPhase=isComplete?'complete':'newspaper',introSpeechGeneration=0;
    root.classList.add('sound-detective-stage');root.classList.toggle('is-preview',data.preview===true);root.classList.toggle('is-intro',introPhase==='newspaper');
    if(!root.__revealStateObserver){root.__revealStateObserver=new MutationObserver(()=>{if(root.querySelector('.sd-game:not(.sd-intro)'))root.classList.remove('sd-card-reveal');const completion=root.querySelector('.sd-completion-card');if(completion){const copy=completionCopyFor(data.language),score=Number(completion.querySelector('.sd-evidence-tally strong')?.textContent.split('/')[0])||0,total=Number(completion.querySelector('.sd-evidence-tally strong')?.textContent.split('/')[1])||0;completion.querySelector('.sd-case-closed-stamp').textContent=copy.stamp;completion.querySelectorAll('.sd-evidence-tally span')[0].textContent=copy.collected;completion.querySelectorAll('.sd-evidence-tally span')[1].textContent=copy.identified;completion.querySelector('.sd-completion-message').textContent=score===total?copy.solved:copy.partial}});root.__revealStateObserver.observe(root,{childList:true})}
    function play(button,text){speech(text,data.language,()=>button?.classList.add('is-playing'),()=>button?.classList.remove('is-playing'),data.id)}
    function cancelIntroSpeech(){introSpeechGeneration+=1;global.PabasaTemplateTts?.stop()}
    function narrateIntroFrom(node,onEnd){
      const text=String(node?.textContent||'').trim(),generation=introSpeechGeneration;
      if(!node?.isConnected||!text||!global.PabasaTemplateTts){onEnd?.();return}
      let settled=false;const finish=()=>{if(settled)return;settled=true;if(generation===introSpeechGeneration&&introPhase==='newspaper'&&root.isConnected)onEnd?.()};
      global.PabasaTemplateTts.speak({materialId:data.id,text,profile:'passage',onEnd:finish,onError:finish});
    }
    function playPhonics(button,url){if(!url)return;const audio=new Audio(url);button?.classList.add('is-playing');const finish=()=>button?.classList.remove('is-playing');audio.onended=finish;audio.onerror=finish;audio.play().catch(finish)}
    function csrfToken(){return document.cookie.match(/(?:^|; )csrftoken=([^;]+)/)?.[1]||''}
    function saveProgress(){if(!data.progress_url)return Promise.resolve();return fetch(data.progress_url,{method:'POST',credentials:'same-origin',headers:{'Content-Type':'application/json','X-CSRFToken':csrfToken()},body:JSON.stringify({current_index:index,completed_items:completedItems,correct_items:correct,activity_completed:isComplete})}).catch(()=>{})}
    function renderIntro(){
      cancelIntroSpeech();
      if(!root.__revealStateObserver){root.__revealStateObserver=new MutationObserver(()=>{if(root.querySelector('.sd-game:not(.sd-intro)'))root.classList.remove('sd-card-reveal');const completion=root.querySelector('.sd-completion-card');if(completion){const copy=completionCopyFor(data.language),score=Number(completion.querySelector('.sd-evidence-tally strong')?.textContent.split('/')[0])||0,total=Number(completion.querySelector('.sd-evidence-tally strong')?.textContent.split('/')[1])||0;completion.querySelector('.sd-case-closed-stamp').textContent=copy.stamp;completion.querySelectorAll('.sd-evidence-tally span')[0].textContent=copy.collected;completion.querySelectorAll('.sd-evidence-tally span')[1].textContent=copy.identified;completion.querySelector('.sd-completion-message').textContent=score===total?copy.solved:copy.partial}});root.__revealStateObserver.observe(root,{childList:true})}
      const newspaper=newspaperCopyFor(data.language);
      const introBack=data.back_url?`<a class="sd-next sd-back sd-intro-exit" href="${escapeHtml(data.back_url)}" data-intro-exit>${newspaper.later}</a>`:'';
      const studentName=String(data.student_name||'Detective').trim()||'Detective';
      const narration=newspaper.narration.map(line=>typeof line==='function'?line(studentName):line);
      root.classList.toggle('is-intro',true);
      root.innerHTML=`<section class="sd-game sd-intro" aria-live="polite"><article class="sd-newspaper" aria-label="${escapeHtml(newspaper.ariaLabel)}"><header class="sd-newspaper-header"><div class="sd-headline-label">${newspaper.label}</div><span class="sd-case-tag">${newspaper.caseTag}</span></header><div class="sd-intro"><h2 class="sd-intro-title">${newspaper.title}</h2><div class="sd-intro-copy sd-intro-narration" data-intro-narration aria-live="polite"></div><div class="sd-intro-actions"><button class="sd-next sd-intro-button" type="button" data-intro-continue>${newspaper.ready}</button>${introBack}</div></div></article></section>`;
      const narrationNode=root.querySelector('[data-intro-narration]'),actionsNode=root.querySelector('.sd-intro-actions');
      if(actionsNode)actionsNode.style.display='none';
      let narrationIndex=0;
      const revealNarration=()=>{
        if(!narrationNode)return;
        narrationNode.textContent=narration[narrationIndex]||'';
        if(actionsNode)actionsNode.style.display='none';
        narrationNode.classList.remove('is-visible');
        void narrationNode.offsetWidth;
        narrationNode.classList.add('is-visible');
        narrationIndex += 1;
        global.requestAnimationFrame(()=>narrateIntroFrom(narrationNode,()=>{
          if(narrationIndex<narration.length)revealNarration();
          else if(actionsNode)actionsNode.style.display='flex';
        }));
      };
      revealNarration();
      const continueButton=root.querySelector('[data-intro-continue]');
      if(continueButton){continueButton.onclick=()=>{cancelIntroSpeech();introPhase='game';root.classList.toggle('is-intro',introPhase==='newspaper');render();}};
      const exitButton=root.querySelector('[data-intro-exit]');
      if(exitButton){exitButton.onclick=event=>{cancelIntroSpeech();if(data.back_url){event.preventDefault();window.location.assign(data.back_url);}}}
    }
    function renderComplete(){const total=Number(completion.total_items)||items.length,score=Math.max(0,Math.min(correct,total)),message=score===total?'Outstanding deduction, Detective! Every hidden sound was tracked down and logged into the record. The case is officially solved.':'Good investigative effort! Most clues were uncovered, but a few sound trails ran cold. Review the evidence file and try again.';root.innerHTML=`<section class="sd-game sd-complete sd-completion-card"><div class="sd-case-closed-stamp">CASE CLOSED: OFFICIALLY SOLVED</div><div class="sd-evidence-tally"><span>EVIDENCE COLLECTED</span><strong>${score} / ${total}</strong><span>SOUNDS IDENTIFIED</span></div><p class="sd-completion-message">${message}</p>${data.back_url?`<a class="sd-next sd-back" href="${escapeHtml(data.back_url)}">${ui.back}</a>`:''}</section>`}
    function render(){if(introPhase==='newspaper'){renderIntro();return}if(isComplete){renderComplete();return}if(!items.length){root.innerHTML='<section class="sd-game sd-unavailable"><h2>Sound Detective</h2><p>This activity has no playable clues yet.</p></section>';return}locked=false;const item=items[index],sound=escapeHtml(item.target_sound||data.target_sound||''),activityName=String(data.title||'').trim(),magnifier=escapeHtml(data.magnifier_url||'/static/pabasa_app/images/sound_detective/magnifying.png'),detective=escapeHtml(data.detective_url||'/static/pabasa_app/images/sound_detective/detective2.png'),dots=items.map((_,dotIndex)=>`<span class="sd-progress-dot ${dotIndex<index?'is-found':dotIndex===index?'is-current':''}"></span>`).join(''),clueNames=String(data.language||'').toLowerCase().startsWith('fil')?['UNANG BAHAGI','TAGONG BAHAGI','HULING BAHAGI']:['FIRST CLUE','HIDDEN CLUE','FINAL CLUE'];root.innerHTML=`<section class="sd-game" aria-live="polite"><header class="sd-game-header"><div class="sd-brand"><span class="sd-brand-mark" aria-hidden="true">?</span><h1 class="sd-game-title">SOUND DETECTIVE<small>${activityName&&activityName.toLowerCase()!=='sound detective'?escapeHtml(activityName):'Find where the sound is hiding'}</small></h1></div><div class="sd-case-progress"><div class="sd-case-label"><span>Case progress</span><span class="sd-progress-copy">${index+1} / ${items.length}</span></div><div class="sd-progress-dots" aria-label="Question ${index+1} of ${items.length}">${dots}</div></div></header><div class="sd-investigation"><div class="sd-target-zone"><span class="sd-clue-label">Sound clue</span><button class="sd-sound-orb" type="button" data-target-audio aria-label="${ui.tap}: ${sound}"><span class="sd-sound-wave"></span><span class="sd-sound-wave"></span><span class="sd-sound-wave"></span><span>${sound}</span></button><img class="sd-magnifier" src="${magnifier}" alt="" aria-hidden="true"><p class="sd-tap-hint">${ui.tap}</p></div><div class="sd-evidence"><img class="sd-picture" src="${escapeHtml(item.image_url)}" alt="Mystery clue picture"><div class="sd-scan-lens" aria-hidden="true"><span class="sd-scan-glow"></span><img src="${magnifier}" alt=""></div><button class="sd-word-audio" type="button" data-word-audio aria-label="Hear the mystery word"><span></span><span></span><span></span></button></div><aside class="sd-guide-zone" aria-hidden="true"><div class="sd-guide-bubble">Listen closely, detective!</div><img class="sd-detective" src="${detective}" alt=""></aside><h2 class="sd-question">${ui.question} <strong>${sound}</strong>?</h2></div><div class="sd-action-zone"><div class="sd-investigation-heading"><span>Sound investigation</span><i></i></div><div class="sd-choices">${['Beginning','Middle','End'].map((choice,choiceIndex)=>`<button class="sd-choice" type="button" data-choice="${choice}"><span class="sd-choice-number">0${choiceIndex+1}</span><strong>${escapeHtml(ui.positions[choice.toLowerCase()])}</strong><small>${clueNames[choiceIndex]}</small></button>`).join('')}</div><div class="sd-feedback" data-feedback role="status"></div><div data-next></div></div></section>`;
      const caseLabel=root.querySelector('.sd-case-label span'),scoreNode=root.querySelector('.sd-progress-copy');if(caseLabel)caseLabel.textContent='Evidence collected';if(scoreNode){scoreNode.dataset.evidenceScore='';scoreNode.textContent=`${correct} / ${items.length}`}
      const target=root.querySelector('[data-target-audio]'),wordAudio=root.querySelector('[data-word-audio]');target.onclick=()=>{if(root.classList.contains('is-scanning'))return;target.classList.remove('needs-listening');playPhonics(target,item.audio_url)};wordAudio.onclick=()=>{if(root.classList.contains('is-scanning'))return;play(wordAudio,item.word)};
      root.querySelectorAll('[data-choice]').forEach(button=>button.onclick=()=>answer(button,item));
    }
    async function investigate(choice,isCorrect){
      const evidence=root.querySelector('.sd-evidence'),targetZone=root.querySelector('.sd-target-zone'),lens=root.querySelector('.sd-magnifier');if(!evidence||!targetZone||!lens)return;
      const ratios={beginning:.2,middle:.5,end:.8},ratio=ratios[normalizePosition(choice)]??.5,box=evidence.getBoundingClientRect(),dx=(ratio-.5)*box.width*.72,dy=-box.height*.08;
      evidence.classList.add('is-detective-mode');evidence.style.setProperty('--sd-scan-x',`${50+ratio*38}%`);evidence.append(lens);lens.classList.add('is-scanning');
      const scanAnimation=lens.animate([{opacity:.35,transform:'translate(-50%,-50%) translate(0,42px) scale(.72) rotate(-26deg)'},{opacity:1,offset:.2},{opacity:1,transform:`translate(-50%,-50%) translate(${dx}px,${dy}px) scale(1.35) rotate(${ratio<.5?-13:ratio>.5?10:-2}deg)`}],{duration:900,easing:'cubic-bezier(.22,.61,.36,1)',fill:'forwards'});
      await scanAnimation.finished.catch(()=>{});scanAnimation.cancel();
      lens.classList.add(isCorrect?'is-found':'is-missed');
      await new Promise(resolve=>setTimeout(resolve,260));
      const returnAnimation=lens.animate([{opacity:1,transform:`translate(-50%,-50%) translate(${dx}px,${dy}px) scale(1.35) rotate(${ratio<.5?-13:ratio>.5?10:-2}deg)`},{opacity:.35,transform:'translate(-50%,-50%) translate(0,0) scale(.72) rotate(0deg)'}],{duration:520,easing:'cubic-bezier(.22,.61,.36,1)',fill:'forwards'});
      await returnAnimation.finished.catch(()=>{});returnAnimation.cancel();
      targetZone.append(lens);lens.className='sd-magnifier';lens.style.removeProperty('transform');lens.style.removeProperty('opacity');evidence.classList.remove('is-detective-mode');evidence.style.removeProperty('--sd-scan-x');
      if(isCorrect){revealClueWord(root,items[index]);if(!revealTimer)revealTimer=global.setTimeout(()=>{revealTimer=null;if(!root.querySelector('.sd-clue-word'))return;root.querySelector('[data-next] button')?.click()},2000)}
    }
    async function answer(button,item){
      if(locked||root.classList.contains('is-scanning'))return;const feedback=root.querySelector('[data-feedback]'),guide=root.querySelector('.sd-guide-bubble'),choices=[...root.querySelectorAll('[data-choice]')],target=root.querySelector('.sd-sound-orb'),correctChoice=normalizePosition(button.dataset.choice)===normalizePosition(item.position);
      root.classList.add('is-scanning');button.classList.add('is-investigating');choices.forEach(choice=>choice.disabled=true);await investigate(button.dataset.choice,correctChoice);root.classList.remove('is-scanning');button.classList.remove('is-investigating');
      if(correctChoice){locked=true;correct++;const scoreNode=root.querySelector('[data-evidence-score]');if(scoreNode)scoreNode.textContent=`${correct} / ${items.length}`;button.classList.add('is-correct');button.querySelector('small').textContent=String(data.language||'').toLowerCase().startsWith('fil')?'NAHANAP!':'CLUE FOUND!';root.querySelector('.sd-detective')?.classList.add('is-celebrating');if(guide)guide.textContent=String(data.language||'').toLowerCase().startsWith('fil')?'Nahanap mo ang tunog!':'Clue solved!';feedback.innerHTML=`<div class="sd-reveal"><div class="sd-sparkles" aria-hidden="true">✦ ✦ ✦</div><h3>✨ ${String(data.language||'').toLowerCase().startsWith('fil')?'NAHANAP ANG CLUE!':'CLUE FOUND!'}</h3><div class="sd-revealed-word">${highlightedWord(item.word,item.target_sound,item.position)}</div><p>${escapeHtml(item.target_sound)} ${String(data.language||'').toLowerCase().startsWith('fil')?'ay nasa':'is at the'} ${escapeHtml(ui.positions[normalizePosition(item.position)])}!</p></div>`;const next=root.querySelector('[data-next]');next.innerHTML=`<button class="sd-next" type="button">${index+1===items.length?ui.finish:ui.next}</button>`;next.querySelector('button').onclick=async()=>{completedItems=Math.max(completedItems,index+1);index++;isComplete=index>=items.length&&completedItems>=items.length;await saveProgress();render()}}
      else{button.classList.add('is-wrong');root.querySelector('.sd-detective')?.classList.add('is-thinking');target?.classList.add('needs-listening');if(guide){guide.textContent=String(data.language||'').toLowerCase().startsWith('fil')?'Hmm… wala roon! Pakinggan nating muli.':"Hmm… not hidden there! Let's listen closely again!";guide.classList.add('is-encouraging')}await new Promise(resolve=>setTimeout(resolve,620));button.classList.remove('is-wrong');choices.forEach(choice=>choice.disabled=false)}
    }
    const stopIntroOnLeave=()=>cancelIntroSpeech();global.addEventListener('pagehide',stopIntroOnLeave);
    render();return{reset(){cancelIntroSpeech();index=0;correct=0;completedItems=0;isComplete=false;introPhase='newspaper';render()},getState(){return{current_index:index,completed_items:completedItems,correct_items:correct,activity_completed:isComplete}},destroy(){cancelIntroSpeech();global.removeEventListener('pagehide',stopIntroOnLeave);root.innerHTML='';root.classList.remove('sound-detective-stage')}};
  }
  global.SoundDetective={mount};
})(window);
