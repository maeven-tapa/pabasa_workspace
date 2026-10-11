(()=>{'use strict';
  const esc=value=>String(value??'').replace(/[&<>"']/g,char=>({'&':'&amp;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));
  const show=({title='Magaling!',message='',backUrl='#',returnLabel='Bumalik sa Aking Aralin'}={})=>{
    if(document.getElementById('s8-completion-popup'))return;
    const popup=document.createElement('div');
    popup.id='s8-completion-popup';popup.className='s8-completion-popup';popup.setAttribute('role','dialog');popup.setAttribute('aria-modal','true');popup.setAttribute('aria-labelledby','s8-completion-popup-title');
    [...document.body.children].forEach(node=>{if(node!==popup){node.dataset.s8CompletionInert='';node.inert=true;node.setAttribute('aria-hidden','true');}});
    popup.innerHTML=`<section class="s8-completion-popup__card"><h2 class="s8-completion-popup__title" id="s8-completion-popup-title">${esc(title)}</h2><p class="s8-completion-popup__message">${esc(message)}</p><a class="s8-completion-popup__return" href="${esc(backUrl)}">${esc(returnLabel)}</a></section>`;
    document.body.appendChild(popup);popup.querySelector('a')?.focus();
  };
  const dedicatedCompletions=[
    ['.l23g2-page .panel.complete','Magaling!','Natapos mo ang Gawain 2.'],
    ['.l23g5-page .complete','Magaling!','Nahanap mo ang lahat ng salita.'],
    ['.l24g2-complete','Magaling!','Natapos mo ang Gawain 2.'],
    ['.l24g3-repeat-dialog-backdrop','Magaling!','Natapos mo ang Gawain 3.'],
  ];
  const showDedicatedCompletion=()=>{
    if(document.getElementById('s8-completion-popup'))return;
    const match=dedicatedCompletions.find(([selector])=>document.querySelector(selector));
    if(!match)return;
    show({title:match[1],message:match[2],backUrl:document.querySelector('a[href]')?.href||'#'});
  };
  window.Session8CompletionPopup={show,showDedicatedCompletion};
  new MutationObserver(showDedicatedCompletion).observe(document.documentElement,{childList:true,subtree:true});
  showDedicatedCompletion();
})();
