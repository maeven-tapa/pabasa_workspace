/*
 * Presentation-only suppression for the audited Session 3 activities.
 * Activities opt in with their own exact feedback phrases, so instructions,
 * prompts, and similarly-shaped activities remain unaffected.
 */
(() => {
  const script = document.currentScript;
  if (!script) return;
  const activityKey = script.dataset.activityKey;
  if (activityKey) {
    const dataNode = document.querySelector('#activity-data,#shape-stamp-data,#shape-read-data,#handwriting-data,#lesson-seven-data,#lesson9-gawain1-data,#lesson9-gawain2-data,#lesson9-gawain3-data');
    try {
      const actualKey = JSON.parse(dataNode?.textContent || '{}').activity_key;
      if (actualKey && actualKey !== activityKey) return;
    } catch (_) {
      return;
    }
  }

  const defaultMessages = {
    'lesson8-gawain1a': ['Magaling!', 'Hindi iyon ang tamang pangalan ng larawan. Subukan muli magsalita.', 'Hindi narinig. Subukan muli.', 'Pakinggan ang salita.', 'May mali. Tingnan muli ang mga larawan at subukan ulit.', 'Natapos mo ang GAWAIN 1A: Letrang Ee.'],
    'lesson9-gawain2': ['Magaling!', 'Hindi iyon ang tamang pangalan ng larawan. Subukan muli magsalita.', 'Hindi narinig. Subukan muli.', 'Hindi tugma ang larawan sa pantig. Subukan muli!', 'Magaling! Natapos mo ang gawain.'],
  };
  let messages;
  try {
    const configured = script.dataset.feedbackMessages ? JSON.parse(script.dataset.feedbackMessages) : null;
    const detectedKey = activityKey || JSON.parse(document.querySelector('#activity-data,#lesson9-g2-data')?.textContent || '{}').activity_key;
    messages = new Set((configured || defaultMessages[detectedKey] || []).map(text => String(text).trim()));
  } catch (_) {
    return;
  }
  if (!messages.size) return;

  const style = document.createElement('style');
  style.textContent = '[data-session3-feedback-suppressed="true"]{visibility:hidden!important}';
  document.head.append(style);

  const mark = node => {
    if (!(node instanceof Element)) return;
    const text = node.textContent.trim();
    if (messages.has(text)) node.dataset.session3FeedbackSuppressed = 'true';
    else delete node.dataset.session3FeedbackSuppressed;
  };
  const inspect = node => {
    if (!(node instanceof Element)) return;
    mark(node);
    node.querySelectorAll?.('#status,#feedback,.status,.feedback,.hint,.done h1,.done p,.complete h1,.complete p').forEach(mark);
  };

  const start = () => {
    inspect(document.body);
    new MutationObserver(records => {
    for (const record of records) {
      if (record.type === 'characterData') mark(record.target.parentElement);
      else {
        mark(record.target);
        record.addedNodes.forEach(inspect);
      }
    }
    }).observe(document.body, {childList: true, subtree: true, characterData: true});
  };
  if (document.body) start();
  else document.addEventListener('DOMContentLoaded', start, {once: true});
})();
