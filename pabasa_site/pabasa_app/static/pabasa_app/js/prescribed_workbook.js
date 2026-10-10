/* Shared workbook presentation for teacher preview and student interaction. */
(() => {
  'use strict';
  const data = JSON.parse(document.getElementById('workbook-payload').textContent);
  const a = data.activity, preview = data.preview;
  const qBuilder = a.activity_key === 'aral-l23-g6-q-syllable-builder';
  const l22G1 = a.activity_key === 'aral-l22-g1-c-syllable-builder';
  const l24Builder = a.activity_key === 'aral-l24-g1-v-syllable-builder';
  const l24G4Builder = a.activity_key === 'aral-l24-g4-x-syllable-builder';
  const cBuilder = (Boolean(a.specialized_builder) && !qBuilder) || a.activity_key === 'aral-l22-g1-c-syllable-builder';
  const specializedBuilder = cBuilder || qBuilder;
  const jReading = a.activity_key === 'aral-l23-g3-j-word-reading';
  const qReading = a.activity_key === 'aral-l23-g7-q-word-reading';
  const l24G3WordReading = a.activity_key === 'aral-l24-g3-x-word-reading';
  const prescribedWordReading = jReading || qReading || l24G3WordReading;
  const jSyllables = a.activity_key === 'aral-l23-g4-j-syllabication';
  const g5Syllables = a.activity_key === 'aral-l24-g5-z-syllabication';
  const g6Search = a.activity_key === 'aral-l24-g6-z-word-search';
  const g7Reading = a.activity_key === 'aral-l24-g7-z-word-reading';
  const s9Family = a.activity_key === 'aral-s9-a1-family-drawing';
  const s9Helping = a.activity_key === 'aral-s9-a2-helping-drawing';
  const l24G2 = a.activity_key === 'aral-l24-g2-v-word-reading';
  const pictureReading = a.activity_key === 'aral-l24-g4-x-pictures';
  const l23G1 = a.activity_key === 'aral-l23-g1-n-syllable-builder';
  const l23G3 = a.activity_key === 'aral-l23-g3-j-word-reading';
  const qG6 = qBuilder;
  const lesson23Activity = l23G1 || l23G3 || jSyllables || qG6 || qReading;
  const lesson24Activity = l24Builder || l24G4Builder || l24G3WordReading || g5Syllables || g6Search || g7Reading || pictureReading;
  const localAudio = (l22G1 || l23G1 || l23G3 || qReading || jSyllables || qG6 || l24Builder || g6Search || g7Reading || pictureReading || l24G3WordReading || l24G4Builder || g5Syllables || s9Family || s9Helping) ? (data.local_audio || {}) : {};
  const G1_MAPPED_TEXT = new Set([
    'Basahin ang mga pantig sa loob ng Big Box at subuking bumuo ng mga salita mula rito.',
    'Ni', 'La', 'ña', 'Cas', 'Bi', 'da', 'El', 'ño', 'ñan', 'Cen', 'ta', 'ñe',
    'Basahin muna ang lahat ng nasa Big Box.', 'Bumuo muna ng lahat ng wastong salita.',
    'Bumuo ng ibang salita.', 'Hindi available ang mikropono sa browser na ito.',
    'Hindi ko malinaw na narinig. Subukan muli.', 'Hindi mabasa ang recording.',
    'Hindi magamit ang mikropono. Subukan muli.', 'Hindi nakuha ang iyong boses. Subukan muli.',
    'Hindi tumugon ang mikropono.', 'Magaling! Nabasa mo nang tama ang lahat ng pantig.',
    'Pakinggan ang tamang pagbigkas pagkatapos ng tatlong maling pagbasa.',
    'Pakinggan muna ang tamang pagbigkas.', 'Subukan muli.', 'Tama!',
    'Walang nakuha sa recording. Subukan muli.', 'Magaling! Nabuo mo ang salitang Niño',
    'Magaling! Natapos mo ang Gawain 1.',
  ]);
  const G3_MAPPED_TEXT = new Set([
    'Basahin ang mga salita sa ibaba na nagtataglay ng hiram na letrang Jj.',
    'Jacket', 'Jennifer', 'jam', 'Jeffrey', 'pajama', 'Jojo', 'Jonathan',
    'Handa ka na?', 'Handa ka na.', 'Hindi available ang audio.', 'Hindi available ang panuto.',
    'Hindi ko malinaw na narinig. Subukan muli.', 'Hindi nakuha ang iyong boses. Subukan muli.',
    'Hindi pinayagan ang mikropono.', 'May problema sa recording.', 'Hindi na-save. Subukan muli.',
    'Subukan Muli.', 'Mahusay!', 'Natapos mo ang gawain!',
  ]);
  const G7_FEEDBACK_TEXT = new Set([
    'Handa ka na?', 'Hindi available ang audio.', 'Hindi available ang panuto.',
    'Hindi ko malinaw na narinig. Subukan muli.', 'Hindi na-save. Subukan muli.',
    'Hindi nakuha ang iyong boses. Subukan muli.', 'Hindi pinayagan ang mikropono.',
    'May problema sa recording.', 'Nakikinig...', 'Sinusuri...', 'Subukan muli.', 'Subukan Muli.',
    'Mahusay!', 'Natapos mo ang gawain!',
  ]);
  const G7_MAPPED_TEXT = new Set([
    'Basahin ang mga salita sa ibaba na nagtataglay ng hiram na letrang Qq.',
    'Quisumbing', 'Quennie', 'Enriquez', 'Quintana', 'Quintos',
    ...G7_FEEDBACK_TEXT,
  ]);
  const G4_MAPPED_TEXT = new Set([
    'Pantigin ang sumusunod na salita.', 'Hindi na-save. Subukan muli.',
    'Hindi available ang panuto.', 'Isulat muna ang sagot.', 'Mahusay!',
    'Subukan muli.', 'Natapos mo ang gawain!',
  ]);
  const L24_G2_PICTURE_MAPPED_TEXT = new Set([
    'Kilalanin ang bawat larawan at subuking basahin ito kasabay ng guro.',
    'Basahin ang salitang nasa larawan.', 'x-ray', 'fax machine', 'fox',
    'Hindi ko malinaw na narinig. Subukan muli.',
    'Hindi magamit ang mikropono. Subukan muli.',
    'Hindi nakuha ang boses. Subukan muli.',
    'Pinoproseso ang iyong pagbasa...', 'Subukan muli.', 'Tama! Magaling!',
    'Magaling! Natapos mo ang gawain.',
  ]);
  const L24_G6_WORD_SEARCH_MAPPED_TEXT = new Set([
    'Panuto: Hanapin at bilugan sa loob ng Big Box ang sumusunod na mga salita.',
    'zipper', 'zoo', 'zebra', 'zigzag', 'Perez', 'Rizal', 'Zamora', 'Zam', 'Zoren', 'Zeny',
    'Nahanap mo na ang salitang ito.', 'Subukan muli.',
    'Magaling! Nahanap mo ang lahat ng salita!',
    'Tama! Nahanap mo ang zipper.', 'Tama! Nahanap mo ang zoo.', 'Tama! Nahanap mo ang zebra.',
    'Tama! Nahanap mo ang zigzag.', 'Tama! Nahanap mo ang Perez.', 'Tama! Nahanap mo ang Rizal.',
    'Tama! Nahanap mo ang Zamora.', 'Tama! Nahanap mo ang Zam.', 'Tama! Nahanap mo ang Zoren.',
    'Tama! Nahanap mo ang Zeny.',
  ]);
  const L24_G7_WORD_READING_MAPPED_TEXT = new Set([
    'Basahin ang mga salita sa ibaba na may hiram na letrang Zz.',
    'zigzag', 'Zandra', 'Zamora', 'Zandro', 'Lazaro', 'Perez', 'Rizal', 'Dizon', 'Gomez',
    'Zarate', 'Zaragosa', 'Zapote', 'Zonrox', 'Lopez', 'Luzon', 'Zeny', 'Zoren', 'Legazpi',
    'Zabala', 'Zambales', 'Gonzales', 'Mendoza', 'Hernandez',
    'Hindi available ang audio.', 'Hindi ko malinaw na narinig. Subukan muli.',
    'Hindi magamit ang mikropono. Subukan muli.', 'Hindi pinayagan ang mikropono.',
    'Sinusuri ang iyong pagbasa...', 'Subukan muli.', 'Tama!',
    'Magaling! Natapos mo ang Gawain 7.',
  ]);
  const L24_G3_WORD_MAPPED_TEXT = new Set([
    'Basahin ang mga salita sa ibaba na nagtataglay ng hiram na letrang Xx.',
    'Alex', 'Alexander', 'Alexis', 'Dixon', 'Felix', 'mixer', 'Saxophone', 'Xylophone',
    'Handa ka na', 'Hindi available ang audio.', 'Hindi available ang mikropono.',
    'Hindi na-reset ang gawain.', 'Hindi na-save ang iyong gawain.',
    'Hindi nakuha ang boses. Subukan muli.',
    'Pakinggan ang tamang pagbigkas pagkatapos ng tatlong maling pagbasa.',
    'Pakinggan ang tamang pagbigkas, pagkatapos ay subukan mong basahin.',
    'Subukan muli.', 'Tama!', 'Magaling! Natapos mo ang Gawain 3.',
  ]);
  const L24_G4_BUILDER_MAPPED_TEXT = new Set([
    'Basahin ang mga pantig sa loob ng Big Box at subuking bumuo ng mga salita mula rito.',
    'A', 'Fe', 'lex', 'lix', 'lo', 'o', 'phone', 'rox', 'sax', 'xy', 'xe',
    'Bumuo muna ng kahit isang wastong salita.', 'Gumamit ng mga pantig sa Big Box.',
    'Hindi na-save ang iyong sagot. Subukan muli.', 'Hindi wastong nabuong salita.',
    'Tama!', 'Magaling! Natapos mo ang Gawain 4.',
  ]);
  const L24_G5_SYLLABLE_MAPPED_TEXT = new Set([
    'Pantigin ang sumusunod na salitang may letrang Zz. Ginawa ang unang bilang para sa iyo.',
    'Isulat muna ang sagot.', 'Mahusay!', 'Subukan muli.', 'Magaling! Natapos mo ang Gawain 5!',
  ]);
  const S9_A1_MAPPED_TEXT = new Set([
    'Draw a picture of your family. Under your drawing, write the sentence “This is my family.”',
    'Good job! Activity 1 is complete!',
  ]);
  const S9_A2_MAPPED_TEXT = new Set([
    'Draw and color a situation at home where you helped someone. Under your drawing, write the courteous word you used: “Please” / “Sorry” / “Thank you” / “You’re welcome.”',
    'Could not save your work. Try again.',
    'Please enter an answer.',
    'Write the kind word first.',
    "Use Please, Sorry, Thank you, or You're welcome.",
    'Good job! Activity 2 is complete!',
  ]);
  const G6_MAPPED_TEXT = new Set([
    'Basahin ang mga pantig sa loob ng Big Box at subuking bumuo ng mga salitang.',
    'Que', 'que', 'En', 'Qui', 'tos', 'no', 'A', 'Quin', 'An', 'ta', 'ja', 'na', 'to', 'ri', 'zon', 'ti',
    'Basahin muna ang lahat ng pantig.', 'Canonical word-building answer key could not be verified from the available workbook/project sources.',
    'Handa ka na?', 'Hindi available ang mikropono sa browser na ito.', 'Hindi ko malinaw na narinig. Subukan muli.',
    'Hindi mabasa ang recording.', 'Hindi magamit ang mikropono. Subukan muli.', 'Hindi na-save. Subukan muli.',
    'Hindi nakuha ang iyong boses. Subukan muli.', 'Hindi tumugon ang mikropono.', 'Hindi wastong mga pantig.',
    'Magaling! Nabasa mo nang tama ang lahat ng pantig.', 'Natapos na ang pagbasa.',
    'Pakinggan ang tamang pagbigkas pagkatapos ng tatlong maling pagbasa.', 'Pakinggan muna ang tamang pagbigkas.',
    'Subukan muli. Hindi pa matiyak ang salitang ito.', 'Subukan muli.', 'Tama!', 'Walang nakuha sa recording. Subukan muli.',
  ]);
  const L24_G1_MAPPED_TEXT = new Set([
    'Basahin ang mga pantig sa loob ng Big Box at subuking bumuo ng mga salita.',
    'lin', 'sa', 'van', 'va', 'E', 'la', 'I', 'Vi', 'Vio', 'le', 'val', 'A',
    'Basahin muna ang lahat ng nasa Big Box.', 'Basahin muna ang mga pantig sa Big Box.',
    'Handa ka na?', 'Hindi available ang mikropono sa browser na ito.', 'Hindi available ang panuto.',
    'Hindi ko malinaw na narinig. Subukan muli.', 'Hindi mabasa ang recording.',
    'Hindi magamit ang mikropono. Subukan muli.', 'Hindi maihanda ang pagbasa. Subukan muli.',
    'Hindi na-save. Subukan muli.', 'Hindi nakuha ang iyong boses. Subukan muli.',
    'Hindi pa nabe-verify ang mga wastong salita.', 'Hindi tumugon ang mikropono.',
    'Hindi wastong mga pantig.', 'Pakinggan ang tamang pagbigkas pagkatapos ng tatlong maling pagbasa.',
    'Pakinggan muna ang tamang pagbigkas o pindutin ang Subukan Muli.', 'Pakinggan muna ang tamang pagbigkas.',
    'Sinusuri ang iyong pagbasa...', 'Subukan muli.', 'Subukan Muli.', 'Tama!',
    'Walang nakuha sa recording. Subukan muli.', 'Magaling! Nabasa mo nang tama ang lahat ng pantig.',
  ]);
  let state = data.state || {}, busy = false, selected = [], builder = [], words = [];
  if (l24G2) {
    if (!state.draft || typeof state.draft !== 'object') state.draft = {builder: [], words: []};
    if (!state.oral || typeof state.oral !== 'object') state.oral = {};
  }
  let activeRecorder = null, activeStream = null, activeReadAloud = null, activeAudioSource = null, audioController = null;
  let audioRun = 0, instructionSpoken = false, pendingSpeech = '', g6CompletionPromise = null, session9DraftEpoch = 0;
  let pictureGuidedAttempt = null;
  const instructionText = a.instruction;
  const l22StartupTtsText = 'Letrang C. Handa kana?';
  const L22_G1_MAPPED_TEXT = new Set([l22StartupTtsText, 'Basahin ang mga pantig sa loob ng Big Box at subuking bumuo ng mga salita mula rito.', 'cac', 'ce', 'ca', 'bu', 'com', 'pu', 'ga', 'tus', 'ter', 'yan', 'Car', 'do', 'bi', 'net', 'te', 'Ce', 'les', 'Handa ka na?', 'Subukan muli.', 'Tama!', 'Magaling! Nabasa mo nang tama ang lahat ng pantig.', 'Magaling! Natapos mo ang Gawain 1.', 'Bumuo muna ng kahit isang wastong salita.', 'Bumuo ng ibang salita.', 'Gumamit ng mga pantig sa Big Box.', 'Hindi available ang audio', 'Hindi available ang audio.', 'Hindi available ang mikropono sa browser na ito.', 'Hindi available ang panuto.', 'Hindi ko malinaw na narinig. Subukan muli.', 'Hindi magamit ang mikropono. Subukan muli.', 'Hindi nakuha ang iyong boses. Subukan muli.', 'Hindi wastong mga pantig.', 'Pakinggan ang tamang pagbigkas pagkatapos ng tatlong maling pagbasa.', 'Pakinggan muna ang tamang pagbigkas.', 'Subukan muli. Hindi pa matiyak ang salitang ito.', 'Walang nakuha sa recording. Subukan muli.']);
  const L22_G1_OPERATIONAL_FEEDBACK = new Set(['Handa ka na?', 'Nakikinig...', 'Sinusuri ang iyong pagbasa...', 'Hindi magamit ang mikropono ngayon. Subukan muli mamaya.']);
  const l22G1ShouldHideResult = text => l22G1 && Boolean(text) && L22_G1_MAPPED_TEXT.has(text) && !L22_G1_OPERATIONAL_FEEDBACK.has(text);
  const session9Activity = s9Family || s9Helping;
  const session9SaveError = 'Could not save your work. Try again.';
  const session9AudioError = 'Audio is not available. Try again.';
  let activityStarted = (!session9Activity && !l22G1 && !lesson23Activity && !lesson24Activity) || preview || Boolean(state.completed), instructionPlayback = false, startupNarrationStarted = false;
  let l22G1Presentation = l22G1 ? (state.read_aloud_completed ? 'building' : 'instruction') : '';
  let l22G1InstructionToken = 0, l22G1TransitionToken = 0;
  const content = document.getElementById('wb-content'), action = document.getElementById('wb-action'), actionHost = action?.parentElement;
  const status = document.getElementById('wb-status');
  if (jReading) {
    const shell = document.querySelector('.wb-shell'), back = document.getElementById('wb-back');
    if (shell && back && shell.parentNode) {
      const pageLayout = document.createElement('div');
      pageLayout.className = 'wb-l23-g3-page-layout';
      back.classList.add('wb-l23-g3-back');
      back.textContent = 'Balik sa Aking Aralin';
      shell.parentNode.insertBefore(pageLayout, shell);
      pageLayout.append(back, shell);
    }
  }
  if (jSyllables) {
    const shell = document.querySelector('.wb-shell'), back = document.getElementById('wb-back');
    if (shell && back && shell.parentNode) {
      const pageLayout = document.createElement('div');
      pageLayout.className = 'wb-l23-g4-page-layout';
      back.classList.add('wb-l23-g4-back');
      back.textContent = 'Balik sa Aking Aralin';
      shell.parentNode.insertBefore(pageLayout, shell);
      pageLayout.append(back, shell);
      const frame = document.createElement('div');
      frame.className = 'wb-l23-g4-content-frame';
      shell.appendChild(frame);
      frame.append(content, action);
    }
  }
  if (l23G3) {
    document.addEventListener('pabasa:l23-started', event => {
      if (event.detail?.activityKey !== a.activity_key) return;
      activityStarted = true;
      render();
    }, {once:true});
  }
  const fil = a.language === 'Filipino';
  const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const token = () => document.querySelector('[name=csrfmiddlewaretoken]').value;
  const endpoint = data.progress_url;
  const item = () => a.items[state.index];
  const oral = () => state.oral[item()?.id] || {passed:false,attempts:0,listens:0,phase:a.model_first?'model':'read'};
  const message = (text, error=false) => {
    status.textContent=text;status.className=error?'wb-error':'wb-save';status.hidden=specializedBuilder||prescribedWordReading||jSyllables||g5Syllables||g6Search;
    if(specializedBuilder){const primary=content.querySelector('.wb-phase-status');if(primary){primary.textContent=text;primary.classList.toggle('wb-feedback-error',error);primary.classList.toggle('wb-audio-only-result',l22G1ShouldHideResult(text));}}
  };
  const stopReadAloud = () => {
    audioRun += 1;
    audioController?.abort();
    audioController = null;
    if(activeReadAloud){activeReadAloud.pause();activeReadAloud.currentTime=0;activeReadAloud=null;}
    if(activeAudioSource){try{activeAudioSource.stop();}catch(_){ }activeAudioSource.disconnect?.();activeAudioSource=null;}
  };
  const localAudioUrl = text => {
    const playbackText = l22G1 && state.completed && text === 'Magaling! Nabasa mo nang tama ang lahat ng pantig.'
      ? 'Magaling! Natapos mo ang Gawain 1.' : text;
    return playbackText === instructionText ? localAudio.instruction
      : (localAudio.words || {})[playbackText] || (localAudio.syllables || {})[playbackText] || (localAudio.feedback || {})[playbackText]
      || (localAudio.completion || {})[playbackText] || null;
  };
  async function playPrescribedAudio(text,allowBusy=false){
    if(pictureReading&&!activityStarted&&text===instructionText)return;
    if(g5Syllables&&!activityStarted&&text===instructionText)return;
    if(!text || (busy&&!allowBusy) || activeStream)return;
    stopReadAloud();
    const run=audioRun, controller=new AbortController();audioController=controller;
    const localUrl=(l22G1 || l23G1 || l23G3 || qReading || jSyllables || qG6 || l24Builder || g6Search || g7Reading || pictureReading || l24G3WordReading || l24G4Builder || g5Syllables || s9Family || s9Helping) ? localAudioUrl(text) : null;
    const mapped = (l22G1 && L22_G1_MAPPED_TEXT.has(text)) || (l23G1 && G1_MAPPED_TEXT.has(text)) || (l23G3 && G3_MAPPED_TEXT.has(text)) || (qReading && G7_MAPPED_TEXT.has(text)) || (jSyllables && G4_MAPPED_TEXT.has(text)) || (qG6 && ((text===instructionText && Boolean(localUrl)) || G6_MAPPED_TEXT.has(text))) || (l24Builder && L24_G1_MAPPED_TEXT.has(text)) || (g6Search && L24_G6_WORD_SEARCH_MAPPED_TEXT.has(text)) || (g7Reading && L24_G7_WORD_READING_MAPPED_TEXT.has(text)) || (pictureReading && L24_G2_PICTURE_MAPPED_TEXT.has(text)) || (l24G3WordReading && L24_G3_WORD_MAPPED_TEXT.has(text)) || (l24G4Builder && L24_G4_BUILDER_MAPPED_TEXT.has(text)) || (g5Syllables && L24_G5_SYLLABLE_MAPPED_TEXT.has(text)) || (s9Family && S9_A1_MAPPED_TEXT.has(text)) || (s9Helping && S9_A2_MAPPED_TEXT.has(text));
    if(mapped){
      if(!localUrl){if(audioController===controller)audioController=null;throw Error((jSyllables||l24Builder)&&text===instructionText?'Hindi available ang panuto.':'Hindi available ang audio.');}
      try{
        if(run!==audioRun||(busy&&!allowBusy)||activeStream)return;
        const audio=new Audio(localUrl);activeReadAloud=audio;
        const l22StartupAudio=l22G1&&text===l22StartupTtsText;
        const startupAudioSnapshot=()=>JSON.stringify({url:audio.src,muted:audio.muted,volume:audio.volume,paused:audio.paused,currentTime:audio.currentTime,readyState:audio.readyState,networkState:audio.networkState});
        if(l22StartupAudio)console.info('L22_G1_STARTUP_AUDIO_ATTEMPT',startupAudioSnapshot());
        if(l22StartupAudio){audio.addEventListener('play',()=>console.info('L22_G1_STARTUP_AUDIO_PLAY',startupAudioSnapshot()),{once:true});audio.addEventListener('pause',()=>console.info('L22_G1_STARTUP_AUDIO_PAUSE',startupAudioSnapshot()),{once:true});audio.addEventListener('error',()=>console.error('L22_G1_STARTUP_AUDIO_ERROR',startupAudioSnapshot()),{once:true});}
        const playPromise=audio.play();
        await playPromise;
        await new Promise((resolve,reject)=>{audio.onended=()=>{if(l22StartupAudio)console.info('L22_G1_STARTUP_AUDIO_ENDED',startupAudioSnapshot());resolve();};audio.onerror=()=>reject(Error((l23G3||jSyllables)?(text===instructionText?'Hindi available ang panuto.':'Hindi available ang audio.'):'Hindi ma-play ang nakatalagang audio.'));});
      }finally{
        if(audioController===controller)audioController=null;
        if(activeReadAloud&&run===audioRun){activeReadAloud.pause();activeReadAloud=null;}
      }
      return;
    }
    const spokenLanguage=fil?'Filipino':'English',expectedTtsLanguage=fil?'fil-PH':'en-PH';
    const form=new FormData();form.append('target_text',text);form.append('language',spokenLanguage);form.append('mode','reading');form.append('prescribed_activity_key',a.activity_key);form.append('prescribed_session_key',a.session_key||'');
    try{
      const response=await fetch(data.read_aloud_url,{method:'POST',credentials:'same-origin',headers:{'Accept':'application/json','X-CSRFToken':token()},body:form,signal:controller.signal});
      const result=await responseJson(response,session9Activity?session9AudioError:'Hindi available ang Filipino audio. Subukan muli.');
      if(!response.ok||!result.success||!result.audio_content)throw Error(result.error||(session9Activity?session9AudioError:'Hindi available ang Filipino audio.'));
      if(fil&&!result.local_audio&&(result.tts_language !== 'fil-PH' || result.voice_name !== 'fil-PH-Wavenet-A'))throw Error(session9Activity?'The right voice is not available.':'Hindi available ang tamang Filipino voice.');
      if(!fil&&!result.local_audio&&result.tts_language!==expectedTtsLanguage)throw Error('The correct English voice is unavailable.');
      if(run!==audioRun||(busy&&!allowBusy)||activeStream)return;
      if(g5Syllables&&await playG5TtsAudio(result.audio_content,run))return;
      const audio=new Audio('data:'+(result.mime_type||'audio/mpeg')+';base64,'+result.audio_content);audio.preload='auto';activeReadAloud=audio;audio.load();
      await audio.play();
      await new Promise((resolve,reject)=>{audio.onended=resolve;audio.onerror=()=>reject(Error(session9Activity?'Audio could not play.':'Hindi ma-play ang Filipino audio.'));});
    }finally{
      if(audioController===controller)audioController=null;
      if(activeReadAloud&&run===audioRun){activeReadAloud.pause();activeReadAloud=null;}
    }
  }
  async function replayInstruction(button){
    if(instructionPlayback||busy||activeStream)return;
    instructionPlayback=true;button.disabled=true;button.classList.add('is-busy');
    try{await playPrescribedAudio(instructionText,true);}catch(e){if(e?.name!=='AbortError')message(e.message||(session9Activity?session9AudioError:'Hindi available ang panuto.'),true);}
    finally{instructionPlayback=false;if(button.isConnected){button.disabled=false;button.classList.remove('is-busy');}}
  }
  function initializeL22Entry(){
    const modal=document.getElementById('wb-l22-g1-start');
    if(!l22G1||preview||state.completed||!modal)return;
    const start=document.getElementById('wb-l22-g1-start-button'),later=document.getElementById('wb-l22-g1-later-button');
    const playStartup=()=>{if(!modal.isConnected||activityStarted)return;stopReadAloud();playPrescribedAudio(l22StartupTtsText,true).catch(error=>{if(error?.name!=='AbortError')console.error('Lesson 22 startup audio failed',{name:error?.name||'Error',message:error?.message||String(error),url:localAudioUrl(l22StartupTtsText)});});};
    document.body.classList.add('lesson-start-open');
    if(!startupNarrationStarted){startupNarrationStarted=true;playStartup();}
    start?.addEventListener('click',()=>{
      if(start.disabled)return;
      start.disabled=true;if(later)later.disabled=true;l22G1InstructionToken++;l22G1TransitionToken++;stopReadAloud();activityStarted=true;instructionSpoken=true;modal.remove();document.body.classList.remove('lesson-start-open');if(!state.read_aloud_completed)l22G1Presentation='instruction';syncL22G1Presentation();render();if(l22G1Presentation==='instruction')playL22G1Instruction();
    });
    later?.addEventListener('click',()=>{
      if(later.disabled)return;
      later.disabled=true;if(start)start.disabled=true;l22G1InstructionToken++;l22G1TransitionToken++;stopReadAloud();window.location.href=document.getElementById('wb-back')?.href||'/dashboard/assessment/';
    });
    window.addEventListener('pagehide',()=>{l22G1InstructionToken++;l22G1TransitionToken++;stopReadAloud();},{once:true});
  }
  function initializeLesson23Entry(){
    if(!lesson23Activity||preview||state.completed)return;
    const suffix=l23G1?'g1':l23G3?'g3':jSyllables?'g4':qG6?'g6':'g7';
    const modal=document.getElementById(`wb-l23-${suffix}-start`);
    if(!modal)return;
    const start=document.getElementById(`wb-l23-${suffix}-start-button`),later=document.getElementById(`wb-l23-${suffix}-later-button`);
    const close=callback=>{if(start?.disabled)return;if(start)start.disabled=true;if(later)later.disabled=true;stopReadAloud();try{callback?.();}finally{modal.remove();document.body.classList.remove('lesson-start-open');}};
    document.body.classList.add('lesson-start-open');
    if(start)start.onclick=()=>close(()=>{activityStarted=true;instructionSpoken=true;render();playPrescribedAudio(instructionText,true).catch(error=>{if(error?.name!=='AbortError')console.error('Lesson 23 instruction audio failed',error);});});
    if(later)later.onclick=()=>{if(later.disabled)return;later.disabled=true;if(start)start.disabled=true;stopReadAloud();window.location.href=document.getElementById('wb-back')?.href||'/dashboard/assessment/';};
  }
  function initializeSession9Entry(){
    const modal=document.getElementById('wb-s9-start'),stage=document.querySelector('.wb-s9-activity-stage');
    if(!session9Activity||preview||state.completed||!modal)return;
    stage?.classList.add('is-waiting');
    const start=document.getElementById('wb-s9-start-button'),later=document.getElementById('wb-s9-later-button'),modalStatus=document.getElementById('wb-s9-start-status');
    const showError=error=>{if(modalStatus)modalStatus.textContent=error?.name==='AbortError'?'':(error?.message||'The instruction audio is unavailable. You may try again.');};
    instructionSpoken=true;
    playPrescribedAudio(instructionText,true).catch(showError);
    start?.addEventListener('click',()=>{
      if(start.disabled)return;start.disabled=true;later.disabled=true;stopReadAloud();activityStarted=true;modal.hidden=true;stage?.classList.remove('is-waiting');render();
    });
    later?.addEventListener('click',()=>{
      if(later.disabled)return;start.disabled=true;later.disabled=true;stopReadAloud();modal.hidden=true;window.location.href=document.getElementById('wb-back')?.href||'/dashboard/assessment/';
    });
  }
  async function responseJson(response, fallback) {
    const contentType = response.headers.get('content-type') || '';
    const body = await response.text();
    if (!contentType.toLowerCase().includes('application/json')) {
      console.error('Workbook request returned a non-JSON response.', {status:response.status,url:response.url,contentType,body:body.slice(0,500)});
      throw Error(fallback);
    }
    try { return JSON.parse(body); }
    catch (error) {
      console.error('Workbook request returned invalid JSON.', {status:response.status,url:response.url,contentType,body:body.slice(0,500),error});
      throw Error(fallback);
    }
  }
  let queue = Promise.resolve();
  function send(event, form=null, announceSaved=true, guardEpoch=null, guardCurrent=null) {
    if(preview) return Promise.resolve();
    const operation = async () => {
      if(guardCurrent&&!guardCurrent())return false;
      if(s9Family&&event?.action==='draft'&&(state.completed||guardEpoch!==session9DraftEpoch))return;
      let body;
      if(form) {form.set('revision',state.revision);if(event?.action)form.set('action',event.action);body=form;}
      else body=JSON.stringify({...event,revision:state.revision});
      const response=await fetch(endpoint,{method:'POST',credentials:'same-origin',headers:{'Accept':'application/json','X-CSRFToken':token(),...(form?{}:{'Content-Type':'application/json'})},body});
      const result=await responseJson(response,session9Activity?session9SaveError:'Hindi na-save. Subukan muli.');
      if(!response.ok||!result.success) throw Error(result.error||(session9Activity?session9SaveError:'Hindi na-save. Subukan muli.'));
      if(guardCurrent&&!guardCurrent())return false;
      const latestDraft=state.draft;
      state=result.state;
      if(event?.action==='draft')state.draft=latestDraft;
      if(announceSaved)message(session9Activity?'Work saved.':(fil?'Na-save ang iyong gawain.':'Your work is saved.'));
      if(guardCurrent)return true;
    };
    const pending=queue.then(operation);queue=pending.catch(()=>{});return pending;
  }
  async function completeG6(){
    if(!g6Search||!data.completion_url)return;
    if(!g6CompletionPromise){
      g6CompletionPromise=fetch(data.completion_url,{method:'POST',credentials:'same-origin',headers:{'Accept':'application/json','X-CSRFToken':token()},body:'{}'})
        .then(responseJson)
        .then(result=>{if(!result.success)throw Error(result.error||'Hindi na-save ang pagkumpleto.');return result;})
        .catch(error=>{g6CompletionPromise=null;throw error;});
    }
    await g6CompletionPromise;
  }

  async function perform(event,form=null){if(busy)return;if(s9Family&&(event?.action==='answer'||event?.action==='restart'))session9DraftEpoch++;busy=true;lock();const wasCompleted=Boolean(state.completed);try{await send(event,form);if(g6Search&&state.completed&&!wasCompleted)await completeG6();render();if(s9Family&&state.completed&&!wasCompleted)await playPrescribedAudio('Good job! Activity 1 is complete!',true);if(s9Helping&&state.completed&&!wasCompleted)await playPrescribedAudio('Good job! Activity 2 is complete!',true);if(l22G1){if(state.completed)await playPrescribedAudio('Magaling! Nabasa mo nang tama ang lahat ng pantig.',true);else if(L22_G1_MAPPED_TEXT.has(state.last_feedback))await playPrescribedAudio(state.last_feedback,true);}if(l23G1){if(state.completed){await playPrescribedAudio('Magaling! Natapos mo ang Gawain 1.',true);await playPrescribedAudio('Magaling! Nabuo ang salitang Niño',true);}else if(G1_MAPPED_TEXT.has(state.last_feedback))await playPrescribedAudio(state.last_feedback,true);}if(jSyllables){if(state.completed)await playPrescribedAudio('Natapos mo ang gawain!',true);else if(G4_MAPPED_TEXT.has(state.last_feedback))await playPrescribedAudio(state.last_feedback,true);}if(qG6&&G6_MAPPED_TEXT.has(state.last_feedback))await playPrescribedAudio(state.last_feedback,true);if(g6Search&&L24_G6_WORD_SEARCH_MAPPED_TEXT.has(state.last_feedback))await playPrescribedAudio(state.last_feedback,true);if(l24Builder){if(state.completed)await playPrescribedAudio('Magaling! Nabasa mo nang tama ang lahat ng pantig.',true);else if(L24_G1_MAPPED_TEXT.has(state.last_feedback))await playPrescribedAudio(state.last_feedback,true);}if(l24G4Builder){if(state.completed)await playPrescribedAudio('Magaling! Natapos mo ang Gawain 4.',true);else if(L24_G4_BUILDER_MAPPED_TEXT.has(state.last_feedback))await playPrescribedAudio(state.last_feedback,true);}if(g5Syllables){if(state.completed)await playPrescribedAudio('Magaling! Natapos mo ang Gawain 5!',true);else if(L24_G5_SYLLABLE_MAPPED_TEXT.has(state.last_feedback))await playPrescribedAudio(state.last_feedback,true);}}catch(e){const text=e.message||'Hindi na-save. Subukan muli.';message(text,true);if((l22G1&&L22_G1_MAPPED_TEXT.has(text))||(l23G1&&G1_MAPPED_TEXT.has(text))||(jSyllables&&G4_MAPPED_TEXT.has(text))||(qG6&&G6_MAPPED_TEXT.has(text))||(g6Search&&L24_G6_WORD_SEARCH_MAPPED_TEXT.has(text))||(l24Builder&&L24_G1_MAPPED_TEXT.has(text))||(l24G4Builder&&L24_G4_BUILDER_MAPPED_TEXT.has(text))||(g5Syllables&&L24_G5_SYLLABLE_MAPPED_TEXT.has(text))||(s9Helping&&S9_A2_MAPPED_TEXT.has(text)))playPrescribedAudio(text,true).catch(()=>{});}finally{busy=false;lock();}}
  function lock(){action.querySelectorAll('button').forEach(b=>b.disabled=busy||preview);}
  function lockG3(){if(l23G3)content.querySelectorAll('.wb-l23-g3-content button').forEach(b=>b.disabled=busy||preview);}
  function setG1ReadingState(next){
    if(!l22G1)return;
    const read=document.getElementById('wb-basahin');
    if(!read)return;
    read.disabled=next!=='idle'||preview;
    if(window.BasahinButton?.setState)window.BasahinButton.setState(read,next);
    else read.textContent=next==='listening'?'Nakikinig...':next==='processing'?'Sinusuri...':next==='calibrating'?'Sandali...':'Basahin';
  }
  function button(text,fn,primary=false){const b=document.createElement('button');b.type='button';b.textContent=text;b.className=primary?'wb-primary':'';if([record,recordJ,recordPictureReading,startCReading].includes(fn)){b.id='wb-basahin';if(window.Basahin?.bindActivity)window.Basahin.bindActivity(b,fn);else if(lesson23Activity)b.onclick=fn;}else b.onclick=fn;action.appendChild(b);return b;}
  function table(){let n=0;return `<table class="wb-table">${a.column_headers?'<thead><tr>'+a.column_headers.map(h=>`<th>${esc(h)}</th>`).join('')+'</tr></thead>':''}<tbody>${a.rows.map(row=>'<tr>'+row.map(text=>{const i=text?a.items[n++]:null;return `<td class="${!preview&&i?(n-1===state.index?'wb-current':n-1<state.index?'wb-done':''):''}">${i&&a.images?.[i.id]?`<img src="${esc(a.images[i.id])}" alt="${esc(text)}"><br>`:''}${esc(i?(a.cell_display?.[i.id]||text):'')}</td>`;}).join('')+'</tr>').join('')}</tbody></table>`;}
  function requestG6Restart(){
    if(document.getElementById('wb-g6-reset-modal'))return;
    document.body.insertAdjacentHTML('beforeend','<div class="wb-g6-reset-modal" id="wb-g6-reset-modal" role="dialog" aria-modal="true" aria-labelledby="wb-g6-reset-title"><div class="wb-g6-reset-card"><h2 id="wb-g6-reset-title">Ulitin Mula sa Simula</h2><p>Sigurado ka bang gusto mong ulitin mula sa simula?</p><div class="wb-g6-completion-actions"><button type="button" class="wb-g6-completion-primary" id="wb-g6-reset-yes">Oo, Ulitin</button><button type="button" class="wb-g6-completion-secondary" id="wb-g6-reset-no">Hindi</button></div></div></div>');
    const modal=document.getElementById('wb-g6-reset-modal');
    document.getElementById('wb-g6-reset-no').onclick=()=>modal.remove();
    document.getElementById('wb-g6-reset-yes').onclick=()=>{g6CompletionPromise=null;modal.remove();perform({action:'restart'});};

    modal.onclick=event=>{if(event.target===modal)modal.remove();};
  }
  function requestG7Restart(){
    if(document.getElementById('wb-g7-reset-modal'))return;
    document.body.insertAdjacentHTML('beforeend','<div class="wb-g7-reset-modal" id="wb-g7-reset-modal" role="dialog" aria-modal="true" aria-labelledby="wb-g7-reset-title"><div class="wb-g7-reset-card"><h2 id="wb-g7-reset-title">Ulitin ang Gawain 7?</h2><p>Mawawala ang kasalukuyang progreso.</p><div class="wb-g7-completion-actions"><button type="button" class="wb-g7-completion-primary" id="wb-g7-reset-yes">Oo, Magsimula Muli</button><button type="button" class="wb-g7-completion-secondary" id="wb-g7-reset-no">Hindi</button></div></div></div>');
    const modal=document.getElementById('wb-g7-reset-modal');
    document.getElementById('wb-g7-reset-no').onclick=()=>modal.remove();
    document.getElementById('wb-g7-reset-yes').onclick=()=>{modal.remove();perform({action:'restart'});};
    modal.onclick=event=>{if(event.target===modal)modal.remove();};
  }
  function requestS9A2Restart(){
    if(document.getElementById('wb-s9-a2-reset-modal'))return;
    document.body.insertAdjacentHTML('beforeend','<div class="wb-s9-a2-modal" id="wb-s9-a2-reset-modal" role="dialog" aria-modal="true" aria-labelledby="wb-s9-a2-reset-title"><div class="wb-s9-a2-modal-card"><h2 id="wb-s9-a2-reset-title">Start Activity 2 over?</h2><p>Your drawing and kind word will be erased.</p><div class="wb-s9-a2-modal-actions"><button type="button" id="wb-s9-a2-reset-no">No</button><button type="button" class="wb-primary" id="wb-s9-a2-reset-yes">Yes, erase them</button></div></div></div>');
    const modal=document.getElementById('wb-s9-a2-reset-modal');
    document.getElementById('wb-s9-a2-reset-no').onclick=()=>modal.remove();
    document.getElementById('wb-s9-a2-reset-yes').onclick=()=>{modal.remove();perform({action:'restart'});};
    modal.onclick=event=>{if(event.target===modal)modal.remove();};
  }
  function requestS9A1Restart(){
    if(document.getElementById('wb-s9-a1-reset-modal'))return;
    document.body.insertAdjacentHTML('beforeend','<div class="wb-s9-a1-modal" id="wb-s9-a1-reset-modal" role="dialog" aria-modal="true" aria-labelledby="wb-s9-a1-reset-title"><div class="wb-s9-a1-modal-card"><h2 id="wb-s9-a1-reset-title">Start Activity 1 over?</h2><p>Your drawing and sentence will be erased.</p><div class="wb-s9-a1-modal-actions"><button type="button" id="wb-s9-a1-reset-no">No</button><button type="button" class="wb-primary" id="wb-s9-a1-reset-yes">Yes, erase them</button></div></div></div>');
    const modal=document.getElementById('wb-s9-a1-reset-modal');
    document.getElementById('wb-s9-a1-reset-no').onclick=()=>modal.remove();
    document.getElementById('wb-s9-a1-reset-yes').onclick=()=>{modal.remove();perform({action:'restart'});};
    modal.onclick=event=>{if(event.target===modal)modal.remove();};
  }
  function requestS9A1Clear(clear){
    if(document.getElementById('wb-s9-a1-clear-modal'))return;
    document.body.insertAdjacentHTML('beforeend','<div class="wb-s9-a1-modal" id="wb-s9-a1-clear-modal" role="dialog" aria-modal="true" aria-labelledby="wb-s9-a1-clear-title"><div class="wb-s9-a1-modal-card"><h2 id="wb-s9-a1-clear-title">Erase the whole drawing?</h2><p>Your sentence will stay.</p><div class="wb-s9-a1-modal-actions"><button type="button" id="wb-s9-a1-clear-no">No</button><button type="button" class="wb-primary" id="wb-s9-a1-clear-yes">Yes, erase it</button></div></div></div>');
    const modal=document.getElementById('wb-s9-a1-clear-modal');
    document.getElementById('wb-s9-a1-clear-no').onclick=()=>modal.remove();
    document.getElementById('wb-s9-a1-clear-yes').onclick=()=>{modal.remove();clear();};
    modal.onclick=event=>{if(event.target===modal)modal.remove();};
  }
  function requestS9A2Clear(clear){
    if(document.getElementById('wb-s9-a2-clear-modal'))return;
    document.body.insertAdjacentHTML('beforeend','<div class="wb-s9-a2-modal" id="wb-s9-a2-clear-modal" role="dialog" aria-modal="true" aria-labelledby="wb-s9-a2-clear-title"><div class="wb-s9-a2-modal-card"><h2 id="wb-s9-a2-clear-title">Erase the whole drawing?</h2><p>Your kind word will stay.</p><div class="wb-s9-a2-modal-actions"><button type="button" id="wb-s9-a2-clear-no">No</button><button type="button" class="wb-primary" id="wb-s9-a2-clear-yes">Yes, erase it</button></div></div></div>');
    const modal=document.getElementById('wb-s9-a2-clear-modal');
    document.getElementById('wb-s9-a2-clear-no').onclick=()=>modal.remove();
    document.getElementById('wb-s9-a2-clear-yes').onclick=()=>{modal.remove();clear();};
    modal.onclick=event=>{if(event.target===modal)modal.remove();};
  }
  function setG7Feedback(text,error=false){const el=document.getElementById('wb-g7-feedback');if(el){el.textContent=text;el.classList.toggle('is-error',error);}}
  function lockG7(){content.querySelectorAll('.wb-g7-panel button').forEach(b=>b.disabled=busy||preview);}
  function renderL24G7WordReading(){
    const current=Math.min(Number(state.index||0),a.items.length-1), done=new Set(state.completed_words||[]), target=a.items[current];
    const columns=[0,1,2].map(column=>a.rows.map(row=>row[column]||''));
    const list=columns.map((column,columnIndex)=>`<div class="wb-g7-column">${column.map((text,rowIndex)=>{const index=columnIndex*8+rowIndex;if(!text)return '<span class="wb-g7-word is-empty" aria-hidden="true"></span>';const complete=done.has(index),active=index===current&&!state.completed;return `<div class="wb-g7-word ${complete?'is-done':''} ${active?'is-current':''}" ${active?'aria-current="step"':''}><span>${complete?'✓ ':''}${esc(text)}</span></div>`;}).join('')}</div>`).join('');
    const phase=state.reading_phase||'read', attempts=Number(state.reading_attempts||0), feedback=state.last_feedback||'Handa ka na?';
    content.innerHTML=`<section class="wb-g7-workspace"><article class="wb-g7-panel wb-g7-list-panel"><div class="wb-g7-panel-heading"><h2>MGA SALITA</h2><span>${a.items.length} salita</span></div><div class="wb-g7-columns">${list}</div></article><article class="wb-g7-panel wb-g7-reading-panel"><h2>BASAHIN</h2><p class="wb-g7-subtitle">Tunog / Salitang Babasahin</p><strong class="wb-g7-current-word">${esc(target?.text||'—')}</strong><p class="wb-g7-attempts">Pagsubok: ${state.completed?0:attempts} / 3</p><div class="wb-g7-controls"><button type="button" class="wb-g7-read-button" id="wb-basahin" aria-label="Simulan ang pagbasa ng ${esc(target?.text||'salita')}">🎙 Simulan ang Pagbasa</button>${phase==='help'?`<button type="button" class="wb-g7-listen-button" id="wb-g7-listen">🔊 Pakinggan ang Tamang Pagbigkas</button><button type="button" class="wb-g7-retry-button" id="wb-g7-retry">Subukan Muli</button>`:''}</div><div class="wb-g7-transcript" aria-live="polite"><span>NARINIG KO</span><strong>${esc(state.last_transcript||'—')}</strong></div><p class="wb-g7-feedback ${state.last_feedback==='Subukan muli.'?'is-error':''}" id="wb-g7-feedback" role="status" aria-live="polite">${esc(feedback)}</p><button type="button" class="wb-g7-reset" id="wb-g7-reset">Ulitin Mula sa Simula</button></article></section>`;
    if(!preview&&!instructionSpoken){instructionSpoken=true;setTimeout(()=>playPrescribedAudio(instructionText).catch(e=>console.error('Gawain 7 instruction audio failed',e)),0);}
    const read=document.getElementById('wb-basahin');
    if(read&&!preview){if(window.Basahin?.bindActivity)window.Basahin.bindActivity(read,recordL24G7Reading);else if(lesson23Activity)read.onclick=recordL24G7Reading;}
    if(preview){content.querySelectorAll('button').forEach(b=>b.disabled=true);return;}
    document.getElementById('wb-g7-listen')?.addEventListener('click',async()=>{if(busy)return;busy=true;lockG7();try{await playPrescribedAudio(target?.text||'',true);await send({action:'read_aloud'},null,false);render();}catch(e){setG7Feedback(e.message||'Hindi available ang audio.',true);}finally{busy=false;lockG7();}});
    document.getElementById('wb-g7-retry')?.addEventListener('click',()=>perform({action:'retry_reading'}));
    document.getElementById('wb-g7-reset')?.addEventListener('click',requestG7Restart);
    lockG7();
  }
  async function recordL24G7Reading(){
    if(busy||!navigator.mediaDevices?.getUserMedia||!window.MediaRecorder){const text='Hindi magamit ang mikropono. Subukan muli.';setG7Feedback(text,true);if(L24_G7_WORD_READING_MAPPED_TEXT.has(text))playPrescribedAudio(text,true).catch(()=>{});return;}
    busy=true;lockG7();let stream=null,recorder=null,requestIndex=Number(state.index||0),requestRevision=Number(state.revision||0),requestActivity=a.activity_key;
    try{
      setG7Feedback('🎙️ Nakikinig... Basahin ang salita.');
      stream=activeStream=await window.Basahin.openMicrophone({audio:true});
      const audio=await window.Basahin.capture({button:document.getElementById('wb-basahin'),stream,onRecorder:value=>{recorder=activeRecorder=value;}});stream.getTracks().forEach(t=>t.stop());activeStream=null;activeRecorder=null;
      if(!audio.size)throw Error('Hindi nakuha ang iyong boses. Subukan muli.');
      if(requestActivity!==a.activity_key||requestIndex!==Number(state.index||0)||requestRevision!==Number(state.revision||0))return;
      setG7Feedback('Sinusuri ang iyong pagbasa...');await playPrescribedAudio('Sinusuri ang iyong pagbasa...',true);const form=new FormData();form.append('audio',audio,'reading.webm');
      await send({action:'reading_attempt',item_index:requestIndex},form,false);render();
      if(state.completed)await playPrescribedAudio('Magaling! Natapos mo ang Gawain 7.',true);else if(state.last_feedback)await playPrescribedAudio(state.last_feedback,true).catch(()=>{});
    }catch(e){stream?.getTracks().forEach(t=>t.stop());activeStream=null;activeRecorder=null;const denied=e?.name==='NotAllowedError'||e?.name==='SecurityError';const text=denied?'Hindi pinayagan ang mikropono.':e.message||'Hindi nakuha ang iyong boses. Subukan muli.';setG7Feedback(text,true);if(L24_G7_WORD_READING_MAPPED_TEXT.has(text))await playPrescribedAudio(text,true).catch(()=>{});
    }finally{busy=false;lockG7();}
  }
  function render(){
    selected=[];builder=state.draft?.builder||[];words=state.draft?.words||[];
    const totalProgress=cBuilder?a.items.length:(a.progress_total||a.items.length), progressValue=state.completed?totalProgress:Math.min(totalProgress, g6Search?Object.keys(state.found_words||{}).length:g7Reading?Number(state.index||0):qBuilder?Number(state.index||0):cBuilder?Number(state.index||0):Number(state.index||0));
    document.getElementById('wb-progress').textContent=preview?'Preview':(g6Search?`Nahanap: ${Object.keys(state.found_words||{}).length} / ${a.items.length}`:g7Reading?`Nabasa: ${Math.min(a.items.length,Number(state.index||0))} / ${a.items.length}`:l24G4Builder?`Nabuo: ${Number(state.built_words?.length||0)} salita`:g5Syllables?`Nasagot: ${Math.min(a.items.length,Number(state.index||0))} / ${a.items.length}`:cBuilder?`Nabasa: ${Math.min(a.items.length,Number(state.index||0))} / ${a.items.length}`:(a.activity_key==='aral-l23-g1-n-syllable-builder'||l24Builder?`Nabasa: ${Math.min(12,Number(state.index||0))} / 12`:`${progressValue} / ${totalProgress}`));
    const progressFill=document.getElementById('wb-progress-fill');if(progressFill)progressFill.style.width=l24G4Builder?(state.completed?'100%':'0%'):`${preview?0:Math.max(0,Math.min(100,progressValue/totalProgress*100))}%`;
    const backLink=document.getElementById('wb-back');if(backLink)backLink.hidden=preview;
    if(qBuilder&&actionHost&&action.parentElement!==actionHost)actionHost.appendChild(action);
    action.replaceChildren();
    if(g6Search&&!state.completed)document.getElementById('wb-g6-completion-modal')?.remove();
    if(state.completed){
      const completionWord=a.activity_key==='aral-l23-g1-n-syllable-builder'?'Niño':(state.found_words||[]).join(', ');
      if(g6Search){
        renderL24G6WordSearch();
        if(!document.getElementById('wb-g6-completion-modal')){
          document.body.insertAdjacentHTML('beforeend',`<div class="wb-g6-completion-modal" id="wb-g6-completion-modal" role="dialog" aria-modal="true" aria-labelledby="wb-g6-completion-title"><div class="wb-g6-completion-card"><p class="wb-g6-completion-kicker">SESSION 8 · LESSON 24 · BAHAGI 2 · GAWAIN 6</p><h2 id="wb-g6-completion-title">Magaling!</h2><p>Natapos mo ang Gawain 6.</p><p>Nahanap mo ang lahat ng sampung salita sa Big Box.</p><div class="wb-g6-completion-actions">${data.next_url?`<a class="wb-g6-completion-primary" href="${esc(data.next_url)}">SUNOD NA GAWAIN</a>`:''}<a class="wb-g6-completion-secondary" href="${esc(document.getElementById('wb-back')?.href||'#')}">BUMALIK SA AKING ARALIN</a><button type="button" class="wb-g6-completion-secondary" id="wb-g6-complete-reset">Ulitin Mula sa Simula</button></div></div></div>`);
        }
        const completeReset=document.getElementById('wb-g6-complete-reset');
        if(completeReset)completeReset.onclick=requestG6Restart;
        return;
      }
      if(g7Reading){
        content.innerHTML=`<div class="wb-g7-completion-modal" role="dialog" aria-modal="true" aria-labelledby="wb-g7-completion-title"><div class="wb-g7-completion-card"><p class="wb-g7-completion-kicker">GAWAIN 7 · PAGBASA</p><h2 id="wb-g7-completion-title">Magaling! Natapos mo ang Gawain 7!</h2><p>Nabasa mo nang tama ang lahat ng 23 salita.</p><div class="wb-g7-completion-actions"><a class="wb-g7-completion-secondary" href="${esc(document.getElementById('wb-back')?.href||'#')}">Bumalik sa Aking Aralin</a><button type="button" class="wb-g7-completion-secondary" id="wb-g7-complete-reset">Ulitin Mula sa Simula</button></div></div></div>`;
        document.getElementById('wb-g7-complete-reset')?.addEventListener('click',requestG7Restart);
        return;
      }
      if(l23G1){
        renderCBuilder();
        if(!document.getElementById('wb-l23-g1-completion-modal')){
          document.body.insertAdjacentHTML('beforeend',`<div class="wb-l23-g1-completion-modal" id="wb-l23-g1-completion-modal" role="dialog" aria-modal="true" aria-labelledby="wb-l23-g1-completion-title"><div class="wb-l23-g1-completion-card"><p class="wb-l23-g1-completion-kicker">SESSION 8 · LESSON 23 · GAWAIN 1</p><h2 id="wb-l23-g1-completion-title">Magaling!</h2><p>Natapos mo ang Gawain 1.</p><div class="wb-l23-g1-completion-actions">${data.next_url?`<a class="wb-l23-g1-completion-primary" href="${esc(data.next_url)}">SUNOD NA GAWAIN</a>`:''}<a class="wb-l23-g1-completion-secondary" href="${esc(data.back_url||document.getElementById('wb-back')?.href||'#')}">BUMALIK SA AKING ARALIN</a></div></div></div>`);
        }
        return;
      }
      if(l22G1){
        // Keep the completed activity visible behind the standard target
        // completion overlay. The server has already persisted both gates
        // before state.completed can reach this branch.
        renderCBuilder();
        if(!document.getElementById('wb-l22-g1-completion-modal')){
          document.body.insertAdjacentHTML('beforeend',`<div class="wb-l22-g1-completion-modal" id="wb-l22-g1-completion-modal" role="dialog" aria-modal="true" aria-labelledby="wb-l22-g1-completion-title"><div class="wb-l22-g1-completion-card"><p class="wb-l22-g1-completion-kicker">SESSION 8 · LESSON 22 · GAWAIN 1</p><h2 id="wb-l22-g1-completion-title">Magaling!</h2><p>Natapos mo ang Gawain 1.</p><div class="wb-l22-g1-completion-actions">${data.next_url?`<a class="wb-l22-g1-completion-primary" href="${esc(data.next_url)}">SUNOD NA GAWAIN</a>`:''}<a class="wb-l22-g1-completion-secondary" href="${esc(data.back_url||document.getElementById('wb-g1-back')?.href||'#')}">BUMALIK SA AKING ARALIN</a></div></div></div>`);
        }
        return;
      }
      if(s9Family){
        content.innerHTML=`<div class="wb-s9-a1-completion" role="dialog" aria-modal="true" aria-labelledby="wb-s9-a1-completion-title"><p class="wb-s9-a1-kicker">SESSION 9 · ACTIVITY 1</p><h2 id="wb-s9-a1-completion-title">Good job! Activity 1 is complete!</h2><p>Your family drawing and sentence were saved.</p><div class="wb-s9-a1-completion-actions">${data.next_url?`<a class="wb-primary" href="${esc(data.next_url)}">Next Activity</a>`:''}<a href="${esc(document.getElementById('wb-back')?.href||'#')}">Back to My Lesson</a><button type="button" id="wb-s9-a1-complete-reset">Start Over</button></div></div>`;
        document.getElementById('wb-s9-a1-complete-reset')?.addEventListener('click',requestS9A1Restart);
        return;
      }
      if(s9Helping){
        content.innerHTML=`<div class="wb-s9-a2-completion" role="dialog" aria-modal="true" aria-labelledby="wb-s9-a2-completion-title"><p class="wb-s9-a2-kicker">SESSION 9 · ACTIVITY 2</p><h2 id="wb-s9-a2-completion-title">Good job! Activity 2 is complete!</h2><p>Your drawing and kind word were saved.</p><div class="wb-s9-a2-completion-actions">${data.next_url?`<a class="wb-primary" href="${esc(data.next_url)}">Next Activity</a>`:''}<a href="${esc(document.getElementById('wb-back')?.href||'#')}">Back to My Lesson</a><button type="button" id="wb-s9-a2-complete-reset">Start Over</button></div></div>`;
        document.getElementById('wb-s9-a2-complete-reset')?.addEventListener('click',requestS9A2Restart);
        return;
      }
      content.innerHTML=`<div class="wb-focus"><h2>${s9Family?'Good job! Activity 1 is complete!':cBuilder?'Magaling! Natapos mo ang Gawain 1.':l24G4Builder?'Magaling! Natapos mo ang Gawain 4.':g5Syllables?'Magaling! Natapos mo ang Gawain 5!':g6Search?'Magaling! Natapos mo ang Gawain 6!':fil?'Natapos mo ang gawain!':'Activity complete!'}</h2>${cBuilder?`<p>${a.activity_key==='aral-l23-g1-n-syllable-builder'?`Magaling! Nabuo mo ang salitang ${completionWord}`:`Nabuo mo na: ${esc(completionWord)}`}</p>`:s9Family?'<p>Your work was saved for the teacher.</p>':g5Syllables?'<p>Natapos mo ang lahat ng siyam na salitang kailangang pantigin.</p>':g6Search?'<p>Nahanap mo ang lahat ng sampung salita sa Big Box.</p>':a.review_required&&!l24G4Builder?'<p>Your written work is saved for teacher review.</p>':''}</div>`;
      if(cBuilder||l24G4Builder){button('Susunod',()=>{if(data.next_url)location.href=data.next_url;},true).disabled=!data.next_url;if(l24G4Builder)button('Ulitin Mula sa Simula',()=>{if(window.confirm('Ulitin ang Gawain 4 mula sa simula?'))perform({action:'restart'});});}
      if((prescribedWordReading||jSyllables||g5Syllables||pictureReading)&&data.next_url)button('Susunod',()=>{location.href=data.next_url;},true);
      if(g5Syllables)button('Ulitin Mula sa Simula',()=>{if(window.confirm('Ulitin ang Gawain 5 mula sa simula? Mawawala ang kasalukuyang progreso.'))perform({action:'restart'});});
      return;
    }
    if(g7Reading){renderL24G7WordReading();return;}
    if(prescribedWordReading){renderJReading();return;}
    if(pictureReading){renderPictureReading();return;}
    if(jSyllables){renderSyllables();return;}
    if(g5Syllables){renderL24G5Syllables();return;}
    if(g6Search){renderL24G6WordSearch();return;}
    if(specializedBuilder&&!preview){renderCBuilder();if(qBuilder){const workspace=document.createElement('div');workspace.className='wb-g6-workspace';const readingPanel=content.querySelector('.wb-reading-panel');const wordPanel=content.querySelector('.wb-word-panel');if(readingPanel)workspace.appendChild(readingPanel);if(wordPanel)workspace.appendChild(wordPanel);content.appendChild(workspace);content.appendChild(action);}lock();return;}
    if(l24G4Builder&&!preview){renderBuilder();lock();return;}
    if(state.index>=a.items.length&&!preview){content.innerHTML='<div class="wb-focus">'+(session9Activity?'All parts are saved.':(fil?'Na-save ang lahat ng bahagi ng gawain.':'All required parts are saved.'))+'</div>';button(fil?'Tapusin ang gawain':'Finish activity',()=>perform({action:'finish'}),true);return;}
    const kind=a.interaction_type;
    content.innerHTML=preview?'<p class="wb-preview-note">Preview · '+(fil?'Walang sagot na napili.':'No answers selected.')+'</p>':'';
    if(kind==='search')renderSearch();
    else if(kind==='drawing')renderDrawing();
    else if(kind==='fill')renderFill();
    else if(kind==='syllables')renderSyllables();
    else if(a.group_titles){content.innerHTML+=a.rows.map((row,i)=>`<section class="wb-focus"><h2>${esc(a.group_titles[i])}</h2><p class="wb-verse">${esc(row[0])}</p></section>`).join('');}
    else if(kind==='builder'){if(preview)content.innerHTML+=table();}
    else if(kind==='reading'){if(preview)content.innerHTML+=table();}
    else content.innerHTML+=table();
    if(preview){if(cBuilder)renderCBuilder();else if(kind==='builder')renderBuilder();return;}
    if(a.oral_flow&&!oral().passed){
      const focus=document.createElement('div');focus.className='wb-focus wb-reading-focus';
      const image=a.images?.[item().id]?`<img class="wb-hero-image" src="${esc(a.images[item().id])}" alt="${esc(item().text)}">`:'';
      const verseTitle=a.group_titles?.[state.index]?`<h2>${esc(a.group_titles[state.index])}</h2>`:'';
      focus.innerHTML=`${image}${verseTitle}<strong>${esc(item().text)}</strong>`;action.appendChild(focus);
      const o=oral();
      button(o.phase==='read'?(fil?`Basahin (${o.attempts}/3)`:`Read (${o.attempts}/3)`):o.phase==='model'?'Read Aloud':`Read Aloud (${o.listens}/3)`,o.phase==='read'?record:aloud,true);
    }else if(kind==='reading'||kind==='builder'&&state.index<a.items.length-1){button(fil?'Susunod':'Next',()=>perform({action:'answer',answer:null}),true);}
    else if(kind==='builder')renderBuilder();
    else if(kind==='search'){button(fil?'Piliin ang salita':'Select word',()=>perform({action:'answer',answer:selected}),true);}
    else if(kind==='syllables'){button(fil?'Isumite':'Submit',()=>perform({action:'answer',answer:{text:document.getElementById('wb-written').value}}),true);}
    else if(kind==='fill'){button('Submit',()=>perform({action:'answer',answer:{blanks:[...content.querySelectorAll('[data-blank]')].map(s=>s.value)}}),true);}
    else if(kind==='drawing'){button(s9Family?'Complete Activity':s9Helping?'✓ Tapusin':'Submit drawing and writing',()=>perform({action:'answer',answer:{text:document.getElementById('wb-written').value,strokes:state.draft.strokes||[]}}),true);}
    lock();
  }
  function instructionBanner(){
    return `<div class="wb-instruction-banner"><span>${esc(instructionText)}</span><button type="button" id="wb-instruction-replay" aria-label="Pakinggan muli ang panuto">Pakinggan Muli</button></div>`;
  }
  function speakInstruction(){
    if(preview||instructionSpoken||((lesson23Activity||lesson24Activity)&&!activityStarted))return;
    instructionSpoken=true;
    const play=()=>playPrescribedAudio(instructionText).catch(e=>{console.error('Workbook instruction audio failed',e);if((l23G3&&G3_MAPPED_TEXT.has(e.message))||(qReading&&G7_MAPPED_TEXT.has(e.message))||(jSyllables&&G4_MAPPED_TEXT.has(e.message))||(l24G3WordReading&&L24_G3_WORD_MAPPED_TEXT.has(e.message))){if(e.message!==instructionText)playPrescribedAudio(e.message,true).catch(()=>{});}});
    if(lesson23Activity||lesson24Activity)play();else setTimeout(play,0);
  }
  function renderJReading(){
    if(l23G3){
      const current=Number(state.index||0), done=new Set(state.completed_words||[]), target=a.items[current];
      content.innerHTML=`<section class="wb-l23-g3-content"><article class="wb-l23-g3-panel wb-l23-g3-list-panel"><h2>Mga salitang may letrang Jj</h2><div class="wb-l23-g3-word-grid" role="list" aria-label="Mga salitang may letrang Jj">${a.items.map((it,i)=>`<div class="wb-l23-g3-word ${done.has(i)?'is-done':''} ${i===current&&!state.completed?'is-current':''}" ${i===current&&!state.completed?'aria-current="step"':''} role="listitem">${done.has(i)?'<span aria-hidden="true">✓ </span>':''}${esc(it.text)}</div>`).join('')}</div></article><article class="wb-l23-g3-panel wb-l23-g3-reading-panel"><h2>BASAHIN</h2><p class="wb-l23-g3-subtitle">SALITANG BABASAHIN</p><strong class="wb-l23-g3-target">${esc(target?.text||'—')}</strong><p class="wb-l23-g3-attempts">Pagsubok: ${state.completed?0:Number(state.reading_attempts||0)} / 3</p><div class="wb-l23-g3-controls"></div><div class="wb-l23-g3-heard" aria-live="polite"><span>NARINIG KO</span><strong>${esc(state.last_transcript||'—')}</strong></div><p class="wb-l23-g3-feedback ${state.last_feedback==='Subukan muli.'?'is-error':''}" id="wb-j-feedback" role="status" aria-live="polite">${esc(state.last_feedback||'Handa ka na.')}</p></article></section>`;
      const replay=document.getElementById('wb-instruction-replay');
      if(replay)replay.onclick=()=>{if(!busy&&!activeStream)playPrescribedAudio(instructionText).catch(e=>{const text=e.message||'Hindi available ang panuto.';setJFeedback(text,true);if(G3_MAPPED_TEXT.has(text))playPrescribedAudio(text,true).catch(()=>{});});};
      const controls=content.querySelector('.wb-l23-g3-controls');
      if(!preview&&target){
        const read=document.createElement('button');read.type='button';read.id='wb-basahin';read.className='wb-primary';read.textContent=window.BasahinButton?.LABEL||'Basahin';read.setAttribute('aria-label',`Basahin ang salitang ${target.text}`);if(window.Basahin?.bindActivity)window.Basahin.bindActivity(read,recordJ);else read.onclick=recordJ;controls.appendChild(read);
        const help=document.createElement('button');help.type='button';help.className='wb-l23-g3-secondary';help.textContent='Pakinggan ang Tamang Pagbigkas';help.setAttribute('aria-label',`Pakinggan ang tamang pagbigkas ng ${target.text}`);help.onclick=()=>playPrescribedAudio(target.text).catch(e=>{const text=e.message||'Hindi available ang audio.';setJFeedback(text,true);if(G3_MAPPED_TEXT.has(text))playPrescribedAudio(text,true).catch(()=>{});});controls.appendChild(help);
      }
      if(!preview)speakInstruction();
      lockG3();
      return;
    }
    const current=Number(state.index||0), done=new Set(state.completed_words||[]);
    content.innerHTML=`${instructionBanner()}<section class="wb-focus wb-j-reading"><h2>Mga salitang may letrang Jj</h2><div class="wb-j-grid">${a.items.map((it,i)=>`<div class="wb-j-word ${done.has(i)?'is-done':''} ${i===current?'is-current':''}" aria-current="${i===current?'step':'false'}">${esc(it.text)}${done.has(i)?'<span aria-label="Tapos na"> ✓</span>':''}</div>`).join('')}</div><p class="wb-j-feedback" id="wb-j-feedback" role="status" aria-live="polite">${esc(state.last_feedback||'Handa ka na.')}</p></section>`;
    const readingHeading=content.querySelector('.wb-j-reading h2');
    if(readingHeading)readingHeading.textContent=a.title;
    const replay=document.getElementById('wb-instruction-replay');
    replay.onclick=()=>{if(!busy&&!activeStream)playPrescribedAudio(instructionText).catch(e=>{const text=e.message||'Hindi available ang panuto.';setJFeedback(text,true);if((l23G3&&G3_MAPPED_TEXT.has(text))||(qReading&&G7_MAPPED_TEXT.has(text))||(l24G3WordReading&&L24_G3_WORD_MAPPED_TEXT.has(text)))playPrescribedAudio(text,true).catch(()=>{});});};
    if(!preview)speakInstruction();
    if(preview)return;
    if(current<a.items.length){
      const word=a.items[current];
      const card=document.createElement('div');card.className='wb-j-controls';
      const read=button(window.BasahinButton?.LABEL||'Basahin',recordJ,true);read.setAttribute('aria-label',`Basahin ang salitang ${word.text}`);
      const help=button('Pakinggan ang Tamang Pagbigkas',()=>playPrescribedAudio(word.text).catch(e=>{const text=e.message||'Hindi available ang audio.';setJFeedback(text,true);if((l23G3&&G3_MAPPED_TEXT.has(text))||(qReading&&G7_MAPPED_TEXT.has(text))||(l24G3WordReading&&L24_G3_WORD_MAPPED_TEXT.has(text)))playPrescribedAudio(text,true).catch(()=>{});}),false);help.setAttribute('aria-label',`Pakinggan ang tamang pagbigkas ng ${word.text}`);
      card.append(read,help);action.appendChild(card);
    }
    setJFeedback(state.last_feedback||'Handa ka na.');
  }
  function setJFeedback(text,error=false){const el=document.getElementById('wb-j-feedback');if(el){el.textContent=text;el.classList.toggle('wb-feedback-error',error);}}
  function setPictureFeedback(text,error=false){const el=document.getElementById('wb-picture-feedback');if(el){el.textContent=text;el.classList.toggle('wb-feedback-error',error);}}
  function renderPictureReading(){
    const current=Math.min(Number(state.index||0),a.items.length-1), target=a.items[current];
    const done=new Set(state.completed_words||[]);
    const steps=a.items.map((it,i)=>`<span class="wb-picture-step ${done.has(i)?'is-done':''} ${i===current&&!state.completed?'is-current':''}" aria-label="${i+1} sa ${a.items.length}">${done.has(i)?'✓':i+1}</span>`).join('');
    document.getElementById('wb-progress').innerHTML=steps;
    content.innerHTML=`${instructionBanner()}<section class="wb-picture-reading">${state.completed?`<div class="wb-picture-complete" role="status">Magaling! Natapos mo ang gawain. 🎉</div>`:`<img class="wb-picture-image" src="${esc(a.images?.[target.id]||'')}" alt="Larawan ng ${esc(target.text)}"><strong class="wb-picture-word">${esc(target.text)}</strong><p class="wb-picture-feedback" id="wb-picture-feedback" role="status" aria-live="polite">${esc(state.last_feedback||'Basahin ang salitang nasa larawan.')}</p>`}</section>`;
    const replay=document.getElementById('wb-instruction-replay');
    if(replay)replay.onclick=()=>{if(!busy&&!activeStream)playPrescribedAudio(instructionText).catch(e=>setPictureFeedback(e.message||'Hindi available ang panuto.',true));};
    if(!preview&&!instructionSpoken&&!pictureReading){instructionSpoken=true;setTimeout(async()=>{try{await playPrescribedAudio(instructionText);if(!state.last_feedback)await playPrescribedAudio('Basahin ang salitang nasa larawan.');}catch(e){console.error('Picture activity instruction audio failed',e);}},0);}
    if(preview||state.completed)return;
    const listen=button('🔊 Pakinggan',()=>playPrescribedAudio(target.text).catch(e=>setPictureFeedback(e.message||'Hindi available ang audio.',true)),false);
    listen.setAttribute('aria-label',`Pakinggan ang ${target.text}`);
    const read=button(window.BasahinButton.LABEL,recordPictureReading,true);
    read.setAttribute('aria-label',`Basahin ang salitang ${target.text}`);
    const controls=document.createElement('div');controls.className='wb-picture-controls';controls.append(read,listen);action.appendChild(controls);
    lock();
  }
  async function recordPictureReading(){
    if(busy||!navigator.mediaDevices?.getUserMedia||!window.MediaRecorder){setPictureFeedback('Hindi magamit ang mikropono. Subukan muli.',true);playPrescribedAudio('Hindi magamit ang mikropono. Subukan muli.',true).catch(()=>{});return;}
    busy=true;lock();let stream=null,recorder=null,requestIndex=Number(state.index||0),requestRevision=Number(state.revision||0),attempt=null,modelPromise=null,modelError=null;
    attempt={id:Symbol('picture-guided-attempt'),controller:new AbortController(),modelAudio:null,modelStartedAt:0,modelEndedAt:0,recordingStartedAt:0,recordingEndedAt:0,submitted:false};
    pictureGuidedAttempt=attempt;
    const target=a.items[requestIndex];
    const playGuidedModel=()=>new Promise((resolve,reject)=>{
      const url=localAudioUrl(target?.text);
      if(!url){reject(Object.assign(new Error('Hindi available ang audio.'),{code:'mapped_audio_missing'}));return;}
      const audio=new Audio(url);attempt.modelAudio=audio;activeReadAloud=audio;
      let settled=false;
      const timer=window.setTimeout(()=>finish(Object.assign(new Error('Hindi available ang audio.'),{code:'mapped_audio_timeout'})),15000);
      const cleanup=()=>{window.clearTimeout(timer);attempt.controller.signal.removeEventListener('abort',onAbort);audio.onplaying=audio.onended=audio.onerror=null;if(activeReadAloud===audio)activeReadAloud=null;};
      const finish=(error)=>{if(settled)return;settled=true;cleanup();if(error){try{audio.pause();audio.currentTime=0;}catch(_){}reject(error);}else resolve();};
      const onAbort=()=>finish(new DOMException('Guided reading canceled.','AbortError'));
      attempt.controller.signal.addEventListener('abort',onAbort,{once:true});
      if(attempt.controller.signal.aborted){onAbort();return;}
      audio.onplaying=()=>{attempt.modelStartedAt=performance.now();console.info('L24_G4_GUIDED_MODEL_PLAYING',{word:target.text,at:attempt.modelStartedAt,recordingStartedAt:attempt.recordingStartedAt});};
      audio.onended=()=>{attempt.modelEndedAt=performance.now();console.info('L24_G4_GUIDED_MODEL_END',{word:target.text,at:attempt.modelEndedAt,recordingStartedAt:attempt.recordingStartedAt,recordingEndedAt:attempt.recordingEndedAt});finish();};
      audio.onerror=()=>finish(Object.assign(new Error('Hindi available ang audio.'),{code:'mapped_audio_playback_failed'}));
      try{Promise.resolve(audio.play()).catch(error=>finish(Object.assign(new Error('Hindi available ang audio.'),{code:'mapped_audio_playback_failed',cause:error})));}catch(error){finish(Object.assign(new Error('Hindi available ang audio.'),{code:'mapped_audio_playback_failed',cause:error}));}
    });
    try{
      setPictureFeedback('🎙️ Nakikinig... Basahin ang salita.');
      console.info('L24_G4_GUIDED_MIC_REQUEST',{word:target.text,at:performance.now(),secureContext:window.isSecureContext,mediaDevices:Boolean(navigator.mediaDevices?.getUserMedia)});
      try{
        stream=activeStream=await window.Basahin.openMicrophone({audio:{echoCancellation:true,noiseSuppression:false,autoGainControl:true}},{signal:attempt.controller.signal});
        const tracks=stream.getAudioTracks();
        console.info('L24_G4_GUIDED_MIC_RESOLVED',{word:target.text,at:performance.now(),trackCount:tracks.length,tracks:tracks.map(track=>{const settings=track.getSettings?.()||{};return {readyState:track.readyState,enabled:track.enabled,muted:track.muted,sampleRate:settings.sampleRate||null,channelCount:settings.channelCount||null,echoCancellation:settings.echoCancellation??null,noiseSuppression:settings.noiseSuppression??null,autoGainControl:settings.autoGainControl??null};})});
      }catch(error){
        const name=error?.name||'Error',failure=name==='NotAllowedError'||name==='SecurityError'?'permission_denied':name==='NotFoundError'?'no_input_device':name==='NotReadableError'?'device_unreadable':error?.message?.startsWith('Hindi tumugon ang mikropono')?'acquisition_timeout':'acquisition_error';
        console.info('L24_G4_GUIDED_MIC_FAILED',{word:target.text,at:performance.now(),failure,name});
        throw error;
      }
      const capturePromise=window.Basahin.capture({button:document.getElementById('wb-basahin'),stream,signal:attempt.controller.signal,silenceMs:2200,maxRecordingMs:12000,diagnostics:true,onDiagnostic:(event,detail)=>console.info('L24_G4_GUIDED_RECORDER',{word:target.text,event,...detail}),onRecorder:value=>{recorder=activeRecorder=value;},onRecordingStarted:value=>{recorder=activeRecorder=value;attempt.recordingStartedAt=performance.now();console.info('L24_G4_GUIDED_RECORDING_START',{word:target.text,at:attempt.recordingStartedAt,recorderState:value?.state});modelPromise=playGuidedModel().catch(error=>{modelError=error;attempt.controller.abort();});}});
      const audio=await capturePromise;
      attempt.recordingEndedAt=performance.now();console.info('L24_G4_GUIDED_RECORDING_END',{word:target.text,at:attempt.recordingEndedAt,modelStartedAt:attempt.modelStartedAt,modelEndedAt:attempt.modelEndedAt});
      if(modelPromise)await modelPromise;
      if(modelError)throw modelError;
      if(pictureGuidedAttempt!==attempt||attempt.controller.signal.aborted)return;
      stream.getTracks().forEach(t=>t.stop());if(activeStream===stream)activeStream=null;if(activeRecorder===recorder)activeRecorder=null;
      if(requestIndex!==Number(state.index||0)||requestRevision!==Number(state.revision||0))return;
      if(!audio?.size)throw Error('Hindi nakuha ang boses. Subukan muli.');
      const form=new FormData();form.append('audio',audio,'reading.webm');
      attempt.submitted=true;console.info('L24_G4_GUIDED_SUBMIT',{word:target.text,at:performance.now(),count:1});
      const saved=await send({action:'reading_attempt',item_index:requestIndex},form,false,null,()=>pictureGuidedAttempt===attempt&&!attempt.controller.signal.aborted&&requestIndex===Number(state.index||0)&&requestRevision===Number(state.revision||0));
      console.info('L24_G4_GUIDED_API_RESULT',{word:target.text,at:performance.now(),success:Boolean(saved),accepted:saved?state.last_feedback==='Tama! Magaling!'||state.last_feedback==='Magaling! Natapos mo ang gawain.':false});
      if(!saved||pictureGuidedAttempt!==attempt||attempt.controller.signal.aborted)return;
      render();
      const feedback=state.completed?'Magaling! Natapos mo ang gawain.':state.last_feedback;
      if(L24_G2_PICTURE_MAPPED_TEXT.has(feedback))await playPrescribedAudio(feedback,true);
    }catch(e){
      if(modelError)e=modelError;
      const stillCurrent=pictureGuidedAttempt===attempt&&e?.name!=='AbortError';
      if(attempt?.submitted)console.info('L24_G4_GUIDED_API_RESULT',{word:target.text,at:performance.now(),success:false,failure:e?.code||e?.name||'request_error'});
      else console.info('L24_G4_GUIDED_ATTEMPT_FAILED',{word:target.text,at:performance.now(),failure:e?.name==='NoSpeechError'?'no_speech':e?.name||'recording_error'});
      attempt?.controller.abort();if(recorder&&recorder.state!=='inactive'){try{recorder.stop();}catch(_){}}stream?.getTracks().forEach(t=>t.stop());if(activeStream===stream)activeStream=null;if(activeRecorder===recorder)activeRecorder=null;
      if(attempt?.modelAudio){try{attempt.modelAudio.pause();attempt.modelAudio.currentTime=0;}catch(_){}}if(activeReadAloud===attempt?.modelAudio)activeReadAloud=null;
      if(!stillCurrent)return;
      const denied=e?.name==='NotAllowedError'||e?.name==='SecurityError';
      const feedback=denied?'Hindi magamit ang mikropono. Subukan muli.':e?.code?.startsWith('mapped_audio')?null:L24_G2_PICTURE_MAPPED_TEXT.has(e?.message)?e.message:'Hindi nakuha ang boses. Subukan muli.';
      setPictureFeedback(denied?'Hindi pinayagan ang mikropono. Subukan muli.':e.message||feedback,true);
      if(feedback)playPrescribedAudio(feedback,true).catch(()=>{});
    }finally{
      attempt?.controller.abort();
      if(recorder&&recorder.state!=='inactive'){try{recorder.stop();}catch(_){}}
      stream?.getTracks().forEach(t=>t.stop());
      if(attempt?.modelAudio){try{attempt.modelAudio.pause();attempt.modelAudio.currentTime=0;}catch(_){}}
      if(activeReadAloud===attempt?.modelAudio)activeReadAloud=null;
      if(activeStream===stream)activeStream=null;if(activeRecorder===recorder)activeRecorder=null;
      if(pictureGuidedAttempt===attempt){pictureGuidedAttempt=null;busy=false;lock();}
    }
  }
  function renderJSyllables(){
    const current=Number(state.index||0), item=a.items[current];
    content.innerHTML=`${instructionBanner()}<section class="wb-focus wb-j-syllables"><h2>Pantigin ang sumusunod na salita.</h2><div class="wb-syllable-rows">${a.items.map((it,i)=>`<div class="wb-syllable-row ${i<current?'is-done':''} ${i===current?'is-current':''}"><span>${i+1}. ${esc(it.text)}</span><span>–</span><span>${i===current?'<input id="wb-j-answer" type="text" inputmode="text" autocomplete="off" aria-label="Sagot para sa '+esc(it.text)+'" value="'+esc(state.draft?.text||'')+'">':i<current?'✓':'—'}</span></div>`).join('')}</div><p class="wb-j-feedback" id="wb-j-feedback" role="status" aria-live="polite">${esc(state.last_feedback||'')}</p></section>`;
    const replay=document.getElementById('wb-instruction-replay');
    replay.onclick=()=>{if(!busy&&!activeStream)playPrescribedAudio(instructionText).catch(e=>setJFeedback(e.message||'Hindi available ang panuto.',true));};
    if(!preview)speakInstruction();
    if(preview||!item)return;
    const input=document.getElementById('wb-j-answer');
    input.oninput=()=>draft({text:input.value});
    button('Suriin',()=>perform({action:'answer',answer:{text:input.value}}),true);
    setJFeedback(state.last_feedback||'');
  }
  async function recordJ(){
    if(busy||!navigator.mediaDevices?.getUserMedia||!window.MediaRecorder){const text=l23G3?'Hindi pinayagan ang mikropono.':l24G3WordReading?'Hindi available ang mikropono.':'Hindi magamit ang mikropono. Subukan muli.';setJFeedback(text,true);if((l23G3&&G3_MAPPED_TEXT.has(text))||(l24G3WordReading&&L24_G3_WORD_MAPPED_TEXT.has(text)))playPrescribedAudio(text,true).catch(()=>{});return;}
    busy=true;lock();let stream=null,recorder=null,timer=null,requestId=Number(state.index||0),requestActivity=a.activity_key;
    try{
      if(!jReading)setJFeedback('Nakikinig...');
      if(l23G3||qReading){await send({action:'reading_started'},null,false);await playPrescribedAudio('Handa ka na?',true);}
      if(l24G3WordReading){await playPrescribedAudio('Handa ka na',true);}
      stream=activeStream=await window.Basahin.openMicrophone({audio:true});
      const audio=await window.Basahin.capture({button:document.getElementById('wb-basahin'),stream,onRecorder:value=>{recorder=activeRecorder=value;}});stream.getTracks().forEach(t=>t.stop());activeStream=null;activeRecorder=null;
      if(!audio.size)throw Error('Hindi nakuha ang iyong boses. Subukan muli.');
      if(requestActivity!==a.activity_key||requestId!==Number(state.index||0))return;
      setJFeedback('Sinusuri...');if(jReading||qReading)await playPrescribedAudio('Sinusuri...',true);const form=new FormData();form.append('audio',audio,'reading.webm');
      await send({action:'reading_attempt'},form,false);render();
      if(l23G3){if(state.completed){await playPrescribedAudio('Mahusay!',true);await playPrescribedAudio('Natapos mo ang gawain!',true);}else if(G3_MAPPED_TEXT.has(state.last_feedback))await playPrescribedAudio(state.last_feedback,true);}
      if(qReading){if(state.completed){await playPrescribedAudio('Mahusay!',true);await playPrescribedAudio('Natapos mo ang gawain!',true);}else if(G7_FEEDBACK_TEXT.has(state.last_feedback))await playPrescribedAudio(state.last_feedback,true);}
      if(l24G3WordReading){const feedback=state.completed?'Magaling! Natapos mo ang Gawain 3.':state.last_feedback;if(L24_G3_WORD_MAPPED_TEXT.has(feedback))await playPrescribedAudio(feedback,true);}
    }catch(e){
      clearTimeout(timer);stream?.getTracks().forEach(t=>t.stop());activeStream=null;activeRecorder=null;
      const denied=e?.name==='NotAllowedError'||e?.name==='SecurityError';const text=denied?(l24G3WordReading?'Hindi available ang mikropono.':'Hindi pinayagan ang mikropono.'):e.message||'Hindi nakuha ang iyong boses. Subukan muli.';setJFeedback(text,true);if(l23G3&&G3_MAPPED_TEXT.has(text))await playPrescribedAudio(text,true).catch(()=>{});if(qReading&&G7_FEEDBACK_TEXT.has(text))await playPrescribedAudio(text,true).catch(()=>{});if(l24G3WordReading&&L24_G3_WORD_MAPPED_TEXT.has(text))await playPrescribedAudio(text,true).catch(()=>{});
    }finally{busy=false;lock();lockG3();}
  }
  function draft(value){if(s9Family&&state.completed)return;state.draft={...state.draft,...value};if(specializedBuilder&&Object.prototype.hasOwnProperty.call(value,'builder')){state.last_feedback='';const feedback=content.querySelector('.wb-builder-feedback');if(feedback)feedback.textContent='';}const snapshot=structuredClone(state.draft),epoch=session9DraftEpoch;send({action:'draft',draft:snapshot},null,true,epoch).catch(e=>{const text=e.message||(session9Activity?session9SaveError:'Hindi na-save. Subukan muli.');message(text,true);if((l24Builder&&L24_G1_MAPPED_TEXT.has(text))||(l24G4Builder&&L24_G4_BUILDER_MAPPED_TEXT.has(text)))playPrescribedAudio(text,true).catch(()=>{});});}
  function syncL22G1Presentation(){
    if(!l22G1)return;
    document.body.classList.remove('wb-l22-g1-instruction','wb-l22-g1-reading','wb-l22-g1-building');
    document.body.classList.add(`wb-l22-g1-${l22G1Presentation}`);
  }
  function playL22G1Instruction(){
    if(!l22G1||l22G1Presentation!=='instruction'||instructionPlayback)return;
    const replay=document.getElementById('wb-instruction-replay');
    const token=++l22G1InstructionToken;
    instructionPlayback=true;
    if(replay){replay.disabled=true;replay.classList.add('is-busy');}
    playPrescribedAudio(instructionText,true).then(async()=>{
      if(token!==l22G1InstructionToken||!activityStarted||l22G1Presentation!=='instruction')return;
      const transitionToken=++l22G1TransitionToken;
      content.classList.add('wb-l22-g1-fade-out');
      if(!window.matchMedia?.('(prefers-reduced-motion: reduce)').matches)await new Promise(resolve=>setTimeout(resolve,300));
      if(transitionToken!==l22G1TransitionToken||token!==l22G1InstructionToken)return;
      l22G1Presentation='reading';
      syncL22G1Presentation();
      render();
      const readingPanel=content.querySelector('.wb-reading-panel');
      if(readingPanel&&!window.matchMedia?.('(prefers-reduced-motion: reduce)').matches){readingPanel.classList.add('wb-l22-g1-fade-in');requestAnimationFrame(()=>readingPanel.classList.remove('wb-l22-g1-fade-in'));}
    }).catch(error=>{
      if(error?.name!=='AbortError')message(error?.message||'Hindi available ang panuto.',true);
    }).finally(()=>{
      instructionPlayback=false;
      if(replay?.isConnected){replay.disabled=false;replay.classList.remove('is-busy');}
    });
  }
  function renderCBuilder(){
    const readDone=Boolean(state.read_aloud_completed), piecesById=Object.fromEntries(a.items.map(i=>[i.id,i.text]));
    let fallbackIndex=0;
    const boxCells=a.bigbox_cells||a.rows.map(row=>row.filter(Boolean).map(()=>[`item-${++fallbackIndex}`]));
    builder=state.draft.builder||[];
    if(l22G1){if(readDone)l22G1Presentation='building';syncL22G1Presentation();}
    content.className=`wb-l22-builder ${l22G1?'wb-l22-g1-active wb-l22-g1-'+l22G1Presentation+' ':''}${qBuilder?'wb-q-builder '+(readDone?'wb-g6-building':'wb-g6-reading'):''}`;
    const current=Math.min(Number(state.index||0),a.items.length-1), phase=state.reading_phase||'read';
    const buildingAttempts=Math.max(0,Math.min(3,Number(state.building_attempts||0))), buildingLocked=readDone&&buildingAttempts>=3;
     const inActivityInstruction=l22G1?'':`<div class="wb-l22-banner"><span class="wb-speaker-icon" aria-hidden="true">🔊</span><strong>${instructionText}</strong><button type="button" id="wb-l22-instruction-replay" aria-label="Pakinggan muli ang panuto">Pakinggan muli</button></div>`;
     content.innerHTML=`${inActivityInstruction}<section class="wb-bigbox"><h2>BIG BOX</h2><p class="wb-box-help">Sundan ang dilaw na highlight.</p><div class="wb-bigbox-grid">${boxCells.map(row=>`<div class="wb-bigbox-row">${row.map(()=>'<div class="wb-bigbox-cell"></div>').join('')}</div>`).join('')}</div></section><section class="wb-reading-panel"><h2>${readDone?'BUMUO NG SALITA':'BASAHIN'}</h2><p class="wb-phase-status" role="status">${readDone?'Magaling! Nabasa mo nang tama ang lahat ng pantig.':state.last_feedback==='Tama!'?'Tama!':'Handa ka na?'}</p><div id="wb-l22-reading-action"></div><p class="wb-reading-tip"><span aria-hidden="true">💡</span><span>${readDone?'Piliin ang mga pantig sa Big Box upang bumuo ng salita.':'Pindutin ang button kapag handa ka nang magbasa.'}</span></p></section><section class="wb-word-panel ${readDone?'':'is-locked'}" aria-disabled="${!readDone}"><h2>${readDone?'NABUONG SALITA':'BUMUO NG SALITA'}</h2>${readDone?`<p>Piliin ang mga pantig sa Big Box.</p><div class="wb-selected-parts" id="wb-selected-parts" aria-live="polite"></div><div class="wb-tools"><button type="button" id="wb-erase">Burahin ang napili</button><button type="button" id="wb-retry">Subukan muli</button></div><p class="wb-builder-feedback${l22G1ShouldHideResult(state.last_feedback)?' wb-audio-only-result':''}" aria-live="polite">${esc(state.last_feedback||'')}</p>${state.found_words?.length?`<div class="wb-builder-words"><strong>Nabuo mo na:</strong><ul>${state.found_words.map(w=>`<li>${esc(w)}</li>`).join('')}</ul></div>`:''}`:'<p class="wb-locked-note"><span class="wb-lock-icon">🔒</span><span>Basahin muna ang lahat ng pantig.</span></p>'}</section>`;
    if(l23G1)content.querySelector('.wb-l22-banner')?.remove();
    if(readDone){
      const wordPanel=content.querySelector('.wb-word-panel');
      wordPanel?.querySelector('h2')?.insertAdjacentHTML('afterend',`<p class="wb-building-instruction">Piliin ang mga pantig sa Big Box upang bumuo ng salita.</p><p class="wb-building-attempts">Pagsubok sa pagbuo: <strong>${buildingAttempts} / 3</strong><span class="wb-attempt-circles" aria-hidden="true">${[0,1,2].map(i=>`<i class="${i<buildingAttempts?'is-filled':''}"></i>`).join('')}</span></p>`);
      wordPanel?.querySelector('#wb-selected-parts')?.insertAdjacentHTML('afterend','<div class="wb-formed-word" id="wb-formed-word" aria-live="polite"></div>');
      const retry=wordPanel?.querySelector('#wb-retry');
      if(retry){retry.textContent='Subukan muli';retry.hidden=!buildingLocked;}
      const erase=wordPanel?.querySelector('#wb-erase');
      if(erase)erase.hidden=buildingLocked;
    }
    const replay=document.getElementById('wb-l22-instruction-replay');
    if(replay)replay.onclick=()=>{if(!busy&&!activeStream)l22G1?playL22G1Instruction():playPrescribedAudio(instructionText).catch(e=>message(e.message||'Hindi available ang panuto.',true));};
    if(!preview&&activityStarted&&!l22G1&&!instructionSpoken){instructionSpoken=true;setTimeout(()=>playPrescribedAudio(instructionText).catch(e=>console.error('Lesson 22 instruction audio failed',e)),0);}
    const readingPanel=content.querySelector('.wb-reading-panel');
     const phaseStatus=readingPanel.querySelector('.wb-phase-status');
     phaseStatus.textContent=readDone?'Magaling! Nabasa mo nang tama ang lahat ng pantig.':state.last_feedback||(l22G1?'Basahin ang pantig na nasa itaas.':'Basahin muna ang mga pantig sa Big Box.');
     phaseStatus.classList.toggle('wb-audio-only-result',l22G1ShouldHideResult(state.last_feedback));
    const readingAttempts=readDone?0:Math.max(0,Math.min(3,Number(state.reading_attempts||0)));
    phaseStatus.insertAdjacentHTML('beforebegin',`<p class="wb-reading-target-label">Pantig na babasahin</p><strong class="wb-reading-target">${esc(readDone?'Natapos na ang pagbasa.':a.items[current]?.text||'')}</strong><p class="wb-reading-attempts">Pagsubok: ${readingAttempts} / 3 <span class="wb-attempt-circles" aria-hidden="true">${[0,1,2].map(i=>`<i class="${i<readingAttempts?'is-filled':''}"></i>`).join('')}</span></p>`);
    readingPanel.querySelector('.wb-reading-tip')?.remove();
    const itemById=Object.fromEntries(a.items.map(i=>[i.id,i]));
    content.querySelectorAll('.wb-bigbox-row').forEach((row,rowIndex)=>{
      row.querySelectorAll('.wb-bigbox-cell').forEach((cell,cellIndex)=>{
        const itemIds=boxCells[rowIndex][cellIndex]||[];
        cell.replaceChildren(...itemIds.map(id=>{
          const item=itemById[id];if(!item)return null;
          const tile=document.createElement('button');tile.type='button';tile.className='wb-bigbox-tile';tile.dataset.tile=item.id;tile.textContent=item.text;tile.disabled=!readDone||preview||buildingLocked;tile.setAttribute('aria-label',`Pantig ${item.text}`);if(builder.includes(item.id))tile.classList.add('is-picked');if(!readDone){const itemIndex=a.items.findIndex(candidate=>candidate.id===item.id);if(itemIndex<current)tile.classList.add('is-complete');if(itemIndex===current){tile.classList.add('is-active');if(current===0)tile.insertAdjacentHTML('afterbegin','<span class="wb-start-cue">Simulan dito</span>');}}tile.onclick=()=>{if(busy||buildingLocked)return;builder.push(item.id);paint();tile.classList.add('is-picked');draft({builder});};return tile;
        }).filter(Boolean));
      });
    });
    const paint=()=>{const selected=document.getElementById('wb-selected-parts');if(!selected)return;selected.replaceChildren(...builder.map(id=>{const span=document.createElement('span');span.className='wb-selected-part';span.textContent=piecesById[id]||'';return span;}));const formed=document.getElementById('wb-formed-word');if(formed)formed.textContent=builder.map(id=>piecesById[id]||'').join('')||'Pipiliin mong salita ay lalabas dito.';};
    paint();
    if(readDone){
      document.getElementById('wb-erase').onclick=()=>{if(buildingLocked)return;builder=[];draft({builder});paint();content.querySelectorAll('[data-tile]').forEach(t=>t.classList.remove('is-picked'));};
      document.getElementById('wb-retry').onclick=()=>{if(buildingLocked){perform({action:'retry_building'});return;}builder=[];draft({builder});paint();content.querySelectorAll('[data-tile]').forEach(t=>t.classList.remove('is-picked'));};
      button('Suriin ang salita',()=>perform({action:'build_word',parts:builder}),true).disabled=!builder.length||buildingLocked;
      button('Tapusin ang Gawain',()=>perform({action:'finish'}),false).disabled=!(state.found_words||[]).length;
      button('Susunod',()=>{if(data.next_url)location.href=data.next_url;}).disabled=true;
    }else if(!preview){
      const readingButton=(text,fn,primary=true)=>{const b=button(text,fn,primary);if(!primary)b.classList.add('wb-secondary');const target=document.getElementById('wb-l22-reading-action');if(target)target.appendChild(b);return b;};
      if(phase==='help'){
        readingButton('Pakinggan ang Tamang Pagbigkas',readAloudC,true);
        if(state.pronunciation_help_played)readingButton('Subukan Muli',retryCReading,false);
      }else readingButton(state.read_aloud_started?'🎙 Basahin ang Pantig':'🎙 Basahin ang mga Pantig',startCReading);
    }
     if(!preview&&!l22G1){
      const restart=button('Ulitin Mula sa Simula',()=>{
        if(window.confirm(`Sigurado ka bang gusto mong magsimula muli? Mawawala ang kasalukuyang progreso sa ${qBuilder?'Gawain 6':'Gawain 1'}.`)) perform({action:'restart'});
      },false);
      restart.classList.add('wb-secondary');
     }else if(!preview&&l22G1){
       const restart=button('Ulitin Mula sa Simula',()=>{
         if(window.confirm('Sigurado ka bang gusto mong magsimula muli? Mawawala ang kasalukuyang progreso sa Gawain 1.')) perform({action:'restart'});
       },false);
       restart.classList.add('wb-secondary');
       restart.id='wb-l22-reset';
       readingPanel.appendChild(restart);
    }
  }
  async function startCReading(){
    if(busy)return;stopReadAloud();busy=true;lock();if(qBuilder){const transcript=content.querySelector('.wb-transcript strong');if(transcript)transcript.textContent='—';}setG1ReadingState('calibrating');let chunks=[],readTimer,recorder;const requestIndex=Number(state.index||0),requestActivity=a.activity_key;
    try{
      await send({action:'reading_started'},null,false);
      if(!navigator.mediaDevices?.getUserMedia||!window.MediaRecorder)throw new Error('Hindi available ang mikropono sa browser na ito.');
      activeStream=await window.Basahin.openMicrophone({audio:true},{timeoutMs:8000});
      setG1ReadingState('listening');
      message('Nakikinig...');
      const audio=await window.Basahin.capture({button:document.getElementById('wb-basahin'),stream:activeStream,onRecorder:value=>{recorder=activeRecorder=value;}});activeStream.getTracks().forEach(t=>t.stop());activeStream=null;activeRecorder=null;
      if(!audio.size)throw new Error('Walang nakuha sa recording. Subukan muli.');
      if(requestActivity!==a.activity_key||requestIndex!==Number(state.index||0))return;
      const form=new FormData();form.append('audio',audio,'reading.webm');message('Sinusuri ang iyong pagbasa...');
      setG1ReadingState('processing');
      await send({action:'reading_syllable_attempt',item_index:requestIndex},form,false);render();
      pendingSpeech=state.read_aloud_completed?'Magaling! Nabasa mo nang tama ang lahat ng pantig.':state.last_feedback==='Tama!'?'Tama!':'Subukan muli.';
      message(pendingSpeech);
    }catch(error){
      clearTimeout(readTimer);
      activeStream?.getTracks().forEach(t=>t.stop());activeStream=null;activeRecorder=null;
      const micError=error?.name==='NotAllowedError'||error?.name==='NotFoundError'||error?.name==='NotReadableError'||error?.name==='SecurityError';
      render();
      if(qBuilder){const transcript=content.querySelector('.wb-transcript strong');if(transcript)transcript.textContent='—';}
      const serviceError=(qBuilder||l22G1)&&(error?.code==='speech_service_unavailable'||/Google service account|GOOGLE_|credential|speech service|not configured|network error|winerror|socket|timed out|connect/i.test(String(error?.message||'')));
      pendingSpeech=micError?'Hindi magamit ang mikropono. Subukan muli.':serviceError?'Hindi magamit ang mikropono ngayon. Subukan muli mamaya.':(error?.message||'Hindi nakuha ang iyong boses. Subukan muli.');
      message(pendingSpeech,true);
    }finally{clearTimeout(readTimer);const speech=pendingSpeech;pendingSpeech='';if(speech){setG1ReadingState('processing');await playPrescribedAudio(speech).catch(e=>console.error('Lesson 22 feedback audio failed',e));}busy=false;lock();setG1ReadingState('idle');}
  }
  async function retryCReading(){
    if(busy)return;stopReadAloud();busy=true;lock();
    try{await send({action:'retry_reading'},null,false);render();message('Handa ka na?');pendingSpeech='Handa ka na?';}
    catch(e){const text=e.message||'Hindi maihanda ang pagbasa. Subukan muli.';render();message(text,true);if((l23G1&&G1_MAPPED_TEXT.has(text))||(l24Builder&&L24_G1_MAPPED_TEXT.has(text)))pendingSpeech=text;}
    finally{busy=false;lock();const speech=pendingSpeech;pendingSpeech='';if(speech)playPrescribedAudio(speech).catch(e=>console.error('Lesson 22 retry audio failed',e));}
  }
  async function readAloudC(){
    if(busy)return;stopReadAloud();busy=true;lock();const current=Math.min(Number(state.index||0),a.items.length-1);
    try{await playPrescribedAudio(a.items[current].text,true);await send({action:'read_aloud'},null,false);render();}catch(e){const text=e.message||'Hindi available ang audio.';render();message(text,true);if((l23G1&&G1_MAPPED_TEXT.has(text))||(l24Builder&&L24_G1_MAPPED_TEXT.has(text)))await playPrescribedAudio(text,true).catch(()=>{});}finally{stopReadAloud();busy=false;lock();}
  }
  function renderSearch(){
    content.innerHTML+=`<div class="wb-search-wrap"><ul class="wb-word-list">${a.items.map((i,n)=>`<li>${esc(a.item_labels?.[n]||`${n+1}.`)} ${esc(i.text)}${!preview&&state.answers[i.id]?' ✓':''}</li>`).join('')}</ul><label>${fil?'Kulay':'Color'} <input id="wb-color" type="color" value="${esc(state.draft.color||'#b6e6c3')}"></label><div class="wb-search ${a.mark_style}" style="--cols:${a.grid[0].length}">${a.grid.map((row,y)=>Array.from(row).map((letter,x)=>`<button type="button" data-y="${y}" data-x="${x}" aria-label="Row ${y+1}, column ${x+1}: ${esc(letter)}">${esc(letter)}</button>`).join('')).join('')}</div></div>`;
    const found=Object.values(state.answers).flat();
    content.querySelectorAll('.wb-search button').forEach(b=>{
      const y=Number(b.dataset.y),x=Number(b.dataset.x);
      if(!preview&&found.some(p=>p[0]===y&&p[1]===x)){b.classList.add('wb-found');const match=Object.entries(state.answers).find(([,path])=>path.some(p=>p[0]===y&&p[1]===x));b.style.setProperty('--mark',state.mark_colors?.[match?.[0]]||'#b6e6c3');}
      b.disabled=preview||!oral().passed;
      b.onclick=()=>{if(busy)return;if(!selected.length){selected=[[y,x]];}else{const [sy,sx]=selected[0],dy=y-sy,dx=x-sx;if(dx&&dy&&Math.abs(dx)!==Math.abs(dy)){selected=[[y,x]];}else{selected=Array.from({length:Math.max(Math.abs(dx),Math.abs(dy))+1},(_,i)=>[sy+i*Math.sign(dy),sx+i*Math.sign(dx)]);}}content.querySelectorAll('.wb-search button').forEach(cell=>cell.classList.toggle('wb-selected',selected.some(p=>p[0]===+cell.dataset.y&&p[1]===+cell.dataset.x)));draft({selected});};
    });
    if(!preview){selected=state.draft.selected||[];content.querySelectorAll('.wb-search button').forEach(b=>b.classList.toggle('wb-selected',selected.some(p=>p[0]===+b.dataset.y&&p[1]===+b.dataset.x)));}
    document.getElementById('wb-color').oninput=e=>{content.style.setProperty('--mark',e.target.value);draft({color:e.target.value});};
  }
  function renderBuilder(){
    const box=document.createElement('div');box.className=`wb-builder${l24G4Builder?' wb-l24-g4-builder':''}`;
    if(l24G4Builder){
      box.innerHTML=`<div class="wb-builder-workspace"><section class="wb-builder-box" aria-labelledby="wb-big-box-title"><h2 id="wb-big-box-title">BIG BOX</h2><p class="wb-builder-help">Pumili ng mga pantig upang bumuo ng salita.</p><div class="wb-big-box-grid" role="grid" aria-label="Big Box na may 12 pantig">${a.items.map((i,n)=>`<button type="button" class="wb-big-box-cell" data-part="${i.id}" data-cell-index="${n}" role="gridcell">${esc(i.text)}</button>`).join('')}</div></section><section class="wb-builder-panel" aria-labelledby="wb-build-title"><h2 id="wb-build-title">BUMUO NG SALITA</h2><p class="wb-builder-help">Napiling mga pantig</p><div id="wb-building" class="wb-building" aria-live="polite"></div><p class="wb-builder-help">Nabuong salita</p><div id="wb-words" class="wb-builder-words" aria-live="polite"></div><div class="wb-tools"><button type="button" id="wb-add">Idagdag ang salita</button><button type="button" id="wb-clear">Burahin</button></div></section></div>`;
    }else{
      box.innerHTML=`<p>${fil?'Pumili ng mga pantig upang bumuo ng salita.':'Choose syllables to build a word.'}</p><div class="wb-syllable-tiles">${a.items.map(i=>`<button type="button" data-part="${i.id}">${esc(i.text)}</button>`).join('')}</div><div id="wb-building" class="wb-building">${fil?'Pipiliin mong salita ay lalabas dito.':'Your word will appear here.'}</div><div class="wb-tools"><button type="button" id="wb-add">${fil?'Idagdag':'Add word'}</button><button type="button" id="wb-clear">${fil?'Burahin':'Clear'}</button></div><div id="wb-words" class="wb-builder-words"></div>`;
    }
    content.appendChild(box);
    const wordText=parts=>parts.map(id=>a.items.find(i=>i.id===id)?.text||'').join('');
    const paint=()=>{const building=box.querySelector('#wb-building');const built=box.querySelector('#wb-words');if(l24G4Builder){const displayedWords=[...(state.built_words||[]),...words];building.innerHTML=builder.length?builder.map((id,index)=>`<button type="button" class="wb-selected-part" data-remove-index="${index}" aria-label="Alisin ang ${esc(wordText([id]))}">${esc(wordText([id]))}<span aria-hidden="true">×</span></button>`).join(''):'<span class="wb-empty-state">Pumili muna ng mga pantig.</span>';built.innerHTML=displayedWords.length?displayedWords.map(word=>`<span class="wb-built-word">${esc(wordText(word))}</span>`).join(''):'<span class="wb-empty-state">Wala pang nabuong salita.</span>';box.querySelectorAll('[data-part]').forEach(b=>b.classList.toggle('is-picked',builder.includes(b.dataset.part)));box.querySelectorAll('[data-remove-index]').forEach(b=>b.onclick=()=>{builder.splice(Number(b.dataset.removeIndex),1);paint();draft({builder,words});});}else{building.textContent=builder.length?wordText(builder):(fil?'Pipiliin mong salita ay lalabas dito.':'Your word will appear here.');built.textContent=words.map(wordText).join(', ');}};
     box.querySelectorAll('[data-part]').forEach(b=>{b.disabled=preview||(!l24G4Builder&&!oral().passed);b.onclick=()=>{builder.push(b.dataset.part);paint();draft({builder,words});if(l24G4Builder){const text=a.items.find(item=>item.id===b.dataset.part)?.text;if(text)playPrescribedAudio(text).catch(e=>message(e.message||'Hindi available ang audio.',true));}};});
     box.querySelector('#wb-add').disabled=preview||(!l24G4Builder&&!oral().passed);box.querySelector('#wb-clear').disabled=preview||(!l24G4Builder&&!oral().passed);
    box.querySelector('#wb-add').onclick=()=>{if(builder.length){words.push([...builder]);builder=[];paint();draft({builder,words});}};
    box.querySelector('#wb-clear').onclick=()=>{builder=[];box.querySelectorAll('[data-part]').forEach(b=>b.classList.remove('is-picked'));paint();draft({builder,words});};paint();
    if(!preview){
      if(l24G4Builder){
        button('Isumite ang mga salita',()=>perform({action:'build_words',words}),true).disabled=!words.length;
        button('Tapusin ang Gawain',()=>perform({action:'finish'}),false).disabled=!(state.built_words||[]).length;
        if(!instructionSpoken)speakInstruction();
      }else button(fil?'Isumite ang mga salita':'Submit words',()=>perform({action:'answer',answer:words}),true);
      if(l24G4Builder&&Number(state.index||0)>0)button('Ulitin Mula sa Simula',()=>{if(window.confirm('Ulitin ang Gawain 4 mula sa simula?'))perform({action:'restart'});});
    }else box.querySelectorAll('button').forEach(b=>b.disabled=true);
  }
  document.getElementById('wb-instruction-replay')?.addEventListener('click',()=>{if(!busy&&!activeStream)playPrescribedAudio(instructionText).catch(e=>message(e.message||'Hindi available ang panuto.',true));});
  function written(prompt){content.innerHTML+=`<div class="wb-focus"><p>${esc(prompt)}</p><label for="wb-written">${fil?'Sagot':'Answer'}</label><textarea id="wb-written" ${preview||a.oral_flow&&!oral().passed?'disabled':''}>${esc(preview?'':state.draft.text||'')}</textarea></div>`;document.getElementById('wb-written').oninput=e=>draft({text:e.target.value});}
  function renderSyllables(){
    if(jSyllables){
      const current=Number(state.index||0), answers=state.answers||{};
      const rows=a.items.map((it,n)=>{
        const done=Object.prototype.hasOwnProperty.call(answers,String(n)), active=n===current&&!state.completed;
        const value=done?answers[String(n)]:active?(state.draft?.text||''):'—';
        return `<div class="wb-syllable-row ${done?'is-done':''} ${active?'is-current':''}" ${active?'aria-current="step"':''}><span class="wb-syllable-number">${esc(a.item_labels?.[n]||`${n+1}.`)}</span><strong class="wb-syllable-word">${esc(it.text)}</strong><span class="wb-syllable-equals">=</span>${active?`<input id="wb-written" type="text" inputmode="text" autocomplete="off" aria-label="Sagot para sa ${esc(it.text)}" value="${esc(value)}" placeholder="Halimbawa: jack-et">`:`<span class="wb-syllable-answer">${esc(value)}</span>`}</div>`;
      }).join('');
      content.innerHTML=`<div class="wb-g4-panels"><section class="wb-j-syllables wb-g4-table-panel" aria-labelledby="wb-j-syllables-title"><div class="wb-j-syllables-heading"><span class="wb-j-syllables-kicker">PANTIGIN ANG MGA SALITA</span><h2 id="wb-j-syllables-title">Pantigin ang sumusunod na salita.</h2></div><div class="wb-syllable-rows">${rows}</div></section><section class="wb-g4-support-panel" aria-labelledby="wb-g4-support-title"><span class="wb-g4-panel-kicker">GAWAIN 4</span><p class="wb-g4-action-guidance">Isulat ang wastong paghahati ng salita sa mga pantig.</p><p class="wb-j-feedback ${state.last_feedback==='Subukan Muli.'?'is-error':''}" role="status" aria-live="polite">${esc(state.last_feedback||'')}</p><div class="wb-g4-action-slot"></div></section></div>`;
      const input=document.getElementById('wb-written');
      if(input&&!preview)input.oninput=()=>draft({text:input.value});
      document.querySelector('.wb-g4-action-slot')?.append(action);
      if(!preview&&!state.completed&&input)button('Suriin',()=>perform({action:'answer',answer:{text:input.value}}),true);
      return;
    }
    if(a.worked_example)content.innerHTML+=`<p>${esc(a.worked_example)}</p>`;
    if(preview){content.innerHTML+=a.items.map((it,n)=>`<p>${esc(a.item_labels?.[n]||`${n+1}.`)} ${esc(it.text)} = ________________</p>`).join('');}
    else {const it=item();const n=state.index;content.innerHTML+=`<div class="wb-focus wb-syllable-focus"><p>${esc(a.item_labels?.[n]||`${n+1}.`)} ${esc(it.text)} = ________________</p></div>`;}
    if(!preview)written(item().text+' = __________');
  }
  function renderL24G5Syllables(){
    const current=Number(state.index||0), answers=state.answers||{};
    const currentItem=a.items[current];
    const list=a.items.map((it,n)=>{
      const done=Boolean(answers[it.id]), active=n===current;
      return `<li class="wb-g5-word ${done?'is-done':''} ${active?'is-current':''}" ${active?'aria-current="step"':''}><span class="wb-g5-number">${esc(a.item_labels?.[n]||`${n+2}.`)}</span><span class="wb-g5-word-text">${esc(it.text)}</span>${done?'<span class="wb-g5-check" aria-label="Nasagutan">✓</span>':''}</li>`;
    }).join('');
    const feedback=state.last_feedback||'';
    content.innerHTML=`<section class="wb-g5-workspace"><article class="wb-g5-list-panel"><div class="wb-g5-panel-heading"><span class="wb-g5-kicker">MGA SALITA</span><span class="wb-g5-count">${current}/${a.items.length}</span></div><div class="wb-g5-example"><span>HALIMBAWA</span><strong>1. zigzag = zig•zag</strong></div><ol class="wb-g5-word-list">${list}</ol></article><article class="wb-g5-task-panel"><div class="wb-g5-panel-heading"><span class="wb-g5-kicker">PANTIGIN</span><span class="wb-g5-task-label">Salitang Papantigin</span></div><div class="wb-g5-current-word">${currentItem?esc(currentItem.text):'—'}</div><p class="wb-g5-help">Hatiin ang salita sa mga pantig gamit ang <strong>-</strong> o <strong>•</strong>.</p><label class="wb-g5-answer-label" for="wb-written">Isulat ang sagot</label><input id="wb-written" type="text" inputmode="text" autocomplete="off" placeholder="Halimbawa: Zan-dra" value="${esc(state.draft?.text||'')}" ${preview?'disabled':''}><p class="wb-g5-feedback ${feedback==='Subukan muli.'?'is-error':''}" role="status" aria-live="polite">${esc(feedback)}</p><button type="button" class="wb-g5-reset" id="wb-g5-reset">Ulitin Mula sa Simula</button></article></section>`;
    const input=document.getElementById('wb-written');
    if(input&&!preview)input.oninput=()=>draft({text:input.value});
    document.getElementById('wb-g5-reset')?.addEventListener('click',()=>{if(window.confirm('Ulitin ang Gawain 5 mula sa simula? Mawawala ang kasalukuyang progreso.'))perform({action:'restart'});});
    if(preview){action.innerHTML='';return;}
    if(currentItem)button('Suriin ang Sagot',()=>perform({action:'answer',item_index:current,answer:{text:document.getElementById('wb-written').value}}),true);
    lock();
  }
  function renderL24G6WordSearch(){
    const found=state.found_words||{}, grid=a.grid||[], targetItems=a.items||[];
    const canonicalPaths={zipper:[[2,2],[2,3],[2,4],[2,5],[2,6],[2,7]],zoo:[[3,1],[3,2],[3,3]],zebra:[[1,6],[2,6],[3,6],[4,6],[5,6]],zigzag:[[0,8],[1,8],[2,8],[3,8],[4,8],[5,8]],Perez:[[3,4],[4,4],[5,4],[6,4],[7,4]],Rizal:[[7,2],[7,3],[7,4],[7,5],[7,6]],Zamora:[[0,0],[0,1],[0,2],[0,3],[0,4],[0,5]],Zam:[[0,0],[1,0],[2,0]],Zoren:[[2,2],[3,2],[4,2],[5,2],[6,2]],Zeny:[[3,1],[4,1],[5,1],[6,1]]};
    const samePath=(left,right)=>left.length===right.length&&left.every((point,index)=>point[0]===right[index][0]&&point[1]===right[index][1]);
    const cellKey=([row,col])=>`${row}:${col}`;
    const foundCells=new Map();
    Object.values(found).forEach(entry=>(entry.path||[]).forEach(path=>foundCells.set(cellKey(path),entry.color||'#b6e6c3')));
    const wordsMarkup=targetItems.map((item,index)=>{
      const done=Boolean(found[item.text]);
      return `<li class="wb-g6-word ${done?'is-done':''}"><span class="wb-g6-number">${esc(a.item_labels?.[index]||`${index+1}.`)}</span><span>${esc(item.text)}</span>${done?'<span class="wb-g6-check" aria-label="Nahanap">✓</span>':''}</li>`;
    }).join('');
    const cells=grid.map((row,rowIndex)=>Array.from(row).map((letter,colIndex)=>{
      const color=foundCells.get(`${rowIndex}:${colIndex}`);
      const isSelected=selected.some(point=>point[0]===rowIndex&&point[1]===colIndex);
      return `<button type="button" class="wb-g6-cell ${color?'is-found':''} ${isSelected?'is-selected':''}" data-row="${rowIndex}" data-col="${colIndex}" role="gridcell" aria-label="Hanay ${rowIndex+1}, kolum ${colIndex+1}: ${esc(letter)}" ${preview?'disabled':''} ${color?`style="--wb-g6-mark:${esc(color)}"`:''}>${esc(letter)}</button>`;
    }).join('')).join('');
    content.innerHTML=`<section class="wb-g6-workspace"><aside class="wb-g6-list-panel"><div class="wb-g6-panel-heading"><h2>MGA HAHANAPIN</h2><span>${Object.keys(found).length} / ${targetItems.length}</span></div><p class="wb-g6-help">Hanapin at bilugan ang bawat salita sa Big Box.</p><ol class="wb-g6-word-list">${wordsMarkup}</ol><p id="wb-g6-feedback" class="wb-g6-feedback ${state.last_feedback==='Subukan muli.'?'is-error':''}" role="status" aria-live="polite">${esc(state.last_feedback||'Pumili ng unang letra, pagkatapos ng huling letra.')}</p><button type="button" class="wb-g6-reset" id="wb-g6-reset">Ulitin Mula sa Simula</button></aside><section class="wb-g6-box-panel"><div class="wb-g6-panel-heading"><h2>BIG BOX</h2><span>8 × 9</span></div><p class="wb-g6-help">Pindutin ang unang letra at ang huling letra ng salita.</p><div class="wb-g6-grid" style="--cols:${grid[0]?.length||9}" role="grid" aria-label="Big Box na may 8 hanay at 9 kolum">${cells}</div><p class="wb-g6-feedback wb-g6-grid-feedback" aria-hidden="true">&nbsp;</p></section></section>`;
    const linePath=(start,end)=>{
      const rowDelta=end[0]-start[0], colDelta=end[1]-start[1], steps=Math.max(Math.abs(rowDelta),Math.abs(colDelta));
      if(!steps || (rowDelta!==0&&colDelta!==0&&Math.abs(rowDelta)!==Math.abs(colDelta)))return [];
      const rowStep=rowDelta===0?0:rowDelta/steps, colStep=colDelta===0?0:colDelta/steps;
      return Array.from({length:steps+1},(_,index)=>[start[0]+rowStep*index,start[1]+colStep*index]);
    };
    const wordForPath=path=>targetItems.find(item=>samePath(canonicalPaths[item.text]||[],path))?.text||'';
    const paintSelection=()=>content.querySelectorAll('.wb-g6-cell').forEach(cell=>cell.classList.toggle('is-selected',selected.some(point=>point[0]===Number(cell.dataset.row)&&point[1]===Number(cell.dataset.col))));
    const gridElement=content.querySelector('.wb-g6-grid');
    let pointerId=null, startPoint=null;
    const pointFromEvent=event=>{const cell=document.elementFromPoint(event.clientX,event.clientY)?.closest('.wb-g6-cell');return cell?[Number(cell.dataset.row),Number(cell.dataset.col)]:null;};
    const clearSelection=()=>{selected=[];startPoint=null;pointerId=null;paintSelection();};
    const cancelSelection=()=>{if(pointerId!==null)clearSelection();};
    gridElement?.addEventListener('pointerdown',event=>{
      if(busy||preview||event.button!==undefined&&event.button!==0)return;
      const point=pointFromEvent(event);if(!point)return;
      pointerId=event.pointerId;startPoint=point;selected=[point];gridElement.setPointerCapture?.(pointerId);paintSelection();event.preventDefault();
    });
    gridElement?.addEventListener('pointermove',event=>{
      if(pointerId===null||event.pointerId!==pointerId)return;
      const point=pointFromEvent(event);if(!point)return;
      selected=linePath(startPoint,point);paintSelection();event.preventDefault();
    });
    gridElement?.addEventListener('pointerup',event=>{
      if(pointerId===null||event.pointerId!==pointerId)return;
      const gesture=selected.slice(), word=wordForPath(gesture);clearSelection();
      if(!word||gesture.length<2){const feedbackNode=document.getElementById('wb-g6-feedback');if(feedbackNode){feedbackNode.textContent='Subukan muli.';feedbackNode.classList.add('is-error');}return;}
      perform({action:'select_word',word,path:gesture,color:'#b6e6c3'});
      event.preventDefault();
    });
    gridElement?.addEventListener('pointercancel',cancelSelection);
    gridElement?.addEventListener('lostpointercapture',cancelSelection);
    document.getElementById('wb-g6-reset')?.addEventListener('click',requestG6Restart);
    const replay=document.getElementById('wb-instruction-replay');
    if(replay)replay.onclick=()=>{if(!busy&&!activeStream)playPrescribedAudio(a.instruction).catch(error=>message(error.message||'Hindi available ang panuto.',true));};
    if(preview)content.querySelectorAll('button').forEach(button=>button.disabled=true);
  }
  function renderFill(){
    content.innerHTML+=`<p>( ${a.options.map(esc).join(', ')} )</p><table class="wb-table"><tr>${a.options.map(x=>`<td>${esc(x)}</td>`).join('')}</tr></table>`;
    if(preview){content.innerHTML+=a.items.map(it=>`<p>${esc(it.text)}</p>`).join('');return;}
    let index=0;
    const sentence=esc(item().text).replace(/_+/g,()=>{const i=index++;return `<select data-blank="${i}" aria-label="Blank ${i+1}"><option value="">_____</option>${a.options.map(o=>`<option value="${esc(o)}" ${state.draft.blanks?.[i]===o?'selected':''}>${esc(o)}</option>`).join('')}</select>`;});
    content.innerHTML+=`<div class="wb-focus">${sentence}</div>`;
    content.querySelectorAll('[data-blank]').forEach(select=>select.onchange=()=>draft({blanks:[...content.querySelectorAll('[data-blank]')].map(s=>s.value)}));
  }
  function renderDrawing(){
    if(s9Helping){
      content.innerHTML+=`<section class="wb-s9-a2-workspace"><div class="wb-s9-a2-drawing-panel"><div class="wb-s9-a2-section-heading"><h2>GUMUHIT AT MAGKULAY</h2><span>Gumuhit ng sitwasyon sa bahay kung saan tumulong ka.</span></div><div class="wb-s9-a2-toolbar" role="toolbar" aria-label="Mga kagamitan sa pagguhit"><div class="wb-s9-a2-tool-group"><button type="button" class="wb-s9-a2-tool is-active" data-tool="draw">✏ Gumuhit</button><button type="button" class="wb-s9-a2-tool" data-tool="eraser">🧽 Pambura</button><button type="button" id="wb-s9-a2-undo" aria-label="Undo">↶ Undo</button><button type="button" id="wb-s9-a2-redo" aria-label="Redo">↷ Redo</button><button type="button" id="wb-s9-a2-clear">🗑 Burahin</button></div><div class="wb-s9-a2-palette" aria-label="Mga kulay">${[['#183e63','Itim'],['#df4b4b','Pula'],['#ed9e2f','Kahel'],['#f4ca43','Dilaw'],['#49a66b','Berde'],['#438fd0','Asul'],['#8d62bd','Lila'],['#9b6b45','Kayumanggi']].map(([color,label])=>`<button type="button" class="wb-s9-a2-color ${color===((state.draft||{}).color||'#183e63')?'is-active':''}" data-color="${color}" aria-label="${label}" style="--swatch:${color}"></button>`).join('')}</div><div class="wb-s9-a2-sizes" aria-label="Laki ng brush"><span>Brush:</span>${[['small','S'],['medium','M'],['large','L']].map(([size,label])=>`<button type="button" class="wb-s9-a2-size ${(state.draft||{}).size===size?'is-active':''}" data-size="${size}">${label}</button>`).join('')}</div></div><canvas id="wb-canvas" width="1200" height="525" aria-label="Malaking drawing area para sa sitwasyon sa bahay"></canvas></div><div class="wb-s9-a2-response"><label for="wb-written">Magalang na salitang ginamit ko:</label><input id="wb-written" type="text" maxlength="160" autocomplete="off" aria-label="Magalang na salitang ginamit ko" value="${esc(state.draft?.text||'')}" ${preview?'disabled':''}><p>Halimbawa: <button type="button" class="wb-s9-a2-example" data-example="Please">Please</button> · <button type="button" class="wb-s9-a2-example" data-example="Sorry">Sorry</button> · <button type="button" class="wb-s9-a2-example" data-example="Thank you">Thank you</button> · <button type="button" class="wb-s9-a2-example" data-example="You're welcome.">You're welcome.</button></p></div></section>`;
    }else if(s9Family){
      content.innerHTML+=`<section class="wb-s9-family-workspace"><div class="wb-s9-drawing-panel"><div class="wb-s9-section-heading"><h2>DRAW YOUR FAMILY</h2></div><div class="wb-s9-a1-toolbar" role="toolbar" aria-label="Drawing tools"><div class="wb-s9-a1-tool-group"><button type="button" class="wb-s9-a1-tool is-active" data-tool="draw">✏ Draw</button><button type="button" class="wb-s9-a1-tool" data-tool="eraser">🧽 Eraser</button><button type="button" id="wb-s9-a1-undo" aria-label="Undo">↶ Undo</button><button type="button" id="wb-s9-a1-redo" aria-label="Redo">↷ Redo</button><button type="button" id="wb-s9-a1-clear">🗑 Clear drawing</button></div><div class="wb-s9-a1-palette" aria-label="Colors">${[['#183e63','Black'],['#df4b4b','Red'],['#ed9e2f','Orange'],['#f4ca43','Yellow'],['#49a66b','Green'],['#438fd0','Blue'],['#8d62bd','Purple'],['#9b6b45','Brown']].map(([color,label])=>`<button type="button" class="wb-s9-a1-color ${color===((state.draft||{}).color||'#183e63')?'is-active':''}" data-color="${color}" aria-label="${label}" style="--swatch:${color}"></button>`).join('')}</div><div class="wb-s9-a1-sizes" aria-label="Brush size"><span>Brush:</span>${[['small','S'],['medium','M'],['large','L']].map(([size,label])=>`<button type="button" class="wb-s9-a1-size ${(state.draft||{}).size===size?'is-active':''}" data-size="${size}">${label}</button>`).join('')}</div></div><canvas id="wb-canvas" width="900" height="500" aria-label="Draw your picture of your family"></canvas></div><div class="wb-s9-writing-panel"><div class="wb-s9-section-heading"><h2>WRITE THE SENTENCE</h2></div><p class="wb-s9-sentence">This is my family.</p><label for="wb-written">Your sentence</label><textarea id="wb-written" maxlength="160" aria-label="Write This is my family" ${preview?'disabled':''}>${esc(preview?'':state.draft?.text||'')}</textarea></div></section>`;
    }else{
      content.innerHTML+='<div class="wb-drawing-card"><div class="wb-tools"><label>Color <input type="color" id="wb-pen" value="#24576b"></label><button type="button" id="wb-undo">Undo stroke</button></div><canvas id="wb-canvas" width="900" height="500" aria-label="Draw your picture"></canvas></div>';
      written('Write under your drawing.');
    }
    if(s9Helping){
      const canvas=document.getElementById('wb-canvas'),ctx=canvas.getContext('2d'),width=1200,height=525;
      let strokes=structuredClone(state.draft?.strokes||[]),redoStack=[],stroke=null,erasing=false;
      let tool=state.draft?.tool==='eraser'?'eraser':'draw',color=state.draft?.color||'#183e63',size=state.draft?.size||'medium';
      const brush={small:4,medium:8,large:14}, eraser={small:22,medium:34,large:50};
      const redraw=()=>{ctx.clearRect(0,0,width,height);for(const current of strokes){ctx.strokeStyle=current.color;ctx.lineWidth=current.width||8;ctx.lineCap='round';ctx.lineJoin='round';ctx.beginPath();current.points.forEach((point,index)=>index?ctx.lineTo(...point):ctx.moveTo(...point));ctx.stroke();}};
      const point=e=>{const rect=canvas.getBoundingClientRect();return [Math.max(0,Math.min(width,(e.clientX-rect.left)*width/rect.width)),Math.max(0,Math.min(height,(e.clientY-rect.top)*height/rect.height))];};
      const save=()=>draft({strokes,text:document.getElementById('wb-written').value,tool,color,size});
      const setActive=()=>{content.querySelectorAll('[data-tool]').forEach(button=>button.classList.toggle('is-active',button.dataset.tool===tool));content.querySelectorAll('[data-color]').forEach(button=>button.classList.toggle('is-active',button.dataset.color===color));content.querySelectorAll('[data-size]').forEach(button=>button.classList.toggle('is-active',button.dataset.size===size));document.getElementById('wb-s9-a2-undo').disabled=!strokes.length;document.getElementById('wb-s9-a2-redo').disabled=!redoStack.length;};
      const eraseAt=target=>{const radius=eraser[size];const kept=strokes.filter(current=>!current.points.some(([x,y])=>Math.hypot(x-target[0],y-target[1])<=radius));if(kept.length!==strokes.length){redoStack=[];strokes=kept;redraw();setActive();save();}};
      canvas.onpointerdown=e=>{if(preview||busy)return;canvas.setPointerCapture(e.pointerId);const target=point(e);if(tool==='eraser'){erasing=true;eraseAt(target);return;}stroke={color,width:brush[size],points:[target]};strokes.push(stroke);redoStack=[];};
      canvas.onpointermove=e=>{if(erasing){eraseAt(point(e));return;}if(!stroke)return;stroke.points.push(point(e));if(stroke.points.length<3000)redraw();};
      const end=()=>{erasing=false;if(stroke){if(stroke.points.length===1)stroke.points.push([...stroke.points[0]]);stroke=null;redraw();setActive();save();}};canvas.onpointerup=end;canvas.onpointercancel=end;
      document.getElementById('wb-s9-a2-undo').onclick=()=>{if(strokes.length){redoStack.push(strokes.pop());redraw();setActive();save();}};
      document.getElementById('wb-s9-a2-redo').onclick=()=>{if(redoStack.length){strokes.push(redoStack.pop());redraw();setActive();save();}};
      document.getElementById('wb-s9-a2-clear').onclick=()=>requestS9A2Clear(()=>{strokes=[];redoStack=[];redraw();setActive();save();});
      content.querySelectorAll('[data-tool]').forEach(button=>button.onclick=()=>{tool=button.dataset.tool;setActive();save();});
      content.querySelectorAll('[data-color]').forEach(button=>button.onclick=()=>{color=button.dataset.color;tool='draw';setActive();save();});
      content.querySelectorAll('[data-size]').forEach(button=>button.onclick=()=>{size=button.dataset.size;setActive();save();});
      document.getElementById('wb-written').oninput=event=>draft({strokes,text:event.target.value,tool,color,size});
      content.querySelectorAll('[data-example]').forEach(button=>button.onclick=()=>{const input=document.getElementById('wb-written');input.value=button.dataset.example;input.dispatchEvent(new Event('input',{bubbles:true}));input.focus();});
      if(!preview&&activityStarted)speakInstruction();redraw();setActive();window.addEventListener('resize',redraw,{once:true});
      return;
    }else if(s9Family){
      const canvas=document.getElementById('wb-canvas'),ctx=canvas.getContext('2d'),width=900,height=500;
      let strokes=structuredClone(state.draft?.strokes||[]),redoStack=[],stroke=null,erasing=false;
      let tool=state.draft?.tool==='eraser'?'eraser':'draw',color=state.draft?.color||'#183e63',size=state.draft?.size||'medium';
      const brush={small:4,medium:8,large:14},eraser={small:22,medium:34,large:50};
      const redraw=()=>{ctx.clearRect(0,0,width,height);for(const current of strokes){ctx.strokeStyle=current.color;ctx.lineWidth=current.width||5;ctx.lineCap='round';ctx.lineJoin='round';ctx.beginPath();current.points.forEach((point,index)=>index?ctx.lineTo(...point):ctx.moveTo(...point));ctx.stroke();}};
      const point=e=>{const rect=canvas.getBoundingClientRect();return [Math.max(0,Math.min(width,(e.clientX-rect.left)*width/rect.width)),Math.max(0,Math.min(height,(e.clientY-rect.top)*height/rect.height))];};
      const save=()=>draft({strokes,text:document.getElementById('wb-written').value,tool,color,size});
      const setActive=()=>{content.querySelectorAll('[data-tool]').forEach(button=>button.classList.toggle('is-active',button.dataset.tool===tool));content.querySelectorAll('[data-color]').forEach(button=>button.classList.toggle('is-active',button.dataset.color===color));content.querySelectorAll('[data-size]').forEach(button=>button.classList.toggle('is-active',button.dataset.size===size));document.getElementById('wb-s9-a1-undo').disabled=!strokes.length;document.getElementById('wb-s9-a1-redo').disabled=!redoStack.length;};
      const eraseAt=target=>{const radius=eraser[size],kept=strokes.filter(current=>!current.points.some(([x,y])=>Math.hypot(x-target[0],y-target[1])<=radius));if(kept.length!==strokes.length){redoStack=[];strokes=kept;redraw();setActive();save();}};
      canvas.onpointerdown=e=>{if(preview||busy)return;canvas.setPointerCapture(e.pointerId);const target=point(e);if(tool==='eraser'){erasing=true;eraseAt(target);return;}stroke={color,width:brush[size],points:[target]};strokes.push(stroke);redoStack=[];};
      canvas.onpointermove=e=>{if(erasing){eraseAt(point(e));return;}if(!stroke)return;stroke.points.push(point(e));if(stroke.points.length<3000)redraw();};
      const end=()=>{erasing=false;if(stroke){if(stroke.points.length===1)stroke.points.push([...stroke.points[0]]);stroke=null;redraw();setActive();save();}};canvas.onpointerup=end;canvas.onpointercancel=end;
      document.getElementById('wb-s9-a1-undo').onclick=()=>{if(strokes.length){redoStack.push(strokes.pop());redraw();setActive();save();}};
      document.getElementById('wb-s9-a1-redo').onclick=()=>{if(redoStack.length){strokes.push(redoStack.pop());redraw();setActive();save();}};
      document.getElementById('wb-s9-a1-clear').onclick=()=>requestS9A1Clear(()=>{strokes=[];redoStack=[];redraw();setActive();save();});
      content.querySelectorAll('[data-tool]').forEach(button=>button.onclick=()=>{tool=button.dataset.tool;setActive();save();});
      content.querySelectorAll('[data-color]').forEach(button=>button.onclick=()=>{color=button.dataset.color;tool='draw';setActive();save();});
      content.querySelectorAll('[data-size]').forEach(button=>button.onclick=()=>{size=button.dataset.size;setActive();save();});
      document.getElementById('wb-written').oninput=event=>draft({strokes,text:event.target.value,tool,color,size});
      if(!preview&&activityStarted)speakInstruction();redraw();setActive();window.addEventListener('resize',redraw);
      return;
    }
    const canvas=document.getElementById('wb-canvas'),ctx=canvas.getContext('2d');let strokes=structuredClone(state.draft.strokes||[]),stroke=null;
    const redraw=()=>{ctx.clearRect(0,0,900,500);for(const s of strokes){ctx.strokeStyle=s.color;ctx.lineWidth=5;ctx.lineCap='round';ctx.beginPath();s.points.forEach((p,i)=>i?ctx.lineTo(...p):ctx.moveTo(...p));ctx.stroke();}};
    const point=e=>{const r=canvas.getBoundingClientRect();return [Math.max(0,Math.min(900,(e.clientX-r.left)*900/r.width)),Math.max(0,Math.min(500,(e.clientY-r.top)*500/r.height))];};
    canvas.onpointerdown=e=>{if(preview||busy)return;canvas.setPointerCapture(e.pointerId);stroke={color:document.getElementById('wb-pen').value,points:[point(e)]};strokes.push(stroke);};
    canvas.onpointermove=e=>{if(!stroke)return;if(stroke.points.length<3000)stroke.points.push(point(e));redraw();};
    const end=()=>{if(stroke){if(stroke.points.length===1)stroke.points.push([...stroke.points[0]]);stroke=null;draft({strokes});}};canvas.onpointerup=end;canvas.onpointercancel=end;
    document.getElementById('wb-undo').onclick=()=>{strokes.pop();redraw();draft({strokes});};redraw();
  }
  async function record(){
    if(busy)return;busy=true;lock();let stream;
    try{
      stream=await window.Basahin.openMicrophone({audio:true});
      message(fil?'Nakikinig...':'Listening...');
      const audio=await window.Basahin.capture({button:document.getElementById('wb-basahin'),stream});
      stream.getTracks().forEach(t=>t.stop());message(fil?'Pinakikinggan ang iyong pagbasa…':'Checking your reading…');const form=new FormData();form.append('audio',audio,'reading.webm');await send(null,form);render();
    }catch(e){message(e.message||'Microphone unavailable. Please try again.',true);}finally{stream?.getTracks().forEach(t=>t.stop());busy=false;lock();}
  }
  async function aloud(){
    if(busy)return;busy=true;lock();
    await window.PabasaTemplateTts.speak({text:item().text,profile:'word',onEnd:async()=>{try{await send({action:oral().phase==='model'?'model_listened':'listened'});render();}catch(e){message(e.message,true);}finally{busy=false;lock();}},onError:e=>{message(e.message,true);busy=false;lock();}});
  }
  window.addEventListener('beforeunload',e=>{if(pictureReading)pictureGuidedAttempt?.controller.abort();activeRecorder?.stop();activeStream?.getTracks().forEach(t=>t.stop());stopReadAloud();if(!specializedBuilder&&busy){e.preventDefault();e.returnValue='';}});
  window.addEventListener('pagehide',()=>{if(pictureReading)pictureGuidedAttempt?.controller.abort();stopReadAloud();});
  if(lesson24Activity&&!preview&&!state.completed){
    const startLesson24=()=>{
      activityStarted=true;render();
      if(!instructionSpoken){
        instructionSpoken=true;
        playPrescribedAudio(instructionText,true).catch(error=>{if(error?.name!=='AbortError')console.error('Lesson 24 instruction audio failed',error);});
      }
    };
    if(g6Search)window.PabasaL24G6Start=startLesson24;
    else document.addEventListener('pabasa:l24-started',startLesson24,{once:true});
  }
  initializeLesson23Entry();
  render();
  initializeL22Entry();
  initializeSession9Entry();
})();
