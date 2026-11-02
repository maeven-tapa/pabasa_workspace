(() => {
  const notificationPane = document.getElementById('principalNotificationPane');
  const sidebar = document.getElementById('dashboardSidebar');
  const focusNotifications = () => {
    if (notificationPane?.classList.contains('show')) notificationPane.querySelector('.notif-close-btn')?.focus({preventScroll:true});
  };
  notificationPane?.addEventListener('shown.bs.offcanvas', focusNotifications);
  // On mobile, the shared Bootstrap trigger closes navigation while opening
  // notifications. Keep keyboard focus in the newly opened notification panel.
  sidebar?.addEventListener('hidden.bs.offcanvas', focusNotifications);
  document.addEventListener('keydown', event => {
    // The notification panel can outlive the mobile navigation focus trap or
    // its Clear confirmation dialog. Escape should still close the panel.
    if (event.key === 'Escape' && notificationPane?.classList.contains('show')
        && !document.querySelector('.modal.show, .modal[aria-modal="true"]')) {
      bootstrap.Offcanvas.getInstance(notificationPane)?.hide();
    }
  });
  document.querySelectorAll('[data-password-toggle]').forEach(button => button.addEventListener('click', () => {
    const input = document.getElementById(button.dataset.passwordToggle);
    const visible = input.type === 'password';
    input.type = visible ? 'text' : 'password';
    button.setAttribute('aria-pressed', String(visible));
    button.dataset.originalLabel ||= button.getAttribute('aria-label');
    button.setAttribute('aria-label', visible ? button.dataset.originalLabel.replace('Show', 'Hide') : button.dataset.originalLabel);
    button.querySelector('i').className = visible ? 'bi bi-eye-slash' : 'bi bi-eye';
  }));
  const collapse = document.getElementById('principalCollapse');
  function setCollapsed(value) {
    document.body.classList.toggle('admin-sidebar-collapsed', value);
    collapse?.setAttribute('aria-expanded', String(!value));
    collapse?.setAttribute('aria-label', value ? 'Expand sidebar' : 'Collapse sidebar');
    const icon = collapse?.querySelector('i');
    if (icon) icon.className = value ? 'bi bi-chevron-right' : 'bi bi-chevron-left';
  }
  try { setCollapsed(localStorage.getItem('pabasaPrincipalSidebarCollapsed') === '1'); } catch (_) { /* optional preference */ }
  collapse?.addEventListener('click', () => {
    const next = !document.body.classList.contains('admin-sidebar-collapsed');
    setCollapsed(next);
    try { localStorage.setItem('pabasaPrincipalSidebarCollapsed', next ? '1' : '0'); } catch (_) { /* optional preference */ }
  });
  document.querySelectorAll('.signature-nav-item.active').forEach(link => link.setAttribute('aria-current', 'page'));
  if (location.hash === '#awaiting-assignment') {
    const awaiting = document.getElementById('awaiting-assignment');
    if (awaiting) awaiting.open = true;
  }
  document.querySelectorAll('[data-export-form]').forEach(form => {
    form.addEventListener('submit', event => {
      if (!event.submitter?.name || event.submitter.name !== 'export') return;
      const status = document.getElementById('principalExportStatus');
      if (status) status.textContent = 'Preparing download. Larger reports may take a moment.';
      // Submit to the normal download response; failures retain their HTTP status.
    });
  });
})();
