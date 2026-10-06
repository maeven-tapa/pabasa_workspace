(() => {
  const app = document.getElementById('app');
  if (!app) return;
  let progress = null;
  const preserve = () => {
    const current = app.querySelector('.numbered-progress');
    if (current) progress = current;
    else if (progress && app.querySelector('.progress') && progress.parentNode !== app) app.appendChild(progress);
  };
  new MutationObserver(preserve).observe(app, {childList: true, subtree: true});
  preserve();
})();
