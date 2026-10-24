/* Small interactive enhancements for the full-stack storefront preview. */
(function () {
  var nodes = document.querySelectorAll('[data-reveal]');
  var reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  if (window.gsap && nodes.length && !reducedMotion) {
    window.gsap.from(nodes, { opacity: 0, y: 18, duration: 0.55, stagger: 0.08, ease: 'power2.out' });
  }

  var navToggle = document.querySelector('[data-foodwagon-nav-toggle]');
  var navPanel = document.getElementById('navbarSupportedContent');
  if (navToggle && navPanel) {
    navToggle.addEventListener('click', function () {
      var expanded = navToggle.getAttribute('aria-expanded') === 'true';
      navToggle.setAttribute('aria-expanded', String(!expanded));
      navPanel.classList.toggle('show', !expanded);
    });
  }

  var orderDialog = document.getElementById('orderDialog');
  document.querySelectorAll('[data-open-order]').forEach(function (button) {
    button.addEventListener('click', function () {
      if (orderDialog && !orderDialog.open) orderDialog.showModal();
    });
  });

  var accountDialog = document.getElementById('accountDialog');
  var accountTitle = document.getElementById('accountDialogTitle');
  document.querySelectorAll('[data-open-account]').forEach(function (button) {
    button.addEventListener('click', function () {
      var action = button.getAttribute('data-open-account') || 'Customer account';
      if (accountTitle) accountTitle.textContent = action + ' is not configured';
      if (accountDialog && !accountDialog.open) accountDialog.showModal();
    });
  });

  document.querySelectorAll('[data-close-dialog]').forEach(function (button) {
    button.addEventListener('click', function () {
      var dialog = button.closest('dialog');
      if (dialog && dialog.open) dialog.close();
    });
  });

  document.querySelectorAll('[data-order-tab]').forEach(function (tab) {
    tab.addEventListener('click', function () {
      var selected = tab.getAttribute('data-order-tab');
      document.querySelectorAll('[data-order-tab]').forEach(function (other) {
        other.setAttribute('aria-selected', String(other === tab));
      });
      document.querySelectorAll('[data-order-panel]').forEach(function (panel) {
        panel.hidden = panel.getAttribute('data-order-panel') !== selected;
      });
    });
  });
}());
